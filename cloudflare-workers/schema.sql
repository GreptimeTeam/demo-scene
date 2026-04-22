-- append_mode = 'true' is what guarantees no data loss: two requests
-- sharing (ts, PK) would otherwise dedupe into one row, which matters
-- because ts has millisecond precision and bursts can exceed 1 req/ms.
--
-- PK is kept only for its secondary job (on-disk clustering for
-- `WHERE colo = 'LAX' ...` queries), covering only low-cardinality
-- filter columns. path_group has higher cardinality so it stays a field.
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
    PRIMARY KEY (colo, country, http_method)
) WITH (ttl = '30d', append_mode = 'true');
