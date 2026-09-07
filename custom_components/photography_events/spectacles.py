"""Dated reports and special targets. A search target is never a sighting.

Publication dates and trip totals are especially tempting false confirmations:
an article published today may describe last week, and 1,000 dolphins seen over
a whole trip do not establish one 1,000-animal pod. Parsers fail quiet on both.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree

from . import astronomy
from .const import ZONES_BY_ID
from .events import Opportunity
from .field_reports import FieldReport, strip_html
from .wildlife import estimate_drive_hours

CONDOR_FEED = "https://www.condorexpress.com/blog-feed.xml"
AURORA_FEED = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"


def condor_reports(raw, now):
    """Only the operator's explicit trip date establishes observation age."""
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return []
    reports = []
    for item in root.findall("./channel/item")[:20]:
        text = strip_html(item.findtext("description") or "")
        date = re.search(r"\b(20\d\d)\s+(\d{2})\s*[-–/]\s*(\d{2})\s+SB Channel\b", text)
        if not date:
            continue
        try:
            observed = datetime(*map(int, date.groups()), tzinfo=timezone.utc)
        except ValueError:
            continue
        if not now - timedelta(days=3) <= observed <= now:
            continue
        body = text[date.end():]
        # Require one explicitly sized pod. A list of daily sightings is not it.
        sentences = re.split(r"(?<=[.!?])\s+", body)
        confirmed = next((s for s in sentences if re.search(
            r"\b(?:mega[ -]?pod|single pod)\b.{0,55}\b(?:[1-9]\d,\d{3}|[1-9],\d{3}|[1-9]\d{3,})\s+(?:common )?dolphins\b", s, re.I)
            and not re.search(r"\b(?:no|not|yesterday|previous|last week)\b", s, re.I)), None)
        if not confirmed:
            continue
        reports.append(FieldReport(
            "condor_express", "Condor Express trip report", item.findtext("link") or CONDOR_FEED,
            "marine", "channel_islands", "Dolphin megapod reported", confirmed[:500], 90,
            now, body[:1200], observed, "dolphin_megapod",
            # The report names a region, never an exact vessel or animal position.
            None, None,
        ))
    return reports


def report_opportunities(reports, now, home):
    result = []
    for report in reports:
        if not report.phenomenon_key or report.observed_at is None:
            continue
        age = now - report.observed_at
        if not timedelta(0) <= age <= timedelta(hours=36):
            continue
        zone = ZONES_BY_ID.get(report.zone_id)
        if zone is None:
            continue
        key = f"report-{report.phenomenon_key}-{report.zone_id}-{report.observed_at.date()}"
        result.append(Opportunity(
            key=key, roll=key, title=report.headline, category=report.category,
            zone_id=report.zone_id, zone_name=zone["name"],
            start=report.observed_at, end=report.observed_at + timedelta(hours=36),
            score=85, detail=report.snippet, source_url=report.url,
            drive_hours=estimate_drive_hours(zone["latitude"], zone["longitude"], home),
            latitude=zone["latitude"], longitude=zone["longitude"], drive_source="estimate",
            extra={"verification": "corroborated", "special": True,
                   "observed_at": report.observed_at.isoformat(), "source_name": report.source_name,
                   "confidence_note": "Confirms a past observation in this region, not that the animals remain there. Contact the operator before booking.",
                   "evidence_note": "The source explicitly names the observation date and phenomenon. Location is regional."},
        ))
    return result


def aurora_opportunities(payload, now, zones, state):
    """A conservative local overhead signal, not a general geomagnetic alarm.

This deliberately misses some horizon-visible aurora. OVATION does not supply
an honest probability of photographing aurora from a particular tripod.
"""
    try:
        observation = datetime.fromisoformat(payload["Observation Time"].replace("Z", "+00:00"))
        forecast = datetime.fromisoformat(payload["Forecast Time"].replace("Z", "+00:00"))
        if not timedelta(0) <= now - observation <= timedelta(minutes=90):
            return []
        if not now - timedelta(minutes=15) <= forecast <= now + timedelta(minutes=100):
            return []
        grid = {(float(x), float(y)): float(p) for x, y, p in payload["coordinates"]}
    except (KeyError, TypeError, ValueError):
        return []
    result = []
    for zone in zones:
        lat, lon = zone["latitude"], zone["longitude"]
        value = grid.get((round(lon) % 360, round(lat)), 0)
        if not math.isfinite(value) or not 30 <= value <= 100:
            continue
        if astronomy.sun_altitude(forecast, math.radians(lat), math.radians(lon)) > math.radians(-12):
            continue
        saved = state.episodes.get("aurora", {})
        previous = datetime.fromisoformat(saved["last"]) if saved else None
        first = datetime.fromisoformat(saved["start"]) if previous and now - previous < timedelta(hours=24) else now
        state.episodes["aurora"] = {"start": first.isoformat(), "last": now.isoformat()}
        key = f"aurora-{first.date()}"
        result.append(Opportunity(
            key=key + "-" + zone["id"], roll=key, title="Exceptional local aurora forecast",
            category="astronomy", zone_id=zone["id"], zone_name=zone["name"],
            start=first, end=forecast + timedelta(minutes=30), score=88,
            detail=f"NOAA OVATION reaches {value:.0f}% at the nearest model cell for {forecast.isoformat()}. This is a model value, not your chance of seeing it.",
            drive_hours=zone["drive_hours"], latitude=lat, longitude=lon,
            source_url="https://www.swpc.noaa.gov/products/aurora-30-minute-forecast",
            extra={"verification": "forecast", "special": True,
                   "evidence_note": f"Solar-wind input timestamp: {observation.isoformat()}. Local aurora has not been visually confirmed.",
                   "confidence_note": "Short notice only. Clouds and horizon visibility remain separate; a weak local cell does not rule out distant aurora."},
        ))
    return result


