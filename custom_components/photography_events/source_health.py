"""Feed health is separate from evidence: a broken feed is not a quiet season.

Never release an evidence ceiling here. A retained observation keeps its real
date and can expire even while a feed is broken. Geometry also remains geometry
when the cloud model fails; only its conditions assessment is degraded.
"""

from datetime import timedelta

from .phenomena import EVIDENCE_STATIC
from .const import CATEGORY_ASTRO

IMPACTS = {
    "streamflow": "Recent Merced basin readings are missing; waterfall flow remains unconfirmed.",
    "weather": "Cloud comparisons and sunset light-path assessments may be incomplete.",
    "air_quality": "Sunset clarity falls back to humidity and visibility.",
    "ebird": "Recent notable bird reports may be missing.",
    "inaturalist": "Recent wildlife sightings and species corroboration may be missing.",
    "theodore_payne": "Wildflower reports may be missing; season dates alone do not confirm blooms.",
    "desertusa": "Desert bloom reports may be missing; season dates alone do not confirm blooms.",
    "california_fall_color": "Autumn colour reports may be missing; calendar estimates remain unconfirmed.",
    "grunion": "Published grunion run dates cannot be refreshed.",
    "ndbc": "Offshore wave observations may be missing or old.",
    "cdip": "Experimental coastal wave forecasts may be missing or old.",
    "surf_alerts": "NWS warnings cannot be checked; Can't Miss rows say so instead of implying all clear.",
    "sunsetwx": "Sunset quality falls back to the built-in local model.",
    "ebird_species": "Condor, eagle, crane and goose counts may be missing from the bird views.",
    "condor_reports": "Dated whale-watch trip reports may be missing.",
    "aurora": "The short-term regional aurora assessment cannot be refreshed.",
    "tides": "Tide predictions for coastal events cannot be refreshed.",
    "park_alerts": "Park access and closure information cannot be refreshed.",
    "routing": "Drive times use retained routes or approximate estimates.",
}


def snapshot(sources, enabled, now):
    """Expose disabled, waiting, healthy, failed and stale states distinctly."""
    result = {}
    for key, source in sources.items():
        if key == "field_reports":  # Its individually monitored hotlines are more useful.
            continue
        active = key in enabled
        stale = (active and key != "routing" and source.fetched_at is not None
                 and now - source.fetched_at > timedelta(minutes=max(60, source.min_interval_minutes * 3)))
        state = ("disabled" if not active else "failed" if source.failures else
                 "stale" if stale else "ok" if source.fetched_at else "waiting")
        result[key] = {**source.status(), "enabled": active, "state": state,
                       "impact": IMPACTS.get(key, ""), "stale": bool(stale)}
    return result


# A source's role for one opportunity decides what its outage may do.
#
# - required: the phenomenon's own condition cannot be assessed without it; an
#   outage removes the row from Can't Miss (the planner still lists it).
# - preferred: a better source with a working fallback. Its outage is shown as
#   "fallback in use" and never blocks - SunsetWx failing must not erase a
#   sunset the local model can still assess on its own terms.
# - optional: supporting evidence. Dated reports expire by themselves, so a
#   dead sighting feed only means fewer confirmations, never a false one.
# - safety: the NWS alert feed. Its outage is handled by the safety gate
#   (unknown safety), not here, so it is not double-counted.
REQUIRED = "required"
PREFERRED = "preferred"
OPTIONAL = "optional"
SAFETY = "safety"

FALLBACK_NOTES = {
    "sunsetwx": "SunsetWx unavailable; the built-in local model decided this sunset.",
}


