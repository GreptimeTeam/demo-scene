-- GreptimeDB Flow aggregations for Dify monitoring
-- Executed by init-flow.sh; also readable as standalone SQL reference.
--
-- These create continuous materialized views that compute RED metrics
-- (Rate, Errors, Duration) from raw OpenTelemetry trace spans.

-- =============================================================================
-- Sink tables (Flow output destinations)
-- =============================================================================

CREATE TABLE IF NOT EXISTS trace_http_latency_30s (
    span_name STRING,
    request_count INT64,
    duration_sketch BINARY,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (span_name)
);

CREATE TABLE IF NOT EXISTS trace_operation_throughput_30s (
    span_name STRING,
    span_kind STRING,
    total_count INT64,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (span_name, span_kind)
);

-- =============================================================================
-- Flows (continuous aggregation)
-- =============================================================================

-- HTTP request latency percentiles (uddsketch) from server spans
CREATE FLOW IF NOT EXISTS trace_http_latency_flow
SINK TO trace_http_latency_30s
EXPIRE AFTER '1h'
COMMENT 'HTTP request latency percentiles (uddsketch) from server spans'
AS
SELECT
    span_name,
    COUNT(span_name) AS request_count,
    uddsketch_state(128, 0.01, duration_nano) AS duration_sketch,
    date_bin('30 seconds'::INTERVAL, "timestamp") AS time_window
FROM opentelemetry_traces
WHERE span_kind = 'SPAN_KIND_SERVER'
GROUP BY span_name, time_window;

-- Operation throughput from all trace spans
CREATE FLOW IF NOT EXISTS trace_operation_throughput_flow
SINK TO trace_operation_throughput_30s
EXPIRE AFTER '1h'
COMMENT 'Operation throughput from all trace spans'
AS
SELECT
    span_name,
    span_kind,
    COUNT(span_name) AS total_count,
    date_bin('30 seconds'::INTERVAL, "timestamp") AS time_window
FROM opentelemetry_traces
GROUP BY span_name, span_kind, time_window;
