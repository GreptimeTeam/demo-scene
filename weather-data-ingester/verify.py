"""Verify stored data and measure SQL latency over the loaded historical interval."""

import argparse
import json
import statistics
import time
from pathlib import Path

from ingest import sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", default="east-asia")
    args = parser.parse_args()
    region = args.region.replace("'", "''")
    rows = sql(
        f"SELECT min(ts), max(ts), count(*) FROM pardig WHERE region_id='{region}'"
    )[0]["records"]["rows"][0]
    if not rows[2]:
        raise RuntimeError("No imported rows in this region")
    start, end, count = rows
    snapshot = sql(
        f"SELECT min(ts) FROM satweave WHERE region_id='{region}' AND ts BETWEEN CAST({start} AS TIMESTAMP) AND CAST({end} AS TIMESTAMP)"
    )[0]["records"]["rows"][0][0]
    if snapshot is None:
        raise RuntimeError("No shared hourly snapshot in this region")
    center_lat, center_lon = sql(
        f"SELECT center_lat, center_lon FROM weather_regions WHERE region_id='{region}'"
    )[0]["records"]["rows"][0]
    queries = {
        "time_aggregation": f"SELECT ts, avg(rain_mm_h), max(rain_mm_h) FROM pardig WHERE region_id='{region}' GROUP BY ts ORDER BY ts",
        "snapshot_join": f"SELECT p.grid_id, p.rain_mm_h, s.brightness_k FROM pardig p JOIN satweave s ON p.region_id=s.region_id AND p.grid_id=s.grid_id AND p.ts=s.ts WHERE p.region_id='{region}' AND s.region_id='{region}' AND p.ts=CAST({snapshot} AS TIMESTAMP) AND s.ts=CAST({snapshot} AS TIMESTAMP) ORDER BY p.rain_mm_h DESC LIMIT 20",
        "spatial_filter": f"SELECT count(*), avg(p.rain_mm_h) FROM pardig p WHERE p.region_id='{region}' AND p.ts=CAST({start} AS TIMESTAMP) AND st_distance_sphere_m(wkt_point_from_latlng(p.latitude,p.longitude),wkt_point_from_latlng({center_lat},{center_lon})) <= 200000",
    }
    results = {
        "region": args.region,
        "pardig_rows": count,
        "start_ms": start,
        "end_ms": end,
        "queries": {},
    }
    for name, query in queries.items():
        timings = []
        for _ in range(3):
            started = time.perf_counter()
            output = sql(query)
            timings.append((time.perf_counter() - started) * 1000)
        if not output[0]["records"]["rows"]:
            raise AssertionError(f"Empty result: {name}")
        results["queries"][name] = {
            "sql": query,
            "http_ms": timings,
            "median_http_ms": statistics.median(timings),
            "result": output,
        }
    Path("data").mkdir(exist_ok=True)
    Path(f"data/query-check-{args.region}.json").write_text(
        json.dumps(results, indent=2)
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
