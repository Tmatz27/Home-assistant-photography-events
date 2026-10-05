# Optional Core development scaffold (Milestone 1)

Independent-review correction: stale cache explanations, blockers, access and
condition state are neutralized along with eligibility and safety. Historical
reason text cannot imply that conditions are still current while Core is offline.

The v0.16.1 local engine remains authoritative and unchanged. Core is not a
production dependency. No card, entity, notification, config flow or websocket
has switched backends. This work has no public release or version bump.

Core lives at https://github.com/Tmatz27/photography-events-core. Its v1 API and
software version are independent of the integration's version. See that repo's
README and IMPLEMENTATION_REVIEW_MILESTONE_1.md for setup and validation.

## Activate the scaffold in a developer HA test

Use an isolated HA test configuration, construct a ConfigEntry with private
`data={"core_url": "http://<LAN-host>:8099", "core_token": "<generated-secret>"}`,
then explicitly call:

```python
from custom_components.photography_events.core_bridge import async_create_developer_bridge
bridge = await async_create_developer_bridge(hass, entry)
assessment = await bridge.refresh()
```

This does not register a production backend mode. Do not manually edit a live
HA `.storage` file. Connection settings are server-side ConfigEntry data; do
not put the bearer token in Lovelace YAML, attributes, websocket messages or
browser JavaScript. No token is returned by this helper.

All HTTP uses HA's shared aiohttp session with a five-second request timeout.
Two requests make one refresh at most ten seconds of asynchronous waiting;
neither blocks the HA loop. Redirects are disabled to avoid forwarding the
token. HTTP/authentication/readiness/version/malformed-data errors are typed.

Validated product data has an in-memory cache and a versioned HA Store keyed
by entry and Core origin. Restarting while Core is unavailable recovers the
last successful payload, visibly marked STALE/incomplete; every cached row is
held and ineligible. Cache older than seven days is omitted. Empty offline
data still means **assessment unavailable**, never a quiet week.

Future production integration needs per-content TTLs (Can't Miss much shorter
than year-planner context), a UI connection flow, websocket projection and a
deliberate cutover. None is silently activated by these modules.

Tests: `python -m unittest discover -s tests -q`; real HA Store tests are in
`test_ha_core_bridge.py` and run in the existing Home Assistant CI matrix.

## Milestone 2 observation intelligence (shadow only)

Core schema 0003 adds qualified report identity, canonical behavior assertions,
generation-scoped PostGIS clusters and persistent pattern episodes. Core owns
this intelligence. Its `CORE_PATTERNS_MODE` defaults to `off`; explicit `shadow`
mode computes development artifacts while the normal opportunity API retains
the accepted M1 decisions. Provisional thresholds cannot promote notifications.

Authenticated `/api/v1/debug/patterns` inspection and held opportunity previews
apply privacy redaction. The HA bridge and Lovelace card do not consume these
debug endpoints, clusters or raw records. Existing additive-field whitelisting
continues to protect HA payloads. No deduplication, clustering, episode matching,
backend cutover or card change is introduced in HA for M2. Any future production
promotion requires independent policy review and current travel checks.
