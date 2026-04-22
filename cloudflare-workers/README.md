# Cloudflare Workers + GreptimeDB

A demo of a Cloudflare Worker that uses GreptimeDB as its **event / log /
time-series store** — the shape Cloudflare Workers currently has no
first-party answer for (D1 is SQLite; Analytics Engine is lossy with
rigid cardinality; KV and R2 aren't the right tool).

The Worker speaks **two GreptimeDB protocols**, one per workload:

- **Writes** — the official InfluxDB v2 JS SDK
  ([`@influxdata/influxdb-client-browser`][influx-js]) over HTTP, against
  GreptimeDB's InfluxDB line-protocol endpoint. Pure fetch, no TCP, no
  connection pool — stateless write path.
- **Reads** — [Cloudflare Hyperdrive][hyperdrive] + [postgres.js][pg-js]
  over GreptimeDB's PostgreSQL wire endpoint. The CF-native path for SQL
  queries from Workers, matching the pattern of every provider on CF's
  [third-party database integrations page][cf-third-party].

[influx-js]: https://github.com/influxdata/influxdb-client-js
[hyperdrive]: https://developers.cloudflare.com/hyperdrive/
[pg-js]: https://github.com/porsager/postgres
[cf-third-party]: https://developers.cloudflare.com/workers/databases/third-party-integrations/

## Architecture

```
                    +-----------------------------------------------+
                    |  docker-compose stack                         |
                    |                                               |
  +--------+        |  +-------------+                              |
  | client |-------->--| Worker      |  (reverse proxy +            |
  |        |<--------<-| :8787       |   event logger)              |
  +--------+        |  +--+--------+-+                              |
                    |     | write  ^ read                           |
                    |     v  path  | path                           |
                    |  +-----------+----------+   +--------------+  |
                    |  | GreptimeDB           |<--| Grafana      |  |
                    |  |  :4000 HTTP/InfluxDB |   |   :3000      |  |
                    |  |  :4003 pg wire       |   | (mysql proto)|  |
                    |  +----------------------+   +--------------+  |
                    +-----------------------------------------------+

  Write: Worker -> InfluxDB v2 SDK  -> GreptimeDB /v1/influxdb
  Read:  Worker -> Hyperdrive (pg)  -> GreptimeDB :4003
```

Everything is containerized. No host-side `npm`, `wrangler`, or Node is
required to run the demo.

## Quick Start

```bash
cd cloudflare-workers
docker compose up -d
```

Four services come up:
- `greptimedb` — the database (HTTP on 4000, pg wire on 4003, MySQL on 4002)
- `init-schema` — applies [`schema.sql`](schema.sql), exits after
- `worker` — the Cloudflare Worker under `wrangler dev`, published on 8787
- `grafana` — on 3000

Generate traffic:

```bash
curl http://localhost:8787/anything?a=1
curl http://localhost:8787/status/404
curl http://localhost:8787/delay/1
for i in $(seq 1 50); do curl -s "http://localhost:8787/anything?i=$i" > /dev/null; done
```

Query events from the edge (this goes Worker → Hyperdrive → GreptimeDB
pg wire):

```bash
curl "http://localhost:8787/_stats?window=5" | jq
```

Typical output:

```json
{
  "colo": "DEV",
  "window_minutes": 5,
  "rows": [
    { "path_group": "/delay/:id", "requests": 4, "p95_ms": 1012.3, "errors": 0 },
    { "path_group": "/anything",  "requests": 50, "p95_ms": 120.1, "errors": 0 }
  ]
}
```

Query directly against GreptimeDB (bypasses the Worker):

```bash
curl -s "http://localhost:4000/v1/sql?db=public" \
  --data-urlencode "sql=SELECT count(*) FROM worker_events"
```

Open Grafana: http://localhost:3000 (anonymous viewer by default). The
**Edge Traffic (CF Workers → GreptimeDB)** dashboard is pre-provisioned
with 8 panels.

## Iterating on Worker code

Edit files under [`worker/src/`](worker/src/) and rebuild only the worker:

```bash
docker compose up -d --build worker
docker compose logs -f worker
```

If you'd rather skip the container for faster edit-loop, see
[`worker/README.md`](worker/README.md#running-on-the-host-escape-hatch).

## Deploying to production

`wrangler deploy` pushes the Worker to Cloudflare's real edge. For that to
work, GreptimeDB needs to be **publicly reachable** — an HTTPS endpoint for
writes and a TCP endpoint for Hyperdrive's pg connection.

Recommended path — use a Cloudflare [named tunnel][named-tunnel] with two
routes. Everything stays inside Cloudflare's network.

### 1. Self-host GreptimeDB

Any public VM works. The compose stack in this repo is a reasonable
starting point (optionally with TLS terminated at your reverse proxy).

### 2. Create a named tunnel and route HTTPS + TCP

```bash
cloudflared tunnel create greptime
cloudflared tunnel route dns greptime greptime-http.example.com
cloudflared tunnel route dns greptime greptime-pg.example.com
```

In `~/.cloudflared/config.yml`:

```yaml
tunnel: <tunnel-id>
credentials-file: /root/.cloudflared/<tunnel-id>.json
ingress:
  - hostname: greptime-http.example.com
    service: http://127.0.0.1:4000
  - hostname: greptime-pg.example.com
    service: tcp://127.0.0.1:4003
  - service: http_status:404
```

### 3. Create the Hyperdrive config

```bash
cd worker
npm install   # only needed on the host for wrangler deploy
npx wrangler hyperdrive create greptime-demo \
  --connection-string="postgres://greptime:greptime@greptime-pg.example.com:4003/public"
```

Paste the returned `id` into `[[hyperdrive]].id` in
[`wrangler.toml`](worker/wrangler.toml), and set
`GREPTIME_URL = "https://greptime-http.example.com"`.

### 4. Secrets (if your GreptimeDB requires auth)

```bash
npx wrangler secret put GREPTIME_USERNAME
npx wrangler secret put GREPTIME_PASSWORD
```

### 5. Apply the schema + deploy

```bash
psql "postgres://greptime:greptime@greptime-pg.example.com:4003/public" \
  -f ../schema.sql
npx wrangler deploy
```

[named-tunnel]: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

## How it works

### Write path — InfluxDB v2 SDK, pure fetch

The Worker builds a `Point` per request and flushes a single line-protocol
record. `@influxdata/influxdb-client-browser` is a pure-fetch build —
`FetchTransport` uses `fetch` + `AbortController` + `ReadableStream` only —
so it runs in the Workers V8 isolate with zero Node compat shims on this
path.

```ts
import { InfluxDB, Point } from "@influxdata/influxdb-client-browser";

const client = new InfluxDB({ url: `${base}/v1/influxdb`, token: "user:pass" });
const writeApi = client.getWriteApi("greptime", "public", "ns", {
  batchSize: 1, flushInterval: 0, maxRetries: 0,
});

const point = new Point("worker_events")
  .tag("colo", "DFW")
  .tag("path_group", "/api/users/:id")
  .intField("status", 200)
  .floatField("latency_ms", 42.5)
  .timestamp(BigInt(Date.now()) * 1_000_000n);

writeApi.writePoint(point);
await writeApi.close();
```

GreptimeDB's InfluxDB v2 compat:
- URL: `${base}/v1/influxdb`
- Token: `username:password` (org ignored — pass any string like `"greptime"`)
- Bucket: your database name

### Read path — Hyperdrive + postgres.js

Hyperdrive is CF's pooling proxy for TCP databases. It exposes a
PG-compatible interface to Workers; standard `postgres.js` works.
Worker-specific knobs worth calling out:

```ts
import postgres from "postgres";
const sql = postgres(env.HYPERDRIVE.connectionString, {
  max: 5,             // CF-recommended cap for Workers
  fetch_types: false, // skip pg_type bootstrap (GreptimeDB's coverage is thin)
  prepare: false,     // simple-query mode — safer with GreptimeDB's pg wire
});
```

Three gotchas:

1. **`prepare: false`** — GreptimeDB's extended query protocol
   (parse/bind/execute) has rough edges. Simple-query mode avoids surprises;
   the caching win is small for ad-hoc queries anyway.
2. **`fetch_types: false`** — postgres.js bootstraps by querying
   `pg_type`. GreptimeDB's `pg_type` view is minimal, and the bootstrap
   can fail or stall.
3. **`max: 5`** — Workers are ephemeral. Many open connections per
   invocation defeats Hyperdrive's pooling.

### `ctx.waitUntil` — don't block the response

```ts
ctx.waitUntil(logEvent(env, request, response.clone(), latencyMs));
return response;
```

Logs run on the Worker's background budget; the user's response returns
immediately. Write failures print to `console.error` and never surface to
the client.

### Path cardinality — the production gotcha

High-cardinality path segments (IDs, UUIDs) as tag values explode
primary-key cardinality. The Worker collapses numeric / UUID / long-hex
segments to placeholders before tagging:

```
/api/users/42                                  -> /api/users/:id
/objects/550e8400-e29b-41d4-a716-446655440000  -> /objects/:uuid
/blob/3f786850e387550fdab836ed7e6dc881         -> /blob/:hex
```

Under-normalizing is the #1 way to get bad time-series performance. In
production, replace the ad-hoc regex in `normalizePathGroup()` with your
router's pattern matcher.

## Example queries

See [`queries.sql`](queries.sql) for seven canonical queries against
`worker_events`: per-minute QPS by colo, p50/p95/p99 by route, error-rate
timeseries, top slow endpoints, traffic by country, colo distribution,
and recent-errors drilldown.

> **Quoting note:** HTTP SQL and PG wire both use double quotes for
> identifiers. The Grafana MySQL datasource uses backticks. Don't mix
> them between panels and the SQL console or results go silently empty.

## Production considerations

- **Batching.** One SDK write per request is fine into the low thousands
  of RPS. At higher volume, pipe events through a [Cloudflare
  Queue][queues] and batch-write from a consumer — the InfluxDB SDK
  supports batched writes natively.
- **Sampling.** Log all errors, sample 2xx aggressively.
- **TTL.** [`schema.sql`](schema.sql) sets `ttl = '30d'`. Adjust per
  retention needs.
- **Partitioning.** High-volume setups benefit from time partitioning —
  see [GreptimeDB docs][gdb-partition].
- **Why not the GreptimeDB TypeScript ingester?** The official
  [`@greptime/ingester`][gti] uses `@grpc/grpc-js` (Node-only) and
  requires Node 20 APIs; it does not run in Workers today. The InfluxDB
  v2 browser SDK covers the ingestion case cleanly against a
  GreptimeDB-native endpoint. A fetch-based `@greptime/ingester-web` is
  mentioned in the SDK roadmap and would be the natural long-term fix.

[queues]: https://developers.cloudflare.com/queues/
[gdb-partition]: https://docs.greptime.com/user-guide/deployments-administration/manage-data/table-sharding
[gti]: https://github.com/GreptimeTeam/greptimedb-ingester-ts

## Appendix: getting listed on `developers.cloudflare.com`

Roadmap for pushing this onto Cloudflare's
[third-party integrations page][cf-third-party]:

1. **Ship this demo** — reproducible reference implementation.
2. **Publish a getting-started guide** on greptime.com covering the CF
   Workers path, with a stable URL.
3. **PR to [`cloudflare/cloudflare-docs`][cf-docs]** adding a page under
   `src/content/docs/workers/databases/third-party-integrations/`. Mirror
   existing provider pages (overview + snippet + link out).
4. **DevRel outreach** — tag the PR in [CF's Developer Discord][cf-discord]
   or reach out directly; review cycles are faster with a champion.

[cf-docs]: https://github.com/cloudflare/cloudflare-docs
[cf-discord]: https://discord.cloudflare.com/

## Cleanup

```bash
docker compose down -v
```
