# V17A verification and remaining gates

Audit completed 2026-10-09 (America/Los_Angeles). Supplied and remote starting
heads matched: HA c76726ece1e485ece03810087927da344289fba7; Core
b14014760beee2c18d02a2b1f36756f6faee93a0, API v1, schema 0008.
HA checkout was clean main before work. No Core source or database was modified.

## Tests actually run

| Check | Result / environment |
| --- | --- |
| Existing complete Python suite, `python -m unittest discover -s tests -p 'test_*.py' -q`, collected before new tests were added | **575 passed**, no skips/failures/errors; 442.058 s. Existing development environment: Python 3.12.14, Home Assistant 2024.11.3, aiohttp 3.10.11, beautifulsoup4 4.15.0. External I/O is faked by existing tests; real HA Store/registry/platform tests ran. |
| New final focused suite, `python -m unittest discover -s tests -p 'test_v17a_contract.py' -q` | **28 passed**, 0.248 s in the same HA development environment. Existing client parses normal fixtures; adversarial tests exercise test-only contract model, not a deployed serializer. |
| Actual upstream schema validation, `python tools/verify_v17a_core_fixtures.py --core-source <read-only-Core-checkout>` | **11 fixtures passed** against actual b140147 OpportunityList, PatternResponse and SourceHealthList model definitions; bundled Python 3.12.14 / Pydantic 2.13.5, matching Core lock. Deliberate API v2 is structurally a Version string; HA compatibility tests reject it. No Core API/SQL/DB access. |
| Existing frontend, `node --test tests/photography-events-card.test.mjs` | **127 passed**, no failures/skips. Existing behavior unchanged. |
| `node scripts/build-card.mjs --check` | Pass: generated card matches all 12 source files. |
| `node scripts/check-version.mjs` | Pass: all versions remain 0.16.1. |
| `node --check custom_components/photography_events/www/photography-events-card.js` | Pass. |
| `python -m pyflakes tests/test_v17a_contract.py tests/v17a_contract_model.py tools/verify_v17a_core_fixtures.py` | Pass. |
| Repository pyflakes gate over all integration Python files and tools | Pass (PowerShell-expanded file list; literal wildcard arguments were corrected). |
| Staged `git diff --check` and scope review | Pass; only new docs, fixtures, test model/test suite and development verification tool. No modifications under custom_components, VERSION, package.json or workflows. |

The initial bundled-Python full-suite attempt lacked aiohttp/beautifulsoup4 and
failed (563 collected, 89 HA skips). This was an environment failure, resolved
by using the existing fully installed HA development environment; no assertion
was changed. A first schema-check attempt in that HA environment lacked Pydantic;
the matching bundled Core Pydantic environment completed the check. One new lint
warning was fixed before final validation. These preliminary attempts are not
reported as product regressions or hidden as successful runs.

Not run: local HA 2025.3.4/Python 3.13 matrix, HACS remote validation, live-browser
screenshots, actual v17 authenticated WebSocket/migration/transport tests, Core
database suite, Unraid/live provider acceptance. Runtime/UI were unchanged;
Core database tests were intentionally not executed against any live database.
The existing CI matrix is unchanged and will validate the committed main state
when pushed. V17B gates in V17B_PLAN.md remain mandatory before runtime rollout.

## Modified file list

All files below are additions; no existing runtime/test assertions changed:

- `docs/v17a/README.md`
- `docs/v17a/DEPENDENCIES.md`
- `docs/v17a/CORE_FIELDS.md`
- `docs/v17a/CONTRACT.md`
- `docs/v17a/MIGRATION_PRIVACY.md`
- `docs/v17a/V17B_PLAN.md`
- `docs/v17a/RESULTS.md`
- `tests/test_v17a_contract.py`
- `tests/v17a_contract_model.py`
- `tools/verify_v17a_core_fixtures.py`
- `tests/fixtures/v17a/README.md`
- `tests/fixtures/v17a/approved_public.json`
- `tests/fixtures/v17a/complete_empty.json`
- `tests/fixtures/v17a/degraded.json`
- `tests/fixtures/v17a/incompatible.json`
- `tests/fixtures/v17a/incomplete.json`
- `tests/fixtures/v17a/never_assessed.json`
- `tests/fixtures/v17a/shadow_patterns.json`
- `tests/fixtures/v17a/source_health.json`
- `tests/fixtures/v17a/stale.json`
- `tests/fixtures/v17a/unknown_safety_access.json`
- `tests/fixtures/v17a/withheld.json`

The delivery receipt outside the commit records its exact commit SHA. Reproduce
with `git log -1 --format=%H -- docs/v17a/RESULTS.md`. No branch, tag, release,
version bump, production notifications or installation change is part of V17A.

## Remaining risks and blockers

1. Core normal products have no per-category/phenomenon coverage/horizon or
   envelope valid_until. Complete empty is not proof of a successfully assessed
   whole week or Birds. Initial V17B must explicitly show coverage_unknown.
2. Normal evaluator scope is Tule elk M1. Live M3A and M2 patterns remain shadow;
   public-source health does not fill the missing production categories.
3. Current HA Core scaffold requires stricter nested serialization, approved
   destination checking, successful-response freshness, preserved assessment ID
   and reviewed schema compatibility before exposure. It remains developer-only.
4. Core user-choice API/principals/instance identity and idempotency are missing.
   Initial V17B choices remain visibly unavailable; no silent legacy transfer.
5. Legacy entity IDs can be preserved, but attributes and available categories
   change. Existing user notification automations must be prevented from acting
   on unknown/stale/shadow data. Initial V17B emits no actionable events.
6. Major config-entry migration/reconfigure/reauth/Repair and registry retention
   are designs, not implemented or tested runtime code. Current HA developer
   docs may use newer helpers than the repository's supported HA matrix; V17B
   must verify APIs in both supported versions and use a compatible Repair flow.
7. Synthetic negative leakage tests prove the proposed boundary examples, not
   end-to-end deployed privacy. Free-form approved product prose and occurrence
   identities still require Core's reviewed public-data guarantees. V17B must
   apply leak tests to actual WS, cache, entities, calendar and diagnostics.
8. No live Unraid readiness/assessment, provider validation or science-policy
   approval is claimed. Independent review should decide the contract gate
   separately from implementation/notification eligibility.

READY FOR V17A INDEPENDENT CLAUDE REVIEW
