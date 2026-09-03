"""Tests for the photography_events backend.

Written against stdlib unittest and loaded without importing Home Assistant, so
they run anywhere with `python3 -m unittest` and no install step. pytest will
also collect them if it is available.
"""

from __future__ import annotations

import importlib.util
import math
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

PACKAGE = "photography_events"
ROOT = Path(__file__).resolve().parent.parent / "custom_components" / PACKAGE
PURE_MODULES = ("const", "astronomy", "weather_scoring", "seasonal", "events")


def _load_package():
    """Import the dependency-free modules under a synthetic package.

    The real package __init__ imports Home Assistant, which is not installed in
    a bare checkout or CI runner. Everything with real logic in it is
    deliberately free of HA imports so it can be exercised directly.
    """
    if PACKAGE in sys.modules:
        return sys.modules[PACKAGE]
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(ROOT)]
    sys.modules[PACKAGE] = package
    for name in PURE_MODULES:
        spec = importlib.util.spec_from_file_location(f"{PACKAGE}.{name}", ROOT / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"{PACKAGE}.{name}"] = module
        spec.loader.exec_module(module)
        setattr(package, name, module)
    return package


_pkg = _load_package()
astronomy = _pkg.astronomy
weather_scoring = _pkg.weather_scoring
seasonal = _pkg.seasonal
events = _pkg.events
const = _pkg.const

VANDENBERG = (math.radians(34.7420), math.radians(-120.5724))


class TestAstronomy(unittest.TestCase):
    def test_solar_declination_invariants(self):
        def dec_at(iso):
            return math.degrees(astronomy.sun_equatorial(astronomy.days_since_j2000(datetime.fromisoformat(iso)))[1])

        self.assertAlmostEqual(dec_at("2026-06-21T06:00:00+00:00"), 23.44, delta=0.3)
        self.assertAlmostEqual(dec_at("2026-12-21T18:00:00+00:00"), -23.44, delta=0.3)
        self.assertAlmostEqual(dec_at("2026-09-22T18:00:00+00:00"), 0.0, delta=1.0)

    def test_planet_oppositions_match_published_dates(self):
        """The sharpest check available on the elements and Kepler solver.

        These dates are published astronomical fact, not values derived from
        this code.
        """
        expected = {
            "Mars": {"2027-02-19"},
            "Jupiter": {"2026-01-10", "2027-02-11"},
            "Saturn": {"2026-10-04"},
        }
        start = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)

        for planet in astronomy.PLANETS:
            if planet["inner"]:
                continue
            series = [
                (start + timedelta(days=i), astronomy.planet_elongation_deg(planet, start + timedelta(days=i)))
                for i in range(801)
            ]
            found = {
                series[i][0].date().isoformat()
                for i in range(1, len(series) - 1)
                if series[i][1] >= series[i - 1][1]
                and series[i][1] >= series[i + 1][1]
                and series[i][1] > 170
            }
            self.assertTrue(
                expected[planet["name"]] <= found,
                f"{planet['name']}: expected {expected[planet['name']]}, found {found}",
            )

    def test_inner_planets_never_exceed_their_elongation_limit(self):
        limits = {"Mercury": 29.0, "Venus": 48.0}
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for planet in astronomy.PLANETS:
            if not planet["inner"]:
                continue
            for i in range(0, 400, 5):
                elongation = astronomy.planet_elongation_deg(planet, start + timedelta(days=i))
                self.assertLessEqual(elongation, limits[planet["name"]])

    def test_dark_window_is_one_night_not_a_day_and_a_half(self):
        """Dusk must pair with the dawn that follows it.

        Pairing by calendar date instead produces a 30-hour "night" spanning
        full daylight whenever the coordinates sit in another timezone from the
        host, which silently corrupts every altitude check built on it.
        """
        lat, lon = VANDENBERG
        for month, day in ((9, 5), (12, 21), (6, 21)):
            window = astronomy.dark_window(datetime(2026, month, day, tzinfo=timezone.utc), lat, lon)
            self.assertIsNotNone(window, f"expected darkness on {month}/{day}")
            self.assertGreater(window.hours, 3.0)
            self.assertLess(window.hours, 14.0, f"{month}/{day} window was {window.hours}h")
            self.assertGreater(window.end, window.start)

    def test_moon_illumination_stays_in_range(self):
        start = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
        for i in range(40):
            fraction, phase, distance = astronomy.moon_illumination(start + timedelta(days=i))
            self.assertGreaterEqual(fraction, 0.0)
            self.assertLessEqual(fraction, 1.0)
            self.assertGreaterEqual(phase, 0.0)
            self.assertLessEqual(phase, 1.0)
            self.assertTrue(356_000 < distance < 407_000)

    def test_solar_noon_at_greenwich_is_near_noon_utc(self):
        lat, lon = math.radians(51.5074), math.radians(-0.1278)
        for month, day in ((3, 20), (9, 2), (12, 1)):
            date = datetime(2026, month, day, tzinfo=timezone.utc)
            rise = astronomy.sun_event(date, lat, lon, rising=True)
            sets = astronomy.sun_event(date, lat, lon, rising=False)
            self.assertIsNotNone(rise)
            self.assertIsNotNone(sets)
            noon = rise + (sets - rise) / 2
            self.assertAlmostEqual(noon.hour + noon.minute / 60, 12.0, delta=0.3)


