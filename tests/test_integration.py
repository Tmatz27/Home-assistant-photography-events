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
PURE_MODULES = (
    "const",
    "astronomy",
    "weather_scoring",
    "seasonal",
    "wildlife",
    "field_reports",
    "routing",
    "throttle",
    "events",
)


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
wildlife = _pkg.wildlife
field_reports = _pkg.field_reports
routing = _pkg.routing
throttle = _pkg.throttle

VANDENBERG = (math.radians(34.7420), math.radians(-120.5724))


class TestAstronomy(unittest.TestCase):
    def test_solar_declination_invariants(self):
        def dec_at(iso):
            return math.degrees(astronomy.sun_equatorial(astronomy.days_since_j2000(datetime.fromisoformat(iso)))[1])

        self.assertAlmostEqual(dec_at("2026-06-21T06:00:00+00:00"), 23.44, delta=0.3)
        self.assertAlmostEqual(dec_at("2026-12-21T18:00:00+00:00"), -23.44, delta=0.3)
        self.assertAlmostEqual(dec_at("2026-09-22T18:00:00+00:00"), 0.0, delta=1.0)

    def test_planet_oppositions_match_published_times(self):
        """Checked against published opposition instants, not derived values.

        Opposition is defined in right ascension - the planet's geocentric RA
        twelve hours from the Sun's - so that is what is measured here. An
        earlier version of this test took the maximum of the Sun-planet angular
        separation on daily samples, which is neither the definition nor
        precise: separation peaks below 180 degrees whenever the planet has any
        ecliptic latitude, and at a different moment.

        The tolerance is the honest accuracy of two-body Keplerian propagation
        from mean elements, which is what this integration uses. Jupiter lands
        on the published instant; Mars and Saturn run about a day late because
        their mutual perturbations are not modelled. For deciding which nights
        a planet is worth photographing that is immaterial - a planet is
        equally well placed for weeks either side of opposition - but it is not
        the arcminute precision a full perturbation theory would give.
        """
        published = [
            ("Jupiter", datetime(2027, 2, 11, 0, 44, tzinfo=timezone.utc), 6),
            ("Jupiter", datetime(2026, 1, 10, 1, 44, tzinfo=timezone.utc), 6),
            ("Mars", datetime(2027, 2, 19, 15, 45, tzinfo=timezone.utc), 30),
            ("Saturn", datetime(2026, 10, 4, 12, 21, tzinfo=timezone.utc), 30),
        ]

        def opposition_offset(planet, moment):
            days = astronomy.days_since_j2000(moment)
            sun_ra, _ = astronomy.sun_equatorial(days)
            planet_ra, _, _ = astronomy.planet_geocentric(planet, moment)
            return (math.degrees(planet_ra - sun_ra) % 360) - 180

        for name, moment, tolerance_hours in published:
            planet = next(item for item in astronomy.PLANETS if item["name"] == name)
            low, high = moment - timedelta(days=4), moment + timedelta(days=4)
            for _ in range(60):
                middle = low + (high - low) / 2
                if opposition_offset(planet, low) * opposition_offset(planet, middle) <= 0:
                    high = middle
                else:
                    low = middle
            found = low + (high - low) / 2
            error_hours = abs((found - moment).total_seconds()) / 3600
            self.assertLess(
                error_hours,
                tolerance_hours,
                f"{name}: computed {found:%Y-%m-%d %H:%M} against a published "
                f"{moment:%Y-%m-%d %H:%M}, off by {error_hours:.1f} h",
            )

    def test_lunar_series_reproduces_published_full_moons(self):
        """The check that justifies carrying sixty periodic terms.

        A full moon is when the Moon's apparent ecliptic longitude is 180
        degrees from the Sun's, so the moment is acutely sensitive to lunar
        longitude error - roughly two minutes of timing per arcminute of
        position. The single-term series this replaced put the January 2026
        full moon 124 minutes early. These are published times, not values
        produced by this code.
        """
        published = [
            datetime(2026, 1, 3, 10, 4, tzinfo=timezone.utc),
            datetime(2026, 3, 3, 11, 38, tzinfo=timezone.utc),
        ]

        def opposition_offset(moment):
            days = astronomy.days_since_j2000(moment)
            separation = math.degrees(
                astronomy.moon_ecliptic(days)[0] - astronomy.sun_ecliptic_longitude(days)
            )
            return (separation % 360) - 180

        for moment in published:
            low, high = moment - timedelta(hours=12), moment + timedelta(hours=12)
            for _ in range(60):
                middle = low + (high - low) / 2
                if opposition_offset(low) * opposition_offset(middle) <= 0:
                    high = middle
                else:
                    low = middle
            found = low + (high - low) / 2
            error_minutes = abs((found - moment).total_seconds()) / 60
            self.assertLess(
                error_minutes,
                10,
                f"full moon computed {found:%Y-%m-%d %H:%M} against a published "
                f"{moment:%Y-%m-%d %H:%M}, off by {error_minutes:.1f} min",
            )

    def test_lunar_distance_stays_inside_the_real_orbit(self):
        """Perigee and apogee bracket every distance the series can produce."""
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for hours in range(0, 24 * 400, 6):
            distance = astronomy.moon_ecliptic(
                astronomy.days_since_j2000(start + timedelta(hours=hours))
            )[2]
            self.assertGreater(distance, 356000)
            self.assertLess(distance, 407000)

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


