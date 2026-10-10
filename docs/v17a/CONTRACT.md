# V17A Core-first architecture and contract gate

Audit date: 2026-10-09, America/Los_Angeles. HA main and origin/main:
`c76726ece1e485ece03810087927da344289fba7`. Core main:
`b14014760beee2c18d02a2b1f36756f6faee93a0`. No difference from supplied
anchors. Core API `v1`, schema `0008`, Core version `0.1.0-dev`.

This slice adds documents and synthetic tests only. It does not activate Core,
alter runtime, installation, versions, notification behavior, Core logic, or
the Unraid database. The existing HA engine is still active until V17B is
implemented. Acceptance of V17A is permission to review this contract, not
permission to delete the old engine or enable notifications.

The rebuild keeps the HACS repository, `photography_events` domain, card host,
visual language and useful interactions. Core owns
SIGNAL -> PATTERN -> PHENOMENON -> OPPORTUNITY. HA retrieves, validates,
sanitizes, caches and presents decisions. It must not reconstruct scoring,
qualification, travel eligibility, evidence interpretation, or safety.
No behavioral parity with the rejected v0.16.1 engine is required.

## Verified runtime and side effects

The exhaustive direct-import inventory is in [DEPENDENCIES.md](DEPENDENCIES.md).
Line references here refer to the audited starting commit, not future V17B.

| Active entry point | Actual behavior to retire in V17B |
| --- | --- |
| `__init__.py:63` `async_setup_entry` | Registers the same bundled card, constructs the legacy coordinator, initializes Store/catalogs, performs first legacy refresh, forwards three platforms and registers services. It never constructs CoreBridge. |
| `coordinator.py:163,221` | Creates all Source objects, event-choice/announcement Store and caches; loads wave calibration and eclipse JSON. |
| `coordinator.py:338` `_async_update_data` | Category/key-gated provider polling; cold-start deferred field-report task; builds opportunities, routes, filters drive, annotates source/access/safety, builds dashboards. |
| `coordinator.py:468` `_build` | HA sunset scoring, meteor/Milky Way windows, seasonal corroboration and text merging, monarch/firefall/snow conditions, bird classification/orca presence, grunion/parks/moonbow watches, waves/tides/aurora/eclipses/full Moon. |
| `coordinator.py:400-443` | `_apply_routing`, `within_drive`, source annotation, access annotation, `eligibility.annotate`, assessment coverage, dashboard and `alert_candidate` run on HA. |
| `coordinator.py:444-452` | `EventState.changes`, persist announcement fingerprints before `hass.bus.async_fire('photography_events_opportunity', ...)`. This is an actionable event side effect even without mobile delivery. |
| `coordinator.py:228` | Choice mutation persists to HA Store, recomputes legacy eligibility/dashboard/top_action and broadcasts entity changes. |
| `__init__.py:86-145`, `coordinator.py:685` | `ingest_report` parses IMAP-supplied text and adds reports to all coordinators; `set_event_choice` also broadcasts to all entries, without per-user choice scope. |
| `coordinator.py:714,754,768` | Deferred scraper refresh, HA Repairs for sources, cancellation of deferred work on unload. |
| `www/src/card.js:131-206` | Backend modes read HA entity attributes. Standalone timeline calls HA `weather/get_forecasts`, then browser `buildEvents` and local astronomy/sky scoring. No direct provider fetch was found in card sources; this is still a second intelligence path to disable. |
| `core_client.py`, `core_bridge.py` | Isolated developer-only scaffold; private ConfigEntry URL/token, bounded requests, no redirects, sanitized products, complete-success cache, held stale fallback. Existing production setup never calls its factory. |

Actual provider calls are verified against `_async_update_data` and fetch bodies;
source listings/guide URLs alone are not collectors:

