"""0.16.1 foliage discoverability through real HA, HTTP parsing and the gate."""
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

import test_ha_pipeline as pipeline


@unittest.skipUnless(pipeline.HAS_HA, "Home Assistant is tested in the HA CI job")
class FoliageWatchingPipeline(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.f = pipeline.PipelineContracts()
        self.f.addCleanup = self.addCleanup
        await self.f.asyncSetUp()
        self.f.set_now(datetime(2026, 9, 27, 17, tzinfo=timezone.utc))

    async def asyncTearDown(self):
        await self.f.asyncTearDown()

    async def cycle(self, page, hours=6.66, categories=None, fail=False):
        f = self.f
        f.router.routes["californiafallcolor.com"] = lambda url, params: (
            pipeline.Response(None, 500) if fail else page)
        # A current cached Google result goes through production routing. It
        # avoids an unrelated network failure deciding this presentation test.
        from custom_components.photography_events import phenomena
        window = phenomena.WINDOWS_BY_KEY["aspen_tier1_high"]
        point = (window.latitude, window.longitude)
        f.coordinator._routing_cache[f.coordinator._route_key(point)] = (
            SimpleNamespace(hours=hours, minutes=round(hours * 60), source="Routes API", in_traffic=True), f.now)
        board = await f.cycle(["foliage"] if categories is None else categories,
                              google_api_key="synthetic", max_drive_hours=6)
        planner = [r for r in f.coordinator.data["opportunities"] if r.phenomenon == "aspen_tier1_high"
                   and r.extra.get("precision") == "peak"]
        return board, planner

    def watch(self, board):
        row = next((r for r in board["watch"] if r["phenomenon"] == "aspen_tier1_high"), None)
        self.assertIsNotNone(row, "The existing aspen window must remain discoverable in Watching")
        return row

    async def test_no_report_keeps_window_and_missing_confirmation_visible(self):
        board, planner = await self.cycle('<div class="entry-content"><p>No fall color reports posted.</p></div>')
        self.assertTrue(planner)
        self.assertEqual(planner[0].start.date().isoformat(), "2026-09-25")
        self.assertEqual(planner[0].end.date().isoformat(), "2026-10-05")
        self.assertNotIn("aspen_tier1_high", [r["phenomenon"] for r in board["events"]])
        self.assertIn("dated report", self.watch(board)["awaiting"])
        self.assertEqual(board["assessment"]["state"], "complete")
        self.assertFalse(self.watch(board)["eligible"])

    async def test_undated_report_is_context_not_confirmation(self):
        board, planner = await self.cycle('<div class="entry-content"><h3>Bishop Creek</h3><p>North Lake aspen near peak color, go now.</p></div>')
        watch = self.watch(board)
        self.assertEqual(planner[0].extra["evidence_state"], "reported_undated")
        self.assertFalse(watch["eligible"])
        self.assertEqual(watch["where"], "Bishop Creek: North Lake")
        self.assertAlmostEqual(watch["drive_hours"], 6.66, places=2)
        self.assertEqual(watch["behavior_evidence"], [])
        self.assertEqual(watch["unconfirmed_reports"][0]["source"], "California Fall Color")
        self.assertIsNone(watch["unconfirmed_reports"][0]["observed_at"])
        self.assertIn("North Lake", watch["unconfirmed_reports"][0]["text"])
        self.assertIn("beyond the 6 h Can't Miss drive limit", watch["blockers"])

    async def test_confirmed_but_distant_remains_in_planner_with_drive_reason(self):
        board, planner = await self.cycle('<div class="entry-content"><h3>Bishop Creek (Sept 25)</h3><p>North Lake aspen at peak color, go now.</p></div>')
        self.assertTrue(planner)
        row = planner[0].compact()
        self.assertEqual(row["evidence_state"], "behavior_confirmed")
        self.assertFalse(row["eligible"])
        self.assertIn("beyond the 6 h Can't Miss drive limit", row["blockers"])
        self.assertNotIn("aspen_tier1_high", [r["phenomenon"] for r in board["events"]])

    async def test_confirmed_inside_drive_limit_can_qualify(self):
        board, planner = await self.cycle('<div class="entry-content"><h3>Bishop Creek (Sept 25)</h3><p>North Lake aspen at peak color, go now.</p></div>', hours=5.0)
        self.assertTrue(planner[0].extra["assessment"]["eligible"], planner[0].extra["assessment"]["blockers"])
        self.assertIn("aspen_tier1_high", [r["phenomenon"] for r in board["events"]])

    async def test_disabled_foliage_has_no_rows_or_invented_category(self):
        board, planner = await self.cycle('<p>North Lake aspen at peak color (Sept 25).</p>', categories=["mammals"])
        self.assertEqual(planner, [])
        self.assertFalse(any(r["category"] == "foliage" for r in board["events"] + board["watch"]))
        self.assertFalse(any(r.category == "foliage" for r in self.f.coordinator.data["opportunities"]))

    async def test_source_failure_preserves_window_and_reports_unavailable_evidence(self):
        board, planner = await self.cycle("", fail=True)
        self.assertTrue(planner)
        watch = self.watch(board)
        self.assertFalse(watch["eligible"])
        self.assertIn("california_fall_color", watch["degraded_sources"])
        self.assertIn("California Fall Color", watch["source_health_note"])
        self.assertIn("dated report", watch["awaiting"])
        # The row can retain context, but the failed confirming source cannot
        # establish a quiet week. This is incomplete coverage, not unsafe access.
        self.assertEqual(board["assessment"]["state"], "incomplete")
        self.assertIn("california_fall_color", [p["source"] for p in board["assessment"]["problems"]])
        self.assertEqual(board["headline"], "Can't Miss assessment incomplete: required data unavailable.")
        self.assertEqual(watch["safety_state"], "safe")
        self.assertNotIn("aspen_tier1_high", [r["phenomenon"] for r in board["held"]])
