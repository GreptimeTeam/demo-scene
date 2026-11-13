#!/bin/sh
set -e
GT=${GREPTIMEDB_HTTP:-http://greptimedb:4000}
sql() {
  curl --fail-with-body --silent --show-error --connect-timeout 5 --max-time 30 \
    -X POST "$GT/v1/sql" --data-urlencode "sql=$1"
}

# Wait for the business namespace column, which may arrive after the first span.
i=0
until sql "SELECT \"resource_attributes.service.namespace\" FROM opentelemetry_traces LIMIT 1" >/dev/null 2>&1; do
  i=$((i+1)); [ "$i" -ge 120 ] && { echo "opentelemetry_traces was not ready after 120 attempts"; exit 1; }
  sleep 2
done

sql "CREATE FLOW IF NOT EXISTS service_error_rate_1m
SINK TO service_error_rate_1m
EVAL INTERVAL '30s'
AS
SELECT
  service_name,
  date_bin('1 minute'::INTERVAL, \"timestamp\") AS time_window,
  count(*) AS total,
  sum(CASE WHEN span_status_code = 'STATUS_CODE_ERROR' THEN 1 ELSE 0 END) AS errors
FROM opentelemetry_traces
WHERE span_kind = 'SPAN_KIND_SERVER'
  AND \"resource_attributes.service.namespace\" = 'opentelemetry-demo'
GROUP BY service_name, time_window"
echo
echo "flow service_error_rate_1m created"
