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
    CATEGORY_SUNSET,
    GEAR_PROFILES,
    TARGET_ZONES,
    ZONES_BY_ID,
)
from .seasonal import active_windows
from .weather_scoring import score_sky

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
