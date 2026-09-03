"""Assembles scored photography opportunities from astronomy, weather, and seasons.

Pure functions over plain data so the whole pipeline can be unit tested without
Home Assistant or network access.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from . import astronomy as astro
from .const import (
    CATEGORY_ASTRO,
    CATEGORY_MARINE,
    CATEGORY_SUNSET,
    DEFAULT_HOME,
    GEAR_PROFILES,
    TARGET_ZONES,
    ZONES_BY_ID,
)
from .seasonal import active_windows
from .weather_scoring import score_sky
from .wildlife import describe_drive, estimate_drive_hours, nearest_zone

# Only showers worth a drive; the spec's ZHR floor.
MIN_METEOR_ZHR = 60

METEOR_SHOWERS: tuple[dict, ...] = (
    {"name": "Quadrantids", "month": 1, "day": 3, "zhr": 110, "ra_deg": 230.1, "dec_deg": 49.0},
    {"name": "Perseids", "month": 8, "day": 12, "zhr": 100, "ra_deg": 48.0, "dec_deg": 58.0},
    {"name": "Geminids", "month": 12, "day": 13, "zhr": 150, "ra_deg": 112.3, "dec_deg": 33.0},
    # Below the alert floor, but kept for the planning calendar.
    {"name": "Lyrids", "month": 4, "day": 22, "zhr": 18, "ra_deg": 271.4, "dec_deg": 34.0},
    {"name": "Eta Aquariids", "month": 5, "day": 5, "zhr": 50, "ra_deg": 338.0, "dec_deg": -1.0},
    {"name": "Orionids", "month": 10, "day": 21, "zhr": 20, "ra_deg": 95.0, "dec_deg": 16.0},
    {"name": "Leonids", "month": 11, "day": 17, "zhr": 15, "ra_deg": 152.0, "dec_deg": 22.0},
    {"name": "Ursids", "month": 12, "day": 22, "zhr": 10, "ra_deg": 217.4, "dec_deg": 75.0},
)

MAX_MOON_ILLUMINATION = 0.40
MIN_RADIANT_ALTITUDE = 30.0
MAX_ASTRO_CLOUD = 25.0
MIN_CORE_ALTITUDE = 15.0

# How long a sighting stays worth acting on after the last report.
SIGHTING_WINDOW_HOURS = 36
# Scraped reports describe the past, so they inform a plan and never an alert.
# This sits deliberately below the default alert threshold.
FIELD_REPORT_MAX_SCORE = 65
FIELD_REPORT_WINDOW_DAYS = 10


@dataclass
class Opportunity:
    """One scored photography opportunity at one zone."""

    key: str
    title: str
    category: str
    zone_id: str
    zone_name: str
    start: datetime
    end: datetime | None
    score: int
    detail: str
    drive_hours: float
    reasons: list[str] = field(default_factory=list)
    gear: dict[str, str] = field(default_factory=dict)
    source_url: str | None = None
    # Where to actually point a router at. Sightings are not at their nearest
    # zone, so without these the one drive time most worth resolving - the
    # vagrant at some lagoon down the road - is the one that cannot be.
    latitude: float | None = None
    longitude: float | None = None

    def as_dict(self) -> dict:
        data = asdict(self)
        data["start"] = self.start.isoformat()
        data["end"] = self.end.isoformat() if self.end else None
        return data


def _gear_for(category: str) -> dict[str, str]:
    return dict(GEAR_PROFILES.get(category, {}))


def _zone_coords(zone: dict) -> tuple[float, float]:
    return math.radians(zone["latitude"]), math.radians(zone["longitude"])


def build_sunset_opportunities(
    zone: dict,
    forecast: dict,
    now: datetime,
    threshold: int,
    days: int = 3,
) -> list[Opportunity]:
    """Score the next few sunsets and sunrises at one zone."""
    lat, lon = _zone_coords(zone)
    found: list[Opportunity] = []

    for offset in range(days):
        day = now + timedelta(days=offset)
        for rising, label in ((False, "Sunset"), (True, "Sunrise")):
            moment = astro.sun_event(day, lat, lon, rising=rising)
            if moment is None or moment < now:
                continue
            scored = score_sky(forecast, moment)
            if scored is None or scored.score < threshold:
                continue
            found.append(
                Opportunity(
                    key=f"sky-{zone['id']}-{moment.date().isoformat()}-{label.lower()}",
                    title=f"{label} could go off at {zone['name']}",
                    category=CATEGORY_SUNSET,
                    zone_id=zone["id"],
                    zone_name=zone["name"],
                    start=moment - timedelta(minutes=45),
                    end=moment + timedelta(minutes=30),
                    score=scored.score,
                    detail=f"{label} at {moment.strftime('%H:%M')} - {scored.summary}.",
                    drive_hours=zone["drive_hours"],
                    reasons=scored.reasons,
                    gear=_gear_for(CATEGORY_SUNSET),
                    latitude=zone["latitude"],
                    longitude=zone["longitude"],
                )
            )
    return found


def build_meteor_opportunities(
    zone: dict,
    now: datetime,
    horizon_days: int,
    cloud_lookup=None,
    alert_only: bool = True,
) -> list[Opportunity]:
    """Meteor shower peaks cross-checked against radiant height and moonlight."""
    lat, lon = _zone_coords(zone)
    found: list[Opportunity] = []
    horizon = now + timedelta(days=horizon_days)

    for shower in METEOR_SHOWERS:
        if alert_only and shower["zhr"] < MIN_METEOR_ZHR:
            continue
        for year in {now.year, horizon.year}:
            peak = datetime(year, shower["month"], shower["day"], 12, tzinfo=now.tzinfo)
            if not now - timedelta(days=1) <= peak <= horizon:
                continue
            window = astro.dark_window(peak, lat, lon)
            if window is None:
                continue

            radiant_alt = astro.max_altitude_in_window(
                shower["ra_deg"], shower["dec_deg"], window.start, window.end, lat, lon
            )
            illumination, _, _ = astro.moon_illumination(window.start)
            cloud = cloud_lookup(window.start) if cloud_lookup else None

            reasons = [f"ZHR ~{shower['zhr']}/hr", f"radiant peaks {round(radiant_alt)}deg"]
            score = 50
            if radiant_alt >= MIN_RADIANT_ALTITUDE:
                score += 25
            else:
                score -= 20
                reasons.append("radiant stays low here")
            if illumination <= MAX_MOON_ILLUMINATION:
                score += 20
                reasons.append(f"moon only {round(illumination * 100)}% lit")
            else:
                score -= 25
                reasons.append(f"moon {round(illumination * 100)}% lit will wash it out")
            if cloud is not None:
                if cloud <= MAX_ASTRO_CLOUD:
                    score += 15
                    reasons.append(f"{round(cloud)}% cloud")
                else:
                    score -= 20
                    reasons.append(f"{round(cloud)}% cloud forecast")
            if zone.get("bortle", 5) <= 3:
                score += 10
                reasons.append(f"Bortle {zone['bortle']} skies")

            found.append(
                Opportunity(
                    key=f"meteor-{shower['name']}-{year}-{zone['id']}",
                    title=f"{shower['name']} peak at {zone['name']}",
                    category=CATEGORY_ASTRO,
                    zone_id=zone["id"],
                    zone_name=zone["name"],
                    start=window.start,
                    end=window.end,
                    score=int(max(0, min(100, score))),
                    detail="Best after midnight once the radiant climbs. " + ", ".join(reasons) + ".",
                    drive_hours=zone["drive_hours"],
                    reasons=reasons,
                    gear=_gear_for(CATEGORY_ASTRO),
                    latitude=zone["latitude"],
                    longitude=zone["longitude"],
                )
            )
    return found


def build_milky_way_opportunities(
    zone: dict,
    now: datetime,
    horizon_days: int,
    cloud_lookup=None,
) -> list[Opportunity]:
    """Nights the galactic core clears the horizon in genuine darkness."""
    lat, lon = _zone_coords(zone)
    found: list[Opportunity] = []

    for offset in range(horizon_days):
        night = now + timedelta(days=offset)
        # The core is only up during darkness from roughly March to September.
        if not 3 <= night.month <= 9:
            continue
        window = astro.dark_window(night, lat, lon)
        if window is None:
            continue
        illumination, _, _ = astro.moon_illumination(window.start)
        if illumination > MAX_MOON_ILLUMINATION:
            continue
        core_alt = astro.max_altitude_in_window(
            astro.GALACTIC_CORE_RA_DEG, astro.GALACTIC_CORE_DEC_DEG, window.start, window.end, lat, lon
        )
        if core_alt < MIN_CORE_ALTITUDE:
            continue

        cloud = cloud_lookup(window.start) if cloud_lookup else None
        score = 45 + min(30, int(core_alt))
        reasons = [f"core reaches {round(core_alt)}deg", f"moon {round(illumination * 100)}% lit"]
        if zone.get("bortle", 5) <= 2:
            score += 20
            reasons.append(f"Bortle {zone['bortle']} - about as dark as California gets")
        elif zone.get("bortle", 5) <= 3:
            score += 10
            reasons.append(f"Bortle {zone['bortle']} skies")
        if cloud is not None:
            if cloud <= MAX_ASTRO_CLOUD:
                score += 10
                reasons.append(f"{round(cloud)}% cloud")
            else:
                score -= 25
                reasons.append(f"{round(cloud)}% cloud forecast")

        found.append(
            Opportunity(
                key=f"milkyway-{zone['id']}-{window.start.date().isoformat()}",
                title=f"Milky Way core at {zone['name']}",
                category=CATEGORY_ASTRO,
                zone_id=zone["id"],
                zone_name=zone["name"],
                start=window.start,
                end=window.end,
                score=int(max(0, min(100, score))),
                detail="Core visible during full darkness. " + ", ".join(reasons) + ".",
                drive_hours=zone["drive_hours"],
                reasons=reasons,
                gear=_gear_for(CATEGORY_ASTRO),
                latitude=zone["latitude"],
                longitude=zone["longitude"],
            )
        )
    return found


def build_seasonal_opportunities(now: datetime, horizon_days: int) -> list[Opportunity]:
    """Wildlife and botanical windows, for the planning calendar."""
    found: list[Opportunity] = []
    for window in active_windows(now, horizon_days):
        zone = ZONES_BY_ID.get(window["zone_id"])
        if zone is None:
            continue
        start = datetime.combine(window["start"], datetime.min.time()).replace(tzinfo=now.tzinfo)
        end = datetime.combine(window["end"], datetime.max.time()).replace(tzinfo=now.tzinfo)
        detail = window["detail"]
        if window["confirm"]:
            detail += " Timing shifts with the season - confirm current reports before driving."

        found.append(
            Opportunity(
                key=window["key"],
                title=f"{window['title']} - {zone['name']}",
                category=window["category"],
                zone_id=zone["id"],
                zone_name=zone["name"],
                start=start,
                end=end,
                # Seasonal windows are planning material, never a drop-everything alert.
                score=60 if window["underway"] else 45,
                detail=detail,
                drive_hours=zone["drive_hours"],
                reasons=["underway now"] if window["underway"] else ["upcoming season"],
                gear=_gear_for(window["category"]),
                latitude=zone["latitude"],
                longitude=zone["longitude"],
            )
        )
    return found


def within_drive(opportunities: list[Opportunity], max_hours: float) -> list[Opportunity]:
    return [item for item in opportunities if item.drive_hours <= max_hours]


def action_window(opportunities: list[Opportunity], now: datetime, hours: int = 48) -> list[Opportunity]:
    """Opportunities starting inside the drop-everything window."""
    cutoff = now + timedelta(hours=hours)
    return sorted(
        (item for item in opportunities if now - timedelta(hours=2) <= item.start <= cutoff),
        key=lambda item: (-item.score, item.start),
    )


def zones_for_category(category: str) -> list[dict]:
    return [zone for zone in TARGET_ZONES if category in zone["specialties"]]


# --- Live sightings ---------------------------------------------------------

# Marine draw ranking. Humpbacks are abundant off this coast in season, so a
# report of one is not news; blue whales and orcas are the reason you cancel
# your afternoon.
MARINE_DRAW = {
    "Orcinus orca": 10,
    "Balaenoptera musculus": 10,
    "Balaenoptera physalus": 6,
    "Megaptera novaeangliae": 0,
}


def build_wildlife_opportunities(
    sightings: list,
    now: datetime,
    home: tuple[float, float] | None = None,
) -> list[Opportunity]:
    """Score clustered live sightings, placing each by its own coordinates.

    Birds and whales decay differently and the scoring says so. A vagrant that
    has not been reported since the day before yesterday has almost certainly
    moved on, while whales stay as long as the food does - so the bird score
    falls off a cliff and the marine score slopes.

    Drive time comes from the sighting's position rather than from a zone. A
    rarity is far more likely to appear at some lagoon nobody listed than at one
    of the twelve destinations, and gating those out would throw away the
    closest, most actionable reports this integration receives.
    """
    origin = home or DEFAULT_HOME
    found: list[Opportunity] = []
    for sighting in sightings:
        drive_hours = estimate_drive_hours(sighting.latitude, sighting.longitude, origin)
        match = nearest_zone(sighting.latitude, sighting.longitude)
        zone_id = match[0]["id"] if match else f"sighting-{_slug(sighting.place)}"
        zone_name = sighting.place or (match[0]["name"] if match else "Reported location")

        age_hours = max(0.0, (now - sighting.latest).total_seconds() / 3600)
        observers = max(sighting.reports, len(sighting.observers))
        reasons: list[str] = []

        if sighting.category == CATEGORY_MARINE:
            score = 55
            if age_hours <= 24:
                score += 22
                reasons.append("reported in the last 24 hours")
            elif age_hours <= 48:
                score += 15
                reasons.append("reported in the last two days")
            elif age_hours <= 72:
                score += 5
                reasons.append("reported in the last three days")
            else:
                score -= 10
                reasons.append(f"last reported {round(age_hours / 24)} days ago")
            draw = MARINE_DRAW.get(sighting.scientific_name, 4)
            score += draw
            if draw >= 10:
                reasons.append("one of the species worth dropping everything for")
        else:
            score = 50
            if age_hours <= 12:
                score += 25
                reasons.append("seen this morning")
            elif age_hours <= 24:
                score += 18
                reasons.append("seen in the last 24 hours")
            elif age_hours <= 48:
                score += 8
                reasons.append("seen in the last two days")
            else:
                score -= 10
                reasons.append(f"not reported for {round(age_hours / 24)} days")

        if observers >= 3:
            score += 12
            reasons.append(f"{observers} separate reports - it is staying put")
        elif observers == 2:
            score += 6
            reasons.append("two separate reports")

        if sighting.confirmed:
            score += 8
            reasons.append("confirmed by a reviewer")
        elif observers < 2:
            # One unreviewed report is where misidentification lives. Worth
            # surfacing, not worth a two-hour drive on its own.
            score -= 5
            reasons.append("single unconfirmed report")

        if sighting.count and sighting.count > 1:
            reasons.append(f"{sighting.count} individuals")

        near = f" near {match[0]['name']}" if match else ""
        detail = (
            f"{sighting.species} at {sighting.place}{near},"
            f" {describe_drive(drive_hours)}, via {sighting.source}."
            " " + ", ".join(reasons) + "."
        )

        found.append(
            Opportunity(
                key=f"sighting-{sighting.source.lower()}-{_slug(sighting.scientific_name or sighting.species)}-{_slug(sighting.place)}",
                title=f"{sighting.species} at {sighting.place}",
                category=sighting.category,
                zone_id=zone_id,
                zone_name=zone_name,
                # A sighting is not an appointment. The window is "while it is
                # still there", so it opens now and runs out with the evidence.
                start=max(now, sighting.latest),
                end=sighting.latest + timedelta(hours=SIGHTING_WINDOW_HOURS),
                score=int(max(0, min(100, score))),
                detail=detail,
                drive_hours=round(drive_hours, 2),
                reasons=reasons,
                gear=_gear_for(sighting.category),
                source_url=sighting.url,
                latitude=sighting.latitude,
                longitude=sighting.longitude,
            )
        )
    return found


def build_field_report_opportunities(reports: list, now: datetime) -> list[Opportunity]:
    """Bloom and colour reports scraped from the hotlines.

    These are leads, not forecasts: somebody drove somewhere and wrote down what
    they saw, days ago. The score is capped below the alert threshold so a
    scraped sentence can never on its own tell you to get in the car.
    """
    found: list[Opportunity] = []
    for report in reports:
        zone = ZONES_BY_ID.get(report.zone_id)
        if zone is None:
            continue
        score = min(FIELD_REPORT_MAX_SCORE, 45 + report.strength)
        detail = f"{report.source_name}: \"{report.snippet}\" Reported {report.age_label(now)}."

        found.append(
            Opportunity(
                key=f"report-{report.source_id}-{report.zone_id}",
                title=f"{report.headline} - {zone['name']}",
                category=report.category,
                zone_id=zone["id"],
                zone_name=zone["name"],
                start=now,
                end=now + timedelta(days=FIELD_REPORT_WINDOW_DAYS),
                score=score,
                detail=detail,
                drive_hours=zone["drive_hours"],
                reasons=[f"{report.source_name} report", "confirm before driving"],
                gear=_gear_for(report.category),
                source_url=report.url,
                latitude=zone["latitude"],
                longitude=zone["longitude"],
            )
        )
    return found


def _slug(text: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in text)
    return "-".join(part for part in cleaned.split("-") if part)[:60]
