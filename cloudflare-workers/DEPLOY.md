# Deploying to Cloudflare's real edge

Two paths, pick based on what you want to prove:

- **Path A — smoke-test writes only.** Free account, no domain needed.
  Hyperdrive isn't configured, so `/_stats` will fail on real edge, but
  writes flow end-to-end: real CF edge → `trycloudflare` quick tunnel →
  your local GreptimeDB. Good for first-time verification, ~5 minutes.
- **Path B — full production.** Writes + Hyperdrive reads. Needs a
  domain on Cloudflare for the named tunnel.

## Prereqs on the host

- [`cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
- Node ≥ 20 + `npm`
- `wrangler` (`npm i -g wrangler`)
- A free [Cloudflare account](https://dash.cloudflare.com/sign-up),
  then `wrangler login`

Verify:

```bash
cloudflared --version     # >= 2024.x
node --version            # >= v20
wrangler --version        # >= 3.x
wrangler whoami           # should print your CF account
```

## Path A — writes only

### 1. Expose local GreptimeDB via a quick tunnel

In a terminal that stays open:

```bash
cloudflared tunnel --url http://localhost:4000
```

Copy the `https://<random>.trycloudflare.com` URL it prints.

### 2. Edit `worker/wrangler.toml`

- `GREPTIME_URL = "https://<random>.trycloudflare.com"` (from step 1)
- `ORIGIN_URL   = "https://echo.hoppscotch.io/"` (or any public origin;
  the in-network `origin:8080` won't resolve from the real edge)
- Comment out the entire `[[hyperdrive]]` block — its placeholder id
  fails CF's deploy-time validation

### 3. Install deps on host and deploy

```bash
cd worker
npm ci
npx wrangler deploy
```

`npm ci` is required on the host before `wrangler deploy`. The demo runs
in docker so the host has no `node_modules`, but `wrangler` bundles with
host-side esbuild.

### 4. Hit the Worker for real and verify

```bash
WORKER=https://greptime-edge-logger.<your-account>.workers.dev
for i in {1..20}; do curl -s -o /dev/null "$WORKER/anything?i=$i"; done

curl -s "http://localhost:4000/v1/sql?db=public" \
  --data-urlencode "sql=SELECT ts, cf_ray, colo, full_path FROM worker_events ORDER BY ts DESC LIMIT 5"
```

**Success signal**: recent rows show a non-empty 16-char hex `cf_ray`
(e.g. `9f0469ebeb372ab6`). That's a real CF-Ray from Cloudflare's edge.
**Don't trust `colo` alone** — Miniflare's local dev populates it via
geo-IP (e.g. `LAX`), so matching `colo` can come from either source.

## Path B — full production (Hyperdrive + reads)

The full read+write path needs GreptimeDB **publicly reachable** — HTTPS
for writes, TCP for Hyperdrive's pg connection. Simplest: a Cloudflare
[named tunnel][named-tunnel] with both ingress rules, so traffic stays
inside Cloudflare.

[named-tunnel]: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

### 1. Create the tunnel + DNS routes

```bash
cloudflared tunnel create greptime
cloudflared tunnel route dns greptime greptime-http.example.com
cloudflared tunnel route dns greptime greptime-pg.example.com
```

`~/.cloudflared/config.yml`:

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

Run: `cloudflared tunnel run greptime`.

### 2. Create Hyperdrive + wire up wrangler.toml

```bash
cd worker
npm ci
npx wrangler hyperdrive create greptime-demo \
  --connection-string="postgres://greptime:greptime@greptime-pg.example.com:4003/public"
```

Paste the returned id into `[[hyperdrive]].id` and set
`GREPTIME_URL = "https://greptime-http.example.com"`.

If the endpoint needs auth:

```bash
npx wrangler secret put GREPTIME_USERNAME
npx wrangler secret put GREPTIME_PASSWORD
```

### 3. Apply the schema + deploy

```bash
psql "postgres://greptime:greptime@greptime-pg.example.com:4003/public" \
  -f ../schema.sql
npx wrangler deploy
```

### 4. Verify

Same as Path A, plus the read path:

```bash
curl "$WORKER/_stats?window=5" | jq
```

## Gotchas we've hit

- **`npm ci` on host is mandatory before `wrangler deploy`.** Demo lives
  in docker; deploy doesn't.
- **Hyperdrive placeholder id fails deploy with `[code: 10157]`.** CF
  validates binding ids at deploy time. Comment the block out (Path A)
  or replace with a real id (Path B).
- **`trycloudflare.com` URLs change on restart and have no SLA.** Only
  for smoke tests. Anything longer, use a named tunnel.
- **Don't use `colo` to prove real-edge delivery.** Miniflare populates
  it via geo-IP. Use `cf_ray` (non-empty 16-char hex) instead.
- **Observability**: Worker → Observability tab in the CF dashboard
  surfaces `console.error` from the real edge in real time. Enable it
  before debugging write failures.