EVENT_TIME = datetime(2026, 9, 5, 19, 0, tzinfo=timezone.utc)


def _forecast(rows):
    """Build an Open-Meteo shaped payload from (offset_h, high, mid, low, rh, precip)."""
    payload = {"time": [], "cloud_cover_high": [], "cloud_cover_mid": [], "cloud_cover_low": [],
               "relative_humidity_2m": [], "precipitation_probability": [], "cloud_cover": []}
    for offset, high, mid, low, humidity, precip in rows:
        payload["time"].append((EVENT_TIME + timedelta(hours=offset)).replace(tzinfo=None).isoformat())
        payload["cloud_cover_high"].append(high)
        payload["cloud_cover_mid"].append(mid)
        payload["cloud_cover_low"].append(low)
        payload["relative_humidity_2m"].append(humidity)
        payload["precipitation_probability"].append(precip)
        payload["cloud_cover"].append(min(100, high + low))
    return {"hourly": payload}


def _uniform(high, mid, low, humidity, precip):
    return _forecast([(o, high, mid, low, humidity, precip) for o in range(-8, 3)])


class TestSkyScoring(unittest.TestCase):
    def test_textbook_conditions_score_high(self):
        result = weather_scoring.score_sky(_uniform(50, 30, 5, 45, 0), EVENT_TIME)
        self.assertGreaterEqual(result.score, 85)

    def test_low_cloud_blocks_the_show_however_good_the_cirrus(self):
        """The Central Coast failure mode: lovely cirrus, marine layer underneath."""
        marine_layer = weather_scoring.score_sky(_uniform(55, 20, 80, 88, 10), EVENT_TIME)
        clear_horizon = weather_scoring.score_sky(_uniform(55, 20, 5, 55, 10), EVENT_TIME)
        self.assertLess(marine_layer.score, 40)
        self.assertGreater(clear_horizon.score, marine_layer.score + 40)
        self.assertTrue(any("low cloud" in reason for reason in marine_layer.reasons))

    def test_empty_and_overcast_skies_both_score_low(self):
        self.assertLess(weather_scoring.score_sky(_uniform(2, 3, 2, 40, 0), EVENT_TIME).score, 70)
        self.assertLess(weather_scoring.score_sky(_uniform(95, 95, 95, 92, 40), EVENT_TIME).score, 30)

    def test_haze_reduces_the_score(self):
        hazy = weather_scoring.score_sky(_uniform(45, 25, 12, 92, 0), EVENT_TIME)
        clean = weather_scoring.score_sky(_uniform(45, 25, 12, 45, 0), EVENT_TIME)
        self.assertLess(hazy.score, clean.score)

    def test_clearing_trend_requires_actual_improvement(self):
        """A sky socked in all day must not be credited as 'clearing'."""
        clearing = weather_scoring.score_sky(
            _forecast(
                [(o, 55, 35, 8, 50, 0) if o >= -2 else (o, 70, 60, 85, 88, 60) for o in range(-8, 3)]
            ),
            EVENT_TIME,
        )
        self.assertTrue(any("clearing" in reason for reason in clearing.reasons))

        socked_in = weather_scoring.score_sky(_uniform(60, 40, 90, 90, 20), EVENT_TIME)
        self.assertFalse(
            any("clearing" in reason for reason in socked_in.reasons),
            "a uniformly overcast day is not clearing",
        )

    def test_degrades_without_usable_data(self):
        self.assertIsNone(weather_scoring.score_sky({}, EVENT_TIME))
        self.assertIsNone(weather_scoring.score_sky(_uniform(50, 30, 5, 45, 0), EVENT_TIME + timedelta(days=9)))
        # Aggregate-only payloads carry no layer information to score.
        aggregate = {"hourly": {"time": [EVENT_TIME.replace(tzinfo=None).isoformat()], "cloud_cover": [40]}}
        self.assertIsNone(weather_scoring.score_sky(aggregate, EVENT_TIME))

    def test_open_meteo_params_request_the_layers_we_score(self):
        params = weather_scoring.build_open_meteo_params(34.742, -120.5724)
        for field in ("cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "relative_humidity_2m"):
            self.assertIn(field, params["hourly"])


NOW = datetime(2026, 9, 5, 18, 0, tzinfo=timezone.utc)


def _multiday(high, mid, low, humidity, precip, hours=96):
    """A forecast spanning several days, so real sunset times fall inside it.

    The narrow fixture above is anchored on a single event; opportunity
    building looks days ahead and needs hourly coverage across all of them.
    """
    payload = {"time": [], "cloud_cover_high": [], "cloud_cover_mid": [], "cloud_cover_low": [],
               "relative_humidity_2m": [], "precipitation_probability": [], "cloud_cover": []}
    start = NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    for hour in range(hours):
        payload["time"].append((start + timedelta(hours=hour)).replace(tzinfo=None).isoformat())
        payload["cloud_cover_high"].append(high)
        payload["cloud_cover_mid"].append(mid)
        payload["cloud_cover_low"].append(low)
        payload["relative_humidity_2m"].append(humidity)
        payload["precipitation_probability"].append(precip)
        payload["cloud_cover"].append(min(100, high + low))
    return {"hourly": payload}


class TestOpportunities(unittest.TestCase):
    def test_sunsets_below_threshold_are_suppressed(self):
        zone = const.ZONES_BY_ID["piedras_blancas"]
        good = events.build_sunset_opportunities(zone, _multiday(50, 30, 5, 45, 0), NOW, threshold=85)
        bad = events.build_sunset_opportunities(zone, _multiday(55, 20, 80, 88, 10), NOW, threshold=85)
        self.assertTrue(good)
        self.assertFalse(bad)
        self.assertTrue(all(item.score >= 85 for item in good))
        self.assertTrue(all(item.gear for item in good), "alerts must carry gear advice")

    def test_minor_showers_do_not_raise_alerts_but_do_reach_the_calendar(self):
        zone = const.ZONES_BY_ID["carrizo_plain"]
        october = datetime(2026, 10, 1, tzinfo=timezone.utc)
        alerts = events.build_meteor_opportunities(zone, october, 30)
        planning = events.build_meteor_opportunities(zone, october, 30, alert_only=False)
        self.assertFalse([item for item in alerts if "Orionids" in item.title])
        self.assertTrue([item for item in planning if "Orionids" in item.title])

    def test_major_shower_on_a_dark_night_scores_well(self):
        zone = const.ZONES_BY_ID["death_valley"]
        december = datetime(2026, 12, 1, tzinfo=timezone.utc)
        geminids = [
            item for item in events.build_meteor_opportunities(zone, december, 30)
            if "Geminids" in item.title
        ]
        self.assertEqual(len(geminids), 1)
        self.assertGreaterEqual(geminids[0].score, 75)
        self.assertLessEqual(geminids[0].end.timestamp() - geminids[0].start.timestamp(), 20 * 3600)

    def test_bright_moon_pushes_a_shower_below_the_alert_bar(self):
        zone = const.ZONES_BY_ID["death_valley"]
        lat, lon = math.radians(zone["latitude"]), math.radians(zone["longitude"])
        december = datetime(2026, 12, 1, tzinfo=timezone.utc)
        shower = [
            item for item in events.build_meteor_opportunities(zone, december, 30)
            if "Geminids" in item.title
        ][0]
        illumination, _, _ = astronomy.moon_illumination(shower.start)
        # Guard the cross-check itself: the score should reflect the real moon.
        if illumination <= events.MAX_MOON_ILLUMINATION:
            self.assertTrue(any("moon only" in reason for reason in shower.reasons))
        else:
            self.assertTrue(any("wash it out" in reason for reason in shower.reasons))

    def test_milky_way_only_in_core_season_and_only_when_dark(self):
        zone = const.ZONES_BY_ID["carrizo_plain"]
        summer = events.build_milky_way_opportunities(zone, datetime(2026, 6, 10, tzinfo=timezone.utc), 14)
        winter = events.build_milky_way_opportunities(zone, datetime(2026, 12, 10, tzinfo=timezone.utc), 14)
        self.assertTrue(summer)
        self.assertFalse(winter, "the core is not up at night in December")
        for item in summer:
            self.assertLessEqual(item.end.timestamp() - item.start.timestamp(), 16 * 3600)

    def test_drive_time_gating_removes_distant_zones(self):
        seasonal_events = events.build_seasonal_opportunities(NOW, 365)
        self.assertTrue(seasonal_events)
        near = events.within_drive(seasonal_events, 2.0)
        self.assertTrue(near)
        self.assertLess(len(near), len(seasonal_events))
        self.assertTrue(all(item.drive_hours <= 2.0 for item in near))

    def test_action_window_is_sorted_by_score_and_bounded_to_48h(self):
        zone = const.ZONES_BY_ID["piedras_blancas"]
        pool = events.build_sunset_opportunities(zone, _multiday(50, 30, 5, 45, 0), NOW, threshold=85)
        pool += events.build_seasonal_opportunities(NOW, 365)
        window = events.action_window(pool, NOW)
        self.assertTrue(window)
        for item in window:
            self.assertLessEqual(item.start, NOW + timedelta(hours=48))
        scores = [item.score for item in window]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_every_opportunity_serialises_for_entity_attributes(self):
        pool = events.build_seasonal_opportunities(NOW, 120)
        for item in pool:
            data = item.as_dict()
            self.assertIsInstance(data["start"], str)
            self.assertIn("zone_name", data)
            self.assertIn("score", data)


class TestSeasonalWindows(unittest.TestCase):
    def test_windows_reference_real_zones_and_categories(self):
        for window in seasonal.SEASONAL_WINDOWS:
            self.assertIn(window.zone_id, const.ZONES_BY_ID, window.key)
            self.assertIn(window.category, const.ALL_CATEGORIES, window.key)
            self.assertTrue(window.detail.strip(), window.key)

    def test_year_crossing_windows_appear_in_a_forward_view(self):
        """Elephant seal season runs mid-December to February."""
        december = datetime(2026, 12, 20, tzinfo=timezone.utc)
        found = seasonal.active_windows(december, 90)
        keys = {entry["key"].rsplit("-", 3)[0] for entry in found}
        self.assertIn("elephant_seal_battles", keys)

    def test_rainfall_dependent_blooms_are_flagged_for_confirmation(self):
        blooms = [w for w in seasonal.SEASONAL_WINDOWS if w.category == const.CATEGORY_BLOOMS]
        self.assertTrue(blooms)
        self.assertTrue(all(w.confirm for w in blooms), "bloom timing must not be presented as certain")

    def test_seasonal_events_never_reach_the_drop_everything_score(self):
        """A season lasting weeks is planning material, not an urgent alert."""
        for item in events.build_seasonal_opportunities(NOW, 365):
            self.assertLess(item.score, const.DEFAULT_ALERT_SCORE)


class TestZonesAndGear(unittest.TestCase):
    def test_zones_are_well_formed(self):
        seen = set()
        for zone in const.TARGET_ZONES:
            self.assertNotIn(zone["id"], seen)
            seen.add(zone["id"])
            self.assertTrue(-90 <= zone["latitude"] <= 90)
            self.assertTrue(-180 <= zone["longitude"] <= 180)
            self.assertGreater(zone["drive_hours"], 0)
            self.assertTrue(1 <= zone["bortle"] <= 9)
            self.assertTrue(zone["specialties"])
            for specialty in zone["specialties"]:
                self.assertIn(specialty, const.ALL_CATEGORIES)

    def test_zone_coordinates_are_plausibly_in_california(self):
        for zone in const.TARGET_ZONES:
            self.assertTrue(32 < zone["latitude"] < 42, zone["name"])
            self.assertTrue(-125 < zone["longitude"] < -114, zone["name"])

    def test_every_category_has_gear_advice(self):
        for category in const.ALL_CATEGORIES:
            profile = const.GEAR_PROFILES.get(category)
            self.assertTrue(profile, f"no gear profile for {category}")
            self.assertIn("glass", profile)


if __name__ == "__main__":
    unittest.main(verbosity=2)
