#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DOWN_ARGS=("$@")

echo "==> Stopping all services (Dify + monitoring)..."
if [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    docker compose \
        -f "$SCRIPT_DIR/docker-compose.yml" \
        --env-file "$SCRIPT_DIR/dify/.env" \
        -p dify \
        down ${DOWN_ARGS[@]+"${DOWN_ARGS[@]}"} || true
fi

echo "==> Done."
