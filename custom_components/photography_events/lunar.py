"""The full Moon as a horizon photograph, told in facts rather than a label.

"Supermoon" has at least two definitions - Nolle's "within 90 % of perigee"
and the looser "a full Moon near perigee" - and neither is what a photographer
needs. The useful facts are objective: when the Moon is full, how far away it
is, how large it looks, how it ranks against the year's other full Moons, and
- above all - where and when it clears the horizon relative to sunset.

So every full Moon is generated and measured, ranked within its calendar year
by distance (which is the same ranking as apparent size), and then located on
the local horizon: moonrise and moonset, their azimuths, the time and azimuth
at 0/1/2/5/10 degrees, and the overlap with sunset, sunrise and the three
twilights. "Supermoon" survives only as a secondary familiar label, attached
when Nolle's definition is actually met.

Nothing here claims a landmark alignment. Terrain and viewpoint geometry are
not modelled; the output is an azimuth to aim at, not a composition.

Verification anchors (published, see DISCOVERY_AUDIT.md): the closest full
Moon of 2026 is 24 Dec at 356,758 km, with 24 Nov (360,800 km) and 22 Jan 2027
(357,661 km) close behind. The series here reproduces those within ~20 km.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from . import astronomy as astro

MOON_RADIUS_KM = 1737.4
EARTH_RADIUS_KM = 6378.14
# Moonrise is when the upper limb meets the horizon: Meeus h0 = 0.7275*parallax
# - 34', combining parallax, refraction and semidiameter.
REFRACTION_DEG = 34 / 60
ALTITUDES = (0, 1, 2, 5, 10)
# A moonrise within this many minutes of sunset puts a low, large-looking Moon
# over a landscape still lit by the Sun. A product threshold, not optics.
PHOTOGENIC_RISE_MINUTES = 60

COMPASS = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW")

# Published by the California Coastal Commission's King Tides Project for the
# 2026-27 season. Later seasons are not guessed at; they are added when the
# Commission publishes them.
KING_TIDE_DATES = (
    (date(2026, 11, 24), date(2026, 11, 26)),
    (date(2026, 12, 23), date(2026, 12, 25)),
    (date(2027, 1, 21), date(2027, 1, 22)),
)
KING_TIDE_SOURCE = "https://www.coastal.ca.gov/kingtides/"
# A widely used tidepooling rule of thumb ("-1.0 ft or lower"); product threshold.
MINUS_TIDE_FT = -1.0


def compass(azimuth_deg: float) -> str:
    return COMPASS[int(((azimuth_deg % 360) + 11.25) // 22.5) % 16]


def moon_distance_km(moment: datetime) -> float:
    return astro.moon_equatorial(astro.days_since_j2000(moment))[2]


def angular_diameter_arcmin(distance_km: float) -> float:
    return math.degrees(2 * math.asin(MOON_RADIUS_KM / distance_km)) * 60


@dataclass
class FullMoon:
    instant: datetime
    distance_km: float
    diameter_arcmin: float
    illumination: float
    perigee_km: float
    apogee_km: float
    distance_rank: int = 0
    size_rank: int = 0
    of_year: int = 0
    labels: list[str] = field(default_factory=list)

    @property
    def nolle_supermoon(self) -> bool:
        """Nolle's definition: within 90 % of the orbit's closest approach."""
        return self.distance_km <= self.perigee_km + 0.1 * (self.apogee_km - self.perigee_km)


def _orbit_extremes(moment: datetime) -> tuple[float, float]:
    """Perigee and apogee distance of the orbit around a moment (±15 days)."""
    samples = [moon_distance_km(moment + timedelta(hours=hour)) for hour in range(-360, 361, 3)]
    return min(samples), max(samples)


def full_moons(start: datetime, end: datetime) -> list[FullMoon]:
    """Every full Moon in a span, measured."""
    found = []
    for instant in astro.full_moons_between(start, end):
        illumination, _phase, distance = astro.moon_illumination(instant)
        perigee, apogee = _orbit_extremes(instant)
        found.append(FullMoon(instant, distance, angular_diameter_arcmin(distance), illumination, perigee, apogee))
    return found


def rank_by_year(moons: list[FullMoon]) -> list[FullMoon]:
    """Rank each full Moon against the others in its calendar year.

    Only complete years are ranked honestly, so each year present is filled
    from a search of that whole year rather than from whatever span the caller
    happened to ask for.
    """
    by_year: dict[int, list[FullMoon]] = {}
    for moon in moons:
        by_year.setdefault(moon.instant.year, []).append(moon)
    for year, group in by_year.items():
        complete = full_moons(datetime(year, 1, 1, tzinfo=timezone.utc), datetime(year + 1, 1, 1, tzinfo=timezone.utc))
        ordered = sorted(complete, key=lambda item: item.distance_km)
        for moon in group:
            rank = 1 + sum(1 for other in ordered if other.distance_km < moon.distance_km - 1)
            moon.distance_rank = moon.size_rank = rank
            moon.of_year = len(ordered)
            moon.labels = _labels(moon)
    return moons


def _ordinal(number: int) -> str:
    return f"{number}{'th' if 10 <= number % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th')}"


def _labels(moon: FullMoon) -> list[str]:
    year = moon.instant.year
    labels = []
    if moon.distance_rank == 1:
        labels.append(f"Closest and largest full Moon of {year}")
    elif moon.distance_rank == moon.of_year:
        labels.append(f"Farthest full Moon of {year} (micromoon)")
    else:
        labels.append(f"{_ordinal(moon.distance_rank)} closest of {moon.of_year} full Moons in {year}")
    if moon.nolle_supermoon:
        labels.append("Meets Nolle's supermoon definition (within 90 % of perigee)")
    return labels


def topocentric_altitude_deg(moment: datetime, lat: float, lon: float) -> float:
    """Unrefracted altitude of the Moon's centre as seen from the surface."""
    ra, dec, distance = astro.moon_equatorial(astro.days_since_j2000(moment))
    altitude, _ = astro.horizontal(ra, dec, moment, lat, lon)
    parallax = math.asin(EARTH_RADIUS_KM / distance)
    return math.degrees(altitude - parallax * math.cos(altitude))


