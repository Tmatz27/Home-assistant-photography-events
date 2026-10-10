"""Preserved action identity, always unavailable: notifications are cancelled."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PhotographyActionOpportunity(hass.data[DOMAIN][entry.entry_id], entry)])


class PhotographyActionOpportunity(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Action opportunity"
    _attr_icon = "mdi:camera-burst"
    _attr_available = False

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_action_opportunity"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": "Photography Events", "manufacturer": "Photography Events"}

    @property
    def available(self):
        return False

    @property
    def is_on(self):
        return None

    @property
    def extra_state_attributes(self):
        return {"notifications_enabled": False, "capability_state": "unsupported", "choices_available": False}
