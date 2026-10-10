"""Secure singleton Core connection; legacy preferences remain inactive."""
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .core_client import PhotographyEventsCoreClient, CoreAuthenticationError, CoreVersionError, CoreProtocolError, CoreError


def connection_schema(url="", *, optional_token=False):
    return vol.Schema({
        vol.Required("core_url", default=url): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.URL)),
        (vol.Optional("core_token") if optional_token else vol.Required("core_token")):
            selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    })


async def validate_connection(hass, data):
    try:
        client = PhotographyEventsCoreClient(async_get_clientsession(hass), data.get("core_url", ""), data.get("core_token", ""))
        await client.health()
        await client.opportunities()  # Readiness alone never validates credentials.
        try:
            await client.source_health()
        except (CoreAuthenticationError, CoreVersionError, CoreProtocolError):
            raise
        except CoreError:
            pass  # Operational status outage cannot invent or renew assessment.
    except CoreAuthenticationError:
        return "invalid_auth"
    except CoreVersionError:
        return "unsupported_api_version"
    except CoreProtocolError:
        return "invalid_core_response"
    except CoreError:
        return "cannot_connect"
    except (ValueError, TypeError, AttributeError):
        return "invalid_connection"
    return None


class PhotographyEventsConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 3

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            data = {"core_url": user_input["core_url"].strip(), "core_token": user_input["core_token"].strip(), "connection_state": "configured"}
            if error := await validate_connection(self.hass, data):
                errors["base"] = error
            else:
                await self.async_set_unique_id(DOMAIN, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Photography Events", data=data)
        return self.async_show_form(step_id="user", data_schema=connection_schema(), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        return await self._connection_form("reconfigure", self._get_reconfigure_entry(), user_input, True)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._connection_form("reauth_confirm", self._get_reauth_entry(), user_input, False)

    async def _connection_form(self, step, entry, user_input, retain):
        errors = {}
        if user_input is not None:
            token = (user_input.get("core_token") or "").strip()
            if not token and retain:
                token = entry.data.get("core_token", "")
            updates = {"core_url": user_input["core_url"].strip(), "core_token": token, "connection_state": "configured"}
            if error := await validate_connection(self.hass, updates):
                errors["base"] = error
            else:
                ir.async_delete_issue(self.hass, DOMAIN, f"core_connection_required_{entry.entry_id}")
                return self.async_update_reload_and_abort(entry, data_updates=updates)
        return self.async_show_form(step_id=step,
                                   data_schema=connection_schema(entry.data.get("core_url", ""), optional_token=retain), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(entry):
        return PhotographyEventsOptionsFlow()


class PhotographyEventsOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Preserve old secrets/preferences exactly; the active runtime does
            # not read them. This selector changes presentation only.
            return self.async_create_entry(title="", data={**self.config_entry.options, "initial_view": user_input["initial_view"]})
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required("initial_view", default=self.config_entry.options.get("initial_view", "cant_miss")):
                selector.SelectSelector(selector.SelectSelectorConfig(options=["cant_miss", "watching", "planner", "birds"], mode=selector.SelectSelectorMode.DROPDOWN)),
        }))
