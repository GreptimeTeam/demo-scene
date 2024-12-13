#!/usr/bin/env bash

set -e

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER}" <<-EOSQL
CREATE EXTENSION postgres_fdw;

CREATE SERVER greptimedb
FOREIGN DATA WRAPPER postgres_fdw
OPTIONS (host '${GREPTIME_HOST:=greptimedb}', dbname '${GREPTIME_DB:=public}', port '4003');

CREATE USER MAPPING FOR postgres
SERVER greptimedb
OPTIONS (user '${GREPTIME_USERNAME:=greptime}', password '${GREPTIME_PASSWORD:=greptime}');

CREATE FOREIGN TABLE ft_demo_logs_json (
  "bytes" INT8,
  "datetime" VARCHAR,
  "host" VARCHAR,
  "method" VARCHAR,
  "protocol" VARCHAR,
  "referer" VARCHAR,
  "request" VARCHAR,
  "status" VARCHAR,
  "user-identifier" VARCHAR,
  "greptime_timestamp" TIMESTAMP
)
SERVER greptimedb
OPTIONS (table_name 'demo_logs_json');

EOSQL
