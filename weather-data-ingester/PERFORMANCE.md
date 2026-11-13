# Schema and index evaluation

Evaluated on GreptimeDB v1.3.0 standalone with 14,638,272 real PARDIG rows from the default import. The procedure follows the GreptimeDB performance diagnosis, table design, and performance tuning skills. Measurements use HTTP SQL on a shared local Docker host; they are not service-level guarantees or cross-database benchmarks.

## Deployed schema

`pardig` and `satweave` retain `PRIMARY KEY(region_id, grid_id)` and `ts TIMESTAMP TIME INDEX`. The leading region key matches dashboard filters. Grid identity is required to keep distinct cells separate and make repeated imports idempotent. Coordinates remain DOUBLE fields. No explicit secondary index is configured in the deployed tables.

The tables retain default deduplication and WAL behavior. Append-only mode would change replay semantics. The observed metrics did not establish a write-stall or cache-capacity problem, so no server cache or write-buffer overrides were applied. PARDIG and SatWeave use separate tables with different sampling intervals and metrics.

The hotspot join filters both inputs explicitly by region and timestamp. `verify.py` resolves the selected center before the spatial query, matching the dashboard's constant point instead of introducing a catalog cross join.

## Isolated candidates

All candidates are in `weather_perf`; the dashboard still reads `weather`. Each candidate contains the same 14,638,272 precipitation observations and was flushed before comparison.

| Candidate | Primary key | Explicit indexes | Finding |
| --- | --- | --- | --- |
| `pardig_plain` | region + string grid ID | None | Baseline |
| `pardig_geo` | region + string grid ID | Inverted indexes on DOUBLE latitude and longitude | Inconsistent latency improvement; not selected |
| `pardig_grid` | region + integer latitude/longitude grid coordinates | Inverted indexes on grid coordinates | Fast selective queries, but InfluxDB string tags cannot write to INT keys in v1.3.0 |
| `pardig_grid_string` | region + four-digit latitude/longitude grid coordinates | Inverted indexes on grid coordinates | Fast selective queries; InfluxDB writes and replay deduplication passed |

The integer-key protocol probe returned HTTP 400: `column lat_idx expect type Int32(Int32Type), given: STRING(12)`. The string-key probe accepted two identical writes and returned one stored row.

For the string candidate, `lat_idx = lpad(string(round((latitude + 90) * 10)), 4, '0')`, with the equivalent longitude expression using +180. Fixed width preserves numeric ordering in string range predicates.

### Spatial query comparison

The query selects points within 200 km of Shanghai. The candidate first filters a conservative grid bounding box, then applies the same exact `st_distance_sphere_m` predicate. Both implementations returned 1,189 cells and matching precipitation means at each timestamp (relative tolerance 1e-10).

One warm-up per query was excluded. Baseline and candidate executions were interleaved, with three measured executions per query. Values are median HTTP round-trip times.

| UTC snapshot, September 1, 2026 | Baseline | String grid candidate |
| --- | ---: | ---: |
| 00:00 | 767.0 ms | 14.0 ms |
| 12:00 | 737.5 ms | 9.7 ms |
| 23:00 | 722.5 ms | 9.4 ms |

This compares schema, index, and query changes together. It does not isolate the contribution of the inverted index. The integer candidate's `EXPLAIN ANALYZE VERBOSE` showed 1,628 rows leaving the scan before the exact distance filter, compared with 150,801 for the original snapshot scan. Warm caches and differing SST layouts affect these measurements.

The DOUBLE-field index candidate produced medians of 249–527 ms in an earlier, non-interleaved run, compared with 475–741 ms for its baseline. This result alone does not establish a reliable index benefit.

## Reproduce the string candidate

The following creates a separate table and copies the loaded precipitation rows. Run once through the SQL endpoint; it does not replace the demo tables.

```sql
CREATE DATABASE weather_perf;
CREATE TABLE weather_perf.pardig_grid_string (
    region_id STRING,
    lat_idx STRING INVERTED INDEX,
    lon_idx STRING INVERTED INDEX,
    latitude DOUBLE,
    longitude DOUBLE,
    rain_mm_h DOUBLE,
    ts TIMESTAMP TIME INDEX,
    PRIMARY KEY(region_id, lat_idx, lon_idx)
);
INSERT INTO weather_perf.pardig_grid_string
SELECT region_id,
       lpad(CAST(CAST(round((latitude + 90) * 10) AS INT) AS STRING), 4, '0'),
       lpad(CAST(CAST(round((longitude + 180) * 10) AS INT) AS STRING), 4, '0'),
       latitude, longitude, rain_mm_h, ts
FROM weather.pardig;
ADMIN flush_table('weather_perf.pardig_grid_string');

EXPLAIN ANALYZE VERBOSE
SELECT count(*), avg(rain_mm_h)
FROM weather_perf.pardig_grid_string
WHERE region_id = 'east-asia'
  AND ts = CAST(1788220800000 AS TIMESTAMP)
  AND lat_idx BETWEEN '1194' AND '1230'
  AND lon_idx BETWEEN '2993' AND '3036'
  AND st_distance_sphere_m(
      wkt_point_from_latlng(latitude, longitude),
      wkt_point_from_latlng(31.2304, 121.4737)) <= 200000;
```

Local evidence is saved under `data/performance/`: deployed schemas, baseline and candidate plans, metrics, build timings, and `interleaved-comparison.json`. This directory is excluded from Git.

## Adoption status

The string grid candidate remains an isolated performance experiment and is not selected for the main demo. The main dashboard keeps direct distance predicates on the original coordinates so its SQL exposes the geo functions without encoded range bounds. Its full InfluxDB batch-ingestion throughput, regional aggregation, and precipitation/satellite JOIN regressions have not been measured. Generalizing the bounding-box query must preserve exact distance results near the poles and antimeridian. Changing the primary key requires new tables and validated migration; adding an index alone does not implement this schema.
