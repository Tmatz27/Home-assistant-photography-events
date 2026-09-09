# Photography Events 0.12.0

- Source health now distinguishes failed, stale, waiting and disabled feeds. Individual hotlines have their own status, last-success timestamps and automatic HA Repairs after repeated failures. Affected events show "Data degraded" without changing their evidence level.
- Failed or partial API responses no longer masquerade as successful empty observations. Valid empty reports remain quiet; failed portions retain cached data with its original dates. Recognizable hotline content is required before a scrape counts as successful.
- Forecast/outlook labels now survive the compact sensor payload and appear in night comparisons and location details. The existing opportunity-event path now shares the 48-hour limit; long-range outlooks cannot fire it.
- Follow/Skip is committed to memory only after Store succeeds. Failed saves cannot silently skip an event or consume an unpublished update. Deferred scraper tasks and the parent coordinator shut down cleanly.
- Added separate real Home Assistant contract tests and an executing CI job. The portable suite still runs without HA. Test dependencies do not alter the integration's runtime requirements.
- Split the card into 11 source files with a dependency-free concatenation script. CI checks source/artifact synchronization; installation still uses one JS file.
- Imported 45 NASA eclipses for 2026–2035, including published coordinates for all 16 central solar paths. Corrected TD versus UT labeling. The backend now evaluates lunar umbral-phase visibility and known sites inside central solar paths; the standalone card uses the same catalog. An ocean path point is never treated as a road destination. Partial-only solar visibility, exhaustive road access and exact solar contacts remain outside this model.
- Added published near-peak meteor radiant drift after the 1,920-night audit found a usable-night change and a preferred-night change. Solar-longitude peak calculations and evidence ceilings are preserved.
- Tier 2 cancelled at the user's request: no notification blueprint or phone delivery, hassfest, upstream brand submission, watching filter, score/drive sorting or separate this_week mode.

Whale Safe remains unwired. Its public site directs API access inquiries to the operator; endpoint/auth/response details could not be verified. No external messages or subscriptions were created. The five deliberately static windows remain static.
