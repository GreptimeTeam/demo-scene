"""Generate the provisioned Grafana dashboard and its SQL query catalog."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DS = {"type": "grafana-postgresql-datasource", "uid": "weather-pg"}
panels = []
queries = {}


def panel(title, kind, x, y, w, h, query=None, unit="short", description=""):
    item = {
        "id": len(panels) + 1,
        "title": title,
        "type": kind,
        "gridPos": {"x": x, "y": y, "w": w, "h": h},
        "description": description,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "color": {"mode": "palette-classic"},
                "custom": {},
            },
            "overrides": [],
        },
        "options": {},
    }
    if query:
        item["datasource"] = DS
        item["targets"] = [
            {
                "datasource": DS,
                "refId": "A",
                "editorMode": "code",
                "format": "time_series" if kind == "timeseries" else "table",
                "rawQuery": True,
                "rawSql": query,
            }
        ]
        queries[str(item["id"])] = {"title": title, "sql": query}
    panels.append(item)
    return item


header = panel("WEATHER OBSERVATORY  /  GreptimeDB", "text", 0, 0, 24, 3)
header["options"] = {
    "mode": "markdown",
    "content": "### A day of rain and clouds, in SQL\n**PARDIG + SatWeave** · 0.1° source grid · GreptimeDB **v1.3.0** · InfluxDB writes → PostgreSQL queries → Grafana\n\nChoose a **region**, a historical **time range**, and a **snapshot**. Maps show the snapshot; charts follow the time range. **Radius** applies to the local rainfall chart. All times are UTC.",
}
region = "region_id = ${region:sqlstring}"
window = f"{region} AND $__timeFilter(ts)"
snapshot = f"{region} AND ts = CAST(${{snapshot}} AS TIMESTAMP)"
near = "st_distance_sphere_m(wkt_point_from_latlng(latitude,longitude), wkt_point_from_latlng(${center_lat},${center_lon})) <= ${radius} * 1000"
for i, (title, query, unit, color) in enumerate(
    [
        (
            "Stored observations",
            f"SELECT sum(n) AS observations FROM (SELECT count(*) AS n FROM pardig WHERE {window} UNION ALL SELECT count(*) AS n FROM satweave WHERE {window})",
            "short",
            "cyan",
        ),
        (
            "Peak precipitation rate",
            f"SELECT max(rain_mm_h) AS peak FROM pardig WHERE {window}",
            "suffix:mm/h",
            "blue",
        ),
        (
            "Coldest infrared pixel",
            f"SELECT min(brightness_k) AS coldest FROM satweave WHERE {window}",
            "kelvin",
            "purple",
        ),
        (
            "Rainy cells · snapshot",
            f"SELECT 100.0 * sum(CASE WHEN rain_mm_h >= 1 THEN 1 ELSE 0 END) / nullif(count(rain_mm_h),0) AS rainy FROM pardig WHERE {snapshot}",
            "percent",
            "green",
        ),
    ]
):
    p = panel(title, "stat", i * 6, 3, 6, 4, query, unit)
    p["fieldConfig"]["defaults"]["color"] = {"mode": "fixed", "fixedColor": color}
    p["options"] = {
        "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
        "colorMode": "value",
        "graphMode": "none",
        "textMode": "auto",
    }

for index, (title, table, field, agg, unit, scheme, limits) in enumerate(
    [
        (
            "PRECIPITATION  /  0.5° cell maxima",
            "pardig",
            "rain_mm_h",
            "max",
            "suffix:mm/h",
            "continuous-BlYlRd",
            (0, 25),
        ),
        (
            "INFRARED  /  0.5° cell means",
            "satweave",
            "brightness_k",
            "avg",
            "kelvin",
            "continuous-BlPu",
            (200, 310),
        ),
    ]
):
    q = f"SELECT floor(latitude * 2) / 2 + 0.25 AS latitude, floor(longitude * 2) / 2 + 0.25 AS longitude, {agg}({field}) AS {field} FROM {table} WHERE {snapshot} GROUP BY floor(latitude * 2), floor(longitude * 2)"
    p = panel(
        title,
        "geomap",
        index * 12,
        7,
        12,
        13,
        q,
        unit,
        "Display-only spatial aggregation. Original 0.1° data remains in GreptimeDB. Hover for values. Brightness temperature is not surface air temperature.",
    )
    p["fieldConfig"]["defaults"].update(
        {"min": limits[0], "max": limits[1], "color": {"mode": scheme}}
    )
    p["options"] = {
        "basemap": {
            "name": "OpenStreetMap",
            "type": "osm-standard",
            "config": {},
            "opacity": 0.7,
        },
        "controls": {
            "showZoom": True,
            "mouseWheelZoom": True,
            "showAttribution": True,
            "showScale": True,
        },
        "view": {
            "id": "fit",
            "allLayers": True,
            "padding": 15,
            "lat": 30,
            "lon": 120,
            "zoom": 12,
        },
        "tooltip": {"mode": "details"},
        "layers": [
            {
                "name": title,
                "type": "markers",
                "location": {
                    "mode": "coords",
                    "latitude": "latitude",
                    "longitude": "longitude",
                },
                "tooltip": True,
                "config": {
                    "showLegend": True,
                    "style": {
                        "color": {"field": field, "fixed": "blue"},
                        "opacity": 0.7,
                        "size": (
                            {"field": field, "fixed": 4, "min": 0, "max": 12}
                            if table == "pardig"
                            else {"fixed": 4, "min": 3, "max": 10}
                        ),
                        "symbol": {
                            "mode": "fixed",
                            "fixed": "img/icons/marker/square.svg",
                        },
                    },
                },
            }
        ],
    }

for title, x, y, query, unit, desc in [
    (
        "Rainfall envelope · every 15 minutes",
        0,
        20,
        f"SELECT ts AS time, avg(rain_mm_h) AS mean_rate, max(rain_mm_h) AS peak_rate FROM pardig WHERE {window} GROUP BY ts ORDER BY ts",
        "suffix:mm/h",
        "Instantaneous rates, not accumulated rainfall. Mean is unweighted across grid points.",
    ),
    (
        "Cloud temperature envelope · hourly",
        12,
        20,
        f"SELECT ts AS time, min(brightness_k) AS coldest, avg(brightness_k) AS mean_brightness FROM satweave WHERE {window} GROUP BY ts ORDER BY ts",
        "kelvin",
        "Measured top-of-atmosphere brightness temperature; not surface air temperature.",
    ),
    (
        "Rainfall within ${radius} km of the selected center",
        0,
        28,
        f"SELECT ts AS time, avg(rain_mm_h) AS local_mean, max(rain_mm_h) AS local_peak FROM pardig WHERE {window} AND {near} GROUP BY ts ORDER BY ts",
        "suffix:mm/h",
        "Uses st_distance_sphere_m on WKT points. East Asia center: Shanghai; Bay Area: San Francisco; city selections: that city. Only imported cells contribute.",
    ),
]:
    p = panel(title, "timeseries", x, y, 12, 8, query, unit, desc)
    p["fieldConfig"]["defaults"]["custom"] = {
        "drawStyle": "line",
        "lineInterpolation": "linear",
        "lineWidth": 2,
        "fillOpacity": 15,
        "showPoints": "never",
        "spanNulls": False,
    }
    p["options"] = {
        "legend": {
            "displayMode": "table",
            "placement": "bottom",
            "calcs": ["lastNotNull", "max"],
        },
        "tooltip": {"mode": "multi", "sort": "desc"},
    }

q = """SELECT p.latitude, p.longitude, p.rain_mm_h, s.brightness_k,
round(st_distance_sphere_m(wkt_point_from_latlng(p.latitude,p.longitude),wkt_point_from_latlng(${center_lat},${center_lon}))/1000,1) AS distance_km
FROM pardig p JOIN satweave s ON p.region_id=s.region_id AND p.grid_id=s.grid_id AND p.ts=s.ts
WHERE p.region_id=${region:sqlstring} AND s.region_id=${region:sqlstring}
AND p.ts=CAST(${snapshot} AS TIMESTAMP) AND s.ts=CAST(${snapshot} AS TIMESTAMP)
ORDER BY p.rain_mm_h DESC, p.grid_id LIMIT 15"""
p = panel(
    "Rain hotspots × satellite observations",
    "table",
    12,
    28,
    12,
    8,
    q,
    description="Exact timestamp + original grid-cell join. No interpolation. Spatial association does not establish causation.",
)
p["options"] = {"showHeader": True, "cellHeight": "sm", "footer": {"show": False}}
p["fieldConfig"]["overrides"] = [
    {
        "matcher": {"id": "byName", "options": "rain_mm_h"},
        "properties": [
            {"id": "unit", "value": "suffix:mm/h"},
            {"id": "custom.cellOptions", "value": {"type": "color-background"}},
            {"id": "color", "value": {"mode": "continuous-BlYlRd"}},
        ],
    },
    {
        "matcher": {"id": "byName", "options": "brightness_k"},
        "properties": [{"id": "unit", "value": "kelvin"}],
    },
]
p = panel("Sources, transformations & license", "text", 0, 36, 24, 4)
p["options"] = {
    "mode": "markdown",
    "content": "**Data:** [PARDIG](https://developers.google.cn/weathernext/guides/pardig) and [SatWeave](https://developers.google.cn/weathernext/guides/satweave), Google DeepMind / Google Research. [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). PARDIG: [Shalev et al., 2026](https://arxiv.org/abs/2611.13941). Upstream providers include ECMWF, NASA, JAXA, NOAA, EUMETSAT and JMA; full notices are in the demo ATTRIBUTION.txt and pardig-attributions.txt.\n\n**Changes:** regional/time subsetting, m/h → mm/h, longitude normalization, SQL aggregation and visualization. Missing observations remain NULL. **Experimental data, not official weather guidance.** No endorsement implied. Map tiles: © OpenStreetMap contributors.",
}


def variable(name, query, current, hide=0, label=None):
    return {
        "name": name,
        "label": label or name.replace("_", " ").title(),
        "type": "query",
        "datasource": DS,
        "query": query,
        "definition": query,
        "refresh": 2,
        "hide": hide,
        "multi": False,
        "includeAll": False,
        "options": [],
        "current": {"text": str(current), "value": str(current)},
        "sort": 0,
    }


variables = [
    variable(
        "region",
        "SELECT region_name AS __text, region_id AS __value FROM weather_regions ORDER BY region_id",
        "east-asia",
        label="Region",
    ),
    variable(
        "center_lat",
        "SELECT center_lat FROM weather_regions WHERE region_id=${region:sqlstring}",
        31.2304,
        2,
    ),
    variable(
        "center_lon",
        "SELECT center_lon FROM weather_regions WHERE region_id=${region:sqlstring}",
        121.4737,
        2,
    ),
    variable(
        "snapshot",
        f"SELECT DISTINCT CAST(ts AS STRING) AS __text, CAST(ts AS BIGINT) AS __value FROM satweave WHERE {window} ORDER BY __value",
        1788220800000,
        label="Snapshot · UTC",
    ),
    {
        "name": "radius",
        "label": "Radius · km",
        "type": "custom",
        "query": "50,100,200,500",
        "current": {"text": "200", "value": "200"},
        "options": [
            {"text": str(v), "value": str(v), "selected": v == 200}
            for v in [50, 100, 200, 500]
        ],
    },
]
dashboard = {
    "uid": "weather-observatory",
    "title": "Weather Observatory · PARDIG × SatWeave",
    "tags": ["GreptimeDB", "weather", "geospatial"],
    "schemaVersion": 41,
    "version": 1,
    "editable": True,
    "style": "dark",
    "timezone": "utc",
    "time": {"from": "2026-09-01T00:00:00.000Z", "to": "2026-09-01T23:59:59.999Z"},
    "refresh": "",
    "templating": {"list": variables},
    "panels": panels,
    "links": [],
}
(ROOT / "queries.json").write_text(json.dumps(queries, indent=2) + "\n")

# Separate dashboards keep translations out of SQL and preserve variable names.

links = [
    {
        "title": "English",
        "type": "link",
        "url": "/d/weather-observatory",
        "includeVars": True,
        "keepTime": True,
    },
    {
        "title": "简体中文",
        "type": "link",
        "url": "/d/weather-observatory-zh",
        "includeVars": True,
        "keepTime": True,
    },
]
dashboard["links"] = links
translated = copy.deepcopy(dashboard)
translated.update(uid="weather-observatory-zh", title="气象观测台 · PARDIG × SatWeave")
titles = [
    "气象观测台 / GreptimeDB",
    "已存储观测数",
    "峰值降水率",
    "最低红外亮温",
    "降雨网格占比 · 快照",
    "降水分布 / 0.5° 网格最大值",
    "红外亮温 / 0.5° 网格平均值",
    "区域降水率 · 每 15 分钟",
    "区域亮温 · 每小时",
    "中心点 ${radius} km 内的降水率",
    "降水热点 × 卫星观测",
    "数据来源、加工与许可",
]
for item, title in zip(translated["panels"], titles):
    item["title"] = title
kind_descriptions = {
    "geomap": "仅对地图显示做空间聚合，数据库保留 0.1° 原始网格。悬停查看数值。红外亮温不是地面气温。",
    "table": "按相同 UTC 时间、区域和原始网格精确关联，不插值。空间关联不表示因果关系。",
}
for item in translated["panels"]:
    if item["type"] in kind_descriptions:
        item["description"] = kind_descriptions[item["type"]]
translated["panels"][0]["options"]["content"] = (
    "### 用 SQL 查看一天的降水与云层\n**PARDIG + SatWeave** · 0.1° 原始网格 · GreptimeDB **v1.3.0** · InfluxDB 写入 → PostgreSQL 查询 → Grafana\n\n选择**区域**、历史**时间范围**与**快照**。地图显示快照，曲线显示所选时段；**半径**只作用于中心点周边降水图。时间均为 UTC。"
)
translated["panels"][7]["description"] = (
    "瞬时降水率，不是累计降水量。平均值为网格点算术平均，未做面积加权。"
)
translated["panels"][8]["description"] = "卫星观测的大气顶亮温，不是地面气温。"
translated["panels"][9]["description"] = (
    "使用 WKT 点和 st_distance_sphere_m 计算球面距离。东亚中心为上海，湾区中心为旧金山；城市参数使用该城市中心。只统计已导入网格。"
)
translated["panels"][-1]["options"]["content"] = (
    "**数据：**[PARDIG](https://developers.google.cn/weathernext/guides/pardig) 与 [SatWeave](https://developers.google.cn/weathernext/guides/satweave)，Google DeepMind / Google Research。[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。PARDIG：[Shalev 等，2026](https://arxiv.org/abs/2611.13941)。上游来源包括 ECMWF、NASA、JAXA、NOAA、EUMETSAT 和 JMA；完整署名见 ATTRIBUTION.txt 与 pardig-attributions.txt。\n\n**加工：**区域与时间裁剪、m/h 转 mm/h、经度归一化、SQL 聚合及可视化。缺失值保留为 NULL。**实验数据，不属于官方气象预报或预警。**不代表数据提供方背书。地图底图：© OpenStreetMap contributors。"
)
labels = {"region": "区域", "snapshot": "快照 · UTC", "radius": "半径 · km"}
for v in translated["templating"]["list"]:
    if v["name"] in labels:
        v["label"] = labels[v["name"]]
    if v["name"] == "region":
        v["query"] = v["query"].replace(
            "region_name AS __text",
            "CASE region_id WHEN 'east-asia' THEN '东亚' WHEN 'bay-area' THEN '旧金山湾区' ELSE region_name END AS __text",
        )
        v["definition"] = v["query"]
field_labels = {
    "observations": "观测数",
    "peak": "峰值",
    "coldest": "最低亮温",
    "rainy": "降雨占比",
    "mean_rate": "平均降水率",
    "peak_rate": "峰值降水率",
    "mean_brightness": "平均亮温",
    "local_mean": "半径内平均值",
    "local_peak": "半径内峰值",
    "latitude": "纬度",
    "longitude": "经度",
    "rain_mm_h": "降水率",
    "brightness_k": "红外亮温",
    "distance_km": "距离（km）",
}
for item in translated["panels"]:
    for key, value in field_labels.items():
        item["fieldConfig"]["overrides"].append(
            {
                "matcher": {"id": "byName", "options": key},
                "properties": [{"id": "displayName", "value": value}],
            }
        )

for board in [dashboard, translated]:
    board["panels"][0]["gridPos"]["h"] = 5
    for item in board["panels"][1:]:
        item["gridPos"]["y"] += 2
    for item in board["panels"]:
        if item["type"] == "geomap" and board is translated:
            item["options"]["layers"][0]["name"] = item["title"]
for filename, board in [("weather.json", dashboard), ("weather-zh.json", translated)]:
    (ROOT / "grafana/dashboards" / filename).write_text(
        json.dumps(board, ensure_ascii=False, indent=2) + "\n"
    )
