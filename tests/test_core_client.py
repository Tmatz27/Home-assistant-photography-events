"""Portable async bridge contracts; no HA runtime or live Core required."""
import asyncio
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import test_integration  # Registers the portable photography_events package.
from photography_events.core_client import (
    PhotographyEventsCoreClient, CoreError, CoreAuthenticationError, CoreVersionError,
    CoreNotReady, CoreProtocolError, CoreAssessment,
)
from photography_events.core_bridge import CoreBridge

NOW = datetime(2026, 9, 27, 17, tzinfo=timezone.utc)
PAYLOAD = json.loads((Path(__file__).parent / "fixtures/core-v1.json").read_text(encoding="utf-8"))
HEALTH = {"core_version": "0.1.0-dev", "api_version": "v1", "schema_version": "0001", "status": "ready"}


class Response:
    def __init__(self, data, status=200, delay=0):
        self.data, self.status, self.delay, self.content = data, status, delay, self

    async def __aenter__(self):
        await asyncio.sleep(self.delay)
        return self

    async def __aexit__(self, *args):
        pass

    async def iter_chunked(self, size):
        yield json.dumps(self.data).encode()


class Session:
    def __init__(self, *responses):
        self.responses, self.requests = list(responses), []

    def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class CoreClientContracts(unittest.IsolatedAsyncioTestCase):
    def client(self, *responses, timeout=0.2):
        session = Session(*responses)
        return PhotographyEventsCoreClient(session, "http://core.lan:8099", "secret-token", timeout), session

    async def test_async_health_and_query(self):
        client, session = self.client(Response(HEALTH), Response(PAYLOAD))
        self.assertEqual((await client.health()).api_version, "v1")
        result = await client.opportunities(presentation="cant_miss", category="mammals")
        self.assertEqual(result.items[0].occurrence_key, "tule_elk_rut-2026-09-15")
        self.assertFalse(session.requests[0][1]["allow_redirects"])
        self.assertEqual(session.requests[0][1]["headers"]["Authorization"], "Bearer secret-token")
        self.assertNotIn("secret-token", repr(result))

    async def test_timeout_does_not_block_loop(self):
        client, _ = self.client(Response(HEALTH, delay=10), timeout=0.03)
        ticks = []
        async def heartbeat():
            for _ in range(3):
                await asyncio.sleep(0.003)
                ticks.append(True)
        task = asyncio.create_task(heartbeat())
        with self.assertRaises(CoreError):
            await client.health()
        await task
        self.assertEqual(len(ticks), 3)

    async def test_authentication_failure(self):
        client, _ = self.client(Response({}, 401))
        with self.assertRaises(CoreAuthenticationError):
            await client.health()

    async def test_unsupported_version(self):
        client, _ = self.client(Response({**HEALTH, "api_version": "v2"}))
        with self.assertRaises(CoreVersionError):
            await client.health()

    async def test_core_unavailable(self):
        client, _ = self.client(OSError("internal details must not escape"))
        with self.assertRaises(CoreError) as caught:
            await client.health()
        self.assertNotIn("internal details", str(caught.exception))

    async def test_database_readiness_failure(self):
        client, _ = self.client(Response({}, 503))
        with self.assertRaises(CoreNotReady):
            await client.health()

    async def test_redirect_not_followed(self):
        client, _ = self.client(Response({}, 302))
        with self.assertRaises(CoreError):
            await client.health()

    async def test_rich_payload_is_typed(self):
        invalid = copy.deepcopy(PAYLOAD)
        invalid["items"][0]["eligibility"] = "yes"
        with self.assertRaises(CoreProtocolError):
            CoreAssessment.parse(invalid)

    async def test_additive_fields_ignored_including_nested_metadata(self):
        data = copy.deepcopy(PAYLOAD)
        data["token"] = "secret"
        data["items"][0]["location"]["exact_geometry"] = "private"
        parsed = CoreAssessment.parse(data)
        self.assertNotIn("secret", json.dumps(parsed.payload))
        self.assertNotIn("exact_geometry", json.dumps(parsed.payload))

    async def test_success_persists_and_restart_offline_is_stale(self):
        client, _ = self.client(Response(HEALTH), Response(PAYLOAD))
        store = type("Store", (), {"async_save": AsyncMock(), "async_load": AsyncMock(return_value=None)})()
        bridge = CoreBridge(client, store, lambda: NOW)
        self.assertFalse((await bridge.refresh())["stale"])
        saved = store.async_save.call_args.args[0]
        self.assertNotIn("secret-token", json.dumps(saved))
        offline, _ = self.client(OSError())
        store.async_load.return_value = saved
        restarted = CoreBridge(offline, store, lambda: NOW + timedelta(hours=1))
        await restarted.initialize()
        result = await restarted.refresh()
        self.assertTrue(result["stale"])
        self.assertEqual(result["assessment_state"], "incomplete")
        self.assertFalse(result["items"][0]["eligibility"])
        self.assertTrue(result["items"][0]["held"])
        self.assertTrue(saved["payload"]["items"][0]["eligibility"], "fallback must not mutate the saved success")

    async def test_expired_cache_is_not_a_quiet_week(self):
        client, _ = self.client(OSError())
        store = type("Store", (), {"async_load": AsyncMock(return_value={"saved_at": NOW.isoformat(), "payload": PAYLOAD})})()
        bridge = CoreBridge(client, store, lambda: NOW + timedelta(days=8))
        await bridge.initialize()
        result = await bridge.refresh()
        self.assertEqual(result["items"], [])
        self.assertEqual(result["assessment_state"], "incomplete")
        self.assertIn("STALE", result["status"])

    async def test_invalid_saved_payload_does_not_load(self):
        client, _ = self.client(OSError())
        store = type("Store", (), {"async_load": AsyncMock(return_value={"payload": {}})})()
        bridge = CoreBridge(client, store)
        await bridge.initialize()
        self.assertIsNone(bridge.cached)

    async def test_incomplete_response_preserves_last_complete_cache(self):
        incomplete = {**PAYLOAD, "assessment_state": "incomplete", "items": []}
        client, _ = self.client(Response(HEALTH), Response(incomplete), OSError())
        store = type("Store", (), {"async_load": AsyncMock(return_value={"saved_at": NOW.isoformat(), "payload": PAYLOAD}),
                                  "async_save": AsyncMock()})()
        bridge = CoreBridge(client, store, lambda: NOW)
        await bridge.initialize()
        self.assertEqual((await bridge.refresh())["items"], [])
        store.async_save.assert_not_called()
        self.assertEqual(len((await bridge.refresh())["items"]), 1)