def moon_azimuth_deg(moment: datetime, lat: float, lon: float) -> float:
    ra, dec, _ = astro.moon_equatorial(astro.days_since_j2000(moment))
    return math.degrees(astro.horizontal(ra, dec, moment, lat, lon)[1]) % 360


def _rise_set(start, end, lat, lon):
    """Moonrise/moonset using Meeus's h0 for the upper limb with refraction."""
    def apparent(moment):
        _, _, distance = astro.moon_equatorial(astro.days_since_j2000(moment))
        parallax = math.degrees(math.asin(EARTH_RADIUS_KM / distance))
        return math.degrees(astro.moon_altitude(moment, lat, lon)) - (0.7275 * parallax - REFRACTION_DEG)
    crossings = astro.find_altitude_crossings(lambda m: math.radians(apparent(m)), start, end, 0.0, step_minutes=5)
    rise = next((c.moment for c in crossings if c.rising), None)
    moonset = next((c.moment for c in crossings if not c.rising and (rise is None or c.moment > rise)), None)
    return rise, moonset


def _sun_crossing(start, end, lat, lon, degrees, rising):
    crossings = astro.find_altitude_crossings(
        lambda moment: astro.sun_altitude(moment, lat, lon), start, end, math.radians(degrees))
    return next((c.moment for c in crossings if c.rising == rising), None)


def horizon_geometry(local_day: date, latitude: float, longitude: float, tz) -> dict:
    """Moon and Sun on the horizon for the evening of a local date and the next morning."""
    lat, lon = math.radians(latitude), math.radians(longitude)
    noon = datetime(local_day.year, local_day.month, local_day.day, 12, tzinfo=tz)
    end = noon + timedelta(hours=24)
    rise, moonset = _rise_set(noon, end, lat, lon)
    evening = {
        "sunset": _sun_crossing(noon, end, lat, lon, -0.833, False),
        "civil_dusk": _sun_crossing(noon, end, lat, lon, -6, False),
        "nautical_dusk": _sun_crossing(noon, end, lat, lon, -12, False),
        "astronomical_dusk": _sun_crossing(noon, end, lat, lon, -18, False),
    }
    morning_start = noon + timedelta(hours=12)
    morning_end = morning_start + timedelta(hours=12)
    morning = {
        "astronomical_dawn": _sun_crossing(morning_start, morning_end, lat, lon, -18, True),
        "nautical_dawn": _sun_crossing(morning_start, morning_end, lat, lon, -12, True),
        "civil_dawn": _sun_crossing(morning_start, morning_end, lat, lon, -6, True),
        "sunrise": _sun_crossing(morning_start, morning_end, lat, lon, -0.833, True),
    }
    climb = []
    if rise is not None:
        for target in ALTITUDES:
            crossings = astro.find_altitude_crossings(
                lambda m: math.radians(topocentric_altitude_deg(m, lat, lon)),
                rise - timedelta(minutes=30), rise + timedelta(hours=3), math.radians(target), step_minutes=2)
            moment = next((c.moment for c in crossings if c.rising), None)
            if moment is not None:
                azimuth = moon_azimuth_deg(moment, lat, lon)
                climb.append({"altitude": target, "time": moment, "azimuth": round(azimuth, 1), "compass": compass(azimuth)})
    rise_az = moon_azimuth_deg(rise, lat, lon) if rise else None
    set_az = moon_azimuth_deg(moonset, lat, lon) if moonset else None
    sunset = evening["sunset"]
    sunrise = morning["sunrise"]
    return {
        "moonrise": rise, "moonset": moonset,
        "moonrise_azimuth": round(rise_az, 1) if rise_az is not None else None,
        "moonrise_compass": compass(rise_az) if rise_az is not None else None,
        "moonset_azimuth": round(set_az, 1) if set_az is not None else None,
        "moonset_compass": compass(set_az) if set_az is not None else None,
        "climb": climb, **evening, **morning,
        "rise_after_sunset_minutes": round((rise - sunset).total_seconds() / 60) if rise and sunset else None,
        "set_after_sunrise_minutes": round((moonset - sunrise).total_seconds() / 60) if moonset and sunrise else None,
    }


