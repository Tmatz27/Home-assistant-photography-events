# Backlog disposition — 0.12.0

User direction on 2026-09-07: execute Tier 1 and the remaining data work; cancel all Tier 2 work. Phone notifications are deferred until explicitly requested later.

## Tier 1 — implemented

1. Separate Home Assistant contract suite covers source isolation, throttles/backoff, multi-coordinate forecast bundles, partial API failure, cold-start deferral, entity payloads, real Store reloads and failed writes, routing deduplication, repairs, cancellation and unload. CI installs HA and actually executes this file; only this file skips in a portable checkout.
2. Named source-health details, per-hotline last success, persistent-on-screen degraded event markers, and automatic nonpersistent HA Repairs after three failures or stale cached data. Recovery/disable/unload clears issues. Fetch health is not confirmation of a phenomenon; observation times still govern corroboration.
3. Card split into 11 plain JavaScript sources. `node scripts/build-card.mjs` regenerates the single shipped card. `--check` and version checks run in CI. No bundler or new runtime dependency.

The original review's numerical wording needed correction: 17 of 22 windows are eligible for live corroboration, not necessarily confirmed now. Existing event_state pure tests and generic card source warnings predated this work; this release adds HA storage/cycle coverage and actionable health detail.

## Tier 2 — cancelled by the user

- Notification blueprint and phone delivery: deferred until a later explicit request.
- Hassfest integration: cancelled.
- Upstream brand-icon submission: cancelled.
- Watching-only filter, score divided by drive sorting, separate this_week mode: cancelled. Existing collapsible time sections and compact seven-day view remain.

## Tier 3 — implemented checks and explicit limits

- NASA catalog extended through 2035: 45 eclipses, 16 sourced central solar paths. TD converted using each row's published Delta T. Lunar windows use the actual umbral phases above the local horizon. Solar rows require a known viewing site inside the central path and inside the approximate drive budget. No ocean-centerline point is presented as a drive destination.
- Exact solar contacts, partial-only solar visibility and an exhaustive search of drivable land along every path remain outside the model. These require more than a centerline table; no prose-derived geometry or road claims were invented.
- Meteor drift audit: 1,920 candidate nights, 12 configured zones, eight showers, 2026–2035. Fixed versus moving radiants change one usable-night verdict (2030 Lyrids, Antelope Valley) and one preferred night (2031 Geminids, Pinnacles). Maximum boundary shift 7.29 minutes. Published Table 6 drift is now applied throughout each candidate night. Reproduce with `python tools/check_meteor_drift.py`.
- Five deliberately static biological windows remain static. No new reliable reporting feed was established for them.

## External information still needed

Whale Safe API: the public operator page https://whalesafe.com/get-involved/ directs API inquiries to its team. The supplied docs URL did not return usable documentation. Endpoint list, authentication requirements and an example response remain unverified. Existing dated operator reports/iNaturalist continue; an API presence rating would still not prove a feeding aggregation.
