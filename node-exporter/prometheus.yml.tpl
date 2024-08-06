# my global config
global:
  scrape_interval: 15s # Set the scrape interval to every 15 seconds. Default is every 1 minute.
  evaluation_interval: 15s # Evaluate rules every 15 seconds. The default is every 1 minute.
  # scrape_timeout is set to the global default (10s).

# A scrape configuration containing exactly one endpoint to scrape:
# Here it's Prometheus itself.
scrape_configs:
  # The job name is added as a label `job=<job_name>` to any timeseries scraped from this config.
  - job_name: "node"

    # metrics_path defaults to '/metrics'
    # scheme defaults to 'http'.

    static_configs:
      - targets: ["node_exporter:9100"]

remote_write:
  - url: "https://${GREPTIME_HOST}/v1/prometheus/write?db=${GREPTIME_DB}"
    basic_auth:
      username: ${GREPTIME_USERNAME}
      password: ${GREPTIME_PASSWORD}
