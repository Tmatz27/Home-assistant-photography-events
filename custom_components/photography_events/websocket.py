"""Authenticated bounded reads from one sanitized coordinator snapshot."""
import copy
import json
import secrets
import time

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .projection import VERSION, timestamp

STATE_KEY = DOMAIN + "_ws"
VIEWS = {"cant_miss", "watching", "planner", "birds"}


def page_limit(value):
    if type(value) is not int or not 1 <= value <= 50:
        raise vol.Invalid("Expected an integer page limit from 1 to 50")
    return value


def clear_entry(hass, entry_id):
    state = hass.data.get(STATE_KEY, {})
    for mapping in (state.get("cursors", {}), state.get("rates", {})):
        for key, value in list(mapping.items()):
            if (isinstance(key, tuple) and key[1] == entry_id) or (isinstance(value, dict) and value.get("entry_id") == entry_id):
                mapping.pop(key, None)


def authorized(hass, user, entry_id):
    if user is None or not user.is_active:
        return False
    if user.is_admin:
        return True
    entries = er.async_entries_for_config_entry(er.async_get(hass), entry_id)
    ids = [e.entity_id for e in entries if e.unique_id.endswith(("_cant_miss", "_planning_outlook", "_connection_state"))]
    return bool(ids) and all(user.permissions.check_entity(eid, POLICY_READ) for eid in ids)


def checked(hass, connection, msg):
    if msg["projection_version"] != VERSION:
        connection.send_error(msg["id"], "unsupported_projection", "Unsupported projection")
        return None
    coordinator = hass.data.get(DOMAIN, {}).get(msg["entry_id"])
    if coordinator is None or not authorized(hass, connection.user, msg["entry_id"]):
        connection.send_error(msg["id"], "unauthorized", "Entry unavailable or unauthorized")
        return None
    now = time.monotonic()
    state = hass.data.setdefault(STATE_KEY, {"cursors": {}, "rates": {}})
    state["cursors"] = {k: v for k, v in state["cursors"].items() if v["expires"] > now}
    state["rates"] = {k: v for k, v in state["rates"].items() if now - v < 60}
    # Rate state must preserve recent keys; prune old keys only.
    key = (connection.user.id, msg["entry_id"], msg.get("view", "detail"))
    previous = state["rates"].get(key)
    if previous is not None and now - previous < 1:
        connection.send_error(msg["id"], "rate_limited", "Read limit reached")
        return None
    if len(state["rates"]) >= 512 and key not in state["rates"]:
        connection.send_error(msg["id"], "rate_limited", "Read limit reached")
        return None
    state["rates"][key] = now
    return coordinator


