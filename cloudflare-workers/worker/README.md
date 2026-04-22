# greptime-edge-logger — Worker

Reverse-proxy Worker that writes request events to GreptimeDB via the
InfluxDB v2 JS SDK, and reads them back on `/_stats` via Hyperdrive +
`postgres.js`. See the [demo README](../README.md) for the end-to-end
walkthrough; this file is a quick reference for worker-side details.

## How it runs

The whole demo runs under `docker compose`, including this Worker. The
[`Dockerfile`](Dockerfile) installs deps and launches `wrangler dev` in
local mode (workerd in-process). The compose service publishes port 8787.
From the parent directory:

```bash
docker compose up -d
# Worker is live on http://localhost:8787
```

Iteration loop when editing code:

```bash
docker compose up -d --build worker   # rebuild + restart worker only
docker compose logs -f worker
```

## Running on the host (escape hatch)

If you want node's faster edit-loop on your host, it still works — but
two values in [`wrangler.toml`](wrangler.toml) assume the compose
network's DNS:

- `GREPTIME_URL` → change `http://greptimedb:4000` to `http://localhost:4000`
- `[[hyperdrive]].localConnectionString` → change `@greptimedb:4003` to
  `@localhost:4003`

Then:

```bash
npm install
npm run dev
```

## Deploy to Cloudflare's edge

`wrangler deploy` needs CF credentials and runs against real Hyperdrive +
real public endpoints — not something the docker-compose stack fronts.

1. Install wrangler on your host: `npm i -g wrangler` (or use the one
   already in the container via `docker compose exec worker npx wrangler
   ...` with a `CLOUDFLARE_API_TOKEN` env var).
2. Create a Hyperdrive pointing at your **publicly reachable** GreptimeDB
   PG endpoint:

   ```bash
   wrangler hyperdrive create greptime-demo \
     --connection-string="postgres://<user>:<pass>@<public-host>:<port>/<db>"
   ```

3. Paste the returned `id` into `[[hyperdrive]].id` in `wrangler.toml`,
   and change `GREPTIME_URL` to your public HTTPS endpoint.
4. If the endpoint needs auth:

   ```bash
   wrangler secret put GREPTIME_USERNAME
   wrangler secret put GREPTIME_PASSWORD
   ```

5. `wrangler deploy`

How to expose GreptimeDB publicly — see the
[parent README's "Deploying to production"](../README.md#deploying-to-production)
section (recommended path is a cloudflared named tunnel with both HTTPS
and TCP routes).

## Config surface

`[vars]` in `wrangler.toml`:

| Var            | What                                                              |
|----------------|-------------------------------------------------------------------|
| `GREPTIME_URL` | HTTPS base URL of GreptimeDB (write path)                         |
| `GREPTIME_DB`  | Target database / InfluxDB bucket name                            |
| `ORIGIN_URL`   | Upstream the Worker proxies to (default `https://httpbin.org`)    |
| `MEASUREMENT`  | Line-protocol measurement / table name (default `worker_events`)  |

`[[hyperdrive]]` binding:
- `id` — the Hyperdrive resource id (ignored by `wrangler dev`)
- `localConnectionString` — where local dev connects instead

Secrets (`wrangler secret put ...`), only when the target endpoint
requires auth:
- `GREPTIME_USERNAME`, `GREPTIME_PASSWORD`

## What's in the code

- **Writes** — [`@influxdata/influxdb-client-browser`][influx-js]. The
  `-browser` package uses pure fetch (no `http`/`stream`/Node bindings),
  so it runs natively in the Workers runtime. Per-request writes use
  `batchSize: 1, flushInterval: 0` — no background buffer, each point
  flushes immediately on `writeApi.close()`.
- **Reads** — [`postgres.js`][postgres-js] via Hyperdrive
  (`env.HYPERDRIVE.connectionString`). `max: 5` is CF-recommended.
  `fetch_types: false` skips the `pg_type` bootstrap round-trip
  (GreptimeDB's pg_type support is thin and the lookup would add
  avoidable latency). `prepare: false` forces simple-query mode —
  GreptimeDB's extended-query protocol has rough edges; simple queries
  are safer.
- **Path normalization** — `normalizePathGroup()` collapses numeric,
  UUID, and long-hex segments to placeholders before they become a tag.
  Without this, `/api/users/:id` explodes into one tag value per id and
  tanks primary-key cardinality.

[influx-js]: https://github.com/influxdata/influxdb-client-js
[postgres-js]: https://github.com/porsager/postgres
