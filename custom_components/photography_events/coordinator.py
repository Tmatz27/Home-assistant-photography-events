"""Active v17 coordinator: Core reads and presentation aging only.

Legacy fetchers, catalogs, scoring, routing, choices and announcements have no
imports or callers here. An outage never constructs the historical backend.
"""
import logging
import hashlib
import json
from datetime import timedelta, datetime, timezone

from homeassistant.config_entries import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_track_point_in_utc_time

from .core_bridge import async_create_bridge
from .projection import project

_LOGGER = logging.getLogger(__name__)


class PhotographyEventsCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, config_entry=entry, name="Photography Events", update_interval=timedelta(minutes=5))
        self.entry, self.bridge = entry, None
        self._cancel_expiry = None

    async def async_initialize(self):
        if self.entry.data.get("core_url") and self.entry.data.get("core_token"):
            self.bridge = await async_create_bridge(self.hass, self.entry)

    def view(self, name="cant_miss"):
        if self.bridge:
            result = self.bridge.view(name)
        else:
            result = project(None, now=datetime.now(timezone.utc), fetched_at=None,
                             availability="connection_required", error_code="connection_required", view=name)
        # Fetch times do not identify a material snapshot. Generation, safe rows,
        # status and local aging do; expiry changes the revision without a fetch.
        base = self.bridge.view("watching") if self.bridge else project(None, now=datetime.now(timezone.utc), fetched_at=None,
                                                                      availability="connection_required", error_code="connection_required", view="watching")
        material = {k: v for k, v in base.items() if k not in {"generated_at", "fetched_at", "saved_at", "expires_at"}}
        if self.bridge:
            material["items"] = base["items"] + self.bridge.view("cant_miss")["items"]
        revision = hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()[:24]
        initial = self.entry.options.get("initial_view", "cant_miss")
        if initial not in {"cant_miss", "watching", "planner", "birds"}:
            initial = "cant_miss"
        result.update(entry_id=self.entry.entry_id, snapshot_id=revision, initial_view=initial)
        return result

    async def _async_update_data(self):
        if self.bridge:
            await self.bridge.refresh()
            if self.bridge.availability == "auth_required":
                # Clear presentation before HA begins the supported reauth path.
                self.async_set_updated_data(self.view())
                raise ConfigEntryAuthFailed("Core authentication required")
            if self.data is None and self.bridge.availability == "offline":
                raise UpdateFailed("Core unavailable")
        self._schedule_expiry()
        return self.view()

    def _schedule_expiry(self):
        if self._cancel_expiry:
            self._cancel_expiry()
            self._cancel_expiry = None
        if not self.bridge or not self.bridge.payload:
            return
        from .projection import timestamp
        view, now = self.view(), self.bridge.clock()
        deadlines = [timestamp(v) for v in [view["expires_at"], *[r["valid_until"] for r in self.bridge.payload["items"]]] if v]
        future = [v for v in deadlines if v > now]
        if future:
            self._cancel_expiry = async_track_point_in_utc_time(self.hass, self._expire, min(future))

    async def _expire(self, _now):
        self.async_set_updated_data(self.view())
        self._schedule_expiry()

    async def async_shutdown(self):
        if self._cancel_expiry:
            self._cancel_expiry()
            self._cancel_expiry = None
        await super().async_shutdown()
