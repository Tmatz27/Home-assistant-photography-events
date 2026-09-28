"""End-to-end pipeline contracts: network payload -> coordinator -> sensor.

The independent review found wiring bugs that 394 passing tests missed,
because those tests checked helpers and stubbed ``_build``. Here the real
coordinator runs a real cycle - fetchers, parsers, evidence, conditions,
source health, eligibility and dashboard assembly - with HTTP faked only at
``session.request``, and the result is read back through the real sensor,
calendar and event bus. Run in the Home Assistant CI job; skipped without HA.
"""
import importlib.util
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

HAS_HA = importlib.util.find_spec("homeassistant") is not None
if HAS_HA:
    from homeassistant.core import HomeAssistant, State
    from homeassistant.util import dt as dt_util
    from custom_components.photography_events import coordinator as module
    from custom_components.photography_events import async_migrate_entry
    from custom_components.photography_events.config_flow import _clean
    from custom_components.photography_events.calendar import PhotographyCalendar
    from custom_components.photography_events.email_reports import parse_email_report
    from custom_components.photography_events.sensor import CantMissSensor, PlanningOutlookSensor
    from custom_components.photography_events.event_state import event_id

NOW = datetime(2026, 9, 27, 17, tzinfo=timezone.utc)
FORECAST_KEYS = ("cloud_cover", "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "relative_humidity_2m",
                 "precipitation_probability", "visibility", "weather_code", "snowfall", "temperature_2m",
                 "wind_speed_10m")


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    async def json(self, **kwargs):
        return self.payload

    async def text(self):
        return self.payload if isinstance(self.payload, str) else json.dumps(self.payload)


def hourly(start, hours=240, **values):
    base = {"cloud_cover": 20, "cloud_cover_low": 5, "cloud_cover_mid": 10, "cloud_cover_high": 40,
            "relative_humidity_2m": 60, "precipitation_probability": 0, "visibility": 30000, "weather_code": 1,
            "snowfall": 0, "temperature_2m": 12, "wind_speed_10m": 2}
    base.update(values)
    times = [start + timedelta(hours=i) for i in range(hours)]
    return {"hourly": {"time": [t.isoformat() for t in times],
                       **{key: [base[key]] * hours for key in FORECAST_KEYS}}}


class Router:
    """A fake aiohttp session: the first matching URL fragment answers."""

    def __init__(self, now):
        self.now = now
        self.calls = []
        self.routes = {
            "api.open-meteo.com": self.forecast,
            "air-quality-api": lambda url, params: [
                {"hourly": {"time": [(now + timedelta(hours=i)).isoformat() for i in range(120)],
                            "aerosol_optical_depth": [0.05] * 120}}
                for _ in str(params["latitude"]).split(",")],
            "api.weather.gov": lambda url, params: {"type": "FeatureCollection", "features": []},
            "api.inaturalist.org": lambda url, params: {"results": []},
            "condorexpress": lambda url, params: "<rss><channel></channel></rss>",
            "ovation": lambda url, params: {"Observation Time": now.isoformat(), "Forecast Time": now.isoformat(),
                                            "coordinates": [[0, 0, 0]]},
            "tidesandcurrents": lambda url, params: {"predictions": []},
            "api.ebird.org": lambda url, params: [],
            "developer.nps.gov": lambda url, params: {"total": "0", "data": []},
        }
        self.forecast_failures = set()

    def forecast(self, url, params):
        latitudes = [float(value) for value in str(params["latitude"]).split(",")]
        if any(round(lat, 3) in self.forecast_failures for lat in latitudes):
            return Response({"error": True, "reason": "test outage"}, 500)
        return [hourly(self.now - timedelta(hours=2)) for _ in latitudes]

    async def request(self, method, url, params=None, headers=None, json=None, data=None):
        self.calls.append((url, dict(params or {})))
        for fragment, handler in self.routes.items():
            if fragment in url:
                result = handler(url, params or {})
                return result if isinstance(result, Response) else Response(result)
        return Response(None, 404)


