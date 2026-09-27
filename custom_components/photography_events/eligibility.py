"""The Can't Miss gate: decide what deserves the photographer's attention, then rank it.

Before 0.16.0 one integer tried to be significance, confidence, urgency and
weather quality at once, every row was ranked by it, and the top five were
shown. A fresh common-bird sighting could outrank a meteor peak because it was
*fresh*. This module separates the questions and puts a **hard eligibility
gate before any ranking**:

1. Is the phenomenon curated as something that can reach the main dashboard
   at all? (Parks, seasons and bird chases never do.)
2. Has its trigger policy been satisfied - the behaviour reported, the count
   met, the documented cycle underway, the geometry and forecast favourable?
3. Does it happen inside the next seven days?
4. Is it within the Can't Miss drive limit? ``planning_only`` does not exempt
   anything here; that exemption belongs to the year planner alone.
5. Does it matter enough (significance floor)?
6. Is it safe? An active NWS warning where it is removes it outright.

Only what passes all six is ranked, by a priority derived from the separate
significance, confidence and urgency. An empty result is a healthy answer:
"Nothing worth changing plans for this week."
"""

from __future__ import annotations

from datetime import datetime, timedelta

from . import curation, gear, weather_hazards
from .curation import (
    CLASS_BIRD_CHASE, CLASS_BIRD_ENCOUNTER, CLASS_BIRD_SPECTACLE, CLASS_CANT_MISS, CLASS_PLANNER,
    CLASS_WATCH, SIGNIFICANCE_FLOOR,
)

CANT_MISS_DAYS = 7
SHOW_LIMIT = 5
WATCH_DAYS = 14

CONFIDENCE = {
    "computed": 90, "measured": 90, "behavior_confirmed": 80, "calendar_presence": 78,
    "calendar": 70, "nowcast": 70, "repeated_presence": 70, "forecast": 60, "schedule": 55,
    "computed_candidate": 45, "presence_only": 40, "reported_undated": 35, "watching": 20,
    "unverified": 15, "season": 10,
}
BASIS = {
    "computed": "Calculated", "measured": "Measured", "behavior_confirmed": "Confirmed by a dated report",
    "calendar_presence": "Documented annual cycle, recent report nearby", "calendar": "Documented annual cycle",
    "nowcast": "Model nowcast", "repeated_presence": "Repeated recent reports", "forecast": "Forecast",
    "schedule": "Published schedule", "computed_candidate": "Calculated sky candidate only",
    "presence_only": "Species reported; behaviour unconfirmed", "reported_undated": "Reported, date unknown",
    "watching": "Watching - nothing reported yet", "unverified": "Estimate", "season": "Season",
}
WATCH_STATES = frozenset({"presence_only", "reported_undated", "watching", "forecast", "computed_candidate", "calendar"})


def _time(value):
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _urgency(item, now) -> tuple[int, str]:
    end = item.end or item.start + timedelta(hours=2)
    if item.start <= now <= end:
        return (95 if end - now <= timedelta(hours=48) else 85), "Now"
    hours = (item.start - now).total_seconds() / 3600
    if hours <= 24:
        return 85, "Within 24 h"
    if hours <= 48:
        return 75, "Tomorrow"
    if hours <= CANT_MISS_DAYS * 24:
        return 55, "This week"
    return 20, "Later"


def _confidence(item, state, now) -> int:
    value = CONFIDENCE.get(state, 30)
    if state == "behavior_confirmed":
        observed = [_time(row.get("observed_at")) for row in item.extra.get("behavior_evidence") or []]
        observed = [moment for moment in observed if moment] or [_time(item.extra.get("observed_at"))]
        observed = [moment for moment in observed if moment]
        if observed:
            age_days = max(0.0, (now - max(observed)).total_seconds() / 86400)
            value = max(55, round(value - 3 * age_days))
    if state == "forecast" and item.extra.get("provider_quality"):
        value = 65
    return value


