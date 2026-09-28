"""Assembles scored photography opportunities from astronomy, weather, and seasons.

Pure functions over plain data so the whole pipeline can be unit tested without
Home Assistant or network access.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from . import astronomy as astro
from .event_state import event_id
from .const import (
    CATEGORY_ASTRO,
    CATEGORY_PARKS,
    CATEGORY_SUNSET,
    DEFAULT_HOME,
    GEAR_PROFILES,
    TARGET_ZONES,
    ZONES_BY_ID,
)
from .parks import active_windows as active_park_windows
from .phenomena import (
    WINDOWS_BY_KEY,
    EVIDENCE_CALENDAR,
    EVIDENCE_COMPUTED,
    EVIDENCE_LIVE,
    EVIDENCE_STATIC,
    LIVE_CORROBORATION_DAYS,
    LIVE_CORROBORATION_KM,
    PRECISION_HORIZON_DAYS,
    active_windows,
)
from .weather_scoring import SkyScore, cloud_confidence, cloud_is_scorable, mark_standouts, score_sky
from .verification import grunion_run_window
from .wildlife import estimate_drive_hours, haversine_km

# Only showers worth a drive; the spec's ZHR floor.
MIN_METEOR_ZHR = 60

# --- Why these are longitudes and not dates ---------------------------------
#
# A meteor stream sits at a fixed place in the Earth's orbit, so the Earth
# reaches it at the same *solar longitude* every year - but on a calendar date
# that slides by up to a day with the leap cycle. "Geminids, 13 December" is
# therefore wrong roughly one year in two, by a whole night, and a shower that
# peaks over a few hours does not forgive that.
#
# So the table stores what is actually constant. Every ``lambda_sun`` below is
# the maximum from the IMO Working List of Visual Meteor Showers, given - as
# the IMO gives all of them - for the equinox J2000.0; ``solar_longitude_crossing``
# applies the precession back to the equinox of date, which by now is a third
# of a degree and eight hours' worth of Sun. Radiants are J2000 as published.
#
# Cross-check: lambda 140.0 puts the 2025 Perseid maximum at 12 August, 19h UT,
# which is the hour the IMO published for it.
METEOR_SHOWERS: tuple[dict, ...] = (
    {"name": "Quadrantids", "lambda_sun": 283.15, "zhr": 120, "ra_deg": 230.1, "dec_deg": 49.0},
    {"name": "Perseids", "lambda_sun": 140.0, "zhr": 100, "ra_deg": 48.0, "dec_deg": 58.0},
    {"name": "Geminids", "lambda_sun": 262.2, "zhr": 150, "ra_deg": 112.0, "dec_deg": 33.0},
    # Below the alert floor, but kept for the planning calendar.
    {"name": "Lyrids", "lambda_sun": 32.32, "zhr": 18, "ra_deg": 271.4, "dec_deg": 34.0},
    {"name": "Eta Aquariids", "lambda_sun": 45.5, "zhr": 50, "ra_deg": 338.0, "dec_deg": -1.0},
    {"name": "Orionids", "lambda_sun": 208.0, "zhr": 20, "ra_deg": 95.0, "dec_deg": 16.0},
    {"name": "Leonids", "lambda_sun": 235.27, "zhr": 15, "ra_deg": 152.0, "dec_deg": 22.0},
    {"name": "Ursids", "lambda_sun": 270.66, "zhr": 10, "ra_deg": 217.0, "dec_deg": 76.0},
)

# IMO 2026 Calendar, Table 6, p26. Differences between the five-day positions
# either side of maximum, in degrees/day (RA, Dec). The offline audit found
# changed usable-night verdicts, so ignoring this is not harmless at the gate.
# DOI 10.13140/RG.2.2.36179.08480; see tools/check_meteor_drift.py for anchors.
RADIANT_DRIFT = {
    "Quadrantids": (0.6, -0.2), "Lyrids": (1.0, 0.0),
    "Eta Aquariids": (0.8, 0.4), "Perseids": (1.2, 0.2),
    "Orionids": (0.8, 0.0), "Leonids": (0.6, -0.4),
    "Geminids": (1.0, 0.0), "Ursids": (0.0, -0.4),
}

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
    # The identity of the *thing*, independent of where you watch it from. The
    # Milky Way core is up over all twelve zones on the same night, and a
    # calendar that says so twelve times has buried everything else. Rows
    # sharing a roll key collapse into one, best zone winning, the rest listed
    # inside it - so the choice of where to drive survives, one level down.
    # Empty means "this row is genuinely one of a kind"; nothing collapses.
    roll: str = ""
    # Where drive_hours came from, so the card can say whether it is a routed
    # figure or an estimate instead of presenting both as equally certain.
    drive_source: str = "baseline"
    drive_in_traffic: bool = False
    # Which curated phenomenon this row is an occurrence of (curation.CATALOG).
    # Eligibility, gear and ethics are looked up from it, never inferred from
    # the title.
    phenomenon: str = ""

    @property
    def time_precision(self) -> str:
        """``interval`` for real instants, ``day`` for date-valued windows.

        Independent of ``planning_only`` (an evidence class). A builder that
        knows its row is a real shooting interval says so with
        ``extra["time_precision"] = "interval"`` or a ``timing_basis``; a
        planning row without either is a date range (seasons, park windows).
        """
        explicit = self.extra.get("time_precision")
        if explicit in ("interval", "day"):
            return explicit
        if self.extra.get("timing_basis") or not self.planning_only or self.category == "waves":
            return "interval"
        return "day"

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
            "event_id": event_id(self),
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
        if self.phenomenon:
            row["phenomenon"] = self.phenomenon
        row["time_precision"] = self.time_precision
        # What the eligibility gate decided, so the planner can say "this one
        # made Can't Miss" or "watch only" without re-deriving it.
        for key in ("presentation", "significance", "eligible", "why_now", "status", "blockers"):
            value = (self.extra.get("assessment") or {}).get(key)
            if value not in (None, "", []):
                row[key] = value
        if self.roll:
            row["roll"] = self.roll
        where = (self.extra.get("primary_locations") or [None])[0] or self.zone_name
        if where:
            row["where"] = where
        if self.planning_only:
            # A park window is a range of days, not an instant. Publishing it as
            # a timestamp implies a precision it does not have - and invites the
            # card to render "ends 23:59:59" on a three-month season.
            if self.category != CATEGORY_PARKS:
                row["detail"] = _shorten(self.detail, 400)
            # Planning-only describes evidence, not time precision. A computed
            # moonbow candidate or a CDFW grunion interval still has real
            # hours; stripping it to a date hid them and, converted in UTC,
            # could move a late-evening run to the next day.
            if self.time_precision == "day":
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

        if self.source_url:
            row["source_url"] = self.source_url
        # Everything the expandable detail needs, and nothing it does not.
        if self.extra.get("verify_urls"):
            row["verify"] = self.extra["verify_urls"]
        for key in (
            "timing_basis", "streamflow_cfs", "streamflow_trend", "streamflow_url",
            "streamflow_observed_at", "condition_states",
            "precision",
            "season_range",
            "duration_minutes",
            "limited_by",
            "light_path",
            "verification",
            "awaiting",
            "best_time_of_day",
            "days_away",
            "confirm",
            "observed_at", "source_name", "evidence_note", "closures", "closure_source",
            "closure_urls", "tide_window_start", "tide_window_end", "needs_tide_table",
            "special", "wave_height_m", "wave_period_s", "wave_direction_deg",
            "measurement_label", "forecast_note", "access_note", "locations_detail",
            "feed_status", "confidence_note", "coastal_advisories",
            "moon_illumination", "peak_altitude", "cloud_cover", "comparison_through",
            "cloud_confidence", "cloud_is_forecast", "degraded_sources", "source_health_note", "degraded_required", "fallback_note",
            "evidence_state", "behavior_evidence", "presence_count", "count", "current_phase", "phases",
            "provider_quality", "provider_percent", "provider_model", "provider_valid_at", "provider_note",
            "sunset_at", "color_window_start", "color_window_end", "moonrise", "moonset",
            "moonrise_azimuth", "moonrise_compass", "moonset_compass", "moon_climb", "distance_km",
            "diameter_arcmin", "distance_rank", "full_moons_in_year", "moon_labels", "rise_after_sunset_minutes",
            "sunrise", "civil_dusk", "nautical_dusk", "astronomical_dusk", "king_tide", "tide_ft",
            "dawn_temp_f", "safety_notes", "safety_summary", "safety_state", "eclipse_type",
            "clearing_at", "firefall_sunset", "light_path_gate", "tide_predictions", "operational",
            "swell_note", "dawn_wind_ms", "dawn_precip_probability", "sunset", "moonset_azimuth",
            "set_after_sunrise_minutes", "civil_dawn", "supermoon_nolle", "illumination", "size_rank",
            "full_moon_at", "ethics", "gear_plan", "drive_basis", "route_fetched_at", "access_state",
            "access_detail", "location_precision", "live_occurrence", "air_quality_note", "contributions",
            "held_reasons", "time_precision",
        ):
            if self.extra.get(key) not in (None, ""):
                row[key] = self.extra[key]
        if self.extra.get("standout"):
            row["standout"] = True
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
    upstream: dict | None = None,
    air_quality: dict | None = None,
    provider: list | None = None,
) -> list[Opportunity]:
    """Score the next few sunsets and sunrises at one place - in practice, home.

    Every candidate in the window is scored before any is filtered, because
    "should I go tonight" is a comparison and not a threshold. A sky only earns
    the standout flag - and with it the right to raise an alert - when nothing
    in the forecast window beats it. That is the difference between being told
    about a good sunset and being told about *the* sunset.

    ``provider`` is a purpose-built external forecast (SunsetWx) when one is
    configured. It becomes the primary opinion: a sky the provider rates in its
    top tier is listed even if the local model is lukewarm, and the local score
    rides along as a comparison. Without it the local model decides alone and
    says so.
    """
    from . import sunburst

    lat, lon = _zone_coords(zone)
    upstream = upstream or {}
    candidates: list[tuple[datetime, bool, str, object]] = []

    for offset in range(days):
        day = now + timedelta(days=offset)
        for rising, label in ((False, "Sunset"), (True, "Sunrise")):
            moment = astro.sun_event(day, lat, lon, rising=rising)
            if moment is None or moment < now:
                continue
            scored = score_sky(
                forecast,
                moment,
                upstream=upstream.get("sunrise" if rising else "sunset"),
                air_quality=air_quality,
            ) if forecast else None
            # A current provider forecast can stand on its own: the local
            # model is a comparison, and its absence must not erase the
            # provider's answer (source roles decide *before* scoring).
            if scored is None and not sunburst.match(provider or [], label.lower(), moment):
                continue
            candidates.append((moment, rising, label, scored))

    mark_standouts([scored for _, _, _, scored in candidates if scored is not None])

    local_home = zone.get("id") == "home"
    found: list[Opportunity] = []
    for moment, rising, label, scored in candidates:
        external = sunburst.match(provider or [], label.lower(), moment)
        top_tier = bool(external and external["quality"] == sunburst.TOP_TIER)
        if scored is None:
            if not top_tier:
                continue
            scored = SkyScore(score=round(external["percent"]), reasons=[f"SunsetWx {external['quality']}"],
                              light_path="provider", limited_by="local model unavailable")
        elif scored.score < threshold and not top_tier:
            continue
        if local_home:
            when = "tonight" if not rising and moment.date() == now.date() else (
                "tomorrow morning" if rising else f"on {moment:%a %d %b}")
            title = f"{label} could be exceptional {when}"
        else:
            title = (
                f"{label} is the best in the forecast at {zone['name']}"
                if scored.standout
                else f"{label} could go off at {zone['name']}"
            )
        # The colour usually builds after the Sun is down; a sunrise mirrors it.
        colour_start = moment - timedelta(minutes=10 if not rising else 25)
        colour_end = moment + timedelta(minutes=25 if not rising else 10)
        extra = {
            "standout": scored.standout,
            "light_path": scored.light_path,
            "limited_by": scored.limited_by,
            "sky": scored.detail,
            "evidence_state": "forecast",
            "verification": "forecast",
            "sunset_at": moment.isoformat(),
            "color_window_start": colour_start.isoformat(),
            "color_window_end": colour_end.isoformat(),
            "best_time_of_day": ("Best colour usually from about 10 minutes before to 25 minutes after sunset"
                                 if not rising else "Best colour usually from about 25 minutes before sunrise to 10 minutes after"),
            "local_score": scored.score if scored.light_path != "provider" else None,
        }
        if external:
            extra.update({
                "provider_quality": external["quality"],
                "provider_percent": external["percent"],
                "provider_model": external["model"],
                "provider_valid_at": external["valid_at"].isoformat(),
                "provider_note": f"{sunburst.ATTRIBUTION}. {external['quality']} ({external['percent']:.0f}%) is their forecast score, not a probability.",
            })
        found.append(
            Opportunity(
                key=f"sky-{zone['id']}-{moment.date().isoformat()}-{label.lower()}",
                roll=f"sky-{moment.date().isoformat()}-{label.lower()}",
                title=title,
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
                phenomenon="sunset_local",
                extra=extra,
            )
        )
    return found


def expected_meteor_rate(zhr: int, radiant_altitude_deg: float) -> int:
    """What you will actually see, rather than the number in the headline.

    A zenithal hourly rate is an idealisation: perfect skies, and the radiant
    straight overhead. Neither is ever true. The standard correction scales by
    the sine of the radiant altitude, and it is brutal - the Geminids' famous
    150 becomes about 80 with the radiant at 32 degrees. Quoting the ZHR is how
    somebody drives two hours expecting two a minute and sees one every three.
    """
    altitude = max(0.0, min(90.0, radiant_altitude_deg))
    return max(1, int(round(zhr * math.sin(math.radians(altitude)))))


def _best_meteor_night(peak: datetime, lat: float, lon: float, shower: dict):
    """Of the two nights either side of the maximum, the one to actually go out on.

    A maximum computed to the hour lands in the middle of somebody's afternoon
    about half the time, and then "the peak night" is genuinely ambiguous. Both
    candidates are evaluated and the one whose dark, radiant-up window sits
    closest to the maximum wins - which is the question an observer is asking
    anyway, and is not answerable from the date alone.
    """
    best = None
    best_gap = None
    for offset in (-1, 0):
        night = (peak + timedelta(days=offset)).replace(hour=12, minute=0, second=0, microsecond=0)
        window = astro.astro_shooting_window(
            night,
            lat,
            lon,
            ra_deg=shower["ra_deg"],
            dec_deg=shower["dec_deg"],
            min_target_altitude=MIN_RADIANT_ALTITUDE,
            max_moon_illumination=MAX_MOON_ILLUMINATION,
            radiant_drift=RADIANT_DRIFT.get(shower["name"], (0.0, 0.0)),
            radiant_epoch=peak,
        )
        if window is None:
            continue
        middle = window.start + (window.end - window.start) / 2
        gap = abs((middle - peak).total_seconds())
        if best_gap is None or gap < best_gap:
            best, best_gap = window, gap
    return best


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
            peak = astro.solar_longitude_crossing(year, shower["lambda_sun"], tz=now.tzinfo)
            if peak is None or not now - timedelta(days=1) <= peak <= horizon:
                continue

            window = _best_meteor_night(peak, lat, lon, shower)
            if window is None:
                # Radiant never clears 30 degrees in darkness, or the moon owns
                # the whole night. Either way there is nothing to alert on.
                continue

            cloud = cloud_lookup(window.start) if cloud_lookup else None
            lead_days = max(0, (window.start - now).total_seconds() / 86400)
            expected = expected_meteor_rate(shower["zhr"], window.peak_target_altitude)
            reasons = [
                f"expect roughly {expected}/hr from here (ZHR {shower['zhr']} at the zenith)",
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
                    reasons.append(f"{round(cloud)}% cloud {'forecast' if cloud_is_scorable(lead_days) else 'outlook'}")

            ceiling, ceiling_reasons = lunar_ceiling(
                peak, window.moon_illumination, _moon_down_throughout(window, lat, lon), cloud
            )
            score = min(int(max(0, min(100, score))), ceiling)
            reasons.extend(ceiling_reasons)

            found.append(
                Opportunity(
                    phenomenon="meteor_major" if shower["zhr"] >= MIN_METEOR_ZHR else "meteor_minor",
                    key=f"meteor-{shower['name']}-{year}-{zone['id']}",
                    roll=f"meteor-{shower['name']}-{year}",
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
                        "verification": "computed",
                        "evidence_state": "computed",
                        "duration_minutes": window.duration_minutes,
                        "limited_by": window.limited_by,
                        "zhr": shower["zhr"],
                        "expected_rate": expected,
                        "cloud_cover": round(cloud, 1) if cloud is not None else None,
                        "cloud_confidence": cloud_confidence(lead_days) if cloud is not None else None,
                        "cloud_is_forecast": bool(cloud is not None and cloud_is_scorable(lead_days)),
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
        # How far out this night is decides what the cloud number may be
        # *called*. Inside a week it is a forecast; past that it is an outlook,
        # and the difference is the difference between a comparison somebody can
        # lean on and one that quietly pretends to skill it does not have.
        lead_days = max(0.0, (window.start - now).total_seconds() / 86400)
        forecast_cloud = cloud_is_scorable(lead_days)
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
            # Cloud ranks every night, near or far: choosing between alternates
            # three weeks out is what this list is for, and the outlook is the
            # only cloud information those nights have. What changes with
            # distance is what it is called. It cannot leak into an alert either
            # way - the drop-everything sensor only ever sees the 48-hour action
            # window, so a distant night is structurally barred from raising one
            # however well it scores.
            suffix = "" if forecast_cloud else " outlook"
            if cloud <= DROP_EVERYTHING_MAX_CLOUD:
                score += 12
                reasons.append(f"{round(cloud)}% cloud{suffix}")
            elif cloud <= MAX_ASTRO_CLOUD:
                score += 6
                reasons.append(f"{round(cloud)}% cloud{suffix}")
            elif cloud > 40:
                score -= 25
                reasons.append(f"{round(cloud)}% cloud {'forecast' if forecast_cloud else 'outlook'}")

        ceiling, ceiling_reasons = lunar_ceiling(night, window.moon_illumination, moon_down, cloud)
        score = min(int(max(0, min(100, score))), ceiling)
        reasons.extend(ceiling_reasons)

        detail = (
            f"Core above {round(astro.MIN_CORE_ALTITUDE_DEG)}deg in full darkness for "
            f"{window.duration_minutes} min. " + ", ".join(reasons) + "."
        )
        if window.is_brief and window.limited_by == "target":
            detail = (
                "Brief window: the core sets soon after darkness. " + detail
            )

        found.append(
            Opportunity(
                phenomenon="milky_way",
                key=f"milkyway-{zone['id']}-{window.start.date().isoformat()}",
                roll=f"milkyway-{window.start.date().isoformat()}",
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
                    "cloud_cover": round(cloud, 1) if cloud is not None else None,
                    # So the card can say which of these it is: a forecast, or
                    # an outlook that ranked the night without promising it.
                    "cloud_confidence": cloud_confidence(lead_days) if cloud is not None else None,
                    "cloud_is_forecast": bool(cloud is not None and forecast_cloud),
                    "moon_illumination": round(window.moon_illumination, 3),
                    "peak_altitude": round(window.peak_target_altitude, 1),
                    "score_ceiling": ceiling,
                    "verification": "computed",
                    "evidence_state": "computed",
                    "comparison_through": (now + timedelta(days=horizon_days)).date().isoformat(),
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

# The hard ceiling on anything a calendar alone is claiming. Below the default
# alert threshold by construction, so a date that nothing has confirmed can
# reach the planning view and never the notification.
UNVERIFIED_CEILING = 60
# A documented calendar cycle ranks above an unverified estimate in the
# planner but still below the alert score: since 0.16.0 the score only ranks
# planner rows, and the Can't Miss gate is ``eligibility.assess``.
CALENDAR_CEILING = 70
CALENDAR_PRESENCE_CEILING = 74
# What a live-confirmed window may reach once something has actually been seen.
CORROBORATED_SCORE = 82


def corroborating_sightings(window, sightings, now) -> list:
    """Recent, nearby sightings of the species this window is about.

    This is the difference between "the calendar says whales" and "four people
    saw whales off that point this week". Only the second is a reason to drive.
    """
    if not window.live_taxa or not sightings:
        return []
    wanted = {name.lower() for name in window.live_taxa}
    cutoff = now - timedelta(days=LIVE_CORROBORATION_DAYS)
    found = []
    for sighting in sightings:
        name = (getattr(sighting, "scientific_name", "") or "").lower()
        if not any(name.startswith(target.lower()) for target in wanted):
            continue
        if sighting.latest < cutoff:
            continue
        distance = haversine_km(window.latitude, window.longitude, sighting.latitude, sighting.longitude)
        if distance <= LIVE_CORROBORATION_KM:
            found.append(sighting)
    return found


def build_seasonal_opportunities(
    now: datetime,
    horizon_days: int,
    home: tuple[float, float] | None = None,
    sightings: list | None = None,
    field_reports: list | None = None,
) -> list[Opportunity]:
    """Natural phenomena, told at the precision the distance justifies.

    Beyond sixty days an entry reports its background season and scores as
    planning material - "gray whales, December to May" is the most honest thing
    anyone can say four months out, and dressing it up as an appointment would
    be a lie. Inside sixty days it switches to the concrete peak window and
    carries the locations, gear and behaviour notes.

    Reports and sightings are merged *into* the phenomenon they are evidence
    for, never listed beside it. Which ones merged is recorded in
    ``extra["merged_reports"]`` so the caller can keep only the unmatched ones
    as standalone planning rows.
    """
    from . import curation, gear as gear_module

    origin = home or DEFAULT_HOME
    found: list[Opportunity] = []

    for entry in active_windows(now, horizon_days):
        window = entry["window"]
        near = entry["precision"] == "peak"
        drive_hours = estimate_drive_hours(window.latitude, window.longitude, origin)
        evidence = window_evidence(window, sightings, field_reports, now)
        definition = curation.definition(window.key)

        if not near:
            score = SEASON_SCORE
            detail = (
                f"{window.name}. Background season: {window.season_range}. Peak window is "
                f"{entry['start']:%d %b} to {entry['end']:%d %b}; specifics firm up inside "
                f"{PRECISION_HORIZON_DAYS} days."
            )
            reasons = [f"season: {window.season_range}", "too far out for specifics"]
            # Even at season range, say what the dates would ultimately rest on.
            verification = {
                EVIDENCE_COMPUTED: "computed",
                EVIDENCE_LIVE: "watching",
                EVIDENCE_CALENDAR: "calendar",
            }.get(window.evidence, "unverified")
            awaiting = (
                f"Too far out to confirm. Specifics and live corroboration start "
                f"{PRECISION_HORIZON_DAYS} days before the window opens."
            )
            state = "season"
        else:
            score = PEAK_UNDERWAY_SCORE if entry["underway"] else PEAK_UPCOMING_SCORE
            if window.confirm:
                score -= UNCONFIRMED_PENALTY
            timing = "underway now" if entry["underway"] else f"opens in {entry['days_away']} days"
            detail = (
                f"Peak window {entry['start']:%d %b} to {entry['end']:%d %b} ({timing}). "
                f"{window.photo_tips}"
            )
            reasons = [
                timing,
                f"peak of a season that runs {window.season_range}",
                window.primary_locations[0],
            ]
            if window.best_time_of_day:
                reasons.append(window.best_time_of_day)
            if window.confirm:
                reasons.append("timing shifts year to year - confirm before driving")

            # The guard against booking a trip around a date nothing has
            # confirmed. A calendar entry may fill the planning view; only
            # evidence, or a narrowly granted documented cycle, may interrupt.
            score, verification, extra_reasons, awaiting = _score_from_evidence(window, score, evidence)
            reasons.extend(extra_reasons)
            state = evidence.state

        start_day = entry["start"]
        # A dated behaviour report ahead of the documented window means it is
        # already happening; the occurrence opens on the report, not the
        # calendar. Only a month early at most, so an off-season report cannot
        # drag next season's window into this one.
        # Not for a conditions phenomenon whose window is geometry: water on
        # Horsetail Fall in January does not move the February alignment.
        if near and evidence.state == "behavior_confirmed" and entry["start"] > now.date() \
                and not (definition and definition.policy == curation.POLICY_CONDITIONS):
            earliest = min(item.observed_at for item in evidence.behavior).date()
            if entry["start"] - earliest <= timedelta(days=30):
                start_day = min(start_day, max(earliest, now.date() - timedelta(days=1)))
                reasons.insert(0, "reported ahead of the documented window")
        plan = gear_module.recommend(definition.gear_profile, land=definition.land,
                                     wildlife=definition.wildlife, drone_useful=definition.drone_useful) \
            if definition else None
        found.append(
            Opportunity(
                key=entry["key"],
                title=window.name if near else f"{window.name} (season)",
                category=window.category,
                zone_id=window.key,
                zone_name=window.primary_locations[0],
                start=datetime.combine(start_day, datetime.min.time()).replace(tzinfo=now.tzinfo),
                end=datetime.combine(entry["end"], datetime.max.time()).replace(tzinfo=now.tzinfo),
                score=score,
                detail=detail,
                drive_hours=round(drive_hours, 2),
                reasons=reasons,
                gear={"glass": plan.take if plan else window.recommended_gear, "settings": window.photo_tips},
                latitude=window.latitude,
                longitude=window.longitude,
                drive_source="estimate",
                phenomenon=window.key,
                # A background season is never something to act on today, and
                # neither is an unconfirmed window.
                planning_only=not near or score <= UNVERIFIED_CEILING,
                extra={
                    "precision": entry["precision"],
                    "evidence": window.evidence,
                    "evidence_state": state,
                    "verification": verification,
                    "awaiting": awaiting,
                    "search_season": window.is_search_season,
                    "peak_days": window.peak_days,
                    "season_range": window.season_range,
                    "peak_start": entry["start"].isoformat(),
                    "peak_end": entry["end"].isoformat(),
                    "days_away": entry["days_away"],
                    "underway": entry["underway"],
                    "primary_locations": list(window.primary_locations),
                    "recommended_gear": plan.take + (f"; optional {plan.optional[0]}" if plan and plan.optional else "")
                    if plan else window.recommended_gear,
                    "photo_tips": window.photo_tips,
                    "best_time_of_day": window.best_time_of_day,
                    "confirm": window.confirm,
                    "lunar_dependent": window.lunar_dependent,
                    # Who actually counts these animals, so a date can be
                    # checked against the surveyors before a trip is booked.
                    "verify_urls": list(window.verify_urls),
                    "presence_count": sum(max(1, item.reports) for item in evidence.presence) if near else 0,
                    "behavior_evidence": [_report_summary(item) for item in evidence.behavior] if near else [],
                    "count": evidence.count if near else None,
                    "merged_reports": [report_id(item) for item in (evidence.behavior + evidence.undated + evidence.insufficient)] if near else [],
                    "latest_observed": evidence.latest.isoformat() if near and evidence.latest else None,
                },
            )
        )
    found.extend(live_occurrences(found, now, origin, sightings, field_reports))
    return found


def live_occurrences(built: list[Opportunity], now: datetime, origin, sightings, field_reports) -> list[Opportunity]:
    """Occurrences that live evidence opens outside the usual window.

    For behaviour-driven biology the seasonal dates are where to look, not a
    prohibition on reality (``PhenomenonDefinition.live_outside_window``). A
    fresh, positive, dated, located report of the behaviour near the site -
    the same requirements as inside the window (observations.admissible) -
    instantiates a bounded occurrence now: from the report to the end of the
    phenomenon's evidence window. Drive, conditions and safety are still
    applied by the gate. Never for calendar-, migration- or physics-bound
    phenomena, and never when an occurrence already covers today.
    """
    from . import curation
    from .phenomena import PEAK_WINDOWS

    result = []
    for window in PEAK_WINDOWS:
        definition = curation.definition(window.key)
        if definition is None or not definition.live_outside_window:
            continue
        if any(item.phenomenon == window.key and item.extra.get("precision") == "peak"
               and item.start <= now <= (item.end or item.start) for item in built):
            continue
        evidence = window_evidence(window, sightings, field_reports, now)
        if not evidence.behavior:
            continue
        newest = max(evidence.behavior, key=lambda item: item.observed_at)
        exact = getattr(newest, "latitude", None) is not None and getattr(newest, "longitude", None) is not None
        latitude, longitude = (newest.latitude, newest.longitude) if exact else (window.latitude, window.longitude)
        end = newest.observed_at + timedelta(days=min(LIVE_CORROBORATION_DAYS, definition.evidence_days))
        if end < now:
            continue
        key = f"{window.key}-live-{newest.observed_at.date().isoformat()}"
        count = f" ({evidence.count:,} counted)" if evidence.count else ""
        result.append(Opportunity(
            key=key, roll=key, title=window.name, category=window.category, zone_id=window.key,
            zone_name=(getattr(newest, "place", "") or "").title() or window.primary_locations[0],
            start=max(newest.observed_at, now - timedelta(hours=12)), end=end, score=CORROBORATED_SCORE,
            detail=f"Reported outside its usual season ({window.season_range}). {newest.snippet}",
            drive_hours=round(estimate_drive_hours(latitude, longitude, origin), 2),
            reasons=[f"confirmed by {newest.source_name}{count}", "outside the usual season - a dated report says it is happening"],
            latitude=latitude, longitude=longitude, drive_source="estimate", phenomenon=window.key,
            source_url=getattr(newest, "url", None) or None,
            extra={
                "precision": "peak", "evidence": window.evidence, "evidence_state": "behavior_confirmed",
                "verification": "corroborated", "live_occurrence": True,
                "observed_at": newest.observed_at.isoformat(),
                "behavior_evidence": [_report_summary(item) for item in evidence.behavior],
                "count": evidence.count, "season_range": window.season_range,
                "merged_reports": [report_id(item) for item in evidence.behavior],
                "location_precision": "reported place" if exact else "site",
                "awaiting": (f"Dated report from {newest.source_name}, observed {newest.observed_at:%d %b}, "
                             "outside the usual season; conditions may have changed since."),
            },
        ))
    return result


@dataclass
class WindowEvidence:
    """Everything the live feeds say about one curated window."""

    state: str
    presence: list = field(default_factory=list)
    behavior: list = field(default_factory=list)
    undated: list = field(default_factory=list)
    # Behaviour reported, but without the count this phenomenon needs.
    insufficient: list = field(default_factory=list)
    count: int | None = None
    latest: datetime | None = None


def report_id(report) -> str:
    """A stable identity for a report, so a merged one is not listed twice."""
    import hashlib

    text = f"{getattr(report, 'source_id', '')}|{getattr(report, 'zone_id', '')}|{getattr(report, 'snippet', '')}"
    return f"{getattr(report, 'source_id', 'report')}:{hashlib.sha1(text.encode()).hexdigest()[:12]}"


def _report_text(report) -> str:
    return " ".join(str(getattr(report, key, "") or "") for key in ("headline", "snippet", "context"))


def _report_summary(report) -> dict:
    observed = getattr(report, "observed_at", None)
    return {"source": getattr(report, "source_name", ""), "observed_at": observed.isoformat() if observed else None,
            "text": (getattr(report, "snippet", "") or "")[:220], "url": getattr(report, "url", "") or None,
            "count": getattr(report, "count", None)}


def _report_matches(window, report, definition) -> bool:
    """Whether a report's own statements describe this phenomenon (not whether it is fresh).

    Decided by the statement normalizer (observations.report_phenomena), so a
    behaviour word in one sentence and the species in another no longer
    combine into a confirmation.
    """
    from .observations import report_phenomena

    if definition is None:
        return False
    return window.key in report_phenomena(report)


def window_evidence(window, sightings, field_reports, now) -> WindowEvidence:
    """Classify the evidence for one window. Pure; no scoring here."""
    from . import curation

    definition = curation.definition(window.key)
    days = min(LIVE_CORROBORATION_DAYS, definition.evidence_days) if definition else LIVE_CORROBORATION_DAYS
    stale_before = now - timedelta(days=days)
    presence = corroborating_sightings(window, sightings, now)
    behavior, undated, insufficient = [], [], []
    from .observations import admissible

    for report in field_reports or []:
        if getattr(report, "polarity", "positive") != "positive" or not _report_matches(window, report, definition):
            continue
        # Corroboration is distance-based; an unlocatable report is nowhere.
        if haversine_km(window.latitude, window.longitude, *_report_point(report, window)) > LIVE_CORROBORATION_KM:
            continue
        observed = getattr(report, "observed_at", None)
        if observed is None:
            undated.append(report)
            continue
        # Download time never renews an observation; the report's own date does.
        if not stale_before <= observed <= now + timedelta(hours=1):
            continue
        # The same requirements every ingress path meets (observations.admissible).
        ok, why = admissible(report, definition, now)
        if not ok:
            if why == "count below the phenomenon's threshold":
                insufficient.append(report)
            continue
        behavior.append(report)
    counts = [getattr(item, "count", None) for item in behavior + insufficient if getattr(item, "count", None)]
    stamps = [item.latest for item in presence] + [item.observed_at for item in behavior]
    latest = max(stamps) if stamps else None

    if window.evidence == EVIDENCE_COMPUTED:
        state = "computed"
    elif behavior:
        state = "behavior_confirmed"
    elif window.evidence == EVIDENCE_CALENDAR:
        state = "calendar_presence" if presence else "calendar"
    elif window.evidence == EVIDENCE_STATIC:
        state = "unverified"
    elif presence:
        state = "presence_only"
    elif undated or insufficient:
        state = "reported_undated"
    else:
        state = "watching"
    return WindowEvidence(state, presence, behavior, undated, insufficient, max(counts) if counts else None, latest)


def _score_from_evidence(window, score, evidence: WindowEvidence):
    """Hold a score down to what the evidence actually supports.

    Four bases, four ceilings:

    - **Computed.** Geometry, verifiable to the minute. Scores on its merits.
    - **Calendar-reliable.** A documented annual cycle (elephant seals,
      Carpinteria harbor seals, the Merced crane fly-in, the tule elk rut). The
      planner ranks it above estimates; the Can't Miss gate may act on it only
      inside the documented core window.
    - **Live.** The dates are a search season. Presence releases a window
      whose phenomenon *is* presence; a window about a behaviour needs a dated
      report of that behaviour. The text names what was seen, when and where.
    - **Static.** A calendar estimate with nothing behind it. Only a dated,
      located report of the behaviour itself can activate it.

    Alongside the ceiling each case returns ``awaiting``: the specific thing
    that would turn this window from an estimate into a fact.
    """
    if window.evidence == EVIDENCE_COMPUTED:
        return score, "computed", [], "Calculated timing; local visibility and conditions still matter."

    if evidence.behavior:
        newest = max(evidence.behavior, key=lambda item: item.observed_at)
        count = f" ({evidence.count:,} counted)" if evidence.count else ""
        return (
            max(score, CORROBORATED_SCORE),
            "corroborated",
            [f"confirmed by {newest.source_name}{count}"],
            f"Dated report from {newest.source_name}, observed {newest.observed_at:%d %b}; "
            "conditions may have changed since, and future presence is not guaranteed.",
        )

    if window.evidence == EVIDENCE_CALENDAR:
        if evidence.state == "calendar_presence":
            nearest = evidence.presence[0]
            return (min(score, CALENDAR_PRESENCE_CEILING), "calendar",
                    [f"documented annual cycle; {nearest.species} reported {nearest.latest:%d %b}"],
                    "Documented annual cycle and a recent report near the site. Conditions and access on the day still matter.")
        return (min(score, CALENDAR_CEILING), "calendar",
                ["documented annual cycle - " + (window.verify_urls[0] if window.verify_urls else "see sources")],
                "Documented annual cycle from the site's managers or monitors; conditions and access on the day still matter.")

    if window.evidence == EVIDENCE_STATIC:
        return (
            min(score, UNVERIFIED_CEILING),
            "unverified",
            ["calendar estimate - no live source confirms this one"],
            "No feed reports this one. A dated report of the behaviour itself is the only thing that can confirm it; species presence cannot.",
        )

    matches = evidence.presence
    if matches and window.requires_behavior:
        return (min(score, UNVERIFIED_CEILING), "presence_only",
                ["species reported; the named behavior or aggregation is not confirmed"],
                "A dated report of this behavior or aggregation at this location. Species presence alone is not enough.")

    if matches:
        freshest = max(item.latest for item in matches)
        observers = sum(max(1, item.reports) for item in matches)
        nearest = min(
            haversine_km(window.latitude, window.longitude, item.latitude, item.longitude)
            for item in matches
        )
        return (
            max(score, CORROBORATED_SCORE),
            "corroborated",
            [
                f"confirmed: {observers} report{'s' if observers != 1 else ''} within "
                f"{round(LIVE_CORROBORATION_KM)} km, most recent {freshest:%d %b}",
            ],
            f"Species presence reported. Nearest report {round(nearest)} km away, "
            f"latest {freshest:%d %b}.",
        )

    if evidence.undated or evidence.insufficient:
        source = (evidence.undated or evidence.insufficient)[0].source_name
        why = ("the page does not date it" if evidence.undated else
               "it does not give the count this phenomenon needs")
        return (min(score, UNVERIFIED_CEILING), "watching",
                [f"reported by {source}, but {why}"],
                f"{source} mentions it, but {why}. A dated report is needed before this can be acted on.")

    taxa = ", ".join(window.live_taxa) if window.live_taxa else "the species"
    return (
        min(score, UNVERIFIED_CEILING),
        "watching",
        ["watch window - nothing reported yet, so this is where to look, not when to go"],
        f"A sighting of {taxa} within {round(LIVE_CORROBORATION_KM)} km in the last "
        f"{LIVE_CORROBORATION_DAYS} days. None yet." if window.live_taxa else
        "A dated report from the listed sources. None yet.",
    )


def _apply_evidence(window, entry, score, sightings, field_reports, now):
    """The planner-facing verdict for one window: (score, verification, reasons, awaiting)."""
    return _score_from_evidence(window, score, window_evidence(window, sightings, field_reports, now))


# Far enough that no corroboration test can pass. Used for a report whose
# location could not be resolved: defaulting such a report to the window's own
# coordinates made its distance zero, so it corroborated every window in the
# table at once - which is the opposite of what a location-scoped check is for.
_NOWHERE = (0.0, 0.0)


def _report_point(report, window) -> tuple[float, float]:
    """Where a field report actually is, or nowhere at all."""
    if getattr(report, "latitude", None) is not None and getattr(report, "longitude", None) is not None:
        return report.latitude, report.longitude
    zone = ZONES_BY_ID.get(getattr(report, "zone_id", ""))
    if zone:
        return zone["latitude"], zone["longitude"]
    return _NOWHERE


def planning_slice(opportunities: list[Opportunity], limit: int) -> list[Opportunity]:
    """Reserve a row for each occurrence before spending space on extra sites.

    A longer astronomy comparison must not fill the payload with near-term
    viewpoints and silently evict next February's firefall or spring moonbows.
    When the limit is reached, retain the strongest site for each occurrence
    first, then distribute additional sites evenly. The sensor marks truncation.
    """
    if len(opportunities) <= limit:
        return opportunities
    groups: dict[str, list[Opportunity]] = {}
    for item in opportunities:
        groups.setdefault(item.roll or item.key, []).append(item)
    for group in groups.values():
        group.sort(key=lambda item: (-item.score, item.drive_hours))
    selected: list[Opportunity] = []
    depth = 0
    while len(selected) < limit:
        layer = [group[depth] for group in groups.values() if len(group) > depth]
        if not layer:
            break
        selected.extend(layer[:limit-len(selected)])
        depth += 1
    return sorted(selected, key=lambda item: item.start)


def within_drive(
    opportunities: list[Opportunity],
    max_hours: float,
    category_limits: dict[str, float] | None = None,
) -> list[Opportunity]:
    """Drop what is too far to drive to, keeping the trips you plan instead.

    The drive limit answers "could I be there tonight", which is the wrong
    question for a national park eight hours away - you go there for a long
    weekend, and gating it out would defeat the point of listing it.

    Some categories want a tighter answer than the global one. A sunset is
    decided on the afternoon's forecast and is worth a short drive at most;
    offering one six hours away is how the whole category becomes noise. A
    per-category cap only ever tightens - it can never let something through
    that the global limit excluded.
    """
    limits = category_limits or {}
    kept = []
    for item in opportunities:
        if item.planning_only:
            kept.append(item)
            continue
        cap = min(max_hours, limits.get(item.category, max_hours))
        if item.drive_hours <= cap:
            kept.append(item)
    return kept


def action_window(opportunities: list[Opportunity], now: datetime, hours: int = 48) -> list[Opportunity]:
    """Opportunities starting inside the drop-everything window.

    Assessed rows that passed the Can't Miss gate lead, by priority; a
    planning row enters only if the gate admitted it. Unassessed rows keep
    the old score order so callers without the gate behave as before.
    """
    cutoff = now + timedelta(hours=hours)

    def admitted(item):
        eligible = (item.extra.get("assessment") or {}).get("eligible")
        return (eligible or not item.planning_only) and item.start <= cutoff \
            and (item.end or item.start + timedelta(hours=2)) > now

    def rank(item):
        assessment = item.extra.get("assessment") or {}
        return (0 if assessment.get("eligible") else 1, -(assessment.get("priority") or item.score), item.start)

    return sorted((item for item in opportunities if admitted(item)), key=rank)


def alert_candidate(item: Opportunity, alert_score: int) -> bool:
    """Whether one opportunity has earned the drop-everything sensor.

    Once the eligibility gate has run (``extra["assessment"]``), its verdict is
    the answer: significance, a satisfied trigger policy, the six-hour drive
    and safety - not a score. The score path below remains only for rows that
    were never assessed, so an older caller cannot fire on a planning row.

    Clearing the score bar is necessary and, for a sky, not sufficient. A good
    sunset happens most weeks; being told about every one of them is how a
    notification gets muted. So a sky must also be a standout and its light
    path must have been modelled rather than guessed at from the deck overhead.
    """
    assessment = item.extra.get("assessment")
    if assessment is not None:
        return bool(assessment.get("eligible"))
    if item.planning_only or item.score < alert_score:
        return False
    if item.category == CATEGORY_SUNSET:
        return bool(item.extra.get("standout")) and item.extra.get("light_path") == "modelled"
    return True


def zones_for_category(category: str) -> list[dict]:
    return [zone for zone in TARGET_ZONES if category in zone["specialties"]]


# --- Live sightings ---------------------------------------------------------

# Marine draw ranking, used by the orca/blue exceptional-presence rule and to
# order background signals. Humpbacks are abundant off this coast in season, so
# a report of one is not news; blue whales and orcas are.
MARINE_DRAW = {
    "Orcinus orca": 10,
    "Balaenoptera musculus": 10,
    "Balaenoptera physalus": 6,
    "Megaptera novaeangliae": 0,
}


# Birds that tend to make a striking photograph. Since 0.16.0 this is only a
# ranking hint inside the optional Bird Chase view; it is not a Can't Miss gate.
# Whether a bird is worth a drive is an encounter question (repeat reports at a
# public place, counts, behaviour), answered in ``birds.py``.
PHOTOGRAPHY_BIRDS = frozenset({
    "vermilion flycatcher", "bald eagle", "golden eagle", "california condor", "peregrine falcon",
    "snowy owl", "great gray owl", "great horned owl", "short-eared owl", "burrowing owl",
    "tufted puffin", "horned puffin", "harlequin duck", "wood duck", "mandarin duck",
    "painted bunting", "scarlet tanager", "summer tanager", "blackburnian warbler",
    "roseate spoonbill", "sandhill crane", "american white pelican", "long-tailed duck", "king eider",
})


def build_field_report_opportunities(reports: list, now: datetime) -> list[Opportunity]:
    """Bloom and colour reports that match no curated phenomenon.

    A report that *does* match one (Carrizo carpets, Bishop Creek "go now") is
    merged into that phenomenon by ``build_seasonal_opportunities`` and must not
    be passed here, or the same bloom appears twice. What arrives here is the
    rest: leads for the planner, capped below the alert threshold, never Can't
    Miss on their own.
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
                planning_only=True,
                phenomenon="hotline_report",
                extra={"verification": "watching", "observed_at": report.observed_at.isoformat() if report.observed_at else None,
                       "evidence_note": "Observation time unknown" if not report.observed_at else "Dated field report"},
                gear=_gear_for(report.category),
                source_url=report.url,
                latitude=zone["latitude"],
                longitude=zone["longitude"],
            )
        )
    return found


