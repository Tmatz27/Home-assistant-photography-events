# Handoff log — 0.10.0

## 2026-09-06: approved direction and implementation

Publication base: c78b53d (merged v0.9.1). Preserved the brand assets, version check script, dependency setup and validation-gated release workflow.

Starting upstream: 5b57b713b5f21059ba3c08364f87b0fdd8cec86a (0.9.0). The user approved implementation and publishing a release after committing. No unrelated repository or stale branch was changed.

Implemented:
- Default integration planner with short expandable rows, location-specific time windows/details, evidence labels, visible access information and approximate drives.
- HA Store-backed Follow/Skip by occurrence, across viewpoints and restarts. Restore is available through Show skipped. Skip suppresses the hero and new opportunity-event notifications.
- Actual hero window opening, with no travel/setup deadline; ongoing events are retained until their end even if the photographer could not arrive in time.
- Persistent meaningful-update events; small score refreshes and repeated downloads do not notify again. Mobile routing is an explicit README automation example, not an installed notification destination.
- Exceptional waves for the Vandenberg coast: NDBC 46011, CDIP B1500, NWS coastal advisories; separate labels for measured offshore versus forecast nearshore height; quality, direction, period, observation and model-run age checks. Initial historical distinct-episode calibration and its limitations are checked in.
- Conservative local NOAA OVATION signal and strict Condor Express dated megapod parser. The latter rejects trip totals, unknown observation dates and old reports.
- CDFW expected grunion schedule with Pacific timezone, midnight rollover and published Santa Barbara offset. The coordinator no longer uses lunar heuristics as exact run dates.
- Search targets for moonbows, glowing surf, winter waterfowl and Pinnacles condors. These remain unconfirmed where no live source is connected.
- Major meteor planning extended to a year; existing astronomical evidence and geometry safeguards retained.
- Species sightings no longer confirm calving, fighting, feeding or aggregations. Correct iNaturalist categories and a fourteen-day query; expired actionable sightings removed.
- Source diagnostics exposed, HTTP-only external links, all version markers updated, tracking inventory regenerated, Python dependency installation added to CI, and version changes on main trigger tested releases.

Validation:
- 182 Python tests passed.
- 85 JavaScript tests passed; JavaScript syntax check passed.
- pyflakes passed for integration and tools.
- Real browser preview checked short rows, expanded location times, source/evidence details and Skip behavior using clearly synthetic events. A preview is not a live Home Assistant deployment test.
- Saved public feed responses were parsed for NDBC, CDIP, CDFW and Condor Express. See SOURCE_VALIDATION.md and the separate output source-check record.

Known limits / follow-up:
- Wave runtime coverage is one calibrated coastal area, not all California. Hindcast frequency is not forecast skill or a promise of one event per year.
- Whale Safe API remains disconnected. No automatic live confirmation for every rut, cub, pupping, monarch, foliage, bloom, bioluminescence or waterfall event. Search targets explicitly say so.
- Moonbow viewpoint geometry/current waterfall confirmation, additional calibrated coastlines and verified elevated wave viewpoints still need work.
- Solar eclipse path-based drive filtering remains blocked on sourced geometry; the explicit standalone timeline still contains the older astronomical implementation and eclipse table through 2028. It has not been silently replaced with invented backend coverage.
- Ingested email stays fixed-vocabulary data. Its received date does not become an observation date. Reports without explicit phenomenon/date cannot corroborate a named spectacle.
- Full Home Assistant installation, HACS upgrade and mobile delivery must be checked on the user's instance; no connection to that instance was provided.
