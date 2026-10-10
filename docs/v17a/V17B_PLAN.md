# Precise V17B implementation sequence

V17B's first functional increment is an authenticated read-only Core card with
truthful coverage gaps. Four-view production breadth and durable choices remain
blocked by the Core ledger. Do not fill gaps with HA providers or browser science.

This plan remains future work; do not execute it during V17A corrections or until
V17B is authorized. Apply the corrected contract's independent fetched_at
transport clock, provisional six-hour assessment cap, per-row valid_until and
state precedence. Core-derived destination artifacts require independently pinned
provenance/digests and product-definition drift checks, never HA-invented sites.

| File/path | Keep / replace / eventual removal | Exact next work and gate |
| --- | --- | --- |
| `core_client.py` | Adapt | Keep private aiohttp session ownership, bounded deadline/size, safe exception codes, no redirects. Preserve assessment_id, strict schema/field/identity validation; add authenticated source health method. Detail method can wait: use snapshot products first. Run existing client tests and new malformed/provenance/version/size tests. |
| `core_bridge.py` | Adapt | Keep complete-success cache foundations. Fix successful-but-expired freshness, empty-envelope deadline, cache namespace/version/auth invalidation; use one sanitized snapshot for all views. Old cache must pass new serializer before use. Test stale/incomplete/restart/token/URL change. |
| `projection.py` (new, small) | Add adapter only | Implement contract typed allowlist, approved destination registry, per-view status and limits. It may reduce action, never promote/re-score. Port test-only acceptance examples to actual serializer tests. No evaluator abstraction or new intelligence framework. |
| `coordinator.py` | Rewrite in place | Keep DataUpdateCoordinator interface; construct Core bridge only, schedule read/expiry and status. Remove active `_sources`, `_build`, `_apply_routing`, annotations, calibration/catalog initialization and deferred provider tasks from execution. No imports that indirectly instantiate collectors. Test no legacy network/task/store/notice calls on setup/refresh/choice/outage. Do not delete file. |
| `const.py` | Adapt | Retain DOMAIN, compatible IDs and card labels; add projection/status/limits only. Preserve legacy constants temporarily for old tests/modules. Remove threshold/source-policy use from new coordinator. If intervals change, follow repository TRACKING regeneration instruction; no version changes in this slice. |
| `config_flow.py` | Rewrite flow paths in place | Implement major-3 design only with explicit V17B approval, URL/password connection, reconfigure, reauth and selector forms. Keep singleton/serialization safeguards and immutable integration identity. Test no duplicate entries, preserved options, blank/replacement token semantics and error forms on actual supported HA versions. Do not delete file. |
| `__init__.py` | Adapt | Implement local v1/v2 migration, dormant status/Repair connection path, active Core setup/unload, card registration independent of Core availability, supported failure exceptions. Do not register legacy ingest_report or broadcast legacy choice service on new setup. If old service definition remains, return an explicit unsupported error without parsing/calling providers. |
| `strings.json`, `translations/en.json` | Adapt | Translated connect/reauth/reconfigure/errors and Repair guidance, inactive legacy controls explained. Token never echoed or logged. |
| `repairs.py` (new) | Add | Small translated completion flow using the same private connection validator and updating the same entry. Prove migrated setup prompts connection and completion removes Repair. No manual storage changes. |
| `websocket.py` (new) | Add | Register only authenticated get_view/get_detail first, permission checks, entry/snapshot/user-scoped bounded cursor, safe errors and rate bounds. Fetch from coordinator snapshot, never browser-provided Core origin. Subscription may wait: summary revision is sufficient first. Choice command remains unavailable until supported Core contract. |
| `sensor.py` | Adapt | Preserve four existing suffixes/device info. Replace rich arrays with <=4 KiB summaries/status/revision. BestSkyScore stays registered unavailable until supported. No legacy PARKS/GEAR/phenomena/events imports in new active projection. |
| `binary_sensor.py` | Adapt | Preserve action ID. Initial read-only rollout unavailable/nonactionable, no notification-triggering on transitions. Later Core action gate requires separate review. Stop importing legacy EventState/event_id. |
| `calendar.py` | Adapt | Same calendar ID, bounded sanitized products and safe unavailable state. Preserve actual aware intervals; explicit precision semantics needed before converting Core date windows to all-day. No synthesized year or raw prose/coordinates. |
| `event_state.py`, `services.yaml` | Preserve temporarily; disconnect | Keep legacy Store readable and untouched for reviewed mapping/export. No EventState.changes/announcement writes in new runtime. Choice controls say unavailable until Core owns persistence. Remove/mark retired ingestion service documentation at implementation; do not implement local proxy persistence. |
| `www/src/card.js` | Adapt | Preserve host, focus/scroll/anchors and configured initial view. Read authenticated WS snapshots on summary revision, expire locally, abort/coalesce requests. Always use Core mode in v17; no `weather/get_forecasts` or `buildEvents` fallback on missing entities/outage. |
| `www/src/cant-miss.js`, `modes.js`, `formatting.js` | Adapt | Consume ha.v17.1 rows/status, keep five previews/More, Watching, list/month/details, filters and expanded state. Truthful empty/unsupported/coverage_unknown/shadow/stale states, hidden unsupported sections, unavailable choices. No old-score aliases or raw reports. |
| `www/src/editor.js`, `catalog.js` | Adapt / preserve cosmetics | Keep appearance/mode choices/entity selections usable; remove misleading backend/threshold/weather fallback controls. Keep category colors only; catalog dates/science cannot backfill Core. |
| `www/src/styles.js`, `header.js`, `register.js` | Preserve/adapt minimally | Keep appearance, accessible navigation and registration; add explicit status copy. Preserve card URL/custom element identity. |
| `www/src/astronomy.js`, `sky-scoring.js`, `timeline.js` | Preserve temporarily; stop assembly/use after gates | Runtime references must disappear from v17 card; replace timeline mode navigation with supported planner or explicit unsupported state, never browser engine fallback. Deletion waits for source assembly/import scan and no-fallback browser tests. |
| `www/photography-events-card.js`, `scripts/card-sources.json` | Regenerate/adapt | Source-first changes; build artifact with existing assembler, inspect diff, version checker must remain coherent. Do not hand-edit generated JS or add a bundler/dependency. |
| Legacy providers/science modules and JSON catalogs | Preserve temporarily; eventual removal | `wildlife`, `field_reports`, `email_reports`, `waves`, `spectacles`, `grunion`, `streamflow`, `verification`, `routing`, `throttle`, `weather_scoring`, `weather_hazards`, `astronomy`, `events`, `phenomena`, `parks`, `signals`, `curation`, `eligibility`, `birds`, `lunar`, `conditions`, `gear`, `observations`, `eclipses`, `sunburst`, `source_health`, eclipse/wave catalogs. Verify all active imports/callers retired; retain as historical reference/tests until Core coverage and independent review permit deletion. |
| Existing tests, `.github/workflows/validate.yml` | Preserve; add tests | Never weaken existing assertions to make the rebuild pass. Keep legacy unit tests until modules deliberately removed; add real-HA migration/auth/registry/setup/WS tests, serializer leak tests and browser state/navigation tests. Tests that assert old active behavior require a separately reviewed retirement decision, not silent deletion. |