| Provider / transport | Fetch entry and gate |
| --- | --- |
| Open-Meteo forecast | `_fetch_forecasts:888`; sunset/astronomy/rare; zones, home, condition points and light-path probes. |
| Open-Meteo air quality | `_fetch_air_quality:990`; sunset at home. |
| SunsetWx Sunburst | `_fetch_sunsetwx:831`; sunset + both client credentials; token POST and sunset/sunrise quality GETs. |
| eBird notable + iconic species | `_fetch_ebird:1009`, `_fetch_ebird_species:859`; Birds + eBird key, region/species loops. |
| iNaturalist | `_fetch_inaturalist:1033`; marine/mammals/rare/birds, union of marine taxa and derived corroboration taxa. |
| Theodore Payne, DesertUSA, California Fall Color | `_fetch_field_reports:1063`, `field_reports.REPORT_SOURCES`; reports enabled + blooms/foliage, deferred on cold start. |
| CDFW grunion HTML | `_fetch_grunion:786`; rare phenomena. |
| USGS OGC continuous discharge | `_fetch_streamflow:942`; rare phenomena, validated Merced gauge, v1/v0 request attempts. |
| NOAA CO-OPS tides | `_fetch_tides:1084`; rare or waves, station requests. |
| NPS alerts | `_fetch_park_alerts:1102`; `park_alerts_needed` + key, complete pagination. |
| NWS active CA alerts | `_fetch_surf_alerts:812`; unconditional each due cycle, safety for every category. |
| NOAA NDBC 46011 | `_fetch_wave_data:795`; Waves, realtime text. |
| CDIP B1500 | `_fetch_wave_data:795`; Waves, THREDDS DAS issue check and ASCII model data. |
| Condor Express RSS | `_fetch_condor:876`; marine. |
| NOAA SWPC OVATION | `_fetch_aurora:882`; astronomy. |
| Google Routes / Distance Matrix | `_apply_routing:1151`, `_fetch_routing:1218`, `_route_batch:1258`; configured key/mode and bounded destinations; cache/endpoint fallback. |

Whale Safe, Pirate Weather, Gemini, WFIGS and an independent monarch-count
service are not called by this HA coordinator. Pirate Weather can only be an
already-configured HA weather entity behind the standalone card request.
WFIGS belongs to Core M3A. NPS/sourced astronomy links are not additional feeds.

## Core-to-HA contract: retain the implemented API

[CORE_FIELDS.md](CORE_FIELDS.md) classifies every response-model field, including
nested debug contracts. Production-defined DTO shape is distinct from supported
production phenomena. The accepted upstream contract remains the real v1 API.
The proposed HA envelope below is a projection, never an upstream replacement.

| Actual GET endpoint | Auth / semantics | HA use |
| --- | --- | --- |
| `/health/ready` | No bearer required by Core; Health has versions/status. Checks DB/schema/PostGIS. 200 ready or 503 safe error. Readiness does not mean the assessment or all categories are current. | Backend startup/periodic probe; token validity proven by authenticated product request. |
| `/api/v1/opportunities` | Bearer; OpportunityList has assessment_id, generated_at, nullable data_as_of, complete/incomplete/degraded, source problem arrays, items. Optional presentation enum and category **mammals or birds only**. Insects exists in Opportunity schema but is not an accepted list category filter. No pagination/range/coverage parameters. | Unfiltered bounded fetch, then presentation-only slicing in HA. Do not send HA's legacy category names. |
| `/api/v1/opportunities/{occurrence_key}` | Bearer; single rich Opportunity, not an envelope. Reads current generation via same database path; 404 means not in current published result, not scientifically cancelled. | Later detail fetch; URL-encode key. Existing HA client lacks this method. For V17B use details already in bounded snapshot to avoid mixed generations. |
| `/api/v1/sources/health` | Bearer; versioned generated_at + SourceHealth records: key, UP/STALE/DOWN, attempt/success/provider timestamps, safe error_code. | Independent operational status. UP never proves opportunity eligibility or per-category assessment. Existing client lacks method. |
| `/api/v1/debug/source-contracts` | Bearer; shadow, production_promotion=false, generated_at, source contract/hash, freshness, operational counters and daily volume. No API/schema version envelope. | Architecture audit only. Never normal card data or a readiness gate. |
| `/api/v1/debug/live/calibration` | Bearer; off/shadow, production_promotion=false, pattern_analysis_state, source freshness, calibration items, monarch_count_confirmation. No generated_at/version envelope. Production eligibility, behavior confirmation and major aggregation confirmation are always false; animal_count is null. | Audit only; optional future admin diagnostics must explicitly say shadow. |
| `/api/v1/debug/patterns` | Bearer; versioned, assessment_id, off/shadow, disabled/unassessed/current/outdated analysis, patterns/clusters/held previews/coherence rejections/identity rejection count. No generated_at. | Audit only. A qualified episode is not actionable. Do not merge previews into normal list. |

