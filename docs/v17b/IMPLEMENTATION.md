Current engineering build: **0.17.0-dev.3**. See [SCHEMA_COMPATIBILITY.md](SCHEMA_COMPATIBILITY.md) for verified Core API v1/schema 0008 and 0009 support, and [CORRECTIONS.md](CORRECTIONS.md) for the dev.2 corrections. The implementation record below describes the reviewed dev.1 baseline. Birds/Planner do not return unsupported rows, and cross-origin reconfiguration requires a new bearer.

# V17B read-only Core development build

Starting HA main: `63dcc0ab46f8e2d3ad23a0ce2b1623357963430b`.
Core source reference remains `b14014760beee2c18d02a2b1f36756f6faee93a0`,
API v1/schema 0008/engine 0.1.0-dev. Core source and the Unraid database are
unmodified. Version **0.17.0-dev.1** is an engineering build; no tag, HACS release
or installation on the user's running Home Assistant is authorized or performed.

## Working vertical slice

The existing `photography_events` entry now constructs only a Core coordinator.
The shared HA aiohttp session makes bounded server-side authenticated GETs to
readiness, normal opportunities and source health. Browser reads use HA's
authenticated WebSocket connection, never a Core URL/token or direct Core HTTP.

The same card resource URL/custom element, HA card host, four tabs, colors,
header, responsive styles, accessible controls, occurrence identity,
expand/collapse, five previews/More, list/month duration bars and detail modal
remain. Existing composed-tree scroll, focus and initiating-control anchor code
is retained. Unsupported data remains visible as a useful status panel. The
bundled artifact contains no astronomy/scoring/catalog/timeline fallback.

Core v1 does not establish reviewed broad assessment coverage. Therefore the
installed build deliberately keeps coverage **unverified**, current opportunity
counts **unknown**, and Can't Miss empty of unauthorized rows. Watching can show
sanitized normal published context, held with its timestamps and assessment
problems. Planner shows only supplied ranges and explicitly unsupported year-wide
coverage; Birds is unsupported. This is not a fully assessed four-category
product. No synthetic wildlife fixture is imported by production.

## File-by-file implementation

