"""Check whether published near-peak radiant drift changes a night's verdict.

IMO 2026 Calendar Table 6 (p26), DOI 10.13140/RG.2.2.36179.08480.
The author's copy is available while imo.net is temporarily offline:
https://www.researchgate.net/publication/393092133_2026_IMO_Meteor_Shower_Calendar
Rates below are differences between adjacent five-day positions bracketing each
maximum, in degrees per day. This is a sensitivity check, not a new ephemeris.
"""
from datetime import timedelta, timezone
from functools import lru_cache
import importlib
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType("photography_events")
package.__path__ = [str(ROOT / "custom_components/photography_events")]
sys.modules.setdefault("photography_events", package)
astro = importlib.import_module("photography_events.astronomy")
events = importlib.import_module("photography_events.events")
const = importlib.import_module("photography_events.const")

RATES = {
    "Quadrantids": (0.6, -0.2),  # Jan 0 228,+50 to Jan 5 231,+49
    "Lyrids": (1, 0),           # Apr 20 269,+34 to Apr 25 274,+34
    "Eta Aquariids": (0.8, 0.4), # May 5 337,-1 to May 10 341,+1
    "Perseids": (1.2, 0.2),     # Aug 10 45,+57 to Aug 15 51,+58
    "Orionids": (0.8, 0),       # Oct 20 94,+16 to Oct 25 98,+16
    "Leonids": (0.6, -0.4),     # Nov 15 150,+23 to Nov 20 153,+21
    "Geminids": (1, 0),         # Dec 10 108,+33 to Dec 15 113,+33
    "Ursids": (0, -0.4),        # Dec 20 217,+76 to Dec 25 217,+74
}


def main():
    assert RATES == events.RADIANT_DRIFT, "Audit and production drift coefficients differ"
    # Repeated target comparisons share Sun/Moon positions. Cache only in this
    # offline audit, not in HA's long-running process.
    astro.sun_equatorial = lru_cache(maxsize=200000)(astro.sun_equatorial)
    astro.moon_equatorial = lru_cache(maxsize=200000)(astro.moon_equatorial)
    verdict_changes, preferred_changes = [], []
    max_shift = 0
    comparisons = 0
    zones = [z for z in const.TARGET_ZONES if z["drive_hours"] <= 6]
    for year in range(2026, 2036):
        for shower in events.METEOR_SHOWERS:
            ra_rate, dec_rate = RATES[shower["name"]]
            peak = astro.solar_longitude_crossing(year, shower["lambda_sun"], tz=timezone.utc)
            for zone in zones:
                lat, lon = events._zone_coords(zone)
                pairs = []
                for offset in (-1, 0):
                    night = (peak + timedelta(days=offset)).replace(hour=12, minute=0, second=0, microsecond=0)
                    windows = []
                    for moving in (False, True):
                        windows.append(astro.astro_shooting_window(night, lat, lon,
                            ra_deg=shower["ra_deg"], dec_deg=shower["dec_deg"],
                            min_target_altitude=events.MIN_RADIANT_ALTITUDE,
                            max_moon_illumination=events.MAX_MOON_ILLUMINATION,
                            radiant_drift=(ra_rate, dec_rate), radiant_epoch=peak if moving else None))
                    comparisons += 1
                    a, b = windows
                    if (a is None) != (b is None):
                        verdict_changes.append([year, shower["name"], zone["id"], offset])
                    if a and b:
                        max_shift = max(max_shift, abs((a.start - b.start).total_seconds()) / 60,
                                        abs((a.end - b.end).total_seconds()) / 60)
                    pairs.append(windows)
                best = []
                for model in (0, 1):
                    candidates = [(abs(((w.start + (w.end - w.start) / 2) - peak).total_seconds()), index)
                                  for index, pair in enumerate(pairs) if (w := pair[model]) is not None]
                    best.append(min(candidates)[1] if candidates else None)
                if best[0] != best[1]:
                    preferred_changes.append([year, shower["name"], zone["id"], *best])
        print(f"Checked {year}", file=sys.stderr, flush=True)
    print(json.dumps({"years": [2026, 2035], "zones": len(zones), "showers": len(RATES),
                      "candidate_nights": comparisons, "verdict_changes": verdict_changes,
                      "preferred_night_changes": preferred_changes, "max_boundary_shift_minutes": round(max_shift, 2)}, indent=2))


if __name__ == "__main__":
    main()
