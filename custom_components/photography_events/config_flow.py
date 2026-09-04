"""Config and options flow for Photography Events.

Every field here is built from a Home Assistant **selector**. That is not
decoration: Home Assistant serialises the schema to JSON to render the form, and
a validator it cannot serialise raises server-side inside ``async_show_form``.
The flow then fails while remaining registered as in progress, so every later
attempt aborts with ``already_in_progress`` and the integration can never be set
up again until Home Assistant restarts.

A bare ``[vol.In(...)]`` list - the obvious way to write a multi-select - is
exactly such a validator. Selectors are the shapes Home Assistant guarantees it
can serialise, so they are what this uses.

The single-instance guard is deliberately ``_async_current_entries()`` rather
than ``async_set_unique_id()``'s in-progress check, for the same class of
reason: it runs before any form is built, and it cannot wedge the flow.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    ALL_CATEGORIES,
    CONF_ALERT_SCORE,
    CONF_EBIRD_API_KEY,
    CONF_ENABLE_FIELD_REPORTS,
    CONF_ENABLED_CATEGORIES,
    CONF_GOOGLE_API_KEY,
    CONF_MAX_DRIVE_HOURS,
    CONF_ROUTING_MODE,
    CONF_SUNSET_SCORE,
    DEFAULT_ALERT_SCORE,
    DEFAULT_MAX_DRIVE_HOURS,
    DEFAULT_SUNSET_SCORE,
    DOMAIN,
    ROUTING_AUTO,
    ROUTING_MODES,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the form. Selectors only - see the module docstring."""
    return vol.Schema(
        {
            vol.Required(
                CONF_ENABLED_CATEGORIES,
                default=defaults.get(CONF_ENABLED_CATEGORIES) or list(ALL_CATEGORIES),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(ALL_CATEGORIES),
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                    translation_key="category",
                )
            ),
            vol.Required(
                CONF_MAX_DRIVE_HOURS,
                default=float(defaults.get(CONF_MAX_DRIVE_HOURS, DEFAULT_MAX_DRIVE_HOURS)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.5,
                    max=12,
                    step=0.25,
                    mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="h",
                )
            ),
            vol.Required(
                CONF_SUNSET_SCORE,
                default=int(defaults.get(CONF_SUNSET_SCORE, DEFAULT_SUNSET_SCORE)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=50, max=100, step=1, mode=selector.NumberSelectorMode.SLIDER)
            ),
            vol.Required(
                CONF_ALERT_SCORE,
                default=int(defaults.get(CONF_ALERT_SCORE, DEFAULT_ALERT_SCORE)),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(min=50, max=100, step=1, mode=selector.NumberSelectorMode.SLIDER)
            ),
            # Free from ebird.org/api/keygen. Without it the bird category
            # produces nothing rather than failing.
            vol.Optional(
                CONF_EBIRD_API_KEY,
                description={"suggested_value": defaults.get(CONF_EBIRD_API_KEY, "")},
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            # Optional. Drive times fall back to a distance estimate calibrated
            # against the zone table when this is empty.
            vol.Optional(
                CONF_GOOGLE_API_KEY,
                description={"suggested_value": defaults.get(CONF_GOOGLE_API_KEY, "")},
            ): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required(
                CONF_ROUTING_MODE,
                default=defaults.get(CONF_ROUTING_MODE, ROUTING_AUTO),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(ROUTING_MODES),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="routing_mode",
                )
            ),
            vol.Required(
                CONF_ENABLE_FIELD_REPORTS,
                default=bool(defaults.get(CONF_ENABLE_FIELD_REPORTS, True)),
            ): selector.BooleanSelector(),
        }
    )


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    """Normalise what the form hands back.

    Number selectors always return floats, and the two scores are compared
    against integers everywhere downstream. Blank API keys come back as empty
    strings; dropping them keeps "no key" as a single representation rather
    than two.
    """
    cleaned = dict(user_input)
    for key in (CONF_SUNSET_SCORE, CONF_ALERT_SCORE):
        if key in cleaned:
            cleaned[key] = int(cleaned[key])
    if CONF_MAX_DRIVE_HOURS in cleaned:
        cleaned[CONF_MAX_DRIVE_HOURS] = float(cleaned[CONF_MAX_DRIVE_HOURS])
    for key in (CONF_EBIRD_API_KEY, CONF_GOOGLE_API_KEY):
        if not (cleaned.get(key) or "").strip():
            cleaned.pop(key, None)
        else:
            cleaned[key] = cleaned[key].strip()
    return cleaned


class PhotographyEventsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Initial setup."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        # Checked before anything is built, so a single-instance abort can never
        # leave a half-created flow behind.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            # raise_on_progress=False: a stale in-progress flow should never be
            # able to block setup outright, which is the failure this replaced.
            await self.async_set_unique_id(DOMAIN, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title="Photography Events", data=_clean(user_input))

        return self.async_show_form(step_id="user", data_schema=_schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(entry: ConfigEntry) -> OptionsFlow:
        return PhotographyEventsOptionsFlow()


class PhotographyEventsOptionsFlow(OptionsFlow):
    """Lets keys, categories, thresholds, and the drive limit change after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=_clean(user_input))

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_schema(current))