def dependency_roles(item) -> dict[str, str]:
    """{source: role} for the feeds that can actually help this opportunity."""
    category = item.category
    phenomenon = getattr(item, "phenomenon", "") or ""
    extra = item.extra
    if item.key.startswith("moonbow-") or phenomenon == "moonbow":
        # The clear-sky condition needs the forecast; the Merced reading is
        # candidate context and never proves spray (see streamflow.py).
        return {"weather": REQUIRED, "streamflow": OPTIONAL}
    if phenomenon in ("horsetail_firefall", "fresh_snow_clearing"):
        # Before the static check: firefall's window is a static estimate,
        # but its sunset condition is read from the forecast.
        return {"weather": REQUIRED}
    if extra.get("evidence") == EVIDENCE_STATIC:
        return {}
    if category == CATEGORY_ASTRO:
        if item.key.startswith("eclipse-"):
            return {}  # This builder currently computes geometry, not cloud.
        if "aurora" in item.key:
            return {"aurora": REQUIRED}
        return {"weather": REQUIRED}
    if category == "sunset":
        if extra.get("provider_quality"):
            # SunsetWx decided; the local model is comparison only.
            return {"sunsetwx": REQUIRED, "weather": OPTIONAL, "air_quality": OPTIONAL}
        return {"weather": REQUIRED, "air_quality": OPTIONAL, "sunsetwx": PREFERRED}
    if category == "waves":
        if phenomenon in ("king_tide", "minus_tide"):
            return {"tides": OPTIONAL}
        if extra.get("evidence_state") == "measured":
            return {"ndbc": REQUIRED, "cdip": OPTIONAL, "surf_alerts": SAFETY}
        return {"cdip": REQUIRED, "ndbc": OPTIONAL, "surf_alerts": SAFETY}
    if category == "blooms":
        return {"theodore_payne": OPTIONAL, "desertusa": OPTIONAL}
    if category == "foliage":
        return {"california_fall_color": OPTIONAL}
    if category == "parks":
        return {"park_alerts": OPTIONAL}
    if category == "birds":
        return {"ebird": OPTIONAL, "ebird_species": OPTIONAL, "inaturalist": OPTIONAL}
    if category == "marine":
        return {"inaturalist": OPTIONAL, "condor_reports": OPTIONAL}
    if category == "mammals":
        return {"inaturalist": OPTIONAL}
    if category == "rare_phenomena" and "grunion" in item.key:
        return {"grunion": REQUIRED, "tides": OPTIONAL}
    if category == "rare_phenomena" and "monarch" in item.key:
        # The cold-dawn condition is a forecast at the grove.
        return {"weather": REQUIRED, "inaturalist": OPTIONAL}
    return {}


def dependencies(item):
    """Only feeds that can actually help this opportunity; no imaginary wiring."""
    return set(dependency_roles(item))


# --- Weather, per forecast point ------------------------------------------------
#
# The forecast is fetched one request per point on purpose, so one bad
# response costs one place. Health has to follow the same grain: a failed Lake
# Tahoe request once marked the whole weather source failed, and that blocked a
# valid Vandenberg sunset whose own forecast was fine. The global state stays as
# a summary; a row is gated on the points it actually consumed.

WEATHER_POINT_STALE_MINUTES = 180


def weather_points(item) -> list[str]:
    """The forecast points an opportunity's condition was read from."""
    phenomenon = getattr(item, "phenomenon", "") or ""
    if phenomenon in ("sunset_local", "full_moon_closest", "full_moon"):
        return ["home"]
    if phenomenon in ("horsetail_firefall", "moonbow") or item.key.startswith("moonbow-"):
        return ["yosemite_valley"]
    if phenomenon == "pismo_monarchs" or (item.category == "rare_phenomena" and "monarch" in item.key):
        return ["pismo_grove"]
    if phenomenon in ("milky_way", "meteor_major", "meteor_minor", "fresh_snow_clearing"):
        return [item.zone_id]
    return []


def point_health(points: dict, now) -> dict:
    """{point: "ok" | "failed" | "stale" | "waiting"} from per-point fetch records."""
    result = {}
    for point, record in (points or {}).items():
        fetched = record.get("fetched_at")
        if record.get("failed"):
            result[point] = "failed"
        elif fetched is None:
            result[point] = "waiting"
        elif now - fetched > timedelta(minutes=WEATHER_POINT_STALE_MINUTES):
            result[point] = "stale"
        else:
            result[point] = "ok"
    return result


