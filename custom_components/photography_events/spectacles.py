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



# --- Moonbow geometry ------------------------------------------------------
#
# A lunar rainbow obeys the same optics as a solar one: the bow is a circle of
# radius about 42 degrees centred on the *antilunar* point, directly opposite
# the Moon. Two consequences decide whether a night is possible at all, and
# both are arithmetic rather than folklore:
#
# - The antilunar point sits as far below the horizon as the Moon sits above
#   it. So the bow only clears the ground when the Moon is **below 42 degrees**
#   of altitude. A high Moon puts the entire bow underfoot.
# - The Moon still has to be up, and high enough to light the spray rather than
#   being screened by the valley wall. Below a few degrees there is nothing on
#   the falls at all.
#
# Add a bright Moon - moonbows are faint enough that the eye sees them white,
# and a gibbous Moon does not deliver the light - and full darkness, and the
# candidate nights fall out of the ephemeris instead of being guessed at as
# "within two days of the full Moon", which is what this replaced.
#
# What is still not modelled, and is named rather than papered over: the
# azimuth the Moon has to occupy to light one specific fall from one specific
# overlook. That is viewpoint geometry nobody has published in a form worth
# computing against, and it is the difference between a possible night and a
# predicted moonbow.
MOONBOW_MIN_ILLUMINATION = 0.90
MOONBOW_MAX_MOON_ALTITUDE = 42.0
MOONBOW_MIN_MOON_ALTITUDE = 6.0
# Full darkness, so the bow is not washed out by twilight.
MOONBOW_MAX_SUN_ALTITUDE = -12.0
MOONBOW_SAMPLE_MINUTES = 20
# A window shorter than this is a sampling artefact at the edge of the
# geometry, not an evening. Yosemite moonbows are a late-evening to small-hours
# phenomenon, so the search has to span a whole local night rather than stopping
# at midnight - an earlier version clipped every window at 01:00 local and
# reported the best nights of the year as ending exactly then, which is the
# signature of a search boundary rather than of the sky.
MOONBOW_MIN_MINUTES = 30


def moonbow_window(night, latitude, longitude):
    """The span on one night when the geometry actually permits a moonbow.

    Returns (start, end, peak_illumination) or None, for the **longest
    contiguous** run of qualifying samples.

    Contiguous is load-bearing. Near a full Moon the geometry opens after
    moonrise, shuts again while the Moon is higher than 42 degrees and the bow
    is underfoot, then reopens as it descends. Taking the first and last
    qualifying sample reports one nine-hour window across a gap in the middle
    when there is nothing to photograph - which is the same mistake as calling
    astronomical darkness a Milky Way window, made about a different object.
    """
    lat = math.radians(latitude)
    lon = math.radians(longitude)
    # Anchored on local mid-morning and run for a full 24 hours, so exactly one
    # night falls inside and neither end of it is cut off.
    start = night.replace(hour=18, minute=0, second=0, microsecond=0)
    step = timedelta(minutes=MOONBOW_SAMPLE_MINUTES)

    runs: list[list[tuple]] = []
    current: list[tuple] = []
    moment = start
    while moment <= start + timedelta(hours=24):
        illumination, _phase, _distance = astronomy.moon_illumination(moment)
        qualifies = False
        if illumination >= MOONBOW_MIN_ILLUMINATION:
            moon = math.degrees(astronomy.moon_altitude(moment, lat, lon))
            sun = math.degrees(astronomy.sun_altitude(moment, lat, lon))
            qualifies = (
                MOONBOW_MIN_MOON_ALTITUDE <= moon <= MOONBOW_MAX_MOON_ALTITUDE
                and sun <= MOONBOW_MAX_SUN_ALTITUDE
            )
        if qualifies:
            current.append((moment, illumination))
        elif current:
            runs.append(current)
            current = []
        moment += step
    if current:
        runs.append(current)

    best = None
    for run in runs:
        length = run[-1][0] - run[0][0]
        if length < timedelta(minutes=MOONBOW_MIN_MINUTES):
            continue
        if best is None or length > best[-1][0] - best[0][0]:
            best = run
    if best is None:
        return None
    return best[0][0], best[-1][0], max(value for _moment, value in best)


MOONBOW_LATITUDE = 37.756
MOONBOW_LONGITUDE = -119.596
MOONBOW_HORIZON_DAYS = 365


# Donald Olson's team at Texas State published six conditions a Yosemite
# moonbow needs, after field work at the falls in 2005 and a spherical-trig
# derivation of the geometry. They are the frame this is measured against, and
# naming them is more honest than "viewpoint geometry" as a catch-all:
#
#   1. Correct rainbow geometry ....... computed (Moon below 42 degrees)
#   2. Bright moonlight ............... computed (illumination threshold)
#   3. Dark skies ..................... computed (Sun below -12 degrees)
#   4. Abundant mist and spray ........ proxied  (USGS discharge, basin-wide)
#   5. Clear skies .................... forecast (Open-Meteo, near dates only)
#   6. Moonlight not blocked by cliffs. NOT MODELLED
#
# Six is the one that keeps this a search window rather than a prediction. The
# valley walls shadow the fall for part of every night, and which part depends
# on the Moon's azimuth against a specific skyline from a specific overlook.
# That is terrain data this does not have.
MOONBOW_SOURCES = (
    "https://www.nps.gov/yose/learn/photosmultimedia/ynn15-moonbows.htm",
    # Olson's method, and the successor site still publishing predictions.
    "https://digital.library.txst.edu/items/da48c8d5-77ef-4d6b-b8a3-8cf87ad41138",
    "https://www.yosemitemoonbow.com/",
)


