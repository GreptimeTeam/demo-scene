-- Schema for the worker_events table. Pre-creating lets us pin types,
-- primary-key columns, and TTL up-front instead of relying on line-protocol
-- auto-schema (which would guess from the first write).
CREATE TABLE IF NOT EXISTS worker_events (
    ts          TIMESTAMP(9) TIME INDEX,
    colo        STRING,
    country     STRING,
    http_method STRING,
    path_group  STRING,
    http_status BIGINT,
    latency_ms  DOUBLE,
    bytes_out   BIGINT,
    cf_ray      STRING,
    ua          STRING,
    full_path   STRING,
    PRIMARY KEY (colo, country, http_method, path_group)
) WITH (ttl = '30d');
