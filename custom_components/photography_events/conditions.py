"""Phenomenon conditions, read at the place the photograph happens.

The trigger policy in ``curation.py`` names what has to be true; this module
fills in the facts the gate checks, from forecasts for *that* place. It exists
because two policies used to check fields nothing ever set: firefall waited for
a cloud value that was never attached, so it could not qualify however clear
the evening, and the monarch cold-dawn test read the Vandenberg forecast for a
grove 45 km away across the Santa Maria valley. A condition checked at the
wrong place is a guess with a number on it.

Pure: forecasts, rows and alerts in; annotations out. No Home Assistant.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from . import astronomy, weather_scoring

# Forecast points for conditions that belong to a spot rather than a zone.
# Fetched alongside the zones; never used for sky scoring.
CONDITION_POINTS = (
    {"id": "pismo_grove", "name": "Pismo State Beach Monarch Butterfly Grove",
     "latitude": 35.1307, "longitude": -120.6349},
)

# --- Fresh snow then clearing (product thresholds) ---------------------------
# Clear enough to light fresh snow: total cloud at or under 30 %.
CLEARING_CLOUD = 30.0
# How far ahead a clearing forecast may be to count. Beyond two days fresh
# snow on trees is mostly gone in a sunny Sierra winter.
CLEARING_HORIZON_HOURS = 48
# How long after the clearing the photograph lasts.
CLEARING_WINDOW_HOURS = 12

# --- Firefall -----------------------------------------------------------------
# Local cloud at sunset at or under this, and the upstream light path open.
# Product thresholds: a clear western horizon is NPS's condition; how clear is
# ours. Merced discharge is a different drainage and is never used for flow.
FIREFALL_MAX_CLOUD = 25.0
FIREFALL_MIN_LIGHT_GATE = 0.75
FIREFALL_ACCESS_TERMS = ("firefall", "horsetail", "el capitan", "northside drive", "southside drive",
                         "yosemite valley")

# --- Monarchs -----------------------------------------------------------------
# Xerces: monarchs generally cannot fly below about 55 °F. Using a dawn
# forecast at or under that as "the clusters will still be hanging" is a
# product heuristic built on that statement, not a published rule.
MONARCH_DAWN_MAX_F = 55.0
MONARCH_DAWN_HOUR = 7


def _local(bundle):
    if not isinstance(bundle, dict):
        return None
    return bundle.get("local") or (bundle if "hourly" in bundle else None)


def _times(forecast):
    out = []
    for stamp in ((forecast or {}).get("hourly") or {}).get("time") or []:
        try:
            moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            moment = None
        if moment is not None and moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        out.append(moment)
    return out


def _value(forecast, key, index):
    series = ((forecast or {}).get("hourly") or {}).get(key) or []
    try:
        value = series[index]
    except (IndexError, TypeError):
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def clearing_after(forecast, after: datetime, now: datetime, hours: int = CLEARING_HORIZON_HOURS,
                   cloud_max: float = CLEARING_CLOUD) -> tuple[datetime, float] | None:
    """First forecast hour after ``after`` (and not in the past) that is clear.

    Only hours still ahead of ``now`` count: a clearing the forecast promised
    for yesterday afternoon is not a clearing forecast today.
    """
    start = max(after, now)
    for index, moment in enumerate(_times(forecast)):
        if moment is None or moment < start or moment > now + timedelta(hours=hours):
            continue
        cloud = _value(forecast, "cloud_cover", index)
        if cloud is not None and cloud <= cloud_max:
            return moment, cloud
    return None


def annotate_snow(rows, forecasts: dict, now: datetime) -> None:
    """Attach the clearing forecast to reported fresh snow.

    Snow is established by a dated report; the clearing by a current forecast
    at the same zone. The gate needs both (``eligibility._conditions``).
    """
    for item in rows:
        if item.phenomenon != "fresh_snow_clearing":
            continue
        forecast = _local((forecasts or {}).get(item.zone_id))
        observed = item.extra.get("observed_at")
        after = datetime.fromisoformat(observed) if observed else item.start
        found = clearing_after(forecast, after, now) if forecast else None
        item.extra["condition_states"] = {
            "Fresh snow": f"Reported {after:%d %b}" if observed else "Not reported",
            "Clearing": (f"Forecast {found[0]:%a %H:%M} UTC, {found[1]:.0f}% cloud" if found
                         else "No clearing forecast in the next 48 h" if forecast else "No forecast for this place"),
        }
        if found is None:
            item.extra.pop("clearing_at", None)
            continue
        item.extra["clearing_at"] = found[0].isoformat()
        item.extra["clearing_cloud"] = round(found[1], 1)
        item.start = found[0]
        item.end = found[0] + timedelta(hours=CLEARING_WINDOW_HOURS)
        item.extra["best_time_of_day"] = "As the sky clears, before the snow falls from the trees"


def _next_sunset(latitude, longitude, now, until):
    moment = now - timedelta(hours=2)
    while moment <= until:
        event = astronomy.sun_event(moment, math.radians(latitude), math.radians(longitude), rising=False)
        if event is not None and event >= now - timedelta(minutes=20) and event <= until:
            return event
        moment += timedelta(days=1)
    return None


def annotate_firefall(rows, forecasts: dict, now: datetime, park_alerts=None) -> None:
    """The evening conditions the firefall policy checks, at Yosemite.

    Alignment is the published mid-February window (the row's own dates).
    Water on Horsetail Fall comes only from a dated report - the row's
    evidence state; this never reads the Merced gauge. Light needs the local
    sky clear at sunset *and* the western light path open upstream, from
    upstream layers that are actually present and valid (a missing layer is
    unknown, never open). Park access is ``annotate_access``'s job; passing
    ``park_alerts`` here is a shortcut that treats them as a current,
    complete read.
    """
    bundle = (forecasts or {}).get("yosemite_valley") or {}
    local = _local(bundle)
    upstream = (bundle.get("upstream") or {}).get("sunset") if isinstance(bundle, dict) else None
    for item in rows:
        if item.phenomenon != "horsetail_firefall" or item.extra.get("precision", "peak") != "peak":
            continue
        end = min(item.end or item.start, now + timedelta(days=7))
        sunset = _next_sunset(item.latitude, item.longitude, max(now, item.start), end) if end >= now else None
        states = {"Alignment": "Inside the published mid-February window" if sunset else "Outside the window"}
        flow = item.extra.get("evidence_state") == "behavior_confirmed"
        states["Water on Horsetail Fall"] = ("Reported" if flow else
                                             "Unconfirmed: needs a dated report. Merced discharge is a different drainage and is not used.")
        for key in ("cloud_cover", "cloud_is_forecast", "light_path_gate", "firefall_sunset"):
            item.extra.pop(key, None)
        if sunset is not None:
            item.extra["firefall_sunset"] = sunset.isoformat()
            cloud = weather_scoring.layer_at(local, "cloud_cover", sunset)
            lead = (sunset - now).total_seconds() / 86400
            if cloud is not None:
                item.extra["cloud_cover"] = round(cloud, 1)
                item.extra["cloud_is_forecast"] = weather_scoring.cloud_is_scorable(lead)
                states["Local sky at sunset"] = f"{cloud:.0f}% cloud forecast"
            else:
                states["Local sky at sunset"] = "No valid forecast for sunset"
            low = weather_scoring.layer_at(upstream, "cloud_cover_low", sunset)
            mid = weather_scoring.layer_at(upstream, "cloud_cover_mid", sunset)
            gate = weather_scoring.light_path_gate_checked(low, mid)
            if gate is not None:
                item.extra["light_path_gate"] = round(gate, 2)
                states["Western light path"] = "Open" if gate >= FIREFALL_MIN_LIGHT_GATE else "Blocked upstream"
            else:
                missing = [name for name, value in (("low", low), ("mid", mid)) if value is None]
                states["Western light path"] = ("Not modelled: no upstream forecast" if not upstream else
                                                f"Unknown: upstream {' and '.join(missing)} cloud missing or invalid at sunset")
        item.extra["condition_states"] = states
    if park_alerts is not None:
        annotate_access([row for row in rows if row.phenomenon == "horsetail_firefall"],
                        park_alerts, now, 0, now)


def annotate_access(rows, park_alerts, fetched_at, failures: int, now: datetime) -> None:
    """Current NPS access for every occurrence whose phenomenon depends on it.

    Driven by the phenomenon and its place (``curation.access_requirement``),
    not by whether the Parks view is switched on. ``access_state`` is
    ``open`` only after a current, complete read that names no closure here;
    otherwise ``closed`` or ``unknown``. The gate blocks a closure and holds
    an unknown.
    """
    from . import curation, verification

    for item in rows:
        requirement = curation.access_requirement(item)
        for key in ("access_state", "access_detail", "access_blocked"):
            item.extra.pop(key, None)
        if requirement is None:
            continue
        park, terms = requirement
        state, detail = verification.access_state(park_alerts, fetched_at, failures, now, park, terms)
        item.extra["access_state"] = state
        item.extra["access_detail"] = detail
        if state == verification.ACCESS_CLOSED:
            item.extra["access_blocked"] = detail.removeprefix("Closure: ")
        states = dict(item.extra.get("condition_states") or {})
        states["Park access"] = detail
        item.extra["condition_states"] = states


def annotate_monarchs(rows, forecasts: dict, now: datetime, tz) -> None:
    """Tomorrow's dawn at the Pismo grove itself - never the home forecast."""
    forecast = _local((forecasts or {}).get("pismo_grove"))
    for item in rows:
        if item.phenomenon != "pismo_monarchs":
            continue
        for key in ("dawn_temp_f", "dawn_wind_ms", "dawn_precip_probability"):
            item.extra.pop(key, None)
        if not forecast:
            item.extra["condition_states"] = {"Dawn at the grove": "No forecast for the grove"}
            continue
        for index, moment in enumerate(_times(forecast)):
            if moment is None or moment <= now or moment - now > timedelta(hours=36):
                continue
            local = moment.astimezone(tz)
            if local.hour != MONARCH_DAWN_HOUR:
                continue
            celsius = _value(forecast, "temperature_2m", index)
            if celsius is None:
                item.extra["condition_states"] = {"Dawn at the grove": "No temperature in the forecast"}
                break
            item.extra["dawn_temp_f"] = round(celsius * 9 / 5 + 32, 1)
            wind = _value(forecast, "wind_speed_10m", index)
            rain = _value(forecast, "precipitation_probability", index)
            if wind is not None:
                item.extra["dawn_wind_ms"] = round(wind, 1)
            if rain is not None:
                item.extra["dawn_precip_probability"] = round(rain)
            item.extra["best_time_of_day"] = (
                f"Dawn {local:%a %H:%M}: {item.extra['dawn_temp_f']:.0f} °F forecast at the grove"
                + (f", wind {wind:.0f} m/s" if wind is not None else "")
                + (f", {rain:.0f}% chance of rain" if rain is not None else "") + ".")
            item.extra["condition_states"] = {
                "Dawn at the grove": f"{item.extra['dawn_temp_f']:.0f} °F (product heuristic: at or under {MONARCH_DAWN_MAX_F:.0f} °F)",
                "Wind and rain": "Shown for context; no threshold is claimed",
            }
            break
        else:
            item.extra["condition_states"] = {"Dawn at the grove": "No dawn hour in the forecast"}
