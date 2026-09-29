# Handoff log — current release 0.16.0

## 2026-09-28: main-only development and explicit releases

The user requested publishing all applicable work to main and removing the other branches after their work is preserved. Both existing side-branch heads are ancestors of the final correction commit `81739ae`; no separate feature merge is needed. The full overhaul history remains intact.

Main pushes continue to run Validate. Removed the automatic release trigger after Validate so publishing the development branch respects the user's no-tag/no-release instruction. Explicit version-tag pushes and manual release-workflow runs retain their existing pre-publication checks. Version remains 0.16.0. GitHub publication and branch cleanup must be verified separately; this entry records the workflow change, not a completed push.

## 2026-09-06: card review and date-choice improvements (0.11.0)

Publication base: 5924f8e3068046333e5e9844d1e9bfeb5c92d354 (released 0.10.0).

User requested compact weekly briefs, consolidated locations, preferred/alternate dates with explanations, relevant eclipses, less ordinary-bird noise, trustworthy individual links, scroll preservation, collapsible sections, a calendar, and visible firefall/moonbow plans. Their follow-up explicitly asks to retain the full date range even when the preferred day is inconvenient.

Implemented the changes described in RELEASE_NOTES.md. Existing Open-Meteo cloud-layer scoring remains the backend weather source; the obsolete standalone UI is bypassed when the integration is installed. No new live confirmation source is claimed for wildlife behavior or waterfall phenomena.

Browser verification uses labelled synthetic fixtures, not current reports. Verified row expansion/collapse keeps both page and internal scroll offsets, section collapse works, and duration bars open an accessible native dialog. Automated tests cover calendar clipping/overlap, night consolidation/tradeoffs, week inclusion, integration routing, eclipse visibility, report URL identity, bird curation, cloudy alternatives and payload fairness.

Release preparation and publication status is also recorded in the workspace running log. Update the final validation counts there after checks complete.

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


## 2026-09-07 — 0.12.0 implementation

- Source health now distinguishes failed, stale, waiting and disabled feeds. Individual hotlines have their own status, last-success timestamps and automatic HA Repairs after repeated failures. Affected events show "Data degraded" without changing their evidence level.
- Failed or partial API responses no longer masquerade as successful empty observations. Valid empty reports remain quiet; failed portions retain cached data with its original dates. Recognizable hotline content is required before a scrape counts as successful.
- Forecast/outlook labels now survive the compact sensor payload and appear in night comparisons and location details. The existing opportunity-event path now shares the 48-hour limit; long-range outlooks cannot fire it.
- Follow/Skip is committed to memory only after Store succeeds. Failed saves cannot silently skip an event or consume an unpublished update. Deferred scraper tasks and the parent coordinator shut down cleanly.
- Added separate real Home Assistant contract tests and an executing CI job. The portable suite still runs without HA. Test dependencies do not alter the integration's runtime requirements.
- Split the card into 11 source files with a dependency-free concatenation script. CI checks source/artifact synchronization; installation still uses one JS file.
- Imported 45 NASA eclipses for 2026–2035, including published coordinates for all 16 central solar paths. Corrected TD versus UT labeling. The backend now evaluates lunar umbral-phase visibility and known sites inside central solar paths; the standalone card uses the same catalog. An ocean path point is never treated as a road destination. Partial-only solar visibility, exhaustive road access and exact solar contacts remain outside this model.
- Added published near-peak meteor radiant drift after the 1,920-night audit found a usable-night change and a preferred-night change. Solar-longitude peak calculations and evidence ceilings are preserved.
- Tier 2 cancelled at the user's request: no notification blueprint or phone delivery, hassfest, upstream brand submission, watching filter, score/drive sorting or separate this_week mode.


See BACKLOG.md for cancelled items, remaining API information and the precise eclipse limits. Validation and publication results are recorded after final checks.

### Local validation completed 2026-09-08

209 portable Python tests and 97 JavaScript tests passed. All 22 isolated Home Assistant contracts passed against HA 2024.11.3 (328 executed tests total). The portable run skips those 22 contracts when HA is absent. Pyflakes, source assembly consistency and version checks passed. Browser review of synthetic examples verified compact rows, full ranges, preferred nights, alternate-night tradeoffs, explicit outlook labels and per-source failure details. CI additionally tests HA 2025.3.4; its result and publication record will be kept in the workspace running log. No connection to the user's installed HA instance was used.


## 2026-09-17: readability and reliability (0.14.0)

Base: 4b4062c28be888472dad8e4bb54183b638664f27 (v0.13.2). The user approved the finishing review and emphasized avoiding information overload. Changes are described in RELEASE_NOTES.md; source limitations and real-browser checks are recorded in SOURCE_VALIDATION.md and BROWSER_VALIDATION.md.

