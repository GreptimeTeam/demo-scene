CREATE TABLE IF NOT EXISTS trades (
    dataset STRING,
    symbol STRING,
    trade_id BIGINT,
    price DECIMAL(24, 8),
    quantity DECIMAL(24, 8),
    notional DECIMAL(38, 16),
    taker_buy BOOLEAN,
    event_time TIMESTAMP(6) TIME INDEX,
    ingested_at TIMESTAMP(6),
    origin STRING,
    PRIMARY KEY (dataset, symbol, trade_id)
);

CREATE TABLE IF NOT EXISTS ingestion (
    dataset STRING,
    symbol STRING,
    worker STRING,
    ts TIMESTAMP(6) TIME INDEX,
    state STRING,
    rows_written BIGINT,
    write_ms DOUBLE,
    last_event_time TIMESTAMP(6),
    status_text STRING,
    PRIMARY KEY (dataset, symbol, worker)
);

CREATE TABLE IF NOT EXISTS gaps (
    dataset STRING,
    symbol STRING,
    ts TIMESTAMP(6) TIME INDEX,
    first_missing_id BIGINT,
    last_missing_id BIGINT,
    status_text STRING,
    PRIMARY KEY (dataset, symbol)
);

CREATE FLOW IF NOT EXISTS crypto_candles_1m
SINK TO candles_1m
AS
SELECT dataset, symbol,
       date_bin(INTERVAL '1 minute', event_time) AS bucket,
       first_value(price ORDER BY event_time, trade_id) AS open,
       max(price) AS high,
       min(price) AS low,
       last_value(price ORDER BY event_time, trade_id) AS close,
       sum(quantity) AS volume,
       sum(notional) AS quote_volume,
       count(*) AS trade_count,
       sum(CASE WHEN taker_buy THEN quantity ELSE 0 END) AS buy_volume
FROM trades
GROUP BY dataset, symbol, bucket;

-- One latest changed quote per sampling interval; Binance bookTicker has no event timestamp.
CREATE TABLE IF NOT EXISTS quotes (
    dataset STRING NOT NULL,
    symbol STRING NOT NULL,
    sampled_at TIMESTAMP(6) TIME INDEX,
    update_id BIGINT NOT NULL,
    bid_price DECIMAL(24,8) NOT NULL,
    bid_quantity DECIMAL(24,8) NOT NULL,
    ask_price DECIMAL(24,8) NOT NULL,
    ask_quantity DECIMAL(24,8) NOT NULL,
    received_at TIMESTAMP(6) NOT NULL,
    PRIMARY KEY (dataset, symbol)
);
