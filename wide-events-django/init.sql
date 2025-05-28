CREATE TABLE "django_http_request_latency" (
    "span_name" STRING NULL,
    "latency_sketch" BINARY,
    "time_window" TIMESTAMP time index,
    PRIMARY KEY ("span_name")
);

CREATE FLOW django_http_request_latency_flow
SINK TO django_http_request_latency
EXPIRE AFTER '30m'
COMMENT 'Aggregate latency using uddsketch'
AS
SELECT
    span_name,
    uddsketch_state(128, 0.01, "duration_nano") AS "latency_sketch",
    date_bin('30 seconds'::INTERVAL, "timestamp") as "time_window",
FROM web_trace_demo
WHERE
    scope_name = 'opentelemetry.instrumentation.django'
GROUP BY
    span_name,
    time_window;