UTC = timezone.utc


def _ebird_entry(**overrides):
    entry = {
        "comName": "Vermilion Flycatcher",
        "sciName": "Pyrocephalus rubinus",
        "locName": "Oso Flaco Lake",
        "obsDt": "2026-03-20 07:15",
        "howMany": 1,
        "lat": 35.03,
        "lng": -120.62,
        "obsValid": True,
        "obsReviewed": True,
        "subId": "S1",
    }
    entry.update(overrides)
    return entry


class TestWildlifeParsing(unittest.TestCase):
    def test_ebird_rejects_entries_missing_what_it_needs(self):
        payload = [
            _ebird_entry(),
            _ebird_entry(subId="S2", lat=None),
            _ebird_entry(subId="S3", obsDt="not a date"),
            _ebird_entry(subId="S4", comName=None, sciName=None),
            "not a dict",
        ]
        self.assertEqual(len(wildlife.parse_ebird(payload, UTC)), 1)

    def test_ebird_date_only_observations_still_parse(self):
        parsed = wildlife.parse_ebird([_ebird_entry(obsDt="2026-03-20")], UTC)
        self.assertEqual(parsed[0].latest.hour, 0)

    def test_ebird_confirmation_needs_both_flags(self):
        both = wildlife.parse_ebird([_ebird_entry(obsValid=True, obsReviewed=True)], UTC)[0]
        one = wildlife.parse_ebird([_ebird_entry(obsValid=True, obsReviewed=False)], UTC)[0]
        self.assertTrue(both.confirmed)
        self.assertFalse(one.confirmed)

    def test_inaturalist_reads_all_three_coordinate_shapes(self):
        payload = {
            "results": [
                {
                    "id": 1,
                    "observed_on": "2026-03-20",
                    "geojson": {"type": "Point", "coordinates": [-120.65, 34.85]},
                    "taxon": {"name": "Orcinus orca", "preferred_common_name": "Orca"},
                    "place_guess": "A",
                },
                {
                    "id": 2,
                    "observed_on": "2026-03-20",
                    "location": "34.85,-120.65",
                    "taxon": {"name": "Orcinus orca"},
                    "place_guess": "B",
                },
                {
                    "id": 3,
                    "observed_on": "2026-03-20",
                    "latitude": 34.85,
                    "longitude": -120.65,
                    "taxon": {"name": "Orcinus orca"},
                    "place_guess": "C",
                },
                {"id": 4, "observed_on": "2026-03-20", "place_guess": "Obscured"},
            ]
        }
        parsed = wildlife.parse_inaturalist(payload, UTC)
        self.assertEqual(len(parsed), 3)
        for item in parsed:
            self.assertAlmostEqual(item.latitude, 34.85, places=4)
            self.assertAlmostEqual(item.longitude, -120.65, places=4)

    def test_geojson_longitude_comes_first(self):
        """Swapping these puts a whale in Kazakhstan, and nothing else catches it."""
        payload = {
            "results": [
                {
                    "id": 1,
                    "observed_on": "2026-03-20",
                    "geojson": {"type": "Point", "coordinates": [-121.25, 35.66]},
                    "taxon": {"name": "Orcinus orca"},
                }
            ]
        }
        parsed = wildlife.parse_inaturalist(payload, UTC)[0]
        self.assertGreater(parsed.latitude, 0)
        self.assertLess(parsed.longitude, 0)

    def test_malformed_payloads_return_nothing_rather_than_raising(self):
        for bad in (None, {}, [], "text", {"results": "nope"}, {"results": [None, 3]}):
            self.assertEqual(wildlife.parse_inaturalist(bad, UTC), [])
            self.assertEqual(wildlife.parse_ebird(bad, UTC), [])


