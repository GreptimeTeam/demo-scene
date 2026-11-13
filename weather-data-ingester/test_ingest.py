"""Regression checks for geographic normalization, missing values, and cadence."""

import datetime as dt
import unittest

import numpy as np
import xarray as xr

from ingest import crop, parse_time, timestamps
from regions import city_region, validate_bbox


class ExtractionTests(unittest.TestCase):
    def test_western_longitude_descending_latitude_and_missing_value(self):
        data = xr.DataArray(
            [[1.0, np.nan], [3.0, 4.0]],
            coords={"latitude": [38.0, 37.0], "longitude": [237.0, 238.0]},
            dims=["latitude", "longitude"],
        )
        spec = {"bay": {"bbox": [-123, 37, -122, 38]}}
        result = crop(data, spec, "brightness_k").sort_values(["latitude", "longitude"])
        self.assertEqual(result.longitude.tolist(), [-123.0, -122.0, -123.0, -122.0])
        self.assertEqual(result.brightness_k.iloc[:3].tolist(), [3.0, 4.0, 1.0])
        self.assertTrue(np.isnan(result.brightness_k.iloc[3]))
        self.assertEqual(result.grid_id.nunique(), 4)

    def test_zero_meridian_selection_and_rain_units(self):
        data = xr.DataArray(
            [[0.001, 0.002, 0.003]],
            coords={"latitude": [51.5], "longitude": [0.0, 1.0, 359.0]},
            dims=["latitude", "longitude"],
        )
        result = crop(data, {"london": {"bbox": [-1.1, 51, 0.1, 52]}}, "rain_mm_h")
        self.assertEqual(result.longitude.tolist(), [0.0, -1.0])
        self.assertEqual(result.rain_mm_h.tolist(), [1.0, 3.0])

    def test_hourly_frames_preserve_half_open_interval(self):
        start = parse_time("2026-09-01T00:15:00Z")
        end = parse_time("2026-09-01T02:00:00Z")
        self.assertEqual(
            list(timestamps(start, end, 60)),
            [dt.datetime(2026, 9, 1, 1, tzinfo=dt.timezone.utc)],
        )
        self.assertEqual(len(list(timestamps(start, end, 15))), 7)

    def test_city_alias_and_reject_invalid_bbox(self):
        self.assertEqual(city_region("上海", 200), city_region("Shanghai", 200))
        with self.assertRaises(ValueError):
            city_region("unlisted", 200)
        with self.assertRaises(ValueError):
            validate_bbox([170, -10, -170, 10])
        with self.assertRaises(ValueError):
            validate_bbox([0, 0, float("nan"), 1])


if __name__ == "__main__":
    unittest.main()
