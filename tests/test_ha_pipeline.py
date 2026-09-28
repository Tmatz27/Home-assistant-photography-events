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
    from custom_components.photography_events.const import ZONES_BY_ID

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
        # (zone latitude, part index) -> edit(part) for one component of one
        # zone's three-part answer: 0 local, 1 sunset path, 2 sunrise path.
        self.forecast_edits = {}

    def forecast(self, url, params):
        latitudes = [float(value) for value in str(params["latitude"]).split(",")]
        if any(round(lat, 3) in self.forecast_failures for lat in latitudes):
            return Response({"error": True, "reason": "test outage"}, 500)
        parts = [hourly(self.now - timedelta(hours=2)) for _ in latitudes]
        for (latitude, index), edit in self.forecast_edits.items():
            if round(latitudes[0], 3) == round(latitude, 3) and index < len(parts):
                parts[index] = edit(parts[index])
        return parts

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

    async def test_nws_geography_the_gate_cannot_place_is_never_safe(self):
        # Second review, R2: a December elephant-seal cycle. Each warning is
        # real and current; none can be placed, so safety is unknown.
        self.set_now(datetime(2026, 12, 20, 18, tzinfo=timezone.utc))

        def warning(**geo):
            return {"type": "Feature", "geometry": geo.pop("geometry", None),
                    "properties": {"event": "High Wind Warning", "headline": "High Wind Warning", "severity": "Severe",
                                   "geocode": geo, "onset": (self.now - timedelta(hours=1)).isoformat(),
                                   "expires": (self.now + timedelta(hours=12)).isoformat()}}
        nan_ring = [[[-121.3, 35.6], [float("nan"), 35.7], [-121.2, 35.7], [-121.3, 35.6]]]
        cases = {"UGC only": warning(UGC=["CAZ340"]), "bogus SAME": warning(SAME=["garbage"]),
                 "scalar SAME": warning(SAME="006079"),
                 "NaN polygon": warning(geometry={"type": "Polygon", "coordinates": nan_ring})}
        for name, feature in cases.items():
            with self.subTest(name):
                alerts = self.coordinator._sources["surf_alerts"]
                alerts.fetched_at, alerts.next_attempt = None, None
                self.router.routes["api.weather.gov"] = lambda url, params, feature=feature: {
                    "type": "FeatureCollection", "features": [feature]}
                board = await self.cycle(["mammals"])
                self.assertEqual(self.coordinator.data["sources"]["surf_alerts"]["state"], "failed")
                self.assertEqual(board["assessment"]["state"], "incomplete")
                self.assertNotIn("elephant_seal_battles", [row["phenomenon"] for row in board["events"]])
                seals = [item for item in self.coordinator.data["opportunities"]
                         if item.phenomenon == "elephant_seal_battles"]
                self.assertTrue(seals)
                self.assertTrue(all(item.extra["assessment"]["safety_state"] != "safe" for item in seals))

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
        pages = {0: {"total": "60", "data": [{"id": f"i{i}", "parkCode": "yose", "title": f"Info {i}",
                                               "category": "Information"} for i in range(50)]},
                 50: {"total": "60", "data": [{"id": f"i{i}", "parkCode": "yose", "title": f"Info {i}",
                                                "category": "Information"} for i in range(50, 60)]}}
        self.router.routes["developer.nps.gov"] = lambda url, params: pages[int(params["start"])]
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertEqual(item.extra["access_state"], "open")
        starts = [params["start"] for url, params in self.router.calls if "developer.nps.gov" in url]
        self.assertEqual(starts, [0, 50])

    async def test_short_nps_read_keeps_access_unknown(self):
        self.router.routes["developer.nps.gov"] = lambda url, params: {"total": "60", "data": [
            {"id": f"i{i}", "parkCode": "yose", "title": "Info", "category": "Information"} for i in range(50)]} if int(params["start"]) == 0 else \
            {"total": "60", "data": []}
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertEqual(item.extra["access_state"], "unknown")
        self.assertEqual(self.coordinator.data["sources"]["park_alerts"]["state"], "failed")

    async def test_real_nps_closure_category_blocks(self):
        self.router.routes["developer.nps.gov"] = lambda url, params: {"total": "1", "data": [
            {"id": "c1", "parkCode": "yose", "title": "Northside Drive closed for firefall", "category": "Park Closure",
             "description": "El Capitan picnic area closed."}]}
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertEqual(item.extra["access_state"], "closed")
        self.assertTrue(any(b.startswith("access:") for b in item.extra["assessment"]["blockers"]))

    async def test_duplicate_or_unreadable_nps_records_keep_access_unknown(self):
        record = {"id": "i1", "parkCode": "yose", "title": "Info", "category": "Information"}
        for data in ([record, record], [record, {**record, "id": "i2", "category": ""}]):
            with self.subTest(data=data):
                self.router.routes["developer.nps.gov"] = lambda url, params, data=data: {"total": "2", "data": data}
                item = await self.firefall_cycle(nps_api_key="test-only")
                self.assertEqual(item.extra["access_state"], "unknown")
                self.assertFalse(item.extra["assessment"]["eligible"])
                self.assertEqual(self.coordinator.data["sources"]["park_alerts"]["state"], "failed")

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

    async def test_another_species_behaviour_never_confirms_through_ha(self):
        # Second review, R3, through ingest and a real cycle.
        reports = parse_email_report("Whale report", "Humpbacks passed Avila today and dolphins were lunge feeding.",
                                     "Whale list", None, None, self.now - timedelta(hours=2))
        self.coordinator._ingested_reports = list(reports)
        board = await self.cycle(["marine"])
        humpback = next(item for item in self.coordinator.data["opportunities"]
                        if item.phenomenon == "humpback_lunge_feeding" and item.extra.get("precision") == "peak")
        self.assertNotEqual(humpback.extra["evidence_state"], "behavior_confirmed")
        self.assertNotIn("humpback_lunge_feeding", [row["phenomenon"] for row in board["events"]])
        self.assertNotIn("humpback_lunge_feeding", [row["phenomenon"] for row in board["held"]])

    async def test_sea_lions_feeding_is_not_a_condor_spectacle_through_ha(self):
        self.set_now(datetime(2026, 12, 20, 18, tzinfo=timezone.utc))
        checklist = [{"speciesCode": "calcon", "comName": "California Condor", "sciName": "Gymnogyps californianus",
                      "locName": "Pinnacles NP--High Peaks", "lat": 36.487, "lng": -121.195, "howMany": 1,
                      "obsDt": (self.now - timedelta(hours=5)).astimezone(dt_util.DEFAULT_TIME_ZONE).strftime("%Y-%m-%d %H:%M"),
                      "subId": "S2", "obsValid": True, "obsReviewed": False}]
        self.router.routes["api.ebird.org"] = lambda url, params: checklist if "calcon" in url else []
        self.coordinator._ingested_reports = list(parse_email_report(
            "Pinnacles", "Condors at Pinnacles today and sea lions feeding.", "Park list", "birds", None,
            self.now - timedelta(hours=3)))
        board = await self.cycle(["birds"], ebird_api_key="test-only")
        self.assertEqual([row for row in board["birds"]["spectacle"] if row["phenomenon"] == "condor_activity"], [])
        self.assertNotIn("condor_activity", [row["phenomenon"] for row in board["events"]])

    async def test_hotline_page_date_does_not_renew_an_old_bloom_through_ha(self):
        # Second review, R4: HTML from the hotline URL through the real scraper,
        # builder, gate and sensor.
        self.set_now(datetime(2026, 3, 27, 18, tzinfo=timezone.utc))
        page = ("<html><body><div class='entry-content'><h2>Carrizo March 27, 2026</h2><p>On March 1, 2026 Carrizo "
                "was carpeted with wildflowers in full bloom. The road was repaired today.</p></div></body></html>")
        self.router.routes["theodorepayne.org"] = lambda url, params: page
        board = await self.cycle(["blooms"])
        reports = self.coordinator._sources["field_reports"].value or []
        carrizo = [report for report in reports if report.zone_id == "carrizo_plain"]
        self.assertEqual([report.observed_at for report in carrizo], [datetime(2026, 3, 1, 12, tzinfo=timezone.utc)])
        bloom = [item for item in self.coordinator.data["opportunities"] if item.phenomenon == "bloom_carrizo_plain"]
        self.assertTrue(bloom)
        self.assertFalse(any(item.extra["assessment"]["eligible"] for item in bloom))
        self.assertNotIn("bloom_carrizo_plain", [row["phenomenon"] for row in board["events"]])

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

    async def test_unused_sunrise_component_failure_keeps_a_valid_firefall(self):
        # R6: Firefall reads the valley and its sunset light path. A broken
        # sunrise probe in the same response must cost the sunrise input only.
        valley = ZONES_BY_ID["yosemite_valley"]["latitude"]
        self.router.forecast_edits[(valley, 2)] = lambda part: {"error": True, "reason": "bad probe"}
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertTrue(item.extra["assessment"]["eligible"], item.extra["assessment"]["blockers"])
        self.assertIsNotNone(item.extra.get("light_path_gate"))
        points = module.source_health.point_health(self.coordinator._weather_points, self.now)
        self.assertEqual(points["yosemite_valley:sunrise"], "failed")
        self.assertEqual(points["yosemite_valley"], "ok")
        self.assertEqual(points["yosemite_valley:sunset"], "ok")
        self.assertNotIn("degraded_required", item.extra)
        board = CantMissSensor(self.coordinator, self.entry).extra_state_attributes
        self.assertNotIn("weather:yosemite_valley:sunrise", [p["source"] for p in board["assessment"]["problems"]])
        self.assertIn("horsetail_firefall", [row["phenomenon"] for row in board["events"]])

    async def test_used_sunset_component_failure_is_reported(self):
        valley = ZONES_BY_ID["yosemite_valley"]["latitude"]
        self.router.forecast_edits[(valley, 1)] = lambda part: {"hourly": {"time": []}}
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertFalse(item.extra["assessment"]["eligible"])
        board = CantMissSensor(self.coordinator, self.entry).extra_state_attributes
        self.assertIn("weather:yosemite_valley:sunset", [p["source"] for p in board["assessment"]["problems"]])
        self.assertEqual(board["headline"], "Can't Miss assessment incomplete: required data unavailable.")

    async def test_unassessed_firefall_layers_are_an_incomplete_week_not_a_quiet_one(self):
        # R5: every one of these blocks Firefall. None of them is an answer
        # about the sky, so none of them may produce the quiet-week headline.
        valley = ZONES_BY_ID["yosemite_valley"]["latitude"]

        def layer(key, value=None, drop=False, shorten=False):
            def edit(part):
                block = part["hourly"]
                if drop:
                    block.pop(key)
                elif shorten:
                    block[key] = block[key][:10]
                else:
                    block[key] = [value] * len(block[key])
                return part
            return edit

        cases = {
            "upstream low missing": (1, layer("cloud_cover_low", drop=True)),
            "upstream mid missing": (1, layer("cloud_cover_mid", drop=True)),
            "upstream low null": (1, layer("cloud_cover_low", None)),
            "upstream mid NaN": (1, layer("cloud_cover_mid", float("nan"))),
            "upstream low infinite": (1, layer("cloud_cover_low", float("inf"))),
            "upstream low negative": (1, layer("cloud_cover_low", -1)),
            "upstream mid over 100": (1, layer("cloud_cover_mid", 101)),
            "upstream low short": (1, layer("cloud_cover_low", shorten=True)),
            "local cloud null": (0, layer("cloud_cover", None)),
        }
        for name, (index, edit) in cases.items():
            with self.subTest(name):
                self.coordinator._weather_points.clear()
                weather = self.coordinator._sources["weather"]
                weather.next_attempt, weather.fetched_at = None, None
                self.router.forecast_edits = {(valley, index): edit}
                item = await self.firefall_cycle(nps_api_key="test-only")
                assessment = item.extra["assessment"]
                self.assertFalse(assessment["eligible"])
                self.assertTrue(assessment["conditions_unassessed"])
                board = CantMissSensor(self.coordinator, self.entry).extra_state_attributes
                self.assertEqual(board["assessment"]["state"], "incomplete")
                self.assertIn("conditions:horsetail_firefall", [p["source"] for p in board["assessment"]["problems"]])
                self.assertEqual(board["headline"], "Can't Miss assessment incomplete: required data unavailable.")
                self.assertIn("horsetail_firefall", [row["phenomenon"] for row in board["held"]])

    async def test_valid_blocked_light_path_is_an_answer(self):
        valley = ZONES_BY_ID["yosemite_valley"]["latitude"]

        def blocked(part):
            for key in ("cloud_cover_low", "cloud_cover_mid"):
                part["hourly"][key] = [100] * len(part["hourly"][key])
            return part
        self.router.forecast_edits[(valley, 1)] = blocked
        item = await self.firefall_cycle(nps_api_key="test-only")
        self.assertFalse(item.extra["assessment"]["eligible"])
        self.assertEqual(item.extra["assessment"]["conditions_unassessed"], [])
        self.assertIn("cloud upstream blocks the sunset light", item.extra["assessment"]["blockers"])
        board = CantMissSensor(self.coordinator, self.entry).extra_state_attributes
        self.assertEqual(board["assessment"]["state"], "complete")
        self.assertEqual(board["headline"], "Nothing worth changing plans for this week.")

    def provider(self, valid_at):
        self.router.routes["sunsetwx.com/v1/login"] = lambda url, params: {"access_token": "t", "expires_in": 3600}
        self.router.routes["sunsetwx.com/v1/quality"] = lambda url, params: {"type": "FeatureCollection", "features": [
            {"properties": {"type": params["type"], "quality": "Great", "quality_percent": 95,
                            "valid_at": valid_at(params["type"]).isoformat(),
                            "last_updated": (self.now - timedelta(hours=1)).isoformat(), "source": "GFS"}}]}

    async def test_provider_prediction_for_another_event_does_not_cover_home(self):
        # R5: a current-model prediction four days past the next sunset
        # assesses nothing this week, so the failed home forecast still shows.
        self.router.forecast_failures.add(round(34.742, 3))
        self.provider(lambda kind: self.now + timedelta(days=4, hours=9))
        board = await self.cycle(["sunset"], sunsetwx_client_id="id", sunsetwx_client_secret="secret")
        self.assertEqual(self.coordinator.data["sources"]["sunsetwx"]["state"], "ok")
        self.assertEqual(board["assessment"]["state"], "incomplete")
        self.assertTrue(any(p["source"].startswith("sunset:") for p in board["assessment"]["problems"]))
        self.assertEqual(board["headline"], "Can't Miss assessment incomplete: required data unavailable.")

    async def test_provider_covers_exactly_the_events_it_predicts(self):
        self.router.forecast_failures.add(round(34.742, 3))
        home = self.coordinator.home_zone
        events = module.event_builder.home_sun_events(home, self.now)
        first = {label.lower(): moment for moment, _, label in events[::-1]}  # earliest of each kind wins
        self.provider(lambda kind: first[kind])
        board = await self.cycle(["sunset"], sunsetwx_client_id="id", sunsetwx_client_secret="secret")
        gaps = {p["source"] for p in board["assessment"]["problems"] if p["source"].startswith("sunset:")}
        self.assertNotIn(f"sunset:{first['sunset'].isoformat()}", gaps)
        self.assertNotIn(f"sunset:{first['sunrise'].isoformat()}", gaps)
        self.assertEqual(len(gaps), len(events) - 2, "later sunsets had no forecast at all")

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

    ROUTE_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "cant-miss-route-rows.json")

    async def routed_rows(self):
        """Current, recent and disputed routes through the real routing, gate and row builder."""
        eligibility = module.eligibility
        self.entry.options = {"google_api_key": "test-only", "max_drive_hours": 6}
        self.router.routes["googleapis.com"] = lambda url, params: Response(None, 500)
        items = {}
        for name, age, routed, estimate, latitude in (("current", timedelta(minutes=30), 2.0, 2.2, 35.2),
                                                      ("recent", timedelta(days=6), 5.8, 5.5, 35.4),
                                                      ("disputed", timedelta(days=6), 5.8, 7.0, 35.6)):
            item = module.event_builder.Opportunity(
                f"route-{name}", f"Milky Way core ({name} route)", "astronomy", "z", "Dark site",
                self.now + timedelta(hours=5), self.now + timedelta(hours=7), 95, "", estimate,
                latitude=latitude, longitude=-119.8, phenomenon="milky_way",
                extra={"evidence_state": "computed", "verification": "computed", "cloud_cover": 5.0,
                       "cloud_is_forecast": True})
            self.coordinator._routing_cache[self.coordinator._route_key(module._point(item))] = (
                SimpleNamespace(hours=routed, minutes=round(routed * 60), source="Routes API", in_traffic=True),
                self.now - age)
            items[name] = item
        await self.coordinator._apply_routing(self.router, self.now, list(items.values()))
        for item in items.values():
            eligibility.assess(item, self.now, max_drive_hours=6, alerts=[])
        return items

    async def test_old_route_cannot_alone_clear_a_trip_the_estimate_puts_over_the_limit(self):
        # R9: a six-day-old 5.8 h route under a 6 h cap, against a 7 h estimate.
        items = await self.routed_rows()
        disputed = items["disputed"].extra["assessment"]
        self.assertFalse(disputed["eligible"])
        self.assertTrue(disputed["held"])
        self.assertIn("route from 6 days ago; the distance estimate is 7.0 h", " ".join(disputed["held_reasons"]))
        self.assertTrue(items["recent"].extra["assessment"]["eligible"], "estimate agrees: the recent route may decide")
        self.assertTrue(items["current"].extra["assessment"]["eligible"])

    async def test_route_basis_reaches_the_card_payload(self):
        # The JS card test renders exactly these backend rows
        # (tests/fixtures/cant-miss-route-rows.json). Regenerate with
        # PE_WRITE_FIXTURES=1 when the row shape changes on purpose.
        items = await self.routed_rows()
        rows = [module.eligibility.cant_miss_row(items[name]) for name in ("current", "recent")]
        payload = json.loads(json.dumps({"generated": self.now.isoformat(), "rows": rows}, default=str))
        self.assertEqual([row["drive_basis"] for row in rows], ["current", "recent"])
        self.assertEqual(rows[1]["estimated_drive_hours"], 5.5)
        self.assertIn("route_fetched_at", rows[1])
        if os.environ.get("PE_WRITE_FIXTURES"):
            with open(self.ROUTE_FIXTURE, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=1, sort_keys=True)
                handle.write("\n")
        with open(self.ROUTE_FIXTURE, encoding="utf-8") as handle:
            self.assertEqual(json.load(handle), payload, "the card fixture no longer matches the backend")

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

    async def test_a_skip_survives_a_restart_through_the_store(self):
        # M2 with a real shutdown: a new coordinator reads the choice back
        # from Home Assistant's Store, not from the old object's memory.
        self.set_now(datetime(2026, 12, 31, 20, tzinfo=timezone.utc))
        await self.cycle(["rare_phenomena"])
        crane = next(item for item in self.coordinator.data["opportunities"]
                     if item.phenomenon == "sandhill_crane_flyin" and item.start <= self.now <= item.end)
        await self.coordinator.async_set_event_choice(event_id(crane), "skip")
        await self.coordinator.async_shutdown()
        await self.hass.async_block_till_done()
        self.coordinator = module.PhotographyEventsCoordinator(self.hass, self.entry)
        await self.coordinator.async_initialize()
        self.coordinator._cold_start = False
        self.set_now(datetime(2027, 1, 1, 9, tzinfo=timezone.utc))
        board = await self.cycle(["rare_phenomena"])
        self.assertTrue(self.coordinator.event_state.suppressed(event_id(crane)))
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

    async def test_legacy_entry_keeps_its_explicit_selection(self):
        # R10: a version-1 list cannot say whether Waves was left out by
        # default or on purpose, so it is never rewritten.
        legacy = [c for c in module.ALL_CATEGORIES if c != "waves"]
        updates = []
        hass = SimpleNamespace(config_entries=SimpleNamespace(
            async_update_entry=lambda target, **changes: updates.append(changes) or target.__dict__.update(changes)))
        for data, options in (({"enabled_categories": legacy}, {}), ({}, {"enabled_categories": legacy}),
                              ({"enabled_categories": []}, {}), ({}, {})):
            with self.subTest(data=data, options=options):
                entry = SimpleNamespace(version=1, data=dict(data), options=dict(options))
                self.assertTrue(await async_migrate_entry(hass, entry))
                self.assertEqual(entry.version, 2)
                self.assertEqual((entry.data, entry.options), (data, options), "stored choices unchanged")
        self.entry.data, self.entry.options = {"enabled_categories": legacy}, {}
        self.assertNotIn("waves", self.coordinator.enabled_categories)
        self.entry.data = {}
        self.assertIn("waves", self.coordinator.enabled_categories, "no stored list: current defaults")
        entry = SimpleNamespace(version=2, data={"enabled_categories": legacy}, options={})
        count = len(updates)
        self.assertTrue(await async_migrate_entry(hass, entry))
        self.assertEqual(len(updates), count, "a version-2 entry is not touched")

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
