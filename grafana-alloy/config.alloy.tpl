prometheus.exporter.unix "local_system" { }

prometheus.scrape "scrape_metrics" {
  targets         = prometheus.exporter.unix.local_system.targets
  forward_to      = [prometheus.relabel.filter_metrics.receiver]
  scrape_interval = "15s"
}

prometheus.relabel "filter_metrics" {
  rule {
    action        = "drop"
    source_labels = ["env"]
    regex         = "dev"
  }

  forward_to = [
    prometheus.remote_write.metrics_service.receiver,
    otelcol.receiver.prometheus.metrics_prm_to_otel.receiver,
  ]
}

prometheus.remote_write "metrics_service" {
  endpoint {
    url = "${GREPTIME_SCHEME:=http}://${GREPTIME_HOST:=greptimedb}:${GREPTIME_PORT:=4000}/v1/prometheus/write?db=${GREPTIME_DB:=public}"

    basic_auth {
      username = "${GREPTIME_USERNAME}"
      password = "${GREPTIME_PASSWORD}"
    }
  }
}

// logs
loki.source.file "example" {
  targets    = [{
    __path__ = "/tmp/foo.log", color="pink",
    instance = constants.hostname,
    __address__ = "alloydemo",
  }]
  forward_to = [otelcol.receiver.loki.logs_loki_to_otel.receiver]
}

// Additional example:
// Convert Prometheus metrics into OpenTelemetry format and ingest into GreptimeDB OTLP endpoint
//
// This is to demo the usage of using OpenTelemetry with GreptimeDB (we just use Prometheus as data source here)
otelcol.receiver.prometheus "metrics_prm_to_otel" {
  output {
    metrics = [otelcol.processor.transform.rename.input]
  }
}

otelcol.receiver.loki "logs_loki_to_otel" {
  output {
    logs = [otelcol.exporter.otlphttp.greptimedb.input]
  }
}

otelcol.processor.transform "rename" {
  metric_statements {
    context = "metric"
    statements = [
      "replace_pattern(name, \"(.*)\", \"otel_$$1\")",
    ]
  }

  output {
    metrics = [otelcol.exporter.otlphttp.greptimedb.input]
  }
}

otelcol.exporter.otlphttp "greptimedb" {
  client {
    endpoint = "${GREPTIME_SCHEME:=http}://${GREPTIME_HOST:=172.17.0.1}:${GREPTIME_PORT:=4000}/v1/otlp/"
    headers  = {
      "X-Greptime-DB-Name" = "${GREPTIME_DB:=public}",
      "x-greptime-table-name" = "demologs",
    }
    auth     = otelcol.auth.basic.credentials.handler
  }
}

otelcol.auth.basic "credentials" {
  username = "${GREPTIME_USERNAME}"
  password = "${GREPTIME_PASSWORD}"
}