| File | Implementation |
| --- | --- |
| `core_client.py` | Shared-session ownership; private bearer; 5 s default/30 s maximum timeout; 2 MiB/500 item caps; redirects disabled; normal v1/schema0008/pinned engine validation; source health; exact assessment IDs and typed allowlists. |
| `projection.py` | Sole rich serializer: typed reconstruction, reviewed normal identity grammar, strict flags/enums/provenance/ranges, unknown-field rejection/discard, fixed source codes, independently reviewed exact destinations and public prose, independent freshness/state projection. |
| `core_bridge.py` | Sanitized complete normal cache only; original fetch/input/row stamps; version/URL+token namespace and policy revalidation; seven-day historical retention; incomplete refresh preserves complete cache; auth/version/protocol hides rich context. |
| `coordinator.py` | Rewritten in place: Core refreshes every five minutes, presentation revision and expiry timers, HA auth/retry lifecycle; no provider/science/routing/choice/announcement imports or calls. |
| `__init__.py` | Local supported v1/v2->v3 migration, dormant missing-connection setup/Repair, card registration independent of Core, platform setup/reload/unload, explicit unsupported retired services. Transient outages use HA retry; auth uses reauth; incompatible/protocol setup requires repair rather than pretending to be a valid empty result. |
| `config_flow.py` | Singleton Core URL/password selectors, actual authenticated validation, reconfigure/reauth on the same entry, no secret prefill, explicitly labelled blank-token retention only in reconfigure, presentation-only initial-view option; old settings retained inactive. |
| `repairs.py` | Connection completion against the existing entry using HA Repairs and the same private validator; issue removed after successful completion. |
| `websocket.py` | Authenticated `get_view`/`get_detail`; entry permissions; explicit versions/views/ranges/limits; one read/user/entry/view/second; synchronous bounded snapshot reads; user/entry/view/revision-bound opaque cursors; 15-minute token lifetime and original snapshot deadline; 128 KiB page/32 KiB detail limits. |
| `sensor.py` | Four retained sensor suffixes plus connection/assessment and small source-status entities; summaries under 4 KiB; no rich arrays; unknown counts are null. Best-sky stays unavailable. |
| `binary_sensor.py` | Existing action identity/device retained, permanently unavailable with unknown boolean; cannot turn on or emit notifications. |
| `calendar.py` | Existing calendar identity retained, unavailable with no invented appointments: current Core lacks time precision. No geometry/prose/calendar leakage. |
| `policy/core-destinations.json` | Reproducible **candidate** from pinned actual Core definitions/code: source paths/hashes, definition hash/version, destination pair/name, public listing and source-controlled public text. |
| `policy/destination-review.json` | Separate **pending** review, `reviewed:false`; no production location is approved by this implementation. |
| `tools/generate_core_destination_policy.py` | Generates the candidate from a clean exact Core checkout; cannot write or renew independent approval. |
| `tools/verify_v17b_boundaries.py` | Exhaustive local-import audit of all active roots, including imports inside functions, plus retired side-effect/browser assembly checks. |
| `www/src/presentation.js` | Cosmetic constants/escaping only; no science or catalog. |
| `www/src/card.js` | HA summary discovery survives customized entity IDs; authenticated coalesced/rate-bounded read requests; local aging; detach discards pending responses; immediate cache hiding on auth/principal change; preserved host/anchor/focus/scroll. |
| `www/src/core-view.js` | Explicit state/coverage messages, normal rows/details, local presentation filters, More/pages, month bars over supplied ranges, stable dialogs; unavailable choice controls with explanation. |
| `www/src/editor.js` | Title, initial view and optional entry ID; no weather, threshold, source or bearer controls. |
| `www/src/styles.js` | Established appearance retained; duration-bar/dialog styling added. |
| `www/src/header.js`, `register.js` | Read-only development identity and unchanged custom element registration. |
| `www/photography-events-card.js` | Regenerated by the existing assembler from seven sources; never hand-edited. |
| `scripts/card-sources.json` | Removes browser astronomy, scoring, catalogs, timeline and legacy backend adapters from assembly. Sources remain as history. |
| `scripts/check-version.mjs` | Preserves consistency checks and admits explicit `-dev.N` versions. |
| `manifest.json` | Existing third-party requirements unchanged; HA frontend/WebSocket dependencies declared; local polling; development version. |
| `services.yaml` | Retired ingestion/choice interfaces explicitly documented as unavailable, with no scientific or persistence promise. |
| `README.md`, `CORE_DEVELOPMENT.md` | Current main is labelled the Core development build; old architecture/scaffold instructions are historical. |
| `.github/workflows/validate.yml` | Existing checks retained, plus new runtime-test lint and the active-path audit. |
| `tools/render_v17b_card_evidence.mjs` | Produces nine explicitly synthetic normal/failure HTML and JSON examples through the actual bundled card's render methods. |
| `strings.json`, `translations/en.json` | Matching secure connection, reauth/reconfigure, error, inactive-setting and Repair copy. |
| `AGENTS.md`, `VERSION`, `package.json`, `CHANGELOG.md`, `RELEASE_NOTES.md` | Authorized read-only Core milestone and internally consistent development version; historical guidance retained; notification cancellation clarified. |
| `tests/test_v17b_runtime.py`, `v17b_fixtures.py` | Actual production serializer/client/cache tests with synthetic normal M1-shaped identities and separate review witnesses. Fixtures never ship as live data. |
| `tests/test_ha_v17b.py` | Real HA shared-session loopback transport, full configured/dormant platform setup, real registry/Store, supported migration/reauth/reconfigure/Repair/reload/unload, authorization/paging/expiry and negative side-effect tests. |
| `tests/v17b-card.test.mjs`, `card-harness.mjs` | Actual shipped-card rendering, no fallback/writes, status/aging, navigation, focus/scroll, month bars, dialog and config privacy. |
| `tests/legacy_v16/*` and historical test import/path changes | Explicit frozen test-only baseline and unchanged original assertions. See its README; historical successes are reported separately from active-v17 coverage. |

`const.py`, legacy provider/science modules, legacy choices, catalogs and their
stored preferences remain unchanged and disconnected. No new runtime dependency,
provider, Core endpoint, local choice authority or notification feature is added.

## Freshness, state and failure behavior

Named limits: transport 15 minutes from **validated HA fetched_at**; provisional
assessment six hours from **Core data_as_of**; each row at **its valid_until**.
Exactly at a deadline is expired. generated_at/saved_at are provenance only.
New retrieval renews transport only. Cache load, card activity/source health and
HA refresh never renew evidence. One expired row does not expire a valid sibling.
The common expiry excludes individual row deadlines. A repeated material
generation keeps revision, but an earlier immutable page retains its own fetch
deadline even after a newer retrieval.

