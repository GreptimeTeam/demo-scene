[sources.host_metrics]
type = "host_metrics"
collectors = ["cpu", "load", "memory"]
scrape_interval_secs = 5

[sources.apache_logs]
type = "demo_logs"
count = 100
format = "apache_common"
interval = 1
lines = ["line1"]

[sinks.metrics]
type = "greptimedb_metrics"
inputs = ["host_metrics"]
endpoint = "${GT_HOST}:${GT_GRPC_PORT}"
dbname = "${GT_DB_NAME}"
username = "${GT_USERNAME}"
password = "${GT_PASSWORD}"
grpc_compression = "gzip"
${GT_TLS}

[sinks.logs]
type = "greptimedb_logs"
inputs = ["apache_logs"]
compression = "gzip"
dbname = "${GT_DB_NAME}"
endpoint = "${GT_SCHEMA}://${GT_HOST}:${GT_HTTP_PORT}"
username = "${GT_USERNAME}"
password = "${GT_PASSWORD}"
pipeline_name = "greptime_identity"
table = "demo_logs"

[sinks.structured_logs]
type = "greptimedb_logs"
inputs = ["apache_logs"]
compression = "gzip"
dbname = "${GT_DB_NAME}"
endpoint = "${GT_SCHEMA}://${GT_HOST}:${GT_HTTP_PORT}"
username = "${GT_USERNAME}"
password = "${GT_PASSWORD}"
pipeline_name = "apache_common_pipeline"
table = "demo_structured_logs"
