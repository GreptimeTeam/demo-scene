#!/usr/bin/env bash
set -euo pipefail

# GreptimeDB HTTP SQL endpoint
GREPTIME_URL="${GREPTIME_URL:-http://localhost:4000}"
DB="public"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-600}"
WAIT_INTERVAL_SECONDS="${WAIT_INTERVAL_SECONDS:-2}"
SQL_FILE="${SQL_FILE:-$(dirname "$0")/flows.sql}"

if ! [[ "$WAIT_TIMEOUT_SECONDS" =~ ^[0-9]+$ ]] || [ "$WAIT_TIMEOUT_SECONDS" -lt 0 ]; then
    echo "ERROR: WAIT_TIMEOUT_SECONDS must be a non-negative integer, got: ${WAIT_TIMEOUT_SECONDS}"
    exit 1
fi
if ! [[ "$WAIT_INTERVAL_SECONDS" =~ ^[0-9]+$ ]] || [ "$WAIT_INTERVAL_SECONDS" -le 0 ]; then
    echo "ERROR: WAIT_INTERVAL_SECONDS must be a positive integer, got: ${WAIT_INTERVAL_SECONDS}"
    exit 1
fi

sql() {
    local stmt="$1"
    echo "  -> $(echo "$stmt" | head -1 | cut -c1-80)..."
    local resp
    resp=$(curl -sf -X POST "${GREPTIME_URL}/v1/sql?db=${DB}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "sql=${stmt}" 2>&1) || {
        echo "     FAILED: ${resp}"
        return 1
    }
    echo "     OK"
}

echo "==> Waiting for opentelemetry_traces table to exist..."
elapsed=0
while true; do
    if curl -sf -X POST "${GREPTIME_URL}/v1/sql?db=${DB}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "sql=SELECT 1 FROM opentelemetry_traces LIMIT 1" > /dev/null 2>&1; then
        echo "    Table found."
        break
    fi
    if [ "$WAIT_TIMEOUT_SECONDS" -gt 0 ] && [ "$elapsed" -ge "$WAIT_TIMEOUT_SECONDS" ]; then
        echo "    ERROR: opentelemetry_traces not found after ${WAIT_TIMEOUT_SECONDS}s."
        echo "    Make sure Dify is running and generating traces."
        exit 1
    fi
    sleep "$WAIT_INTERVAL_SECONDS"
    elapsed=$((elapsed + WAIT_INTERVAL_SECONDS))
done

echo ""
echo "==> Executing SQL from ${SQL_FILE}..."

# Strip comments, collapse into single line, split on semicolons, execute each statement
sed 's/--.*$//' "$SQL_FILE" | tr '\n' ' ' | tr ';' '\n' | while IFS= read -r stmt; do
    stmt=$(echo "$stmt" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$stmt" ] && continue
    sql "$stmt"
done

echo ""
echo "==> Done! Flow-derived metrics will appear in Grafana 'Dify Monitoring' dashboard."
echo ""
echo "   Verify with:"
echo "     mysql -h 127.0.0.1 -P 4002 -e 'SELECT * FROM trace_http_latency_30s LIMIT 5'"
echo ""
