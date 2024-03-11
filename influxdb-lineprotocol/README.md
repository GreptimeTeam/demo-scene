# Ingestion with InfluxDB Line Protocol, Analysis with SQL and PromQL

## Step 1: Install requirements

```shell
pip3 install -r requirements.txt
```

## Step 2: Set up Greptime service

1. Obtain a free Greptime service from [GreptimeCloud](https://console.greptime.cloud/). 
2. Go to the "Connect" tab and find the connection string.
3. Copy `.env.example` to `.env` and set the connection string.

![Connection](/media/connstr.png)

## Step 3: Write data via line protocol


