"""Sensors summarising the next opportunity and the best sky score."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ALL_CATEGORIES, GEAR_PROFILES, CATEGORY_SUNSET, DOMAIN
from .parks import PARKS
from .coordinator import PhotographyEventsCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            NextOpportunitySensor(coordinator, entry),
            BestSkyScoreSensor(coordinator, entry),
            PlanningOutlookSensor(coordinator, entry),
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


class PlanningOutlookSensor(_BaseSensor):
    """The whole year ahead, in one attribute, for the card to render.

    The calendar entity is the right home for these events as far as Home
    Assistant is concerned, but its REST shape carries only a summary, a
    description and times - not the score, category, drive time or gear that
    the planning view is built around. Rather than smuggle those through the
    description as encoded text, the list is published here in full.

    ``_unrecorded_attributes`` is what makes that affordable: without it, a few
    hundred events would be written to the recorder database on every state
    change, forever, to store something that is recomputed from scratch each
    cycle anyway. The attribute still reaches the card over the websocket.
    """

    _attr_name = "Planning outlook"
    _attr_icon = "mdi:calendar-month"
    _attr_native_unit_of_measurement = "events"
    _unrecorded_attributes = frozenset({"events", "categories"})

    # A hard ceiling so a future source cannot quietly turn one attribute into
    # a megabyte of websocket traffic on every update.
    MAX_EVENTS = 400

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry, "planning_outlook")

    @property
    def native_value(self) -> int:
        return len(self._opportunities)

    @property
    def extra_state_attributes(self) -> dict:
        upcoming = self._opportunities[: self.MAX_EVENTS]
        return {
            "events": [item.compact() for item in upcoming],
            "categories": sorted({item.category for item in self._opportunities}),
            "all_categories": list(ALL_CATEGORIES),
            "gear_by_category": {
                category: profile for category, profile in GEAR_PROFILES.items()
            },
            "parks": {
                park.key: {
                    "name": park.name,
                    "miles": park.miles,
                    "drive_hours": park.drive_hours,
                    "drive_label": park.drive_label,
                    "dogs": park.dogs,
                    "dog_label": park.dog_label,
                    "dog_detail": park.dog_detail,
                }
                for park in PARKS
            },
            "truncated": len(self._opportunities) > self.MAX_EVENTS,
            "generated": (self.coordinator.data or {}).get("generated"),
        }
