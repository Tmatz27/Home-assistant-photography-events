"""Sourced eclipse geometry, without turning ocean coordinates into a road trip.

Solar events require a known viewing site inside the published central path.
Nearby unvetted centerline points are only search leads, never destinations.
Lunar opportunities intersect actual umbral phases with local Moon visibility.
"""
from datetime import datetime, timedelta
import math

from . import astronomy as astro
from .const import CATEGORY_ASTRO
from .events import Opportunity
from .wildlife import haversine_km, estimate_drive_hours


def _bearing(a, b):
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dl = math.radians(b[1] - a[1])
    return math.atan2(math.sin(dl) * math.cos(lat2),
                      math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dl))


def segment_distance(point, start, end):
    """Great-circle segment distance in km; valid across the date line."""
    arc = haversine_km(*start, *end) / 6371
    if arc < 1e-9:
        return haversine_km(*point, *start)
    distance = haversine_km(*start, *point) / 6371
    angle = _bearing(start, point) - _bearing(start, end)
    across = math.asin(max(-1, min(1, math.sin(distance) * math.sin(angle))))
    along = math.atan2(math.sin(distance) * math.cos(angle), math.cos(distance))
    if 0 <= along <= arc:
        return abs(across) * 6371
    return min(haversine_km(*point, *start), haversine_km(*point, *end))


def central_path_margin(row, point):
    """Positive means safely inside a sampled path corridor, in kilometres.

    Use the narrower adjacent width and a 10 km margin. A coarse path table is
    sufficient for preliminary planning, not contact predictions at an edge.
    Requiring Sun altitude at the location is still necessary at the endpoints.
    """
    path = row.get("path") or []
    return max((min(a[3], b[3]) / 2 - 10 - segment_distance(point, a[1:3], b[1:3])
                for a, b in zip(path, path[1:])), default=-math.inf)


def lunar_window(row, point):
    """Visible umbral phase only, never arbitrary hours around global maximum."""
    peak = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
    duration = row.get("partial_minutes", 0)
    if duration <= 0:
        return None
    start, end = peak - timedelta(minutes=duration / 2), peak + timedelta(minutes=duration / 2)
    lat, lon = map(math.radians, point)
    visible = []
    moment = start
    while moment <= end:
        if astro.moon_altitude(moment, lat, lon) >= math.radians(5):
            visible.append(moment)
        moment += timedelta(minutes=1)
    if not visible:
        return None
    preferred = min(visible, key=lambda when: abs((when - peak).total_seconds()))
    total_half = timedelta(minutes=row.get("total_minutes", 0) / 2)
    total_visible = row.get("total_minutes", 0) > 0 and any(peak - total_half <= t <= peak + total_half for t in visible)
    return visible[0], visible[-1], preferred, total_visible


def opportunities(catalog, now, zones, home, max_drive_hours, horizon_days=365):
    found = []
    sites = [{"id": "home", "name": "Your Home Assistant location", "latitude": home[0], "longitude": home[1]}] + list(zones)
    for row in catalog.get("events", []):
        peak = datetime.fromisoformat(row["date"].replace("Z", "+00:00"))
        if not now - timedelta(hours=4) <= peak <= now + timedelta(days=horizon_days):
            continue
        if row["type"] == "penumbral":
            continue
        for site in sites:
            point = site["latitude"], site["longitude"]
            drive = 0 if site["id"] == "home" else estimate_drive_hours(*point, home)
            if drive > max_drive_hours:
                continue
            if row["kind"] == "solar":
                if central_path_margin(row, point) < 0:
                    continue
                closest = min(row["path"], key=lambda p: haversine_km(*point, p[1], p[2]))
                moment = datetime.fromisoformat(row["date"][:10] + "T" + closest[0] + ":00+00:00")
                moment = min((moment + timedelta(days=d) for d in (-1,0,1)), key=lambda t: abs((t-peak).total_seconds()))
                if astro.sun_altitude(moment, *map(math.radians, point)) < math.radians(5):
                    continue
                start = end = moment
                title = f"{row['type'].title()} solar eclipse"
                detail = "Known viewing location lies inside NASA's sampled central path. Local contact times still need a dedicated eclipse calculation."
                note = "Approximate local maximum from the nearest published path sample; road access and local contacts are not verified. Partial-only visibility outside the central path is not modelled."
                planning_only = True
            else:
                visible = lunar_window(row, point)
                if visible is None:
                    continue
                start, end, preferred, total_visible = visible
                if end <= now:
                    continue
                title = "Total lunar eclipse" if total_visible else "Partial lunar eclipse"
                detail = f"Visible umbral phase with the Moon above 5 degrees. Preferred time near {preferred:%H:%M} UTC, closest to eclipse maximum while visible."
                note = ("Totality is visible here." if total_visible else "Only the partial phase is verified as visible here.")
                note += " Other minutes within the listed window can work, but are farther from maximum eclipse. Horizon obstructions and weather can reduce visibility. NASA catalog times use its published Delta T; precision is about a minute."
                planning_only = False
            found.append(Opportunity(
                key=f"eclipse-{row['date'][:10]}-{site['id']}", roll=f"eclipse-{row['date'][:10]}",
                title=title, category=CATEGORY_ASTRO, zone_id=site["id"], zone_name=site["name"],
                start=start, end=end, score=90 if row["kind"] == "lunar" and total_visible else 75,
                detail=detail, drive_hours=round(drive, 2), latitude=point[0], longitude=point[1],
                source_url=row.get("path_url") or row["source_url"], planning_only=planning_only,
                drive_source="estimate", extra={"verification": "computed", "evidence_note": note,
                    "confidence_note": "Path-table prediction; verify local contacts." if planning_only else "",
                    "best_time_of_day": f"{preferred:%Y-%m-%d %H:%M} UTC" if row["kind"] == "lunar" else f"About {moment:%Y-%m-%d %H:%M} UTC",
                    "duration_minutes": int((end - start).total_seconds() / 60),
                    "photo_tips": "Use a tripod and long lens; exposure changes dramatically during totality." if row["kind"] == "lunar" else "Use a certified solar filter for every non-total phase."},
            ))
    return found