Core `database.envelope` marks absent/expired assessment or required source
failure incomplete; noncomplete run/degraded sources produce degraded.
Expired products or a noncomplete envelope become held and ineligible before
presentation/category filtering. `generated_at` is response time, not evidence
time. List validity depends on internal assessment valid_until, which is **not**
exposed on the envelope. A fresh empty filtered list can say complete even if
that category has no evaluator (`tests/test_database.py:143-145`). Therefore
neither `items=[]`, `ready`, nor `category=birds` proves Birds was assessed.

Reused fields: exact occurrence_key/phenomenon_key, starts_at/ends_at,
presentation, eligibility/held/watching, significance/confidence/urgency,
evidence_state, safety_state/access_state/condition_state, drive_minutes/basis,
reason/awaiting/blockers, gear/ethics/safety text/detail, data_as_of/valid_until,
definition_key/version/hash/engine_version. Never compress separate scores into
the old `score` or invent precision/source-report text not supplied by Core.
`assessment_id` identifies a generation; `pattern_episode_id` is backend-only.

### Validation and cache rules (proposed, not activated)

- Preserve existing 5-second request deadline (maximum configurable 30 seconds),
  2 MiB input cap and 500-item cap. One unfiltered fetch; over-limit or invalid
  response is a protocol error, never a silently truncated successful assessment.
- Validate exact API v1 and reviewed schema compatibility set initially `{0008}`,
  then actual field types/enums, aware timestamps, finite coordinate/drive values,
  integer 0..100 scores, boolean flags, unique nonempty occurrence keys <=256
  characters, definition provenance and start <= end. Unknown API/schema or new
  enum fails closed until reviewed. Ignore additive unknown fields recursively.
  A schema revision is not an API version; compatibility can later expand after tests.
- Existing parser is reusable transport groundwork, **not sufficient**: it
  discards assessment_id, accepts any string schema version, does not verify
  location policy/approved coordinates or full text/list types, and copies several
  nested values without recursive type validation. Existing bridge treats a
  successful old complete response as fresh and can persist it. V17B must fix
  these before exposing data; this audit does not change the scaffold.
- Set a HA presentation refresh age of 15 minutes (product transport policy,
  not ecological freshness). Reject timestamps >60 seconds into HA's future as
  clock error. Keep generated_at, data_as_of, fetched_at, saved_at distinct. Do
  not renew evidence time by polling, cache reload, choice edit or source recovery.
- Effective UI deadline is min(fetched_at +15m, all displayed item valid_until).
  Empty scope requires reviewed coverage plus sufficiently recent data_as_of;
  until Core exposes envelope validity, this is an additional conservative UI
  bound, not a claim of Core evidence coverage. Missing data_as_of cannot be current.
- Persist only the sanitized projection of the last complete, validated normal
  snapshot. Preserve it through incomplete refreshes; retain up to seven days
  for clearly labelled historical context, never current action. Revalidate on
  load with projection/API/schema versions and connection namespace. Clear active
  action immediately on timeout/disconnect/auth/version/protocol error or expiry.
