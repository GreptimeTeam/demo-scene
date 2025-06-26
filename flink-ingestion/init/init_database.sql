CREATE TABLE IF NOT EXISTS nginx_access_log (
  access_time TIMESTAMP TIME INDEX,
  client STRING,
  "method" STRING,
  uri STRING,
  protocol STRING,
  "status" UINT16,
  size DOUBLE,
  agent STRING,
)
WITH (
  append_mode = 'true'
);

SHOW TABLES;

DESC TABLE nginx_access_log;
