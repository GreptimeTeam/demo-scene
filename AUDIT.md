# Demo audit — GreptimeDB v1.3

Audit date: 2026-11-13. Local container tests used GreptimeDB v1.3.0, isolated Compose projects, random loopback ports, and fresh test data. A successful startup alone is not treated as an end-to-end result.

## Changes

- Shared GreptimeDB version updated to v1.3.0; startup uses `--grpc-bind-addr`. Dify's data volume now matches the database data directory.
- Kafka advertises its Compose hostname and creates its topic after broker readiness. Pipeline initialization propagates HTTP failures; dependent collectors wait for initialization.
- Flink builds the repository's local sink, uses the Kafka connector for Flink 1.20, and quotes the reserved SQL column `size`.
- OpenSky uses OAuth2 and current state vectors. Flight measurements are fields; only `icao24` is a tag. Existing flight tables require a fresh database because primary keys changed.
- EV mock parsing and battery data are corrected; the image uses Python 3.11 and a pinned Poetry version. The missing Grafana bind mount was removed.
- Keyboard Monitor handles empty aggregates, refreshes cached queries, queries complete local calendar days across timezone offsets, and stops after repeated write failures.
- InfluxDB migration instructions use the correct database variable and stop on HTTP failures. Ollama's Compose build explicitly selects its lowercase Dockerfile.
- Django waits for its trace table before creating the aggregation Flow; initialization can run again.
- Preset Grafana dashboards have English and Chinese versions. The root URL selects a language; manual links retain time ranges and filters. Translation parity is checked in CI.

## Verification

| Demo | Verified | Remaining limit |
| --- | --- | --- |
| OTel playground (imported) | Shop checkout, traces/logs/metrics, Flow output, datasource health, 80/80 bilingual data panels, trace selection outside the time range, log filters | Headless Chrome language navigation and screenshots verified |
| Native Histogram Lab (new) | OTLP exponential histogram ingestion, all 8 bilingual panels, scenario change; observed long-tail mean ≈76 ms and P99 ≈1.15 s | Measurements vary with random delays and host load |
| Vibration Lab (new) | Ingestion into all three tables, 513 spectrum bins/window, all 10 bilingual panels, scenario change, FFT amplitude/frequency and fault-feature tests | Synthetic signal, no hardware validation |
| Kafka | Stack startup; log and CPU metric tables created | No external Kafka cluster tested |
| Flink | Maven test and Java 11 container build; job submission; 47,001 ingested rows observed | Single local job |
| Vector | Pipeline registration and collector startup; 21 tables created | Cloud credentials not tested |
| Nginx | Stack startup; log, metric, and aggregate tables created | Headless Chrome dashboard screenshot verified |
| Elasticsearch ingestion | Logstash stack startup and Nginx log table creation | Local generated logs |
| Node Exporter | Prometheus scraping; 607 tables created | Host is the Docker Linux VM |
| Grafana Alloy | Collector startup; 529 metric/log tables created | Headless Chrome dashboard screenshot verified |
| PostgreSQL FDW | Foreign-table query returned 531 rows | Local connection |
| Cloudflare Workers | Local Worker proxy request, event ingestion, and `/_stats` query | Cloud deployment/Hyperdrive credentials not tested |
| Django tracing | Fresh 404 request → JSON2 summary/filter → trace link → Django/SQLite spans | Headless Chrome dashboard screenshot verified |
| Self-hosted game analytics | Stack startup and event/metric table creation | Unity client not run |
| EV telemetry | Complete mock stack startup and 20 metric tables; observer image build | Real Tesla account/API not tested |
| Flight ingestion | OAuth cache/refresh and bounding-box tests; Go SDK wrote a state row; actual DDL has only `icao24` as primary key | No OpenSky credentials for live polling |
| GenAI observability | App dependencies/import, base stack, real OTLP SDK fixture ingestion and Flow DDL | No paid model call or load profile run |
| Ollama telemetry | App image build and Ollama/Collector/database startup | Model generation not run |
| Dify monitoring | Compose configuration, Trace V1 fixture ingestion and Flow DDL | External Dify application not connected |
| InfluxDB line protocol | Python SDK write/read against v1.3 | UI interaction not run |
| InfluxDB v1/v2 migration | Both GreptimeDB write endpoints returned HTTP 204 for line protocol | No production/source InfluxDB export migrated |
| Telegraf | Local `--once` collection with endpoint adapted to the test database; 17 CPU rows verified | Cloud credentials not tested |
| Keyboard Monitor | Source review and Python syntax checks | OS keyboard permissions and Streamlit interaction not tested |

All 18 Compose demo definitions parse. OTel playground's rendered configuration starts separately. The translation generator verifies 11 dashboard pairs; playground checks its four pairs independently. HTTP checks cover Chinese/English routing and preservation of query parameters, including the non-default playground port. `git diff --check` passes.

Headless Chrome verified English/Chinese default routing, language links preserving service/time filters, and both lab scenario controls. Screenshots were refreshed for the playground, both labs, Django, Nginx, Cloudflare Workers, game analytics, and Alloy. Vibration waveform time bounds and spectrum legend options were corrected after visual inspection. External-account screenshots were retained and were not revalidated. A clean checkout of the playground successfully fetched the pinned upstream revision and rendered its Compose configuration. Local README links resolve. Live demo sites were not modified. No deployment was performed.

## Schema review

Reviewed against the local `greptimedb-table-design` skill and v1.3 table-design documentation. Flight measurement tags were corrected. New vibration tables retain device/time identity; frequency distinguishes bins with the same window timestamp, while scenario and measurements remain fields. Short TTLs retain raw signals/spectra for 15 minutes and features for one day.

Existing append-only log/event tables and deduplicated Flow sinks retain their storage semantics. No speculative indexes, partitions, or bulk primary-key migrations were added.

## Feature scope

The additions are limited to an integrated observability playground, native histograms, and the approved IoT vibration experiment. Existing JSON2/Trace V2 and Flow demos remain in place. No new demo was added solely to cover every release feature, and experimental semantic-graph behavior is not presented as a stock v1.3 capability.