- On token revocation/missing token, hide cached rich data pending reauth; a token
  change invalidates cache until authenticated. URL changes invalidate the
  connection's active cache. No legacy provider or browser intelligence fallback.

## HA-to-Lovelace presentation contract: proposed `ha.v17.1`

Use HA's authenticated WebSocket connection. Browser never learns Core URL or
token and never contacts Core. These are **new HA commands for V17B**, not Core
endpoints and not registered by V17A:

`photography_events/get_view` request: `entry_id`, `projection_version: 'ha.v17.1'`,
`view: cant_miss|watching|planner|birds`, optional `snapshot_id`, optional opaque
`cursor`, `limit` (1..50; default 50). Planner may include `from`/`through` aware
dates bounded to 366 days; these slice only published Core products. Do not
call upstream date filters that do not exist. No browser-supplied Core origin.

Response fields:

| Field | Type / meaning |
| --- | --- |
| projection_version | Exact `ha.v17.1`; mismatch -> unsupported_projection error, no rows. |
| entry_id, snapshot_id | Existing HA entry and opaque connection+generation+projection revision. Repeated fetches of same material snapshot keep revision; no token/URL encoded in it. |
| generated_at, data_as_of, fetched_at, expires_at | RFC3339 aware UTC; data_as_of nullable only for unassessed/error. Retain Core times; fetched_at is HA retrieval time. |
| availability | online / offline / auth_required / connection_required / incompatible / invalid_response. |
| assessment_state | complete / incomplete / degraded / not_assessed; first three preserve Core meaning. not_assessed derived from missing assessment_id/data_as_of. |
| freshness | current / stale / unknown. Local aging can only reduce freshness. |
| view_state | current / empty_assessed / not_assessed / incomplete / degraded / unsupported / coverage_unknown / shadow_only / offline_stale / unavailable. |
| coverage | `{state: verified|unverified|unsupported|shadow, scope: [phenomenon keys], through: timestamp|null, basis: reviewed-capability|unknown}`. HA-derived declarations explicitly marked; never inferred from empty items or SourceHealth. Initial b140147 normal broad category coverage is unverified. |
| problems | Bounded array of safe fixed source/error codes plus public explanations; no exception dumps, headers, SQL or URLs. |
| counts | available, returned, suppressed; null available for unknown/incomplete scope. Zero only expresses the bounded successfully assessed scope, never all categories. |
| items, next_cursor, truncated | <=50 projected rows, cursor|null, bool. Truncated means more rows in same immutable snapshot; not missing evidence. |
| choices | `{available:false, authority:'pending_core'}` initially; no fake durable successes. |

Each row keeps **the same Core field names** for the reused fields above, and
adds `event_id = occurrence_key`, `row_state`, `actionable` and `choice` (default
when persistence unavailable). Location is separately sanitized. No alias maps
`confidence` to eligibility. Details may be a second bounded command
`photography_events/get_detail` with entry_id/version/snapshot_id/occurrence_key;
returns one <=32 KiB row from that snapshot or snapshot_expired/not_found.
No upstream request per expand/click in the first V17B slice.

Future change notices use `photography_events/subscribe` (HA WS subscription)
with only entry_id, revision and availability; coalesce notices <=1/second and
fetch pages when revision changes. Default first slice can use a small summary
entity revision to trigger read requests; no need to implement both paths at once.
One read per user/entry/view per second, maximum two in flight; disconnect
cleans subscriptions, unload unregisters per-entry state. Reject unauthorized
entry access using HA auth context and supported permission checks. Writes, when
implemented later, derive user identity from HA context, never request payload.

Wire limits: 128 KiB UTF-8 per page, 32 KiB detail, 50 rows/page, 500 rows per
snapshot, <=64 source/problem entries, <=32 array elements per row text field,
<=2,048 chars per detail/reason/awaiting, <=256 chars per title/key, <=512 chars
per gear/safety array entry. Reject oversized rows safely; set invalid_response
rather than claim successful completeness after dropping one. Escape every
text insertion; never HTML from providers. Page tokens bind entry, user,
snapshot and view, expire after 15 minutes. A changed generation yields
snapshot_expired; the card reloads and preserves UI state by occurrence key.
No per-push 400-row attributes.