Short rows and five-item previews now lead into progressive details; later months and crowded calendar weeks stay compact without removing access to remaining events. Grouped moonbow keys survive changes in preferred night. Local stale/connection handling and updating native dialogs retain sections, focus and scroll. Corrected USGS health dependencies, rare-only weather fetching, OGC v1 parsing, non-finite cloud rejection, individual moonbow condition states and preservation of timed planning-only candidates.

The installed HA version/local URL was requested but not supplied during this implementation. Do not claim a successful upgrade on the user's instance. No phone delivery or cancelled Tier 2 features were added. Remaining source/installation work is accurately listed in BACKLOG.md rather than described as completed.

Validation for 0.14.0: 231 portable Python tests, 25 real HA contract tests and 102 JS tests pass (358 total). Pyflakes is clean; build/artifact and version checks pass. HA tests used the existing isolated HA 2024.11.3 installation; CI additionally covers HA 2025.3.4. Browser checks and their limits are in BROWSER_VALIDATION.md.

Final documentation review corrected the old HACS resource URL, minimum HA version, 30-day horizon, Whale Safe API claim, timeline-mode behavior and eclipse coverage. Removed the obsolete standalone sunset-notification example and conflicting hardcoded meteor-date claim. Documented source assembly and the local freshness timer.


## 2026-09-27: Can't Miss overhaul (0.16.0)

Base: 522023d (0.15.0). The user asked for a regret-prevention system instead of an encyclopedia: a narrow default dashboard, broad collection behind it, and SIGNAL → PHENOMENON → OPPORTUNITY as distinct concepts. DISCOVERY_AUDIT.md was written and committed first (3d32adc), then the refactor.

Implemented (see RELEASE_NOTES.md for the user-facing summary):
- `signals.py`, `curation.py`, `eligibility.py`: raw evidence, curated phenomena with significance/policy/product class and a written reason, and a hard gate before ranking. Assessments carry separate significance, confidence, urgency, encounter, access and condition quality.
- `sensor.photography_events_can_t_miss`; action binary sensor requires an eligible occurrence. `_build` still returns a list (a real-HA contract); signals and bird views are left on the coordinator.
- Reports merge into phenomena by fixed vocabulary; hotline and email dates come only from the text. This fixed a pre-existing gap: ingested emails and scraped hotlines could never corroborate anything in production.
- `calendar_reliable` evidence for sourced annual cycles; static windows activate only on a dated behaviour report.
- `birds.py`, `lunar.py`, `sunburst.py`, `weather_hazards.py`, `gear.py` (see CHANGELOG).
- Card: Can't Miss view, `birds` mode, planner "Can't miss" badge, new synthetic fixture.

Validation: 288 portable Python tests; 27 real Home Assistant contract tests against HA 2024.11.3 in a local venv (Python 3.12); 112 JavaScript tests; pyflakes clean; card build and version checks pass. Browser checks in BROWSER_VALIDATION.md. Real HA caught one regression during the work (the `_build` return contract) which was fixed before commit.

Not verified: no live network access to any data host from this container (all returned blocked), so SunsetWx, the eBird species endpoint and the all-California NWS alert shape were written against documentation and published client libraries, not a live response. The user's installed Home Assistant was not available. See BACKLOG.md for remaining work.


## 2026-09-27: 0.16.0 hardening pass (same version; never tagged)

The user supplied a 15-item correction brief (trust over coverage: "watch it, plan for it, or show nothing"). Version kept at 0.16.0 because tags stop at v0.15.0 and `main` is still 0.15.0. No Phase 2 work (Docker, databases, moving collection out of HA) was started; the new logic is in pure modules (`conditions.py`, `source_health.py`, `weather_hazards.py`, `eligibility.py`, `gear.py`, `lunar.py`, `birds.py`).

Implemented: source roles (required/preferred/optional) with visible fallback; NWS safe/caution/unsafe/unknown by exposure with held travel rows; fresh snow = dated report + current clearing forecast; moonbow supported-candidate vs viewpoint-validated; firefall evening conditions; per-phenomenon evidence freshness; orca spatial clustering and operator reports; monarch dawn at the grove; King Tide published-date rows with NOAA enrichment; grunion nearest-station fix; bird views from the shared classification with drive limits; gear worth-adding and required lists; solar-eclipse profiles; planner Moon geometry and gear. Details: CHANGELOG.md and RELEASE_NOTES.md.

Bugs found beyond the brief and fixed: the Can't Miss sensor did not publish `held`; solar eclipses used the lunar gear profile; several lunar fields (including `sunset`) never reached the payload; numeric fractions ("1/2 mile") could become report dates; tides were fetched only when rare phenomena were enabled.

