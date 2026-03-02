#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Stopping Dify..."
if [ -f "$SCRIPT_DIR/dify/docker-compose.yaml" ]; then
    docker compose \
        -f "$SCRIPT_DIR/dify/docker-compose.yaml" \
        -f "$SCRIPT_DIR/dify-compose-override.yml" \
        --env-file "$SCRIPT_DIR/dify/.env" \
        -p dify \
        down || true
fi

echo "==> Stopping monitoring stack..."
docker compose -f "$SCRIPT_DIR/docker-compose.yml" down

echo "==> Done. Add -v flag to the commands above to also remove volumes."
