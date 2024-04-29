# Migrate data from InfluxDB v1 to GreptimeDB

## Prerequisites

You need to be able to access your InfluxDB engine path, which contains your data files. If you run a server with InfluxDB's v1.8 official Docker Image, the engine path is `/var/lib/influxdb`.

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

## Step 2: Export data from InfluxDB v1 server

You can run the following commands to export data in InfluxDB's line protocol:

```shell
export DATABASE="<dbname>"         # possible value: mydb 
export ENGINE_PATH="<engine-path>" # possible value: /var/lib/influxdb

influx_inspect export \
    -database $DATABASE \
    -lponly \
    -datadir $ENGINE_PATH/data \
    -waldir $ENGINE_PATH/wal \
    -out /tmp/influxdb_export.lp
```

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
        -X POST "https://${GREPTIME_HOST}/v1/influxdb/write?db=$GREPTIME_DB" \
        --data-binary @${file}
    sleep 1
done
```

You're done!
