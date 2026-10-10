# V17A migration, choices and privacy design

Design only. Config-entry VERSION remains 2 in V17A; no runtime, Store or database
migration is implemented here. Proposed V17B schema major 3 requires a separately
reviewed release. Product release/version updates remain outside this slice.

## Config-entry migration and connection

HA's authoritative documentation was reviewed on 2026-10-09:
[config flow, migration, reconfigure and reauth](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/),
[setup failures and retry/auth exceptions](https://developers.home-assistant.io/docs/integration_setup_failures/),
[Repairs](https://developers.home-assistant.io/docs/core/platform/repairs/),
[authenticated WebSocket protocol](https://developers.home-assistant.io/docs/api/websocket/),
[entity registry](https://developers.home-assistant.io/docs/entity_registry_index/).
Reconfigure and reauth update the existing entry and abort; they do not create
a second entry. Use supported config-entry update helpers. Transient setup
failure raises ConfigEntryNotReady; wrong/revoked credentials raise
ConfigEntryAuthFailed and start reauth. Migration should be local and repeatable,
independent of network availability. No manual `.storage` edits.

| Starting condition | Proposed V17B supported behavior |
| --- | --- |
| Version 1 legacy entry | Preserve entry_id, unique_id (normally DOMAIN), data/options and literal enabled_categories including []; do the existing v1->v2 semantic migration, then v2->v3 local metadata change. Retain legacy values under their existing keys as inactive settings; do not execute them. |
| Version 2 legacy entry without Core configuration | Copy data/options without deleting credentials/preferences, add `connection_state='needs_connection'` in private data, set version=3 using async_update_entry. Setup a dormant status coordinator and the same summary entities/resources; do not construct legacy sources. Create a translated persistent Repairs issue `core_connection_required` with a fix flow to securely complete connection. Integrations Reconfigure uses the same validation path. Card states connection required with instructions to Settings > Devices & services > Photography Events. |
| Version 2 developer Core data | Preserve URL/token in private data, do not assume token valid from readiness. Require health version plus authenticated normal list before state becomes connected. Existing developer cache is revalidated/sanitized or ignored, never blindly forwarded. |
| Fresh install | Single-instance guard before form; selectors for URL and password token, no token prefill. Validate origin, versions, readiness and authenticated normal API. Errors cannot_connect/invalid_auth/unsupported_api_version/invalid_core_response remain in form; no half-created entry. Title/domain and singleton unique ID stay the same. Initial choice persistence unavailable explained in UI. |
| Migrated entry with missing token | Dormant connection_required status and Repair; secure connect flow. This is configuration completion, not invalid-token reauth. No legacy fallback, no polling providers. |
| Wrong/revoked token | ConfigEntryAuthFailed at connected setup or coordinator update; translated reauth confirmation/password form, no new entry; rich cache hidden. Validation proves authorized access, updates existing private data and reloads. |
| Core outage/not ready on configured setup | Register card resource independently, then raise ConfigEntryNotReady for automatic HA retry. Existing registry entities remain unavailable; card can still distinguish unavailable integration. No legacy constructor. After successful setup, a refresh outage preserves stale historical context with explicit status; action becomes unavailable. |
| Malformed URL, incompatible API/schema or corrupt products | Form error during setup; connected instance safe incompatible/invalid_response state and repair/reconfigure guidance. Do not repeatedly retry protocol mismatches as though valid empty data. |
| Unsupported future config-entry version | Reject with translated migration error; do not downgrade or wipe. Restore supported code/config backup. |
| Options edit, restart, reload, unload | Reload same entry; cancel pending requests/expiry timers/subscriptions and remove per-entry service state. Register static resource once and never remove a dashboard resource. Entry migration retries must not duplicate entities or Repairs. |

URL reconfigure (`async_step_reconfigure`) must target `_get_reconfigure_entry`,
preserve singleton unique ID, guard mismatch, validate the new connection, then
`async_update_reload_and_abort`. Core URL cannot become the unique ID. Existing
singleton unique ID/domain remains stable; same entry_id retains all entity keys.
Changing Core origin requires an explicit UI warning that choices cannot map
across an unverified Core instance; invalidate active cache. Wrong-token flow
uses `_get_reauth_entry` and the same existing-entry helper. Blank token fields
mean retain current token only on an explicitly labelled reconfigure form;
replacement uses a separate password input, never suggested current secret.
Missing-token completion requires a new nonempty value. Never store Core token
in entry.options, entities, services, diagnostics, card config or browser storage.

Preserve device `(DOMAIN, entry.entry_id)` and all six existing entity suffixes
listed in CONTRACT.md. Keep unsupported score/status entities registered as
unavailable rather than delete/recreate. New summary status entity has its own
stable suffix. Registry tests must prove existing customized entity_id/name,
disabled state and dashboard resource URL survive v1/v2 migration and reload.
Legacy user automations can still reference old IDs, but changed attributes and
unsupported categories need explicit migration notes. Do not use unknown=zero
as compatibility. Calendar all-day end handling needs Core time precision first.

Only presentation filters/categories remain HA options. Legacy thresholds,
provider keys, routing and source-enable options become inactive preserved
configuration; no effect on Core eligibility. Explain this in reconfigure UI.
No drive-limit control should imply changing Core travel policy through a GET.

Rollback: V17A is docs/tests only and can be reverted cleanly. A later major-3
rollout needs a HA backup of config entries, registry and choice/cache Store
before upgrading. The old runtime rejects entries above v2; restoring only old
code is not a supported downgrade. Restore matching code/config backup. Never
automatically reactivate the rejected intelligence engine on Core failure.

## User-choice identity and ownership

Existing `event_state.event_id` uses roll-or-key; choice Store is
`photography_events.<entry_id>.events`, choice and announcement maps shared by
all HA users. Current service does not bind entry/user and loops all coordinators.
Grouping nightly rows supplies multiple choice_ids. These are legacy identities,
not evidence of equivalence with Core keys.

Event UI identity is exactly Core `occurrence_key`. It is stable across score,
preferred location and assessment generation updates. `phenomenon_key` names a
recurring class, never a year's selected event. Do not hash titles, dates,
coordinates or scores to create replacement identities. A changed occurrence
key is a distinct occurrence unless Core supplies an explicit reviewed alias.
`assessment_id`, `pattern_episode_id` and array position are not choice keys.

Preferred eventual authority is Core persistence. Proposed durable scope:
`(core_instance_id, core_principal_id, occurrence_key)`; both instance/principal
IDs need future supported contracts. Map authenticated HA user to an opaque Core
principal through a backend registration/mapping contract; do not send arbitrary
user IDs in browser requests or treat the shared bearer as multi-user identity.
Default choices are per-user across their devices; household sharing must be an
explicit setting with a separate household principal. Each user's notification
channel/preferences remain distinct. HA WebSocket read/write authorization must
enforce the entry and current principal; no leaking another user's choices.

- Follow subscribes to reviewed meaningful updates for this occurrence.
- Skip suppresses this occurrence for this user.
- Seen/Got the shot marks this occurrence completed for this user.
- Default clears the choice. Annual recurrence is a new occurrence; recurring
  subscriptions, if later offered, require an explicit separate operation.

Future mutation contract must assign request UUID/idempotency key, stable actor
scope, occurrence_key, desired choice and expected choice revision. Retrying
the identical command returns the same result; divergent reuse rejects. Compare
revision detects two-device conflicts; authoritative acknowledgment updates UI.
No optimistic success before persistence. Bounded retries for transport failures;
auth/conflict/unknown occurrence are explicit. Initial V17B exposes unavailable
choice controls (`pending_core`); no local Store shadow authority, no invented
Core write endpoints, and no choice DB migrations in V17A.

Preserve legacy choice Store unchanged for possible export/review. Copy only with
a proven one-to-one mapping of occurrence/season/time scope and explicitly chosen
owner; shared legacy preferences cannot silently become every user's choices.
Ambiguous rolls/grouped nightly IDs, unavailable historical occurrences or changes
to Core instance remain unmapped with an audit reason. Never fuzzy-match species,
title or nearest date. Legacy announced fingerprints must never become Core
deduplication/evidence. A choice cannot change confidence, evidence, eligibility,
source health, required gates or assessment timestamps.

## Explicit public-location serialization

Retain Core's curated-public-destination approach. `PublicLocation` has
key/name/latitude/longitude/policy, but schema acceptance alone is insufficient:
withheld policy does not itself prohibit coordinates. Core's database validates
products and integrity and shadow read redacts sensitive facts; HA must still
enforce its output boundary, including cache and details.

1. Only `policy='curated_public_site'` plus a key and exact coordinate pair in
   a independently reviewed destination registry may emit usable coordinates.
   For V17B registry entries come from audited Core definitions/public visitor
   destinations (Carrizo Tule elk destination; Pismo is shadow context only).
   Registry metadata includes public visitor listing/review and source version;
   it is destination authorization, never an intelligence engine. A missing
   registry entry or mismatch fails to withheld, not a guessed replacement.
2. Emit key/name from the reviewed public registry, not arbitrary incoming text.
   A coordinate pair must be finite, in range, both present and matching the
   approved pair. Coordinates are public destination coordinates, never a
   wildlife point. Public destinations can be useful even with no wildlife
   coordinates; a destination alone proves no travel eligibility.
3. For `policy='withheld'`, unknown policy or unapproved destination emit exactly
   `{policy:'withheld', key:null, name:'Location withheld', latitude:null,
   longitude:null}`. Suppress upstream key/name, drive_minutes, drive_basis,
   detail/reason/awaiting/blockers/gear and other location-bearing free text;
   use fixed public explanation and generic safety/access labels. No map URL,
   region hint, offset, blurred point or reverse geocoding. Preserve only a
   reviewed nonsensitive opaque occurrence/phenomenon identity. Reject identifiers
   that embed provider IDs/locations; this requires Core identity review, not a
   regex promise that arbitrary free text is safe.
4. Use explicit field-by-field typed reconstruction, never `dict(row)` or a
   permissive nested passthrough. No raw report geometry, protected/obscured
   points, analysis centroids, private observers, unapproved auto destinations,
   raw sensitive observation IDs/descriptions, evidence lists or raw URLs.
   If public product prose ever includes these, reject/suppress the row; source
   controlled public prose is the trusted boundary, not provider descriptions.
5. Safe normal public text is bounded and escaped. Future evidence links require
   a separately reviewed sanitized public contract and HTTP(S) allowlist; do not
   blindly follow or persist URLs with embedded credentials/query identifiers.
   All rich outputs, cache, summary entities, details, calendar descriptions and
   any later notification use the same serializer. Diagnostics redact all
   credentials and connection details independently.

Negative tests inject synthetic sentinel credentials, sensitive IDs/descriptions,
geometry/centroids/observer metadata and unknown nested arrays at every boundary;
the serialized bytes must omit them. Withheld rows also carry malicious prose
inside otherwise recognized fields and must lose it. Approved exact coordinates
survive; altered/unapproved/nonfinite/partial pairs cannot survive. Known limits:
the current test-only model proves these rules on synthetic fixtures, not a
deployed HA boundary; V17B must apply the same tests to its actual serializer,
Store, authenticated WebSocket, calendar and diagnostics before activation.
