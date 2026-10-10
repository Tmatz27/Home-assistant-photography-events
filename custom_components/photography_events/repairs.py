"""Complete a migrated entry in place using supported HA Repairs APIs."""
from homeassistant.components.repairs import RepairsFlow
from homeassistant.helpers import issue_registry as ir
from .config_flow import connection_schema, validate_connection
from .const import DOMAIN


class CoreConnectionRepair(RepairsFlow):
    def __init__(self, entry_id):
        self.entry_id = entry_id

    async def async_step_init(self, user_input=None):
        entry = self.hass.config_entries.async_get_entry(self.entry_id)
        if entry is None:
            return self.async_abort(reason="entry_missing")
        errors = {}
        if user_input is not None:
            updates = {"core_url": user_input["core_url"].strip(), "core_token": user_input["core_token"].strip(), "connection_state": "configured"}
            if error := await validate_connection(self.hass, updates):
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(entry, data={**entry.data, **updates})
                ir.async_delete_issue(self.hass, DOMAIN, f"core_connection_required_{entry.entry_id}")
                self.hass.config_entries.async_schedule_reload(entry.entry_id)
                return self.async_create_entry(data={})
        return self.async_show_form(step_id="init", data_schema=connection_schema(entry.data.get("core_url", "")), errors=errors)


async def async_create_fix_flow(hass, issue_id, data):
    return CoreConnectionRepair((data or {}).get("entry_id"))
