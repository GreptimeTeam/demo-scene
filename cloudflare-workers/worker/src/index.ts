// A Cloudflare Worker that:
//   - proxies every request to an origin and logs the event to GreptimeDB
//     via the InfluxDB v2 JS SDK (pure-fetch browser build, Workers-safe);
//   - exposes `/_stats` which queries GreptimeDB through Hyperdrive +
//     postgres.js to return edge analytics for a colo.
//
// Two GreptimeDB protocols in one Worker: HTTP line protocol for writes,
// PostgreSQL wire protocol for reads. Both are first-class on the
// GreptimeDB side; splitting by workload gives us familiar SDKs on both
// paths and sidesteps the V8-isolate TCP restriction without Hyperdrive on
// the hot write path.

import { Point } from "@influxdata/influxdb-client-browser";
import postgres from "postgres";

export interface Env {
  HYPERDRIVE: Hyperdrive;
  GREPTIME_URL: string;
  GREPTIME_DB: string;
  GREPTIME_USERNAME?: string;
  GREPTIME_PASSWORD?: string;
  ORIGIN_URL: string;
  MEASUREMENT: string;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/_stats") {
      return handleStats(request, env);
    }

    const start = Date.now();
    const origin = new URL(env.ORIGIN_URL || "https://httpbin.org");
    origin.pathname = url.pathname;
    origin.search = url.search;

    let response: Response;
    try {
      // `new Request(url, request)` rebases the URL; workerd handles
      // header/body normalization (Host, Content-Length, etc.).
      response = await fetch(new Request(origin.toString(), request));
    } catch (err) {
      console.error("upstream fetch error", err);
      response = new Response("bad gateway", { status: 502 });
    }

    const latencyMs = Date.now() - start;
    // logEvent only reads status + headers, no body, so no clone needed.
    ctx.waitUntil(logEvent(env, request, response, latencyMs));
    return response;
  },
} satisfies ExportedHandler<Env>;

async function logEvent(env: Env, req: Request, res: Response, latencyMs: number): Promise<void> {
  const cf = req.cf;
  const colo = (cf?.colo as string | undefined) ?? "DEV";
  const country = (cf?.country as string | undefined) ?? "XX";
  const httpMethod = req.method;
  const reqUrl = new URL(req.url);
  const path = reqUrl.pathname;
  const pathGroup = normalizePathGroup(path);
  const fullPath = (path + reqUrl.search).slice(0, 256);
  const ua = (req.headers.get("user-agent") ?? "").slice(0, 128);

  // Use the SDK's Point builder for line-protocol serialization, but POST
  // via raw fetch. The SDK's WriteApi silently drops writes in Workers —
  // close() resolves but no HTTP request leaves — matches
  // influxdata/influxdb-client-js#170.
  //
  // Tags map to PRIMARY KEY columns in GreptimeDB. Only low-cardinality
  // filter dimensions are tagged; path_group is a field (see schema.sql).
  const point = new Point(env.MEASUREMENT || "worker_events")
    .tag("colo", colo)
    .tag("country", country)
    .tag("http_method", httpMethod)
    .intField("http_status", res.status)
    .floatField("latency_ms", latencyMs)
    .intField("bytes_out", parseBytesOut(res.headers.get("content-length")))
    .stringField("path_group", pathGroup)
    .stringField("cf_ray", req.headers.get("cf-ray") ?? "")
    .stringField("ua", ua)
    .stringField("full_path", fullPath)
    .timestamp(BigInt(Date.now()) * 1_000_000n);

  const line = point.toLineProtocol();
  if (!line) {
    console.error("greptime: empty line protocol (point had no fields?)");
    return;
  }

  const base = env.GREPTIME_URL.replace(/\/$/, "");
  const db = encodeURIComponent(env.GREPTIME_DB || "public");
  const url = `${base}/v1/influxdb/api/v2/write?org=greptime&bucket=${db}&precision=ns`;
  const headers: Record<string, string> = { "Content-Type": "text/plain; charset=utf-8" };
  if (env.GREPTIME_USERNAME && env.GREPTIME_PASSWORD) {
    headers["Authorization"] = `token ${env.GREPTIME_USERNAME}:${env.GREPTIME_PASSWORD}`;
  }

  try {
    const r = await fetch(url, { method: "POST", headers, body: line });
    if (!r.ok) {
      console.error("greptime write failed", r.status, await r.text());
    }
  } catch (err) {
    console.error("greptime write error", err);
  }
}

