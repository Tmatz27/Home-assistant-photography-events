"""Validated sanitized cache and connection state; no provider or intelligence code."""
import copy
import hashlib
from datetime import datetime, timezone

from .core_client import PhotographyEventsCoreClient, CoreError, CoreAuthenticationError, CoreVersionError, CoreProtocolError
from .projection import VERSION, DestinationPolicy, InvalidProjection, MAX_CACHE_AGE, MAX_CLOCK_SKEW, timestamp, sanitize_envelope, project


class CoreBridge:
    def __init__(self, client, store, clock=lambda: datetime.now(timezone.utc), *, namespace="test", policy=None):
        self.client, self.store, self.clock, self.namespace = client, store, clock, namespace
        self.policy = policy or DestinationPolicy()
        self.cached = self.payload = None
        self.saved_at = self.fetched_at = self.cached_fetch = None
        self.availability, self.error_code = "offline", "core_unavailable"
        self.sources = {"items": [], "error_code": "source_unavailable"}

    def _check_time(self, payload):
        for value in [payload["generated_at"], payload["data_as_of"], *[r["data_as_of"] for r in payload["items"]]]:
            if value is not None and timestamp(value) > self.clock() + MAX_CLOCK_SKEW:
                raise InvalidProjection("future_timestamp")

    async def initialize(self):
        try:
            saved = await self.store.async_load()
            if not isinstance(saved, dict) or saved.get("projection_version") != VERSION or saved.get("namespace") != self.namespace:
                return
            fetch, stamp = timestamp(saved["fetched_at"]), timestamp(saved["saved_at"])
            if not fetch <= stamp <= self.clock() + MAX_CLOCK_SKEW or self.clock() - stamp >= MAX_CACHE_AGE:
                return
            payload = sanitize_envelope(saved["payload"], self.policy)
            self._check_time(payload)
            if payload["assessment_state"] != "complete":
                return
            self.cached, self.saved_at, self.cached_fetch = payload, stamp, fetch
        except (OSError, InvalidProjection, KeyError, TypeError):
            self.cached = None

    async def refresh(self):
        try:
            await self.client.health()
            assessment = await self.client.opportunities()
            payload = sanitize_envelope(assessment.payload, self.policy)
            self._check_time(payload)
            fetched = self.clock()
            try:
                self.sources = await self.client.source_health()
            except (CoreAuthenticationError, CoreVersionError, CoreProtocolError):
                raise
            except CoreError:
                self.sources = {"items": [], "error_code": "source_unavailable"}
            self.payload, self.fetched_at = payload, fetched
            self.availability, self.error_code = "online", None
            if payload["assessment_state"] == "complete" and payload["assessment_id"] is not None and payload["data_as_of"] is not None:
                saved = {"projection_version": VERSION, "namespace": self.namespace, "saved_at": fetched.isoformat(),
                         "fetched_at": fetched.isoformat(), "payload": copy.deepcopy(payload)}
                try:
                    await self.store.async_save(saved)
                    self.cached, self.saved_at, self.cached_fetch = copy.deepcopy(payload), fetched, fetched
                except OSError:
                    self.error_code = "cache_unavailable"
        except (CoreError, InvalidProjection) as exc:
            self.error_code = exc.code if isinstance(exc, CoreError) else "invalid_core_response"
            self.availability = ("auth_required" if isinstance(exc, CoreAuthenticationError) else
                                 "incompatible" if isinstance(exc, CoreVersionError) else
                                 "invalid_response" if isinstance(exc, (CoreProtocolError, InvalidProjection)) else "offline")
            usable = self.cached and self.saved_at and self.clock() - self.saved_at < MAX_CACHE_AGE
            self.payload = copy.deepcopy(self.cached) if self.availability == "offline" and usable else None
            self.fetched_at = self.cached_fetch if self.payload else None
            if self.availability != "offline":
                # Revocation and replacement cannot expose a prior principal's context.
                self.cached = None
            self.sources = {"items": [], "error_code": self.error_code}
        return self.view()

    def view(self, view="cant_miss", *, coverage="unverified"):
        return project(self.payload, now=self.clock(), fetched_at=self.fetched_at, saved_at=self.saved_at,
                       availability=self.availability, error_code=self.error_code,
                       cached_context=self.payload is not None and self.availability == "offline", coverage=coverage, view=view)


async def async_create_bridge(hass, entry):
    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    from homeassistant.helpers.storage import Store
    url, token = entry.data["core_url"], entry.data["core_token"]
    namespace = hashlib.sha256((url.rstrip("/") + "\0" + token).encode()).hexdigest()
    policy = await hass.async_add_executor_job(DestinationPolicy.load)
    store = Store(hass, 2, f"photography_events.core_cache.{entry.entry_id}.{namespace[:24]}")
    bridge = CoreBridge(PhotographyEventsCoreClient(async_get_clientsession(hass), url, token), store,
                        namespace=namespace, policy=policy)
    await bridge.initialize()
    return bridge