def _closure_source(park_key: str, park_alerts) -> str:
    """Whether closures were actually checked, and by what."""
    from .verification import closure_coverage

    agency = closure_coverage(park_key)
    if agency:
        return f"not checked - {agency} unit, outside the NPS alerts feed"
    if not park_alerts:
        return "not checked - no National Park Service key configured"
    return "National Park Service alerts"


def _closures_for(park_key: str, park_alerts) -> list:
    """Blocking alerts published by the park itself, if any were fetched."""
    if not park_alerts:
        return []
    from .verification import NPS_PARK_CODES, alerts_for

    code = NPS_PARK_CODES.get(park_key)
    return alerts_for(park_alerts, code) if code else []


def _slug(text: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in text)
    return "-".join(part for part in cleaned.split("-") if part)[:60]


# --- Parks ------------------------------------------------------------------

PARK_OPTIMAL_SCORE = 55
PARK_GOOD_SCORE = 40


def build_park_opportunities(
    now: datetime,
    horizon_days: int,
    park_alerts: list | None = None,
) -> list[Opportunity]:
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

        # A closure is the one thing a calendar can never infer and that ends a
        # trip outright: right window, animals present, road shut.
        closures = _closures_for(park.key, park_alerts)
        if closures:
            score = min(score, 35)
            reasons.insert(0, f"CLOSURE: {closures[0].title}")

        found.append(
            Opportunity(
                key=window["key"],
                phenomenon="park_season",
                title=f"{park.name} - {tier_text.lower()}",
                category=CATEGORY_PARKS,
                zone_id=park.key,
                zone_name=park.name,
                start=datetime.combine(window["start"], datetime.min.time()).replace(tzinfo=now.tzinfo),
                end=datetime.combine(window["end"], datetime.max.time()).replace(tzinfo=now.tzinfo),
                score=score,
                detail=(
                    (f"CLOSURE REPORTED: {closures[0].title}. " if closures else "")
                    + f"{tier_text} to visit {park.name} ({park.drive_label}). Dogs: {park.dog_detail}"
                ),
                drive_hours=park.drive_hours,
                reasons=reasons,
                gear=_gear_for(CATEGORY_PARKS),
                latitude=park.latitude,
                longitude=park.longitude,
                planning_only=True,
                extra={
                    "tier": window["tier"],
                    "closures": [alert.title for alert in closures],
                    # Says "nothing can check this" rather than implying "all clear".
                    "closure_source": _closure_source(park.key, park_alerts),
                    "closure_urls": [alert.url for alert in closures if alert.url],
                    "miles": park.miles,
                    "dogs": park.dogs,
                    "dog_label": park.dog_label,
                    "dog_detail": park.dog_detail,
                },
            )
        )
    return found


