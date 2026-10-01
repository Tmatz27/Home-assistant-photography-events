"""Real HA Store restart test for the optional Core scaffold."""
import importlib.util
import os
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from test_core_client import PAYLOAD, NOW

HAS_HA = importlib.util.find_spec("homeassistant") is not None
if HAS_HA:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.storage import Store
    from custom_components.photography_events.core_bridge import CoreBridge
    from custom_components.photography_events.core_client import CoreAssessment, CoreError


@unittest.skipUnless(HAS_HA, "Real HA Store requires Home Assistant")
class CoreStoreContracts(unittest.IsolatedAsyncioTestCase):
    async def test_real_store_survives_restart_offline(self):
        if os.name == "nt":
            permissions = patch("os.fchmod", create=True)
            permissions.start()
            self.addCleanup(permissions.stop)
        with tempfile.TemporaryDirectory() as directory:
            hass = HomeAssistant(directory)
            self.addAsyncCleanup(hass.async_stop, force=True)
            client = type("Client", (), {"health": AsyncMock(), "opportunities": AsyncMock(return_value=CoreAssessment.parse(PAYLOAD))})()
            first = CoreBridge(client, Store(hass, 1, "photography_events.core_cache.test"), lambda: NOW)
            await first.refresh()
            client.health.side_effect = CoreError()
            second = CoreBridge(client, Store(hass, 1, "photography_events.core_cache.test"), lambda: NOW + timedelta(hours=1))
            await second.initialize()
            result = await second.refresh()
            self.assertTrue(result["stale"])
            self.assertFalse(result["items"][0]["eligibility"])
            self.assertEqual(result["items"][0]["occurrence_key"], "tule_elk_rut-2026-09-15")
