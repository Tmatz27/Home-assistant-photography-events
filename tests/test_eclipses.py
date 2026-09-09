"""Sourced catalog/time-basis and local visibility regressions."""
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import unittest

from test_integration import _load_package

_load_package()
from photography_events import eclipses, astronomy, events, const

CATALOG = json.loads((Path(__file__).resolve().parents[1] / "custom_components/photography_events/eclipse_catalog.json").read_text())


class EclipseTests(unittest.TestCase):
    def test_catalog_extends_through_2035_and_preserves_time_basis(self):
        self.assertEqual(len(CATALOG["events"]), 45)
        self.assertEqual(CATALOG["coverage"], [2026, 2035])
        for row in CATALOG["events"]:
            td = datetime.fromisoformat(row["td"])
            ut = datetime.fromisoformat(row["date"])
            self.assertEqual((td-ut).total_seconds(), row["delta_t_seconds"])
            if row["kind"] == "solar" and row["type"] in {"annular", "total", "hybrid"}:
                self.assertGreaterEqual(len(row["path"]), 20)
                self.assertTrue(row["path_url"].startswith("https://eclipse.gsfc.nasa.gov/"))

    def test_nasa_2027_greatest_td_is_not_mislabeled_as_utc(self):
        row = next(r for r in CATALOG["events"] if r["date"].startswith("2027-02-06"))
        self.assertEqual(row["td"], "2027-02-06T16:00:48Z")
        self.assertEqual(row["date"], "2027-02-06T15:59:32Z")

    def test_path_distance_wraps_across_dateline(self):
        self.assertLess(eclipses.segment_distance((0,180), (0,179), (0,-179)), 0.001)
        self.assertGreater(eclipses.segment_distance((0,0), (0,179), (0,-179)), 19000)

    def test_california_cannot_see_2027_central_solar_paths(self):
        for row in CATALOG["events"]:
            if row["kind"] == "solar" and row["date"].startswith("2027"):
                self.assertLess(eclipses.central_path_margin(row, const.DEFAULT_HOME), -1000)

    def test_published_centerline_point_is_inside_its_path(self):
        row = next(r for r in CATALOG["events"] if r["date"].startswith("2027-08-02"))
        middle = row["path"][len(row["path"])//2]
        self.assertGreater(eclipses.central_path_margin(row, middle[1:3]), 50)

    def test_lunar_window_uses_real_umbral_phase_and_actual_altitude(self):
        row = next(r for r in CATALOG["events"] if r["kind"] == "lunar" and r["date"].startswith("2026-03-03"))
        window = eclipses.lunar_window(row, const.DEFAULT_HOME)
        self.assertIsNotNone(window)
        start, end, preferred, total = window
        self.assertTrue(total)
        peak = datetime.fromisoformat(row["date"])
        self.assertLessEqual((end-start).total_seconds()/60, row["partial_minutes"])
        self.assertLess(abs((preferred-peak).total_seconds()), 61)
        for moment in (start, end):
            self.assertGreaterEqual(math.degrees(astronomy.moon_altitude(moment, *map(math.radians, const.DEFAULT_HOME))), 5)

    def test_no_solar_rows_from_foreign_paths_or_penumbral_only_eclipses(self):
        rows = eclipses.opportunities(CATALOG, datetime(2027,1,1,tzinfo=timezone.utc), const.TARGET_ZONES, const.DEFAULT_HOME, 6)
        self.assertFalse(any("solar" in row.title.lower() for row in rows))
        self.assertFalse(any("penumbral" in row.title.lower() for row in rows))


class MeteorDriftTests(unittest.TestCase):
    def test_2030_lyrid_marginal_night_changes_with_published_drift(self):
        shower = next(s for s in events.METEOR_SHOWERS if s["name"] == "Lyrids")
        zone = next(z for z in const.TARGET_ZONES if z["id"] == "antelope_valley")
        peak = astronomy.solar_longitude_crossing(2030, shower["lambda_sun"], tz=timezone.utc)
        night = (peak - timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
        coords = events._zone_coords(zone)
        kwargs = dict(ra_deg=shower["ra_deg"], dec_deg=shower["dec_deg"],
                      min_target_altitude=30, max_moon_illumination=0.4)
        fixed = astronomy.astro_shooting_window(night, *coords, **kwargs)
        moving = astronomy.astro_shooting_window(night, *coords, **kwargs,
            radiant_epoch=peak, radiant_drift=events.RADIANT_DRIFT["Lyrids"])
        self.assertNotEqual(fixed is None, moving is None)

    def test_drift_covers_exactly_the_runtime_showers(self):
        self.assertEqual(set(events.RADIANT_DRIFT), {s["name"] for s in events.METEOR_SHOWERS})

    def test_drift_is_applied_to_each_candidate_night(self):
        from unittest.mock import patch
        shower = next(s for s in events.METEOR_SHOWERS if s["name"] == "Geminids")
        peak = astronomy.solar_longitude_crossing(2031, shower["lambda_sun"], tz=timezone.utc)
        with patch.object(astronomy, "astro_shooting_window", return_value=None) as solve:
            events._best_meteor_night(peak, 0.6, -2.1, shower)
        self.assertEqual(solve.call_count, 2)
        for call in solve.call_args_list:
            self.assertEqual(call.kwargs["radiant_drift"], (1,0))
            self.assertEqual(call.kwargs["radiant_epoch"], peak)

    def test_zero_drift_preserves_existing_window_geometry(self):
        night = datetime(2026,9,7,tzinfo=timezone.utc)
        coords = tuple(map(math.radians, const.DEFAULT_HOME))
        fixed = astronomy.astro_shooting_window(night, *coords)
        stationary = astronomy.astro_shooting_window(night, *coords, radiant_epoch=night)
        self.assertEqual(fixed.start, stationary.start)
        self.assertEqual(fixed.end, stationary.end)
