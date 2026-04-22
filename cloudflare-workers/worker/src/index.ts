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
      // Canonical proxy pattern — new Request rebases URL while workerd
      // handles header/body normalization (Host, Content-Length, etc.).
      response = await fetch(new Request(origin.toString(), request));
    } catch (err) {
      console.error("upstream fetch error", err);
      response = new Response(`upstream error: ${err}`, { status: 502 });
    }

    const latencyMs = Date.now() - start;
    // Write runs on the background budget so the user's response returns
    // immediately. Verified to work end-to-end in `wrangler dev` local
    // mode — console.log inside the callback also reaches stdout.
    ctx.waitUntil(logEvent(env, request, response.clone(), latencyMs));
    return response;
  },
} satisfies ExportedHandler<Env>;

async function logEvent(env: Env, req: Request, res: Response, latencyMs: number): Promise<void> {
  const cf = req.cf;
  const colo = (cf?.colo as string | undefined) ?? "DEV";
  const country = (cf?.country as string | undefined) ?? "XX";
  const httpMethod = req.method;
  const path = new URL(req.url).pathname;
  const pathGroup = normalizePathGroup(path);
  const ua = (req.headers.get("user-agent") ?? "").slice(0, 128);

  // Use the InfluxDB SDK's Point builder for line-protocol formatting +
  // tag/field escaping, but POST via raw fetch. The SDK's WriteApi
  // (getWriteApi + writePoint + close) silently drops writes in Workers
  // — the close() promise resolves but no HTTP request actually hits the
  // server. Confirmed empirically against this demo and matches
  // influxdata/influxdb-client-js#170. A direct POST avoids the
  // WriteApi's async buffer/flush lifecycle and makes success/failure
  // observable.
  const point = new Point(env.MEASUREMENT || "worker_events")
    .tag("colo", colo)
    .tag("country", country)
    .tag("http_method", httpMethod)
    .tag("path_group", pathGroup)
    .intField("http_status", res.status)
    .floatField("latency_ms", latencyMs)
    .intField("bytes_out", Number(res.headers.get("content-length") ?? 0))
    .stringField("cf_ray", req.headers.get("cf-ray") ?? "")
    .stringField("ua", ua)
    .stringField("full_path", path.slice(0, 256))
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
    if (r.ok) {
      console.log("greptime write ok", r.status);
    } else {
      console.error("greptime write failed", r.status, await r.text());
    }
  } catch (err) {
    console.error("greptime write error", err);
  }
}

async function handleStats(request: Request, env: Env): Promise<Response> {
  const url = new URL(request.url);
  const windowMinutes = clamp(Number(url.searchParams.get("window")) || 5, 1, 60);
  const cf = request.cf;
  const requestedColo = url.searchParams.get("colo");
  const colo = requestedColo ?? (cf?.colo as string | undefined) ?? "DEV";

  // postgres.js over Hyperdrive. max=5 matches CF's recommendation for
  // Workers; fetch_types=false avoids a startup round-trip for type OIDs
  // (GreptimeDB's pg_type coverage isn't complete and the lookup would
  // add latency to the first query on every isolate).
  const sql = postgres(env.HYPERDRIVE.connectionString, {
    max: 5,
    fetch_types: false,
    prepare: false,
  });

  // Compute the window threshold in JS instead of doing interval arithmetic
  // in SQL — GreptimeDB's pg wire accepts neither `make_interval(...)` nor
  // `INTERVAL '1 minute' * n`. A plain epoch-ms bigint via
  // `to_timestamp_millis()` sidesteps both.
  const sinceMs = Date.now() - windowMinutes * 60_000;

  // sql.unsafe() with no params uses simple-query protocol (a plain Query
  // message), avoiding Parse/Bind. GreptimeDB's extended-query path
  // rejects postgres.js's type OIDs with `unknown_parameter_type`, so
  // simple-query is the safe option. Inputs are sanitized: windowMinutes
  // is clamped to [1, 60] integer; colo is single-quote escaped; the
  // table name (from env.MEASUREMENT, must match the write path) is
  // validated against a strict identifier allowlist.
  const escColo = colo.replace(/'/g, "''");
  const table = sanitizeIdent(env.MEASUREMENT || "worker_events");

  try {
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
    return new Response(`query error: ${err}`, { status: 500 });
  } finally {
    // Release the connection back to Hyperdrive's pool.
    await sql.end({ timeout: 5 });
  }
}

// High-cardinality paths like /api/users/42 would blow up GreptimeDB's
// primary key cardinality. Normalize numeric / UUID / long-hex segments to
// stable placeholders before they become a tag. In production, replace with
// your router's pattern matcher.
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

// MEASUREMENT is user-supplied via wrangler.toml; reject anything that
// isn't a plain identifier so we can safely interpolate into SQL.
function sanitizeIdent(s: string): string {
  if (!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(s)) {
    throw new Error(`invalid MEASUREMENT table name: ${JSON.stringify(s)}`);
  }
  return s;
}
