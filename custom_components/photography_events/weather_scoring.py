"""Sunset and sunrise colour scoring from layered cloud data.

The Lovelace card had to infer cloud structure from a single aggregate
percentage, because that is all a Home Assistant weather entity exposes. Open-
Meteo publishes the decks separately, which lets this score the actual physics
instead of a proxy for it (see NOAA/SPC, "The Colors of Twilight and Sunset"):

  high cloud   the canvas. Cirrus at 5-10km catches light that has not yet
               crossed the murky boundary layer, which is what turns red.
  mid cloud    adds texture and depth, and can light up spectacularly.
  low cloud    the blocker. A stratus deck on the western horizon stops the
               light from ever getting underneath the higher cloud, and no
               amount of pretty cirrus above will save it.
  humidity     haze mutes saturation. Contrary to folklore, dirty air makes
               sunsets worse, not better.

Scoring is a pure function of a forecast dict so it can be unit tested without
network access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

# Hours either side of the event that describe the sky during the show.
SAMPLE_OFFSETS_HOURS = (-1, 0, 1)

# Hours before the event used to detect an unsettled spell that is clearing.
CLEARING_LOOKBACK_HOURS = (3, 4, 5, 6, 7, 8)


@dataclass
class SkyScore:
    """A 0-100 colour-potential score with the reasoning behind it."""

    score: int
    reasons: list[str] = field(default_factory=list)
    detail: dict[str, float] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        return ", ".join(self.reasons) if self.reasons else "no strong signals"


def _mean(values: list[float]) -> float | None:
    numeric = [v for v in values if isinstance(v, (int, float))]
    return sum(numeric) / len(numeric) if numeric else None


def _series(forecast: dict, key: str) -> list:
    return forecast.get("hourly", {}).get(key) or []


def _index_for(forecast: dict, moment: datetime) -> int | None:
    """Index of the hourly slot nearest the given moment."""
    times = _series(forecast, "time")
    if not times:
        return None
    target = moment.timestamp()
    best_index, best_delta = None, None
    for index, stamp in enumerate(times):
        try:
            parsed = datetime.fromisoformat(stamp)
        except (TypeError, ValueError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=moment.tzinfo)
        delta = abs(parsed.timestamp() - target)
        if best_delta is None or delta < best_delta:
            best_index, best_delta = index, delta
    # Beyond 90 minutes the slot no longer describes the event.
    if best_delta is None or best_delta > 5400:
        return None
    return best_index


def _sample(forecast: dict, key: str, index: int, offsets: tuple[int, ...]) -> list[float]:
    values = _series(forecast, key)
    out = []
    for offset in offsets:
        position = index + offset
        if 0 <= position < len(values) and isinstance(values[position], (int, float)):
            out.append(float(values[position]))
    return out


def score_sky(forecast: dict, event_time: datetime) -> SkyScore | None:
    """Score the colour potential of one sunset or sunrise."""
    index = _index_for(forecast, event_time)
    if index is None:
        return None

    high = _mean(_sample(forecast, "cloud_cover_high", index, SAMPLE_OFFSETS_HOURS))
    mid = _mean(_sample(forecast, "cloud_cover_mid", index, SAMPLE_OFFSETS_HOURS))
    low = _mean(_sample(forecast, "cloud_cover_low", index, SAMPLE_OFFSETS_HOURS))
    humidity = _mean(_sample(forecast, "relative_humidity_2m", index, SAMPLE_OFFSETS_HOURS))
    precip = _sample(forecast, "precipitation_probability", index, SAMPLE_OFFSETS_HOURS)
    precip_max = max(precip) if precip else 0.0

    if high is None and mid is None and low is None:
        return None

    score = 0.0
    reasons: list[str] = []

    # The canvas: high cloud catching light from below.
    if high is not None:
        if 30 <= high <= 70:
            score += 40
            reasons.append(f"{round(high)}% high cloud to catch the light")
        elif 15 <= high < 30 or 70 < high <= 85:
            score += 25
            reasons.append(f"{round(high)}% high cloud")
        else:
            score += 8
            reasons.append("little high cloud" if high < 15 else "high cloud thick enough to flatten out")

    # Mid cloud adds structure, until it becomes a second lid.
    if mid is not None:
        if 10 <= mid <= 50:
            score += 15
        elif 50 < mid <= 75:
            score += 8
        else:
            score += 2

    # The blocker. This is the gate: no clear western horizon, no show.
    if low is not None:
        if low < 10:
            score += 30
            reasons.append("clear horizon")
        elif low < 20:
            score += 22
            reasons.append("mostly clear horizon")
        elif low < 35:
            score += 10
        elif low < 60:
            score -= 10
            reasons.append(f"{round(low)}% low cloud may block the horizon")
        else:
            score -= 35
            reasons.append(f"{round(low)}% low cloud - the light will not get underneath")

    # Haze mutes colour.
    if humidity is not None:
        if humidity < 50:
            score += 10
            reasons.append("clean, dry air")
        elif humidity < 65:
            score += 5
        elif humidity >= 80:
            score -= 10
            reasons.append("hazy, humid air")

    if precip_max >= 50:
        score -= 25
        reasons.append("rain likely")
    elif precip_max >= 30:
        score -= 12
        reasons.append("showers around")

    if _has_clearing_trend(forecast, index, precip_max, low):
        score += 12
        reasons.append("clearing after an unsettled spell")

    final = int(max(0, min(100, round(score))))
    return SkyScore(
        score=final,
        reasons=reasons,
        detail={
            "cloud_high": round(high, 1) if high is not None else -1,
            "cloud_mid": round(mid, 1) if mid is not None else -1,
            "cloud_low": round(low, 1) if low is not None else -1,
            "humidity": round(humidity, 1) if humidity is not None else -1,
            "precipitation_probability": round(precip_max, 1),
        },
    )


def _has_clearing_trend(
    forecast: dict, index: int, precip_now: float, low_now: float | None
) -> bool:
    """Unsettled earlier in the day, genuinely better by the event.

    Both halves matter. Checking only that the day *was* unsettled credits a sky
    that is socked in from dawn to dusk, which is the opposite of the setup this
    is meant to reward.
    """
    if precip_now >= 25:
        return False
    lookback = tuple(-h for h in CLEARING_LOOKBACK_HOURS)
    earlier_precip = _sample(forecast, "precipitation_probability", index, lookback)
    earlier_low = _sample(forecast, "cloud_cover_low", index, lookback)

    dried_out = bool(earlier_precip) and max(earlier_precip) >= 35
    if low_now is None:
        return dried_out
    opened_up = bool(earlier_low) and max(earlier_low) >= 70 and low_now <= max(earlier_low) - 30
    return (dried_out and low_now < 60) or opened_up


def build_open_meteo_params(latitude: float, longitude: float, days: int = 3) -> dict:
    """Query parameters for the free, keyless Open-Meteo forecast endpoint."""
    return {
        "latitude": f"{latitude:.4f}",
        "longitude": f"{longitude:.4f}",
        "hourly": ",".join(
            (
                "cloud_cover",
                "cloud_cover_low",
                "cloud_cover_mid",
                "cloud_cover_high",
                "relative_humidity_2m",
                "precipitation_probability",
                "visibility",
            )
        ),
        "forecast_days": str(days),
        "timezone": "UTC",
    }
