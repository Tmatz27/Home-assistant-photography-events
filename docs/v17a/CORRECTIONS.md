# V17A independent-review corrections

Starting main and origin/main were verified clean at
`c15abcbf022b2607f4e6926cbfe329e18e26492a`. Core reference remains
`b14014760beee2c18d02a2b1f36756f6faee93a0` (v1/schema 0008), unmodified.
The accepted V17A design is corrected here; V17B is not started. No production
integration files, versions, workflows, notification behavior or database change.

## Five corrections

1. Independent clocks: transport expires at fetched_at + 15 minutes; provisional
   assessment expires at envelope data_as_of + six hours; rows expire at their
   own valid_until. Core generated_at and cache saved_at are provenance only.
   Constants name the policies. A validated fetch can renew transport only;
   cache/UI/source-health activity cannot renew assessment or row validity.
2. Online stale is stale. offline_stale requires an unavailable connection and
   previously validated normal cached context. No usable cache or nonrecoverable
   connection state is unavailable. All expired/unsupported/shadow contexts are
   held/nonactionable; notifications remain disabled in all cases.
3. Precedence matches CONTRACT.md: connection failures, shadow origin,
   unsupported scope, missing generation, incomplete/degraded, expiry, unverified
   coverage, then current/empty_assessed. Coverage, Core status/source problems,
   error codes and transport/assessment/row freshness stay orthogonal. Missing
   generation does not erase Core's incomplete status.
4. AGENTS.md now identifies v0.16.1 as frozen historical intelligence guidance
   and v0.17 as the same-repository Core-first rebuild. Privacy/truthfulness,
   accessibility, identity, appearance and focus/scroll invariants still govern
   the frontend. Historical backend parity and silent fallback are prohibited;
   settled/cancelled features are preserved, including disabled notifications.
5. Core owns curated destination approval. The former test-only PUBLIC dictionary
   becomes a synthetic Core-derived artifact plus a separate review pin. Canonical
   digest, source/revision checks and per-product definition provenance prevent
   silent drift. HA cannot authorize new sites merely from curated_public_site.
   V17B artifact generation and live policy validation are designs, not implemented
   here; no new Core API exists.

## Focused evidence

All original **28 test methods remain**; corrected expectations remove the
reviewed stale/offline bug, with additional assertions. **18 new methods** bring
the focused suite to **46 passing** tests. No legacy test file/assertion changed.

| Required scenario | Test evidence |
| --- | --- |
| 30-minute-old assessment/row, recent fetch, verified scope | `test_thirty_minute_assessment_and_row_remain_current_after_recent_fetch`: current presentation and actionable synthetic row; notifications false. |
| Exactly 15 minutes from actual HA fetch | `test_transport_boundary_uses_actual_fetch_not_generated_or_saved_time`: 1 microsecond before/current, exactly/stale, 1 microsecond after/stale; old generated_at/new saved_at cannot change it. |
| Exactly six hours from data_as_of | `test_assessment_boundary_is_exactly_six_hours_with_fresh_transport`: before/current, exactly/stale, after/stale, transport still current. |
| Fresh HTTP, seven-hour assessment | `test_fresh_http_seven_hour_assessment_is_online_stale`: online + stale, no offline connection error, held. |
| Expired row cannot be renewed by fetch | `test_row_deadline_boundary_is_independent_of_a_new_fetch`: fresh transport/current assessment at all samples; only valid_until determines row expiry at the exact instant. |
| One expired row, one valid sibling | `test_one_expired_row_does_not_expire_valid_sibling`: first stale/held, sibling current/actionable, board current. |
| Offline cached vs no usable cache | `test_offline_cache_cannot_act`, `test_offline_without_validated_cache_is_unavailable`, `test_shadow_diagnostics_cannot_supply_normal_offline_cache`. |
| Incomplete with unknown coverage/expired input | `test_incomplete_unknown_coverage_preserves_all_orthogonal_problems`: incomplete state, unverified coverage, stale assessment, current transport and required-source problem preserved. |
| Missing generation vs unverified coverage | `test_missing_generation_is_distinct_from_missing_coverage`: not_assessed vs coverage_unknown; no zero-count success. |
| Ordered competing states | `test_precedence_matches_contract_including_competing_states`, `test_connection_failures_hide_rich_data_before_scope_and_shadow`: table-driven assertions, no notification enablement. |
| Empty assessment scope and age | `test_empty_assessment_requires_scope_and_its_own_freshness`, `test_empty_without_coverage_witness_is_unknown`. |
| Fetch/cache timestamp separation | `test_fetch_renews_only_transport_and_cache_reload_cannot_renew_assessment`, `test_missing_fetch_time_cannot_be_inferred_from_generated_or_cache_time`; input and evidence timestamps unchanged. |
| Destination source/review/definition drift | `test_destination_registry_requires_independent_review_and_provenance`, `test_destination_authority_revision_commit_and_content_drift_fail_closed`, `test_core_definition_drift_cannot_reuse_an_approved_destination`; withheld, no hints/coordinates/action. |
| Meaningful annual occurrence boundaries | Strengthened `test_annual_recurrence_has_separate_identity`: same winter window crossing New Year keeps identity through a new generation; next annual nonoverlapping window has a distinct Core key, so a prior-season skip cannot match it. |

