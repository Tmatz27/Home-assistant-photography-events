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
    CATEGORY_PARKS,
    CATEGORY_SUNSET,
    DEFAULT_HOME,
    GEAR_PROFILES,
    TARGET_ZONES,
    ZONES_BY_ID,
)
from .parks import active_windows as active_park_windows
from .phenomena import PRECISION_HORIZON_DAYS, active_windows
from .weather_scoring import score_sky
from .wildlife import describe_drive, estimate_drive_hours, nearest_zone

# Only showers worth a drive; the spec's ZHR floor.
MIN_METEOR_ZHR = 60

METEOR_SHOWERS: tuple[dict, ...] = (
    {"name": "Quadrantids", "month": 1, "day": 3, "zhr": 120, "ra_deg": 230.1, "dec_deg": 49.0},
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
MOON_SUPPRESSION = 0.20

# --- The lunar look-ahead ---------------------------------------------------
#
# The failure this exists to prevent: a cloudless night with a 72% moon scoring
# in the nineties and shouting "go now", when the new moon nine days later is a
# categorically better night at the same site. Cloud cover is a forecast of
# tonight; moon phase is a near-certainty about next week, and a scoring model
# that only looks at tonight will always mis-rank the two.
MOON_LOOKAHEAD_DAYS = 10
MOON_LOOKAHEAD_ILLUMINATION = 0.25
MOON_LOOKAHEAD_CEILING = 75

# "Drop everything" is reserved, not earned by good cloud alone.
NEW_MOON_PROXIMITY_DAYS = 3.0
DROP_EVERYTHING_SCORE = 90
DROP_EVERYTHING_MAX_CLOUD = 15.0

# Below this a night is not worth a row of its own.
MIN_ASTRO_SCORE = 60

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
    # Trips rather than events: shown in the year view, never gated on drive
    # time, never eligible for a drop-everything alert.
    planning_only: bool = False
    extra: dict = field(default_factory=dict)
    # Where drive_hours came from, so the card can say whether it is a routed
    # figure or an estimate instead of presenting both as equally certain.
    drive_source: str = "baseline"
    drive_in_traffic: bool = False

    def as_dict(self) -> dict:
        data = asdict(self)
        data["start"] = self.start.isoformat()
        data["end"] = self.end.isoformat() if self.end else None
        return data

    def compact(self) -> dict:
        """A row for the planning view, with every repeated string factored out.

        The full form runs about a kilobyte an event, most of it gear advice and
        dog regulations that are identical across dozens of rows. A year of
        events that way is a hundred kilobytes of attribute re-sent on every
        update to say the same twenty things over and over. Gear is per
        category and park rules are per park, so both are published once as
        reference maps and looked up by key instead.
        """
        row = {
            "key": self.key,
            "title": self.title,
            "category": self.category,
            "zone_id": self.zone_id,
            "zone": self.zone_name,
            "start": self.start.isoformat(),
            "end": self.end.isoformat() if self.end else None,
            "score": self.score,
            "drive_hours": self.drive_hours,
            "drive_source": self.drive_source,
        }
        if self.planning_only:
            # A park window is a range of days, not an instant. Publishing it as
            # a timestamp implies a precision it does not have - and invites the
            # card to render "ends 23:59:59" on a three-month season.
            row["all_day"] = True
            row["start"] = self.start.date().isoformat()
            row["end"] = self.end.date().isoformat() if self.end else None
            # Everything else about a park window is in the parks reference map.
            row["planning_only"] = True
            if self.extra.get("tier"):
                row["tier"] = self.extra["tier"]
        else:
            row["detail"] = _shorten(self.detail)
            if self.reasons:
                row["reasons"] = self.reasons[:3]
            if self.source_url:
                row["source_url"] = self.source_url

        # Everything the expandable detail needs, and nothing it does not.
        for key in (
            "precision",
            "season_range",
            "duration_minutes",
            "limited_by",
            "best_time_of_day",
            "days_away",
            "confirm",
        ):
            if self.extra.get(key) not in (None, ""):
                row[key] = self.extra[key]
        if self.extra.get("primary_locations"):
            row["locations"] = self.extra["primary_locations"]
        # Only gear specific to this entry. Category gear is identical across
        # dozens of rows and is published once in the reference map instead -
        # putting it back on every row is what made the payload 100 KB.
        if self.extra.get("recommended_gear"):
            row["gear"] = self.extra["recommended_gear"]
        if self.extra.get("photo_tips"):
            row["tips"] = _shorten(self.extra["photo_tips"], 400)
        return row


def _shorten(text: str, limit: int = 160) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "\u2026"


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
    """The single peak night of each shower worth driving for.

    A shower is not a fortnight-long event. Rates climb and collapse around one
    night, and plotting the broad activity period as a date range is how a
    calendar ends up saying "Perseids" for three weeks and meaning nothing on
    any of them. Each entry here is the night of maximum, and the window inside
    it is the intersection of darkness, radiant elevation and moonlight - the
    same engine the Milky Way uses, pointed at the radiant.
    """
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

            window = astro.astro_shooting_window(
                peak,
                lat,
                lon,
                ra_deg=shower["ra_deg"],
                dec_deg=shower["dec_deg"],
                min_target_altitude=MIN_RADIANT_ALTITUDE,
                max_moon_illumination=MAX_MOON_ILLUMINATION,
            )
            if window is None:
                # Radiant never clears 30 degrees in darkness, or the moon owns
                # the whole night. Either way there is nothing to alert on.
                continue

            cloud = cloud_lookup(window.start) if cloud_lookup else None
            reasons = [
                f"ZHR ~{shower['zhr']}/hr at maximum",
                f"radiant peaks {round(window.peak_target_altitude)}deg",
                f"{window.duration_minutes} min above {round(MIN_RADIANT_ALTITUDE)}deg in darkness",
            ]

            score = 55
            score += min(20, int(window.peak_target_altitude / 3))
            if window.moon_illumination <= 0.10:
                score += 15
                reasons.append("essentially no moon")
            elif window.moon_illumination <= MAX_MOON_ILLUMINATION:
                score += 8
                reasons.append(f"moon {round(window.moon_illumination * 100)}% lit")
            if window.duration_minutes >= 180:
                score += 10
            elif window.duration_minutes < 60:
                score -= 15
                reasons.append("short radiant window")
            if zone.get("bortle", 5) <= 3:
                score += 8
                reasons.append(f"Bortle {zone['bortle']} skies")
            if cloud is not None:
                if cloud <= MAX_ASTRO_CLOUD:
                    score += 12
                    reasons.append(f"{round(cloud)}% cloud")
                else:
                    score -= 25
                    reasons.append(f"{round(cloud)}% cloud forecast")

            ceiling, ceiling_reasons = lunar_ceiling(
                peak, window.moon_illumination, _moon_down_throughout(window, lat, lon), cloud
            )
            score = min(int(max(0, min(100, score))), ceiling)
            reasons.extend(ceiling_reasons)

            found.append(
                Opportunity(
                    key=f"meteor-{shower['name']}-{year}-{zone['id']}",
                    title=f"{shower['name']} peak at {zone['name']}",
                    category=CATEGORY_ASTRO,
                    zone_id=zone["id"],
                    zone_name=zone["name"],
                    start=window.start,
                    end=window.end,
                    score=score,
                    detail=(
                        f"Peak night only. Radiant above {round(MIN_RADIANT_ALTITUDE)}deg in darkness "
                        f"for {window.duration_minutes} min. " + ", ".join(reasons) + "."
                    ),
                    drive_hours=zone["drive_hours"],
                    reasons=reasons,
                    gear=_gear_for(CATEGORY_ASTRO),
                    latitude=zone["latitude"],
                    longitude=zone["longitude"],
                    extra={
                        "duration_minutes": window.duration_minutes,
                        "limited_by": window.limited_by,
                        "zhr": shower["zhr"],
                        "moon_illumination": round(window.moon_illumination, 3),
                        "peak_altitude": round(window.peak_target_altitude, 1),
                        "score_ceiling": ceiling,
                    },
                )
            )
    return found


def lunar_ceiling(
    night: datetime,
    illumination: float,
    moon_down_all_window: bool,
    cloud: float | None,
) -> tuple[int, list[str]]:
    """The highest score a night is allowed, given what is coming.

    Two separate caps, for two separate reasons:

    - **A better night is imminent.** If a new moon falls inside the next ten
      days and tonight is washed by more than a quarter-lit moon, tonight is
      not a ninety-something however clear it is. It is capped at 75 - still
      listed, still worth knowing, but never a drop-everything.
    - **Ninety-plus is reserved.** It means darkness that will not come again
      for a month: within three days of new moon, or a moon that is down for
      the whole window, *and* genuinely clear skies. Anything else tops out at
      89 no matter what the components add up to.
    """
    reasons: list[str] = []
    ceiling = 100

    upcoming = astro.next_new_moon(night, horizon_days=int(MOON_LOOKAHEAD_DAYS))
    if upcoming is not None and illumination > MOON_LOOKAHEAD_ILLUMINATION:
        ceiling = MOON_LOOKAHEAD_CEILING
        days = max(1, round((upcoming - night).total_seconds() / 86400))
        reasons.append(f"new moon in {days} days will be far darker - worth waiting")

    _, offset_days = astro.nearest_new_moon(night)
    near_new = abs(offset_days) <= NEW_MOON_PROXIMITY_DAYS
    if not (near_new or moon_down_all_window):
        ceiling = min(ceiling, DROP_EVERYTHING_SCORE - 1)
    if cloud is None or cloud >= DROP_EVERYTHING_MAX_CLOUD:
        ceiling = min(ceiling, DROP_EVERYTHING_SCORE - 1)

    return ceiling, reasons


def _moon_down_throughout(window, lat: float, lon: float) -> bool:
    """Whether the Moon stays below the horizon for the whole window."""
    span = window.end - window.start
    return all(
        astro.moon_altitude(window.start + span * fraction, lat, lon) < 0
        for fraction in (0.0, 0.25, 0.5, 0.75, 1.0)
    )


def build_milky_way_opportunities(
    zone: dict,
    now: datetime,
    horizon_days: int,
    cloud_lookup=None,
) -> list[Opportunity]:
    """Nights the galactic core is actually shootable, and for how long.

    The window is the intersection of darkness, core elevation and moonlight -
    never the span of astronomical night. In September from California the core
    is below the ridgeline by half past ten, so a dusk-to-dawn window overstates
    the real opportunity roughly fivefold and sends you out on the wrong night.
    """
    lat, lon = _zone_coords(zone)
    found: list[Opportunity] = []

    for offset in range(horizon_days):
        night = now + timedelta(days=offset)
        window = astro.astro_shooting_window(night, lat, lon)
        if window is None:
            continue

        cloud = cloud_lookup(window.start) if cloud_lookup else None
        moon_down = _moon_down_throughout(window, lat, lon)

        score = 40
        reasons = [
            f"core peaks at {round(window.peak_target_altitude)}deg",
            f"{window.duration_minutes} min of usable darkness",
        ]
        score += min(25, int(window.peak_target_altitude))
        # Duration cuts both ways. A twenty-minute slot between the end of
        # twilight and the core dropping into the haze is not a good night with
        # a caveat - it is barely worth the drive, and scoring it in the
        # eighties is how this thing loses trust.
        if window.duration_minutes >= 180:
            score += 15
        elif window.duration_minutes >= 120:
            score += 10
        elif window.duration_minutes >= 75:
            score += 5
        elif window.duration_minutes >= 45:
            score -= 10
            reasons.append("short window - set up before dark")
        else:
            score -= 25
            reasons.append(f"only {window.duration_minutes} min - marginal")

        if window.moon_illumination <= 0.05:
            score += 10
            reasons.append("no moon at all")
        elif window.moon_illumination <= MOON_SUPPRESSION:
            score += 5
            reasons.append(f"moon only {round(window.moon_illumination * 100)}% lit")
        elif moon_down:
            score += 5
            reasons.append("moon down for the whole window")
        else:
            reasons.append(f"moon {round(window.moon_illumination * 100)}% lit")

        bortle = zone.get("bortle", 5)
        if bortle <= 2:
            score += 15
            reasons.append(f"Bortle {bortle} - about as dark as California gets")
        elif bortle <= 3:
            score += 8
            reasons.append(f"Bortle {bortle} skies")

        if cloud is not None:
            if cloud <= DROP_EVERYTHING_MAX_CLOUD:
                score += 12
                reasons.append(f"{round(cloud)}% cloud")
            elif cloud <= MAX_ASTRO_CLOUD:
                score += 6
                reasons.append(f"{round(cloud)}% cloud")
            elif cloud > 40:
                score -= 25
                reasons.append(f"{round(cloud)}% cloud forecast")

        ceiling, ceiling_reasons = lunar_ceiling(night, window.moon_illumination, moon_down, cloud)
        score = min(int(max(0, min(100, score))), ceiling)
        reasons.extend(ceiling_reasons)

        if score < MIN_ASTRO_SCORE:
            continue

        detail = (
            f"Core above {round(astro.MIN_CORE_ALTITUDE_DEG)}deg in full darkness for "
            f"{window.duration_minutes} min. " + ", ".join(reasons) + "."
        )
        if window.is_brief and window.limited_by == "target":
            detail = (
                f"Brief window: core sets early at {window.target_sets.strftime('%H:%M')}. " + detail
            )

        found.append(
            Opportunity(
                key=f"milkyway-{zone['id']}-{window.start.date().isoformat()}",
                title=f"Milky Way core at {zone['name']}",
                category=CATEGORY_ASTRO,
                zone_id=zone["id"],
                zone_name=zone["name"],
                start=window.start,
                end=window.end,
                score=score,
                detail=detail,
                drive_hours=zone["drive_hours"],
                reasons=reasons,
                gear=_gear_for(CATEGORY_ASTRO),
                latitude=zone["latitude"],
                longitude=zone["longitude"],
                extra={
                    "duration_minutes": window.duration_minutes,
                    "limited_by": window.limited_by,
                    "target_sets": window.target_sets.isoformat() if window.target_sets else None,
                    "moon_illumination": round(window.moon_illumination, 3),
                    "peak_altitude": round(window.peak_target_altitude, 1),
                    "score_ceiling": ceiling,
                },
            )
        )
    return found


# A background season is planning material and nothing more. Only a concrete
# peak window may reach the alert threshold, and only as it opens.
SEASON_SCORE = 45
PEAK_UPCOMING_SCORE = 65
PEAK_UNDERWAY_SCORE = 78
UNCONFIRMED_PENALTY = 8


def build_seasonal_opportunities(
    now: datetime,
    horizon_days: int,
    home: tuple[float, float] | None = None,
) -> list[Opportunity]:
    """Natural phenomena, told at the precision the distance justifies.

    Beyond thirty days an entry reports its background season and scores as
    planning material - "gray whales, December to May" is the most honest thing
    anyone can say four months out, and dressing it up as an appointment would
    be a lie. Inside thirty days it switches to the concrete peak window and
    carries the locations, gear and behaviour notes, and only then can it reach
    the alert threshold.

    The alert fires as the window *opens*, not every day it is open: the
    48-hour action window admits an opportunity by its start date, so a
    five-week rut peak announces itself once rather than for thirty-five
    consecutive days.
    """
    origin = home or DEFAULT_HOME
    found: list[Opportunity] = []

    for entry in active_windows(now, horizon_days):
        window = entry["window"]
        near = entry["precision"] == "peak"
        drive_hours = estimate_drive_hours(window.latitude, window.longitude, origin)

        if not near:
            score = SEASON_SCORE
            detail = (
                f"{window.name}. Background season: {window.season_range}. Peak window is "
                f"{entry['start']:%d %b} to {entry['end']:%d %b}; specifics firm up inside "
                f"{PRECISION_HORIZON_DAYS} days."
            )
            reasons = [f"season: {window.season_range}", "too far out for specifics"]
        else:
            score = PEAK_UNDERWAY_SCORE if entry["underway"] else PEAK_UPCOMING_SCORE
            if window.confirm:
                score -= UNCONFIRMED_PENALTY
            state = "underway now" if entry["underway"] else f"opens in {entry['days_away']} days"
            detail = (
                f"Peak window {entry['start']:%d %b} to {entry['end']:%d %b} ({state}). "
                f"{window.photo_tips}"
            )
            reasons = [
                state,
                f"peak of a season that runs {window.season_range}",
                window.primary_locations[0],
            ]
            if window.best_time_of_day:
                reasons.append(window.best_time_of_day)
            if window.confirm:
                reasons.append("timing shifts year to year - confirm before driving")

        found.append(
            Opportunity(
                key=entry["key"],
                title=window.name if near else f"{window.name} (season)",
                category=window.category,
                zone_id=window.key,
                zone_name=window.primary_locations[0],
                start=datetime.combine(entry["start"], datetime.min.time()).replace(tzinfo=now.tzinfo),
                end=datetime.combine(entry["end"], datetime.max.time()).replace(tzinfo=now.tzinfo),
                score=score,
                detail=detail,
                drive_hours=round(drive_hours, 2),
                reasons=reasons,
                gear={"glass": window.recommended_gear, "settings": window.photo_tips},
                latitude=window.latitude,
                longitude=window.longitude,
                drive_source="estimate",
                # A background season is never something to act on today.
                planning_only=not near,
                extra={
                    "precision": entry["precision"],
                    "season_range": window.season_range,
                    "peak_start": entry["start"].isoformat(),
                    "peak_end": entry["end"].isoformat(),
                    "days_away": entry["days_away"],
                    "primary_locations": list(window.primary_locations),
                    "recommended_gear": window.recommended_gear,
                    "photo_tips": window.photo_tips,
                    "best_time_of_day": window.best_time_of_day,
                    "confirm": window.confirm,
                    "lunar_dependent": window.lunar_dependent,
                },
            )
        )
    return found


def within_drive(opportunities: list[Opportunity], max_hours: float) -> list[Opportunity]:
    """Drop what is too far to drive to, keeping the trips you plan instead.

    The drive limit answers "could I be there tonight", which is the wrong
    question for a national park eight hours away - you go there for a long
    weekend, and gating it out would defeat the point of listing it.
    """
    return [item for item in opportunities if item.planning_only or item.drive_hours <= max_hours]


def action_window(opportunities: list[Opportunity], now: datetime, hours: int = 48) -> list[Opportunity]:
    """Opportunities starting inside the drop-everything window."""
    cutoff = now + timedelta(hours=hours)
    return sorted(
        (
            item
            for item in opportunities
            if not item.planning_only and now - timedelta(hours=2) <= item.start <= cutoff
        ),
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
                drive_source="estimate",
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


# --- Parks ------------------------------------------------------------------

PARK_OPTIMAL_SCORE = 55
PARK_GOOD_SCORE = 40


def build_park_opportunities(now: datetime, horizon_days: int) -> list[Opportunity]:
    """National park and monument seasons, for the year view.

    Scored well below the alert threshold and flagged ``planning_only``, because
    a park is not something that happens - it is somewhere that is worth the
    drive in some months and not others, and no scoring should ever turn that
    into a reason to leave the house right now.
    """
    found: list[Opportunity] = []
    for window in active_park_windows(now, horizon_days):
        park = window["park"]
        optimal = window["tier"] == "optimal"
        score = PARK_OPTIMAL_SCORE if optimal else PARK_GOOD_SCORE
        if window["underway"]:
            score += 5

        tier_text = "Best window" if optimal else "Good window"
        reasons = [f"{tier_text.lower()} for this park", park.drive_label, park.dog_label]

        found.append(
            Opportunity(
                key=window["key"],
                title=f"{park.name} - {tier_text.lower()}",
                category=CATEGORY_PARKS,
                zone_id=park.key,
                zone_name=park.name,
                start=datetime.combine(window["start"], datetime.min.time()).replace(tzinfo=now.tzinfo),
                end=datetime.combine(window["end"], datetime.max.time()).replace(tzinfo=now.tzinfo),
                score=score,
                detail=f"{tier_text} to visit {park.name} ({park.drive_label}). Dogs: {park.dog_detail}",
                drive_hours=park.drive_hours,
                reasons=reasons,
                gear=_gear_for(CATEGORY_PARKS),
                latitude=park.latitude,
                longitude=park.longitude,
                planning_only=True,
                extra={
                    "tier": window["tier"],
                    "miles": park.miles,
                    "dogs": park.dogs,
                    "dog_label": park.dog_label,
                    "dog_detail": park.dog_detail,
                },
            )
        )
    return found
