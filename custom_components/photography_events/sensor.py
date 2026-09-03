"""Sensors summarising the next opportunity and the best sky score."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CATEGORY_SUNSET, DOMAIN
from .coordinator import PhotographyEventsCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextOpportunitySensor(coordinator, entry),
            BestSkyScoreSensor(coordinator, entry),
        ]
    )


class _BaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PhotographyEventsCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Photography Events",
            "manufacturer": "Photography Events",
        }

    @property
    def _opportunities(self) -> list:
        return (self.coordinator.data or {}).get("opportunities") or []


class NextOpportunitySensor(_BaseSensor):
    """The next scored opportunity of any category."""

    _attr_name = "Next opportunity"
    _attr_icon = "mdi:calendar-star"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "next_opportunity")

    @property
    def native_value(self) -> str | None:
        upcoming = self._opportunities
        return upcoming[0].title if upcoming else None

    @property
    def extra_state_attributes(self) -> dict:
        upcoming = self._opportunities
        if not upcoming:
            return {"count": 0}
        nxt = upcoming[0]
        return {
            "count": len(upcoming),
            "starts": nxt.start.isoformat(),
            "score": nxt.score,
            "category": nxt.category,
            "target_zone": nxt.zone_name,
            "drive_hours": nxt.drive_hours,
            "detail": nxt.detail,
            "source_url": nxt.source_url,
        }


class BestSkyScoreSensor(_BaseSensor):
    """Highest sunrise/sunset colour score across the reachable zones."""

    _attr_name = "Best sky score"
    _attr_icon = "mdi:weather-sunset"
    _attr_native_unit_of_measurement = "score"

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "best_sky_score")

    @property
    def _best(self):
        skies = [item for item in self._opportunities if item.category == CATEGORY_SUNSET]
        return max(skies, key=lambda item: item.score) if skies else None

    @property
    def native_value(self) -> int:
        best = self._best
        return best.score if best else 0

    @property
    def extra_state_attributes(self) -> dict:
        best = self._best
        if best is None:
            return {"target_zone": None}
        return {
            "target_zone": best.zone_name,
            "starts": best.start.isoformat(),
            "detail": best.detail,
            "reasons": best.reasons,
            "drive_hours": best.drive_hours,
        }
