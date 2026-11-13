"""Read public Zarr frames, cache regional subsets, and write Influx line protocol."""

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import time
from pathlib import Path
from urllib.parse import urlencode

import aiohttp
import numpy as np
import pandas as pd
import requests
import xarray as xr
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from regions import CITIES, REGIONS, select_regions

DATASETS = {
    "pardig": (
        "pardig_1/NRT/zarr",
        "predictions",
        "precipitation",
        "rain_mm_h",
        "m h**-1",
        15,
    ),
    "satweave": (
        "satweave_1/zarr",
        "mosaic",
        "mosaic_11200_nm",
        "brightness_k",
        "K",
        60,
    ),
}
URL = os.environ.get("GREPTIME_URL", "http://127.0.0.1:28400").rstrip("/")
SESSION = requests.Session()
SESSION.mount(
    "http://",
    HTTPAdapter(
        max_retries=Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods=["POST", "GET"],
        )
    ),
)


def sql(statement, database="weather"):
    response = SESSION.post(
        f"{URL}/v1/sql", params={"db": database}, data={"sql": statement}, timeout=120
    )
    if not response.ok:
        raise RuntimeError(f"SQL failed ({response.status_code}): {response.text}")
    result = response.json()
    if "error" in result:
        raise RuntimeError(result)
    return result["output"]


def parse_time(value):
    result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError(
            "Time must include a timezone, for example 2026-09-01T00:00:00Z"
        )
    return result.astimezone(dt.timezone.utc)


def timestamps(start, end, cadence):
    current = start
    while current < end:
        if current.minute % cadence == 0:
            yield current
        current += dt.timedelta(minutes=15)


def crop(data, regions, field):
    # Boolean indexing handles both latitude orders and longitudes crossing zero.
    longitude = (data.longitude.values + 180) % 360 - 180
    latitude = data.latitude.values
    frames = []
    for region, spec in regions.items():
        west, south, east, north = spec["bbox"]
        yi = np.flatnonzero((latitude >= south - 1e-8) & (latitude <= north + 1e-8))
        xi = np.flatnonzero((longitude >= west - 1e-8) & (longitude <= east + 1e-8))
        if not len(yi) or not len(xi):
            raise ValueError(f"Region {region} contains no source grid points")
        frame = (
            data.isel(latitude=yi, longitude=xi).to_dataframe(name=field).reset_index()
        )
        frame = frame[["latitude", "longitude", field]].copy()
        frame["latitude"] = frame.latitude.round(1)
        frame["longitude"] = ((frame.longitude + 180) % 360 - 180).round(1)
        frame[field] = frame[field].astype("float64")
        if field == "rain_mm_h":
            frame[field] *= 1000
        if np.isinf(frame[field]).any():
            raise ValueError("Source contains infinite values")
        frame["region_id"] = region
        frame["grid_id"] = (
            (frame.latitude.add(90).mul(10).round().astype(int) * 3600)
            + frame.longitude.add(180).mul(10).round().astype(int)
        ).astype(str)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def extract(dataset, instant, regions, cache):
    bucket, store, variable, field, unit, _ = DATASETS[dataset]
    key = hashlib.sha256(json.dumps(regions, sort_keys=True).encode()).hexdigest()[:16]
    path = cache / f"{dataset}-{instant:%Y%m%dT%H%M%S}-{key}.csv.gz"
    meta = path.with_suffix(".json")
    if path.exists() and meta.exists():
        return (
            pd.read_csv(path, dtype={"grid_id": str}),
            json.loads(meta.read_text()),
            True,
        )
    source = f"https://storage.googleapis.com/{bucket}/2026_to_present/{instant:%Y%m%dT%H%M%S}/{store}.zarr"
    # A full spatial chunk serves all requested regions, avoiding duplicate downloads.
    with xr.open_zarr(
        source,
        chunks=None,
        storage_options={
            "client_kwargs": {
                "trust_env": True,
                "timeout": aiohttp.ClientTimeout(total=180),
            }
        },
    ) as ds:
        actual = pd.Timestamp(ds.time.values.reshape(-1)[0]).tz_localize("UTC")
        if actual != instant or ds[variable].attrs.get("units") != unit:
            raise ValueError(f"Unexpected source time or units: {source}")
        data = ds[variable].load()
        frame = crop(data, regions, field)
        metadata = {
            "source": source,
            "time": instant.isoformat(),
            "variable": variable,
            "attributes": ds.attrs,
            "variable_attributes": ds[variable].attrs,
            "regions": regions,
        }
    temporary = path.with_suffix(".tmp")
    frame.to_csv(temporary, index=False, compression="gzip")
    temporary.replace(path)
    temporary_meta = meta.with_suffix(".json.tmp")
    temporary_meta.write_text(json.dumps(metadata, indent=2))
    temporary_meta.replace(meta)
    return frame, metadata, False


