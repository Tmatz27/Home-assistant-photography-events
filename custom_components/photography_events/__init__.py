"""The Photography Events integration."""

from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .const import ALL_CATEGORIES, DOMAIN
from .coordinator import PhotographyEventsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]

CARD_FILENAME = "photography-events-card.js"
CARD_URL = f"/{DOMAIN}/{CARD_FILENAME}"

SERVICE_INGEST_REPORT = "ingest_report"
INGEST_REPORT_SCHEMA = vol.Schema(
    {
        vol.Required("source"): cv.string,
        vol.Required("body"): cv.string,
        vol.Optional("subject", default=""): cv.string,
        vol.Optional("category"): vol.In(list(ALL_CATEGORIES)),
        vol.Optional("zone_id"): cv.string,
        vol.Optional("received"): cv.datetime,
        vol.Optional("url", default=""): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Photography Events from a config entry."""
    await _async_register_card(hass)

    coordinator = PhotographyEventsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _async_register_services(hass)
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the report ingestion service, once per Home Assistant.

    The way in for sources that publish a mailing list rather than an API. An
    automation on the built-in IMAP integration's ``imap_content`` event passes
    the body here; parsing, and the decision to discard it, happen in
    ``email_reports``.
    """
    if hass.services.has_service(DOMAIN, SERVICE_INGEST_REPORT):
        return

    async def _async_ingest(call: ServiceCall) -> None:
        received = call.data.get("received") or dt_util.utcnow()
        if received.tzinfo is None:
            received = received.replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        reports = await hass.async_add_executor_job(
            _parse_ingested_report,
            call.data.get("subject", ""),
            call.data["body"],
            call.data["source"],
            call.data.get("category"),
            call.data.get("zone_id"),
            received,
            call.data.get("url", ""),
        )
        if not reports:
            _LOGGER.debug("Ingested message from %s produced no usable report", call.data["source"])
            return
        for coordinator in list(hass.data.get(DOMAIN, {}).values()):
            await coordinator.async_add_ingested_reports(reports)

    hass.services.async_register(
        DOMAIN, SERVICE_INGEST_REPORT, _async_ingest, schema=INGEST_REPORT_SCHEMA
    )


def _parse_ingested_report(subject, body, source, category, zone_id, received, url):
    """Run the parser off the event loop - it walks the whole message body."""
    from .email_reports import parse_email_report

    return parse_email_report(
        subject=subject,
        body=body,
        source_name=source,
        category=category,
        zone_id=zone_id,
        received=received,
        url=url,
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data.get(DOMAIN):
            hass.services.async_remove(DOMAIN, SERVICE_INGEST_REPORT)
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