# --- Assessment coverage -------------------------------------------------------
#
# Which sources must have answered before an empty Can't Miss list may be
# called a quiet week, per enabled category. These are the feeds that *build*
# or *confirm* the Can't Miss-capable phenomena of that category; if one is
# down, "nothing qualifies" was not established. The NWS feed and, when used,
# the NPS feed apply to every category.
ASSESSMENT_SOURCES = {
    CATEGORY_ASTRO: ("weather", "aurora"),
    "sunset": ("weather",),
    "rare_phenomena": ("weather",),
    "waves": ("ndbc",),
    "marine": ("inaturalist", "condor_reports"),
    "mammals": ("inaturalist",),
    "birds": ("ebird", "ebird_species"),
    "blooms": ("theodore_payne", "desertusa"),
    "foliage": ("california_fall_color",),
}
ASSESSMENT_ALWAYS = ("surf_alerts", "park_alerts")
# Forecast points each category's assessment reads.
ASSESSMENT_POINTS = {"sunset": ("home",), "rare_phenomena": ("yosemite_valley", "pismo_grove")}


def assessment_coverage(health: dict, categories, points: dict | None = None,
                        sunset_provider_current: bool = False) -> dict:
    """``{"state": "complete"|"incomplete", "problems": [...]}`` for the dashboard.

    ``sunset_provider_current``: a current SunsetWx forecast assessed the home
    sunsets, so the home forecast point is not required for that category.
    """
    wanted = set(ASSESSMENT_ALWAYS)
    for category in categories or ():
        wanted.update(ASSESSMENT_SOURCES.get(category, ()))
    problems = []
    # Weather is judged per forecast point when points were recorded: the
    # summary state turns "failed" when any one point fails, which would hide
    # *which* place could not be assessed.
    per_point = bool(points)
    for key in sorted(wanted):
        status = health.get(key)
        if not status or not status.get("enabled"):
            continue
        if key == "weather" and per_point:
            continue
        if status.get("state") in ("failed", "stale", "waiting"):
            problems.append({"source": key, "name": status.get("name", key), "state": status["state"],
                             "impact": status.get("impact") or IMPACTS.get(key, "")})
    weather_wanted = "weather" in wanted and health.get("weather", {}).get("enabled")
    if weather_wanted and per_point:
        needed_points = set()
        for category in categories or ():
            if category == "sunset" and sunset_provider_current:
                continue
            needed_points.update(ASSESSMENT_POINTS.get(category, ()))
        if CATEGORY_ASTRO in (categories or ()):
            needed_points.update(point for point in (points or {}) if point not in ("home", "pismo_grove"))
        for point in sorted(needed_points):
            state = (points or {}).get(point)
            if state in ("failed", "stale", "waiting"):
                problems.append({"source": f"weather:{point}", "name": f"Forecast for {point.replace('_', ' ')}",
                                 "state": state, "impact": "Conditions at this place could not be assessed."})
    return {"state": "incomplete" if problems else "complete", "problems": problems}


def annotate(opportunities, health, points: dict | None = None):
    """Mark each row with the degraded sources it depends on.

    Weather is judged by the forecast points the row consumed (``points`` is
    ``point_health``) when that is known, so an unrelated point's failure does
    not degrade it.
    """
    for item in opportunities:
        roles = dependency_roles(item)
        broken = []
        for key in roles:
            state = health.get(key, {}).get("state")
            consumed = weather_points(item) if key == "weather" and points else []
            if consumed and all(point in points for point in consumed):
                if any(points[point] in ("failed", "stale", "waiting") for point in consumed):
                    broken.append(key)
            elif state in {"failed", "stale"}:
                broken.append(key)
        broken = sorted(broken)
        # Rebuilding normally creates fresh objects; clear these defensively
        # so a recovery cannot leave a retained object marked degraded.
        for key in ("degraded_sources", "source_health_note", "degraded_required", "fallback_note"):
            item.extra.pop(key, None)
        if broken:
            item.extra["degraded_sources"] = broken
            item.extra["source_health_note"] = " ".join(
                f"{health.get(key, {}).get('name', key)}: {health.get(key, {}).get('impact', IMPACTS.get(key, ''))}"
                for key in broken)
            required = [key for key in broken if roles[key] == REQUIRED]
            if required:
                item.extra["degraded_required"] = required
            fallback = [FALLBACK_NOTES[key] for key in broken if roles[key] == PREFERRED and key in FALLBACK_NOTES]
            if fallback:
                item.extra["fallback_note"] = " ".join(fallback)
        # The builder knew the provider could not decide even though its feed
        # was reachable (for example a current download of an old model run).
        if item.extra.get("provider_fallback") and not item.extra.get("fallback_note"):
            item.extra["fallback_note"] = item.extra["provider_fallback"]
    return opportunities