Retain small entity unique IDs `<entry_id>_next_opportunity`, `_cant_miss`,
`_planning_outlook`, `_calendar`, `_action_opportunity` and `_best_sky_score`.
Summary attrs <=4 KiB contain projection version, entry_id, snapshot revision,
status, timestamps and bounded counts; no rich lists/credentials. Keep sunset
score entity registered but unavailable with unsupported status until Core
provides it; zero would falsely mean an assessed bad sunset. Unknown action
binary sensor is unavailable, not off-success. V17B initially prevents all
action event emission and keeps the action entity nonactionable. Calendar maps
sanitized published rows; precise calendar day/all-day semantics await explicit
Core time precision, never infer wildlife appointment times from midnight.

### Retained feature requirements

| Feature | Backend payload needed / current Core gap |
| --- | --- |
| A. Can't Miss | Core cant_miss + eligibility=true, held=false, current normal product, complete assessment, reviewed scope and coherent safety/access/conditions; reason, time, destination, gear and provenance. Compact five previews with More over bounded pages. No HA re-ranking intelligence; supplied urgency is display ordering only, ties by starts_at/key. Initial scope warning required. |
| B. Watching | Normal watching/held products, evidence_state, awaiting, blockers, times, public location and source status. Preserve details/navigation without promoting signals. No normal pattern feed currently exists; shadow previews stay out. |
| C. Year Planner | Available planner products, bounded date intervals, category and provenance; month/list switch, category filters, expanded sections and dialogs. Display known published windows and explicitly unknown coverage through the requested year. Core does not yet supply a one-year assessed plan, alternatives, time precision or all legacy categories. |
| D. Birds | Normal bird_spectacle/bird_encounter and bird_classification; useful visual grouping only. No production bird evaluator and no Chase contract; show unsupported, never confidently no birds. |
| E. Details | Same stable occurrence identity, definition provenance, safety/access/condition state, ethics, gear, detail/reason/awaiting and timestamps. Raw reports/observation links are unavailable and must not be recreated. Full ranges supported; preferred nights/alternatives/owned-kit/add/required and drone rules beyond Gear are missing. |
| F. Follow/Skip/Seen | Stable occurrence identity, user scope, authoritative choice state and acknowledged mutation. Keep controls visibly unavailable (`pending_core`) in first V17B slice until Core persistence exists. Local expanded/focus/scroll/month/filter state remains usable. |
| G. Source and assessment status | Authenticated source health plus separate assessment_state, problems, scope and freshness. Distinguish fetched, provider-updated and assessed dates. No raw debug panel in normal card. |
| H. Offline/unavailable | Explicit connection/auth/version/error + preserved timestamps, expired deadline and held cached context. No quiet-week copy, travel CTA or implied safety. A reconnect does not upgrade old evidence. |

Existing UI mechanisms to preserve: initial configured mode, in-card tabs,
More/collapsed buckets, month bars/detail dialogs, filters, full date ranges,
expanded nested sections, initiating-control anchor, focus, composed-tree scroll
owners and local stale timer. Adapt `card.js`, `cant-miss.js`, `modes.js`,
`formatting.js`, `editor.js` at the transport boundary. Remove browser fallback
use of `astronomy.js`, `sky-scoring.js`, `timeline.js` in V17B, preserve source
files until disconnection tests pass. Cosmetic catalog colors may remain;
catalog opportunity dates/qualifications must not supply missing Core output.

### State precedence and notification prohibition

