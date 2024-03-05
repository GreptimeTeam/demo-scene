# Keyboard Monitor

## Step 1: Install requirements

```shell
pip3 install -r requirements.txt
```

## Step 2: Set up Greptime service

1. Obtain a free Greptime service from [GreptimeCloud](https://console.greptime.cloud/). 
2. Go to the "Connect" tab and find the connection string.
3. Copy `.env.example` to `.env` and set the connection string.

## Step 3: Start keyboard monitor

```shell
python3 agent.py
```

## Step 4: Query keyboard inputs statistics



```sql
SELECT hits, COUNT(*) as times
FROM keyboard_monitor
GROUP BY hits
ORDER BY times DESC limit 10;
```
