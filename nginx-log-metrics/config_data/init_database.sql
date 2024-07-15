CREATE TABLE `ngx_access_log` (
  `client` STRING NULL,
  `ua_platform` STRING NULL,
  `referer` STRING NULL,
  `method` STRING NULL,
  `endpoint` STRING NULL,
  `protocol` STRING NULL,
  `status` SMALLINT UNSIGNED NULL,
  `size` INT UNSIGNED NULL,
  `agent` STRING NULL,
  `access_time` TIMESTAMP(3) NOT NULL,
  TIME INDEX (`access_time`)
)
WITH(
  append_mode = 'true'
);

-- min(size) as min_size, max(size) as max_size, avg(size) as avg_size
CREATE FLOW ngx_aggregation
SINK TO ngx_statistics
AS 
SELECT 
    status,
    count(client) AS total_logs
FROM ngx_access_log 
GROUP BY
    status,
    tumble(access_time, '1 minutes', '2024-01-01 00:00:00');

SHOW TABLES;
