"""Measured exceptional swell, with coastal forecasts kept distinct from breakers."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
NDBC_URL = "https://www.ndbc.noaa.gov/data/realtime2/{station}.txt"
CDIP_ROOT = "https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/model/MOP_alongshore/"
CDIP_FIELDS = "waveTime,waveHs,waveTp,waveDp,waveFlagPrimary,metaLatitude,metaLongitude"


def recent_forecast_metadata(raw, now):
    """A newly downloaded old model run is still an old model run."""
    match = re.search(r'date_created\s+"([^"]+)"', raw or "")
    if not match:
        return False
    try:
        issued = datetime.fromisoformat(match[1].replace("Z", "+00:00"))
        if issued.tzinfo is None:
            issued = issued.replace(tzinfo=UTC)
        return -timedelta(minutes=10) <= now - issued <= timedelta(hours=24)
    except ValueError:
        return False


@dataclass(frozen=True)
class Wave:
    time: datetime
    height: float
    period: float
    direction: float


def parse_ndbc(text):
    """NDBC real-time MM and historical 99/999 sentinels are not huge storms."""
    header = None
    found = {}
    for line in text.splitlines():
        parts = line.split()
        if line.startswith("#YY"):
            header = [value.lstrip("#") for value in parts]
            continue
        if not header or line.startswith("#") or len(parts) < len(header):
            continue
        row = dict(zip(header, parts))
        try:
            year = int(row["YY"])
            if year < 100:
                year += 2000 if year < 70 else 1900
            moment = datetime(year, int(row["MM"]), int(row["DD"]), int(row["hh"]), int(row.get("mm", 0)), tzinfo=UTC)
            height, period, direction = (float(row[key]) for key in ("WVHT", "DPD", "MWD"))
            if not all(math.isfinite(x) for x in (height, period, direction)):
                continue
            if not (0 < height < 35 and 0 < period <= 40 and 0 <= direction <= 360):
                continue
        except (KeyError, ValueError, OverflowError):
            continue
        found[moment] = Wave(moment, height, period, direction)
    return sorted(found.values(), key=lambda row: row.time)


def parse_cdip(text, expected=None):
    """Read the server's ASCII projection; no netCDF/numpy dependency needed."""
    body = text.split("---------------------------------------------")[-1]
    def array(name):
        match = re.search(r"(?m)^" + name + r"\[\d+\]\s*\n([^\n]+)", body)
        if not match:
            return []
        try:
            return [float(x.strip()) for x in match[1].split(",")]
        except ValueError:
            return []
    def scalar(name):
        match = re.search(r"(?m)^" + name + r",\s*([-\d.]+)", body)
        return float(match[1]) if match else None
    latitude, longitude = scalar("metaLatitude"), scalar("metaLongitude")
    if expected and (latitude is None or longitude is None or
                     abs(latitude - expected[0]) > .02 or abs(longitude - expected[1]) > .02):
        return []
    values = [array(name) for name in ("waveTime", "waveHs", "waveTp", "waveDp", "waveFlagPrimary")]
    if not values[0] or len({len(v) for v in values}) != 1:
        return []
    result = []
    for stamp, height, period, direction, flag in zip(*values):
        if flag != 1 or not all(math.isfinite(x) for x in (stamp, height, period, direction)):
            continue
        if not (0 < height < 35 and 0 < period <= 40 and 0 <= direction <= 360):
            continue
        try:
            result.append(Wave(datetime.fromtimestamp(stamp, UTC), height, period, direction))
        except (ValueError, OSError, OverflowError):
            continue
    return sorted(result, key=lambda row: row.time)


def qualifies(wave, threshold, min_period=14, direction=(240, 330)):
    return wave.height >= threshold and wave.period >= min_period and direction[0] <= wave.direction <= direction[1]


def episodes(rows, threshold, min_period=14, direction=(240, 330)):
    """Count distinct episodes, not exceedance readings, for calibration."""
    result = []
    for row in rows:
        if not qualifies(row, threshold, min_period, direction):
            continue
        if not result or row.time - result[-1][-1].time > timedelta(hours=48):
            result.append([])
        result[-1].append(row)
    return result


