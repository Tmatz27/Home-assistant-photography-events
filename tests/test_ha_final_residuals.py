"""Final R1/R2/R3/R5 corrections: synthetic HTTP through real HA and final board.

Reuse the existing HA fixture without inheriting/re-running its test methods.
These expectations come from the third review, before the implementation.
"""
import unittest
from datetime import datetime, timedelta, timezone

import test_ha_pipeline as pipeline


@unittest.skipUnless(pipeline.HAS_HA, "Home Assistant is tested in the HA CI job")
class FinalResidualPipeline(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.f = pipeline.PipelineContracts()
        # This fixture is composed, not run by unittest. Register its patches
        # with our live runner so they cannot leak into later HA test classes.
        self.f.addCleanup = self.addCleanup
        await self.f.asyncSetUp()

    async def asyncTearDown(self):
        await self.f.asyncTearDown()

    def refetch(self, *names):
        for name in names:
            source = self.f.coordinator._sources[name]
            source.fetched_at = source.next_attempt = None

    def assert_incomplete(self, board, phenomenon):
        self.assertEqual(board["assessment"]["state"], "incomplete")
        self.assertNotIn(phenomenon, [r["phenomenon"] for r in board["events"]])
        self.assertNotEqual(board["headline"], "Nothing worth changing plans for this week.")

    async def test_nps_unknown_semantics_never_clear_firefall(self):
        f = self.f
        record = {"id": "review", "parkCode": "yose", "title": "Yosemite Valley closed", "category": "Park Closure"}
        for edit in ({"category": "UnexpectedCategory"}, {"parkCode": "????"}, {"parkCode": "zzzz"}, {"id": True}):
            with self.subTest(edit=edit):
                self.refetch("park_alerts")
                f.router.routes["developer.nps.gov"] = lambda u, p, edit=edit: {"total": "1", "data": [{**record, **edit}]}
                item = await f.firefall_cycle(nps_api_key="synthetic")
                self.assertEqual(item.extra["access_state"], "unknown")
                self.assert_incomplete(f.coordinator.data["cant_miss"], "horsetail_firefall")
                self.assertTrue(any(r["phenomenon"] == "horsetail_firefall" for r in f.coordinator.data["cant_miss"]["held"]))

    async def test_nps_valid_empty_information_and_closure_controls(self):
        f = self.f
        for category, access, eligible in ((None, "open", True), ("Information", "open", True),
                                           ("Caution", "open", True), ("Park Closure", "closed", False), ("Danger", "closed", False)):
            with self.subTest(category=category):
                self.refetch("park_alerts")
                data = [] if category is None else [{"id": "review", "parkCode": "yose", "title": "Yosemite Valley closed", "category": category}]
                f.router.routes["developer.nps.gov"] = lambda u, p, data=data: {"total": str(len(data)), "data": data}
                item = await f.firefall_cycle(nps_api_key="synthetic")
                self.assertEqual(item.extra["access_state"], access)
                self.assertEqual(item.extra["assessment"]["eligible"], eligible)
                self.assertEqual(f.coordinator.data["cant_miss"]["assessment"]["state"], "complete")

    def warning(self, same, geometry=None):
        return {"type": "Feature", "geometry": geometry, "properties": {
            "event": "High Wind Warning", "geocode": {"SAME": same},
            "expires": (self.f.now + timedelta(hours=12)).isoformat()}}

    async def test_nws_unresolvable_geography_is_not_safe(self):
        f = self.f
        f.set_now(datetime(2026, 12, 28, 18, tzinfo=timezone.utc))
        cases = [self.warning([code]) for code in ("106079", "906079", "999999", "006000", "006002", "006117")]
        cases += [self.warning([], {"type": "Polygon", "coordinates": [ring]}) for ring in (
            [[-121.2, 35.6]] * 4,
            [[-121, 35], [-120, 36], [-119, 37], [-121, 35]],
            [[False, True], [False, 2], [3, 2], [False, True]],
            [["-121", 35], [-120, 35], [-120, 36], ["-121", 35]],
            [[-121, 35], [-120, 35], [-120, 36]],
        )]
        for feature in cases:
            with self.subTest(feature=feature):
                self.refetch("surf_alerts")
                f.router.routes["api.weather.gov"] = lambda u, p, feature=feature: {"type": "FeatureCollection", "features": [feature]}
                board = await f.cycle(["mammals"])
                self.assert_incomplete(board, "elephant_seal_battles")
                held = next(r for r in board["held"] if r["phenomenon"] == "elephant_seal_battles")
                self.assertIn("Safety not fully checked", held["summary"])
                self.assertIn("1 unreadable alert(s)", held["summary"])
                row = next(r for r in f.coordinator.data["opportunities"] if r.phenomenon == "elephant_seal_battles"
                           and r.extra.get("precision") == "peak")
                self.assertEqual(row.extra["assessment"]["safety_state"], "unknown")

    async def test_nws_usable_county_polygon_and_mixed_collection_still_block(self):
        f = self.f
        f.set_now(datetime(2026, 12, 28, 18, tzinfo=timezone.utc))
        county = self.warning(["006079"])
        polygon = self.warning([], {"type": "Polygon", "coordinates": [[[-122, 35], [-120, 35], [-120, 36], [-122, 36], [-122, 35]]]})
        for features, complete in (([county], True), ([polygon], True), ([county, self.warning(["999999"])], False)):
            with self.subTest(features=features):
                self.refetch("surf_alerts")
                f.router.routes["api.weather.gov"] = lambda u, p, features=features: {"type": "FeatureCollection", "features": features}
                board = await f.cycle(["mammals"])
                self.assertNotIn("elephant_seal_battles", [r["phenomenon"] for r in board["events"]])
                row = next(r for r in f.coordinator.data["opportunities"] if r.phenomenon == "elephant_seal_battles" and r.extra.get("precision") == "peak")
                self.assertEqual(row.extra["assessment"]["safety_state"], "unsafe")
                self.assertEqual(board["assessment"]["state"], "complete" if complete else "incomplete")

    async def test_ambiguous_humpback_grammar_and_context_do_not_confirm(self):
        f = self.f
        cases = [
            ("Whale report", "Dolphins beside humpbacks were lunge feeding at Avila today."),
            ("Whale report", "Humpbacks beside dolphins were lunge feeding at Avila today."),
            ("Whale report", "Avila today. Pismo today. Humpbacks lunge feeding."),
            ("Trip cancelled at Avila today", "Humpbacks lunge feeding."),
            ("Whale report", "Humpbacks lunge feeding and dolphins passed Avila today."),
            ("Whale report", "Dolphins passed Avila today and humpbacks lunge feeding."),
        ]
        for subject, body in cases:
            with self.subTest(body=body, subject=subject):
                f.coordinator._ingested_reports = pipeline.parse_email_report(subject, body, "Independent", "marine", None, f.now)
                board = await f.cycle(["marine"])
                self.assertNotIn("humpback_lunge_feeding", [r["phenomenon"] for r in board["events"]])
                self.assertFalse(any(r.extra.get("evidence_state") == "behavior_confirmed" for r in f.coordinator.data["opportunities"] if r.phenomenon == "humpback_lunge_feeding"))

    async def test_other_animals_feeding_do_not_promote_one_condor(self):
        f = self.f
        f.router.routes["api.ebird.org"] = lambda u, p: [{"speciesCode": "calcon", "comName": "California Condor",
            "sciName": "Gymnogyps californianus", "locName": "Pinnacles", "lat": 36.487, "lng": -121.195,
            "howMany": 1, "obsDt": (f.now - timedelta(hours=2)).astimezone(pipeline.dt_util.DEFAULT_TIME_ZONE).strftime("%Y-%m-%d %H:%M"),
            "subId": "review", "obsValid": True}] if "calcon" in u else []
        for body in ("Ravens beside condors were feeding at Pinnacles today.",
                     "Condors beside ravens were feeding at Pinnacles today.",
                     "Condors at Pinnacles today and ground squirrels were feeding."):
            with self.subTest(body=body):
                f.coordinator._ingested_reports = pipeline.parse_email_report("Bird report", body, "Independent", "birds", None, f.now)
                board = await f.cycle(["birds"], ebird_api_key="synthetic")
                self.assertNotIn("condor_activity", [r["phenomenon"] for r in board["events"]])
                self.assertEqual(board["birds"]["spectacle"], [])

    async def snow_cycle(self, edit):
        f = self.f
        f.set_now(datetime(2027, 2, 16, 18, tzinfo=timezone.utc))
        f.coordinator._ingested_reports = pipeline.parse_email_report("Yosemite today",
            "Fresh snow on the Yosemite Valley floor this morning.", "Independent", "rare_phenomena", None, f.now)
        f.router.forecast_edits[(37.7456, 0)] = edit
        return await f.cycle(["rare_phenomena"], nps_api_key="synthetic")

    async def test_duplicate_snow_hours_are_not_48_hours_of_coverage(self):
        def duplicate(part):
            for key, values in part["hourly"].items():
                part["hourly"][key] = [values[0]] * 49
            part["hourly"]["time"] = [self.f.now.isoformat()] * 49
            part["hourly"]["cloud_cover"] = [100] * 49
            return part
        board = await self.snow_cycle(duplicate)
        self.assert_incomplete(board, "fresh_snow_clearing")

    async def test_snow_missing_future_hours_is_unassessed(self):
        def short(part):
            for key, values in part["hourly"].items():
                part["hourly"][key] = values[:15]
            part["hourly"]["cloud_cover"] = [100] * 15
            return part
        board = await self.snow_cycle(short)
        self.assert_incomplete(board, "fresh_snow_clearing")

    async def test_snow_complete_bad_forecast_is_an_answer(self):
        def cloudy(part):
            part["hourly"]["cloud_cover"] = [100] * len(part["hourly"]["time"])
            return part
        board = await self.snow_cycle(cloudy)
        self.assertEqual(board["assessment"]["state"], "complete")
        self.assertNotIn("fresh_snow_clearing", [r["phenomenon"] for r in board["events"]])

    async def test_snow_complete_clear_forecast_still_qualifies(self):
        board = await self.snow_cycle(lambda part: part)
        self.assertIn("fresh_snow_clearing", [r["phenomenon"] for r in board["events"]])
        self.assertEqual(board["assessment"]["state"], "complete")

    async def astronomy_cycle(self, transform=None):
        f = self.f
        f.set_now(datetime(2026, 8, 12, 17, tzinfo=timezone.utc))
        if transform:
            base = f.router.forecast
            def changed(url, params):
                parts = base(url, params)
                for part in parts:
                    transform(part["hourly"])
                return parts
            f.router.routes["api.open-meteo.com"] = changed
        return await f.cycle(["astronomy"])

    async def test_fresh_download_with_past_axis_cannot_clear_perseids(self):
        def past(hourly):
            hourly["time"] = [(datetime.fromisoformat(t) - timedelta(days=30)).isoformat() for t in hourly["time"]]
        board = await self.astronomy_cycle(past)
        self.assert_incomplete(board, "meteor_major")
        rows = [r for r in self.f.coordinator.data["opportunities"] if r.phenomenon == "meteor_major" and r.start < self.f.now + timedelta(days=7)]
        self.assertTrue(rows)
        self.assertTrue(all(r.extra.get("conditions_unassessed") for r in rows))

    async def test_night_gap_cannot_be_replaced_by_neighboring_days(self):
        def gap(hourly):
            indices = [i for i, t in enumerate(hourly["time"]) if not self.f.now <= datetime.fromisoformat(t) < self.f.now + timedelta(days=2)]
            for key, values in hourly.items():
                hourly[key] = [values[i] for i in indices]
        self.assert_incomplete(await self.astronomy_cycle(gap), "meteor_major")

    async def test_invalid_and_reversed_astronomy_axes_are_incomplete(self):
        for reversed_axis in (False, True):
            with self.subTest(reversed_axis=reversed_axis):
                self.refetch("weather")
                def broken(hourly):
                    if reversed_axis:
                        hourly["time"] = hourly["time"][::-1]
                    else:
                        hourly["time"][20] = "not-a-timestamp"
                self.assert_incomplete(await self.astronomy_cycle(broken), "meteor_major")

    async def test_near_term_full_moon_with_past_axis_is_held(self):
        f = self.f
        f.set_now(datetime(2026, 12, 23, 17, tzinfo=timezone.utc))
        base = f.router.forecast
        def old_axis(url, params):
            parts = base(url, params)
            for part in parts:
                part["hourly"]["time"] = [(datetime.fromisoformat(t) - timedelta(days=30)).isoformat()
                                          for t in part["hourly"]["time"]]
            return parts
        f.router.routes["api.open-meteo.com"] = old_axis
        board = await f.cycle(["astronomy"])
        rows = [r for r in f.coordinator.data["opportunities"] if r.phenomenon == "full_moon_closest"
                and r.start < f.now + timedelta(days=7)]
        self.assertTrue(rows)
        self.assertTrue(all(r.extra.get("conditions_unassessed") for r in rows))
        self.assert_incomplete(board, "full_moon_closest")

    async def test_astronomy_complete_clear_forecast_qualifies(self):
        board = await self.astronomy_cycle()
        self.assertIn("meteor_major", [r["phenomenon"] for r in board["events"]])
        self.assertEqual(board["assessment"]["state"], "complete")

    async def test_astronomy_complete_cloudy_forecast_is_an_answer(self):
        def cloudy(hourly):
            hourly["cloud_cover"] = [100] * len(hourly["time"])
        board = await self.astronomy_cycle(cloudy)
        self.assertEqual(board["assessment"]["state"], "complete")
        self.assertNotIn("meteor_major", [r["phenomenon"] for r in board["events"]])

    async def test_future_planner_dates_do_not_require_operational_weather(self):
        f = self.f
        board = await self.astronomy_cycle()
        later = [r for r in f.coordinator.data["opportunities"] if r.phenomenon == "milky_way" and r.start > f.now + timedelta(days=16)]
        self.assertTrue(later)
        self.assertTrue(all(not r.extra.get("conditions_unassessed") for r in later))
        self.assertEqual(board["assessment"]["state"], "complete")
