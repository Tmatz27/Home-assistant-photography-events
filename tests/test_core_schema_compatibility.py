"""Pinned schema 0009 route responses through the shipped HA boundaries."""
import copy
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import test_integration
test_integration._load_package()
from photography_events.core_client import (PhotographyEventsCoreClient, CoreAssessment, CoreVersionError,
                                            CoreProtocolError)
from photography_events.core_bridge import CoreBridge
from photography_events.projection import DestinationPolicy, InvalidProjection, sanitize_envelope, timestamp, validate_envelope
from test_core_client import Session, Response
from v17b_fixtures import NOW, payload

CAPTURE = json.loads((Path(__file__).parent / "fixtures/core-schema0009.json").read_text(encoding="utf-8"))
RESPONSES = CAPTURE["responses"]


class CoreSchemaCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    def client(self, *responses):
        session = Session(*(Response(r) for r in responses))
        return PhotographyEventsCoreClient(session, "http://core.invalid", "PRIVATE_TEST_TOKEN"), session

    async def test_both_explicit_schemas_validate_all_normal_endpoints(self):
        for schema in ("0008", "0009"):
            with self.subTest(schema=schema):
                data = [{**copy.deepcopy(RESPONSES[k]), "schema_version": schema} for k in ("health", "opportunities", "sources")]
                client, session = self.client(*data)
                self.assertEqual((await client.health()).schema_version, schema)
                assessment = await client.opportunities()
                self.assertEqual(assessment.payload["schema_version"], schema)
                self.assertEqual(assessment.items[0].occurrence_key, "tule_elk_rut-2026-09-15")
                self.assertEqual(len((await client.source_health())["items"]), 2)
                safe = sanitize_envelope(assessment.payload, DestinationPolicy.load())
                self.assertEqual(safe["items"][0]["location"]["policy"], "withheld")
                self.assertFalse(safe["items"][0]["eligibility"])
                self.assertNotIn("PRIVATE_TEST_TOKEN", repr(assessment) + json.dumps(safe))
                self.assertEqual(len(session.requests), 3)
                for _, options in session.requests:
                    self.assertEqual(options["headers"]["Authorization"], "Bearer PRIVATE_TEST_TOKEN")
                    self.assertFalse(options["allow_redirects"])

    async def test_captured_0009_empty_and_incomplete_keep_their_meaning(self):
        for key, state in (("empty", "complete"), ("incomplete", "incomplete")):
            result = CoreAssessment.parse(RESPONSES[key])
            self.assertEqual(result.payload["assessment_state"], state)
            self.assertEqual(result.payload["items"], [])
            self.assertEqual(validate_envelope(result.payload)["schema_version"], "0009")

    async def test_unverified_schemas_and_api_versions_fail_at_every_endpoint(self):
        changes = [{"schema_version": value} for value in ("0007", "0010", "9999", "9", "0009 ", 9, None, [], {})]
        changes += [{"api_version": value} for value in ("v2", "v1.1", None)]
        changes += [{"core_version": "0.2.0"}]
        for change in changes:
            for key, method in (("health", "health"), ("opportunities", "opportunities"), ("sources", "source_health")):
                with self.subTest(change=change, endpoint=key):
                    client, _ = self.client({**RESPONSES[key], **change})
                    with self.assertRaises(CoreVersionError) as caught:
                        await getattr(client, method)()
                    self.assertNotIn("PRIVATE_TEST_TOKEN", str(caught.exception))
            with self.assertRaises(InvalidProjection):
                validate_envelope({**RESPONSES["opportunities"], **change})

    async def test_0009_does_not_relax_normal_response_or_row_validation(self):
        for change in (lambda d: d.update(mode="shadow"), lambda d: d.update(preview_opportunities=[]),
                       lambda d: d["items"][0].update(eligibility="true"),
                       lambda d: d["items"][0].update(occurrence_key="private-observer-id"),
                       lambda d: d["items"][0].update(valid_until="not-a-time")):
            data = copy.deepcopy(RESPONSES["opportunities"])
            change(data)
            with self.assertRaises(CoreProtocolError):
                CoreAssessment.parse(data)
        source = copy.deepcopy(RESPONSES["sources"])
        source["items"][0]["state"] = "invented"
        client, _ = self.client(source)
        with self.assertRaises(CoreProtocolError):
            await client.source_health()

    async def test_schema_upgrade_reconnect_and_cache_restart_keep_original_clocks(self):
        data8 = payload()
        data9 = {**copy.deepcopy(data8), "schema_version": "0009"}
        health = RESPONSES["health"]
        sources = {**RESPONSES["sources"], "generated_at": NOW.isoformat()}
        client, _ = self.client({**health, "schema_version": "0008"}, data8, {**sources, "schema_version": "0008"},
                                health, data9, sources)
        store = SimpleNamespace(async_save=AsyncMock())
        bridge = CoreBridge(client, store, lambda: NOW, namespace="same-origin-and-token")
        await bridge.refresh()
        self.assertEqual(bridge.payload["schema_version"], "0008")
        await bridge.refresh()
        self.assertEqual(bridge.availability, "online")
        self.assertEqual(bridge.payload["schema_version"], "0009")
        saved = store.async_save.call_args.args[0]
        restored = CoreBridge(client, SimpleNamespace(async_load=AsyncMock(return_value=saved)),
                              lambda: NOW + timedelta(minutes=15), namespace="same-origin-and-token")
        await restored.initialize()
        self.assertEqual(restored.cached["schema_version"], "0009")
        self.assertEqual(timestamp(saved["fetched_at"]), NOW)
        self.assertEqual(saved["payload"]["data_as_of"], data9["data_as_of"])
        client, _ = self.client({**health, "schema_version": "0010"})
        bridge.client = client
        await bridge.refresh()
        self.assertEqual(bridge.availability, "incompatible")
        self.assertIsNone(bridge.payload)
        self.assertIsNone(bridge.cached)

    async def test_version_error_copy_is_consistent_for_setup_and_repair(self):
        root = Path(__file__).resolve().parents[1] / "custom_components/photography_events"
        for name in ("strings.json", "translations/en.json"):
            strings = json.loads((root / name).read_text(encoding="utf-8"))
            message = strings["config"]["error"]["unsupported_api_version"]
            self.assertIn("v1", message)
            self.assertIn("0008 or 0009", message)
            self.assertEqual(message, strings["issues"]["core_connection_required"]["fix_flow"]["error"]["unsupported_api_version"])