def build_opportunities(now, observations, forecasts, calibration, state, home, alerts=None):
    from .events import Opportunity
    from .wildlife import estimate_drive_hours

    result = []
    # Model metadata fetched and checked in SOURCE_VALIDATION.md. Offshore and
    # nearshore heights remain separately labelled throughout the payload.
    sites = (
        ("B1500", "Vandenberg coast — Surf / Ocean Beach area", 34.75812, -120.64311),
    )
    for station, config in calibration.items():
        if station != "46011":
            continue
        threshold = config["threshold_m"]
        rows = [r for r in observations.get(station, []) if r.time <= now + timedelta(minutes=10)]
        recent = [r for r in rows if now - r.time <= timedelta(hours=3)]
        latest = recent[-1] if recent else None
        measured = latest is not None and qualifies(latest, threshold)
        coastal_threshold = calibration.get("B1500", {}).get("threshold_m")
        coastal = [r for r in forecasts.get("B1500", []) if now - timedelta(hours=3) <= r.time <= now + timedelta(days=4)]
        groups = episodes(coastal, coastal_threshold) if coastal_threshold else []
        # Two separate incoming storms must not become a single long window.
        predicted = next((group for group in groups if group[-1].time >= now), [])
        if measured and predicted and predicted[0].time - latest.time > timedelta(hours=48):
            predicted = []  # An unrelated future storm cannot confirm this one.
        if not measured and not predicted:
            continue
        if measured:
            episode = episodes([r for r in rows if now - r.time <= timedelta(days=10)], threshold)[-1]
            first = episode[0].time
        else:
            first = predicted[0].time
        saved = state.episodes.get(station)
        if saved:
            old_last = datetime.fromisoformat(saved["last"])
            if first - old_last <= timedelta(hours=48):
                first = datetime.fromisoformat(saved["start"])
        last = predicted[-1].time if predicted else latest.time
        state.episodes[station] = {"start": first.isoformat(), "last": last.isoformat()}
        occurrence = f"swell-{station}-{first.date().isoformat()}"
        for point, name, lat, lon in sites:
            if station != "46011":
                continue
            future = [r for r in predicted if now <= r.time]
            peak = max(future, key=lambda r: r.height) if future else None
            forecast_note = (f"CDIP experimental nearshore significant wave height peaks at {peak.height:.1f} m "
                             f"at {peak.time.isoformat()}; not breaker height."
                             if peak else "No fresh qualifying coastal forecast for this episode. Peak time and local surf height unknown.")
            display = latest if measured else max(predicted, key=lambda r: r.height)
            supported = bool(predicted)
            result.append(Opportunity(
                key=occurrence + "-" + point, roll=occurrence,
                title="Exceptional Pacific swell", category="waves", zone_id=point, zone_name=name,
                start=first, end=last + timedelta(hours=3), score=92 if measured and supported else 85 if supported else 60,
                planning_only=not supported,
                detail=(f"NDBC {station} measured" if measured else "CDIP forecasts") +
                       f" {display.height:.1f} m significant wave height, "
                       f"{display.period:.0f} s period, from {display.direction:.0f}°. " +
                       (f"Offshore threshold {threshold:.1f} m." if measured else f"Coastal model threshold {coastal_threshold:.1f} m."),
                drive_hours=round(estimate_drive_hours(lat, lon, home), 1),
                latitude=lat, longitude=lon, drive_source="estimate",
                gear={"glass": "70–200mm or 100–400mm from an open elevated viewpoint",
                      "support": "Weather protection and a stable tripod",
                      "settings": "Fast shutter for spray; keep a long working distance"},
                source_url=(f"https://www.ndbc.noaa.gov/station_page.php?station={station}"
                            if measured else "https://cdip.ucsd.edu/?nav=recent&sub=forecast"),
                extra={"verification": "corroborated" if measured else "forecast", "special": True,
                       "observed_at": latest.time.isoformat() if measured else None,
                       "wave_height_m": round(display.height, 2),
                       "wave_period_s": display.period, "wave_direction_deg": display.direction,
                       "measurement_label": "Measured offshore significant wave height" if measured else "Forecast nearshore significant wave height",
                       "evidence_note": "Buoy confirms offshore swell; coastal height remains a model estimate." if measured else "Experimental coastal forecast; swell not yet confirmed by buoy.",
                       "forecast_note": forecast_note,
                       "confidence_note": "No claim about a particular breaker or splash height. Local wind seas and shoreline exposure vary.",
                       "access_note": "Check current Ocean Beach access and NWS surf warnings. This point is a coastal model location, not an approved or safe shooting position.",
                       "verify_urls": ["https://cdip.ucsd.edu/", "https://www.weather.gov/lox",
                                       "https://www.countyofsb.org/parks"],
                       "coastal_advisories": [a.get("headline", "") for a in (alerts or []) if a.get("headline")],
                       "best_time_of_day": "Daylight; exact local peak timing depends on the coastal forecast."},
            ))
    return result
