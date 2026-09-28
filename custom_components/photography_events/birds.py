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
from .observations import admissible
from .wildlife import estimate_drive_hours, haversine_km


def curation_definition(key):
    from .curation import definition
    return definition(key)

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
        definition = curation_definition(spec["phenomenon"]) if spec["phenomenon"] else None
        for site in spec["sites"]:
            name, lat, lon, land = site
            here = [item for item in recent if item.scientific_name == scientific and _site_for(item, (site,))]
            if not here:
                continue
            used.update(id(item) for item in here)
            observers = {obs for item in here for obs in (item.observers or [f"{item.source}-{item.latest}"])}
            days = {day for item in here for day in (item.dates or [item.latest.date().isoformat()])}
            latest = max(item.latest for item in here)
            # Each count keeps its own timestamp. The spectacle needs one count
            # at or above the threshold that is itself fresh: a 3,000 count from
            # a week ago plus a one-bird sighting today is not a current 3,000.
            fresh_counts = [item for item in here if spec["count"] is not None and (item.count or 0) >= spec["count"]
                            and now - item.latest <= timedelta(days=SPECTACLE_FRESH_DAYS)]
            max_count = max((item.count or 0) for item in here)
            # Behaviour reports must name this species' phenomenon in their own
            # statement, be positive, dated, fresh (the spectacle window) and at
            # this site (observations.admissible).
            behavior_reports = []
            if definition is not None:
                for report in reports or []:
                    ok, _why = admissible(report, definition, now, site=(lat, lon), radius_km=SITE_RADIUS_KM * 3)
                    if ok and now - report.observed_at <= timedelta(days=SPECTACLE_FRESH_DAYS):
                        behavior_reports.append(report)
            drive = estimate_drive_hours(lat, lon, home)
            concentrated = bool(fresh_counts)
            repeated = len(observers) >= ENCOUNTER_REPORTS and len(days) >= ENCOUNTER_DAYS
            qualifying = max(fresh_counts, key=lambda item: (item.count or 0, item.latest)) if fresh_counts else None
            evidence_time = (qualifying.latest if qualifying else
                             max(report.observed_at for report in behavior_reports) if behavior_reports else latest)
            summary = {
                "species": spec["name"], "scientific_name": scientific, "site": name,
                "latitude": lat, "longitude": lon, "drive_hours": round(drive, 2), "drive_basis": "estimate",
                "reports": len(observers), "days": len(days), "max_count": max_count or None,
                "latest": latest.isoformat(), "phenomenon": spec["phenomenon"],
                "evidence_at": evidence_time.isoformat(),
                "qualifying_count": qualifying.count if qualifying else None,
                "url": ((qualifying.url if qualifying and qualifying.url else None)
                        or next((item.url for item in sorted(here, key=lambda i: i.latest, reverse=True) if item.url), None)),
            }
            if spec["phenomenon"] and (concentrated or behavior_reports):
                why = (f"{qualifying.count:,} counted in one report on {qualifying.latest:%d %b}" if concentrated
                       else f"behaviour reported by {behavior_reports[0].source_name}")
                spectacle.append(_spectacle_row(spec, scientific, site, summary, why, now, land, behavior_reports))
            elif repeated and drive <= max_drive_hours:
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
    # One occurrence per site: a Woodbridge crane count is not the Merced
    # fly-in, so the two never share an identity (or a Follow/Skip).
    key = f"birds-{spec['phenomenon']}-{name.lower().replace(' ', '-')}-{now.date().isoformat()}"
    return Opportunity(
        key=key, roll=key,
        title=f"{spec['name']} at {name}", category="birds", zone_id=spec["phenomenon"], zone_name=name,
        # Valid for the spectacle window from the evidence, not from now.
        start=now, end=datetime.fromisoformat(summary["evidence_at"]) + timedelta(days=SPECTACLE_FRESH_DAYS), score=80,
        detail=f"{spec['name']} reported repeatedly at {name}: {why}.",
        drive_hours=summary["drive_hours"], latitude=lat, longitude=lon, drive_source="estimate",
        source_url=summary["url"], phenomenon=spec["phenomenon"],
        reasons=[why, f"{summary['reports']} reports on {summary['days']} days"],
        extra={"verification": "corroborated", "evidence_state": "behavior_confirmed",
               # The time of the evidence that qualified, not the newest bird.
               "observed_at": summary["evidence_at"], "count": summary["qualifying_count"],
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
        "drive_hours": round(drive, 2), "drive_basis": "estimate", "reports": reports, "days": max(1, days),
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


# Orcas move tens of kilometres a day, so observations only combine when they
# are plausibly the same animals in the same place. Product thresholds:
#
# - ORCA_WINDOW_HOURS: every contributing observation must itself be inside the
#   last 72 h. Filtering happens on raw observations *before* anything is
#   combined, so a ten-day-old observer can never be counted as a current one.
# - ORCA_CLUSTER_KM is a maximum *diameter*: every pair of observations in a
#   cluster is within 25 km of each other (complete linkage). Single linkage
#   let A-B-C-D chain along 70 km of coast and call it one "25 km cluster".
# - Two independent observers (distinct source/person identities) are needed,
#   or one dated operator report within ORCA_OPERATOR_HOURS.
# - Obscured or private points are fuzzed by the source; they cannot establish
#   that two observations were in the same place, so they never form or join a
#   cluster. They remain background signals.
ORCA_CLUSTER_KM = 25.0
ORCA_WINDOW_HOURS = 72
ORCA_OPERATOR_HOURS = 36
ORCA_TERMS = ("orca", "killer whale")
ORCA_SCIENTIFIC = "Orcinus orca"


def _observer_id(item) -> str:
    """One identity per person/checklist per source; never shared between observations."""
    who = next(iter(item.observers), None) if item.observers else None
    return f"{item.source}:{who or item.url or item.latest.isoformat()}"


def _orca_clusters(items: list) -> list[list]:
    """Complete-linkage groups: every pair within ORCA_CLUSTER_KM (the cluster diameter).

    Greedy from the newest observation: each observation joins the first
    existing cluster whose *every* member is within the diameter, otherwise it
    starts its own. Deterministic, and no chain can stretch a cluster.
    """
    groups: list[list] = []
    for item in sorted(items, key=lambda row: row.latest, reverse=True):
        home = next((group for group in groups if all(
            haversine_km(item.latitude, item.longitude, other.latitude, other.longitude) <= ORCA_CLUSTER_KM
            for other in group)), None)
        if home is None:
            groups.append([item])
        else:
            home.append(item)
    return groups


def operator_orca_reports(reports: list | None, now: datetime) -> list:
    """Dated operator or subscription reports whose own statement names orcas.

    A trip report from an operator is a trusted observer: someone whose job is
    finding these animals, writing the date down. The report must pass the
    shared normalizer (a positive statement about orcas, not "no orcas today"),
    be dated inside ORCA_OPERATOR_HOURS and be locatable.
    """
    from .curation import definition
    from .observations import admissible, report_point

    presence = definition("orca_presence")
    hunting = definition("transient_orca_hunt")
    found = []
    for report in reports or []:
        observed = getattr(report, "observed_at", None)
        if observed is None or not timedelta(0) <= now - observed <= timedelta(hours=ORCA_OPERATOR_HOURS):
            continue
        if report.category != "marine" or not (report.source_id == "condor_express" or report.source_id.startswith("email_")):
            continue
        if not (admissible(report, presence, now)[0] or admissible(report, hunting, now)[0]):
            continue
        point = report_point(report)
        if point is None:
            continue  # An unlocatable report corroborates nothing.
        found.append((report, point[0], point[1]))
    return found


def marine_presence(sightings: list, now: datetime, home: tuple[float, float], reports: list | None = None) -> list:
    """Orcas reported coherently enough to be worth a boat trip.

    ``sightings`` must be **raw observations** (one per observer/checklist,
    each with its own coordinates and time) - never a digest that has already
    merged places, times and observers. A single community observation - even
    research grade - stays a background signal and never becomes a row: one
    photo of a dorsal fin says the pod passed, not where it is now. Humpbacks
    and dolphins never qualify here - their presence is ordinary.
    """
    here = [item for item in sightings or [] if item.scientific_name == ORCA_SCIENTIFIC
            and timedelta(hours=-1) <= now - item.latest <= timedelta(hours=ORCA_WINDOW_HOURS)
            and not getattr(item, "private_location", False)]
    operators = operator_orca_reports(reports, now)
    found = []
    for group in _orca_clusters(here):
        observers = {_observer_id(item) for item in group}
        latest = max(group, key=lambda item: item.latest)
        backing = [row for row in operators if all(
            haversine_km(row[1], row[2], item.latitude, item.longitude) <= ORCA_CLUSTER_KM * 2 for item in group)]
        for row in backing:
            operators.remove(row)
        if len(observers) < 2 and not backing:
            continue
        found.append(_orca_row(latest.latitude, latest.longitude, latest.latest, latest.place, latest.url, now, home,
                               observers=len(observers), operator=backing[0][0] if backing else None,
                               contributions=group))
    for report, latitude, longitude in operators:
        found.append(_orca_row(latitude, longitude, report.observed_at, report.source_name, report.url, now, home,
                               observers=0, operator=report))
    return found


def _orca_row(latitude, longitude, seen, place, url, now, home, *, observers, operator, contributions=()):
    drive = estimate_drive_hours(latitude, longitude, home)
    parts = []
    if observers:
        parts.append(f"{observers} independent observer{'s' if observers != 1 else ''}")
    if operator is not None:
        parts.append(f"a dated report from {operator.source_name}")
    summary = " and ".join(parts)
    evidence = []
    if operator is not None:
        evidence.append({"source": operator.source_name, "observed_at": operator.observed_at.isoformat(),
                         "text": operator.snippet[:220], "url": operator.url or None})
    day = seen.date().isoformat()
    key = f"orca-presence-{day}-{round(latitude, 1)}-{round(longitude, 1)}"
    return Opportunity(
        key=key, roll=key, title="Orcas reported",
        category="marine", zone_id="orca_presence", zone_name=place,
        start=max(now, seen), end=seen + timedelta(hours=ORCA_WINDOW_HOURS),
        score=80 + MARINE_DRAW.get("Orcinus orca", 0) // 2,
        detail=f"Orcas: {summary}; latest near {place}.",
        drive_hours=round(drive, 2), latitude=latitude, longitude=longitude,
        drive_source="estimate", source_url=url or (operator.url if operator else None), phenomenon="orca_presence",
        reasons=[summary + (" within a 25 km area in the last 72 h" if observers > 1 else "")],
        extra={"verification": "corroborated", "evidence_state": "repeated_presence",
               "observed_at": seen.isoformat(), "behavior_evidence": evidence,
               # Every contribution with its own place, time and identity.
               "contributions": [{"source": item.source, "observer": _observer_id(item), "place": item.place,
                                  "latitude": item.latitude, "longitude": item.longitude,
                                  "observed_at": item.latest.isoformat(), "url": item.url}
                                 for item in contributions],
               "evidence_note": "Orca presence only; hunting behaviour is not confirmed. A boat trip is usually required.",
               "confidence_note": "Orcas travel fast; contact an operator before booking."},
    )