# These are intentionally broad search targets. No published feed currently
# confirms behavior, glowing surf, or a moonbow at these exact locations.
WATCH_TARGETS = (
    ("bioluminescent_surf", "Bioluminescent surf", "rare_phenomena", "channel_islands", 1, 12,
     "No dependable annual date. Requires a recent report of visibly glowing water, not just a red tide.",
     "https://scripps.ucsd.edu/news/everything-you-wanted-know-about-red-tides"),
    ("waterfowl_flights", "Mass winter waterfowl flights", "birds", "carrizo_plain", 11, 2,
     "Sacramento National Wildlife Refuge is a longer-trip target. Seasonal abundance is established; the timing of a mass lift-off is not predictable. Check refuge counts and access.",
     "https://www.fws.gov/refuge/sacramento"),
    ("condor_viewing", "California condors at Pinnacles", "birds", "pinnacles", 1, 12,
     "Year-round personal target. High Peaks and the park's current viewing guidance are the starting points; individual sightings do not guarantee a repeat encounter.",
     "https://www.nps.gov/pinn/learn/nature/condor-viewing-tips.htm"),
)


def watch_opportunities(now, home):
    result = []
    for slug, title, category, zone_id, first, last, detail, url in WATCH_TARGETS:
        # Waterfowl has its own sourced refuge coordinates, not Carrizo's.
        zone = ZONES_BY_ID[zone_id]
        lat, lon, name = (39.4208, -122.1647, "Sacramento National Wildlife Refuge") if slug == "waterfowl_flights" else (zone["latitude"], zone["longitude"], zone["name"])
        for year in (now.year, now.year + 1):
            start = datetime(year, first, 1, tzinfo=now.tzinfo)
            end_year = year + (last < first)
            end = datetime(end_year + (last == 12), last % 12 + 1, 1, tzinfo=now.tzinfo) - timedelta(seconds=1)
            if end < now or start > now + timedelta(days=365):
                continue
            result.append(Opportunity(
                key=f"watch-{slug}-{year}", title=title, category=category, zone_id=slug, zone_name=name,
                start=start, end=end, score=45, planning_only=True, detail=detail,
                drive_hours=estimate_drive_hours(lat, lon, home), latitude=lat, longitude=lon,
                drive_source="estimate", source_url=url,
                extra={"verification": "unverified", "awaiting": detail, "special": True,
                       "confidence_note": "Search target; no automatic live confirmation source connected for this phenomenon."},
            ))
    for full in astronomy.full_moons_between(now - timedelta(days=2), now + timedelta(days=365)):
        if full.month not in (4, 5, 6):
            continue
        result.append(Opportunity(
            key=f"moonbow-{full.date()}", title="Yosemite moonbow candidate nights", category="rare_phenomena",
            zone_id="yosemite_valley", zone_name="Yosemite Falls — viewing position needs confirmation",
            start=full-timedelta(days=2), end=full+timedelta(days=2), score=55, planning_only=True,
            detail="Full Moon timing is calculated. These surrounding nights are a search window, not a predicted moonbow: viewpoint geometry, flowing water, spray and clear moonlight must all align.",
            drive_hours=estimate_drive_hours(37.756, -119.596, home), latitude=37.756, longitude=-119.596,
            source_url="https://www.nps.gov/yose/learn/photosmultimedia/ynn15-moonbows.htm",
            extra={"verification": "unverified", "special": True,
                   "awaiting": "Published viewpoint-specific moonbow times and current waterfall conditions. No live confirmation connected.",
                   "recommended_gear": "Fast wide lens, sturdy tripod, remote release and protection from spray"},
        ))
    return result
