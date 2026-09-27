"""Weather as a hazard gate, and weather as a subject that is only ever a watch.

Two jobs, kept apart:

1. **Safety.** Every opportunity gets one of four states against the NWS
   active-alert feed:

   - ``safe`` - the place was checked and nothing relevant is in effect;
   - ``caution`` - an advisory, watch or exposure-specific warning applies; the
     row may still be shown, with the instruction it implies;
   - ``unsafe`` - a warning that makes going a bad idea (severe thunderstorm,
     flash flood, winter storm, fire, extreme heat, tsunami...). It removes the
     row from Can't Miss however good it is. This is a photography planner, not
     a storm-chasing system;
   - ``unknown`` - the feed failed or went stale, or the place cannot be
     matched to an alert area. **Unknown is not safe.** Can't Miss holds any
     row that needs travel until the check can be made; the planner keeps it.

   Hazards depend on exposure. A High Surf Warning blocks a night on the beach
   and turns an exceptional-swell row into a strict viewpoint instruction
   (high, set-back ground; never beaches, rocks or jetties); it says nothing
   about a Carrizo elk morning. A Red Flag Warning is critical fire *weather*,
   not a fire: a caution with fire-weather instructions, not a block.

2. **Watch signals.** Forecast thunder or forecast snow followed by clearing
   can make a photograph, but a forecast is not an observation. These become
   background signals, never primary rows; a dated report is what promotes the
   curated phenomenon.

Alerts are matched to a location by the alert polygon when NWS supplies one,
otherwise by the county SAME code. Marine-zone alerts (Gale, Small Craft,
Special Marine) carry marine zone codes this table does not resolve; boat trips
therefore always say "check the marine forecast" rather than implying a
checked sea. A failed alert feed is never read as "no warnings".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .signals import BASIS_FORECAST, Signal
from .wildlife import haversine_km

# Exposures a curated phenomenon declares (curation.PhenomenonDefinition.exposure).
EXPOSURE_HOME = "home"          # at or beside the house; no travel
EXPOSURE_BEACH = "beach"        # on the sand or rocks, often at night
EXPOSURE_COASTAL = "coastal"    # bluffs, overlooks, boardwalks, piers
EXPOSURE_BOAT = "boat"          # on the water with an operator
EXPOSURE_MOUNTAIN = "mountain"  # Sierra roads and trails
EXPOSURE_DESERT = "desert"
EXPOSURE_GENERAL = "general"
_ALL = None

STATE_SAFE = "safe"
STATE_CAUTION = "caution"
STATE_UNSAFE = "unsafe"
STATE_UNKNOWN = "unknown"

# event -> (exposures it makes unsafe, or _ALL; exposures it is a caution for,
# or _ALL; what to say). An exposure in neither set ignores the alert.
# Reviewed against the NWS product list (weather.gov/help-map, NWSI 10-511/10-515).
_TRAVEL = frozenset({EXPOSURE_BEACH, EXPOSURE_COASTAL, EXPOSURE_BOAT, EXPOSURE_MOUNTAIN,
                     EXPOSURE_DESERT, EXPOSURE_GENERAL})
_SHORE = frozenset({EXPOSURE_BEACH, EXPOSURE_COASTAL})
HAZARDS: dict[str, tuple] = {
    # Life-threatening wherever you are: never send anyone into these.
    **{event: (_ALL, _ALL, "Do not go; this is not a storm-chasing system.") for event in (
        "Tornado Warning", "Severe Thunderstorm Warning", "Flash Flood Warning", "Flood Warning",
        "Winter Storm Warning", "Blizzard Warning", "Ice Storm Warning", "High Wind Warning",
        "Extreme Wind Warning", "Fire Warning", "Evacuation Immediate", "Dust Storm Warning",
        "Tsunami Warning", "Snow Squall Warning", "Civil Danger Warning", "Shelter In Place Warning",
        "Tropical Storm Warning", "Hurricane Warning", "Storm Surge Warning", "Hurricane Force Wind Warning")},
    # Heat: dangerous to be out in, not to glance at from the porch.
    "Excessive Heat Warning": (_TRAVEL, _ALL, "Dangerous heat; do not plan time outdoors away from shelter."),
    "Extreme Heat Warning": (_TRAVEL, _ALL, "Dangerous heat; do not plan time outdoors away from shelter."),
    "Avalanche Warning": (frozenset({EXPOSURE_MOUNTAIN}), _ALL, "Avalanche danger; stay off and below slopes."),
    # Water and shoreline.
    "Coastal Flood Warning": (_SHORE, _ALL, "Coastal flooding: stay off beaches, seawalls and low shore roads."),
    "High Surf Warning": (frozenset({EXPOSURE_BEACH}), frozenset({EXPOSURE_COASTAL, EXPOSURE_BOAT, EXPOSURE_HOME}),
                          "Photograph only from high, set-back ground - never on the beach, rocks or jetties."),
    "High Surf Advisory": ((), _SHORE | {EXPOSURE_BOAT},
                           "Large breaking waves: stay well above the wash line; never on rocks or jetties."),
    "Beach Hazards Statement": ((), _SHORE, "Sneaker waves and rip currents: stay above the wash line."),
    "Rip Current Statement": ((), _SHORE, "Rip currents: stay out of the water."),
    "Coastal Flood Advisory": ((), _SHORE, "Minor coastal flooding: low beaches and paths may be awash."),
    "Special Marine Warning": (frozenset({EXPOSURE_BOAT}), _SHORE, "Hazardous conditions on the water; trips will be cancelled."),
    "Gale Warning": (frozenset({EXPOSURE_BOAT}), (), "Gale on the water; no boat trip."),
    "Storm Warning": (frozenset({EXPOSURE_BOAT}), (), "Storm-force wind on the water; no boat trip."),
    "Small Craft Advisory": ((), frozenset({EXPOSURE_BOAT}), "Rough water; expect a hard ride or a cancelled trip."),
    # Fire weather is not a fire.
    "Red Flag Warning": ((), _TRAVEL, "Critical fire weather: no flame or sparks, don't park on dry grass, and check for new fires and closures."),
    "Fire Weather Watch": ((), _TRAVEL, "Fire weather possible; check for new fires and closures."),
    # Advisories and watches: tell the photographer, do not hide the row.
    **{event: ((), _ALL, note) for event, note in (
        ("Wind Advisory", "Strong gusts: secure the tripod; no drone."),
        ("Dense Fog Advisory", "Dense fog: slow, hazardous driving; the view may be gone."),
        ("Heat Advisory", "Heat: carry water; avoid midday exertion."),
        ("Winter Weather Advisory", "Snow or ice on the roads: carry chains; check road status."),
        ("Air Quality Alert", "Poor air quality."),
        ("Dense Smoke Advisory", "Dense smoke: poor air and visibility."),
        ("Flood Advisory", "Minor flooding: avoid low crossings."),
        ("Winter Storm Watch", "A winter storm is possible: recheck before leaving."),
        ("Flash Flood Watch", "Flash flooding possible: avoid washes and slot canyons."),
        ("Severe Thunderstorm Watch", "Severe storms possible: recheck before leaving."),
        ("Tornado Watch", "Tornadoes possible: recheck before leaving."),
        ("High Wind Watch", "High wind possible: recheck before leaving."),
        ("Tropical Storm Watch", "Tropical storm possible: recheck before leaving."),
        ("Hurricane Watch", "Hurricane possible: recheck before leaving."),
        ("Freeze Warning", "Below-freezing temperatures: dress for it; watch for ice."),
        ("Extreme Cold Warning", "Dangerous cold: dress for it; watch for ice."),
        ("Extreme Cold Watch", "Dangerous cold possible."),
    )},
}
# Kept for callers and tests that name the families directly.
BLOCKING_EVENTS = frozenset(event for event, (unsafe, _, _) in HAZARDS.items() if unsafe is _ALL)
CAUTION_EVENTS = frozenset(event for event, (unsafe, _, _) in HAZARDS.items() if unsafe is not _ALL)
SURF_EVENTS = frozenset({"High Surf Warning", "High Surf Advisory", "Beach Hazards Statement",
                         "Rip Current Statement", "Coastal Flood Advisory", "Coastal Flood Warning"})
# An alert older than this is not a current check (the feed refreshes hourly).
ALERTS_MAX_AGE_HOURS = 3

# Reference points for the places this integration sends people, with the
# county's six-digit SAME code (0 + state FIPS 06 + county FIPS). Used only when
# an alert has no polygon.
COUNTY_POINTS = (
    (34.742, -120.572, "006083"), (34.389, -119.502, "006083"), (34.585, -119.980, "006083"),
    (34.418, -119.670, "006083"), (34.758, -120.643, "006083"),
    (35.131, -120.635, "006079"), (35.666, -121.257, "006079"), (35.191, -119.793, "006079"),
    (35.178, -120.740, "006079"),
    (34.249, -119.264, "006111"), (34.725, -118.400, "006037"),
    (36.372, -121.902, "006053"), (36.605, -121.890, "006053"), (36.491, -121.183, "006069"),
    (36.565, -118.773, "006107"), (35.924, -118.585, "006107"), (36.788, -118.669, "006019"),
    (37.172, -122.222, "006087"), (36.505, -117.079, "006027"), (37.361, -118.400, "006027"),
    (37.227, -118.626, "006027"), (37.746, -119.594, "006043"), (37.783, -119.080, "006051"),
    (37.950, -119.220, "006051"), (37.630, -119.085, "006051"), (39.097, -120.032, "006017"),
    (38.750, -119.950, "006003"), (37.180, -120.600, "006047"), (38.156, -121.416, "006077"),
    (33.256, -116.375, "006073"), (32.860, -117.250, "006073"), (38.100, -122.950, "006041"),
    (39.421, -122.165, "006021"), (33.873, -115.901, "006065"),
)
COUNTY_MATCH_KM = 40.0


def compact_alert(feature: dict) -> dict | None:
    """Keep what the gate needs from one NWS GeoJSON feature."""
    if not isinstance(feature, dict):
        return None
    props = feature.get("properties") if isinstance(feature.get("properties"), dict) else {}
    if not props.get("event"):
        return None
    geocode = props.get("geocode") if isinstance(props.get("geocode"), dict) else {}
    return {
        "event": props.get("event"), "headline": props.get("headline") or props.get("event"),
        "severity": props.get("severity"), "areaDesc": props.get("areaDesc", ""),
        "onset": props.get("onset") or props.get("effective"), "ends": props.get("ends"),
        "expires": props.get("expires"), "same": list(geocode.get("SAME") or []),
        "geometry": feature.get("geometry") if isinstance(feature.get("geometry"), dict) else None,
        "url": props.get("@id") or props.get("id"),
    }


def county_for(latitude: float, longitude: float) -> str | None:
    best = min(COUNTY_POINTS, key=lambda row: haversine_km(latitude, longitude, row[0], row[1]))
    return best[2] if haversine_km(latitude, longitude, best[0], best[1]) <= COUNTY_MATCH_KM else None


def _in_ring(point, ring) -> bool:
    x, y = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            inside = not inside
    return inside


def in_geometry(latitude: float, longitude: float, geometry: dict) -> bool:
    """Point in a GeoJSON Polygon/MultiPolygon (outer rings, lon-lat order)."""
    kind = geometry.get("type")
    coords = geometry.get("coordinates") or []
    polygons = [coords] if kind == "Polygon" else coords if kind == "MultiPolygon" else []
    point = (longitude, latitude)
    for polygon in polygons:
        try:
            ring = [tuple(map(float, pair[:2])) for pair in polygon[0]]
        except (TypeError, ValueError, IndexError):
            continue
        if len(ring) >= 3 and _in_ring(point, ring):
            return True
    return False


def _time(value) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def alerts_at(alerts: list, latitude: float, longitude: float, start: datetime, end: datetime,
              now: datetime) -> tuple[list[dict], bool]:
    """Active alerts overlapping a place and time, and whether the place was checkable.

    Checkable means the place resolves to an alert county: only then does an
    empty result mean "no alerts here". A polygon from some other alert does
    not make an unlisted place checkable - county-only alerts would be missed.
    """
    county = county_for(latitude, longitude)
    found = []
    for alert in alerts or []:
        expires = _time(alert.get("ends")) or _time(alert.get("expires"))
        onset = _time(alert.get("onset"))
        if expires and (expires <= now or expires < start):
            continue
        if onset and onset > end:
            continue
        geometry = alert.get("geometry")
        if geometry:
            hit = in_geometry(latitude, longitude, geometry)
        else:
            hit = bool(county and county in (alert.get("same") or []))
        if hit:
            found.append(alert)
    return found, county is not None


def _rule(alert: dict) -> tuple:
    """The (unsafe, caution, note) rule for an alert, including unknown events."""
    event = alert.get("event", "")
    if event in HAZARDS:
        return HAZARDS[event]
    # An event this table has not reviewed: trust NWS's own severity.
    if (alert.get("severity") or "") in ("Extreme", "Severe"):
        return _ALL, _ALL, "Do not go until you have read it."
    return (), _ALL, ""


def _applies(exposures, exposure: str) -> bool:
    return exposures is _ALL or exposure in exposures


def safety(item, alerts: list | None, now: datetime, exposure: str = EXPOSURE_GENERAL) -> dict:
    """SAFE, CAUTION, UNSAFE or UNKNOWN for one opportunity, and what to say.

    ``alerts`` is None when the feed failed or is stale: that is UNKNOWN,
    never SAFE. ``travel`` says whether going there means leaving home; the
    eligibility gate holds a travel row whose safety is unknown.
    """
    travel = exposure != EXPOSURE_HOME and (getattr(item, "drive_hours", None) or 0) > 0.25
    base = {"unsafe": False, "notes": [], "checked": False, "travel": travel, "state": STATE_UNKNOWN}
    if exposure == EXPOSURE_BOAT:
        base["notes"] = ["Marine-zone warnings are not matched here: check the NWS coastal waters forecast and the operator before going."]
    if alerts is None:
        return {**base, "summary": "Safety not checked: NWS alerts are unavailable. Check warnings before leaving."}
    if item.latitude is None or item.longitude is None:
        return {**base, "summary": "Safety not checked: this location cannot be matched to NWS alerts."}
    end = item.end or item.start + timedelta(hours=2)
    active, checkable = alerts_at(alerts, item.latitude, item.longitude, item.start, end, now)
    notes, unsafe, caution = list(base["notes"]), False, False
    for alert in active:
        event = alert.get("event", "")
        blocks, warns, note = _rule(alert)
        if _applies(blocks, exposure):
            unsafe = True
            notes.insert(0, f"{event} in effect. {note}".strip())
        elif _applies(warns, exposure):
            caution = True
            notes.append(f"{event} in effect. {note}".strip())
    if unsafe:
        state, summary = STATE_UNSAFE, "Unsafe: " + notes[0]
    elif caution:
        state, summary = STATE_CAUTION, "Caution: " + "; ".join(note for note in notes if " in effect" in note)
    elif checkable:
        state, summary = STATE_SAFE, "No NWS warnings for this place and time."
    else:
        state, summary = STATE_UNKNOWN, "Safety not checked: this location is not matched to an NWS county. Check warnings yourself."
    return {"unsafe": unsafe, "notes": notes, "checked": checkable or unsafe or caution,
            "travel": travel, "state": state, "summary": summary}


def current_alerts(value, fetched_at: datetime | None, failures: int, now: datetime) -> list | None:
    """The alert list only while it is a current check; otherwise None (unknown)."""
    if fetched_at is None or failures or now - fetched_at > timedelta(hours=ALERTS_MAX_AGE_HOURS):
        return None
    return list(value or [])


# --- Forecast watch signals ------------------------------------------------------

THUNDER_CODES = range(95, 100)
SNOW_ZONES = ("yosemite_valley", "eastern_sierra", "sequoia_kings", "lake_tahoe")
# Product thresholds: roughly four inches of modelled snow in 24 h, then a
# mostly clear sky within 18 h. A watch, never a recommendation.
SNOW_CM = 10.0
CLEARING_CLOUD = 30.0
CLEARING_HOURS = 18


def _hourly(forecast):
    hourly = (forecast or {}).get("hourly") or {}
    times = []
    for stamp in hourly.get("time") or []:
        moment = _time(stamp)
        times.append(moment)
    return times, hourly


def _value(series, index):
    try:
        value = series[index]
    except (IndexError, TypeError):
        return None
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def watch_signals(forecasts: dict, zones: list[dict], now: datetime, horizon_hours: int = 72) -> list[Signal]:
    """Forecast setups worth knowing about, and not worth acting on alone."""
    found = []
    by_id = {zone["id"]: zone for zone in zones}
    for zone_id, bundle in (forecasts or {}).items():
        zone = by_id.get(zone_id)
        if zone is None:
            continue
        forecast = bundle.get("local") if isinstance(bundle, dict) and "local" in bundle else bundle
        times, hourly = _hourly(forecast)
        codes = hourly.get("weather_code") or []
        snow = hourly.get("snowfall") or []
        cloud = hourly.get("cloud_cover") or []
        window = [i for i, moment in enumerate(times) if moment and now <= moment <= now + timedelta(hours=horizon_hours)]
        thunder = next((i for i in window if (_value(codes, i) or 0) in THUNDER_CODES), None)
        if thunder is not None:
            found.append(Signal(kind="forecast", source="Open-Meteo model", subject="Thunderstorms possible",
                                category="rare_phenomena", basis=BASIS_FORECAST, valid_at=times[thunder],
                                latitude=zone["latitude"], longitude=zone["longitude"], place=zone["name"],
                                text="Forecast thunder is a watch only: no lightning detection is connected. Photograph lightning only from a vehicle or building, never from ridges or open ground.",
                                phenomena=["thunderstorm_watch"]))
        if zone_id in SNOW_ZONES and snow:
            for i in window:
                day_total = sum(_value(snow, j) or 0 for j in range(max(0, i - 23), i + 1))
                if day_total < SNOW_CM:
                    continue
                clear = next((j for j in range(i + 1, min(len(times), i + 1 + CLEARING_HOURS))
                              if (_value(cloud, j) if _value(cloud, j) is not None else 100) <= CLEARING_CLOUD), None)
                if clear is None:
                    continue
                found.append(Signal(kind="forecast", source="Open-Meteo model", subject="Fresh snow then clearing forecast",
                                    category="rare_phenomena", basis=BASIS_FORECAST, valid_at=times[clear],
                                    latitude=zone["latitude"], longitude=zone["longitude"], place=zone["name"],
                                    text=f"About {day_total:.0f} cm of modelled snow, then clearing. A model forecast, not observed accumulation; check chain controls and road status.",
                                    phenomena=["fresh_snow_clearing"]))
                break
    return found


def dawn_temperature(forecast: dict | None, now: datetime, tz, hour: int = 7) -> tuple[datetime, float] | None:
    """Forecast temperature at the next local dawn hour, in °C."""
    times, hourly = _hourly(forecast)
    temps = hourly.get("temperature_2m") or []
    for index, moment in enumerate(times):
        if moment is None or moment <= now:
            continue
        local = moment.astimezone(tz)
        if local.hour == hour and moment - now <= timedelta(hours=36):
            value = _value(temps, index)
            return (moment, value) if value is not None else None
    return None