def moonbow_opportunities(now, home, streamflow=None, cloud_lookup=None):
    """Nights the moonbow geometry actually permits, not a guess near a full Moon.

    This replaced a window of "the full Moon, plus or minus two days" in April,
    May and June. That was a reasonable guess and it was still a guess: it
    included nights when the Moon never drops below 42 degrees while it is dark,
    on which the bow is underfoot the entire time, and it excluded perfectly good
    nights in March and July because of the month they fell in.

    Two of the three unknowns the old entry listed are now answered. The
    geometry is computed. The water is measured - by a gauge on the Merced,
    which is the basin these falls drain and not the falls themselves, and the
    text says so in as many words. The third, the azimuth the Moon must occupy
    to light one specific fall from one specific overlook, is still not modelled
    and is still named.
    """
    found = []
    horizon = now + timedelta(days=MOONBOW_HORIZON_DAYS)
    night = now - timedelta(days=1)
    while night <= horizon:
        window = moonbow_window(night, MOONBOW_LATITUDE, MOONBOW_LONGITUDE)
        night += timedelta(days=1)
        if window is None:
            continue
        start, end, illumination = window
        if end < now:
            continue
        minutes = round((end - start).total_seconds() / 60)
        cloud = cloud_lookup(start) if cloud_lookup else None

        detail = (
            f"Geometry permits a moonbow for {minutes} min: the Moon is "
            f"{round(illumination * 100)}% lit and stays between "
            f"{round(MOONBOW_MIN_MOON_ALTITUDE)} and {round(MOONBOW_MAX_MOON_ALTITUDE)} degrees, "
            "which is the band that puts the bow above the ground rather than underfoot, "
            "in full darkness."
        )
        awaiting = (
            "Whether the valley walls shadow the fall at these hours - the sixth of Olson's "
            "six conditions, and the only one left unmodelled. It depends on the Moon's "
            "azimuth against a specific skyline from a specific overlook, which is terrain "
            "data this does not have. So these are nights the sky permits a moonbow, not "
            "nights one is predicted."
        )
        score = 58
        reasons = [
            f"{minutes} min of usable geometry",
            f"moon {round(illumination * 100)}% lit, below {round(MOONBOW_MAX_MOON_ALTITUDE)}deg",
        ]

        if streamflow is not None:
            detail += " " + streamflow.summary()
            reasons.append(f"{streamflow.name.split(' at ')[0]} {round(streamflow.cfs):,} cfs, {streamflow.trend}")
        else:
            awaiting = "Current basin flow, plus " + awaiting[4:]

        if cloud is not None:
            # Olson's first condition, and the only one of the six that a
            # forecast can answer. Beyond the forecast's reach it is simply
            # absent rather than assumed clear.
            reasons.append(f"{round(cloud)}% cloud forecast")
            if cloud <= 25:
                score += 8
            elif cloud >= 60:
                score -= 15

        found.append(Opportunity(
            key=f"moonbow-{start.date()}", title="Yosemite moonbow window", category="rare_phenomena",
            zone_id="yosemite_valley", zone_name="Yosemite Falls - viewpoint still needs confirming",
            start=start, end=end, score=max(0, min(100, score)), planning_only=True,
            detail=detail, reasons=reasons,
            drive_hours=estimate_drive_hours(MOONBOW_LATITUDE, MOONBOW_LONGITUDE, home),
            latitude=MOONBOW_LATITUDE, longitude=MOONBOW_LONGITUDE, drive_source="estimate",
            source_url=MOONBOW_SOURCES[0],
            extra={
                # The *timing* is computed and exact. The *phenomenon* is not
                # confirmed, and in this codebase "computed" means exact and
                # free to alert - which a moonbow is not, because the viewpoint
                # azimuth is unmodelled and the water is only proxied. Two
                # different facts, two different fields, and collapsing them
                # into one is how a search lead starts reading as a promise.
                "verification": "unverified",
                "timing_basis": "computed geometry",
                "special": True,
                "duration_minutes": minutes,
                "moon_illumination": round(illumination, 3),
                "awaiting": awaiting,
                "streamflow_cfs": round(streamflow.cfs) if streamflow else None,
                "streamflow_trend": streamflow.trend if streamflow else None,
                "streamflow_url": streamflow.url if streamflow else None,
                "cloud_cover": round(cloud, 1) if cloud is not None else None,
                "verify_urls": list(MOONBOW_SOURCES),
                "conditions_met": "5 of Olson's 6" if cloud is not None and streamflow is not None else "4 of Olson's 6",
                "recommended_gear": "Fast wide lens, sturdy tripod, remote release and protection from spray",
            },
        ))
    return found


def watch_opportunities(now, home, streamflow=None, cloud_lookup=None):
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
    result.extend(moonbow_opportunities(now, home, streamflow, cloud_lookup))
    return result