The test-only model accepts trusted backend witnesses (fetch stamp, validated
cache, coverage and independent policy review). It is not an authenticated HA
transport or a production intelligence implementation. The policy fixtures
explicitly say synthetic and are separate from the **11 unchanged actual Core
DTO-shaped fixtures**.

## Checks and commands

- Full Python/real-HA suite: `python -m unittest discover -s tests -p 'test_*.py' -q`:
  621 passed, no skips/failures/errors, 341.803 seconds (Python 3.12.14,
  HA 2024.11.3, aiohttp 3.10.11, beautifulsoup4 4.15.0). Final focused assertions
  were rerun after the small orthogonal-status metadata amendment.
- Final focused suite: `python -m unittest discover -s tests -p 'test_v17a_contract.py' -q`: 46 passed.
- Existing frontend: `node --test tests/photography-events-card.test.mjs`: 127 passed.
- `node scripts/build-card.mjs --check`, JavaScript `node --check`, and
  `node scripts/check-version.mjs`: passed; version remains 0.16.1.
- Pyflakes over integration files, tools and the two changed test modules: passed.
- `python tools/verify_v17a_core_fixtures.py --core-source <b140147 checkout>`:
  all 11 upstream DTO fixtures passed against actual Core Pydantic models.
- Diff/scope review: no production changes; original 28 test names preserved.

The original V17A [Validate CI run](https://github.com/Tmatz27/Home-assistant-photography-events/actions/runs/38030610408)
was independently confirmed successful. The final correction SHA, full-suite
counts and new CI URL/result are recorded in the delivery receipt after that
commit is pushed and CI completes; do not mistake the original run for corrected
CI. The unchanged workflow includes real HA 2024.11.3/Python 3.12 and
2025.3.4/Python 3.13, HACS and portable/frontend checks.

## Exact changed file list

- `AGENTS.md`
- `docs/v17a/CONTRACT.md`
- `docs/v17a/MIGRATION_PRIVACY.md`
- `docs/v17a/V17B_PLAN.md`
- `docs/v17a/README.md`
- `docs/v17a/CORRECTIONS.md` (new)
- `tests/fixtures/v17a/README.md`
- `tests/fixtures/v17a/policy/core-destinations.json` (new)
- `tests/fixtures/v17a/policy/destination-review.json` (new)
- `tests/test_v17a_contract.py`
- `tests/v17a_contract_model.py`

## Remaining limitations

The six-hour assessment cap is provisional development policy and must be
replaced or constrained by reviewed Core assessment/phenomenon semantics before
production promotion. Current v1 lacks scope/horizon/envelope-validity and live
destination-policy/source-commit metadata. Source-controlled artifact provenance
and product hash binding are defense in depth, not a new authority for HA.
Synthetic review pins are not an actual generated Core allowlist or destination
API. V17B still needs runtime serializer/cache/auth/WS/migration/registry tests;
no live provider, Unraid, choice persistence or notification promotion is claimed.

READY FOR V17A CORRECTION INDEPENDENT VERIFICATION
