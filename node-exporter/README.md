# Use GreptimeDB to store and visualize data from Node Exporter

## Rationales

GreptimeDB implements APIs for both Prometheus remote read and remote write. You can [use GreptimeDB as a Prometheus backend](https://docs.greptime.com/user-guide/ingest-data/for-observerbility/prometheus).

Meanwhile, GreptimeDB [supports PromQL](https://docs.greptime.com/user-guide/query-data/promql) as its query interface, so that you can use GreptimeDB as a drop-in replacement for Prometheus.

This demo showcases how to run the famous Node Exporter integrations with GreptimeDB as the storage backend.

## Step 1: Set up GreptimeDB service

First of all, let's get a free GreptimeDB service:

1. Obtain a free GreptimeDB service from [GreptimeCloud](https://console.greptime.cloud/).
2. Click the "Connection Information" button and find the connection string.
3. Create a `greptime.env` by copy the `greptime.env.sample` and fill with your
   connection information.

```shell
GREPTIME_SCHEME=https
GREPTIME_PORT=443

## Fill with your connection information
GREPTIME_HOST=
GREPTIME_DB=
GREPTIME_USERNAME=
GREPTIME_PASSWORD=
```

![Connection](/media/conninfo.png)

## Step 2: Start Node Exporter and Prometheus with Docker Compose

We build a docker-compose file to start Prometheus node exporter and Prometheus
with just one call. Make sure you have `docker` and `docker-compose`
installed. Run:

```
docker compose up
```

## Step 3: Visualize on GreptimeCloud Dashboard

You can visualize the node mertics from the Web Dashboard:

![Portal](/media/portal.png)

![Configure Workbench Node Exporter Full](media/workbench-dashboard.png)

The "Node Exporter Full" dashboard template will give you the same charts as the Grafana Node Exporter Dashboard.

![Node Exporter Full Charts](media/node-exporter-full.png)

## Bonus: Visualize with Grafana Dashboard

Since GreptimeDB can be used as a drop-in replacement of Prometheus, it's also possible to visualize node metrics with Grafana Dashboard with the Prometheus plugin, as if GreptimeDB is a Prometheus instance.

First, start a Grafana container:

```bash
docker run -d --name=grafana -p 3000:3000 grafana/grafana
```

Open `http://localhost:3000/` at browser and log in with the default credential: both username and password are `admin`.

You should add GreptimeDB as an instance of Prometheus data source. Click "Connections", "Data sources", and then "Add new data source":

![Grafana Data Source](media/grafana-datasource.png)

Choose "Prometheus" and add the necessary configuration:

![Grafana Connection Info](media/grafana-connection-info.png)

Click "Save & Test" at the button to ensure the connection is correctly set up.

Then, go the "Dashboard" page and click "Create Dashboard":

![Grafana Create Dashboard](media/grafana-create-dashboard.png)

Choose "Import a dashboard" and then load the Node Exporter Full public template (`https://grafana.com/grafana/dashboards/1860-node-exporter-full/`):

![Grafana Import Dashboard](media/grafana-import-dashboard.png)

Use the data source you just registered, and click "Import". You will be redirected to the final dashboard:

![Grafana Final Dashboard](media/grafana-final-dashboard.png)