Connection/auth/compatibility/protocol failure comes first; debug/shadow normal
input is rejected before publication; unsupported view, missing generation,
incomplete/degraded, expiry, unknown coverage, then scoped current/empty follow
the approved order. Availability, Core status, source problems and the independent
clocks remain orthogonal. Contradictory complete/source-failure or actionable/
watching flags cannot authorize action. All notifications remain disabled.

| Input | Normal safe result |
| --- | --- |
| Ready + authenticated current normal list | Online; initially `coverage_unknown`, known normal context held, no assumed whole-week coverage. |
| Valid 30-minute input with recent fetch | Assessment/transport current; synthetic reviewed-scope tests prove current presentation without using generated_at as a fetch clock. |
| Fresh fetch with seven-hour data_as_of | Online `stale`; no evidence renewal. |
| Individual expired row beside a valid row | Expired row held; valid row retains independent validity. |
| 503/timeout/connect failure | Setup retry; after successful setup, validated normal cache becomes `offline_stale`, held, within retention; otherwise unavailable. |
| Missing connection/token after migration | Dormant `connection_required`, same entities/resource, persistent connection Repair. |
| Invalid/revoked token | HA auth failure/reauth; rich cache hidden immediately. |
| Unknown API/schema/engine or malformed JSON/products | Safe incompatible/invalid-response state, no rows, repair guidance; no legacy fallback. |
| Incomplete/degraded with unknown coverage | Core status retained independently of coverage and freshness. |
| Complete empty without scope witness | `coverage_unknown`, unknown available count; never confidently quiet-week copy. |
| Shadow/preview records at normal boundary | Rejected; no debug provenance or private records forwarded. |
| Unapproved/mismatched destination or definition/prose | Withheld location, generic title/explanation, no coordinate pair, drive/region hint, raw prose or travel action. |

The six-hour cap is provisional and must be replaced/constrained by independently
reviewed Core phenomenon freshness semantics before production promotion.

## Migration and lifecycle proof

Real-HA tests migrate versions 1 and 2 with `async_update_entry(version=3)`.
entry_id/unique_id, literal category lists including `[]`, private legacy keys,
options and all six original entity suffixes are preserved. A future major
version is rejected. Migration uses no network, old coordinator or Store edit.

A full disposable HA installation loads eight actual registry-backed entities,
registers the existing card URL, completes configured Core reads against a local
authenticated synthetic Core contract server, reloads and unloads. A separate
legacy missing-connection installation migrates in place; a customized entity ID
and name survive reload. Disabled-state preservation and actual reconfigure/
reauth/Repair updates use the same entry, with no secret prefill or duplicate.
Real HA Store restart keeps original retrieval/assessment stamps; changed token/
URL namespaces cannot load prior context. These tests run on the two CI HA
versions; Windows local tests replace only absent POSIX fchmod and the Windows
incompatible DNS resolver, while using actual aiohttp HTTP and HA session/Store.

## Retired paths proven inactive

Active import audit reaches only `__init__`, const, Core client/bridge/projection,
coordinator, config flow/Repairs, WebSocket and entity platforms. There is no
active import of events, EventState, wildlife, field_reports, email_reports,
verification, routing, astronomy, weather_scoring, weather_hazards, phenomena,
curation, eligibility, signals, conditions, birds, lunar, gear, sunburst, waves,
grunion, streamflow, spectacles or eclipses.

The old coordinator `_sources`, `_build`, `_apply_routing`, all `_fetch_*`
provider methods, ingested-report Store, calibration/catalog initialization,
deferred scrapers and `EventState.changes`/announcements do not exist on the
active coordinator. Active request traces contain only Core readiness, normal
opportunities and source health. No opportunity event is emitted; action never
becomes on; retired ingestion/choice services return explicit unsupported errors
without parsing or persistence. Browser artifacts have no weather call,
buildEvents, source catalog, science function or choice service call.

## Privacy and authorization evidence

Runtime tests inject synthetic token/observer/geometry/centroid metadata into
top-level and nested fields, and sensitive prose into recognized withheld fields.
Serializer, persisted cache, WS page/detail and compact summary outputs exclude
those bytes. Calendar returns no invented/private event. Approved synthetic
exact pairs survive only matching independently pinned definition/destination
provenance; coordinate/hash/review/source/revision drift fails closed. Even
recognized public prose must match the separate reviewed public-text set.

