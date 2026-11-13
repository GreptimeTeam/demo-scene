"""Named regions and deterministic city bounding boxes (WGS84 degrees)."""

import math

REGIONS = {
    "east-asia": {
        "name": "East Asia",
        "bbox": [100, 20, 150, 50],
        "center": [31.2304, 121.4737],
    },
    "bay-area": {
        "name": "San Francisco Bay Area",
        "bbox": [-124, 36, -120, 40],
        "center": [37.7749, -122.4194],
    },
}
CITIES = {
    "shanghai": (31.2304, 121.4737, "上海"),
    "san-francisco": (37.7749, -122.4194, "旧金山"),
    "san-jose": (37.3382, -121.8863, "圣何塞"),
    "beijing": (39.9042, 116.4074, "北京"),
    "shenzhen": (22.5431, 114.0579, "深圳"),
    "hangzhou": (30.2741, 120.1551, "杭州"),
    "hong-kong": (22.3193, 114.1694, "香港"),
    "tokyo": (35.6762, 139.6503, "东京"),
    "seattle": (47.6062, -122.3321, "西雅图"),
    "new-york": (40.7128, -74.0060, "纽约"),
    "london": (51.5074, -0.1278, "伦敦"),
    "singapore": (1.3521, 103.8198, "新加坡"),
}


def validate_bbox(bbox):
    west, south, east, north = bbox
    if not all(math.isfinite(x) for x in bbox):
        raise ValueError("Bounding box coordinates must be finite")
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError(
            "Expected -180 <= west < east <= 180 and -90 <= south < north <= 90"
        )
    return list(bbox)


def city_region(name, radius):
    key = name.strip().lower().replace(" ", "-")
    key = next((k for k, v in CITIES.items() if v[2] == key), key)
    if key not in CITIES:
        raise ValueError(f"Unknown city {name!r}; use --list-regions or --bbox W S E N")
    if not math.isfinite(radius) or not 10 <= radius <= 1000:
        raise ValueError("City radius must be between 10 and 1000 km")
    lat, lon, _ = CITIES[key]
    angle = radius / 6371.0088
    dlat = math.degrees(angle)
    dlon = math.degrees(math.asin(math.sin(angle) / math.cos(math.radians(lat))))
    bbox = validate_bbox([lon - dlon, lat - dlat, lon + dlon, lat + dlat])
    return f"{key}-{radius:.17g}km", {
        "name": f"{key.replace('-', ' ').title()} / {radius:g} km",
        "bbox": bbox,
        "center": [lat, lon],
    }


def select_regions(args):
    selected = {}
    for key in args.region or []:
        selected[key] = REGIONS[key]
    for name in args.city or []:
        key, region = city_region(name, args.radius_km)
        selected[key] = region
    if args.bbox:
        bbox = validate_bbox(args.bbox)
        key = "bbox-" + "-".join(f"{v:.17g}" for v in bbox)
        selected[key] = {
            "name": "Custom bounding box",
            "bbox": bbox,
            "center": [(bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2],
        }
    return selected or REGIONS.copy()
