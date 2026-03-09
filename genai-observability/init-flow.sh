#!/bin/sh
set -eu

# GreptimeDB HTTP SQL endpoint
GREPTIME_URL="${GREPTIME_URL:-http://localhost:4000}"
DB="public"
WAIT_TIMEOUT_SECONDS="${WAIT_TIMEOUT_SECONDS:-600}"
WAIT_INTERVAL_SECONDS="${WAIT_INTERVAL_SECONDS:-2}"

# Validate env vars
case "$WAIT_TIMEOUT_SECONDS" in
    ''|*[!0-9]*) echo "ERROR: WAIT_TIMEOUT_SECONDS must be a non-negative integer, got: ${WAIT_TIMEOUT_SECONDS}"; exit 1;;
esac
case "$WAIT_INTERVAL_SECONDS" in
    ''|*[!0-9]*|0) echo "ERROR: WAIT_INTERVAL_SECONDS must be a positive integer, got: ${WAIT_INTERVAL_SECONDS}"; exit 1;;
esac

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

echo "==> Waiting for opentelemetry_traces table with gen_ai.* columns..."
elapsed=0
while true; do
    # Wait until gen_ai spans exist (not just the table), so Flow column references resolve
    if curl -sf -X POST "${GREPTIME_URL}/v1/sql?db=${DB}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "sql=SELECT 1 FROM opentelemetry_traces WHERE \"span_attributes.gen_ai.system\" IS NOT NULL LIMIT 1" > /dev/null 2>&1; then
        echo "    Table found with gen_ai.* columns."
        break
    fi
    if [ "$WAIT_TIMEOUT_SECONDS" -gt 0 ] && [ "$elapsed" -ge "$WAIT_TIMEOUT_SECONDS" ]; then
        echo "    ERROR: opentelemetry_traces with gen_ai.* columns not found after ${WAIT_TIMEOUT_SECONDS}s."
        echo "    Make sure the GenAI app or load generator has run at least once."
        exit 1
    fi
    sleep "$WAIT_INTERVAL_SECONDS"
    elapsed=$((elapsed + WAIT_INTERVAL_SECONDS))
done

echo ""
echo "==> Creating sink tables..."

sql "CREATE TABLE IF NOT EXISTS genai_token_usage_1m (
    model STRING,
    request_count INT64,
    total_input_tokens DOUBLE,
    total_output_tokens DOUBLE,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (model)
)"

sql "CREATE TABLE IF NOT EXISTS genai_latency_1m (
    model STRING,
    request_count INT64,
    duration_sketch BINARY,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (model)
)"

sql "CREATE TABLE IF NOT EXISTS genai_status_1m (
    model STRING,
    span_status STRING,
    request_count INT64,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (model, span_status)
)"

echo ""
echo "==> Creating flows..."

sql "CREATE FLOW IF NOT EXISTS genai_token_usage_flow
SINK TO genai_token_usage_1m
EXPIRE AFTER '24h'
COMMENT 'Token usage per model per minute'
AS
SELECT
    \"span_attributes.gen_ai.request.model\" AS model,
    COUNT(\"span_attributes.gen_ai.request.model\") AS request_count,
    SUM(CAST(\"span_attributes.gen_ai.usage.input_tokens\" AS DOUBLE)) AS total_input_tokens,
    SUM(CAST(\"span_attributes.gen_ai.usage.output_tokens\" AS DOUBLE)) AS total_output_tokens,
    date_bin('1 minute'::INTERVAL, \"timestamp\") AS time_window
FROM opentelemetry_traces
WHERE \"span_attributes.gen_ai.system\" IS NOT NULL
GROUP BY \"span_attributes.gen_ai.request.model\", time_window"

sql "CREATE FLOW IF NOT EXISTS genai_latency_flow
SINK TO genai_latency_1m
EXPIRE AFTER '24h'
COMMENT 'LLM call latency distribution per model'
AS
SELECT
    \"span_attributes.gen_ai.request.model\" AS model,
    COUNT(\"span_attributes.gen_ai.request.model\") AS request_count,
    uddsketch_state(128, 0.01, duration_nano) AS duration_sketch,
    date_bin('1 minute'::INTERVAL, \"timestamp\") AS time_window
FROM opentelemetry_traces
WHERE \"span_attributes.gen_ai.system\" IS NOT NULL
GROUP BY \"span_attributes.gen_ai.request.model\", time_window"

sql "CREATE FLOW IF NOT EXISTS genai_status_flow
SINK TO genai_status_1m
EXPIRE AFTER '24h'
COMMENT 'Request count by model and status per minute'
AS
SELECT
    \"span_attributes.gen_ai.request.model\" AS model,
    span_status_code AS span_status,
    COUNT(\"span_attributes.gen_ai.request.model\") AS request_count,
    date_bin('1 minute'::INTERVAL, \"timestamp\") AS time_window
FROM opentelemetry_traces
WHERE \"span_attributes.gen_ai.system\" IS NOT NULL
GROUP BY \"span_attributes.gen_ai.request.model\", span_status_code, time_window"

echo ""
echo "==> Done! GenAI Flow metrics will populate automatically."
echo ""
echo "   Verify with:"
echo "     mysql -h 127.0.0.1 -P 4002 -e 'SELECT * FROM genai_token_usage_1m LIMIT 5'"
echo ""
