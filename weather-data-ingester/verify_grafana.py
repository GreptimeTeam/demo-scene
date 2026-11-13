"""Exercise the dashboard queries through Grafana's PostgreSQL datasource."""

import argparse
import json
import os
import time
from pathlib import Path

import requests

from ingest import sql

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--region", default="east-asia")
args = parser.parse_args()
region = args.region.replace("'", "''")
center = sql(
    f"SELECT center_lat, center_lon FROM weather_regions WHERE region_id='{region}'"
)[0]["records"]["rows"][0]
bounds = sql(f"SELECT min(ts),max(ts) FROM satweave WHERE region_id='{region}'")[0][
    "records"
]["rows"][0]
if bounds[0] is None:
    raise RuntimeError("No satellite data loaded")
base = os.environ.get("GRAFANA_URL", "http://127.0.0.1:23000")
report = {}
for uid in ["weather-observatory", "weather-observatory-zh"]:
    response = requests.get(f"{base}/api/dashboards/uid/{uid}", timeout=30)
    response.raise_for_status()
    dashboard = response.json()["dashboard"]
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            query = target["rawSql"]
            for key, value in {
                "${region:sqlstring}": f"'{region}'",
                "${snapshot}": str(bounds[0]),
                "${center_lat}": str(center[0]),
                "${center_lon}": str(center[1]),
                "${radius}": "200",
            }.items():
                query = query.replace(key, value)
            body = {
                "from": str(bounds[0]),
                "to": str(bounds[1] + 3599999),
                "queries": [
                    {
                        **target,
                        "rawSql": query,
                        "intervalMs": 60000,
                        "maxDataPoints": 20000,
                    }
                ],
            }
            start = time.perf_counter()
            response = requests.post(f"{base}/api/ds/query", json=body, timeout=120)
            response.raise_for_status()
            result = response.json()["results"]["A"]
            if result.get("error") or result.get("status", 200) != 200:
                raise RuntimeError(result)
            rows = sum(
                len(f["data"]["values"][0]) if f["data"]["values"] else 0
                for f in result.get("frames", [])
            )
            if not rows:
                raise AssertionError(f"No data in {uid}/{panel['title']}")
            report[f"{uid}/{panel['id']}"] = {
                "title": panel["title"],
                "rows": rows,
                "http_ms": round((time.perf_counter() - start) * 1000, 2),
            }
Path("data").mkdir(exist_ok=True)
Path(f"data/grafana-check-{args.region}.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2)
)
print(json.dumps(report, ensure_ascii=False, indent=2))
