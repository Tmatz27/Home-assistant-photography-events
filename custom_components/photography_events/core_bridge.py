"""Developer-only bridge with hot and persisted product cache.

The production coordinator does not instantiate this class. No local behavior
or card contract changes in Milestone 1. See CORE_DEVELOPMENT.md for activation.
"""
import copy
import hashlib
from datetime import datetime, timezone, timedelta

from .core_client import CoreAssessment, CoreError, aware_timestamp, PhotographyEventsCoreClient

MAX_CACHE_AGE = timedelta(days=7)


class CoreBridge:
    def __init__(self, client, store, clock=lambda: datetime.now(timezone.utc)):
        self.client, self.store, self.clock = client, store, clock
        self.cached, self.saved_at = None, None

    async def initialize(self):
        saved = await self.store.async_load()
        if not isinstance(saved, dict):
            return
        try:
            self.saved_at = aware_timestamp(saved.get("saved_at"))
            self.cached = CoreAssessment.parse(saved.get("payload"))
        except CoreError:
            self.cached, self.saved_at = None, None

    async def refresh(self):
        try:
            await self.client.health()
            result = await self.client.opportunities()
            stamp = self.clock()
            # Persist only validated API products, never provider payloads.
            if result.payload["assessment_state"] == "complete":
                await self.store.async_save({"saved_at": stamp.isoformat(), "payload": result.payload})
                self.cached, self.saved_at = result, stamp
            return {**copy.deepcopy(result.payload), "stale": False, "core_error": None}
        except CoreError as exc:
            result = None
            if self.cached and self.saved_at and timedelta(0) <= self.clock() - self.saved_at <= MAX_CACHE_AGE:
                result = copy.deepcopy(self.cached.payload)
                for row in result["items"]:
                    row.update(eligibility=False, presentation="held", held=True, watching=False,
                               safety_state="unknown", safety_summary="STALE: safety has not been checked.")
            if result is None:
                result = {"items": [], "data_as_of": None, "missing_required_sources": ["core"], "degraded_sources": []}
            result.update(stale=True, assessment_state="incomplete", core_error=exc.code,
                          status="Core unavailable. Cached information is STALE; no current travel assessment.")
            return result


async def async_create_developer_bridge(hass, entry):
    """Construct explicitly from private ConfigEntry data; never entry options/card config.

    Called by developer tests only in M1. Credentials are not added to entities,
    services, diagnostic payloads, websocket responses, or logs.
    """
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.storage import Store

    url, token = entry.data["core_url"], entry.data["core_token"]
    connection = hashlib.sha256(url.rstrip("/").encode()).hexdigest()[:16]
    store = Store(hass, 1, f"photography_events.core_cache.{entry.entry_id}.{connection}")
    bridge = CoreBridge(PhotographyEventsCoreClient(async_get_clientsession(hass), url, token), store)
    await bridge.initialize()
    return bridge
