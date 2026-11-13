CREATE TABLE IF NOT EXISTS vibration_raw (
    greptime_timestamp TIMESTAMP(9) TIME INDEX,
    device STRING,
    scenario STRING,
    acceleration DOUBLE,
    PRIMARY KEY (device)
) WITH (ttl = '15m');

CREATE TABLE IF NOT EXISTS vibration_spectrum (
    greptime_timestamp TIMESTAMP(9) TIME INDEX,
    device STRING,
    frequency STRING,
    scenario STRING,
    amplitude DOUBLE,
    PRIMARY KEY (device, frequency)
) WITH (ttl = '15m');

CREATE TABLE IF NOT EXISTS vibration_features (
    greptime_timestamp TIMESTAMP(9) TIME INDEX,
    device STRING,
    scenario STRING,
    rms DOUBLE,
    peak DOUBLE,
    crest_factor DOUBLE,
    PRIMARY KEY (device)
) WITH (ttl = '1d');
