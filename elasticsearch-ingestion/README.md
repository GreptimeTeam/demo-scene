# Elasticsearch Ingestion Demo

This demo shows how to ingest data from Elasticsearch to GreptimeDB. The related documentation is [here](https://docs.greptime.com/nightly/user-guide/ingest-data/for-observability/elasticsearch).

## How to run this demo

Ensure you have `git`, `docker` and `docker-compose` installed. To run this
demo:

```console
git clone https://github.com/GreptimeTeam/demo-scene.git
cd demo-scene/elasticsearch-ingestion
docker compose up
```

It can take a while for the first run to pull down images and also build
necessary components.

You can access GreptimeDB using `mysql` client. Just run `mysql -h 127.0.0.1 -P
4002` to connect to the database and use SQL queries like `SHOW TABLES` as a
start. You can query the `nginx` table to see the data that has been ingested.

```console
$ mysql -h 127.0.0.1 -P 4002
Welcome to the MySQL monitor.  Commands end with ; or \g.
Your MySQL connection id is 8
Server version: 8.4.2 Greptime

Copyright (c) 2000, 2024, Oracle and/or its affiliates.

Oracle is a registered trademark of Oracle Corporation and/or its
affiliates. Other names may be trademarks of their respective
owners.

Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

mysql> show tables;
+---------+
| Tables  |
+---------+
| nginx   |
| numbers |
+---------+
2 rows in set (0.02 sec)

mysql> SELECT * FROM nginx LIMIT 3 \G;
*************************** 1. row ***************************
   ip_address: 104.165.107.159
  http_method: DELETE
  status_code: 200
 request_line: /contact HTTP/2.0
   user_agent: Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 OPR/26.0.1656.60
response_size: 927
    timestamp: 2025-02-07 08:12:52
*************************** 2. row ***************************
   ip_address: 110.181.64.38
  http_method: DELETE
  status_code: 404
 request_line: /signup HTTP/2.0
   user_agent: Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/534.16 (KHTML, like Gecko) Chrome/10.0.648.133 Safari/534.16
response_size: 789
    timestamp: 2025-02-07 08:05:45
*************************** 3. row ***************************
   ip_address: 118.236.67.182
  http_method: DELETE
  status_code: 500
 request_line: /blog HTTP/1.1
   user_agent: Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.122 UBrowser/4.0.3214.0 Safari/537.36
response_size: 684
    timestamp: 2025-02-07 08:12:46
3 rows in set (0.02 sec)
```

## How to stop this demo

```console
docker compose down
```

It will stop all the services and remove the containers(including the data).