Validation: 394 Python tests including 28 real Home Assistant contracts (HA 2024.11.3, Python 3.12 venv; the portable run skips those 28), 115 JavaScript tests, pyflakes clean, card build and version checks pass, TRACKING.md regenerated. Browser checks in BROWSER_VALIDATION.md.

Still not live-verified from this container: SunsetWx login/quality, the eBird species endpoint, the statewide NWS alert payload, Friends of the Elephant Seal's current page, Condor Express orca wording. The user's Home Assistant instance was not used.


## 2026-09-28: 0.16.0 correction pass after independent review (same version; never tagged)

Base 9671efc. An independent (Codex) review listed 6 critical, 11 high, 6 medium and 1 low finding. The review document itself was not in the repository; the work followed the finding list supplied by the user. Each finding was reproduced against 9671efc before it was changed. `main` is still 0.15.0; nothing was tagged, released or merged, and no Phase 2 work was started.

Architecture changes (see CHANGELOG.md for the per-finding list):
- `observations.py`: statement-level report normalization and one admissibility gate for every report ingress path. Context (place, date) is borrowed only from a subject line, an explicit automation zone or a short header statement.
- Safety: land and marine components; boat phenomena are held until marine zones are connected. NWS collections are validated per feature; incomplete checks cannot conclude safe.
- Park access as a phenomenon/place dependency with paginated, `total`-validated NPS reads.
- Assessment coverage on the Can't Miss sensor and card; per-point weather health.
- Source inputs resolved before scoring (SunsetWx model time, air quality health, provider-only sunsets).
- Raw orca observations with complete-linkage clusters; bird evidence keeps its own timestamps and site; bounded live occurrences outside seasonal windows for behaviour-driven phenomena.
- Aging routing cache with `drive_basis`; explicit `time_precision`; year-crossing occurrences; suppression before representative; qualify-then-rank events; literal categories with a version 2 config migration; explicit secret clearing.

Additional bugs found: NPS "Park Closure" never matched the blocking categories; the Condor megapod report carried no count; a failed alert fetch was treated as never fetched; an unrecognised place name let a statement borrow another sentence's place; sunset scoring called one missing upstream layer "modelled"; `wildlife.cluster` shared list objects with cached records; the CI job ran only `test_ha_integration.py`.

Validation (local): 441 portable Python tests; 52 Home Assistant tests (28 contracts + 24 new pipeline tests) against HA 2024.11.3 in a Python 3.12 venv - 493 Python in total; 117 JavaScript tests; pyflakes clean; card build/check and version checks pass; TRACKING.md regenerated. Browser checks in BROWSER_VALIDATION.md.

Still not live-verified: SunsetWx login/current quality and `last_updated`; eBird species responses; the statewide NWS payload; Friends of the Elephant Seal; Condor Express real wording; real Open-Meteo bundles; NPS pagination/access; current CDFW parsing; NOAA station/timezone enrichment. The user's Home Assistant instance was not used.

## 2026-09-28: 0.16.0 residual pass after the second independent review (same version; never tagged)

Base f3a6561. The second review (uploaded by the user, not in the repository) rated 13 findings verified fixed and 11 partial, with residuals R1-R11, and returned the work. Each residual was reproduced first. `main` is still 0.15.0; nothing was tagged, released, merged or opened as a PR, and no Phase 2 work was started.

- R1 NPS records validated one by one; distinct ids must equal `total`.
- R2 NWS geography must be something `alerts_at` can place.
- R3 behaviour/count bound to their own animal; conservative header rule; multi-place context unplaced.
- R4 hotline reports built per normalized observation.
- R5 unassessed condition inputs hold the row and make coverage incomplete; per-event sunset coverage (provider covers only what it predicts).
- R6 forecast parts tracked as `zone`, `zone:sunset`, `zone:sunrise`.
- R7 explicit zones keep the observed point; region-only glowing surf is not a destination.
- R8 operator orca backing within the 25 km diameter; operator point in contributions.
- R9 drive basis and route age on the card; an old route alone cannot clear a trip the estimate puts over the limit.
- R10 the version 1 to 2 migration no longer rewrites saved categories (release notes tell pre-Waves users to switch Waves on once).
- R11 snow policy, README notification text, BACKLOG and release-note completion claims reconciled.

Validation (local): 457 portable Python tests (66 HA tests skipped without HA); HA contracts and pipeline suites run against HA 2024.11.3 in a Python 3.12 venv; 118 JavaScript tests; pyflakes clean; card build/check, version checks and `git diff --check` pass; TRACKING.md regenerated. Browser checks in BROWSER_VALIDATION.md.

