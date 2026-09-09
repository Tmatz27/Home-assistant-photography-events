"""Portable health/evidence regressions; no Home Assistant import."""
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from test_integration import _load_package

_load_package()
from photography_events import source_health, field_reports
from photography_events.throttle import Source
from photography_events.phenomena import EVIDENCE_STATIC

NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)


class SourceHealthTests(unittest.TestCase):
    def test_retry_after_cached_failure_obeys_backoff(self):
        source = Source("Daily", 1440)
        source.succeed(NOW, [1])
        source.fail(NOW + timedelta(minutes=1), "failed")
        self.assertFalse(source.due(NOW + timedelta(minutes=15)))
        self.assertTrue(source.due(NOW + timedelta(minutes=16)))
        self.assertEqual(source.value, [1])

    def test_disabled_and_not_yet_fetched_are_not_outages(self):
        sources = {"weather": Source("Weather", 60), "ebird": Source("eBird", 60)}
        states = source_health.snapshot(sources, {"weather"}, NOW)
        self.assertEqual(states["weather"]["state"], "waiting")
        self.assertEqual(states["ebird"]["state"], "disabled")

    def test_stale_success_is_visible_without_a_reported_exception(self):
        source = Source("Weather", 30)
        source.succeed(NOW - timedelta(hours=4), {})
        health = source_health.snapshot({"weather": source}, {"weather"}, NOW)
        self.assertEqual(health["weather"]["state"], "stale")

    def test_source_failure_cannot_change_evidence_or_score(self):
        item = SimpleNamespace(category="astronomy", key="milky-way", extra={"verification": "computed"}, score=95)
        health = {"weather": {"state": "failed", "name": "Weather", "impact": "Cloud unavailable."}}
        source_health.annotate([item], health)
        self.assertEqual(item.extra["verification"], "computed")
        self.assertEqual(item.score, 95)
        self.assertEqual(item.extra["degraded_sources"], ["weather"])
        health["weather"]["state"] = "ok"
        source_health.annotate([item], health)
        self.assertNotIn("degraded_sources", item.extra)

    def test_static_species_does_not_claim_a_feed_can_confirm_it(self):
        item = SimpleNamespace(category="mammals", key="bighorn", extra={"evidence": EVIDENCE_STATIC})
        self.assertEqual(source_health.dependencies(item), set())

    def test_legitimate_quiet_hotline_page_is_valid_empty_data(self):
        html = '<main><h1>Wildflower report</h1><p>No flowers yet; it is too early this season.</p></main>'
        self.assertEqual(field_reports.checked_report(html, field_reports.REPORT_SOURCES[0], NOW), [])

    def test_hotline_layout_failure_and_challenge_are_not_empty_success(self):
        for html in ('<body>Maintenance</body>', '<main><p>Verify you are human to view wildflowers</p></main>', None):
            with self.subTest(html=html), self.assertRaises(ValueError):
                field_reports.checked_report(html, field_reports.REPORT_SOURCES[0], NOW)
