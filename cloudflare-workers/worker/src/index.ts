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

import { InfluxDB, Point } from "@influxdata/influxdb-client-browser";
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
      response = await fetch(origin.toString(), {
        method: request.method,
        headers: request.headers,
        body: request.method === "GET" || request.method === "HEAD" ? undefined : request.body,
        redirect: "manual",
      });
    } catch (err) {
      response = new Response(`upstream error: ${err}`, { status: 502 });
    }

    const latencyMs = Date.now() - start;
    ctx.waitUntil(logEvent(env, request, response.clone(), latencyMs));
    return response;
  },
} satisfies ExportedHandler<Env>;

async function logEvent(env: Env, req: Request, res: Response, latencyMs: number): Promise<void> {
  const cf = req.cf;
  const colo = (cf?.colo as string | undefined) ?? "DEV";
  const country = (cf?.country as string | undefined) ?? "XX";
  const method = req.method;
  const path = new URL(req.url).pathname;
  const pathGroup = normalizePathGroup(path);
  const ua = (req.headers.get("user-agent") ?? "").slice(0, 128);

  // GreptimeDB's InfluxDB v2 compat accepts the org as arbitrary (it has no
  // concept of orgs), so we pass a stable placeholder. The bucket maps to
  // the target database.
  const base = env.GREPTIME_URL.replace(/\/$/, "");
  const clientOptions: { url: string; token?: string } = {
    url: `${base}/v1/influxdb`,
  };
  if (env.GREPTIME_USERNAME && env.GREPTIME_PASSWORD) {
    clientOptions.token = `${env.GREPTIME_USERNAME}:${env.GREPTIME_PASSWORD}`;
  }
  const client = new InfluxDB(clientOptions);
  // batchSize=1 + flushInterval=0 makes each writePoint flush immediately —
  // the right shape for a per-request Worker, not a long-lived server.
  const writeApi = client.getWriteApi("greptime", env.GREPTIME_DB || "public", "ns", {
    batchSize: 1,
    flushInterval: 0,
    maxRetries: 0,
  });

  const point = new Point(env.MEASUREMENT || "worker_events")
    .tag("colo", colo)
    .tag("country", country)
    .tag("method", method)
    .tag("path_group", pathGroup)
    .intField("status", res.status)
    .floatField("latency_ms", latencyMs)
    .intField("bytes_out", Number(res.headers.get("content-length") ?? 0))
    .stringField("cf_ray", req.headers.get("cf-ray") ?? "")
    .stringField("ua", ua)
    .stringField("full_path", path.slice(0, 256))
    .timestamp(BigInt(Date.now()) * 1_000_000n);

  try {
    writeApi.writePoint(point);
    await writeApi.close();
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

  try {
    const rows = await sql`
      SELECT
        path_group,
        count(*)::int AS requests,
        round(approx_percentile_cont(latency_ms, 0.95)::numeric, 1) AS p95_ms,
        sum(CASE WHEN status >= 400 THEN 1 ELSE 0 END)::int AS errors
      FROM worker_events
      WHERE ts > now() - make_interval(mins => ${windowMinutes})
        AND colo = ${colo}
      GROUP BY path_group
      ORDER BY p95_ms DESC NULLS LAST
      LIMIT 20
    `;
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