def _conditions(item, definition, now) -> tuple[bool, str]:
    """Phenomenon-specific conditions on top of the evidence state."""
    key = definition.key
    extra = item.extra
    if key == "sunset_local":
        if item.zone_id != "home":
            return False, "sunset quality is assessed at home only"
        if extra.get("provider_quality"):
            return (extra["provider_quality"] == "Great",
                    f"SunsetWx rates it {extra['provider_quality']} ({extra.get('provider_percent')}%)")
        if extra.get("light_path") != "modelled":
            return False, "upstream light path not modelled; local-only score"
        return bool(extra.get("standout")), "not the standout of the forecast window"
    if key == "meteor_major":
        return item.score >= 75, f"conditions score {item.score}: moon, radiant or cloud not good enough"
    if key == "milky_way":
        forecast = extra.get("cloud_is_forecast") is True
        return (item.score >= 90 and forecast,
                "not a drop-everything night (new Moon, forecast clear, dark site)")
    if key == "full_moon_closest":
        if not extra.get("photogenic_rise"):
            return False, "moonrise not near sunset"
        cloud = extra.get("cloud_cover")
        if cloud is not None and extra.get("cloud_is_forecast") and cloud >= 70:
            return False, f"{cloud:.0f}% cloud forecast at moonrise"
        return True, ""
    if key == "pismo_monarchs":
        temp = extra.get("dawn_temp_f")
        if temp is None:
            return False, "no dawn temperature forecast to confirm the colony stays clustered"
        return temp <= 55, f"dawn forecast {temp:.0f} °F; monarchs fly above about 55 °F (Xerces)"
    if key == "bioluminescent_surf":
        moon = extra.get("moon_illumination")
        return (moon is not None and moon < 0.5, "Moon too bright for glowing surf" if moon is not None else "night geometry unknown")
    if key in ("horsetail_firefall", "moonbow"):
        cloud = extra.get("cloud_cover")
        if cloud is None or extra.get("cloud_is_forecast") is not True:
            return False, "no clear-sky forecast yet"
        return cloud <= 25, f"{cloud:.0f}% cloud forecast"
    return True, ""


def assess(item, now: datetime, *, max_drive_hours: float, alerts: list | None = None,
           sunset_drive_hours: float | None = None) -> dict:
    """Separate significance, confidence, urgency and eligibility for one row."""
    definition = curation.definition(item.phenomenon, item.category)
    state = item.extra.get("evidence_state") or ("season" if item.planning_only else "unverified")
    safety = weather_hazards.safety(item, alerts, now)
    urgency, urgency_label = _urgency(item, now)
    blockers: list[str] = []

    if definition is None:
        significance, product_class, actionable = 40, CLASS_PLANNER, False
        blockers.append("not a curated phenomenon")
    else:
        significance = definition.significance
        product_class = definition.product_class
        actionable = state in definition.actionable
        if product_class not in (CLASS_CANT_MISS, CLASS_BIRD_SPECTACLE):
            blockers.append("planning context, not a Can't Miss event")
        if not actionable:
            if state == "calendar" and "calendar_presence" in definition.actionable:
                blockers.append("encounter unconfirmed: needs a recent report of the animals near the site")
            else:
                blockers.append(f"{definition.policy.replace('_', ' ')}: " + (item.extra.get("awaiting") or BASIS.get(state, state)))
        else:
            ok, why = _conditions(item, definition, now)
            if not ok:
                actionable = False
                blockers.append(why)
        if significance < SIGNIFICANCE_FLOOR:
            blockers.append("significance below the Can't Miss floor")

    end = item.end or item.start + timedelta(hours=2)
    if end < now:
        blockers.append("already over")
    elif item.start > now + timedelta(days=CANT_MISS_DAYS):
        blockers.append("beyond the seven-day Can't Miss horizon")
    limit = max_drive_hours
    if item.phenomenon == "sunset_local" and sunset_drive_hours is not None:
        limit = min(limit, sunset_drive_hours)
    if item.drive_hours is not None and item.drive_hours > limit:
        blockers.append(f"beyond the {limit:g} h Can't Miss drive limit")
    if safety["unsafe"]:
        blockers.append(safety["summary"])
    # A forecast from a feed that stopped updating is not a current forecast.
    if state == "forecast" and item.extra.get("degraded_sources"):
        blockers.append("the forecast feed behind this is stale or failing")

    eligible = not blockers
    if eligible:
        presentation = CLASS_CANT_MISS
    elif product_class in (CLASS_BIRD_SPECTACLE, CLASS_BIRD_ENCOUNTER, CLASS_BIRD_CHASE):
        presentation = product_class
    elif state in WATCH_STATES and not item.planning_only or state in ("presence_only", "reported_undated"):
        presentation = CLASS_WATCH
    else:
        presentation = CLASS_PLANNER
    confidence = _confidence(item, state, now)
    plan = None
    if definition is not None:
        plan = gear.recommend(definition.gear_profile, land=definition.land, wildlife=definition.wildlife,
                              wind_ms=item.extra.get("wind_ms"), drone_useful=definition.drone_useful)
    result = {
        "phenomenon": definition.key if definition else item.phenomenon,
        "name": definition.name if definition else item.title,
        "policy": definition.policy if definition else "",
        "significance": significance,
        "confidence": confidence,
        "confidence_basis": BASIS.get(state, state),
        "urgency": urgency,
        "urgency_label": urgency_label,
        "encounter": definition.encounter if definition else "unknown",
        "access": ("closure reported" if item.extra.get("closures") else
                   "unsafe" if safety["unsafe"] else "check access" if item.extra.get("access_note") else "public"),
        "condition_quality": item.extra.get("provider_percent") or (item.score if state in ("computed", "forecast") else None),
        "evidence_state": state,
        "actionable": actionable,
        "eligible": eligible,
        "blockers": blockers,
        "presentation": presentation,
        "priority": round(0.5 * significance + 0.3 * confidence + 0.2 * urgency) if eligible else None,
        "status": BASIS.get(state, state),
        "why_now": why_now(item, state, definition),
        "unsafe": safety["unsafe"],
    }
    item.extra["assessment"] = result
    item.extra["safety_notes"] = safety["notes"]
    item.extra["safety_summary"] = safety["summary"]
    if definition is not None:
        if definition.ethics:
            item.extra["ethics"] = definition.ethics
        if definition.safety:
            item.extra["safety_notes"] = [*safety["notes"], definition.safety]
    if plan is not None:
        item.extra["gear_plan"] = plan.as_dict()
    return result


