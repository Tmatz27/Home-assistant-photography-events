"""Weather as a hazard gate, and weather as a subject that is only ever a watch.

Two jobs, kept apart:

1. **Safety.** An active NWS warning where an opportunity is - severe
   thunderstorm, flash flood, winter storm, fire, extreme heat - removes it
   from Can't Miss however good it is. This is a photography planner, not a
   storm-chasing system: it must never say "go now" into a warned area. The
   swell phenomenon is the one place a surf warning is expected, and there it
   becomes a strict viewpoint instruction instead of a block.

2. **Watch signals.** Forecast thunder or forecast snow followed by clearing
   can make a photograph, but a forecast is not an observation. These become
   background signals, never primary rows; a dated report is what promotes the
   curated phenomenon.

Alerts are matched to a location by the alert polygon when NWS supplies one,
otherwise by the county SAME code. A location this table cannot place says
"alerts not checked" rather than implying all clear. A failed alert feed is
reported through source health; it is never read as "no warnings".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .signals import BASIS_FORECAST, Signal
from .wildlife import haversine_km

BLOCKING_EVENTS = frozenset({
    "Tornado Warning", "Severe Thunderstorm Warning", "Flash Flood Warning", "Flood Warning",
    "Winter Storm Warning", "Blizzard Warning", "Ice Storm Warning", "High Wind Warning",
    "Extreme Wind Warning", "Fire Warning", "Evacuation Immediate", "Excessive Heat Warning",
    "Extreme Heat Warning", "Dust Storm Warning", "Tsunami Warning", "Coastal Flood Warning",
    "Avalanche Warning", "Snow Squall Warning", "Civil Danger Warning", "Shelter In Place Warning",
    "Tropical Storm Warning", "Hurricane Warning", "Special Marine Warning",
})
CAUTION_EVENTS = frozenset({
    "High Surf Warning", "High Surf Advisory", "Beach Hazards Statement", "Rip Current Statement",
    "Wind Advisory", "Dense Fog Advisory", "Heat Advisory", "Winter Weather Advisory",
    "Red Flag Warning", "Air Quality Alert", "Dense Smoke Advisory", "Flood Advisory",
    "Winter Storm Watch", "Flash Flood Watch", "Fire Weather Watch", "Severe Thunderstorm Watch",
    "High Wind Watch", "Small Craft Advisory", "Gale Warning", "Coastal Flood Advisory",
})
SURF_EVENTS = frozenset({"High Surf Warning", "High Surf Advisory", "Beach Hazards Statement",
                         "Rip Current Statement", "Coastal Flood Advisory", "Coastal Flood Warning"})

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
    """Active alerts overlapping a place and time, and whether the place was checkable."""
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
    checkable = county is not None or any(alert.get("geometry") for alert in alerts or [])
    return found, checkable


def safety(item, alerts: list | None, now: datetime) -> dict:
    """Whether an opportunity may be recommended, and what to say either way."""
    if alerts is None:
        return {"unsafe": False, "notes": [], "checked": False,
                "summary": "NWS alerts unavailable - check warnings before leaving."}
    if item.latitude is None or item.longitude is None:
        return {"unsafe": False, "notes": [], "checked": False, "summary": "Location not checked against NWS alerts."}
    end = item.end or item.start + timedelta(hours=2)
    active, checkable = alerts_at(alerts, item.latitude, item.longitude, item.start, end, now)
    swell = getattr(item, "phenomenon", "") == "exceptional_swell"
    notes, unsafe = [], False
    for alert in active:
        event = alert.get("event", "")
        if swell and event in SURF_EVENTS:
            notes.append(f"{event}: photograph only from high, set-back ground - never on the beach, rocks or jetties.")
        elif event in BLOCKING_EVENTS:
            unsafe = True
            notes.append(f"{event} in effect. Do not go; this is not a storm-chasing system.")
        elif event in CAUTION_EVENTS:
            notes.append(f"{event} in effect.")
    summary = ("Unsafe: " + notes[0]) if unsafe else ("; ".join(notes) if notes else
               ("No NWS warnings for this place and time." if checkable else "Location not matched to an NWS county; check warnings yourself."))
    return {"unsafe": unsafe, "notes": notes, "checked": checkable, "summary": summary}


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