# --- Grunion runs -----------------------------------------------------------

# Runs follow the full and new moons, for a few nights each.
GRUNION_RUN_NIGHTS = 4
GRUNION_LAG_NIGHTS = 1
GRUNION_SEASON = ((3, 1), (8, 31))


def build_grunion_runs(
    now: datetime,
    horizon_days: int,
    home: tuple[float, float] | None = None,
    tides: list | None = None,
) -> list[Opportunity]:
    """The actual run nights, computed rather than assumed.

    A grunion run is not a season - it is a handful of nights a month, on the
    nights following a full or new moon, for about an hour. Storing it as
    "1 April to 15 June" describes seventy-five nights of which perhaps sixteen
    are right, which is the difference between a plan and a wasted drive.

    The nights come from lunar geometry and are exact. The *hour* comes from the
    tide, which needs a tide table - until one is wired in, each night says so
    rather than guessing a time.
    """
    origin = home or DEFAULT_HOME
    window = WINDOWS_BY_KEY.get("grunion_run")
    if window is None:
        return []

    horizon = now + timedelta(days=horizon_days)
    found: list[Opportunity] = []

    anchors = [("new moon", moment) for moment in astro.new_moons_between(now - timedelta(days=2), horizon)]
    anchors += [("full moon", moment) for moment in astro.full_moons_between(now - timedelta(days=2), horizon)]
    anchors.sort(key=lambda pair: pair[1])

    for phase_name, moment in anchors:
        first_night = (moment + timedelta(days=GRUNION_LAG_NIGHTS)).date()
        last_night = first_night + timedelta(days=GRUNION_RUN_NIGHTS - 1)
        if last_night < now.date() or first_night > horizon.date():
            continue
        if not _in_grunion_season(first_night):
            continue

        start = datetime.combine(first_night, datetime.min.time()).replace(tzinfo=now.tzinfo)
        end = datetime.combine(last_night, datetime.max.time()).replace(tzinfo=now.tzinfo)

        # The nights come from lunar geometry; the hour comes from the tide.
        # With a tide table the window is a real time to stand on the sand;
        # without one it stays a night, and says so.
        tide_window = grunion_run_window(tides, first_night, (window.latitude, window.longitude)) if tides else None
        hour_note = (
            f"first night's window {tide_window[0]:%H:%M}-{tide_window[1]:%H:%M} "
            f"(1-2 h after the {tide_window[0].strftime('%H:%M')} high tide)"
            if tide_window
            else "exact hour depends on the tide - check a local tide table"
        )
        found.append(
            Opportunity(
                key=f"grunion-{first_night.isoformat()}",
                title="Grunion run nights",
                phenomenon="grunion_run",
                category=window.category,
                zone_id="grunion_run",
                zone_name=window.primary_locations[0],
                start=start,
                end=end,
                score=55,
                planning_only=True,
                detail=(
                    f"Runs expected on the {GRUNION_RUN_NIGHTS} nights following the "
                    f"{phase_name} of {moment.strftime('%d %b')}, starting one to two hours "
                    f"after high tide and lasting under an hour. {window.photo_tips}"
                ),
                drive_hours=round(estimate_drive_hours(window.latitude, window.longitude, origin), 2),
                reasons=[
                    f"{GRUNION_RUN_NIGHTS} nights after the {phase_name}",
                    hour_note,
                    window.primary_locations[0],
                ],
                gear={"glass": window.recommended_gear, "settings": window.photo_tips},
                latitude=window.latitude,
                longitude=window.longitude,
                drive_source="estimate",
                extra={
                    "precision": "peak",
                    "evidence": EVIDENCE_STATIC,
                    "verification": "unverified",
                    "awaiting": (
                        "Lunar heuristic only. Use the published CDFW schedule for expected nights and hours."
                    ),
                    "lunar_phase": phase_name,
                    "primary_locations": list(window.primary_locations),
                    "recommended_gear": window.recommended_gear,
                    "photo_tips": window.photo_tips,
                    "best_time_of_day": window.best_time_of_day,
                    "needs_tide_table": tide_window is None,
                    "tide_window_start": tide_window[0].isoformat() if tide_window else None,
                    "tide_window_end": tide_window[1].isoformat() if tide_window else None,
                },
            )
        )
    return found


def _in_grunion_season(day) -> bool:
    (first_month, first_day), (last_month, last_day) = GRUNION_SEASON
    return (first_month, first_day) <= (day.month, day.day) <= (last_month, last_day)
