# Core schema compatibility: 0.17.0-dev.4

Current explicit support is Core API v1, engine 0.1.0-dev and schemas
0008/0009/0010. See [the Batch 2A compatibility review](BATCH_2A_DEPLOYMENT.md)
for accepted-source hashes, pinned route verification, regression coverage and
the unpublished candidate pair. Destination approval remains separately pinned.

## Historical 0.17.0-dev.3 verification record

Starting HA main: `95a746cbcc3c97b95dd05774481cc13fad2c6955`.
Core API remains `v1`, engine `0.1.0-dev`. Only schema strings `0008` and
`0009` are accepted. There is no numeric range, automatic future acceptance or
disabled version check. The existing `ha.v17.1` presentation contract remains.

## Actual Core verification

The deployed rc.2 source is pinned to Core tag `v0.1.0-rc.2`, commit
[`1b59779831e96bbff32e8a4547a4f0d577fdb537`](https://github.com/Tmatz27/photography-events-core/tree/1b59779831e96bbff32e8a4547a4f0d577fdb537).
Its `src/pec/__init__.py` reports schema `0009`. The public `schemas.py` is
byte-identical to reviewed schema 0008 source `b14014760beee2c18d02a2b1f36756f6faee93a0`.
Migration 0009 adds collector leases/checkpoints and source-reference barriers;
it does not change the normal Health, OpportunityList or SourceHealthList DTOs.
Core main has since advanced to schema `0010`; that version remains rejected.

`tests/fixtures/core-schema0009.json` captures actual rc.2 FastAPI ASGI responses
from `/health/ready`, `/api/v1/opportunities` and `/api/v1/sources/health`, plus
complete-empty and incomplete-empty opportunity responses. It records the exact
source commit, file hashes and explicit synthetic test-data provenance. The
upstream test database and M1 input fixture supply data; no PostgreSQL, app
lifespan, collectors or deployed service is accessed. Both data endpoints reject
missing and incorrect bearer credentials with HTTP 401. Readiness alone is not
an authentication proof.

Reproduce in a disposable development venv containing rc.2's pinned FastAPI,
SQLAlchemy, asyncpg and Pydantic dependencies plus httpx/pytest:

```text
python tools/verify_core_schema0009.py --core-source /path/to/unmodified/core-rc2
```

The tool pins the source SHA, checks hashes and the unchanged public models,
executes the actual routes, and compares all five captured responses exactly.
It is test-only; HA acquires no new dependencies or Core package imports.

## HA changes and regression coverage

Transport version validation and the separate projection/cache-envelope validator
share the explicit schema tuple. Updating only the HTTP client would still fail
on the second guard. The destination-policy artifact remains separately pinned
to schema 0008 and its original reviewed source hash; accepting a wire schema
does not approve destinations, new product identities or new intelligence.

Setup and repair errors now name API v1, schemas 0008/0009 and the existing
engine constraint in both source strings and English translations. Config flow,
origin comparison, private token handling and reconnect/reauth code are unchanged.

New portable tests run captured responses through the actual HTTP client,
typed assessment, projection sanitization and cache restart. They prove both
schemas work; future/unknown/malformed schema values, wrong API/engine versions,
invalid rows and shadow responses fail closed. A 0008-to-0009 refresh preserves
credentials, identity and original evidence clocks. Pending destinations remain
withheld. The old unsupported-0009 negative fixture now uses unsupported 0010;
all its original assertions and all historical tests remain.

New real HA tests serve the captured 0009 responses over controlled loopback
HTTP and exercise the actual user flow, coordinator, outage/recovery, existing
entry blank-token reconfiguration, revoked-token handling and reauthentication.
They reject 0010 independently at readiness, opportunities and source health,
retain the old configuration on failure, and reject invalid bearer tokens.
Existing two-origin forwarding, same-user rate-limit and pagination-expiry tests
remain intact. Full counts and final published SHA are in the review receipt.

## Boundaries

No PostgreSQL, Core API, collector, HA intelligence or dashboard behavior changes.
The bundled card is rebuilt only to synchronize its engineering version as
required by AGENTS.md. No release or tag is published. No user's live HA or Core
installation is edited. Actual private deployment reachability and installation
are not claimed by isolated tests.

Destination approval remains false. Birds/Planner coverage and calendar precision
remain unsupported; notifications, the legacy opportunity event and persistent
Follow/Skip/Seen remain disabled. Migration warning about unrestricted user-owned
HA state-trigger automations in `CORRECTIONS.md` still applies.