Implementation order: (1) client + serializer tests, (2) bridge/cache tests,
(3) coordinator with no collectors or notice side effects, (4) config/Repairs
and setup migration, (5) summary entities/calendar, (6) authenticated bounded
read transport, (7) card source adapters and assembly, (8) integration/browser
validation and independent review. Keep each increment reviewable; do not expose
the card to partially validated Core products during development.

Required gates before activation/deletion:

1. Fixtures reflect the **actual** v1 schema, and privacy/type/limits tests run
   against the production serializer. Core normal/debug separation is proven.
2. Current scoped empty, unknown coverage, never assessed, incomplete, degraded,
   unsupported, shadow, stale/offline, wrong token/API and corrupt snapshot are
   distinct in HA and browser. Entire-year/entire-week coverage is never assumed.
3. Real HA v1/v2 migration preserves registry IDs/options/resources and prompts
   secure completion. Reconfigure/reauth updates exactly one entry. Missing token,
   first-refresh outage, failed setup and reload/unload cannot crash HA.
4. Trace setup/refresh/browser interactions under outage and assert zero external
   provider requests, zero legacy assessments and zero opportunity events. Action
   entity cannot inadvertently revive user-owned legacy notification automation.
5. Authenticated WS permission/rate/cursor tests; cache/calendar/entity/detail
   negative leakage tests; exact approved public destinations only. No bearer in
   logs, diagnostics, storage projections or browser network/storage.
6. Retained tab/mode/More/dialog/group/focus/scroll behaviors pass browser checks,
   without grouped occurrence identity guesses. Tests must age data without pushes.
7. Existing pure Python, real HA matrix, Node tests, card assembly/syntax/version,
   pyflakes and HACS checks pass or documented existing failures are independently
   accepted. Local synthetic tests do not substitute for live deployment validation.
8. Small read-only live Core acceptance on an isolated HA installation: inspect
   metadata/status without changing Core logic or running Unraid DB; independently
   review supported scope and provenance. No notifications. Back up HA config.

V17A rollback is a docs/tests commit revert. V17B rollback requires matching
pre-upgrade configuration backup if entry version changes. On operational failure
stay unavailable; never quietly return to legacy intelligence. Runtime deletion,
notification enablement and expansion of Core breadth are later explicit gates.
