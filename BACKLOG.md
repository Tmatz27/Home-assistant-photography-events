# Remaining work after 0.14.0

Updated 2026-09-17. Read AGENTS.md first. The cancelled feature list below remains authoritative.

## Delivered

Source-health/HA contract foundations, card source split and sourced eclipse paths shipped in 0.12.0. Version 0.14.0 adds readable progressive details, five-row/list/calendar previews, stable grouped moonbow occurrences, stale/offline states, popup/scroll/focus preservation, USGS OGC v1 migration and strict validation, rare-only weather/streamflow health wiring, separate moonbow condition states and candidate-time preservation. See RELEASE_NOTES.md and BROWSER_VALIDATION.md.

## Still requires real data or installation access

- **Installed Home Assistant:** the user's screenshots show it has run. Agents have tested isolated HA contracts and real browser fixtures, but have not inspected the user's HA version, logs or upgrade. Await the version/local URL; then validate actual installation/restart/options/resource refresh and one full live update cycle.
- **Moonbow predictions:** generic sky geometry is not a viewpoint model. A historical Lower Falls timetable was cross-checked; its actual viewing interval is substantially shorter. Links and separate viewpoint guidance are present, but current dated predictions, terrain shadow and waterfall spray still need verification. No future date is copied from a past-year table, and no flow-to-spray threshold is invented.
- **Firefall:** seasonal alignment dates are a planning guide. Contrary to the previous backlog, this builder does not consume the Merced gauge and does not solve exact firefall light geometry. Actual Horsetail flow and the western light path remain unconfirmed. A river in another drainage would not close these gaps.
- **Waves:** only NDBC 46011/CDIP B1500 are calibrated. The Point Sal public trail and closure links were researched, but they do not establish safe storm access or validate B1500 heights at a different viewpoint. A verified elevated shooting position remains open. Expanding coastline coverage requires separate historical calibration/exposure checks.
- **Wildlife:** species reports remain distinct from rut, pupping and mass-aggregation reports. Unconfirmed subjects retain explicit verification routes; no new behavior feed is claimed.
- **Eclipses:** sourced central paths and known-site screening are implemented through 2035. Partial-only solar visibility, exhaustive drivable-land search and exact contacts remain outside the model.
- **Whale Safe:** settled. The public API has ship/compliance data, not whale presence. Presence access needs an external data agreement; do not use VSR dates as whale evidence.

## Cancelled by the user

Phone notifications/delivery, notification blueprint, hassfest, brand submission, the optional watching filter, score divided by drive sorting, and a separate this_week mode. Do not revive these without a new request.