@unittest.skipUnless(HAS_HA, "Home Assistant is tested in the separate HA CI job")
class PipelineContracts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if os.name == "nt":
            permissions = patch("os.fchmod", create=True)
            permissions.start()
            self.addCleanup(permissions.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        self.hass.config.latitude, self.hass.config.longitude = 34.742, -120.5724
        await self.hass.config.async_set_time_zone("America/Los_Angeles")
        self.addCleanup(dt_util.set_default_time_zone, timezone.utc)
        self.entry = SimpleNamespace(entry_id="pipeline", data={}, options={}, version=2)
        self.now = NOW
        self.router = Router(self.now)
        for target, value in (("async_get_clientsession", lambda hass: self.router),
                              ("ir.async_create_issue", Mock()), ("ir.async_delete_issue", Mock()),
                              ("GROUP_STAGGER_SECONDS", 0), ("INATURALIST_SPACING_SECONDS", 0)):
            context = patch(f"{module.__name__}.{target}", value)
            context.start()
            self.addCleanup(context.stop)
        self.clock = patch(f"{module.__name__}.dt_util.utcnow", side_effect=lambda: self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.coordinator = module.PhotographyEventsCoordinator(self.hass, self.entry)
        await self.coordinator.async_initialize()
        self.coordinator._cold_start = False

    async def asyncTearDown(self):
        await self.coordinator.async_shutdown()
        await self.hass.async_stop(force=True)
        self.directory.cleanup()

    def set_now(self, moment):
        self.now = moment
        self.router.now = moment

    async def cycle(self, categories, **options):
        self.entry.options = {"enabled_categories": list(categories), **options}
        self.coordinator.data = await self.coordinator._async_update_data()
        return CantMissSensor(self.coordinator, self.entry).extra_state_attributes

    # --- C1 ------------------------------------------------------------------------

    async def test_boat_with_empty_land_alerts_is_held_not_recommended(self):
        observations = [{"id": i, "uri": f"https://inat.test/{i}", "quality_grade": "research",
                         "geojson": {"coordinates": [-119.70, 34.40 + 0.01 * i]},
                         "time_observed_at": (self.now - timedelta(hours=3 + i)).isoformat(),
                         "taxon": {"name": "Orcinus orca", "preferred_common_name": "Orca"},
                         "user": {"login": f"observer{i}"}, "place_guess": "Santa Barbara Channel"} for i in range(2)]
        self.router.routes["api.inaturalist.org"] = lambda url, params: (
            {"results": observations} if params.get("taxon_name") == "Orcinus orca" else {"results": []})
        board = await self.cycle(["marine"])
        self.assertEqual(board["events"], [])
        held = [row for row in board["held"] if row["phenomenon"] == "orca_presence"]
        self.assertEqual(len(held), 1)
        self.assertIn("Marine conditions not checked", held[0]["summary"])
        self.assertNotEqual(board["headline"], "Nothing worth changing plans for this week.")
        self.assertIsNone(self.coordinator.data["top_action"])

    # --- C6 ------------------------------------------------------------------------

    async def test_malformed_nws_features_are_an_incomplete_check_end_to_end(self):
        self.router.routes["api.weather.gov"] = lambda url, params: {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"headline": "no event, no area"}}]}
        board = await self.cycle(["mammals"])
        health = self.coordinator.data["sources"]["surf_alerts"]
        self.assertEqual(health["state"], "failed")
        self.assertIn("unusable", health["last_error"])
        self.assertEqual(board["assessment"]["state"], "incomplete")
        self.assertIn("surf_alerts", [p["source"] for p in board["assessment"]["problems"]])
        self.assertNotEqual(board["headline"], "Nothing worth changing plans for this week.")

    async def test_valid_empty_nws_feed_is_a_healthy_check(self):
        board = await self.cycle(["mammals"])
        self.assertEqual(self.coordinator.data["sources"]["surf_alerts"]["state"], "ok")
        self.assertEqual(board["assessment"]["state"], "complete")

    # --- C2 ------------------------------------------------------------------------

    async def firefall_cycle(self, **options):
        self.set_now(datetime(2027, 2, 16, 18, tzinfo=timezone.utc))
        report = parse_email_report("Yosemite conditions", "Horsetail Fall is flowing this morning.",
                                    "Ranger list", "rare_phenomena", "yosemite_valley", self.now - timedelta(hours=4))
        self.coordinator._ingested_reports = list(report)
        await self.cycle(["rare_phenomena"], **options)
        return next(item for item in self.coordinator.data["opportunities"]
                    if item.phenomenon == "horsetail_firefall" and item.extra.get("precision") == "peak")

    async def test_rare_on_parks_off_firefall_without_nps_is_held(self):
        item = await self.firefall_cycle()
        self.assertEqual(item.extra["access_state"], "unknown")
        self.assertFalse(item.extra["assessment"]["eligible"])
        self.assertIn("Park access not checked", " ".join(item.extra["assessment"]["blockers"]))

    async def test_rare_on_parks_off_fetches_nps_for_firefall_with_pagination(self):
        pages = {0: {"total": "60", "data": [{"parkCode": "yose", "title": f"Info {i}", "category": "Information"}
                                              for i in range(50)]},
                 50: {"total": "60", "data": [{"parkCode": "yose", "title": f"Info {i}", "category": "Information"}
                                               for i in range(50, 60)]}}
        self.router.routes["developer.nps.gov"] = lambda url, params: pages[int(params["start"])]
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertEqual(item.extra["access_state"], "open")
        starts = [params["start"] for url, params in self.router.calls if "developer.nps.gov" in url]
        self.assertEqual(starts, [0, 50])

    async def test_short_nps_read_keeps_access_unknown(self):
        self.router.routes["developer.nps.gov"] = lambda url, params: {"total": "60", "data": [
            {"parkCode": "yose", "title": "Info", "category": "Information"}] * 50} if int(params["start"]) == 0 else \
            {"total": "60", "data": []}
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertEqual(item.extra["access_state"], "unknown")
        self.assertEqual(self.coordinator.data["sources"]["park_alerts"]["state"], "failed")

    async def test_real_nps_closure_category_blocks(self):
        self.router.routes["developer.nps.gov"] = lambda url, params: {"total": "1", "data": [
            {"parkCode": "yose", "title": "Northside Drive closed for firefall", "category": "Park Closure",
             "description": "El Capitan picnic area closed."}]}
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertEqual(item.extra["access_state"], "closed")
        self.assertTrue(any(b.startswith("access:") for b in item.extra["assessment"]["blockers"]))

    # --- C5 ------------------------------------------------------------------------

    async def test_negated_lunge_feeding_email_through_ingest_and_cycle(self):
        reports = parse_email_report("Whale report", "No lunge feeding at Avila today. Humpbacks are passing offshore.",
                                     "Whale list", None, None, self.now - timedelta(hours=2))
        self.coordinator._ingested_reports = list(reports)
        board = await self.cycle(["marine"])
        humpback = next(item for item in self.coordinator.data["opportunities"]
                        if item.phenomenon == "humpback_lunge_feeding" and item.extra.get("precision") == "peak")
        self.assertNotEqual(humpback.extra["evidence_state"], "behavior_confirmed")
        self.assertNotIn("humpback_lunge_feeding", [row["phenomenon"] for row in board["events"]])

    # --- H5 / H6 --------------------------------------------------------------------

    async def test_stale_sunsetwx_model_downloaded_now_falls_back_visibly(self):
        stale = (self.now - timedelta(days=5)).isoformat()
        self.router.routes["sunsetwx.com/v1/login"] = lambda url, params: {"access_token": "t", "expires_in": 3600}
        self.router.routes["sunsetwx.com/v1/quality"] = lambda url, params: {"type": "FeatureCollection", "features": [
            {"properties": {"type": params["type"], "quality": "Great", "quality_percent": 95,
                            "valid_at": (self.now + timedelta(hours=9)).isoformat(), "last_updated": stale,
                            "source": "GFS"}}]}
        await self.cycle(["sunset"], sunsetwx_client_id="id", sunsetwx_client_secret="secret")
        health = self.coordinator.data["sources"]["sunsetwx"]
        self.assertEqual(health["state"], "failed")
        self.assertIn("not current", health["last_error"])
        for item in self.coordinator.data["opportunities"]:
            if item.category == "sunset":
                self.assertNotIn("provider_quality", item.extra, "a five-day-old model must not decide")

    async def test_failed_optional_air_quality_does_not_score_the_sunset(self):
        source = self.coordinator._sources["air_quality"]
        source.succeed(self.now - timedelta(hours=10), {"home": {"hourly": {
            "time": [(self.now + timedelta(hours=i)).isoformat() for i in range(48)],
            "aerosol_optical_depth": [3.0] * 48}}})
        source.fail(self.now - timedelta(hours=1), "offline")
        source.next_attempt = self.now + timedelta(hours=1)
        await self.cycle(["sunset"])
        skies = [item for item in self.coordinator.data["opportunities"] if item.category == "sunset"]
        for item in skies:
            self.assertNotIn("aerosol", " ".join(item.reasons))
            self.assertIn("air_quality_note", item.extra)

    # --- H7 / H8 --------------------------------------------------------------------

    async def test_unrelated_weather_point_failure_leaves_home_rows_healthy(self):
        tahoe = next(zone for zone in module.TARGET_ZONES if zone["id"] == "lake_tahoe")
        self.router.forecast_failures.add(round(tahoe["latitude"], 3))
        board = await self.cycle(["sunset", "astronomy"], max_drive_hours=12)
        self.assertEqual(self.coordinator.data["sources"]["weather"]["state"], "failed")
        for item in self.coordinator.data["opportunities"]:
            if item.phenomenon == "sunset_local":
                self.assertNotIn("degraded_required", item.extra)
        problems = [p["source"] for p in board["assessment"]["problems"]]
        self.assertIn("weather:lake_tahoe", problems)
        self.assertNotIn("weather:home", problems)

    async def test_home_point_failure_makes_the_assessment_incomplete(self):
        self.router.forecast_failures.add(round(34.742, 3))
        board = await self.cycle(["sunset"])
        self.assertEqual(board["assessment"]["state"], "incomplete")
        self.assertEqual(board["headline"], "Can't Miss assessment incomplete: required data unavailable.")

    # --- H9 -------------------------------------------------------------------------

    async def test_birds_on_rare_off_keeps_the_crane_spectacle(self):
        self.set_now(datetime(2026, 12, 20, 18, tzinfo=timezone.utc))
        checklist = [{"speciesCode": "sancra", "comName": "Sandhill Crane", "sciName": "Antigone canadensis",
                      "locName": "Merced NWR", "lat": 37.18, "lng": -120.60, "howMany": 4000,
                      "obsDt": (self.now - timedelta(hours=10)).astimezone(dt_util.DEFAULT_TIME_ZONE).strftime("%Y-%m-%d %H:%M"),
                      "subId": "S1", "obsValid": True, "obsReviewed": False}]
        self.router.routes["api.ebird.org"] = lambda url, params: checklist if "sancra" in url else []
        board = await self.cycle(["birds"], ebird_api_key="test-only")
        cranes = [row for row in board["birds"]["spectacle"] if row["phenomenon"] == "sandhill_crane_flyin"]
        self.assertEqual(len(cranes), 1)

    # --- H10 ------------------------------------------------------------------------

    async def test_out_of_season_blue_whale_report_is_not_lost(self):
        self.set_now(datetime(2026, 10, 25, 18, tzinfo=timezone.utc))
        reports = parse_email_report("Channel report", "Blue whales feeding off Santa Cruz Island this morning.",
                                     "Whale list", "marine", None, self.now - timedelta(hours=3))
        self.coordinator._ingested_reports = list(reports)
        board = await self.cycle(["marine"])
        live = [item for item in self.coordinator.data["opportunities"] if item.extra.get("live_occurrence")]
        self.assertEqual([item.phenomenon for item in live], ["blue_whale_feeding"])
        self.assertIn("blue_whale_feeding", [row["phenomenon"] for row in board["held"]])

    # --- H11 ------------------------------------------------------------------------

    async def test_thirty_day_old_route_is_not_current_traffic(self):
        item = module.event_builder.Opportunity("mw", "Milky Way", "astronomy", "z", "Zone", self.now + timedelta(hours=5),
                                                self.now + timedelta(hours=7), 95, "", 1.0, latitude=35.2, longitude=-119.8)
        point = module._point(item)
        self.coordinator._routing_cache[self.coordinator._route_key(point)] = (
            SimpleNamespace(hours=0.5, minutes=30, source="Routes API", in_traffic=True), self.now - timedelta(days=30))
        self.entry.options = {"google_api_key": "test-only"}
        self.router.routes["routes.googleapis.com"] = lambda url, params: Response(None, 500)
        self.router.routes["maps.googleapis.com"] = lambda url, params: Response(None, 500)
        await self.coordinator._apply_routing(self.router, self.now, [item])
        self.assertEqual(item.extra["drive_basis"], "estimate")
        self.assertEqual(item.drive_hours, 1.0)
        self.assertFalse(item.drive_in_traffic)
        self.assertFalse(any("current traffic" in reason for reason in item.reasons))

    async def test_recent_route_is_labelled_not_current(self):
        item = module.event_builder.Opportunity("mw", "Milky Way", "astronomy", "z", "Zone", self.now + timedelta(hours=5),
                                                self.now + timedelta(hours=7), 95, "", 1.0, latitude=35.2, longitude=-119.8)
        self.coordinator._routing_cache[self.coordinator._route_key(module._point(item))] = (
            SimpleNamespace(hours=0.75, minutes=45, source="Routes API", in_traffic=True), self.now - timedelta(days=2))
        self.entry.options = {"google_api_key": "test-only"}
        self.router.routes["googleapis.com"] = lambda url, params: Response(None, 500)
        await self.coordinator._apply_routing(self.router, self.now, [item])
        self.assertEqual(item.extra["drive_basis"], "recent")
        self.assertFalse(item.drive_in_traffic)
        self.assertTrue(any("not current traffic" in reason for reason in item.reasons))

    # --- M1 -------------------------------------------------------------------------

    async def test_grunion_and_moonbow_are_timed_calendar_entries_in_pacific_time(self):
        from custom_components.photography_events import grunion, spectacles
        start = datetime(2027, 3, 14, 21, 50, tzinfo=dt_util.get_time_zone("America/Los_Angeles"))
        (run,) = grunion.opportunities([(start, start + timedelta(hours=2))], datetime(2027, 3, 1, tzinfo=timezone.utc),
                                       (34.742, -120.5724))
        event = PhotographyCalendar._to_calendar_event(run)
        self.assertIsInstance(event.start, datetime)
        self.assertEqual(dt_util.as_local(event.start).strftime("%Y-%m-%d %H:%M"), "2027-03-14 22:15")
        moonbow = spectacles.moonbow_opportunities(datetime(2026, 5, 25, tzinfo=timezone.utc), (34.742, -120.5724))[0]
        self.assertIsInstance(PhotographyCalendar._to_calendar_event(moonbow).start, datetime)

    # --- M2 -------------------------------------------------------------------------

    async def test_skip_on_a_winter_occurrence_survives_new_year_through_the_store(self):
        self.set_now(datetime(2026, 12, 31, 20, tzinfo=timezone.utc))
        await self.cycle(["rare_phenomena"])
        crane = next(item for item in self.coordinator.data["opportunities"]
                     if item.phenomenon == "sandhill_crane_flyin" and item.start <= self.now <= item.end)
        await self.coordinator.async_set_event_choice(event_id(crane), "skip")
        self.set_now(datetime(2027, 1, 1, 9, tzinfo=timezone.utc))
        board = await self.cycle(["rare_phenomena"])
        crane_now = next(item for item in self.coordinator.data["opportunities"]
                         if item.phenomenon == "sandhill_crane_flyin" and item.start <= self.now <= item.end)
        self.assertEqual(event_id(crane_now), event_id(crane))
        self.assertTrue(self.coordinator.event_state.suppressed(event_id(crane_now)))
        self.assertNotIn("sandhill_crane_flyin", [row["phenomenon"] for row in board["events"]])

    # --- M4 -------------------------------------------------------------------------

    async def test_opportunity_event_announces_the_eligible_alternative(self):
        fired = []
        self.hass.bus.async_listen("photography_events_opportunity", lambda event: fired.append(event.data))
        base = self.now + timedelta(hours=5)
        extra = {"verification": "computed", "evidence_state": "computed", "cloud_is_forecast": True, "cloud_cover": 5}
        near = module.event_builder.Opportunity("mw-near", "Milky Way core", "astronomy", "near", "Near", base,
                                                base + timedelta(hours=2), 94, "", 1.0, extra=dict(extra),
                                                latitude=35.191, longitude=-119.793, roll="mw-night", phenomenon="milky_way")
        # Higher score, same occurrence, but its cloud is only an outlook:
        # it fails the gate and must not shadow the eligible viewpoint.
        far = module.event_builder.Opportunity("mw-far", "Milky Way core", "astronomy", "far", "Far", base,
                                               base + timedelta(hours=2), 95, "", 1.5,
                                               extra={**extra, "cloud_is_forecast": False},
                                               latitude=35.4, longitude=-119.9, roll="mw-night", phenomenon="milky_way")
        async def build(*args):
            return [near, far]
        self.coordinator._build = build
        await self.cycle(["astronomy"])
        await self.hass.async_block_till_done()
        self.assertFalse(far.extra["assessment"]["eligible"])
        self.assertEqual([event["where"] for event in fired], ["Near"])

    # --- M5 / M6 --------------------------------------------------------------------

    async def test_clearing_a_secret_in_options_removes_it(self):
        self.entry.data = {"ebird_api_key": "old-key", "nps_api_key": "old-nps"}
        self.entry.options = _clean({"enabled_categories": ["birds"]}, options=True)
        self.assertEqual(self.coordinator.ebird_key, "")
        self.assertEqual(self.coordinator.nps_key, "")
        self.assertNotIn("ebird", self.coordinator._enabled_sources())
        self.entry.options = _clean({"enabled_categories": ["birds"], "ebird_api_key": " new "}, options=True)
        self.assertEqual(self.coordinator.ebird_key, "new")
        self.assertNotIn("ebird_api_key", _clean({"ebird_api_key": ""}), "setup keeps one representation")

    async def test_explicit_empty_categories_mean_none(self):
        self.entry.options = {"enabled_categories": []}
        self.assertEqual(self.coordinator.enabled_categories, set())
        board = await self.cycle([])
        self.assertEqual(self.coordinator.data["opportunities"], [])
        self.assertFalse(any("api.open-meteo.com" in url for url, _ in self.router.calls))
        self.entry.options = {}
        self.assertEqual(len(self.coordinator.enabled_categories), 10, "missing setting uses the defaults")
        self.assertIn("assessment", board)

    async def test_waves_intentionally_disabled_stays_disabled(self):
        everything_but_waves = [c for c in module.ALL_CATEGORIES if c != "waves"]
        self.entry.options = {"enabled_categories": everything_but_waves}
        self.assertNotIn("waves", self.coordinator.enabled_categories)
        await self.cycle(everything_but_waves)
        self.assertNotIn("waves", self.coordinator.enabled_categories, "reading a setting never changes it")

    async def test_legacy_entry_is_migrated_once(self):
        legacy = [c for c in module.ALL_CATEGORIES if c != "waves"]
        entry = SimpleNamespace(version=1, data={"enabled_categories": legacy}, options={})
        updates = []
        hass = SimpleNamespace(config_entries=SimpleNamespace(
            async_update_entry=lambda target, **changes: updates.append(changes) or target.__dict__.update(changes)))
        self.assertTrue(await async_migrate_entry(hass, entry))
        self.assertIn("waves", entry.data["enabled_categories"])
        self.assertEqual(entry.version, 2)
        entry.data = {"enabled_categories": legacy}  # a version-2 choice is left alone
        self.assertTrue(await async_migrate_entry(hass, entry))
        self.assertNotIn("waves", entry.data["enabled_categories"])
        self.assertEqual(len(updates), 1)

    # --- Payload and recorder -------------------------------------------------------

    async def test_heavy_attributes_are_excluded_by_the_real_recorder_path(self):
        from homeassistant.components.recorder.db_schema import MAX_STATE_ATTRS_BYTES, StateAttributes
        await self.cycle(["astronomy", "rare_phenomena", "marine", "mammals", "waves", "sunset"], max_drive_hours=12)
        for sensor in (CantMissSensor(self.coordinator, self.entry), PlanningOutlookSensor(self.coordinator, self.entry)):
            attributes = sensor.extra_state_attributes
            self.assertLess(len(json.dumps(attributes, default=str)), 2_000_000, "websocket payload stays bounded")
            unrecorded = sensor._Entity__combined_unrecorded_attributes
            state = State("sensor.test", str(sensor.native_value), json.loads(json.dumps(attributes, default=str)),
                          state_info={"unrecorded_attributes": unrecorded})
            stored = StateAttributes.shared_attrs_bytes_from_event(
                SimpleNamespace(data={"new_state": state}), None)
            recorded = json.loads(stored)
            for heavy in ("events", "watch", "held", "signals", "birds", "sources", "assessment"):
                self.assertNotIn(heavy, recorded)
            self.assertLess(len(stored), MAX_STATE_ATTRS_BYTES)


if __name__ == "__main__":
    unittest.main()
