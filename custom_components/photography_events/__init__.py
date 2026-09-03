"""The Photography Events integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PhotographyEventsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]

CARD_FILENAME = "photography-events-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Photography Events from a config entry."""
    await _async_register_card(hass)

    coordinator = PhotographyEventsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options change, so category toggles take effect immediately."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve and register the bundled Lovelace card.

    Shipping the card inside the integration means one HACS install covers both
    halves, with no manual dashboard resource step. Registration failing is
    never fatal: the backend entities are useful on their own, and the card can
    always be added by hand.
    """
    if hass.data.get(f"{DOMAIN}_card_registered"):
        return

    try:
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig

        card_path = Path(__file__).parent / "www" / CARD_FILENAME
        if not card_path.is_file():
            _LOGGER.warning("Bundled card not found at %s; add it as a resource manually", card_path)
            return

        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(card_path), cache_headers=False)]
        )
        add_extra_js_url(hass, CARD_URL)
        hass.data[f"{DOMAIN}_card_registered"] = True
        _LOGGER.debug("Registered Photography Events card at %s", CARD_URL)
    except Exception:  # noqa: BLE001 - the backend must still load
        _LOGGER.warning(
            "Could not auto-register the Photography Events card; add %s as a dashboard "
            "resource manually if you want the card",
            CARD_URL,
            exc_info=True,
        )