async function handleStats(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  // `?window=0` should clamp to 1 (lower bound), not silently become the
  // default 5 — so only fall back when the param is absent or non-numeric.
  const windowParam = url.searchParams.get("window");
  const parsedWindow = windowParam == null ? NaN : Number(windowParam);
  const windowMinutes = clamp(Number.isFinite(parsedWindow) ? parsedWindow : 5, 1, 60);

  // colo is interpolated into SQL (escaped); validate the shape strictly
  // so we never send arbitrary strings to the DB. "DEV" is the Miniflare
  // local-dev default; real CF colos are 3-letter uppercase codes.
  const cf = request.cf;
  const requestedColo = url.searchParams.get("colo");
  const colo = requestedColo ?? (cf?.colo as string | undefined) ?? "DEV";
  if (!/^[A-Z]{3,4}$/.test(colo)) {
    return new Response("invalid colo (expected 3-4 uppercase letters)", { status: 400 });
  }

  // Three Workers-specific knobs:
  //   prepare: false     — GreptimeDB's pg extended-query rejects type
  //                        OIDs with `unknown_parameter_type`; combined
  //                        with sql.unsafe() below this forces simple-
  //                        query protocol.
  //   fetch_types: false — skip the pg_type bootstrap (GreptimeDB's
  //                        coverage is thin).
  //   max: 5             — CF-recommended cap for Workers.
  const sql = postgres(env.HYPERDRIVE.connectionString, {
    max: 5,
    fetch_types: false,
    prepare: false,
  });

  // GreptimeDB's pg wire accepts neither `make_interval(...)` nor
  // `INTERVAL '1 minute' * n`. Compute the threshold in JS, pass via
  // `to_timestamp_millis()`.
  const sinceMs = Date.now() - windowMinutes * 60_000;

  try {
    // sql.unsafe(string) with no params uses simple-query protocol, which
    // GreptimeDB tolerates. Inputs are sanitized: windowMinutes clamped,
    // colo regex-validated above, table name allowlist-checked.
    // sanitizeIdent runs inside try{} so a bad MEASUREMENT returns a
    // controlled 500 via catch and still runs finally.
    const escColo = colo.replace(/'/g, "''");
    const table = sanitizeIdent(env.MEASUREMENT || "worker_events");
    const rows = await sql.unsafe(`
      SELECT
        path_group,
        count(*) AS requests,
        approx_percentile_cont(latency_ms, 0.95) AS p95_ms,
        sum(CASE WHEN http_status >= 400 THEN 1 ELSE 0 END) AS errors
      FROM ${table}
      WHERE ts > to_timestamp_millis(${sinceMs})
        AND colo = '${escColo}'
      GROUP BY path_group
      ORDER BY p95_ms DESC
      LIMIT 20
    `);
    return Response.json({ colo, window_minutes: windowMinutes, rows });
  } catch (err) {
    console.error("stats query error", err);
    return new Response("stats query failed", { status: 500 });
  } finally {
    // A throw from sql.end() in `finally` would override the try's
    // Response — isolate the shutdown so cleanup failures don't surface.
    try {
      await sql.end({ timeout: 5 });
    } catch (e) {
      console.error("sql.end error", e);
    }
  }
}

// High-cardinality path segments (IDs, UUIDs) as tags explode PK
// cardinality. Collapse numeric / UUID / long-hex segments before tagging.
// Swap for your router's pattern matcher in production.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const NUMERIC_RE = /^\d+$/;
const HEX_RE = /^[0-9a-f]{16,}$/i;
const MAX_SEGMENTS = 8;

function normalizePathGroup(path: string): string {
  const segments = path.split("/").slice(0, MAX_SEGMENTS + 1);
  const normalized = segments.map((seg) => {
    if (!seg) return seg;
    if (UUID_RE.test(seg)) return ":uuid";
    if (NUMERIC_RE.test(seg)) return ":id";
    if (HEX_RE.test(seg)) return ":hex";
    return seg;
  });
  return normalized.join("/") || "/";
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, n));
}

// Coerce non-finite / negative / missing Content-Length to 0 so the
// BIGINT column never sees NaN.
function parseBytesOut(raw: string | null): number {
  if (raw == null) return 0;
  const n = Number(raw);
  return Number.isFinite(n) && n >= 0 ? Math.trunc(n) : 0;
}

// MEASUREMENT comes from wrangler.toml and is interpolated into SQL;
// allow only plain identifiers.
function sanitizeIdent(s: string): string {
  if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(s)) {
    throw new Error(`invalid MEASUREMENT table name: ${JSON.stringify(s)}`);
  }
  return s;
}