Availability error beats action; offline cached -> offline_stale, no cache ->
unavailable. Incompatible/auth-required data never enters current rows. Shadow
origin -> shadow_only regardless of alleged eligibility. Unsupported scope ->
unsupported; unknown coverage -> coverage_unknown. Missing generation/evidence
time -> not_assessed; noncomplete -> incomplete/degraded; expired -> stale.
Only complete, current, verified scoped normal production data can use
current/empty_assessed. Multiple conditions remain visible as orthogonal fields,
not erased by the primary view_state. Empty assessed copy names scope and
coverage period; it never says the whole week is clear when coverage is partial.

Notifications are disabled for all V17A and the initial V17B. Any future enablement
must separately establish Core-owned deduplication/choices and reviewed product
coverage. Even then forbid delivery on shadow, unsupported, unverified scope,
never assessed, incomplete, degraded, stale/offline, wrong API/schema, missing
credentials, invalid response, missing/ambiguous identity, held/ineligible,
unknown/unsafe safety, unknown/unreviewed access, unknown conditions, expired
item, missing provenance, withheld/unapproved travel destination or suppressed
user preference. Fail closed on contradictory flags. Display cannot promote.
Follow affects notification preference only; it cannot alter scientific evidence.

## Missing Core feature ledger (no Core changes in V17A)

| Gap | Current evidence | Gate / future owner |
| --- | --- | --- |
| Category/phenomenon coverage, assessment horizon and envelope validity | OpportunityList has none; filtered empty birds can be complete. | Core capability/coverage contract and independent review. Until then explicit coverage_unknown; no whole-week empty claim. |
| Production phenomena breadth | `phenomena.definition` accepts only tule_elk_rut; normal publication M1 vertical slice. | Core, selectively rebuild extraordinary opportunities, not legacy parity. |
| Live collection -> production publication | M3A collects iNaturalist bears/monarchs, WFIGS/NWS context; calibration is shadow with production_promotion=false. | Core release/policy approval. Source UP is not a new production evaluator. |
| Other mammals/marine/birds/monarchs | M2 fixture policies for monarch/bear/eagle/orca/etc are provisional; M3A live policies restrict bears/monarchs. No production Birds/Chase. | Core independent policy validation and approved destinations; no HA inference. |
| Sunsets/astronomy, Milky Way/meteors/eclipse/full Moon, blooms/foliage, waves/tides/grunion, park plans/moonbows/snow/firefall | Missing normal API category/evaluator coverage. HA has legacy code, not authority. | Core later selective implementation. Planner tabs show unsupported gaps, not old calculations. |
| Travel/access/conditions completeness | Drive estimate/basis, safety/access and not_required/unknown condition fields exist. Current port's access='public' is not universal current road/park access. | Core reviewed per-phenomenon required gates. HA retains exact statuses and conservatively withholds action. |
| Privacy-safe evidence summaries/links and source dependency roles | Public definition provenance exists; normal API lacks per-row source attribution/details/coverage-role list. Debug is not public evidence. | Core bounded sanitized public summaries; no HA raw report reconstruction. |
| Planner precision, horizon, preferred times/alternatives and multi-location grouping | starts/ends and best_time_of_day/detail exist; no time_precision/choice_ids/alternative-night comparison contract. | Core explicit semantic fields. No grouping that invents occurrence identity. |
| Owned-kit extras and required safety equipment | Gear has take/optional/skip/start/support/technique/video/drone/status. Legacy add/required plans missing. | Core product fields; hide unsupported sections. |
| Follow/Skip/Seen and user identity | Existing DB has choice/notification groundwork; API only GETs, no supported write/read choice contract. | Core persistence contract, idempotency and authentication principal mapping later. No new POST endpoints in V17A. |
| Core instance/principal identity | Version/health do not expose stable instance/account IDs. | Future identity contract for connection replacement and multi-HA users. URL hash is cache scoping only, not durable Core identity. |

These gaps are blockers to a fully functional four-view product and actionable
notifications, not reasons to postpone a bounded read-only V17B card showing
available normal products, explicit scope limits and unavailable controls.