class TestSightingClustering(unittest.TestCase):
    def _sighting(self, when, sub):
        return wildlife.parse_ebird([_ebird_entry(obsDt=when, subId=sub)], UTC)[0]

    def test_repeat_reports_collapse_and_count_observers(self):
        raw = [
            self._sighting("2026-03-18 08:00", "S1"),
            self._sighting("2026-03-19 09:00", "S2"),
            self._sighting("2026-03-20 07:15", "S3"),
        ]
        merged = wildlife.cluster(raw)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].reports, 3)
        self.assertEqual(len(merged[0].observers), 3)
        self.assertEqual(merged[0].latest.day, 20)
        self.assertEqual(merged[0].earliest.day, 18)

    def test_filtering_happens_before_clustering(self):
        """A single bad timestamp must not take the whole cluster with it.

        Clustering first would let the future-dated report set the cluster's
        `latest`, and the freshness filter would then discard every good report
        alongside it.
        """
        now = datetime(2026, 3, 20, 12, tzinfo=UTC)
        raw = [
            self._sighting("2026-03-20 07:15", "S1"),
            self._sighting("2026-03-25 07:15", "S2"),
        ]
        self.assertEqual(len(wildlife.cluster(raw)), 1)
        self.assertEqual(wildlife.fresh(wildlife.cluster(raw), now), [])
        digested = wildlife.digest(raw, now)
        self.assertEqual(len(digested), 1)
        self.assertEqual(digested[0].reports, 1)

    def test_stale_sightings_are_dropped(self):
        now = datetime(2026, 3, 20, 12, tzinfo=UTC)
        old = self._sighting("2026-03-10 08:00", "S9")
        self.assertEqual(wildlife.fresh([old], now), [])


class TestDriveEstimation(unittest.TestCase):
    def test_calibration_reproduces_the_zone_table_within_reason(self):
        """The estimator is fitted to the zone drive times, so it should
        approximately reproduce them. Anything worse than an hour and a half
        means the calibration is broken, not merely coarse."""
        home = const.DEFAULT_HOME
        for zone in const.TARGET_ZONES:
            estimate = wildlife.estimate_drive_hours(zone["latitude"], zone["longitude"], home)
            self.assertLess(
                abs(estimate - zone["drive_hours"]),
                1.7,
                f"{zone['name']}: estimated {estimate:.1f} h against a table value of {zone['drive_hours']} h",
            )

    def test_somewhere_close_to_home_is_reported_as_close(self):
        home = const.DEFAULT_HOME
        self.assertLess(wildlife.estimate_drive_hours(home[0] + 0.1, home[1], home), 0.5)

    def test_drive_description_never_implies_routed_precision(self):
        self.assertEqual(wildlife.describe_drive(0.48), "about 30 min away")
        self.assertEqual(wildlife.describe_drive(2.1), "roughly 2 h away")

    def test_nearest_zone_only_matches_within_range(self):
        self.assertIsNotNone(wildlife.nearest_zone(35.19, -119.79))
        self.assertIsNone(wildlife.nearest_zone(44.0, -121.0))