Only active authenticated HA users may read. Non-admin entry access requires
HA read permission for the entry's registered presentation/status entities; no
registry witness fails closed. Cursors cannot cross entry, user, view or revision;
old retrieval deadlines and token expiry apply. User-supplied URL/token/debug
view/unsupported versions/oversized limits are rejected. Details use the same
bounded snapshot, without an upstream request. All choice writes/notifications
are unavailable across UI, service, entity and coordinator boundaries.

## Validation commands and independent-review limits

Run from repository root:

```text
python -m unittest discover -s tests -p 'test_*.py' -q
python -m unittest discover -s tests -p 'test_ha_*.py' -v
node --test
npm run check
python -m pyflakes custom_components/photography_events/*.py tools/*.py
python -m pyflakes tests/test_v17b_runtime.py tests/test_ha_v17b.py tests/v17b_fixtures.py
python tools/verify_v17b_boundaries.py
python tools/verify_v17a_core_fixtures.py --core-source <clean b140147 checkout>
python tools/generate_core_destination_policy.py --core-source <clean b140147 checkout> --output <scratch candidate>
```

On Windows expand pyflakes wildcard file paths before invoking Python. Compare
the scratch candidate byte-for-byte to the shipped candidate; generation never
updates the review. Final counts, exact file list, commits and final-head CI URLs
are in the delivery receipt, avoiding a self-referential SHA in this document.
The coordinator constructor was also checked against the [supported HA 2024.11.3 source](https://github.com/home-assistant/core/blob/2024.11.3/homeassistant/helpers/update_coordinator.py).

The supplied Unraid Core readiness URL was reached and reported ready with
API v1/schema0008/0.1.0-dev. **No authenticated actual-Unraid-to-HA deployment is
claimed.** The real HA transport/install tests use an explicitly synthetic
loopback contract server. A live bearer was not supplied for a real deployment.
The delivery packet contains sanitized synthetic normal/failure render evidence,
clearly labelled as test evidence, not live wildlife.

Remaining unsupported features: reviewed broad/weekly/year/category scope,
live source-commit/policy attestation, production-approved destination/prose
review, calendar precision, Birds and legacy science categories, per-user Core
choices, alternatives/grouping semantics, and all notifications. Current health
does not prove the running Core source SHA. The shipped review is deliberately
pending; no fixture review is copied into production. Independent Claude review
and a separately authorized live isolated deployment are still required before
claiming actual Unraid-to-HA success or production readiness.

## Isolated installation and rollback

1. Create a separate HA test instance/config volume, with no production
   automations or notification integrations. Use HA 2024.11.3 or 2025.3.4 as
   exercised by CI. Take a supported full backup before migrating legacy entries.
2. Copy the tested packet's complete `custom_components/photography_events`
   directory into that isolated instance's `/config/custom_components/` and
   restart the **isolated** HA. Keep the backup outside custom_components. Do
   not install this unreviewed build on the user's running HA.
3. Fresh setup: Settings > Devices & services > Add integration > Photography
   Events. Enter the private Core origin (the supplied test target is
   `http://192.168.1.132:8099`) and bearer through the password selector. Readiness
   and authenticated normal retrieval must both pass.
4. Legacy v1/v2 setup: the same entry migrates to major 3 and remains dormant.
   Open its connection Repair or Reconfigure and enter the private connection.
   Old provider keys/preferences stay stored but inactive. No manual `.storage`
   edit and no old engine start is necessary.
5. Reload the browser after HA restart. Existing card placement/custom element
   and `/photography_events/photography-events-card.js` resource remain. Choose
   the entry in the card editor only if every summary entity was disabled and
   automatic discovery is unavailable. Verify four views, connection/assessment
   stamps, coverage gaps, withheld locations and disabled choices/notifications.
6. Test disconnect, invalid token/reauth, reconfigure, expiry, reload and restart
   in the isolated instance. Confirm no provider requests, opportunity events or
   action-on transitions, and inspect sanitized WS/entity data.
7. Rollback: stop the isolated instance, restore matching pre-upgrade integration
   code **and the supported full pre-migration HA backup**, then restart. Old code
   rejects major-3 entries; reverting code alone is not a supported downgrade.
   Never decrement versions or edit `.storage` by hand, and never reactivate
   legacy intelligence automatically on Core failure.

READY FOR V17B INDEPENDENT CLAUDE REVIEW
