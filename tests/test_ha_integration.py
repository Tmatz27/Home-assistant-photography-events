"""Real HA contracts, isolated from the portable pure-module suite.

Run with Home Assistant installed in the dedicated CI job. Without HA only this
file skips; missing dependencies in an installed HA must fail, not hide tests.
All external I/O is fake. Store persistence uses a temporary configuration dir.
"""
import asyncio
import importlib.util
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

HAS_HA = importlib.util.find_spec("homeassistant") is not None
if HAS_HA:
    from homeassistant.core import HomeAssistant
    from custom_components.photography_events import coordinator as module
    from custom_components.photography_events import async_unload_entry
    from custom_components.photography_events.events import Opportunity
    from custom_components.photography_events.event_state import event_id
    from custom_components.photography_events.sensor import PlanningOutlookSensor, NextOpportunitySensor, BestSkyScoreSensor
    from custom_components.photography_events.binary_sensor import PhotographyActionOpportunity
    from custom_components.photography_events.calendar import PhotographyCalendar
    from custom_components.photography_events import source_health

NOW = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


class Response:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    async def json(self, **kwargs):
        return self.payload

    async def text(self):
        return self.payload


class Session:
    def __init__(self, *responses):
        self.request = AsyncMock(side_effect=responses)


@unittest.skipUnless(HAS_HA, "Home Assistant is tested in the separate HA CI job")
class HomeAssistantContracts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if os.name == "nt":
            # HA runs on Linux. Let Windows exercise the same JSON/atomic
            # writes, stubbing only a POSIX permission syscall absent here.
            permissions = patch("os.fchmod", create=True)
            permissions.start()
            self.addCleanup(permissions.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.hass = HomeAssistant(self.directory.name)
        self.hass.config.latitude, self.hass.config.longitude = 34.742, -120.5724
        self.entry = SimpleNamespace(entry_id="test_entry", data={}, options={"enabled_categories": ["astronomy"]})
        self.coordinator = module.PhotographyEventsCoordinator(self.hass, self.entry)
        self.session = Session()
        for target, value in (("async_get_clientsession", lambda hass: self.session),
                              ("ir.async_create_issue", Mock()), ("ir.async_delete_issue", Mock()),
                              ("dt_util.utcnow", lambda: NOW)):
            context = patch.object(module, target, value) if "." not in target else patch(f"{module.__name__}.{target}", value)
            context.start()
            self.addCleanup(context.stop)
        await self.coordinator.async_initialize()

    async def asyncTearDown(self):
        await self.coordinator.async_shutdown()
        await self.hass.async_stop(force=True)
        self.directory.cleanup()

    def opportunity(self, key="night", days=0):
        start = NOW + timedelta(days=days, hours=2)
        return Opportunity(key, "Milky Way core", "astronomy", "test", "Test location", start,
                           start + timedelta(hours=2), 95, "Calculated window", 1,
                           extra={"verification": "computed"}, roll=key)

    def fake_cycle(self, opportunities=None):
        self.coordinator._fetch_forecasts = AsyncMock(return_value={"test": {"local": {}, "upstream": {}}})
        self.coordinator._fetch_aurora = AsyncMock(return_value={"coordinates": []})
        self.coordinator._build = AsyncMock(return_value=opportunities or [])

    async def test_one_source_failure_preserves_cycle_and_marks_affected_event(self):
        self.fake_cycle([self.opportunity()])
        self.coordinator._fetch_forecasts.side_effect = ValueError("offline")
        data = await self.coordinator._async_update_data()
        self.assertEqual(data["sources"]["weather"]["state"], "failed")
        self.assertEqual(data["sources"]["aurora"]["state"], "ok")
        self.assertEqual(data["opportunities"][0].compact()["degraded_sources"], ["weather"])

    async def test_cycle_throttles_successful_sources(self):
        self.fake_cycle()
        await self.coordinator._async_update_data()
        await self.coordinator._async_update_data()
        self.coordinator._fetch_forecasts.assert_awaited_once()
        self.coordinator._fetch_aurora.assert_awaited_once()

    async def test_cached_failure_retries_on_backoff_and_retains_payload(self):
        source = self.coordinator._sources["field_reports"]
        source.succeed(NOW, ["cached"])
        fetch = AsyncMock(side_effect=ValueError("offline"))
        later = NOW + timedelta(days=1)
        await self.coordinator._refresh(source, later, fetch)
        await self.coordinator._refresh(source, later + timedelta(minutes=1), fetch)
        self.assertEqual(fetch.await_count, 1)
        await self.coordinator._refresh(source, later + timedelta(minutes=15), fetch)
        self.assertEqual(fetch.await_count, 2)
        self.assertEqual(source.value, ["cached"])
        self.assertEqual(source.fetched_at, NOW)

    async def test_partial_batch_retains_failed_part_and_publishes_new_part(self):
        self.coordinator._finish_batch("ebird", {"a": ["old a"], "b": ["old b"]}, [])
        with self.assertRaises(module.PartialFetchError) as result:
            self.coordinator._finish_batch("ebird", {"a": ["new a"]}, ["b"])
        self.assertEqual(result.exception.value, ["new a", "old b"])
        source = self.coordinator._sources["ebird"]
        await self.coordinator._refresh(source, NOW, AsyncMock(side_effect=result.exception))
        self.assertEqual(source.failures, 1)
        self.assertEqual(source.value, ["new a", "old b"])

    async def test_forecast_http_bundle_keeps_upstream_coordinates(self):
        parts = [{"hourly": {"time": [NOW.isoformat()], "cloud_cover": [v]}} for v in (10, 90, 40)]
        session = Session(Response(parts))
        zone = {"id": "test", "name": "Test", "latitude": 34.7, "longitude": -120.5}
        result = await self.coordinator._fetch_forecasts(session, [zone], NOW)
        self.assertEqual(result["test"]["local"], parts[0])
        self.assertEqual(result["test"]["upstream"], {"sunset": parts[1], "sunrise": parts[2]})
        self.assertEqual(len(session.request.call_args.kwargs["params"]["latitude"].split(",")), 3)

    async def test_build_passes_forecast_bundle_to_sunset_builder(self):
        local, upstream = {"hourly": {}}, {"sunset": {"hourly": {}}}
        zone = {"id": "test", "name": "Test", "latitude": 34.7, "longitude": -120.5}
        with patch.object(module.event_builder, "build_sunset_opportunities", return_value=[]) as build:
            await self.coordinator._build(NOW, [zone], {"test": {"local": local, "upstream": upstream}}, {}, {"sunset"})
        self.assertEqual(build.call_args.args[1], local)
        self.assertEqual(build.call_args.args[5], upstream)

    async def test_incomplete_forecast_response_is_failure(self):
        zone = {"id": "test", "name": "Test", "latitude": 34.7, "longitude": -120.5}
        with self.assertRaises(module.PartialFetchError):
            await self.coordinator._fetch_forecasts(Session(Response({"error": True})), [zone], NOW)

    async def test_cold_start_defers_hotlines_and_shutdown_cancels_task(self):
        self.entry.options = {"enabled_categories": ["blooms"]}
        self.coordinator._build = AsyncMock(return_value=[])
        self.coordinator._fetch_field_reports = AsyncMock(return_value=[])
        await self.coordinator._async_update_data()
        self.coordinator._fetch_field_reports.assert_not_awaited()
        self.assertIsNotNone(self.coordinator._deferred_task)
        await self.coordinator.async_shutdown()
        self.assertTrue(self.coordinator._deferred_task.done())
        self.assertTrue(self.coordinator._shutdown_requested)

    async def test_failed_hotline_is_named_and_other_hotline_is_not_refetched(self):
        self.entry.options = {"enabled_categories": ["blooms"]}
        self.coordinator._get_text = AsyncMock(side_effect=[None, '<main><h1>Wildflower report</h1><p>No flowers yet; too early.</p></main>'])
        with patch.object(module, "GROUP_STAGGER_SECONDS", 0):
            with self.assertRaises(module.PartialFetchError):
                await self.coordinator._fetch_field_reports(self.session, NOW)
        health = source_health.snapshot(self.coordinator._sources, self.coordinator._enabled_sources(), NOW)
        self.assertEqual(health["theodore_payne"]["state"], "failed")
        self.assertEqual(health["desertusa"]["state"], "ok")
        self.coordinator._get_text = AsyncMock(return_value='<main><h1>Wildflower report</h1><p>No flowers yet; too early.</p></main>')
        with patch.object(module, "GROUP_STAGGER_SECONDS", 0):
            await self.coordinator._fetch_field_reports(self.session, NOW + timedelta(minutes=15))
        self.coordinator._get_text.assert_awaited_once()

    async def test_routing_deduplicates_shared_viewpoints_and_retains_approximate_cache(self):
        self.entry.options["google_api_key"] = "test-only"
        items = [self.opportunity("a"), self.opportunity("b")]
        for item in items:
            item.latitude, item.longitude = 34.5, -120.5
        async def fetch(session, points, key):
            self.assertEqual(points, [(34.5,-120.5)])
            self.coordinator._routing_cache[points[0]] = SimpleNamespace(hours=1.25, minutes=75, source="test route", in_traffic=False)
            return 1
        self.coordinator._fetch_routing = AsyncMock(side_effect=fetch)
        await self.coordinator._apply_routing(self.session, NOW, items)
        await self.coordinator._apply_routing(self.session, NOW + timedelta(hours=1), items)
        self.coordinator._fetch_routing.assert_awaited_once()
        self.assertEqual([item.drive_hours for item in items], [1.25,1.25])

    async def test_empty_ebird_is_valid_but_auth_error_is_failure(self):
        self.entry.options["ebird_api_key"] = "test-only"
        with patch.object(module, "EBIRD_REGIONS", ["county"]):
            self.assertEqual(await self.coordinator._fetch_ebird(Session(Response([]))), [])
            with self.assertRaises(module.PartialFetchError):
                await self.coordinator._fetch_ebird(Session(Response({}, 401)))

    async def test_empty_inaturalist_is_valid_but_error_object_is_failure(self):
        with patch.object(module, "MARINE_TAXA", ["taxon"]), patch.object(module.phenomena_module, "corroboration_taxa", return_value=[]):
            self.assertEqual(await self.coordinator._fetch_inaturalist(Session(Response({"results": []})), NOW), [])
            with self.assertRaises(module.PartialFetchError):
                await self.coordinator._fetch_inaturalist(Session(Response({"error": "unavailable"})), NOW)

    async def test_follow_skip_survive_real_store_reload(self):
        item = self.opportunity()
        self.coordinator.data = {"opportunities": [item], "action_events": [item], "top_action": item}
        for choice in ("follow", "skip"):
            await self.coordinator.async_set_event_choice(event_id(item), choice)
            reloaded = module.PhotographyEventsCoordinator(self.hass, self.entry)
            await reloaded.async_initialize()
            self.assertEqual(reloaded.event_state.choice(event_id(item)), choice)
        self.assertIsNone(self.coordinator.data["top_action"])

    async def test_invalid_choice_does_not_change_persistent_preferences(self):
        self.coordinator.data = {"opportunities": []}
        with self.assertRaises(ValueError):
            await self.coordinator.async_set_event_choice("gone", "skip")
        self.assertEqual(self.coordinator.event_state.choices, {})

    async def test_failed_store_write_cannot_apply_an_unacknowledged_skip(self):
        item = self.opportunity()
        self.coordinator.data = {"opportunities": [item], "action_events": [item], "top_action": item}
        with patch.object(self.coordinator._store, "async_save", AsyncMock(side_effect=OSError("disk full"))):
            with self.assertRaises(OSError):
                await self.coordinator.async_set_event_choice(event_id(item), "skip")
        self.assertEqual(self.coordinator.event_state.choice(event_id(item)), "default")
        self.assertIs(self.coordinator.data["top_action"], item)

    async def test_failed_store_write_does_not_consume_a_future_event(self):
        self.fake_cycle([self.opportunity()])
        with patch.object(self.coordinator._store, "async_save", AsyncMock(side_effect=OSError("disk full"))):
            with self.assertRaises(OSError):
                await self.coordinator._async_update_data()
        self.assertEqual(self.coordinator.event_state.announced, {})
        await self.coordinator._async_update_data()
        self.assertIn("night", self.coordinator.event_state.announced)

    async def test_distant_outlook_cannot_emit_opportunity_event(self):
        self.fake_cycle([self.opportunity(days=10)])
        with patch.object(type(self.hass.bus), "async_fire") as fire:
            data = await self.coordinator._async_update_data()
        self.assertIsNone(data["top_action"])
        self.assertFalse(any(call.args[0] == "photography_events_opportunity" for call in fire.call_args_list))

    async def test_repairs_after_three_failures_and_recover_or_disable(self):
        source = self.coordinator._sources["weather"]
        for _ in range(3):
            source.fail(NOW, "offline")
        health = source_health.snapshot(self.coordinator._sources, {"weather"}, NOW)
        self.coordinator._update_repairs(health)
        self.assertEqual(module.ir.async_create_issue.call_args.args[2], "test_entry_weather")
        source.succeed(NOW, {})
        self.coordinator._update_repairs(source_health.snapshot(self.coordinator._sources, {"weather"}, NOW))
        module.ir.async_delete_issue.assert_any_call(self.hass, "photography_events", "test_entry_weather")
        source.fail(NOW, "offline")
        module.ir.async_create_issue.reset_mock()
        self.coordinator._update_repairs(source_health.snapshot(self.coordinator._sources, set(), NOW))
        module.ir.async_create_issue.assert_not_called()

    async def test_entities_publish_confidence_health_and_calendar_end(self):
        item = self.opportunity()
        item.extra.update(cloud_cover=40, cloud_is_forecast=False, cloud_confidence="outlook")
        self.coordinator.data = {"opportunities": [item], "top_action": item,
                                 "sources": {"weather": {"state": "failed"}}, "action_events": [item]}
        attributes = PlanningOutlookSensor(self.coordinator, self.entry).extra_state_attributes
        self.assertIs(attributes["events"][0]["cloud_is_forecast"], False)
        self.assertEqual(attributes["sources"]["weather"]["state"], "failed")
        self.assertTrue(PhotographyActionOpportunity(self.coordinator, self.entry).is_on)
        self.assertEqual(NextOpportunitySensor(self.coordinator, self.entry).native_value, item.title)
        self.assertEqual(BestSkyScoreSensor(self.coordinator, self.entry).native_value, 0)
        calendar = PhotographyCalendar(self.coordinator, self.entry)
        self.assertEqual(calendar.event.end, item.end)
        item.planning_only = True
        self.assertEqual(calendar.event.end, item.end.date() + timedelta(days=1))
        self.assertEqual(len(await calendar.async_get_events(self.hass, NOW, NOW + timedelta(days=1))), 1)

    async def test_zero_coordinate_is_a_valid_home_location(self):
        self.hass.config.latitude, self.hass.config.longitude = 0, 0
        self.assertEqual(self.coordinator.home, (0, 0))

    async def test_cancelled_http_request_propagates(self):
        session = Session(asyncio.CancelledError())
        with self.assertRaises(asyncio.CancelledError):
            await self.coordinator._get_json(session, "https://example.test/")

    async def test_unload_cleans_coordinator_and_services(self):
        self.hass.data["photography_events"] = {self.entry.entry_id: self.coordinator}
        with patch.object(self.hass, "config_entries", SimpleNamespace(async_unload_platforms=AsyncMock(return_value=True))):
            self.assertTrue(await async_unload_entry(self.hass, self.entry))
        self.assertEqual(self.hass.data["photography_events"], {})
