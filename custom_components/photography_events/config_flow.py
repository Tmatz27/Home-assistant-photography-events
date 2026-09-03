"""Config and options flow for Photography Events."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    ALL_CATEGORIES,
    CONF_ALERT_SCORE,
    CONF_EBIRD_API_KEY,
    CONF_ENABLED_CATEGORIES,
    CONF_MAX_DRIVE_HOURS,
    CONF_SUNSET_SCORE,
    DEFAULT_ALERT_SCORE,
    DEFAULT_MAX_DRIVE_HOURS,
    DEFAULT_SUNSET_SCORE,
    DOMAIN,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_ENABLED_CATEGORIES,
                default=defaults.get(CONF_ENABLED_CATEGORIES, list(ALL_CATEGORIES)),
            ): vol.All(vol.Length(min=1), [vol.In(ALL_CATEGORIES)]),
            vol.Required(
                CONF_MAX_DRIVE_HOURS,
                default=defaults.get(CONF_MAX_DRIVE_HOURS, DEFAULT_MAX_DRIVE_HOURS),
            ): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=12)),
            vol.Required(
                CONF_SUNSET_SCORE,
                default=defaults.get(CONF_SUNSET_SCORE, DEFAULT_SUNSET_SCORE),
            ): vol.All(vol.Coerce(int), vol.Range(min=50, max=100)),
            vol.Required(
                CONF_ALERT_SCORE,
                default=defaults.get(CONF_ALERT_SCORE, DEFAULT_ALERT_SCORE),
            ): vol.All(vol.Coerce(int), vol.Range(min=50, max=100)),
            vol.Optional(
                CONF_EBIRD_API_KEY,
                description={"suggested_value": defaults.get(CONF_EBIRD_API_KEY, "")},
            ): str,
        }
    )


class PhotographyEventsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Photography Events", data=user_input)

        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return PhotographyEventsOptionsFlow()


class PhotographyEventsOptionsFlow(OptionsFlow):
    """Lets categories, thresholds, and the drive limit be changed after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))
