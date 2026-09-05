#!/usr/bin/env python3
"""Regenerate TRACKING.md from the code, so the two can never disagree.

The list of what this integration watches is the thing you check before
trusting it, and a hand-written list rots the first time a window moves. So it
is generated: every date, evidence level and source URL below is read out of
the modules that actually run.

    python3 tools/generate_tracking_inventory.py > TRACKING.md
"""

from __future__ import annotations

import importlib.util
import math
import sys
import types
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "custom_components" / "photography_events"
MODULES = ("const", "parks", "astronomy", "weather_scoring", "phenomena", "wildlife",
           "field_reports", "routing", "verification", "throttle", "events")


def load():
    package = types.ModuleType("photography_events")
    package.__path__ = [str(ROOT)]
    sys.modules["photography_events"] = package
    for name in MODULES:
        spec = importlib.util.spec_from_file_location(f"photography_events.{name}", ROOT / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        setattr(package, name, module)
        spec.loader.exec_module(module)
    return package


pkg = load()
const, phenomena, events, astronomy = pkg.const, pkg.phenomena, pkg.events, pkg.astronomy
parks, verification, weather_scoring = pkg.parks, pkg.verification, pkg.weather_scoring

YEARS = (2026, 2027)
EVIDENCE_LABEL = {
    phenomena.EVIDENCE_COMPUTED: "computed",
    phenomena.EVIDENCE_LIVE: "live",
    phenomena.EVIDENCE_STATIC: "static",
}
out = print


def month_day(pair):
    return date(2001, *pair).strftime("%-d %b")


out("# What this integration actually tracks")
out()
out("_Generated from the code by `tools/generate_tracking_inventory.py`. Every date,")
out("evidence level and link below is read out of the modules that run, so this file")
out("cannot drift from the thing it describes._")
out()
out(f"Generated {datetime.now(timezone.utc):%Y-%m-%d}.")
out()
out("## How to read this")
out()
out("Everything tracked carries an **evidence level**, and that decides what it is")
out("allowed to do. This is the whole design: a date being on a calendar is not a")
out("reason to drive anywhere.")
out()
out("| Evidence | What the dates rest on | May it raise an alert? |")
out("| --- | --- | --- |")
out("| **computed** | Orbital geometry. Verifiable to the minute against any ephemeris. | Yes, on its own. |")
out("| **live** | A *search season* - when to start watching. The dates alone are an estimate. | Only once a live sighting corroborates it. |")
out("| **static** | A calendar estimate. No feed anywhere publishes this. | **Never**, at any score. |")
out()
out(f"Corroboration means a reported sighting of the named species within "
    f"**{round(phenomena.LIVE_CORROBORATION_KM)} km** in the last "
    f"**{phenomena.LIVE_CORROBORATION_DAYS} days**. Without one, a live window is capped at "
    f"{events.UNVERIFIED_CEILING} and marked planning-only.")
out()
out(f"Inside **{phenomena.PRECISION_HORIZON_DAYS} days** every window switches from its background season to concrete")
out("dates, locations, gear, and a plain statement of what has and has not been confirmed.")
out("Beyond it you get the broad season, because that is genuinely all anyone can say.")
out()

out("## 1. Computed from geometry")
out()
out("Nothing here needs a network. It is solved from the ephemeris in `astronomy.py`,")
out("which is Meeus chapters 25 (solar) and 47 (lunar, 60 periodic terms).")
out()
out("### Meteor showers")
out()
out("Stored as **solar longitude**, not as a date. A stream sits at a fixed point in the")
out("Earth's orbit; the calendar date it falls on slides by up to a day with the leap")
out("cycle. Longitudes are the IMO Working List values, which the IMO publishes for the")
out("equinox J2000.0, so the code precesses them to the equinox of date before solving -")
out("worth about 0.35 degrees today, which is eight hours of Sun.")
out()
out("| Shower | λ☉ (J2000) | Published ZHR | " + " | ".join(f"Peak {y} (UT)" for y in YEARS) + " | Alerts? |")
out("| --- | --- | --- | " + " | ".join("---" for _ in YEARS) + " | --- |")
for shower in events.METEOR_SHOWERS:
    peaks = []
    for year in YEARS:
        moment = astronomy.solar_longitude_crossing(year, shower["lambda_sun"])
        peaks.append(f"{moment:%d %b %H:%M}" if moment else "-")
    alerts = "yes" if shower["zhr"] >= events.MIN_METEOR_ZHR else "planning only"
    out(f"| {shower['name']} | {shower['lambda_sun']}° | {shower['zhr']}/hr | "
        + " | ".join(peaks) + f" | {alerts} |")
out()
out("The quoted rate on the card is **not** the ZHR. ZHR assumes the radiant at the")
out("zenith and perfect skies; the card scales it by the sine of the radiant altitude at")
out(f"your site, so the Geminids' 150 becomes roughly {events.expected_meteor_rate(150, 32)}/hr with the radiant at 32°.")
out()
out("Verify against: <https://www.imo.net/resources/calendar/>")
out()
out("### Milky Way core")
out()
out(f"Galactic centre at RA {astronomy.GALACTIC_CORE_RA_DEG}°, Dec {astronomy.GALACTIC_CORE_DEC_DEG}° (Sgr A*).")
out("A night is reported as the **intersection** of three independent conditions, not as")
out("the span of astronomical darkness:")
out()
out(f"- sun below {round(math.degrees(astronomy.ASTRONOMICAL_TWILIGHT))}°,")
out(f"- core above {round(events.MIN_CORE_ALTITUDE)}°,")
out(f"- moon down, or under {round(events.MOON_SUPPRESSION * 100)}% illuminated.")
out()
out("There is also a **lunar look-ahead**: a cloudless night with a bright moon is capped")
out(f"at {events.MOON_LOOKAHEAD_CEILING} when a night inside the next {events.MOON_LOOKAHEAD_DAYS} days has the moon under")
out(f"{round(events.MOON_LOOKAHEAD_ILLUMINATION * 100)}%. Moon phase next week is far more certain than cloud tonight, and")
out("without this the model says \"go now\" on the worse of the two.")
out()
out("### Grunion runs")
out()
lag = "the night after" if events.GRUNION_LAG_NIGHTS == 1 else f"{events.GRUNION_LAG_NIGHTS} nights after"
out(f"Run nights are the {events.GRUNION_RUN_NIGHTS} nights beginning {lag} each new and full moon,")
out("inside the CDFW season. The **hour** comes from live NOAA tide predictions -")
out("runs start one to two hours after the night high tide, and without a tide table the")
out("card says the hour is unknown rather than inventing one.")
out()
out("Verify against: <" + phenomena.SOURCE_CDFW_GRUNION + ">")
out()

out("## 2. Sky quality (sunset, sunrise, and cloud gating for astro)")
out()
out("Rebuilt around where the light actually comes from. A sunset has two separate")
out("requirements in two separate places:")
out()
out("- **The canvas**, overhead - high and mid cloud to catch the light.")
out(f"- **The light path**, upstream - a gap roughly {round(weather_scoring.LIGHT_PATH_KM)} km toward the sun, where the")
out("  beam grazes the surface. This one is a gate: if it is shut, nothing overhead")
out("  matters. On this coast it is usually the offshore marine layer, and it is invisible")
out("  from your own forecast.")
out()
out("Two extra probe points per zone are fetched for this, on the sun's own azimuth at the")
out("event, mirrored for sunrise. Without them the score falls back to the local deck, is")
out(f"capped at {weather_scoring.LOCAL_ONLY_CEILING}, and is labelled so on the card.")
out()
out("Measured inputs, all from Open-Meteo (free, no key):")
out()
for field in weather_scoring.OPEN_METEO_HOURLY:
    out(f"- `{field}`")
out("- `aerosol_optical_depth`, `dust` (air-quality endpoint) - decides saturation.")
out()
out(f"A sky only raises an alert when it is a **standout**: at least {weather_scoring.STANDOUT_MIN_SCORE}, and within")
out(f"{weather_scoring.STANDOUT_MARGIN} points of the best in the forecast window, with a modelled light path.")
out("\"Is this a good sunset\" is the wrong question; \"is this the one to go out for\" is")
out("the right one, and it is comparative.")
out()
out("Verify against: <https://open-meteo.com/en/docs> and <https://open-meteo.com/en/docs/air-quality-api>")
out()

by_evidence: dict[str, list] = {}
for window in phenomena.PEAK_WINDOWS:
    by_evidence.setdefault(window.evidence, []).append(window)

out("## 3. Biological windows")
out()
out(f"{len(phenomena.PEAK_WINDOWS)} entries. Each carries a background season (informational, never scored)")
out("and a concrete peak window (the only thing that scores).")
out()
for evidence, heading, blurb in (
    (phenomena.EVIDENCE_LIVE, "Live-verified windows",
     "These may alert, but only once a sighting corroborates them. Until then they are "
     "shown as watch windows and capped at planning level."),
    (phenomena.EVIDENCE_STATIC, "Estimates nothing can confirm",
     "**These never alert.** No feed publishes them. They are in the calendar so you can "
     "plan around them, and they are flagged on the card as estimates - check the "
     "sources yourself before booking anything."),
    (phenomena.EVIDENCE_COMPUTED, "Computed windows", "Geometry. Exact."),
):
    group = by_evidence.get(evidence, [])
    if not group:
        continue
    out(f"### {heading} (`{EVIDENCE_LABEL[evidence]}`)")
    out()
    out(blurb)
    out()
    out("| Phenomenon | Peak window | Days | Background season | Corroborated by | Where to verify |")
    out("| --- | --- | --- | --- | --- | --- |")
    for window in sorted(group, key=lambda w: w.peak_start):
        taxa = ", ".join(f"_{name}_" for name in window.live_taxa) or "—"
        links = " ".join(f"[{index + 1}]({url})" for index, url in enumerate(window.verify_urls)) or "**none**"
        flag = " ⚠︎ moves year to year" if window.confirm else ""
        span = f"{month_day(window.peak_start)} – {month_day(window.peak_end)}"
        days = str(window.peak_days)
        if window.key == "grunion_run":
            # The actual run nights are computed per lunar cycle (section 1);
            # this row is the season those nights are filtered against, and
            # showing its width as a "peak" would be exactly the thing this
            # whole design exists to stop.
            span += " (season gate only)"
            days = "see §1"
        out(f"| {window.name}{flag} | {span} | {days} | {window.season_range} | {taxa} | {links} |")
    out()

out("## 4. National parks and monuments")
out()
out("Trips rather than evenings: never gated on drive time, never eligible for a")
out("drop-everything alert. Seasons are about road access, heat and snow rather than")
out("biology, which is genuinely a matter of months. Closures are live.")
out()
out("| Unit | Best months | Closure feed |")
out("| --- | --- | --- |")
for park in parks.PARKS:
    agency = verification.closure_coverage(park.key)
    feed = f"**not covered** – {agency}" if agency else "NPS alerts API"
    best = ", ".join(
        f"{date(2001, a, 1):%b}–{date(2001, b, 1):%b}" if a != b else f"{date(2001, a, 1):%b}"
        for a, b in park.optimal
    )
    out(f"| {park.name} | {best} | {feed} |")
out()

out("## 5. Every external source, and what it is for")
out()
out("| Source | Used for | Key | Polled no more than |")
out("| --- | --- | --- | --- |")
rows = [
    ("Open-Meteo forecast", "Layered cloud at each zone and both light-path probes", "none",
     f"every {const.MIN_INTERVAL_WEATHER} min"),
    ("Open-Meteo air quality", "Aerosol optical depth and dust - colour saturation", "none",
     f"every {const.MIN_INTERVAL_AIR_QUALITY // 60} h"),
    ("eBird notable observations", "Rare birds, and crane corroboration", "free, instant",
     f"every {const.MIN_INTERVAL_EBIRD} min"),
    ("iNaturalist observations", "Whale, dolphin and mammal corroboration", "none",
     f"every {const.MIN_INTERVAL_INATURALIST} min"),
    ("Theodore Payne Wildflower Hotline", "Whether a bloom is actually happening", "none (scraped)",
     f"every {const.MIN_INTERVAL_FIELD_REPORTS // 60} h"),
    ("DesertUSA wildflower reports", "Desert bloom reports", "none (scraped)",
     f"every {const.MIN_INTERVAL_FIELD_REPORTS // 60} h"),
    ("California Fall Color", "Aspen colour reports", "none (scraped)",
     f"every {const.MIN_INTERVAL_FIELD_REPORTS // 60} h"),
    ("NOAA CO-OPS tide predictions", "The hour of a grunion run", "none",
     f"every {const.MIN_INTERVAL_TIDES // 60} h"),
    ("NPS alerts API", "Road and area closures - the trip-killer nothing else sees", "free",
     f"every {const.MIN_INTERVAL_PARK_ALERTS // 60} h"),
    ("Google Routes API", "Traffic-aware drive times", "yours, optional",
     f"every {const.MIN_INTERVAL_ROUTING} min"),
    ("Any subscription email", "Whatever a mailing list reports, via the IMAP integration "
     "and `photography_events.ingest_report`", "none", "whenever it arrives"),
]
for row in rows:
    out("| " + " | ".join(row) + " |")
out()
out("Requests are staggered into groups on startup so a Home Assistant restart does not")
out("fire everything at once, and each source backs off on its own after a failure.")
out()

out("## 6. Known gaps")
out()
out("Written down rather than papered over.")
out()
out("- **Whale Safe** (<" + phenomena.SOURCE_WHALE_SAFE + ">) is the best corroboration")
out("  source on this coast - a daily whale-presence rating for the Santa Barbara Channel")
out("  built from hydrophones, observers and a habitat model. Its API is by request only")
out("  (`boi-whalesafe@ucsb.edu`). The code is shaped for a key to drop straight in; it")
out("  links out rather than inventing an endpoint.")
out(f"- The {len(by_evidence.get(phenomena.EVIDENCE_STATIC, []))} `static` entries above have no live feed anywhere. That is a fact")
out("  about the world, not a shortcut - nobody publishes machine-readable rut or")
out("  pupping data. They are flagged, capped, and never alert.")
out("- Planet positions come from a two-body solution, so opposition dates can be up to")
out("  about a day off. Fine for planning, not an ephemeris.")
out("- Bloom timing depends on winter rainfall and cannot be computed at all. The three")
out("  hotline scrapers are the only real source, and they describe the past.")
