# Validation results

The default import was executed against GreptimeDB v1.3.0 standalone, with Grafana 12.2.1 and the built-in PostgreSQL datasource. Data covers September 1, 2026, UTC. The importer used Python 3.11.

| Dataset | East Asia | San Francisco Bay Area | Total |
| --- | ---: | ---: | ---: |
| PARDIG, 96 frames | 14,476,896 | 161,376 | 14,638,272 |
| SatWeave 11.2 μm, 24 frames | 3,619,224 | 40,344 | 3,659,568 |
| Total | 18,096,120 | 201,720 | 18,297,840 |

All 120 frames passed row-count, non-null-count, and numeric-sum verification against the extracted source values. The recorded import took 271.47 seconds overall, excluding image builds. Acknowledged HTTP write calls totaled 26.84 seconds for 1,929,658,290 payload bytes, approximately 681,709 acknowledged row writes per second. The first snapshot had been loaded during a smoke test and was rewritten. These numbers describe this local run, not a sustained ingestion benchmark.

The import report is `data/run-20261113T140636.json`; source URLs and transformation metadata are retained beside cached extracts. Cache files and local measurement outputs are excluded from Git.

Browser checks used isolated headless Chrome contexts with `en-US` and `zh-CN` locales. The entry page selected the corresponding dashboard. Manual language switching retained the Bay Area region, 50 km radius, snapshot, and time range. Neither context reported JavaScript exceptions or failing Grafana datasource responses during those checks. The invalid `continuous-PuBu` palette was replaced with Grafana's supported `continuous-BlPu` palette.

The extraction regression suite covers reversed latitude order, western longitude normalization, prime-meridian selection, missing values, precipitation unit conversion, hourly sampling within a half-open interval, city aliases, and rejected bounding boxes.

See [PERFORMANCE.md](PERFORMANCE.md) for the schema/index experiments and their adoption status. In particular, candidate spatial-query timings must not be attributed to the deployed dashboard schema.

Final container checks passed: four extraction regression tests, three SQL query checks for each region, and 20 Grafana panel queries per region (10 data panels in each language), for 40 successful datasource queries.

A fresh clone of the PR branch was also checked with an empty database volume and download cache. The README's 30-minute Bay Area import downloaded three source frames and verified 5,043 observations. Repeating the command used all three cached frames and retained the same row count. All three SQL checks and 20 bilingual Grafana panel queries passed. City aliases, custom bounding boxes, and the three-day row estimate were checked with `--plan`. Docker image layers were reused; this was not an uncached image-build test. The local Docker address pool was exhausted, so this isolated run used a temporary explicit subnet and separate ports.

Seven extraction regression tests pass, including interrupted metadata writes and distinct city/bounding-box inputs on opposite sides of a grid boundary. The three added regressions failed before their corresponding fixes.