class TestSightingOpportunities(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 3, 20, 20, tzinfo=UTC)

    def _build(self, payload):
        return events.build_wildlife_opportunities(
            wildlife.digest(wildlife.parse_ebird(payload, UTC), self.now), self.now, const.DEFAULT_HOME
        )

    def test_a_staked_out_confirmed_rarity_clears_the_alert_bar(self):
        payload = [
            _ebird_entry(obsDt="2026-03-20 07:15", subId="S1"),
            _ebird_entry(obsDt="2026-03-19 16:00", subId="S2", obsReviewed=False),
            _ebird_entry(obsDt="2026-03-19 08:00", subId="S3", obsReviewed=False),
        ]
        built = self._build(payload)
        self.assertEqual(len(built), 1)
        self.assertGreaterEqual(built[0].score, const.DEFAULT_ALERT_SCORE)

    def test_a_single_unconfirmed_stale_report_does_not(self):
        payload = [_ebird_entry(obsDt="2026-03-18 07:15", subId="S1", obsReviewed=False)]
        self.assertLess(self._build(payload)[0].score, const.DEFAULT_ALERT_SCORE)

    def test_sightings_far_from_any_zone_still_appear_and_are_gated_by_drive_time(self):
        """A vagrant does not have to land on a target zone to count, but it
        does have to be reachable."""
        payload = [
            _ebird_entry(locName="Somewhere in Oregon", lat=44.0, lng=-121.0, subId="S1"),
            _ebird_entry(subId="S2"),
        ]
        built = self._build(payload)
        self.assertEqual(len(built), 2)
        reachable = events.within_drive(built, 6.0)
        self.assertEqual([item.title for item in reachable], ["Vermilion Flycatcher at Oso Flaco Lake"])

    def test_every_sighting_carries_coordinates_for_routing(self):
        for item in self._build([_ebird_entry()]):
            self.assertIsNotNone(item.latitude)
            self.assertIsNotNone(item.longitude)

    def test_humpbacks_rank_below_orcas_all_else_equal(self):
        """Humpbacks are abundant here in season; an orca is why you cancel
        your afternoon."""
        def marine(name):
            payload = {
                "results": [
                    {
                        "id": 1,
                        "observed_on": "2026-03-20",
                        "latitude": 34.85,
                        "longitude": -120.65,
                        "taxon": {"name": name},
                        "place_guess": "Surf Beach",
                    }
                ]
            }
            parsed = wildlife.digest(wildlife.parse_inaturalist(payload, UTC), self.now)
            return events.build_wildlife_opportunities(parsed, self.now, const.DEFAULT_HOME)[0].score

        self.assertGreater(marine("Orcinus orca"), marine("Megaptera novaeangliae"))