def best_evening(moon: FullMoon, latitude: float, longitude: float, tz) -> tuple[date, dict]:
    """The evening near full whose moonrise lands closest to sunset."""
    local = moon.instant.astimezone(tz).date()
    options = []
    for day in (local - timedelta(days=1), local):
        geometry = horizon_geometry(day, latitude, longitude, tz)
        gap = geometry["rise_after_sunset_minutes"]
        options.append((abs(gap) if gap is not None else 10_000, day, geometry))
    _, day, geometry = min(options, key=lambda item: item[0])
    return day, geometry


def king_tide_on(day: date) -> tuple[date, date] | None:
    return next(((start, end) for start, end in KING_TIDE_DATES if start <= day <= end), None)


def _iso(value):
    return value.isoformat() if isinstance(value, datetime) else value


def opportunities(now: datetime, home: tuple[float, float], tz, horizon_days: int = 365,
                  cloud_lookup=None, eclipse_catalog: dict | None = None, coastal: bool = True) -> list:
    """Every full Moon as a planner row; the year's closest may reach the dashboard."""
    from .events import Opportunity
    from .weather_scoring import cloud_confidence, cloud_is_scorable

    moons = rank_by_year(full_moons(now - timedelta(days=1), now + timedelta(days=horizon_days)))
    lunar_eclipses = {row["date"][:10] for row in (eclipse_catalog or {}).get("events", []) if row.get("kind") == "lunar"}
    found = []
    for moon in moons:
        day, geometry = best_evening(moon, home[0], home[1], tz)
        rise = geometry["moonrise"]
        if rise is None:
            continue
        start = rise - timedelta(minutes=20)
        top = next((row["time"] for row in geometry["climb"] if row["altitude"] == 10), rise + timedelta(hours=1))
        if top < now:
            continue
        gap = geometry["rise_after_sunset_minutes"]
        closest = moon.distance_rank == 1
        notes = list(moon.labels)
        tide = king_tide_on(day) if coastal else None
        if tide:
            notes.append(f"Coincides with the Coastal Commission King Tide dates ({tide[0]:%d %b}-{tide[1]:%d %b}); a coastal high-tide frame is possible.")
        if moon.instant.date().isoformat() in lunar_eclipses:
            notes.append("A lunar eclipse falls on this full Moon; see the eclipse entry.")
        cloud = cloud_lookup(rise) if cloud_lookup else None
        lead = max(0.0, (rise - now).total_seconds() / 86400)
        timing = (f"Moonrise {rise.astimezone(tz):%H:%M} at {geometry['moonrise_azimuth']:.0f}° "
                  f"{geometry['moonrise_compass']}")
        if gap is not None:
            timing += f", {abs(gap)} min {'after' if gap >= 0 else 'before'} sunset"
        detail = f"{notes[0]}: {moon.distance_km:,.0f} km, {moon.diameter_arcmin:.1f}′ across. {timing}."
        found.append(Opportunity(
            key=f"fullmoon-{moon.instant.date().isoformat()}", roll=f"fullmoon-{moon.instant.date().isoformat()}",
            title=(f"Largest full Moon of {moon.instant.year}" if closest else f"Full Moon · {notes[0]}"),
            category="astronomy", zone_id="home", zone_name="Home horizon (Vandenberg)",
            start=start, end=top, score=70 if closest else 40, detail=detail,
            drive_hours=0.0, latitude=home[0], longitude=home[1], planning_only=not closest,
            phenomenon="full_moon_closest" if closest else "full_moon",
            reasons=[timing, *notes[1:]],
            extra={
                "verification": "computed", "evidence_state": "computed", "timing_basis": "Computed lunar and solar geometry",
                "full_moon_at": moon.instant.isoformat(), "distance_km": round(moon.distance_km),
                "diameter_arcmin": round(moon.diameter_arcmin, 2), "illumination": round(moon.illumination, 4),
                "distance_rank": moon.distance_rank, "size_rank": moon.size_rank, "full_moons_in_year": moon.of_year,
                "supermoon_nolle": moon.nolle_supermoon, "moon_labels": notes,
                "moonrise": _iso(rise), "moonset": _iso(geometry["moonset"]),
                "moonrise_azimuth": geometry["moonrise_azimuth"], "moonrise_compass": geometry["moonrise_compass"],
                "moonset_azimuth": geometry["moonset_azimuth"], "moonset_compass": geometry["moonset_compass"],
                "moon_climb": [{**row, "time": _iso(row["time"])} for row in geometry["climb"]],
                "sunset": _iso(geometry["sunset"]), "civil_dusk": _iso(geometry["civil_dusk"]),
                "nautical_dusk": _iso(geometry["nautical_dusk"]), "astronomical_dusk": _iso(geometry["astronomical_dusk"]),
                "sunrise": _iso(geometry["sunrise"]), "civil_dawn": _iso(geometry["civil_dawn"]),
                "rise_after_sunset_minutes": gap, "set_after_sunrise_minutes": geometry["set_after_sunrise_minutes"],
                "photogenic_rise": gap is not None and abs(gap) <= PHOTOGENIC_RISE_MINUTES,
                "king_tide": bool(tide),
                "cloud_cover": round(cloud, 1) if cloud is not None else None,
                "cloud_is_forecast": bool(cloud is not None and cloud_is_scorable(lead)),
                "cloud_confidence": cloud_confidence(lead) if cloud is not None else None,
                "best_time_of_day": timing,
                "access_note": "Choose a viewpoint with an open horizon toward the azimuth given. No landmark alignment has been verified.",
                "verify_urls": ["https://science.nasa.gov/moon/supermoons/", *([KING_TIDE_SOURCE] if tide else [])],
            },
        ))
    return found


