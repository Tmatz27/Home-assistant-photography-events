# Batch 2A compatibility and beta candidate

Prepared HA version: `0.17.0-dev.4`. Starting main/origin:
`a958ab2e3e0e1ec44f4d246b3471bd0d1faaac73`.
Paired proposed Core prerelease: `v0.1.0-rc.3` (not published).
Core Batch 2A accepted freeze: `10bde5f0dcb57821f36a971af9e3dc4183271202`,
with user-supplied independent Claude PASS. Exact candidate SHAs and CI receipts
are recorded in the final deployment-review handoff after validation.

This is preparation for review. No release, tag, draft release, GHCR image,
installed HA or Unraid/database operation is performed by this change.

## Explicit compatibility review

Core's `src/pec/schemas.py` is byte-identical at reviewed schema 0008 source
`b14014760beee2c18d02a2b1f36756f6faee93a0`, deployed 0009 rc.2 source
`1b59779831e96bbff32e8a4547a4f0d577fdb537`, and accepted 0010 source `10bde5f`.
Migration 0010 adds environmental history and a native freshness column/view;
it does not expand normal Health, OpportunityList, Opportunity or SourceHealthList
models. The API adds authenticated ingestion debug routes that HA never requests.
No provider record, forecast or M2 shadow result becomes a normal HA product.

Both `core_client.validate_version` and `projection.validate_envelope` retain
the exact API `v1` and engine `0.1.0-dev` guards and share only the explicit tuple
`("0008", "0009", "0010")`. Unknown, malformed or future values (including 0011)
fail closed at readiness, opportunities, source health and cache admission.
Normal row identity, type, enum, dates, size, clock, provenance and source-text
redaction checks are unchanged. Authentication, redirect refusal, URL origin
binding, bounded HTTP and read-only GET-only behavior remain intact.

Destination authority remains separately pinned to the original schema 0008
artifact/source/definition hashes. Wire support for 0010 does not approve a new
artifact, destination, product identity or public coordinates. Pending locations
remain withheld; stale/held/incomplete states keep their existing meaning.
`ha.v17.1` and config-entry version 3 remain. No engine, source fusion, provider
collection, notification or legacy opportunity event is restored in HA.

`tests/fixtures/core-schema0010.json` contains actual pinned FastAPI ASGI route
responses using Core's upstream FakeDatabase and explicitly synthetic M1 test
input. Five normal/empty/incomplete route responses and four bearer-rejection
checks are independently reproducible with `tools/verify_core_schema0010.py`.
No PostgreSQL, lifespan, providers or installed service is used for that capture.
HA CI checks out the exact accepted Core commit and verifies source hashes,
unchanged public models and exact responses. Core's separate CI exercises real
PostgreSQL 18/PostGIS 3.6 migration and persistence.

Regression coverage includes all three explicit schemas, both validators,
per-endpoint future rejection, new/unreviewed identities and debug rejection,
privacy/source redaction, sequential 0008→0009→0010 reconnect, cache restart with
original clocks, no cache reuse after version failure, and real HA setup and
coordinator behavior across the supported HA test matrix. Old unsupported-0010
negative tests now use unsupported 0011; their assertions remain in force.

## Proposed publication and operator order, after explicit approval only

1. Review the paired commits, full CI and migration receipts; preserve verified
   HA/config/Store and Core 0009 data/configuration backups.
2. Publish `v0.17.0-dev.4` as a GitHub prerelease and install that beta through
   HACS. Restart HA and refresh the dashboard. The existing Core 0009 connection
   must still work with the same origin/token/entry/entity identity.
3. Publish Core `v0.1.0-rc.3` at the reviewed exact commit. Its release workflow
   validates before GHCR publication and verifies real anonymous pulls. The
   prerelease updates `preview`, never stable `latest`.
4. In the existing Unraid Compose Manager Photography Events stack, retain all
   secrets, paths, networks and health settings; keep `CORE_SOURCE_KEYS=all`,
   `CORE_PATTERNS_MODE=shadow`, `CORE_SOURCE_HISTORY=true` and the configured
   `CORE_COLLECTION_SCOPE_JSON`. Use the approved preview channel or exact
   published version. Select **Pull & Up**, then wait for **healthy**.
5. The operator verifies schema 0010 readiness, retained data/roles/revisions,
   current and historical polling progress, per-station freshness, and HA's
   read-only status/privacy. No opportunity promotion or notifications are enabled.

The HA release workflow is still explicit tag/manual invocation only. Its new
tested argument policy marks development versions as prereleases and passes
`--latest=false`. Preparing this branch or pushing main cannot publish it.
Do not create/push a release tag or run either publishing workflow during review.

Core schema 0010 is forward-only. An older 0009 image cannot safely use the
upgraded database. Recovery requires the matching verified pre-upgrade backup
and image/configuration; preserve upgraded data first. See the paired Core
`docs/BATCH_2A_DEPLOYMENT_CANDIDATE.md` for full stack and rollback instructions.

NPS remains credential-pending by user choice. Full backfill and installed
verification are separate from disposable test success. Batch 2B resumes only
once the reviewed, explicitly approved deployment is ready; preserve all 81
source entries and ongoing historical collection.
