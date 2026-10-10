"""Compact status entities; rich changing arrays travel only over authorized WS."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


def summary(coordinator):
    v = coordinator.view()
    return {k: v[k] for k in ("projection_version", "entry_id", "snapshot_id", "availability", "assessment_state", "view_state",
                              "freshness", "transport_freshness", "assessment_freshness", "generated_at", "data_as_of",
                              "fetched_at", "saved_at", "expires_at", "error_code", "counts", "notifications_enabled", "initial_view")}


async def async_setup_entry(hass, entry, async_add_entities):
    c = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NextOpportunitySensor(c, entry), CantMissSensor(c, entry), PlanningOutlookSensor(c, entry),
                        BestSkyScoreSensor(c, entry), ConnectionStateSensor(c, entry), SourceStateSensor(c, entry)])


class SummarySensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:camera"

    def __init__(self, coordinator, entry, suffix, name):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"
        self._attr_name = name
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": "Photography Events", "manufacturer": "Photography Events"}

    @property
    def available(self):
        return True  # Status remains readable during outages; counts can be unknown.

    @property
    def extra_state_attributes(self):
        return summary(self.coordinator)


class NextOpportunitySensor(SummarySensor):
    def __init__(self, c, e):
        super().__init__(c, e, "next_opportunity", "Next opportunity")

    @property
    def native_value(self):
        rows = self.coordinator.view()["items"]
        return rows[0]["title"] if rows else None


class CantMissSensor(SummarySensor):
    def __init__(self, c, e):
        super().__init__(c, e, "cant_miss", "Can't Miss")

    @property
    def native_value(self):
        return self.coordinator.view()["counts"]["available"]


class PlanningOutlookSensor(SummarySensor):
    def __init__(self, c, e):
        super().__init__(c, e, "planning_outlook", "Planning outlook")

    @property
    def native_value(self):
        return self.coordinator.view("planner")["counts"]["available"]


class BestSkyScoreSensor(SummarySensor):
    def __init__(self, c, e):
        super().__init__(c, e, "best_sky_score", "Best sky score")

    @property
    def native_value(self):
        return None

    @property
    def available(self):
        return False

    @property
    def extra_state_attributes(self):
        return {**summary(self.coordinator), "capability_state": "unsupported"}


class ConnectionStateSensor(SummarySensor):
    def __init__(self, c, e):
        super().__init__(c, e, "connection_state", "Connection and assessment")

    @property
    def native_value(self):
        return self.coordinator.view()["view_state"]


class SourceStateSensor(SummarySensor):
    def __init__(self, c, e):
        super().__init__(c, e, "source_state", "Source status")

    @property
    def native_value(self):
        return "available" if self.coordinator.bridge and not self.coordinator.bridge.sources.get("error_code") else "unknown"

    @property
    def extra_state_attributes(self):
        sources = self.coordinator.bridge.sources.get("items", []) if self.coordinator.bridge else []
        # A small fixed set of known source keys; no provider records.
        states = {r["key"]: r["state"] for r in sources}
        return {**summary(self.coordinator), "sources": states}
