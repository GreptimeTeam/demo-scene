#!/bin/sh
set -eu

# GreptimeDB HTTP SQL endpoint
GREPTIME_URL="${GREPTIME_URL:-http://localhost:4000}"
DB="public"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-600}"
WAIT_INTERVAL_SECONDS="${WAIT_INTERVAL_SECONDS:-2}"
SQL_FILE="${SQL_FILE:-/flows.sql}"

# Validate env vars
case "$WAIT_TIMEOUT_SECONDS" in
    ''|*[!0-9]*) echo "ERROR: WAIT_TIMEOUT_SECONDS must be a non-negative integer, got: ${WAIT_TIMEOUT_SECONDS}"; exit 1;;
esac
case "$WAIT_INTERVAL_SECONDS" in
    ''|*[!0-9]*) echo "ERROR: WAIT_INTERVAL_SECONDS must be a positive integer, got: ${WAIT_INTERVAL_SECONDS}"; exit 1;;
esac
if [ "$WAIT_INTERVAL_SECONDS" -eq 0 ]; then
    echo "ERROR: WAIT_INTERVAL_SECONDS must be a positive integer, got: ${WAIT_INTERVAL_SECONDS}"; exit 1
fi

sql() {
    stmt="$1"
    echo "  -> $(echo "$stmt" | head -1 | cut -c1-80)..."
    resp=$(curl -sf -X POST "${GREPTIME_URL}/v1/sql?db=${DB}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "sql=${stmt}" 2>&1) || {
        echo "     FAILED: ${resp}"
        return 1
    }
    echo "     OK"
}

echo "==> Waiting for successful gen_ai spans (with token usage columns)..."
elapsed=0
while true; do
    # Wait until a span with token usage exists — error-only spans lack gen_ai.usage.* columns,
    # so checking gen_ai.system alone is not enough for CREATE FLOW to resolve all columns.
    if curl -sf -X POST "${GREPTIME_URL}/v1/sql?db=${DB}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "sql=SELECT 1 FROM opentelemetry_traces WHERE \"span_attributes.gen_ai.usage.input_tokens\" IS NOT NULL LIMIT 1" > /dev/null 2>&1; then
        echo "    Found gen_ai spans with token usage columns."
        break
    fi
    if [ "$WAIT_TIMEOUT_SECONDS" -gt 0 ] && [ "$elapsed" -ge "$WAIT_TIMEOUT_SECONDS" ]; then
        echo "    ERROR: No gen_ai spans with token usage found after ${WAIT_TIMEOUT_SECONDS}s."
        echo "    Make sure the LLM backend (Ollama/OpenAI) is reachable and at least one successful call has been made."
        exit 1
    fi
    sleep "$WAIT_INTERVAL_SECONDS"
    elapsed=$((elapsed + WAIT_INTERVAL_SECONDS))
done

echo ""
echo "==> Executing SQL from ${SQL_FILE}..."

if [ ! -f "$SQL_FILE" ]; then
    echo "ERROR: SQL file not found: ${SQL_FILE}"
    exit 1
fi

# Strip comments, collapse into single line, split on semicolons, execute each statement
sed 's/--.*$//' "$SQL_FILE" | tr '\n' ' ' | tr ';' '\n' > /tmp/stmts.txt
while IFS= read -r stmt; do
    stmt=$(echo "$stmt" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -z "$stmt" ] && continue
    sql "$stmt"
done < /tmp/stmts.txt

echo ""
echo "==> Done! GenAI Flow metrics will populate automatically."
echo ""
echo "   Verify with:"
echo "     mysql -h 127.0.0.1 -P 4002 -e 'SELECT * FROM genai_token_usage_1m LIMIT 5'"
echo ""
