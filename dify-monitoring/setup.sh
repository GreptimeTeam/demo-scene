#!/usr/bin/env bash
set -euo pipefail

DIFY_VERSION="${DIFY_VERSION:-1.13.0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  Dify + GreptimeDB Monitoring Demo Setup"
echo "============================================"
echo ""

# --- Prerequisites ---
command -v docker >/dev/null 2>&1 || { echo "Error: docker is required but not found."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "Error: docker compose v2 is required."; exit 1; }

# --- Download Dify ---
if [ ! -d "$SCRIPT_DIR/dify" ]; then
    echo "==> Downloading Dify ${DIFY_VERSION}..."
    tmpdir=$(mktemp -d)
    curl -sL "https://github.com/langgenius/dify/archive/refs/tags/${DIFY_VERSION}.tar.gz" \
        | tar xz -C "$tmpdir" --strip-components=1
    mv "$tmpdir/docker" "$SCRIPT_DIR/dify"
    rm -rf "$tmpdir"
    echo "    Done."
else
    echo "==> dify/ already exists, skipping download."
fi

# --- Configure Dify .env ---
echo "==> Configuring Dify environment..."
cd "$SCRIPT_DIR/dify"
if [ ! -f .env ]; then
    cp .env.example .env
fi

# Helper: set or append an env var
set_env() {
    local key="$1" val="$2" file=".env"
    if grep -q "^${key}=" "$file"; then
        sed -i.bak "s|^${key}=.*|${key}=${val}|" "$file"
    else
        echo "${key}=${val}" >> "$file"
    fi
}

set_env "ENABLE_OTEL"                  "true"
set_env "OTLP_BASE_ENDPOINT"          "http://otel-collector:4318"
set_env "OTEL_SAMPLING_RATE"           "1.0"
set_env "OTEL_METRIC_EXPORT_INTERVAL"  "15000"

rm -f .env.bak
cd "$SCRIPT_DIR"
echo "    OTEL enabled, exporting to otel-collector:4318."

# --- Start all services (Dify + monitoring) ---
echo "==> Starting all services (Dify + GreptimeDB + OTel Collector + Grafana)..."
docker compose \
    -f "$SCRIPT_DIR/docker-compose.yml" \
    --env-file "$SCRIPT_DIR/dify/.env" \
    -p dify \
    up -d

echo ""
echo "============================================"
echo "  All services are starting up!"
echo "============================================"
echo ""
echo "  Dify UI:              http://localhost"
echo "  Grafana:              http://localhost:3000  (admin / admin)"
echo "  GreptimeDB Dashboard: http://localhost:4000/dashboard"
echo "  GreptimeDB MySQL:     mysql -h 127.0.0.1 -P 4002"
echo ""
echo "  View collector logs:  docker compose logs -f otel-collector"
echo "  Stop everything:      ./teardown.sh"
echo ""
echo "  Traces & metrics are collected via Dify's native OTEL instrumentation."
echo "  Container logs (api, worker, nginx) are collected via Docker fluentd driver."
echo ""
echo "==> Initializing Flow aggregations in background..."
echo "    (waiting for traces table to appear, then creating flows)"
echo "    Log: /tmp/init-flow.log"
"$SCRIPT_DIR/init-flow.sh" > /tmp/init-flow.log 2>&1 &
echo ""
