"""Outside sources that can actually confirm or contradict a plan.

No service publishes peak windows. Nobody serves "gray whale southbound peak =
5-25 January" as machine-readable data, so no amount of API integration will
verify the dates in ``phenomena``. Chasing that is chasing something that does
not exist.

What *can* be verified is narrower and more useful: the conditions a plan
depends on, and whether the place is even open.

- **NOAA CO-OPS tide predictions.** Free, no key, and authoritative - these are
  the official predictions, not a model of them. A grunion run starts an hour or
  two after a high tide, so without a tide table the night is knowable and the
  hour is a guess.
- **The National Park Service alerts API.** Free key. Road closures, area
  closures and permit changes, straight from the park. This is the one that
  stops a trip being wasted for a reason nobody could have inferred from a
  calendar: the window was right, the animals were there, and the road in was
  shut.

Request building and parsing only. The coordinator owns the HTTP and the quota
discipline, and both sources fail soft - a plan with no tide table says the hour
is unknown rather than inventing one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

NOAA_TIDES_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
NPS_ALERTS_URL = "https://developer.nps.gov/api/v1/alerts"

# NOAA requires an application identifier on every request.
NOAA_APPLICATION = "home-assistant-photography-events"

# Official CO-OPS stations covering the coastline this integration watches.
TIDE_STATIONS: dict[str, dict] = {
    "santa_barbara": {"station": "9411340", "name": "Santa Barbara", "latitude": 34.4083, "longitude": -119.6858},
    "port_san_luis": {"station": "9412110", "name": "Port San Luis", "latitude": 35.1767, "longitude": -120.7600},
    "monterey": {"station": "9413450", "name": "Monterey", "latitude": 36.6050, "longitude": -121.8883},
    "los_angeles": {"station": "9410660", "name": "Los Angeles", "latitude": 33.7200, "longitude": -118.2717},
}

# Park codes for the NPS-managed units in the planning calendar. Sequoia and
# Kings Canyon share one code because the Park Service administers them jointly.
NPS_PARK_CODES: dict[str, str] = {
    "channel_islands_np": "chis",
    "pinnacles_np": "pinn",
    "sequoia_np": "seki",
    "kings_canyon_np": "seki",
    "joshua_tree_np": "jotr",
    "yosemite_np": "yose",
    "death_valley_np": "deva",
    "devils_postpile_nm": "depo",
}

# Not everything in the calendar is a National Park Service unit, and the NPS
# API knows nothing about the ones that are not: Carrizo Plain is BLM and Giant
# Sequoia is Forest Service. Listing them here rather than leaving a silent gap,
# because "no closures reported" and "nothing can report closures here" are very
# different things to show somebody planning a drive.
NON_NPS_UNITS: dict[str, str] = {
    "carrizo_plain_nm": "Bureau of Land Management",
    "giant_sequoia_nm": "US Forest Service",
}


def closure_coverage(park_key: str) -> str | None:
    """Which agency runs a unit the NPS alerts feed cannot see."""
    return NON_NPS_UNITS.get(park_key)


# Alert categories that can end a trip rather than merely colour it.
BLOCKING_CATEGORIES = {"closure", "danger"}

# A grunion run begins roughly this long after the high tide.
GRUNION_LAG_MIN = timedelta(hours=1)
GRUNION_LAG_MAX = timedelta(hours=2)


@dataclass(frozen=True)
class TideEvent:
    """One predicted high or low water."""

    moment: datetime
    feet: float
    high: bool


@dataclass(frozen=True)
class ParkAlert:
    """One alert published by a park."""

    park_code: str
    title: str
    category: str
    description: str
    url: str

    @property
    def blocking(self) -> bool:
        return self.category.strip().lower() in BLOCKING_CATEGORIES


# --- NOAA tides -------------------------------------------------------------


def build_tide_request(station: str, start: date, end: date) -> tuple[str, dict]:
    """URL and parameters for high/low predictions at one station.

    ``interval=hilo`` returns only the turning points, which is all a shooting
    plan needs and a fraction of the payload of six-minute predictions.
    """
    return NOAA_TIDES_URL, {
        "product": "predictions",
        "application": NOAA_APPLICATION,
        "datum": "MLLW",
        "station": station,
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json",
        "begin_date": start.strftime("%Y%m%d"),
        "end_date": end.strftime("%Y%m%d"),
    }


def parse_tide_predictions(payload, tz=None) -> list[TideEvent]:
    """Turn a predictions payload into tide events.

    NOAA returns local station time without an offset (``lst_ldt``), so the
    caller supplies the zone. Getting that wrong shifts a run window by hours,
    which for a phenomenon lasting under an hour means missing it entirely.
    """
    if not isinstance(payload, dict):
        return []
    predictions = payload.get("predictions")
    if not isinstance(predictions, list):
        return []

    found: list[TideEvent] = []
    for entry in predictions:
        if not isinstance(entry, dict):
            continue
        moment = _parse_noaa_time(entry.get("t"), tz)
        feet = _as_float(entry.get("v"))
        kind = (entry.get("type") or "").strip().upper()
        if moment is None or feet is None or kind not in ("H", "L"):
            continue
        found.append(TideEvent(moment=moment, feet=feet, high=kind == "H"))
    return sorted(found, key=lambda item: item.moment)


def _parse_noaa_time(value, tz) -> datetime | None:
    if not isinstance(value, str):
        return None
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            moment = datetime.strptime(value.strip(), pattern)
        except ValueError:
            continue
        return moment.replace(tzinfo=tz) if tz else moment
    return None


def high_tides_on(tides: list[TideEvent], night: date) -> list[TideEvent]:
    """High waters on a given night, including the small hours after midnight."""
    return [
        tide
        for tide in tides
        if tide.high and (tide.moment.date() == night or (tide.moment.date() == night + timedelta(days=1) and tide.moment.hour < 4))
    ]


def grunion_run_window(tides: list[TideEvent], night: date) -> tuple[datetime, datetime] | None:
    """When to be standing on the sand, from the tide rather than a guess.

    Runs follow the *night-time* high tide, so a daytime high is no use however
    large it is - the fish come ashore in darkness. Returns None when the
    predictions do not cover the night, which is the honest answer rather than
    a plausible invented hour.
    """
    candidates = [tide for tide in high_tides_on(tides, night) if tide.moment.hour >= 19 or tide.moment.hour < 4]
    if not candidates:
        return None
    peak = max(candidates, key=lambda tide: tide.feet)
    return peak.moment + GRUNION_LAG_MIN, peak.moment + GRUNION_LAG_MAX


# --- NPS alerts -------------------------------------------------------------


def build_nps_alerts_request(park_codes: list[str], api_key: str, limit: int = 50) -> tuple[str, dict]:
    return NPS_ALERTS_URL, {
        "parkCode": ",".join(sorted(set(park_codes))),
        "limit": limit,
        "api_key": api_key,
    }


def parse_nps_alerts(payload) -> list[ParkAlert]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, list):
        return []

    found: list[ParkAlert] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        found.append(
            ParkAlert(
                park_code=(entry.get("parkCode") or "").strip().lower(),
                title=title,
                category=(entry.get("category") or "").strip(),
                description=(entry.get("description") or "").strip(),
                url=(entry.get("url") or "").strip(),
            )
        )
    return found


def alerts_for(alerts: list[ParkAlert], park_code: str, blocking_only: bool = True) -> list[ParkAlert]:
    """Alerts for one park, closures first."""
    code = (park_code or "").lower()
    matching = [alert for alert in alerts if alert.park_code == code]
    if blocking_only:
        matching = [alert for alert in matching if alert.blocking]
    return sorted(matching, key=lambda alert: (not alert.blocking, alert.title))


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
