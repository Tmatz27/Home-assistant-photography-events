"""Fetches forecasts and assembles scored opportunities on a schedule."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import events as event_builder
from .const import (
    ALL_CATEGORIES,
    CATEGORY_ASTRO,
    CATEGORY_SUNSET,
    CONF_ALERT_SCORE,
    CONF_ENABLED_CATEGORIES,
    CONF_MAX_DRIVE_HOURS,
    CONF_SUNSET_SCORE,
    DEFAULT_ALERT_SCORE,
    DEFAULT_MAX_DRIVE_HOURS,
    DEFAULT_SUNSET_SCORE,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
    OPEN_METEO_URL,
    TARGET_ZONES,
)
from .weather_scoring import build_open_meteo_params

_LOGGER = logging.getLogger(__name__)

CALENDAR_HORIZON_DAYS = 365
ASTRO_HORIZON_DAYS = 30
REQUEST_TIMEOUT = 30


class PhotographyEventsCoordinator(DataUpdateCoordinator):
    """Polls weather per zone and rebuilds the opportunity list."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_MINUTES),
        )
        self.entry = entry

    @property
    def _options(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    @property
    def enabled_categories(self) -> set[str]:
        configured = self._options.get(CONF_ENABLED_CATEGORIES)
        return set(configured) if configured else set(ALL_CATEGORIES)

    @property
    def max_drive_hours(self) -> float:
        return float(self._options.get(CONF_MAX_DRIVE_HOURS, DEFAULT_MAX_DRIVE_HOURS))

    @property
    def alert_score(self) -> int:
        return int(self._options.get(CONF_ALERT_SCORE, DEFAULT_ALERT_SCORE))

    @property
    def sunset_score(self) -> int:
        return int(self._options.get(CONF_SUNSET_SCORE, DEFAULT_SUNSET_SCORE))

    async def _async_update_data(self) -> dict:
        now = datetime.now(timezone.utc)
        categories = self.enabled_categories
        zones = [zone for zone in TARGET_ZONES if zone["drive_hours"] <= self.max_drive_hours]

        forecasts = await self._async_fetch_forecasts(zones)
        opportunities: list[event_builder.Opportunity] = []

        for zone in zones:
            forecast = forecasts.get(zone["id"])
            cloud_lookup = _make_cloud_lookup(forecast)

            if CATEGORY_SUNSET in categories and forecast:
                opportunities.extend(
                    await self.hass.async_add_executor_job(
                        event_builder.build_sunset_opportunities,
                        zone,
                        forecast,
                        now,
                        self.sunset_score,
                    )
                )

            if CATEGORY_ASTRO in categories:
                opportunities.extend(
                    await self.hass.async_add_executor_job(
                        event_builder.build_meteor_opportunities,
                        zone,
                        now,
                        ASTRO_HORIZON_DAYS,
                        cloud_lookup,
                    )
                )
                opportunities.extend(
                    await self.hass.async_add_executor_job(
                        event_builder.build_milky_way_opportunities,
                        zone,
                        now,
                        14,
                        cloud_lookup,
                    )
                )

        seasonal = await self.hass.async_add_executor_job(
            event_builder.build_seasonal_opportunities, now, CALENDAR_HORIZON_DAYS
        )
        opportunities.extend(item for item in seasonal if item.category in categories)

        opportunities = event_builder.within_drive(opportunities, self.max_drive_hours)
        action = event_builder.action_window(opportunities, now)
        top = next((item for item in action if item.score >= self.alert_score), None)

        return {
            "generated": now,
            "opportunities": sorted(opportunities, key=lambda item: item.start),
            "action_events": action,
            "top_action": top,
            "zone_count": len(zones),
            "forecast_zones": sorted(forecasts),
        }

    async def _async_fetch_forecasts(self, zones: list[dict]) -> dict[str, dict]:
        """Fetch Open-Meteo hourly data per zone, tolerating individual failures.

        Open-Meteo needs no key and no account. One zone failing must not take
        down the rest of the integration, so every request is isolated.
        """
        session = async_get_clientsession(self.hass)

        async def fetch(zone: dict) -> tuple[str, dict | None]:
            params = build_open_meteo_params(zone["latitude"], zone["longitude"])
            try:
                async with asyncio.timeout(REQUEST_TIMEOUT):
                    response = await session.get(OPEN_METEO_URL, params=params)
                    if response.status != 200:
                        _LOGGER.warning(
                            "Open-Meteo returned %s for %s", response.status, zone["name"]
                        )
                        return zone["id"], None
                    return zone["id"], await response.json()
            except (TimeoutError, asyncio.CancelledError):
                _LOGGER.warning("Open-Meteo timed out for %s", zone["name"])
                return zone["id"], None
            except Exception:  # noqa: BLE001 - never let one zone break the update
                _LOGGER.exception("Open-Meteo request failed for %s", zone["name"])
                return zone["id"], None

        results = await asyncio.gather(*(fetch(zone) for zone in zones))
        return {zone_id: payload for zone_id, payload in results if payload}


def _make_cloud_lookup(forecast: dict | None):
    """Total cloud cover nearest a moment, or None when there is no forecast."""
    if not forecast:
        return None
    hourly = forecast.get("hourly", {})
    times = hourly.get("time") or []
    clouds = hourly.get("cloud_cover") or []
    if not times or not clouds:
        return None

    parsed: list[tuple[float, float]] = []
    for stamp, value in zip(times, clouds):
        if not isinstance(value, (int, float)):
            continue
        try:
            moment = datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        parsed.append((moment.timestamp(), float(value)))

    if not parsed:
        return None

    def lookup(moment: datetime) -> float | None:
        target = moment.timestamp()
        stamp, value = min(parsed, key=lambda item: abs(item[0] - target))
        return value if abs(stamp - target) <= 5400 else None

    return lookup
