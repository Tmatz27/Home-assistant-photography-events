# Photography Events V17A acceptance packet

This is the bounded Core-first architecture/contract/migration gate. Both remote
main heads matched the supplied starting commits on 2026-10-09:

- HA: `c76726ece1e485ece03810087927da344289fba7`
- Core: `b14014760beee2c18d02a2b1f36756f6faee93a0`, API v1, schema 0008

| Acceptance item | Review artifact |
| --- | --- |
| 1. Verified dependency inventory | [DEPENDENCIES.md](DEPENDENCIES.md), exact imports and existing tests; [CONTRACT.md](CONTRACT.md), verified provider call paths and side effects. |
| 2. Keep/replace/remove matrix | [V17B_PLAN.md](V17B_PLAN.md), per-file retention and deletion gates. |
| 3. Exact Core-to-HA contract | [CORE_FIELDS.md](CORE_FIELDS.md) and [CONTRACT.md](CONTRACT.md), actual endpoint models/field classes and compatibility. |
| 4. HA-to-Lovelace contract | [CONTRACT.md](CONTRACT.md), proposed versioned authenticated HA projection, bounds and view states. |
| 5. Missing Core ledger | [CONTRACT.md](CONTRACT.md), production scope vs shadow calibration and missing presentation/persistence contracts. |
| 6. Config-entry migration | [MIGRATION_PRIVACY.md](MIGRATION_PRIVACY.md), version 1/2, proposed version 3, reconnect/reauth, registry/resources and rollback. |
| 7. Choices and identity | [MIGRATION_PRIVACY.md](MIGRATION_PRIVACY.md), Core authority, per-user scope, idempotency and ambiguous legacy mappings. |
| 8. Security/privacy | [MIGRATION_PRIVACY.md](MIGRATION_PRIVACY.md), typed allowlist and approved/withheld location boundary. |
| 9. Fixtures/results | [fixture README](../../tests/fixtures/v17a/README.md), `tests/test_v17a_contract.py`, test-only model and [RESULTS.md](RESULTS.md). |
| 10. V17B sequence | [V17B_PLAN.md](V17B_PLAN.md), exact implementation order, validation and no-fallback rule. |
| 11. Modified files/commit | [RESULTS.md](RESULTS.md); this packet's commit is `git log -1 --format=%H -- docs/v17a/README.md`. External delivery receipt records its full SHA (avoids embedding a self-referential SHA in the commit). |
| 12. Remaining risks/blockers | [RESULTS.md](RESULTS.md) and missing-feature ledger. |

Pinned source evidence:
[HA coordinator](https://github.com/Tmatz27/Home-assistant-photography-events/blob/c76726ece1e485ece03810087927da344289fba7/custom_components/photography_events/coordinator.py),
[HA Core client](https://github.com/Tmatz27/Home-assistant-photography-events/blob/c76726ece1e485ece03810087927da344289fba7/custom_components/photography_events/core_client.py),
[Core API](https://github.com/Tmatz27/photography-events-core/blob/b14014760beee2c18d02a2b1f36756f6faee93a0/src/pec/api.py),
[Core public schemas](https://github.com/Tmatz27/photography-events-core/blob/b14014760beee2c18d02a2b1f36756f6faee93a0/src/pec/schemas.py),
[Core database envelope](https://github.com/Tmatz27/photography-events-core/blob/b14014760beee2c18d02a2b1f36756f6faee93a0/src/pec/database.py),
[Core debug pattern boundary](https://github.com/Tmatz27/photography-events-core/blob/b14014760beee2c18d02a2b1f36756f6faee93a0/src/pec/patterns/api.py).

Independent review should challenge four gates first: an empty list is not proof
of category coverage; debug calibration never promotes; current scaffold needs
additional sanitization/freshness checks; migrating users keep the same entry and
entity identity without reviving the old engine. This packet is not a deployed
v17 integration or approval of full Core product breadth.

READY FOR V17A INDEPENDENT CLAUDE REVIEW