def init_database(regions):
    version = sql("SELECT version()", "public")[0]["records"]["rows"][0][0]
    if version != "1.3.0":
        raise ValueError(f"This demo requires GreptimeDB 1.3.0, got {version}")
    sql("CREATE DATABASE IF NOT EXISTS weather", "public")
    for table, spec in DATASETS.items():
        sql(
            f"CREATE TABLE IF NOT EXISTS {table} (region_id STRING, grid_id STRING, latitude DOUBLE, longitude DOUBLE, {spec[3]} DOUBLE, ts TIMESTAMP TIME INDEX, PRIMARY KEY(region_id, grid_id))"
        )
    sql(
        "CREATE TABLE IF NOT EXISTS weather_regions (region_id STRING PRIMARY KEY, region_name STRING, center_lat DOUBLE, center_lon DOUBLE, ts TIMESTAMP TIME INDEX)"
    )
    for key, spec in regions.items():
        # All keys/names are generated from the local registry or numeric bounds.
        sql(
            f"INSERT INTO weather_regions VALUES ('{key}', '{spec['name']}', {spec['center'][0]}, {spec['center'][1]}, '2000-01-01T00:00:00Z')"
        )


def ingest_frame(dataset, instant, frame):
    field = DATASETS[dataset][3]
    timestamp = int(instant.timestamp() * 1000)
    elapsed, total_bytes = 0.0, 0
    for offset in range(0, len(frame), 10000):
        lines = []
        for row in frame.iloc[offset : offset + 10000].itertuples(index=False):
            value = getattr(row, field)
            fields = f"latitude={row.latitude},longitude={row.longitude}"
            if not pd.isna(value):
                fields += f",{field}={float(value)!r}"
            lines.append(
                f"{dataset},region_id={row.region_id},grid_id={row.grid_id} {fields} {timestamp}"
            )
        payload = "\n".join(lines).encode()
        start = time.perf_counter()
        response = SESSION.post(
            f"{URL}/v1/influxdb/api/v2/write",
            params={"bucket": "weather", "precision": "ms"},
            data=payload,
            headers={"Content-Type": "text/plain"},
            timeout=120,
        )
        response.raise_for_status()
        elapsed += time.perf_counter() - start
        total_bytes += len(payload)
    return elapsed, total_bytes


