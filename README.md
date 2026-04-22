<p align="center">
  <a href="http://console.greptime.cloud/">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="https://greptime.com/logo/icon/logo-cloud-routine-level.svg">
    <source media="(prefers-color-scheme: dark)" srcset="https://greptime.com/logo/icon/logo-cloud-light-level.svg">
    <img alt="GreptimeCloud Logo" src="placeholder" width="400px">
  </picture>
  </a>
</p>

# Demo Scene

Scripts and samples to support Greptime Demos and Talks. Might be rough around the edges ;-)

## Content

### Applications

* [Keyboard Monitor](keyboard-monitor) ([✍️ blog](https://greptime.com/blogs/2024-03-19-keyboard-monitoring))
* [Observability for Nginx on Logs & Metrics](nginx-log-metrics)
* [Dify Monitoring with OpenTelemetry](dify-monitoring)
* [Tesla EV Metrics with OpenTelemetry](ev-open-telemetry)

### Observability

* [GenAI Observability with OpenTelemetry](genai-observability)
* [Ollama + OpenTelemetry + GreptimeDB](ollama-opentelemetry)
* [Django Tracing with OpenTelemetry](opentelemetry-trace-django)
* [OpenTelemetry + Grafana Alloy + GreptimeDB](grafana-alloy)

### Data Pipelines

* [Vector + GreptimeDB](vector-ingestion)
* [Kafka + Vector + GreptimeDB](kafka-ingestion)
* [Apache Flink + GreptimeDB](flink-ingestion)
* [Elasticsearch + GreptimeDB](elasticsearch-ingestion) ([📖 docs](https://docs.greptime.com/nightly/user-guide/ingest-data/for-observability/elasticsearch))
* [InfluxDB Line Protocol + GreptimeDB + Web UI](influxdb-lineprotocol) ([🎥 tutorial](https://www.youtube.com/watch?v=JZuq0inSO9Q))
* [Prometheus Node Exporter + GreptimeDB + Web Dashboard or Grafana Dashboard](node-exporter)
* [Telegraf + GreptimeDB + Web UI](telegraf-ingestion)
* [Flight data ingestion and visualization](flight-data-ingester), including
  geospatial index with H3

### Integrations

* [PostgreSQL Foreign Data Wrapper for GreptimeDB](postgres-fdw)
* [Cloudflare Workers + GreptimeDB: edge event storage](cloudflare-workers)

### Data Migrations

* [From InfluxDB v2 to GreptimeDB](influxdb-v2-to-greptime) ([🎥 tutorial](https://www.youtube.com/watch?v=jiwZoRMzYis) / [✍️ blog](https://greptime.com/blogs/2024-04-16-migrate-data-from-influxdbv2))
* [From InfluxDB v1 to GreptimeDB](influxdb-v1-to-greptime)

## Feedback & Questions

* Bugs or issues with demo: raise an issue on this GitHub project
* General question and assistance: [GitHub Discussions](https://github.com/orgs/GreptimeTeam/discussions) / [Slack](https://greptime.com/slack)
