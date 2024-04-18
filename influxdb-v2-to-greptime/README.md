# Migrate data from InfluxDB v2 to GreptimeDB

> [!NOTE]
>
> Read the blog ["How to Quickly Migrate Data from InfluxDB v2 to GreptimeDB"](https://greptime.com/blogs/2024-04-16-migrate-data-from-influxdbv2) for a full explanation.

## Prerequisites

You need to be able to access your InfluxDB engine path, which contains your data files. If you run a server with InfluxDB's official Docker Image, the engine path is `/var/lib/influxdb2/engine/`.

## Step 1: Set up Greptime service

1. Obtain a free Greptime service from [GreptimeCloud](https://console.greptime.cloud/). 
2. Click the "Connection Information" button and find the connection string.
3. Export the necessary environment variables:

```shell
export GREPTIME_DB="<dbname>"
export GREPTIME_HOST="<host>"
export GREPTIME_USERNAME="<username>"
export GREPTIME_PASSWORD="<password>"
```

![Connection](/media/conninfo.png)

## Step 2: Export data from InfluxDB v2 server

Get the bucket ID to be migrated:

```shell
influx bucket list
```

Outputs like:

```text
ID                  Name           Retention  Shard group duration  Organization ID   Schema Type
009db1e8c106b996    _monitoring    168h0m0s   24h0m0s               b1eee2f732e310b7  implicit
1c42c39dff6ee55d    _tasks         72h0m0s    24h0m0s               b1eee2f732e310b7  implicit
ebf8464ccfc1129a    example-bucket infinite   168h0m0s              b1eee2f732e310b7  implicit
```

Login to the server you deployed InfluxDB v2. Run the following command to export data in InfluxDB Line Protocol format:

```shell
# The engine path is often "/var/lib/influxdb2/engine/".
export ENGINE_PATH="<engine-path>"
# Export all the data in example-bucket (ID=ebf8464ccfc1129a).
influxd inspect export-lp --bucket-id ebf8464ccfc1129a --engine-path $ENGINE_PATH --output-path influxdb_export.lp
```

> [!TIP]
>
> You can specify more concrete data set to be exported, like measurements and time range. Refer to the [`influxd inspect export-lp`](https://docs.influxdata.com/influxdb/v2/reference/cli/influxd/inspect/export-lp/) manual for details.

## Step 3: Import data to GreptimeDB

Copy the `influxdb_export.lp` file to a working directory. Before import data to GreptimeDB, if the data file is too large, it's recommended to split the data file into multiple slices:

```shell
split -l 1000 -d -a 10 influxdb_export.lp influxdb_export_slice.
# -l [line_count]    Create split files line_count lines in length.
# -d                 Use a numeric suffix instead of a alphabetic suffix.
# -a [suffix_length] Use suffix_length letters to form the suffix of the file name.
```

Now, import data to GreptimeDB via the HTTP API:

```shell
for file in influxdb_export_slice.*; do
    curl -i -H "Authorization: token $GREPTIME_USERNAME:$GREPTIME_PASSWORD" \
        -X POST "https://${GREPTIME_HOST}/v1/influxdb/api/v2/write?db=$GREPTIME_DB" \
        --data-binary @${file}
    sleep 1
done
```

You're done!
