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

### 3. Moonbow viewpoint azimuth, and a sourced flow threshold

Two of the three unknowns closed in 0.13.0: the **altitude** geometry is
computed (the bow only clears the ground while the Moon is below 42 degrees),
and the water is **measured** by USGS 11264500 on the Merced.

What is left is narrower and both halves need sourcing, not coding:

- **Viewpoint azimuth.** Which bearing the Moon must hold to light one specific
  fall from one specific overlook. Nobody has published this in a form worth
  computing against, and it is the difference between "the sky permits a
  moonbow" and "a moonbow is predicted".
- **A flow-to-spray threshold.** The gauge reads the Merced; Yosemite Creek and
  Horsetail's catchment are separate drainages. No published cfs figure was
  found that says "above this, the falls are running". Do not invent one.

Firefall keeps the same shape: light geometry solved, flowing water now proxied,
clear western horizon still unmodelled.

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

## Resolved: Whale Safe is not available as data

Chased across several sessions as "the strongest corroboration source on this
coast". It is - and its public API does not carry it.

`api.whalesafe.com` publishes an OpenAPI spec at `/__docs__/` with nine
endpoints, every one ship-side: operator scorecards, vessel-speed-reduction
compliance grades, AIS track segments as GeoJSON, CSV dumps of ships and
operators. No presence endpoint, no detection endpoint, no sightings endpoint.
That API is the accountability half of the project - grading shipping companies
on whether they slowed down - not the whale half.

The near-real-time whale-presence rating (acoustic detections + trained
observers + blue whale habitat model, graded low/medium/high/very high) reaches
the shipping industry through private feeds and everyone else through the map on
the website. The only route to it as data remains a request to the Benioff Ocean
Science Lab, `boi-whalesafe@ucsb.edu`.

**Do not substitute the VSR data.** Speed-reduction seasons are fixed periods
declared in advance, so they encode an expectation of whales rather than an
observation of one. Wiring them in would manufacture exactly the broad seasonal
confidence the evidence model exists to refuse.

Nothing to build here. Marine windows stay on iNaturalist corroboration.

## Standing rule

The evidence model is the product. Every item above is a place where the honest
answer is currently "we do not know", and each one is only closed by a real
source — never by widening a window, softening a label, or inferring behaviour
from presence.
