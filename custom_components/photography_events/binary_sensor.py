"""The drop-everything flag: on when something worth driving to is imminent."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PhotographyEventsCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PhotographyActionOpportunity(coordinator, entry)])


class PhotographyActionOpportunity(CoordinatorEntity, BinarySensorEntity):
    """Turns on when a high-scoring opportunity is within the drive limit.

    Everything an automation needs to write a useful notification - where, how
    far, why, and what to pack - is exposed as attributes, so the automation
    itself stays a few lines of templating.
    """

    _attr_has_entity_name = True
    _attr_name = "Action opportunity"
    _attr_icon = "mdi:camera-burst"

    def __init__(self, coordinator: PhotographyEventsCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_action_opportunity"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Photography Events",
            "manufacturer": "Photography Events",
        }

    @property
    def _top(self):
        return (self.coordinator.data or {}).get("top_action")

    @property
    def is_on(self) -> bool:
        return self._top is not None

    @property
    def extra_state_attributes(self) -> dict:
        top = self._top
        if top is None:
            upcoming = (self.coordinator.data or {}).get("action_events") or []
            return {
                "event_name": None,
                "confidence_score": 0,
                "candidates_48h": len(upcoming),
            }

        gear = top.gear
        return {
            "event_name": top.title,
            "confidence_score": top.score,
            "category": top.category,
            "target_zone": top.zone_name,
            "zone_id": top.zone_id,
            "drive_time": f"{top.drive_hours:.1f} h",
            "drive_hours": top.drive_hours,
            "starts": top.start.isoformat(),
            "ends": top.end.isoformat() if top.end else None,
            "condition_summary": top.detail,
            "reasons": top.reasons,
            "recommended_gear": ", ".join(value for value in gear.values() if value),
            "gear_glass": gear.get("glass"),
            "gear_support": gear.get("support"),
            "gear_settings": gear.get("settings"),
        }
