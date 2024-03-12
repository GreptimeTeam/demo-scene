# Ingestion with InfluxDB Line Protocol, Analysis with SQL and PromQL

## Prerequisites

This demo requires Python 3.12 or later. And you should install packages with:

```shell
pip3 install -r requirements.txt
```

## Step 1: Set up Greptime service

1. Obtain a free Greptime service from [GreptimeCloud](https://console.greptime.cloud/). 
2. Go to the "Connect" tab and find the connection string.
3. Copy `.env.example` to `.env` and set the connection string.

![Connection](/media/connstr.png)

## Step 2: Write data via line protocol

Download the sample data:

```shell
curl -O https://raw.githubusercontent.com/influxdata/influxdb2-sample-data/master/air-sensor-data/air-sensor-data.lp 
```

> [!TIP]
>
> Use `https://mirror.ghproxy.com/https://raw.githubusercontent.com/influxdata/influxdb2-sample-data/master/air-sensor-data/air-sensor-data.lp` if you encounter network issues.

Ingest the air sensors data with:

```shell
python3 ingest.py air-sensor-data.lp
```

The script supports ingesting any data in [line protocol format](https://docs.influxdata.com/influxdb/v2/reference/syntax/line-protocol/). You can specify the data file and timestamp precision:

```
$ python3 ingest.py --help
usage: ingest.py [-h] [--precision PRECISION] file

positional arguments:
  file                  File to ingest

options:
  -h, --help            show this help message and exit
  --precision PRECISION
                        Precision of the data (default: s)
```

## Step 3: Query data with SQL and PromQL