def _light(moment: datetime, latitude: float, longitude: float) -> str:
    altitude = math.degrees(astro.sun_altitude(moment, math.radians(latitude), math.radians(longitude)))
    return "daylight" if altitude > 0 else "civil twilight" if altitude > -6 else "dark"


# Where King Tide rows are planned from: the NOAA station nearest home.
def _home_station(home: tuple[float, float]) -> dict:
    from .verification import TIDE_STATIONS
    from .wildlife import haversine_km

    return min(TIDE_STATIONS.values(), key=lambda row: haversine_km(home[0], home[1], row["latitude"], row["longitude"]))


def king_tide_opportunities(now: datetime, home: tuple[float, float], tz, tides: list | None = None,
                            swell=None) -> list:
    """Every published King Tide window of the season, from the day it is published.

    Two kinds of fact, kept apart. The **published date** is a planning fact
    from the Coastal Commission, available months ahead. The **exact time and
    height** is an operational prediction from NOAA, which the integration
    fetches only about 45 days ahead; until then the row says so rather than
    inventing a time. Once NOAA covers the dates, each day's highest water is
    attached with whether it falls in daylight, twilight or dark.
    """
    from .events import Opportunity
    from .wildlife import estimate_drive_hours

    station = _home_station(home)
    highs: dict[date, object] = {}
    for tide in tides or []:
        if not tide.high or getattr(tide, "station", "") not in ("", station["name"]):
            continue
        local = tide.moment.astimezone(tz)
        if king_tide_on(local.date()) and (local.date() not in highs or tide.feet > highs[local.date()].feet):
            highs[local.date()] = tide
    found = []
    for first, last in KING_TIDE_DATES:
        if last < now.astimezone(tz).date():
            continue
        start = datetime.combine(first, datetime.min.time(), tz)
        end = datetime.combine(last, datetime.max.time(), tz)
        days = [highs[day] for day in sorted(highs) if first <= day <= last]
        predictions = [{"station": station["name"], "time": tide.moment.isoformat(), "ft": tide.feet,
                        "light": _light(tide.moment, station["latitude"], station["longitude"])} for tide in days]
        extra = {
            "verification": "schedule", "evidence_state": "schedule", "king_tide": True,
            "timing_basis": "California Coastal Commission published King Tide dates",
            "operational": bool(days),
            "verify_urls": [KING_TIDE_SOURCE, "https://tidesandcurrents.noaa.gov/"],
            "access_note": "Stay off jetties, seawalls and beach access paths; waves overtop at high water.",
        }
        if days:
            best = max(days, key=lambda tide: tide.feet)
            local = best.moment.astimezone(tz)
            extra.update({
                "tide_predictions": predictions, "tide_ft": best.feet,
                "timing_basis": "Published King Tide dates; times and heights from NOAA CO-OPS predictions",
                "best_time_of_day": (f"Highest water {local:%a %d %b %H:%M}, {best.feet:.1f} ft MLLW at "
                                     f"{station['name']} ({predictions[days.index(best)]['light']})"),
            })
        else:
            extra["awaiting"] = ("Published date only. Exact times and heights appear when NOAA predictions "
                                 "cover these days (the integration fetches about 45 days ahead).")
            extra["best_time_of_day"] = "Morning high water on most King Tide days; exact time pending NOAA"
        latest = swell[-1] if swell else None
        if latest is not None and days and now - latest.time <= timedelta(hours=3) \
                and first <= now.astimezone(tz).date() + timedelta(days=1) and now.astimezone(tz).date() <= last:
            extra["swell_note"] = (f"Buoy 46011 measured {latest.height:.1f} m at {latest.period:.0f} s: with the "
                                   "King Tide, expect wave overtopping. Watch from high, set-back ground.")
        key = f"king_tide-{first.isoformat()}"
        found.append(Opportunity(
            key=key, roll=key, title="King Tides" + (" · NOAA times" if days else " (published dates)"),
            category="waves", zone_id=station["name"], zone_name=f"{station['name']} and nearby coast",
            start=start, end=end, score=50, detail=(
                f"Published King Tide dates {first:%d %b}-{last:%d %b}. "
                + ("; ".join(f"{row['ft']:.1f} ft at {datetime.fromisoformat(row['time']).astimezone(tz):%a %H:%M} ({row['light']})"
                             for row in predictions) if predictions else "Times not yet predicted.")),
            drive_hours=round(estimate_drive_hours(station["latitude"], station["longitude"], home), 2),
            latitude=station["latitude"], longitude=station["longitude"], planning_only=True,
            phenomenon="king_tide", drive_source="estimate", source_url=KING_TIDE_SOURCE, extra=extra,
        ))
    return found


