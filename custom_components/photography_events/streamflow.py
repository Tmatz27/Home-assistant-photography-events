"""Measured river discharge, as the honest proxy it is for a waterfall.

A moonbow needs spray, and firefall needs water on the face of Horsetail Fall.
Both were previously listed as unknowable - "current waterfall conditions. No
live confirmation connected." That was true of the individual falls and false of
the basin they sit in, which the USGS has gauged continuously since 1915.

**What this measures, and what it does not.** The gauge is the Merced River at
Happy Isles Bridge (USGS 11264500), which drains 181 square miles of the upper
basin above Yosemite Valley - Vernal and Nevada Falls and the high country
behind them. It is *not* a measurement of:

- **Yosemite Falls**, which is on Yosemite Creek, a separate and far smaller
  drainage that commonly stops altogether by late summer.
- **Horsetail Fall**, whose catchment is a small ephemeral pocket on top of
  El Capitan and which can be bone dry in a February when the Merced is healthy.

So this is a **basin snowmelt proxy**: it says whether the high country is
still melting into the valley, which is the single biggest factor in whether
those falls are running. It never says that either one of them is. Every string
this module produces is written to keep that distinction, because "the Merced is
at 900 cfs and rising" and "Yosemite Falls is flowing" are different claims and
only the first is measured.

No published flow-to-spray threshold is wired in, because none was found to
source. The reading and its trend are reported; a number that decided whether to
drive four hours would have to be invented, and inventing it is the failure this
project exists to avoid.

Request building and parsing only. The coordinator owns the HTTP.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

# The legacy instantaneous-values service. Free, no key, and the one every
# Yosemite flow page quotes.
USGS_IV_URL = "https://waterservices.usgs.gov/nwis/iv/"

# 00060 is discharge in cubic feet per second.
DISCHARGE_PARAMETER = "00060"

GAUGES: dict[str, dict] = {
    "yosemite_valley": {
        "site": "11264500",
        "name": "Merced River at Happy Isles Bridge",
        "drains": "the upper Merced basin above Yosemite Valley",
        "latitude": 37.7317,
        "longitude": -119.5583,
        "url": "https://waterdata.usgs.gov/monitoring-location/USGS-11264500/",
    },
}

# A reading older than this is not telling you about today.
MAX_READING_AGE = timedelta(hours=12)

# How much the discharge has to move across the fetched window before it counts
# as going anywhere. Relative rather than absolute on purpose: an absolute
# cubic-feet threshold for "the falls are running" would have to be invented,
# and this project does not invent thresholds.
TREND_BAND = 0.05


@dataclass(frozen=True)
class Streamflow:
    """One gauge's most recent discharge reading, with its own recent history."""

    site: str
    name: str
    drains: str
    url: str
    cfs: float
    observed_at: datetime
    window_peak_cfs: float
    window_low_cfs: float
    window_first_cfs: float

    @property
    def trend(self) -> str:
        """Where the discharge has moved across the fetched window.

        Measured from the start of the window to now, rather than against its
        peak. Against the peak, a reading two percent below the highest value of
        the last three days reads as "rising" when it is simply at the top - and
        the question a photographer is asking is whether there will be more
        water or less, not whether this hour beat the last one.
        """
        if self.window_first_cfs <= 0:
            return "unknown"
        ratio = self.cfs / self.window_first_cfs
        if ratio >= 1 + TREND_BAND:
            return "rising"
        if ratio <= 1 - TREND_BAND:
            return "falling"
        return "steady"

    def fresh(self, now: datetime) -> bool:
        return timedelta(0) <= now - self.observed_at <= MAX_READING_AGE

    def summary(self) -> str:
        """One sentence that never claims to have measured a waterfall."""
        return (
            f"{self.name} is running {round(self.cfs):,} cfs and {self.trend} "
            f"({self.observed_at:%-d %b %H:%M}). That gauges {self.drains}, "
            f"not the fall itself."
        )


def build_streamflow_request(site: str, period_hours: int = 72) -> tuple[str, dict]:
    """URL and parameters for one gauge's recent instantaneous discharge.

    A window rather than a single value, so the reading carries its own trend -
    600 cfs on the way up in May and 600 cfs on the way down in July mean
    opposite things about the weeks ahead.
    """
    return USGS_IV_URL, {
        "format": "json",
        "sites": site,
        "parameterCd": DISCHARGE_PARAMETER,
        "siteStatus": "active",
        "period": f"PT{int(period_hours)}H",
    }


def parse_streamflow(payload, gauge: dict) -> Streamflow | None:
    """Turn an instantaneous-values payload into one reading, or nothing.

    USGS marks missing intervals with a sentinel of -999999 rather than omitting
    them. Treating that as a discharge would report the Merced flowing
    backwards at a million cubic feet a second, so it is dropped like any other
    unparseable value.
    """
    if not isinstance(payload, dict):
        return None
    series = (payload.get("value") or {}).get("timeSeries")
    if not isinstance(series, list) or not series:
        return None

    readings: list[tuple[datetime, float]] = []
    for entry in series:
        if not isinstance(entry, dict):
            continue
        for block in entry.get("values") or []:
            if not isinstance(block, dict):
                continue
            for item in block.get("value") or []:
                if not isinstance(item, dict):
                    continue
                moment = _parse_time(item.get("dateTime"))
                value = _as_float(item.get("value"))
                if moment is None or value is None or value < 0:
                    continue
                readings.append((moment, value))

    if not readings:
        return None
    readings.sort(key=lambda pair: pair[0])
    latest_at, latest = readings[-1]
    values = [value for _moment, value in readings]

    return Streamflow(
        site=gauge["site"],
        name=gauge["name"],
        drains=gauge["drains"],
        url=gauge["url"],
        cfs=latest,
        observed_at=latest_at,
        window_peak_cfs=max(values),
        window_low_cfs=min(values),
        window_first_cfs=values[0],
    )


def _parse_time(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        moment = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
