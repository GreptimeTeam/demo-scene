-- Sample queries for worker_events. Run via curl against
--   http://localhost:4000/v1/sql?db=public
-- or the web console at http://localhost:4000/dashboard.
--
-- Quoting gotcha: HTTP SQL uses double quotes ("path_group"); the Grafana
-- MySQL datasource uses backticks (`path_group`). Swap when copying between.

-- 1. Request count per minute by CF colo (PoP).
SELECT
    date_bin('1 minute'::INTERVAL, ts) AS minute,
    colo,
    count(*) AS requests
FROM worker_events
WHERE ts > now() - INTERVAL '1 hour'
GROUP BY minute, colo
ORDER BY minute DESC;

-- 2. Latency percentiles by route (p50 / p95 / p99, last 1h).
SELECT
    path_group,
    count(*) AS requests,
    round(approx_percentile_cont(latency_ms, 0.50), 1) AS p50_ms,
    round(approx_percentile_cont(latency_ms, 0.95), 1) AS p95_ms,
    round(approx_percentile_cont(latency_ms, 0.99), 1) AS p99_ms
FROM worker_events
WHERE ts > now() - INTERVAL '1 hour'
GROUP BY path_group
ORDER BY p95_ms DESC
LIMIT 20;

-- 3. Error-rate timeseries (anything >= 400).
SELECT
    date_bin('1 minute'::INTERVAL, ts) AS minute,
    count(*) AS total,
    sum(CASE WHEN http_status >= 400 THEN 1 ELSE 0 END) AS errors,
    round(
      100.0 * sum(CASE WHEN http_status >= 400 THEN 1 ELSE 0 END) / count(*),
      2
    ) AS error_rate_pct
FROM worker_events
WHERE ts > now() - INTERVAL '1 hour'
GROUP BY minute
ORDER BY minute DESC;

-- 4. Top 10 slowest endpoints by average latency.
SELECT
    path_group,
    count(*) AS requests,
    round(avg(latency_ms), 1) AS avg_latency_ms,
    round(max(latency_ms), 1) AS max_latency_ms
FROM worker_events
WHERE ts > now() - INTERVAL '1 hour'
GROUP BY path_group
ORDER BY avg_latency_ms DESC
LIMIT 10;

-- 5. Traffic distribution by country.
SELECT
    country,
    count(*) AS requests,
    round(avg(latency_ms), 1) AS avg_latency_ms
FROM worker_events
WHERE ts > now() - INTERVAL '1 hour'
GROUP BY country
ORDER BY requests DESC
LIMIT 20;

-- 6. CF edge location distribution (which colos served traffic).
SELECT
    colo,
    count(*) AS requests,
    count(DISTINCT country) AS countries_served
FROM worker_events
WHERE ts > now() - INTERVAL '1 hour'
GROUP BY colo
ORDER BY requests DESC;

-- 7. Drill into recent errors — useful when error_rate_pct spikes.
SELECT
    ts,
    http_status,
    colo,
    country,
    http_method,
    full_path,
    latency_ms,
    cf_ray
FROM worker_events
WHERE http_status >= 400
  AND ts > now() - INTERVAL '15 minutes'
ORDER BY ts DESC
LIMIT 50;