def verify_frame(dataset, instant, frame):
    field = DATASETS[dataset][3]
    actual = sql(
        f"SELECT region_id, count(*), count({field}), sum({field}) FROM {dataset} WHERE ts='{instant.isoformat()}' GROUP BY region_id"
    )[0]["records"]["rows"]
    actual = {row[0]: row[1:] for row in actual}
    for region, subset in frame.groupby("region_id"):
        expected_sum = math.fsum(subset[field].dropna())
        count, valid, total = actual[region]
        if count != len(subset) or valid != int(subset[field].count()):
            raise AssertionError(
                (dataset, instant, region, "row count mismatch", actual[region])
            )
        if valid and not math.isclose(total, expected_sum, rel_tol=1e-9, abs_tol=1e-8):
            raise AssertionError(
                (dataset, instant, region, "sum mismatch", total, expected_sum)
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2026-09-01T00:00:00Z")
    parser.add_argument(
        "--end", default="2026-09-02T00:00:00Z", help="Exclusive UTC end"
    )
    parser.add_argument("--region", action="append", choices=REGIONS)
    parser.add_argument(
        "--city",
        action="append",
        help="City name or supported Chinese alias; repeatable",
    )
    parser.add_argument(
        "--radius-km",
        type=float,
        default=200,
        help="City bounding-box half-width; not a circular crop",
    )
    parser.add_argument(
        "--bbox", type=float, nargs=4, metavar=("WEST", "SOUTH", "EAST", "NORTH")
    )
    parser.add_argument("--list-regions", action="store_true")
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Show row estimate without downloading or writing",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    if args.list_regions:
        print(
            json.dumps(
                {"regions": REGIONS, "cities": CITIES}, indent=2, ensure_ascii=False
            )
        )
        return
    regions = select_regions(args)
    start, end = parse_time(args.start), parse_time(args.end)
    if start.year < 2026 or end <= start or end > dt.datetime.now(dt.timezone.utc):
        parser.error("Use a historical interval starting in 2026 or later")
    if any(t.minute % 15 or t.second or t.microsecond for t in (start, end)):
        parser.error("Start and end must align to 15-minute boundaries")
    grid_count = 0
    for spec in regions.values():
        west, south, east, north = spec["bbox"]
        grid_count += (
            math.floor(min(east, 179.9) * 10 + 1e-7) - math.ceil(west * 10 - 1e-7) + 1
        ) * (math.floor(north * 10 + 1e-7) - math.ceil(south * 10 - 1e-7) + 1)
    plan = {
        "start": start.isoformat(),
        "end_exclusive": end.isoformat(),
        "regions": regions,
        "rows": {
            name: grid_count * len(list(timestamps(start, end, spec[5])))
            for name, spec in DATASETS.items()
        },
    }
    print(json.dumps(plan, indent=2), flush=True)
    if args.plan:
        return
    cache = args.data_dir / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    init_database(regions)
    report = {
        "plan": plan,
        "frames": [],
        "rows": 0,
        "write_seconds": 0.0,
        "write_bytes": 0,
    }
    begun = time.perf_counter()
    report_path = (
        args.data_dir / f"run-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}.json"
    )
    for dataset, spec in DATASETS.items():
        for instant in timestamps(start, end, spec[5]):
            before = time.perf_counter()
            frame, metadata, cached = extract(dataset, instant, regions, cache)
            read_seconds = time.perf_counter() - before
            write_seconds, size = ingest_frame(dataset, instant, frame)
            verify_frame(dataset, instant, frame)
            report["rows"] += len(frame)
            report["write_seconds"] += write_seconds
            report["write_bytes"] += size
            report["frames"].append(
                {
                    "dataset": dataset,
                    "time": instant.isoformat(),
                    "rows": len(frame),
                    "valid": int(frame[spec[3]].count()),
                    "source": metadata["source"],
                    "cache_hit": cached,
                    "read_seconds": read_seconds,
                    "write_seconds": write_seconds,
                }
            )
            report["wall_seconds"] = time.perf_counter() - begun
            report["acknowledged_rows_per_second"] = (
                report["rows"] / report["write_seconds"]
            )
            report_path.write_text(json.dumps(report, indent=2))
            print(
                f"{dataset} {instant.isoformat()} rows={len(frame):,} read={read_seconds:.2f}s write={write_seconds:.2f}s verified",
                flush=True,
            )
    print(
        f"Report: {report_path}; {report['rows']:,} rows; acknowledged HTTP throughput: {report['acknowledged_rows_per_second']:,.0f} rows/s",
        flush=True,
    )
    params = urlencode(
        {
            "from": int(start.timestamp() * 1000),
            "to": int(end.timestamp() * 1000) - 1,
            "var-region": next(iter(regions)),
        }
    )
    print(f"Grafana: http://localhost:23000/?{params}", flush=True)


if __name__ == "__main__":
    main()