def tide_opportunities(tides: list, now: datetime, home: tuple[float, float], tz) -> list:
    """Daylight minus tides, as planner rows.

    Only as far ahead as NOAA predictions are fetched (about 45 days): a minus
    tide is an operational prediction, and nothing here pretends to know one
    further out. King Tides have their own published-date rows above.
    """
    from .events import Opportunity
    from .wildlife import estimate_drive_hours

    found = []
    stations: dict[str, list] = {}
    for tide in tides or []:
        stations.setdefault(getattr(tide, "station", "") or "NOAA station", []).append(tide)
    for station, rows in stations.items():
        for tide in rows:
            local = tide.moment.astimezone(tz) if tide.moment.tzinfo else tide.moment.replace(tzinfo=tz)
            if local < now:
                continue
            daylight = 7 <= local.hour <= 18
            if tide.high or tide.feet > MINUS_TIDE_FT or not daylight:
                continue
            kind, title = "minus_tide", f"Minus tide {tide.feet:.1f} ft · {station}"
            detail = f"{tide.feet:.1f} ft MLLW at {local:%H:%M}. Arrive an hour before low water."
            key = f"{kind}-{station.lower().replace(' ', '_')}-{local.date().isoformat()}"
            if any(item.key == key for item in found):
                continue
            lat, lon = getattr(tide, "latitude", None) or home[0], getattr(tide, "longitude", None) or home[1]
            found.append(Opportunity(
                key=key, roll=key, title=title, category="waves", zone_id=station, zone_name=station,
                start=local - timedelta(hours=1), end=local + timedelta(hours=1), score=45, detail=detail,
                drive_hours=round(estimate_drive_hours(lat, lon, home), 2), latitude=lat, longitude=lon,
                planning_only=True, phenomenon=kind, drive_source="estimate",
                source_url="https://tidesandcurrents.noaa.gov/",
                extra={"verification": "computed", "evidence_state": "computed", "operational": True,
                       "timing_basis": "NOAA CO-OPS tide prediction", "tide_ft": tide.feet,
                       "access_note": "Stay off jetties and seawalls; skip during High Surf advisories."},
            ))
    return found
