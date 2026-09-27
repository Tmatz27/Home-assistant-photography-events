"""Three bird products, because "a rare bird was seen" answers the wrong question.

The question a photographer asks before a drive is: *if I go, what is the
realistic chance I find the bird and photograph something extraordinary?*
Ecological rarity does not answer it (one Painted Bunting in a hedge is rare
and usually gone), photogenic appearance does not, and eBird's "notable" flag
does not. So bird signals are sorted into:

- **Bird Spectacle** - an iconic subject, a credible encounter, *and* the
  behaviour or concentration that makes the photograph: several condors on the
  ridge, eagles fishing, thousands of geese. May reach Can't Miss.
- **Bird Encounter** - an iconic subject reported repeatedly at one public
  viewing area, without behaviour. Bird view only.
- **Bird Chase** - notable individual birds. Bird view only, ranked by how
  likely the bird still is to be there.

Thresholds here are **product thresholds** (tunable choices about what is worth
attention), not ecological facts: repetition means at least three independent
reports on at least two days within a week, within 15 km of a known public
viewing area; a spectacle count is the per-species number below.

Private eBird locations and obscured iNaturalist points are used as evidence
but never shown as a place to go.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from .events import MARINE_DRAW, PHOTOGRAPHY_BIRDS, Opportunity
from .gear import LAND_NPS, LAND_REFUGE, LAND_UNKNOWN, recommend
from .wildlife import estimate_drive_hours, haversine_km

SITE_RADIUS_KM = 15.0
ENCOUNTER_REPORTS = 3
ENCOUNTER_DAYS = 2
ENCOUNTER_WINDOW_DAYS = 7
SPECTACLE_FRESH_DAYS = 3
CHASE_FRESH_HOURS = 48

# Iconic species, the public viewing areas they are photographed from, and the
# count that turns an encounter into a spectacle.
ICONIC = {
    "Gymnogyps californianus": {
        "name": "California condors", "phenomenon": "condor_activity", "count": 3,
        "behaviors": ("roosting", "soaring together", "feeding"),
        "sites": (("Pinnacles High Peaks", 36.4870, -121.1950, LAND_NPS),
                  ("Big Sur coast, Highway 1 turnouts", 36.2300, -121.7700, LAND_UNKNOWN)),
    },
    "Haliaeetus leucocephalus": {
        "name": "Bald eagles", "phenomenon": "bald_eagle_cachuma", "count": 3,
        "behaviors": ("fishing", "catching fish"),
        "sites": (("Cachuma Lake", 34.5850, -119.9800, LAND_UNKNOWN),),
    },
    "Aquila chrysaetos": {
        "name": "Golden eagles", "phenomenon": "", "count": None,
        "behaviors": ("courtship", "sky dance", "display"),
        "sites": (),
    },
    "Antigone canadensis": {
        "name": "Sandhill cranes", "phenomenon": "sandhill_crane_flyin", "count": 1000,
        "behaviors": ("fly-in",),
        "sites": (("Merced National Wildlife Refuge", 37.1800, -120.6000, LAND_REFUGE),
                  ("Woodbridge Ecological Reserve", 38.1560, -121.4160, LAND_UNKNOWN)),
    },
    "Anser rossii": {
        "name": "Ross's geese", "phenomenon": "waterfowl_mass_flight", "count": 1000,
        "behaviors": ("lift-off", "blast-off"),
        "sites": (("Merced National Wildlife Refuge", 37.1800, -120.6000, LAND_REFUGE),),
    },
    "Anser caerulescens": {
        "name": "Snow geese", "phenomenon": "waterfowl_mass_flight", "count": 1000,
        "behaviors": ("lift-off", "blast-off"),
        "sites": (("Merced National Wildlife Refuge", 37.1800, -120.6000, LAND_REFUGE),),
    },
    "Aechmophorus occidentalis": {
        "name": "Western grebes", "phenomenon": "", "count": None, "behaviors": ("rushing",), "sites": (),
    },
    "Aechmophorus clarkii": {
        "name": "Clark's grebes", "phenomenon": "", "count": None, "behaviors": ("rushing",), "sites": (),
    },
}

# eBird species codes for the iconic species worth a direct query, and the
# counties their viewing areas lie in. Kept small: six requests every six hours.
EBIRD_SPECIES_QUERIES = (
    ("calcon", "US-CA-069"), ("calcon", "US-CA-053"), ("baleag", "US-CA-083"),
    ("sancra", "US-CA-047"), ("rosgoo", "US-CA-047"), ("snogoo", "US-CA-047"),
)


def _is_bird(sighting) -> bool:
    return sighting.category == "birds" or sighting.scientific_name in ICONIC


def _site_for(sighting, sites):
    for name, lat, lon, land in sites:
        if haversine_km(lat, lon, sighting.latitude, sighting.longitude) <= SITE_RADIUS_KM:
            return name, lat, lon, land
    return None


def classify(sightings: list, now: datetime, home: tuple[float, float], max_drive_hours: float,
             reports: list | None = None) -> dict:
    """Sort bird sightings (raw, unclustered) into spectacle, encounter and chase.

    Returns ``{"spectacle": [Opportunity], "encounter": [dict], "chase": [dict]}``.
    Spectacle rows are Opportunities so the eligibility gate can weigh them
    against everything else; the other two are view rows only.
    """
    recent = [item for item in sightings or []
              if _is_bird(item) and now - timedelta(days=ENCOUNTER_WINDOW_DAYS) <= item.latest <= now + timedelta(hours=1)]
    spectacle, encounter, used = [], [], set()

    for scientific, spec in ICONIC.items():
        for site in spec["sites"]:
            name, lat, lon, land = site
            here = [item for item in recent if item.scientific_name == scientific and _site_for(item, (site,))]
            if not here:
                continue
            used.update(id(item) for item in here)
            observers = {obs for item in here for obs in (item.observers or [f"{item.source}-{item.latest}"])}
            days = {day for item in here for day in (item.dates or [item.latest.date().isoformat()])}
            latest = max(item.latest for item in here)
            max_count = max((item.count or 0) for item in here)
            behavior_reports = [report for report in reports or []
                                if getattr(report, "observed_at", None) and now - report.observed_at <= timedelta(days=SPECTACLE_FRESH_DAYS)
                                and haversine_km(lat, lon, *_report_point(report)) <= SITE_RADIUS_KM * 3
                                and any(term in (report.snippet or "").lower() for term in spec["behaviors"])]
            drive = estimate_drive_hours(lat, lon, home)
            fresh = now - latest <= timedelta(days=SPECTACLE_FRESH_DAYS)
            concentrated = spec["count"] is not None and max_count >= spec["count"]
            repeated = len(observers) >= ENCOUNTER_REPORTS and len(days) >= ENCOUNTER_DAYS
            summary = {
                "species": spec["name"], "scientific_name": scientific, "site": name,
                "latitude": lat, "longitude": lon, "drive_hours": round(drive, 2),
                "reports": len(observers), "days": len(days), "max_count": max_count or None,
                "latest": latest.isoformat(), "phenomenon": spec["phenomenon"],
                "url": next((item.url for item in sorted(here, key=lambda i: i.latest, reverse=True) if item.url), None),
            }
            if fresh and spec["phenomenon"] and (concentrated or behavior_reports):
                why = (f"{max_count:,} counted in one report" if concentrated
                       else f"behaviour reported by {behavior_reports[0].source_name}")
                spectacle.append(_spectacle_row(spec, scientific, site, summary, why, now, land, behavior_reports))
            elif repeated:
                encounter.append({**summary, "class": "bird_encounter",
                                  "why": f"{len(observers)} independent reports on {len(days)} days in the last week at a public viewing area",
                                  "encounter_confidence": min(90, 40 + 10 * len(observers) + 5 * len(days))})

    chase = []
    for item in recent:
        if id(item) in used or not getattr(item, "notable", False) or item.scientific_name in ICONIC:
            continue
        age = (now - item.latest).total_seconds() / 3600
        if age > CHASE_FRESH_HOURS or item.private_location:
            continue
        drive = estimate_drive_hours(item.latitude, item.longitude, home)
        if drive > max_drive_hours:
            continue
        chase.append(_chase_row(item, age, drive))
    chase = _merge_chase(chase)
    chase.sort(key=lambda row: (-row["encounter_confidence"], row["drive_hours"]))
    return {"spectacle": spectacle, "encounter": encounter, "chase": chase}


def _report_point(report):
    if getattr(report, "latitude", None) is not None and getattr(report, "longitude", None) is not None:
        return report.latitude, report.longitude
    from .const import ZONES_BY_ID
    zone = ZONES_BY_ID.get(getattr(report, "zone_id", ""))
    return (zone["latitude"], zone["longitude"]) if zone else (0.0, 0.0)


def _spectacle_row(spec, scientific, site, summary, why, now, land, behavior_reports):
    name, lat, lon, _land = site
    plan = recommend("birds_in_flight_low_light" if spec["phenomenon"] in ("sandhill_crane_flyin", "waterfowl_mass_flight") else "raptor",
                     land=land, wildlife=True)
    key = f"birds-{spec['phenomenon']}-{name.lower().replace(' ', '-')}-{now.date().isoformat()}"
    return Opportunity(
        key=key, roll=f"birds-{spec['phenomenon']}-{now.date().isoformat()}",
        title=f"{spec['name']} at {name}", category="birds", zone_id=spec["phenomenon"], zone_name=name,
        start=now, end=now + timedelta(days=SPECTACLE_FRESH_DAYS), score=80,
        detail=f"{spec['name']} reported repeatedly at {name}: {why}.",
        drive_hours=summary["drive_hours"], latitude=lat, longitude=lon, drive_source="estimate",
        source_url=summary["url"], phenomenon=spec["phenomenon"],
        reasons=[why, f"{summary['reports']} reports on {summary['days']} days"],
        extra={"verification": "corroborated", "evidence_state": "behavior_confirmed",
               "observed_at": summary["latest"], "count": summary["max_count"],
               "bird_summary": summary, "recommended_gear": plan.take,
               "behavior_evidence": [{"source": report.source_name, "observed_at": report.observed_at.isoformat(),
                                      "text": report.snippet[:200], "url": report.url or None} for report in behavior_reports],
               "evidence_note": "Reported concentration or behaviour at a public viewing area. Birds move; a report is not a guarantee.",
               "access_note": "Public viewing areas only; never approach roosts or nests."},
    )


def _chase_row(item, age_hours, drive):
    reports = max(item.reports, len(item.observers) or 1)
    days = len(item.dates or [])
    # A heuristic ranking of "still findable", not a probability: repeat
    # reports and reviewer confirmation raise it, age lowers it.
    confidence = 25 + 12 * min(reports, 4) + (12 if days >= 2 else 0) + (8 if item.confirmed else 0) - int(age_hours / 6) * 4
    return {
        "class": "bird_chase", "species": item.species, "scientific_name": item.scientific_name,
        "site": item.place, "latitude": item.latitude, "longitude": item.longitude,
        "drive_hours": round(drive, 2), "reports": reports, "days": max(1, days),
        "latest": item.latest.isoformat(), "confirmed": item.confirmed, "url": item.url,
        "photogenic": item.species.casefold() in PHOTOGRAPHY_BIRDS,
        "encounter_confidence": max(5, min(90, confidence)),
        "why": f"{reports} report{'s' if reports != 1 else ''}, last {round(age_hours)} h ago" + (", reviewer-confirmed" if item.confirmed else ""),
    }


def _merge_chase(rows: list[dict]) -> list[dict]:
    """One row per species; the most findable place wins, the rest are alternatives."""
    best: dict[str, dict] = {}
    for row in rows:
        key = row["scientific_name"] or row["species"]
        current = best.get(key)
        if current is None or row["encounter_confidence"] > current["encounter_confidence"]:
            if current:
                row["alternatives"] = [*current.get("alternatives", []), {k: current[k] for k in ("site", "latest", "url")}]
            best[key] = row
        else:
            current.setdefault("alternatives", []).append({k: row[k] for k in ("site", "latest", "url")})
    return list(best.values())


def marine_presence(sightings: list, now: datetime, home: tuple[float, float]) -> list:
    """Orcas (and blue whales) reported repeatedly: exceptional presence.

    Product threshold, documented in curation.py: two independent reports within
    72 hours, or one research-grade report within 36 hours. Humpbacks and
    dolphins never qualify here - their presence is ordinary.
    """
    found = []
    for scientific in ("Orcinus orca",):
        here = [item for item in sightings or [] if item.scientific_name == scientific
                and now - item.latest <= timedelta(hours=72) and item.latest <= now + timedelta(hours=1)]
        if not here:
            continue
        observers = {obs for item in here for obs in (item.observers or [item.url or item.place])}
        confirmed_recent = any(item.confirmed and now - item.latest <= timedelta(hours=36) for item in here)
        if len(observers) < 2 and not confirmed_recent:
            continue
        latest = max(here, key=lambda item: item.latest)
        drive = estimate_drive_hours(latest.latitude, latest.longitude, home)
        found.append(Opportunity(
            key=f"orca-presence-{latest.latest.date().isoformat()}", roll=f"orca-presence-{latest.latest.date().isoformat()}",
            title="Orcas reported", category="marine", zone_id="orca_presence", zone_name=latest.place,
            start=max(now, latest.latest), end=latest.latest + timedelta(hours=72), score=80 + MARINE_DRAW.get(scientific, 0) // 2,
            detail=f"{len(observers)} independent report{'s' if len(observers) != 1 else ''} of orcas; latest at {latest.place}.",
            drive_hours=round(drive, 2), latitude=latest.latitude, longitude=latest.longitude,
            drive_source="estimate", source_url=latest.url, phenomenon="orca_presence",
            reasons=[f"{len(observers)} independent reports in 72 h"],
            extra={"verification": "corroborated", "evidence_state": "repeated_presence",
                   "observed_at": latest.latest.isoformat(),
                   "evidence_note": "Orca presence only; hunting behaviour is not confirmed. A boat trip is usually required.",
                   "confidence_note": "Orcas travel fast; contact an operator before booking."},
        ))
    return found