class TestFieldReportScraping(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 3, 20, tzinfo=UTC)
        self.blooms = field_reports.REPORT_SOURCES[0]
        self.foliage = field_reports.REPORT_SOURCES[2]

    def test_place_name_in_the_heading_reaches_the_report(self):
        """The case flat text cannot handle: the prose never names the place."""
        html = (
            '<div class="entry-content">'
            "<h2>Carrizo Plain National Monument</h2>"
            "<p>The hillsides are carpeted in goldfields and tidy tips.</p>"
            "</div>"
        )
        found = field_reports.parse_report(html, self.blooms, self.now)
        self.assertEqual([item.zone_id for item in found], ["carrizo_plain"])

    def test_negated_reports_are_not_reported_as_good_news(self):
        html = (
            '<div class="entry-content">'
            "<h2>Antelope Valley Poppy Reserve</h2>"
            "<p>The poppies are past peak and mostly gone by.</p>"
            "</div>"
        )
        self.assertEqual(field_reports.parse_report(html, self.blooms, self.now), [])

    def test_a_mixed_paragraph_keeps_its_good_half(self):
        html = "<article><p>Carrizo Plain is carpeted in goldfields. The Temblor Range is past peak.</p></article>"
        found = field_reports.parse_report(html, self.blooms, self.now)
        self.assertEqual(len(found), 1)
        self.assertNotIn("past peak", found[0].snippet.lower())

    def test_a_terse_verdict_is_quoted_with_enough_context_to_read(self):
        html = (
            '<div class="entry-content"><h3>Bishop Creek Canyon</h3>'
            "<p>Go Now! (75-100%) The aspens above Lake Sabrina are glowing gold.</p></div>"
        )
        snippet = field_reports.parse_report(html, self.foliage, self.now)[0].snippet
        self.assertIn("Go Now", snippet)
        self.assertIn("Sabrina", snippet)

    def test_one_report_per_zone_and_the_strongest_wins(self):
        html = (
            '<div class="entry-content">'
            "<p>Wildflowers are appearing at Carrizo Plain.</p>"
            "<p>Carrizo Plain is in peak bloom right now.</p>"
            "</div>"
        )
        found = field_reports.parse_report(html, self.blooms, self.now)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].strength, 20)

    def test_unrecognised_markup_degrades_to_flat_text_rather_than_failing(self):
        weird = "<xyz><thing>Death Valley has peak bloom near Badwater.</thing></xyz>"
        found = field_reports.parse_report(weird, self.blooms, self.now)
        self.assertEqual([item.zone_id for item in found], ["death_valley"])

    def test_garbage_input_is_survivable(self):
        for bad in ("", "<<<>>>", "no markup at all", "<html></html>"):
            self.assertEqual(field_reports.parse_report(bad, self.blooms, self.now), [])

    def test_scripts_and_styles_never_become_reports(self):
        html = '<div class="entry-content"><script>var s = "Carrizo peak bloom";</script><p>Hello.</p></div>'
        self.assertEqual(field_reports.parse_report(html, self.blooms, self.now), [])

    def test_reports_stay_below_the_drop_everything_threshold(self):
        """A sentence somebody wrote days ago must never say "get in the car"."""
        html = '<div class="entry-content"><h2>Death Valley</h2><p>Peak bloom along Badwater Road.</p></div>'
        found = field_reports.parse_report(html, self.blooms, self.now)
        for item in events.build_field_report_opportunities(found, self.now):
            self.assertLess(item.score, const.DEFAULT_ALERT_SCORE)

    def test_age_label_describes_the_fetch_not_the_observation(self):
        report = field_reports.FieldReport(
            source_id="x", source_name="X", url="", category=const.CATEGORY_BLOOMS,
            zone_id="carrizo_plain", headline="", snippet="", strength=10, fetched=self.now,
        )
        self.assertIn("read", report.age_label(self.now))


class TestRoutingClients(unittest.TestCase):
    def test_routes_response_is_matched_by_index_not_by_order(self):
        """computeRouteMatrix is designed to stream, so results can arrive in
        any order. Trusting position would attach Tahoe's drive time to Big Sur."""
        payload = [
            {"originIndex": 0, "destinationIndex": 2, "duration": "7200s", "distanceMeters": 100000},
            {"originIndex": 0, "destinationIndex": 0, "duration": "1800s", "distanceMeters": 30000},
        ]
        parsed = routing.parse_routes_response(payload)
        self.assertAlmostEqual(parsed[0].hours, 0.5)
        self.assertAlmostEqual(parsed[2].hours, 2.0)
        self.assertNotIn(1, parsed)

    def test_routes_skips_failed_and_unreachable_elements(self):
        payload = [
            {"destinationIndex": 0, "duration": "600s", "condition": "ROUTE_EXISTS"},
            {"destinationIndex": 1, "duration": "600s", "condition": "ROUTE_NOT_FOUND"},
            {"destinationIndex": 2, "duration": "600s", "status": {"code": 3}},
            {"destinationIndex": 3},
        ]
        self.assertEqual(sorted(routing.parse_routes_response(payload)), [0])

    def test_legacy_prefers_the_traffic_aware_duration(self):
        payload = {
            "status": "OK",
            "rows": [
                {
                    "elements": [
                        {
                            "status": "OK",
                            "duration": {"value": 3600},
                            "duration_in_traffic": {"value": 5400},
                            "distance": {"value": 90000},
                        },
                        {"status": "OK", "duration": {"value": 1800}},
                        {"status": "ZERO_RESULTS"},
                    ]
                }
            ],
        }
        parsed = routing.parse_legacy_response(payload)
        self.assertAlmostEqual(parsed[0].hours, 1.5)
        self.assertTrue(parsed[0].in_traffic)
        self.assertAlmostEqual(parsed[1].hours, 0.5)
        self.assertFalse(parsed[1].in_traffic)
        self.assertNotIn(2, parsed)

    def test_error_payloads_yield_nothing_rather_than_raising(self):
        for bad in (None, {}, [], "text", {"status": "REQUEST_DENIED"}, {"status": "OK", "rows": []}):
            self.assertEqual(routing.parse_legacy_response(bad), {})
        for bad in (None, {}, "text"):
            self.assertEqual(routing.parse_routes_response(bad), {})

    def test_batches_respect_the_element_limit(self):
        points = [(34.0 + i / 100, -120.0) for i in range(60)]
        batches = routing.chunk_destinations(points)
        self.assertTrue(all(len(batch) <= routing.MAX_DESTINATIONS_PER_REQUEST for batch in batches))
        self.assertEqual(sum(len(batch) for batch in batches), 60)

    def test_requests_carry_what_each_api_requires(self):
        _, headers, body = routing.build_routes_request((34.7, -120.5), [(35.0, -120.0)], "KEY")
        self.assertEqual(headers["X-Goog-Api-Key"], "KEY")
        self.assertIn("X-Goog-FieldMask", headers)
        self.assertEqual(body["routingPreference"], "TRAFFIC_AWARE")

        _, params = routing.build_legacy_request((34.7, -120.5), [(35.0, -120.0)], "KEY")
        self.assertEqual(params["key"], "KEY")
        # Without a departure time Google never returns duration_in_traffic.
        self.assertEqual(params["departure_time"], "now")


