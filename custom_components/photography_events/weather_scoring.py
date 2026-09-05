"""Sunset and sunrise scoring, built around where the light actually comes from.

The model this replaced scored a three-hour average of the cloud decks directly
above the tripod. That is the wrong question, and it produced exactly the wrong
answer on the Central Coast's most common evening: 55% cirrus overhead, a clear
patch of sky above your head, and a solid marine layer sitting 200km out over
the Pacific. It scored in the eighties. Nothing happened, because the sunlight
never got underneath the cirrus - it was absorbed by a stratus deck far to the
west, over the ocean, where nobody was looking.

That is the physics this scores instead. At sunset the beam lighting a cloud at
height ``h`` above you grazes the surface roughly ``sqrt(2 * R * h)`` away
toward the sun: about 140km for a low deck, 230km for mid-level cloud, over
300km for cirrus. So a sunset has two separate requirements in two separate
places, and conflating them is what makes a scoring model unreliable:

  **the canvas**, overhead - cloud to catch the light. High cirrus is the best
  of it, mid-level adds depth, and even a solid low deck lights up from
  underneath. No cloud at all is not a great sunset; it is a plain one.

  **the light path**, upstream - a gap on the horizon several hundred
  kilometres toward the sun. This one is a gate rather than a bonus. If it is
  shut, nothing above you matters, however beautiful.

Those two are combined multiplicatively for that reason. Clarity - aerosol
load, visibility, surface humidity - then decides how saturated the colour is
once the light does arrive; it moves the score by up to about a third, but it
can never rescue a blocked path or an empty sky.

When no upstream forecast is available the local low deck stands in for the
light path, which is the old behaviour, and the score is capped and labelled so
a number built on a proxy is never presented as one built on the real thing.

Scoring is a pure function of forecast dicts, so the whole model is unit
testable without network access.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from . import astronomy as astro

# --- Where the beam grazes the surface --------------------------------------
#
# One probe per direction per zone. The exact figure is a compromise: the
# blocking deck can be anywhere from about 120km (low stratus) to 320km (the
# path to cirrus), and a single sample at 200km sits in the middle of that and
# catches the offshore marine layer, which is what actually kills sunsets here.
LIGHT_PATH_KM = 200.0

# Hours either side of the event that describe the sky during the show.
SAMPLE_OFFSETS_HOURS = (-1, 0, 1)

# Hours before the event used to detect an unsettled spell that is clearing.
CLEARING_LOOKBACK_HOURS = (3, 4, 5, 6, 7, 8)

# The top of the scale is reserved for the post-frontal setup - the sky
# breaking up after rain - because that is genuinely the best it gets, and a
# scale whose maximum is reachable on an ordinary good evening cannot tell you
# when to drop what you are doing.
MAX_BASE_SCORE = 98.0
CLEARING_BONUS = 8.0

# A score built on the local deck instead of a real upstream forecast cannot
# honestly claim the light path is open, so it is not allowed near the top.
LOCAL_ONLY_CEILING = 88

# "Just right" is a comparison, not a threshold. A sky is a standout when it is
# good in absolute terms *and* nothing in the forecast window is better - which
# is the actual question behind "should I go tonight".
STANDOUT_MIN_SCORE = 82
STANDOUT_MARGIN = 3

# Trapezoid response curves: (rises from, full from, full to, falls to).
CANVAS_HIGH = (8.0, 28.0, 68.0, 92.0)
CANVAS_MID = (5.0, 20.0, 55.0, 88.0)
CANVAS_LOW = (10.0, 25.0, 100.0, 101.0)
MID_CONTRIBUTION = 0.45
LOW_CONTRIBUTION = 0.25
# A cloudless sky is still a sunset. It is not a photograph.
CANVAS_FLOOR = 0.04

# Above this much blocking cloud upstream, the light path is shut.
PATH_OPEN_BELOW = 20.0
PATH_SHUT_ABOVE = 88.0
PATH_SHUT_GATE = 0.10


@dataclass
class SkyScore:
    """A 0-100 colour-potential score with the reasoning behind it."""

    score: int
    reasons: list[str] = field(default_factory=list)
    detail: dict[str, float] = field(default_factory=dict)
    # The single component holding the score down, so a card can say why.
    limited_by: str = ""
    # ``modelled`` when a real upstream forecast decided the light path,
    # ``local`` when the deck overhead had to stand in for it.
    light_path: str = "local"
    # Set by :func:`mark_standouts` once the whole window has been scored.
    standout: bool = False

    @property
    def summary(self) -> str:
        return ", ".join(self.reasons) if self.reasons else "no strong signals"


# --- Response curves --------------------------------------------------------


def _band(value: float, rise_from: float, full_from: float, full_to: float, fall_to: float) -> float:
    """Trapezoid: 0 below ``rise_from``, 1 across the plateau, 0 above ``fall_to``."""
    if value <= rise_from or value >= fall_to:
        return 0.0
    if value < full_from:
        return (value - rise_from) / (full_from - rise_from)
    if value <= full_to:
        return 1.0
    return (fall_to - value) / (fall_to - full_to)


def _ramp(value: float, best: float, worst: float, floor: float = 0.0) -> float:
    """1.0 at ``best``, ``floor`` at ``worst``, straight line between."""
    if best < worst:
        if value <= best:
            return 1.0
        if value >= worst:
            return floor
    else:
        if value >= best:
            return 1.0
        if value <= worst:
            return floor
    return floor + (1.0 - floor) * abs(worst - value) / abs(worst - best)


def _top_up(base: float, addition: float, weight: float) -> float:
    """Add a secondary contribution to what the primary left unused."""
    return base + (1.0 - base) * weight * addition


def canvas_strength(high: float | None, mid: float | None, low: float | None) -> float:
    """How much there is up there for the light to land on, 0-1.

    High cloud is the canvas proper: it sits above the murk, so the light
    reaching it has not been filtered through the boundary layer and it is what
    goes red. Mid-level cloud adds depth. A low deck counts too - lit from
    underneath through a horizon gap it is spectacular - but it contributes
    least, because that gap has to be exactly right and usually is not.
    """
    strength = _band(high, *CANVAS_HIGH) if high is not None else 0.0
    if mid is not None:
        strength = _top_up(strength, _band(mid, *CANVAS_MID), MID_CONTRIBUTION)
    if low is not None:
        strength = _top_up(strength, _band(low, *CANVAS_LOW), LOW_CONTRIBUTION)
    return max(CANVAS_FLOOR, min(1.0, strength))


def light_path_gate(low: float | None, mid: float | None) -> float:
    """Whether the beam gets through, 0-1.

    Low cloud blocks outright. Mid-level cloud only blocks once it is more than
    broken, because a beam at that grazing angle threads gaps a satellite would
    still call cloudy.
    """
    if low is None and mid is None:
        return 1.0
    blocked = (low or 0.0) + 0.6 * max(0.0, (mid or 0.0) - 45.0)
    if blocked <= PATH_OPEN_BELOW:
        return 1.0
    if blocked >= PATH_SHUT_ABOVE:
        return PATH_SHUT_GATE
    span = PATH_SHUT_ABOVE - PATH_OPEN_BELOW
    return 1.0 - (1.0 - PATH_SHUT_GATE) * (blocked - PATH_OPEN_BELOW) / span


def clarity_factor(aod: float | None, visibility: float | None, humidity: float | None) -> tuple[float, str]:
    """How saturated the colour will be, 0-1, and what is limiting it.

    Contrary to the folklore about pollution making sunsets better, aerosol
    scatters the short wavelengths that give a sunset its range and leaves a
    flat orange smear. Aerosol optical depth is the direct measurement of that
    and is weighted highest; visibility is the near-field version of the same
    thing. Surface humidity is weighted lowest deliberately - marine air on
    this coast is humid on the clearest evenings of the year, and penalising it
    hard would suppress exactly the sunsets worth driving to.
    """
    terms: list[tuple[float, float, str]] = []
    if aod is not None:
        terms.append((_ramp(aod, 0.08, 0.60, 0.12), 0.45, "heavy aerosol haze"))
    if visibility is not None:
        terms.append((_ramp(visibility, 25000.0, 4000.0, 0.12), 0.35, "poor visibility"))
    if humidity is not None:
        terms.append((_ramp(humidity, 60.0, 97.0, 0.30), 0.15, "very humid air"))
    if not terms:
        return 0.85, ""

    total_weight = sum(weight for _, weight, _ in terms)
    value = sum(term * weight for term, weight, _ in terms) / total_weight
    worst = min(terms, key=lambda item: item[0])
    return value, worst[2] if worst[0] < 0.6 else ""


# --- Forecast plumbing ------------------------------------------------------


def _mean(values: list[float]) -> float | None:
    numeric = [v for v in values if isinstance(v, (int, float))]
    return sum(numeric) / len(numeric) if numeric else None


def _series(forecast: dict, key: str) -> list:
    if not isinstance(forecast, dict):
        return []
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


def _at(forecast: dict | None, key: str, moment: datetime) -> float | None:
    """Mean of one variable across the show, or None when it is not available."""
    if not forecast:
        return None
    index = _index_for(forecast, moment)
    if index is None:
        return None
    return _mean(_sample(forecast, key, index, SAMPLE_OFFSETS_HOURS))


# --- The score --------------------------------------------------------------


def score_sky(
    forecast: dict,
    event_time: datetime,
    upstream: dict | None = None,
    air_quality: dict | None = None,
) -> SkyScore | None:
    """Score the colour potential of one sunset or sunrise.

    ``upstream`` is the forecast for the point roughly 200km toward the sun,
    where the light path is decided. Passing it is what makes the score
    trustworthy; omitting it falls back to the deck overhead and says so.
    """
    index = _index_for(forecast, event_time)
    if index is None:
        return None

    high = _mean(_sample(forecast, "cloud_cover_high", index, SAMPLE_OFFSETS_HOURS))
    mid = _mean(_sample(forecast, "cloud_cover_mid", index, SAMPLE_OFFSETS_HOURS))
    low = _mean(_sample(forecast, "cloud_cover_low", index, SAMPLE_OFFSETS_HOURS))
    humidity = _mean(_sample(forecast, "relative_humidity_2m", index, SAMPLE_OFFSETS_HOURS))
    visibility = _mean(_sample(forecast, "visibility", index, SAMPLE_OFFSETS_HOURS))
    precip = _sample(forecast, "precipitation_probability", index, SAMPLE_OFFSETS_HOURS)
    precip_max = max(precip) if precip else 0.0
    aod = _at(air_quality, "aerosol_optical_depth", event_time)

    if high is None and mid is None and low is None:
        return None

    reasons: list[str] = []
    canvas = canvas_strength(high, mid, low)

    upstream_low = _at(upstream, "cloud_cover_low", event_time)
    upstream_mid = _at(upstream, "cloud_cover_mid", event_time)
    if upstream_low is not None or upstream_mid is not None:
        gate = light_path_gate(upstream_low, upstream_mid)
        source = "modelled"
    else:
        # No upstream forecast. The deck overhead is the only proxy available,
        # and it is a poor one - it is the reason the old model kept promising
        # sunsets that the marine layer had already eaten.
        gate = light_path_gate(low, None)
        source = "local"

    clarity, clarity_problem = clarity_factor(aod, visibility, humidity)

    base = MAX_BASE_SCORE * (canvas ** 0.85) * gate * (0.70 + 0.30 * clarity)

    if precip_max >= 60:
        base *= 0.45
    elif precip_max >= 35:
        base *= 0.75

    clearing = _has_clearing_trend(forecast, index, precip_max, low)
    if clearing:
        base += CLEARING_BONUS

    # Whatever is costing the most is what somebody actually wants told.
    limited_by = ""
    if gate < 0.55:
        where = f"{round(upstream_low)}% low cloud" if upstream_low is not None else "low cloud"
        limited_by = (
            f"the light path is blocked - {where} about {round(LIGHT_PATH_KM)}km toward the sun"
            if source == "modelled"
            else f"{round(low or 0)}% low cloud on the horizon"
        )
    elif canvas < 0.35:
        limited_by = "not enough cloud up there to catch anything"
    elif precip_max >= 35:
        limited_by = "rain over the top of it"
    elif clarity < 0.6 and clarity_problem:
        limited_by = clarity_problem

    if high is not None and _band(high, *CANVAS_HIGH) >= 0.75:
        reasons.append(f"{round(high)}% high cloud to catch the light")
    if gate >= 0.85:
        reasons.append("clear light path to the horizon" if source == "modelled" else "clear horizon")
    if clarity >= 0.85:
        reasons.append("clean, dry air")
    if clearing:
        reasons.append("clearing after an unsettled spell")
    if limited_by:
        reasons.append(limited_by)

    final = int(max(0, min(100, round(base))))
    if source == "local":
        final = min(final, LOCAL_ONLY_CEILING)

    return SkyScore(
        score=final,
        reasons=reasons,
        detail={
            "cloud_high": round(high, 1) if high is not None else -1,
            "cloud_mid": round(mid, 1) if mid is not None else -1,
            "cloud_low": round(low, 1) if low is not None else -1,
            "upstream_low": round(upstream_low, 1) if upstream_low is not None else -1,
            "upstream_mid": round(upstream_mid, 1) if upstream_mid is not None else -1,
            "humidity": round(humidity, 1) if humidity is not None else -1,
            "visibility_m": round(visibility) if visibility is not None else -1,
            "aerosol_optical_depth": round(aod, 3) if aod is not None else -1,
            "precipitation_probability": round(precip_max, 1),
            "canvas": round(canvas, 3),
            "light_path_gate": round(gate, 3),
            "clarity": round(clarity, 3),
        },
        limited_by=limited_by,
        light_path=source,
    )


def mark_standouts(scores: list[SkyScore]) -> list[SkyScore]:
    """Flag the skies that are as good as it is going to get.

    A fixed threshold answers "is this a good sunset". The question actually
    being asked is "is this the one to go out for", and that is comparative: an
    85 is worth rearranging an evening for when the rest of the week is in the
    fifties, and is worth ignoring when tomorrow is a 96. Everything within a
    few points of the best is flagged, so a run of good nights all get marked
    rather than the model picking an arbitrary winner between them.
    """
    usable = [item for item in scores if item.score >= STANDOUT_MIN_SCORE]
    if not usable:
        for item in scores:
            item.standout = False
        return scores
    best = max(item.score for item in usable)
    for item in scores:
        item.standout = item.score >= STANDOUT_MIN_SCORE and item.score >= best - STANDOUT_MARGIN
    return scores


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


# --- Request building -------------------------------------------------------

OPEN_METEO_HOURLY = (
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "relative_humidity_2m",
    "precipitation_probability",
    "visibility",
)


def build_open_meteo_params(latitude, longitude, days: int = 3) -> dict:
    """Query parameters for the free, keyless Open-Meteo forecast endpoint.

    Accepts either one coordinate or a sequence of them. Open-Meteo answers a
    multi-coordinate request with a list of forecasts in the order asked, which
    is how a zone and its upstream probes are fetched as one call rather than
    three.
    """
    return {
        "latitude": _coords(latitude),
        "longitude": _coords(longitude),
        "hourly": ",".join(OPEN_METEO_HOURLY),
        "forecast_days": str(days),
        "timezone": "UTC",
    }


def build_air_quality_params(latitude, longitude, days: int = 3) -> dict:
    """Aerosol load from Open-Meteo's air quality API - free, keyless, same shape.

    Aerosol optical depth is the difference between a sunset that holds magenta
    and one that goes flat orange, and no weather forecast carries it.
    """
    return {
        "latitude": _coords(latitude),
        "longitude": _coords(longitude),
        "hourly": "aerosol_optical_depth,dust",
        "forecast_days": str(days),
        "timezone": "UTC",
    }


def light_path_probes(latitude: float, longitude: float, moment: datetime) -> dict[str, tuple[float, float]]:
    """Where to sample the light path for one day's sunset and sunrise.

    Two points, because the geometry is mirrored: the sunset beam arrives from
    the west and the sunrise beam from the east, so a single probe would score
    one of them against weather in entirely the wrong place. The bearing is the
    sun's own azimuth at the event, which moves through about sixty degrees
    across the year on this coast - far too much to approximate with a fixed
    compass point.
    """
    lat_rad = math.radians(latitude)
    lon_rad = math.radians(longitude)
    probes: dict[str, tuple[float, float]] = {}
    for key, rising in (("sunset", False), ("sunrise", True)):
        event = astro.sun_event(moment, lat_rad, lon_rad, rising=rising)
        if event is None:
            continue
        bearing = astro.sun_azimuth(event, lat_rad, lon_rad)
        probes[key] = astro.offset_point(latitude, longitude, bearing, LIGHT_PATH_KM)
    return probes


def _coords(value) -> str:
    if isinstance(value, (list, tuple)):
        return ",".join(f"{float(item):.4f}" for item in value)
    return f"{float(value):.4f}"


def split_multi_location(payload) -> list[dict]:
    """Normalise Open-Meteo's answer, which is a list only when asked for many."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []
