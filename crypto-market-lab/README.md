# Crypto market lab

A local market-quality desk for Binance Spot BTC/USDT and ETH/USDT. GreptimeDB stores public trades and sampled best quotes. A Flow maintains minute OHLCV, quote volume, trade counts, and taker-buy volume.

## Run

Requires Docker Compose and access to Binance public market-data endpoints. The optional frontend regression test uses Node.js. No exchange account or API key is required.

```sh
cd crypto-market-lab
docker compose up -d --build
```

- Market desk: http://localhost:25200
- Chinese desk: http://localhost:25200/?lang=zh-CN
- Grafana diagnostics: http://localhost:25300
- GreptimeDB HTTP: http://localhost:25400

The desk language selector switches between English and 简体中文. The URL `lang` parameter overrides the saved browser choice; otherwise the desk uses the saved choice or browser language. Switching retains the selected market and time mode. SQL remains unchanged.

The history worker imports the most recent published daily archive shared by both symbols, checking the previous three UTC days. Live trades and quotes run independently. Archives contain trades; historical quotes are unavailable. The desk supports the live hour, the final hour of the imported archive, and the active replay dataset. Clicking the chart or a row in Time & sales opens the largest 25 trades in that minute. The SQL inspector shows the chart query and compares a complete archive day; `/#lab` opens this panel directly.

```sh
docker compose logs -f history live quotes
```

## Data and schema

| Table | Time index | Primary key | Contents |
| --- | --- | --- | --- |
| `trades` | `event_time`, microseconds | `dataset, symbol, trade_id` | Exact decimal price, quantity, notional, and taker side |
| `quotes` | `sampled_at`, microseconds | `dataset, symbol` | Latest changed best quote per roughly one-second sampling interval |
| `candles_1m` | `bucket`, microseconds | `dataset, symbol` | Flow-maintained minute aggregates |
| `ingestion` | `ts`, microseconds | `dataset, symbol, worker` | Collector status and submitted batch statistics |
| `gaps` | `ts`, microseconds | `dataset, symbol` | Observed missing trade-ID ranges; no automatic backfill |

The venue is Binance Spot throughout this demo. Symbol names are scoped to that venue. The row identity includes the primary key and time index: repeated writes deduplicate only when both match. Different trade IDs at the same microsecond remain separate. A changed timestamp for the same trade ID is a different row. Historical imports and live capture use `market`; replay uses an isolated dataset.

Price and quantity use `DECIMAL(24,8)`; notional uses `DECIMAL(38,16)`. Parsing rejects unsupported price or quantity precision. Open and close are ordered by event time, then trade ID. Trade IDs are event identifiers and do not appear in aggregate-table keys. The schema does not request inverted indexes on trade IDs.

`quotes.received_at` records local message reception. Binance JSON `bookTicker` has no exchange event timestamp. The collector writes only changed observations; the age shown is time since reception, not exchange latency. Quote update IDs are fields, not series dimensions. These snapshots do not contain full depth or order-level events.

`trades.ingested_at` records batch submission time, not network reception. Submitted-row statistics count submitted batches, including repeated imports; they are not unique-trade counts. No TTL is configured; stored trades, quotes, and telemetry accumulate until explicitly removed.

## Reproduce and verify

Downloaded ZIPs, checksums, and generated verification reports are cached in ignored `data/`. Database files live in a Docker volume. Raw datasets are not tracked in Git. `datasets.json` records the source URLs and SHA-256 values for the verified reference day. The downloader validates archives against the provider's `.CHECKSUM` before import.

```sh
docker compose run --rm ingest history --date 2026-11-13
docker compose run --rm --entrypoint python ingest verify.py \
  --history-date 2026-11-13 --grafana http://grafana:3000
docker compose run --rm --entrypoint python ingest -m unittest test_quotes.py test_replay.py test_desk.py
node test_web.cjs en
node test_web.cjs zh-CN
```

Verification covers same-microsecond identities, repeated writes, event ordering, late arrivals, Flow totals, official daily candles, Grafana queries, replay completion and cancellation, pause boundaries, single-trade steps, future-event exclusion, and bilingual interaction handlers. HTTP integration tests require both imported symbols and a running desk. Grafana checks require recent live data.

## Playback and chart controls

The transport below the chart accepts an archived UTC start minute and a 1- or 5-minute interval. **Load replay** creates an isolated dataset and loads it paused. Play starts the event clock; pause acknowledges the last committed batch. Step writes exactly one trade, including when several trades share a timestamp. Speed can change between 1×, 10×, and 100× during playback or while paused. Space toggles play/pause and the right arrow advances one trade when focus is outside form controls.

The replay chart, tape, profile, and selected-minute queries are bounded by the same committed event time and trade ID. One-second and replay candles are calculated from raw events; other minute candles use the Flow table. Replay never displays live quotes. A new interval creates another dataset; stopped runs retain partial results. One run is active at a time, with a maximum of 100,000 trades. Restarting the desk ends its in-memory replay session. Stored datasets remain queryable in Grafana.

The chart supports mouse-wheel zoom and a crosshair. Trade bubbles show the most recent 200 trades, with size determined by base quantity and color by aggressor side. Time & sales displays the most recent 80. Volume at price groups executed base volume into price bands over the selected window; it does not represent resting orders or full market depth. Cumulative delta sums buy volume minus sell volume from the window start. No order placement, matching simulation, or P&L is included.


The command-line replay reads a downloaded archive and preserves original event timestamps:

```sh
docker compose run --rm ingest replay --date 2026-11-13 --symbols BTCUSDT \
  --start 2026-11-13T12:00:00Z --end 2026-11-13T12:01:00Z --speed 100
```

The command prints its isolated dataset name. Select that dataset and original time range in Grafana. Command-line replay datasets can be inspected in Grafana; the desk follows runs started from its playback controls.

The SQL comparison runs three alternating raw/Flow queries and reports median HTTP round-trip time, including serialization. It checks exact per-minute counts, volumes, and notionals. Results depend on local hardware, concurrent ingestion, and cache state; this is not a controlled engine benchmark.

## Sources

- [Binance public archives](https://github.com/binance/binance-public-data)
- [Binance market-data-only endpoints](https://developers.binance.com/en/docs/products/spot/faqs/market_data_only)
- [Binance WebSocket payloads](https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md)
- [TradingView Bar Replay controls](https://www.tradingview.com/support/solutions/43000474024-how-do-i-turn-bar-replay-on/)
- [Bookmap volume dots and chart components](https://bookmap.com/knowledgebase/docs/KB-SettingUpAndOperating-HeatmapMainChart)
- [Aperiodic](https://github.com/aperiodic-io), inspiration for market-microstructure exploration

Market data remains subject to its provider's terms. The repository contains download code and provenance, not a redistributed archive.
