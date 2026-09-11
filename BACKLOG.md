# What is left, in the order it is worth doing

Rewritten 2026-09-11, after v0.12.0. The previous version of this file is now
history: of its ten items, three were delivered in 0.12.0, six were cancelled by
the user, and one was closed by an audit. Read `AGENTS.md` first.

---

## Done — do not re-open

Delivered in 0.12.0. Listed because a stale backlog is how work gets done twice.

- **Coordinator and entity coverage.** 22 real Home Assistant contract tests in
  `tests/test_ha_integration.py`, executed by their own CI job against HA
  2024.11.3 and 2025.3.4. The portable suite still runs with no HA installed.
- **Source health.** Failed / stale / waiting / disabled are now distinct
  states, per-hotline, with last-success timestamps and automatic HA Repairs
  after repeated failures. Affected rows show "Data degraded" *without* changing
  their evidence level — which was the important half.
- **Failed responses no longer look like empty ones.** A partial or failed fetch
  retains cached data with its original dates; only a genuinely empty valid
  response is quiet.
- **Card split** into 11 files under `www/src/` with a dependency-free
  concatenation script, CI-checked for source/artifact sync.
- **Eclipse catalogue**: 45 NASA eclipses 2026–2035 with published coordinates
  for all 16 central solar paths, TD vs UT corrected. An ocean path point is
  never treated as a road destination.
- **Meteor radiant drift**, added after a 1,920-night audit found it changed
  both a usable-night and a preferred-night verdict. Worth noting the audit was
  the right move: the previous backlog said "verify it matters before building
  it", and it did.

## Cancelled by the user — do not propose again

Notification blueprint, phone delivery, hassfest in CI, upstream brand
submission, a `watching` filter, score ÷ drive sorting, and a separate
`this_week` mode.

---

## Tier 1 — the largest remaining unknown

### 1. None of this has ever run on the user's Home Assistant

Everything is validated by CI, contract tests and synthetic browser fixtures.
No connection to the user's instance has ever been available to any agent
working on this. That makes installation, HACS upgrade, entity registration,
dashboard rendering at real payload size and mobile behaviour the only
completely untested surface left — and it is the one the user actually touches.

**This is not agent work.** It needs the user to install, restart, and report
what breaks. Until then, treat "it works" as unverified.

Worth preparing for that first contact: the served card is now 226 KB. Check
first paint and scroll on a real dashboard with a full year of events, on
phone as well as desktop, before assuming the split changed nothing.

---

## Tier 2 — coverage the data honestly lacks

### 2. Wave coverage is one calibrated stretch of coast

NDBC 46011 / CDIP B1500 cover the Vandenberg area. The calibration is
Vandenberg-specific and the hindcast frequency is explicitly not forecast skill.
Extending to other California coastlines means calibrating each one, not
reusing this one's thresholds.

Also open: verified elevated viewpoints for big-swell photography. Currently
there is swell data and no confirmed place to stand.

### 3. Moonbow geometry and waterfall flow

Moonbows need viewpoint-specific geometry (moon altitude and azimuth relative to
a specific overlook and spray cone) plus confirmation that water is actually
flowing. Neither exists. The targets are correctly labelled as search leads;
promoting them needs both halves, and the flow half has no feed.

The same gap covers firefall: seasonal light geometry is solved, flowing water
and clear western horizon are not.

### 4. Solar eclipse model limits

Central path coordinates are in. Still outside the model: partial-only solar
visibility, exhaustive road access to a path point, and exact contact times.
A path point being within six hours as the crow flies is not the same as
reachable, and the model should keep saying so rather than implying otherwise.

### 5. Behaviour still has no live confirmation

Rut, cubs, pupping, monarch clustering, foliage, bloom and bioluminescence have
no feed that confirms the *behaviour* — only that a species was reported. The
current labelling ("Species reported, not behavior confirmed") is correct and
should stay that way until a real source appears. Do not close this gap by
inference.

---

## Blocked on the user, not on work

- **Whale Safe API.** Needs the endpoint list, whether a key is required, and
  one example response body. `api.whalesafe.com` is unreachable from every
  review sandbox so far and is not indexed anywhere searchable. It remains the
  strongest single corroboration source available for this coast.

---

## Standing rule

The evidence model is the product. Every item above is a place where the honest
answer is currently "we do not know", and each one is only closed by a real
source — never by widening a window, softening a label, or inferring behaviour
from presence.