def why_now(item, state, definition) -> str:
    """One sentence: why this matters now, in terms of the evidence."""
    extra = item.extra
    if item.phenomenon == "sunset_local":
        if extra.get("provider_quality"):
            return f"SunsetWx forecasts {extra['provider_quality']} ({extra.get('provider_percent'):.0f}%); local model {extra.get('local_score')}."
        return "Best sky in the forecast window with an open light path to the west." if extra.get("standout") else "Promising sky forecast."
    if item.phenomenon == "full_moon_closest":
        gap = extra.get("rise_after_sunset_minutes")
        return (f"Closest full Moon of the year, rising {abs(gap)} min {'after' if (gap or 0) >= 0 else 'before'} sunset."
                if gap is not None else "Closest full Moon of the year.")
    if item.phenomenon == "milky_way":
        return "New-Moon darkness with a clear forecast at a dark site."
    if item.phenomenon == "meteor_major":
        rate = extra.get("expected_rate")
        return f"Peak night; roughly {rate}/hr expected from here." if rate else "Peak night."
    if state == "behavior_confirmed":
        evidence = (extra.get("behavior_evidence") or [{}])[0]
        when = _time(evidence.get("observed_at") or extra.get("observed_at"))
        source = evidence.get("source") or extra.get("source_name") or "a dated report"
        return f"Reported by {source}" + (f" on {when:%d %b}." if when else ".")
    if state == "calendar_presence":
        return "Peak of the documented annual cycle, with a recent report near the site."
    if state == "calendar":
        phase = extra.get("current_phase")
        return f"Documented peak underway{': ' + phase if phase else ''}."
    if state == "measured":
        return f"Buoy measured {extra.get('wave_height_m')} m offshore."
    if state == "nowcast":
        return "Short-term aurora model reaches this location tonight."
    if state == "repeated_presence":
        return item.reasons[0] if item.reasons else "Repeated recent reports."
    if state == "computed":
        return item.reasons[0] if item.reasons else "Calculated geometry."
    return BASIS.get(state, "")


def annotate(opportunities, now, *, max_drive_hours, alerts=None, sunset_drive_hours=None):
    for item in opportunities:
        assess(item, now, max_drive_hours=max_drive_hours, alerts=alerts, sunset_drive_hours=sunset_drive_hours)
    return opportunities