@websocket_api.websocket_command({
    vol.Required("type"): "photography_events/get_view",
    vol.Required("entry_id"): vol.All(str, vol.Length(min=1, max=128)),
    vol.Required("projection_version"): vol.All(str, vol.Length(max=64)),
    vol.Required("view"): vol.In(VIEWS),
    vol.Optional("snapshot_id"): vol.All(str, vol.Length(max=64)),
    vol.Optional("cursor"): vol.All(str, vol.Length(max=128)),
    vol.Optional("limit", default=50): page_limit,
    vol.Optional("from"): vol.All(str, vol.Length(max=64)), vol.Optional("through"): vol.All(str, vol.Length(max=64)),
})
@websocket_api.async_response
async def get_view(hass, connection, msg):
    coordinator = checked(hass, connection, msg)
    if coordinator is None:
        return
    state = hass.data[STATE_KEY]
    result = coordinator.view(msg["view"])
    if msg.get("snapshot_id") and msg["snapshot_id"] != result["snapshot_id"]:
        connection.send_error(msg["id"], "snapshot_expired", "Snapshot changed")
        return
    offset = 0
    if "cursor" in msg:
        cursor = state["cursors"].get(msg["cursor"])
        if (cursor is None or cursor["entry_id"] != msg["entry_id"] or cursor["user"] != connection.user.id
                or cursor["view"] != msg["view"] or cursor["snapshot_id"] != result["snapshot_id"]):
            connection.send_error(msg["id"], "snapshot_expired", "Cursor expired")
            return
        deadline = cursor["snapshot"].get("expires_at")
        if (deadline and cursor["snapshot"]["freshness"] == "current" and coordinator.bridge
                and timestamp(deadline) <= coordinator.bridge.clock()):
            # A later fetch can retain material revision while renewing transport.
            # It cannot extend the retrieval clock of an immutable earlier page.
            connection.send_error(msg["id"], "snapshot_expired", "Snapshot deadline expired")
            return
        result, offset = copy.deepcopy(cursor["snapshot"]), cursor["offset"]
    elif "from" in msg or "through" in msg:
        try:
            first, last = timestamp(msg["from"]), timestamp(msg["through"])
            if msg["view"] != "planner" or not 0 <= (last - first).total_seconds() <= 366 * 86400:
                raise ValueError
            result["items"] = [r for r in result["items"] if timestamp(r["starts_at"]) <= last and timestamp(r["ends_at"]) >= first]
        except (ValueError, KeyError):
            connection.send_error(msg["id"], "invalid_range", "Invalid planner range")
            return
    snapshot = copy.deepcopy(result)
    rows = result["items"][offset:offset + msg["limit"]]
    result["items"] = rows
    while rows and len(json.dumps(result, ensure_ascii=False).encode()) > 120 * 1024:
        rows.pop()
    if len(json.dumps(result, ensure_ascii=False).encode()) > 128 * 1024:
        connection.send_error(msg["id"], "invalid_response", "Projection too large")
        return
    next_offset = offset + len(rows)
    more = next_offset < len(snapshot["items"])
    result["counts"]["returned"] = len(rows)
    result["truncated"] = more
    if more:
        if len(state["cursors"]) >= 512:
            connection.send_error(msg["id"], "rate_limited", "Cursor limit reached")
            return
        token = secrets.token_urlsafe(24)
        state["cursors"][token] = {"entry_id": msg["entry_id"], "user": connection.user.id,
                                  "view": msg["view"], "snapshot_id": result["snapshot_id"],
                                  "offset": next_offset, "snapshot": snapshot, "expires": time.monotonic() + 900}
        result["next_cursor"] = token
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({
    vol.Required("type"): "photography_events/get_detail",
    vol.Required("entry_id"): vol.All(str, vol.Length(min=1, max=128)),
    vol.Required("projection_version"): vol.All(str, vol.Length(max=64)),
    vol.Required("snapshot_id"): vol.All(str, vol.Length(max=64)),
    vol.Required("occurrence_key"): vol.All(str, vol.Length(min=1, max=256)),
})
@websocket_api.async_response
async def get_detail(hass, connection, msg):
    coordinator = checked(hass, connection, msg)
    if coordinator is None:
        return
    # Read-only details use the same all-row projection, never an upstream fetch.
    result = coordinator.view("watching")
    if msg["snapshot_id"] != result["snapshot_id"]:
        connection.send_error(msg["id"], "snapshot_expired", "Snapshot changed")
        return
    rows = result["items"] + coordinator.view("cant_miss")["items"]
    row = next((r for r in rows if r["occurrence_key"] == msg["occurrence_key"]), None)
    if row is None:
        connection.send_error(msg["id"], "not_found", "Occurrence unavailable")
    elif len(json.dumps(row, ensure_ascii=False).encode()) > 32768:
        connection.send_error(msg["id"], "invalid_response", "Detail too large")
    else:
        connection.send_result(msg["id"], row)


def async_register(hass):
    key = DOMAIN + "_ws_registered"
    if hass.data.get(key):
        return
    websocket_api.async_register_command(hass, get_view)
    websocket_api.async_register_command(hass, get_detail)
    hass.data[key] = True
