#!/usr/bin/env bash
set -euo pipefail

# GreptimeDB HTTP SQL endpoint
GREPTIME_URL="${GREPTIME_URL:-http://localhost:4000}"
DB="public"

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
for i in $(seq 1 30); do
    if curl -sf -X POST "${GREPTIME_URL}/v1/sql?db=${DB}" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "sql=SELECT 1 FROM opentelemetry_traces LIMIT 1" > /dev/null 2>&1; then
        echo "    Table found."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "    ERROR: opentelemetry_traces not found after 60s."
        echo "    Make sure Dify is running and generating traces."
        exit 1
    fi
    sleep 2
done

echo ""
echo "==> Creating sink tables..."

sql "CREATE TABLE IF NOT EXISTS trace_http_latency_30s (
    span_name STRING,
    request_count INT64,
    duration_sketch BINARY,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (span_name)
)"

sql "CREATE TABLE IF NOT EXISTS trace_operation_throughput_30s (
    span_name STRING,
    span_kind STRING,
    total_count INT64,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (span_name, span_kind)
)"

echo ""
echo "==> Creating flows..."

sql "CREATE FLOW IF NOT EXISTS trace_http_latency_flow
SINK TO trace_http_latency_30s
EXPIRE AFTER '1h'
COMMENT 'HTTP request latency percentiles (uddsketch) from server spans'
AS
SELECT
    span_name,
    COUNT(span_name) AS request_count,
    uddsketch_state(128, 0.01, duration_nano) AS duration_sketch,
    date_bin('30 seconds'::INTERVAL, \"timestamp\") AS time_window
FROM opentelemetry_traces
WHERE span_kind = 'SPAN_KIND_SERVER'
GROUP BY span_name, time_window"

sql "CREATE FLOW IF NOT EXISTS trace_operation_throughput_flow
SINK TO trace_operation_throughput_30s
EXPIRE AFTER '1h'
COMMENT 'Operation throughput from all trace spans'
AS
SELECT
    span_name,
    span_kind,
    COUNT(span_name) AS total_count,
    date_bin('30 seconds'::INTERVAL, \"timestamp\") AS time_window
FROM opentelemetry_traces
GROUP BY span_name, span_kind, time_window"

echo ""
echo "==> Done! Flow-derived metrics will appear in Grafana 'Dify Trace-Derived Metrics' dashboard."
echo ""
echo "   Verify with:"
echo "     mysql -h 127.0.0.1 -P 4002 -e 'SELECT * FROM trace_http_latency_30s LIMIT 5'"
echo ""
