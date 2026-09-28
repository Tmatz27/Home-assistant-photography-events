# Remaining work after 0.16.0

Updated 2026-09-17. Read AGENTS.md first. The cancelled feature list below remains authoritative.

## Delivered

Source-health/HA contract foundations, card source split and sourced eclipse paths shipped in 0.12.0. Version 0.14.0 adds readable progressive details, five-row/list/calendar previews, stable grouped moonbow occurrences, stale/offline states, popup/scroll/focus preservation, USGS OGC v1 migration and strict validation, rare-only weather/streamflow health wiring, separate moonbow condition states and candidate-time preservation. See RELEASE_NOTES.md and BROWSER_VALIDATION.md.

## Still requires real data or installation access

- **Installed Home Assistant:** the user's screenshots show it has run. Agents have tested isolated HA contracts and real browser fixtures, but have not inspected the user's HA version, logs or upgrade. Await the version/local URL; then validate actual installation/restart/options/resource refresh and one full live update cycle.
- **Moonbow predictions:** generic sky geometry is not a viewpoint model. A historical Lower Falls timetable was cross-checked; its actual viewing interval is substantially shorter. Links and separate viewpoint guidance are present, but current dated predictions, terrain shadow and waterfall spray still need verification. No future date is copied from a past-year table, and no flow-to-spray threshold is invented. Since 0.16.0 a moonbow is actionable only with a `viewpoint_validated` prediction; the YosemiteMoonbow.com timetables are page images, so nothing produces that state. A machine-readable viewpoint timetable (or a terrain-shadow model for the Lower Fall footbridge) is the open item.
- **Firefall:** the published mid-February window stands in for the alignment; exact light geometry on the fall is not solved. Since 0.16.0 the gate checks a dated water report, local sunset cloud, the upstream light path and reported closures. Horsetail flow still comes only from reports; a river in another drainage would not close that gap.
- **Marine-zone alerts:** NWS Gale, Small Craft and Special Marine products use marine zone codes that the county table does not resolve. Boat trips always say "check the coastal waters forecast". Matching PZZ zones for Santa Barbara Channel, Morro Bay and Monterey Bay is open.
- **Filter kit:** the photographer owns a set of magnetic filters whose contents are not yet declared. Once they are, CPL/ND suggestions can move from technique text into the owned lists.
- **Waves:** only NDBC 46011/CDIP B1500 are calibrated. The Point Sal public trail and closure links were researched, but they do not establish safe storm access or validate B1500 heights at a different viewpoint. A verified elevated shooting position remains open. Expanding coastline coverage requires separate historical calibration/exposure checks.
- **Wildlife:** species reports remain distinct from rut, pupping and mass-aggregation reports. Unconfirmed subjects retain explicit verification routes; no new behavior feed is claimed.
- **Eclipses:** sourced central paths and known-site screening are implemented through 2035. Partial-only solar visibility, exhaustive drivable-land search and exact contacts remain outside the model.
- **Whale Safe:** settled. The public API has ship/compliance data, not whale presence. Presence access needs an external data agreement; do not use VSR dates as whale evidence.

## Cancelled by the user

Phone notifications/delivery, notification blueprint, hassfest, brand submission, the optional watching filter, score divided by drive sorting, and a separate this_week mode. Do not revive these without a new request.


## Open after 0.16.0

- **Live checks of new sources.** SunsetWx login/quality, the eBird species endpoint and the all-California NWS alert payload were implemented against documentation and published clients; confirm against a live response on the user's instance.
- **Friends of the Elephant Seal "What's happening now".** The best live rookery source; its structure could not be inspected from here, so no scraper. Until then, docent updates go through `ingest_report`.
- **Lightning.** No detection feed is connected (GOES GLM needs netCDF tooling); thunder stays a watch signal.
- **Weather subjects deferred (watch-only by design, not built):** lightning (no lightning-detection feed; forecast thunder stays a watch signal), lenticular clouds, rainbows (geometry is computable, radar is not wired), fog inversions (no validated viewpoint above the deck), halos, sun pillars and other ice-crystal optics, waterspouts. None may reach Can't Miss on a forecast; each would need an observation source first. `tests/test_hardening.py::TestWeatherIsNotCantMiss` guards this.
- **Sky gaps:** planetary and Moon-planet conjunctions in the backend (the standalone card computes them), bright comets (needs an observed-magnitude source such as COBS; predictions are not facts), zodiacal light.
- **Wildlife deferred:** sea otter mother-pup rafts (conflicting peak statements), grebe rushing (no sourced dates within six hours), golden eagle display (no public concentration found), La Jolla leopard sharks and tarantulas are planner-only candidates not yet built as rows.
- **Monarch counts** have no machine-readable source; they must arrive by report.
