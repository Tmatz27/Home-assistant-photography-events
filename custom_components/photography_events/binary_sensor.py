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
                "sources": (self.coordinator.data or {}).get("sources", {}),
            }

        gear = top.gear
        return {
            # The checklist or observation this came from, when there is one.
            # A rare-bird alert is worth very little without a way to check
            # whether it is still being seen.
            "source_url": top.source_url,
            "event_name": top.title,
            "confidence_score": top.score,
            "category": top.category,
            "target_zone": top.zone_name,
            "zone_id": top.zone_id,
            "drive_time": _drive_label(top.drive_hours),
            "drive_hours": top.drive_hours,
            "drive_minutes": int(round(top.drive_hours * 60)),
            # "Routes API" / "Distance Matrix API" when Google answered,
            # "baseline" or "estimate" otherwise. The card says which, rather
            # than presenting a guess with the same confidence as a route.
            "drive_source": top.drive_source,
            "drive_in_traffic": top.drive_in_traffic,
            "starts": top.start.isoformat(),
            "ends": top.end.isoformat() if top.end else None,
            "condition_summary": top.detail,
            "reasons": top.reasons,
            "recommended_gear": ", ".join(value for value in gear.values() if value),
            "gear_glass": gear.get("glass"),
            "gear_support": gear.get("support"),
            "gear_settings": gear.get("settings"),
            # What actually closes the window, so the card can say "1h 36m
            # before the core sets" rather than a bare end time.
            "duration_minutes": top.extra.get("duration_minutes"),
            "limited_by": top.extra.get("limited_by"),
            "precision": top.extra.get("precision"),
            "primary_locations": top.extra.get("primary_locations"),
            "best_time_of_day": top.extra.get("best_time_of_day"),
            "season_range": top.extra.get("season_range"),
            "evidence": top.extra.get("evidence"),
            "verification": top.extra.get("verification"),
            "verify_urls": top.extra.get("verify_urls"),
            "sources": (self.coordinator.data or {}).get("sources", {}),
        }


def _drive_label(hours: float) -> str:
    """A drive time a person would say out loud."""
    minutes = int(round(hours * 60))
    if minutes < 90:
        return f"{minutes} min"
    whole, remainder = divmod(minutes, 60)
    if remainder == 0:
        return f"{whole} h"
    return f"{whole} h {remainder:02d} min"
