"""Preserved calendar identity; no inferred wildlife appointment precision."""
from homeassistant.components.calendar import CalendarEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PhotographyCalendar(hass.data[DOMAIN][entry.entry_id], entry)])


class PhotographyCalendar(CoordinatorEntity, CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Planning calendar"
    _attr_icon = "mdi:calendar-month"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": "Photography Events", "manufacturer": "Photography Events"}

    @property
    def available(self):
        return False  # Core v1 has no time_precision: no invented timed appointments.

    @property
    def event(self):
        return None

    @property
    def extra_state_attributes(self):
        return {"capability_state": "unsupported", "reason": "Core calendar precision is not available"}

    async def async_get_events(self, hass, start_date, end_date):
        return []
