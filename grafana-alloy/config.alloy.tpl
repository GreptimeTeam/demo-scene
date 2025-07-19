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

// Additional example:
// Convert Prometheus metrics into OpenTelemetry format and ingest into GreptimeDB OTLP endpoint
//
// This is to demo the usage of using OpenTelemetry with GreptimeDB (we just use Prometheus as data source here)
otelcol.receiver.prometheus "metrics_prm_to_otel" {
  output {
    metrics = [otelcol.processor.transform.rename.input]
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
    endpoint = "${GREPTIME_SCHEME:=http}://${GREPTIME_HOST:=greptimedb}:${GREPTIME_PORT:=4000}/v1/otlp/"
    headers  = {
      "x-greptime-db-name" = "${GREPTIME_DB:=public}",
    }
    auth     = otelcol.auth.basic.credentials.handler
  }
}

otelcol.exporter.otlphttp "greptimedb_logs" {
  client {
    endpoint = "${GREPTIME_SCHEME:=http}://${GREPTIME_HOST:=greptimedb}:${GREPTIME_PORT:=4000}/v1/otlp/"
    headers  = {
      "x-greptime-db-name" = "${GREPTIME_DB:=public}",
      "x-greptime-log-table-name" = "alloy_meta_logs",
      "x-greptime-log-extract-keys" = "hostname",
    }
    auth     = otelcol.auth.basic.credentials.handler
  }
}

loki.write "greptime_loki" {
  endpoint {
    url = "${GREPTIME_SCHEME:=http}://${GREPTIME_HOST:=greptimedb}:${GREPTIME_PORT:=4000}/v1/loki/api/v1/push"
    headers  = {
      "x-greptime-db-name" = "${GREPTIME_DB:=public}",
      "x-greptime-log-table-name" = "${GREPTIME_LOG_TABLE_NAME:=loki_demo_logs}",
    }
    basic_auth {
      username = "${GREPTIME_USERNAME}"
      password = "${GREPTIME_PASSWORD}"
    }
  }
  external_labels = {
    "job" = "greptime",
    "from" = "alloy",
  }
}

otelcol.auth.basic "credentials" {
  username = "${GREPTIME_USERNAME}"
  password = "${GREPTIME_PASSWORD}"
}

otelcol.processor.attributes "enrichment" {
  action {
    key = "hostname"
    value = constants.hostname
    action = "insert"
  }

  output {
    logs = [otelcol.exporter.otlphttp.greptimedb_logs.input]
  }
}

otelcol.receiver.loki "greptime" {
  output {
    logs = [otelcol.processor.attributes.enrichment.input]
  }
}

logging {
  level    = "info"
  format   = "json"
  write_to = [otelcol.receiver.loki.greptime.receiver,  loki.write.greptime_loki.receiver]
}

otelcol.exporter.otlphttp "greptimedb_traces" {
  client {
    endpoint = "${GREPTIME_SCHEME:=http}://${GREPTIME_HOST:=greptimedb}:${GREPTIME_PORT:=4000}/v1/otlp/"
    headers  = {
      "x-greptime-db-name" = "${GREPTIME_DB:=public}",
      "x-greptime-trace-table-name" = "myapp_traces",
      "x-greptime-pipeline-name" = "greptime_trace_v1",
    }
    auth     = otelcol.auth.basic.credentials.handler
  }
}

otelcol.receiver.otlp "otel_traces" {
  http {}
  grpc {}

  output {
    traces  = [otelcol.exporter.otlphttp.greptimedb_traces.input]
  }
}
