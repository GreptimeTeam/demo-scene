-- GreptimeDB Flow aggregations for GenAI observability
-- Executed by init-flow.sh; also readable as standalone SQL reference.
--
-- These create continuous materialized views that pre-aggregate
-- OpenTelemetry GenAI trace data into per-minute summaries.

-- =============================================================================
-- Sink tables (Flow output destinations)
-- =============================================================================

CREATE TABLE IF NOT EXISTS genai_token_usage_1m (
    model STRING,
    request_count INT64,
    total_input_tokens DOUBLE,
    total_output_tokens DOUBLE,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (model)
);

CREATE TABLE IF NOT EXISTS genai_latency_1m (
    model STRING,
    request_count INT64,
    duration_sketch BINARY,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (model)
);

CREATE TABLE IF NOT EXISTS genai_status_1m (
    model STRING,
    span_status STRING,
    request_count INT64,
    time_window TIMESTAMP TIME INDEX,
    PRIMARY KEY (model, span_status)
);

-- =============================================================================
-- Flows (continuous aggregation)
-- =============================================================================

-- Token usage per model per minute
CREATE FLOW IF NOT EXISTS genai_token_usage_flow
SINK TO genai_token_usage_1m
EXPIRE AFTER '24h'
COMMENT 'Token usage per model per minute'
AS
SELECT
    "span_attributes.gen_ai.request.model" AS model,
    COUNT("span_attributes.gen_ai.request.model") AS request_count,
    SUM(CAST("span_attributes.gen_ai.usage.input_tokens" AS DOUBLE)) AS total_input_tokens,
    SUM(CAST("span_attributes.gen_ai.usage.output_tokens" AS DOUBLE)) AS total_output_tokens,
    date_bin('1 minute'::INTERVAL, "timestamp") AS time_window
FROM opentelemetry_traces
WHERE "span_attributes.gen_ai.system" IS NOT NULL
GROUP BY "span_attributes.gen_ai.request.model", time_window;

-- Latency distribution (uddsketch) per model per minute
CREATE FLOW IF NOT EXISTS genai_latency_flow
SINK TO genai_latency_1m
EXPIRE AFTER '24h'
COMMENT 'LLM call latency distribution per model'
AS
SELECT
    "span_attributes.gen_ai.request.model" AS model,
    COUNT("span_attributes.gen_ai.request.model") AS request_count,
    uddsketch_state(128, 0.01, duration_nano) AS duration_sketch,
    date_bin('1 minute'::INTERVAL, "timestamp") AS time_window
FROM opentelemetry_traces
WHERE "span_attributes.gen_ai.system" IS NOT NULL
GROUP BY "span_attributes.gen_ai.request.model", time_window;

-- Request count by model and status code per minute
CREATE FLOW IF NOT EXISTS genai_status_flow
SINK TO genai_status_1m
EXPIRE AFTER '24h'
COMMENT 'Request count by model and status per minute'
AS
SELECT
    "span_attributes.gen_ai.request.model" AS model,
    span_status_code AS span_status,
    COUNT("span_attributes.gen_ai.request.model") AS request_count,
    date_bin('1 minute'::INTERVAL, "timestamp") AS time_window
FROM opentelemetry_traces
WHERE "span_attributes.gen_ai.system" IS NOT NULL
GROUP BY "span_attributes.gen_ai.request.model", span_status_code, time_window;
