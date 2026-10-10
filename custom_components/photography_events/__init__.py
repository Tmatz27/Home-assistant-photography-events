"""Read-only Core integration; resources retain their existing URL."""
import logging
from pathlib import Path
from homeassistant.const import Platform
from homeassistant.exceptions import ServiceValidationError, ConfigEntryError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN
from .coordinator import PhotographyEventsCoordinator
from .websocket import async_register

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]
CARD_FILENAME = "photography-events-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_migrate_entry(hass, entry):
    if entry.version > 3:
        return False
    if entry.version < 3:
        data = dict(entry.data)
        data["connection_state"] = "configured" if data.get("core_url") and data.get("core_token") else "needs_connection"
        # Both v1 and v2 lists, including [], remain literal; options and private
        # credentials remain untouched and inactive. No network or Store load.
        hass.config_entries.async_update_entry(entry, data=data, version=3)
    return True


async def async_setup_entry(hass, entry):
    await _async_register_card(hass)
    coordinator = PhotographyEventsCoordinator(hass, entry)
    try:
        await coordinator.async_initialize()
        await coordinator.async_config_entry_first_refresh()
    except ValueError:
        await coordinator.async_shutdown()
        raise ConfigEntryError("Core connection requires reconfiguration") from None
    except Exception:
        await coordinator.async_shutdown()
        raise
    if coordinator.bridge and coordinator.bridge.availability in {"incompatible", "invalid_response"}:
        await coordinator.async_shutdown()
        ir.async_create_issue(hass, DOMAIN, f"core_connection_required_{entry.entry_id}", is_fixable=True, is_persistent=True,
                              severity=ir.IssueSeverity.WARNING, translation_key="core_connection_required", data={"entry_id": entry.entry_id})
        raise ConfigEntryError("Core connection requires reconfiguration")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    async_register(hass)
    _async_register_services(hass)
    issue = f"core_connection_required_{entry.entry_id}"
    if not coordinator.bridge:
        ir.async_create_issue(hass, DOMAIN, issue, is_fixable=True, is_persistent=True,
                              severity=ir.IssueSeverity.WARNING, translation_key="core_connection_required",
                              data={"entry_id": entry.entry_id})
    else:
        ir.async_delete_issue(hass, DOMAIN, issue)
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await coordinator.async_shutdown()
        raise
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


def _async_register_services(hass):
    async def retired(_call):
        raise ServiceValidationError("Unavailable: Core choices and report ingestion are not supported in this read-only build")
    for name in ("ingest_report", "set_event_choice"):
        if not hass.services.has_service(DOMAIN, name):
            hass.services.async_register(DOMAIN, name, retired)


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if coordinator:
            await coordinator.async_shutdown()
        from .websocket import clear_entry
        clear_entry(hass, entry.entry_id)
        if not hass.data.get(DOMAIN):
            for name in ("ingest_report", "set_event_choice"):
                hass.services.async_remove(DOMAIN, name)
    return unloaded


async def _async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_card(hass) -> None:
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