def merge_into_phenomena(opportunities: list, extra_rows: list, now: datetime) -> list:
    """Fold live-evidence rows into the phenomenon they are evidence for.

    A crane count of 3,000 at Merced is evidence for the crane fly-in window,
    not a second crane row. When a planner row for the same phenomenon covers
    today, it is upgraded in place and the extra row is dropped. Returns the
    rows that had nowhere to go (for example condors, which have no window).
    """
    remaining = []
    for row in extra_rows:
        target = next((item for item in opportunities if item.phenomenon == row.phenomenon
                       and item.start <= now <= (item.end or item.start)
                       and item.extra.get("precision", "peak") == "peak"), None)
        if target is None:
            remaining.append(row)
            continue
        target.extra["evidence_state"] = "behavior_confirmed"
        target.extra["verification"] = "corroborated"
        target.extra["behavior_evidence"] = [*(target.extra.get("behavior_evidence") or []),
                                             *(row.extra.get("behavior_evidence") or [
                                                 {"source": row.detail, "observed_at": row.extra.get("observed_at"),
                                                  "url": row.source_url, "text": row.detail}])]
        target.extra["count"] = max(target.extra.get("count") or 0, row.extra.get("count") or 0) or None
        target.reasons = [*row.reasons[:1], *target.reasons]
    return remaining


def cant_miss_row(item, alternatives: int = 0) -> dict:
    row = item.compact()
    assessment = item.extra.get("assessment") or {}
    row.update({key: assessment.get(key) for key in (
        "significance", "confidence", "confidence_basis", "urgency", "urgency_label", "encounter",
        "access", "condition_quality", "priority", "status", "why_now", "policy", "name")})
    row["gear_plan"] = item.extra.get("gear_plan") or {}
    row["safety_notes"] = item.extra.get("safety_notes") or []
    if item.extra.get("ethics"):
        row["ethics"] = item.extra["ethics"]
    if item.extra.get("awaiting"):
        row["awaiting"] = item.extra["awaiting"]
    if alternatives:
        row["alternative_count"] = alternatives
    return row


def _group_key(item) -> str:
    return item.roll or item.key


def dashboard(opportunities: list, now: datetime, *, suppressed=lambda key: False,
              signals: list | None = None, birds: dict | None = None, limit: int = 12) -> dict:
    """The Can't Miss payload: eligible rows ranked, a watch list, background signals."""
    from .event_state import event_id
    from .signals import background

    eligible = [item for item in opportunities if (item.extra.get("assessment") or {}).get("eligible")]
    groups: dict[str, list] = {}
    for item in eligible:
        groups.setdefault(_group_key(item), []).append(item)
    # Consecutive Milky Way nights are one lunar window, not five rows.
    milky = sorted((key for key, rows in groups.items() if rows[0].phenomenon == "milky_way"),
                   key=lambda key: groups[key][0].start)
    for previous, current in zip(milky, milky[1:]):
        if groups[current][0].start - groups[previous][0].start <= timedelta(days=3):
            groups[current].extend(groups.pop(previous))

    rows, suppressed_count = [], 0
    for items in groups.values():
        items.sort(key=lambda item: (-(item.extra["assessment"]["priority"] or 0), item.drive_hours, item.start))
        best = items[0]
        if all(suppressed(event_id(item)) for item in items):
            suppressed_count += 1
            continue
        row = cant_miss_row(best, alternatives=len(items) - 1)
        row["choice_ids"] = sorted({event_id(item) for item in items})
        rows.append((best, row))
    rows.sort(key=lambda pair: (-(pair[1]["priority"] or 0), pair[0].start))

    horizon = now + timedelta(days=WATCH_DAYS)
    watch, seen = [], set()
    for item in sorted(opportunities, key=lambda item: -((item.extra.get("assessment") or {}).get("significance") or 0)):
        assessment = item.extra.get("assessment") or {}
        if assessment.get("presentation") != CLASS_WATCH or assessment.get("eligible"):
            continue
        if item.start > horizon or (item.end or item.start) < now or item.phenomenon in seen:
            continue
        seen.add(item.phenomenon)
        watch.append({"title": item.title.replace(" (season)", ""), "phenomenon": item.phenomenon,
                      "status": assessment.get("status"), "awaiting": item.extra.get("awaiting") or (assessment.get("blockers") or [""])[0],
                      "start": item.start.isoformat(), "end": (item.end or item.start).isoformat(),
                      "where": item.zone_name, "significance": assessment.get("significance")})
    watch = watch[:limit]

    return {
        "events": [row for _, row in rows],
        "eligible_count": len(rows),
        "suppressed_count": suppressed_count,
        "show_limit": SHOW_LIMIT,
        "headline": None if rows else "Nothing worth changing plans for this week.",
        "watch": watch,
        "signals": background(signals or [], now),
        "signal_count": len(signals or []),
        "birds": {
            "spectacle": [cant_miss_row(item) for item in (birds or {}).get("spectacle", [])],
            "encounter": (birds or {}).get("encounter", [])[:20],
            "chase": (birds or {}).get("chase", [])[:25],
        },
    }