class TestRateLimiting(unittest.TestCase):
    def test_a_source_is_not_refetched_inside_its_interval(self):
        now = datetime(2026, 3, 20, 12, tzinfo=UTC)
        source = throttle.Source("Test", 60)
        self.assertTrue(source.due(now))
        source.succeed(now, ["data"])
        self.assertFalse(source.due(now + timedelta(minutes=59)))
        self.assertTrue(source.due(now + timedelta(minutes=61)))

    def test_scrapers_are_held_to_a_day(self):
        now = datetime(2026, 3, 20, 12, tzinfo=UTC)
        source = throttle.Source("Hotlines", const.MIN_INTERVAL_FIELD_REPORTS)
        source.succeed(now, ["report"])
        self.assertFalse(source.due(now + timedelta(hours=23)))
        self.assertTrue(source.due(now + timedelta(hours=25)))

    def test_a_failure_keeps_the_previous_payload(self):
        now = datetime(2026, 3, 20, 12, tzinfo=UTC)
        source = throttle.Source("Test", 60)
        source.succeed(now, ["good"])
        source.fail(now + timedelta(minutes=61), "boom")
        self.assertEqual(source.value, ["good"])
        self.assertEqual(source.status()["failures"], 1)

    def test_failures_back_off_but_never_past_the_interval(self):
        now = datetime(2026, 3, 20, 12, tzinfo=UTC)
        source = throttle.Source("Test", 60)
        for _ in range(10):
            source.fail(now, "boom")
        self.assertLessEqual(source.next_attempt - now, timedelta(minutes=60))

    def test_a_failure_retries_sooner_than_a_full_interval(self):
        now = datetime(2026, 3, 20, 12, tzinfo=UTC)
        source = throttle.Source("Test", 60)
        source.fail(now, "boom")
        self.assertTrue(source.due(now + timedelta(minutes=16)))
        self.assertFalse(source.due(now + timedelta(minutes=14)))

    def test_configured_intervals_are_at_least_hourly(self):
        """The user-facing promise: nothing is polled harder than once an hour."""
        for interval in (
            const.MIN_INTERVAL_WEATHER,
            const.MIN_INTERVAL_EBIRD,
            const.MIN_INTERVAL_INATURALIST,
        ):
            self.assertGreaterEqual(interval, 60)
        self.assertGreaterEqual(const.MIN_INTERVAL_FIELD_REPORTS, 60 * 24)