Still not live-verified: unchanged from the previous entry (SunsetWx, eBird species, statewide NWS payload, Friends of the Elephant Seal, Condor Express wording, real Open-Meteo bundles, NPS pagination/access, CDFW parsing, NOAA enrichment, Google routing). The user's Home Assistant instance was not used.

## 2026-09-28: implementation of the final four residual classes

Base `bfac765cd7c2495a9570c28fab708e87e8b2ed78`, branch `claude/photography-events-overhaul-tyxuv9`. Scope is R1, R2, R3 and R5 plus their tests and documentation. Version stays 0.16.0 unreleased. No PR, merge, tag, release or Phase 2 work. This is an implementation handoff for Claude's independent verification, not a release verdict.

- R1: NPS records now need a requested/resolvable park and recognized category, in addition to nonempty string id/title and complete, unique pagination. Unknown semantics cannot establish open access. `SemanticAlerts` and `FinalResidualPipeline` cover the exact unknown-category/broken-park reproductions, malformed ids, requested-park scope, and empty/information/caution/closure/danger controls through the real HTTP coordinator and final board.
- R2: reject Boolean/non-numeric coordinates, unclosed or zero-area rings, insufficient distinct vertices and unsupported/impossible SAME codes. Valid county/polygon warnings still block; a mixed valid/invalid collection remains incomplete and retains readable warnings. Portable matrices and real HA cycles include all-equal points, collinear points, 106079/906079 subdivisions, impossible counties and malformed finite coordinates.
- R3: replace nearest-animal attachment with conservative assertion binding. Counts and place/date belong to that assertion; only genuine headers lend context. Distinct precise headers, content from another animal, cancelled/planned reports and conflicting dates cannot manufacture an observation. Tests include both animal orders, unlisted squirrels, cross-assertion place/date borrowing, precise-place conflicts and simple positive controls. Real HA cycles exercise humpbacks and one-condor-plus-raven reports. Existing colony-pup and explicit continuing-date examples still pass.
- R5: shared strict forecast chronology rejects duplicate, invalid and reversed timestamps. Samples must cover the actual event with no missing hourly interval. Near-term meteor/Milky Way/full-Moon missing cloud is unassessed; long-range planning remains independent of the operational horizon. A negative snow-clearing conclusion requires full future hourly coverage. Actual HA tests include duplicate snow hours, old axes, gaps, short horizons, favorable/unfavorable controls, a near-term closest full Moon and future planner rows.

Additional production bug found within R5: favorable Moon/radiant geometry could leave a meteor score above its threshold under 100% cloud. The gate now also applies the existing 25% astronomy cloud limit. No unrelated production change was made. A cleanup leak in the new composed HA fixture was found and fixed during validation; existing startup code/tests are unchanged.

Existing tests changed in `test_codex_review.py`: the unnamed lunge-feeding sentence followed by a negated humpback sentence now expects no confirmation (the old expectation borrowed its subject); the payload-size test's 60 intended eligible meteor fixtures now include valid cloud, retaining its 60-row assertion. No other existing test expectation changed. New tests were reproduced against the base before the fixes, then expanded with neighboring cases.

Validation: 553 Python tests passed in Python 3.12.14 with HA 2024.11.3: 470 portable plus 83 HA (28 contracts, 38 existing pipeline, 17 new pipeline methods). The new portable module adds 13 methods. All 118 JavaScript tests pass; pyflakes on integration/tools and both new test files is clean; card build, build --check, syntax, version 0.16.0 and git diff --check pass. Browser fixture: 21 checks, three viewports, no overflow or console errors (see BROWSER_VALIDATION.md). The second HA version in CI was not run locally. TRACKING inputs did not change.

Third-review scripts were replayed, preserving the original captures. The four residual classes now reject their adversarial evidence; the 31 earlier HA probe groups, 13 broader groups and four final hotline/operator/provider/saved-CDFW groups retain their prior outputs. No previously verified residual regression was found, including R4/R6/R7/R8/R9/R10/R11. These are local synthetic/stored-response results, not fresh live-provider validation.

Judgment calls: unsupported SAME subdivisions make coverage incomplete rather than being approximated; ambiguous report grammar favors false negatives; explicit "last night and today" is a continuing observation today. Invalid/duplicate/out-of-order axes are rejected rather than repaired. A valid exact future clear hour can qualify snow before the entire 48-hour search is available, but saying there is no clearing requires the full interval. One missing event sample within the seven-day decision horizon marks that condition unassessed.

Live sources still unverified: SunsetWx, eBird species, statewide NWS feed, Friends of the Elephant Seal, Condor Express wording, real Open-Meteo bundles, NPS pagination, CDFW, NOAA enrichment and Google routing. The user's Home Assistant instance was not used.
