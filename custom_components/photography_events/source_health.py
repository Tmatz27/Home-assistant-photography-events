"""Feed health is separate from evidence: a broken feed is not a quiet season.

Never release an evidence ceiling here. A retained observation keeps its real
date and can expire even while a feed is broken. Geometry also remains geometry
when the cloud model fails; only its conditions assessment is degraded.
"""

from datetime import timedelta

from .phenomena import EVIDENCE_STATIC
from .const import CATEGORY_ASTRO

IMPACTS = {
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
    "surf_alerts": "Coastal advisories cannot be refreshed.",
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


def dependencies(item):
    """Only feeds that can actually help this opportunity; no imaginary wiring."""
    category = item.category
    if item.extra.get("evidence") == EVIDENCE_STATIC:
        return set()
    if category == CATEGORY_ASTRO:
        if item.key.startswith("eclipse-"):
            return set()  # This builder currently computes geometry, not cloud.
        return {"aurora"} if "aurora" in item.key else {"weather"}
    if category == "sunset":
        return {"weather", "air_quality"}
    if category == "waves":
        return {"ndbc", "cdip", "surf_alerts"}
    if category == "blooms":
        return {"theodore_payne", "desertusa"}
    if category == "foliage":
        return {"california_fall_color"}
    if category == "parks":
        return {"park_alerts"}
    if category == "birds":
        return {"ebird", "inaturalist"}
    if category == "marine":
        return {"inaturalist", "condor_reports"}
    if category == "mammals":
        return {"inaturalist"}
    if category == "rare_phenomena" and "grunion" in item.key:
        return {"grunion", "tides"}
    if category == "rare_phenomena" and "monarch" in item.key:
        return {"inaturalist"}
    return set()


def annotate(opportunities, health):
    for item in opportunities:
        broken = sorted(key for key in dependencies(item)
                        if health.get(key, {}).get("state") in {"failed", "stale"})
        # Rebuilding normally creates fresh objects; clear these defensively
        # so a recovery cannot leave a retained object marked degraded.
        item.extra.pop("degraded_sources", None)
        item.extra.pop("source_health_note", None)
        if broken:
            item.extra["degraded_sources"] = broken
            item.extra["source_health_note"] = " ".join(
                f"{health[key]['name']}: {health[key]['impact']}" for key in broken)
    return opportunities
