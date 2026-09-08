# What is left, in the order it is worth doing

Written after reviewing v0.11.0/0.11.1. Each item says what "done" looks like and
which invariant it must not break. Read `AGENTS.md` first.

**The data layer is not where the remaining work is.** 17 of 22 windows are
live-verified across 14 wired sources, and the evidence model holds. Adding more
feeds is the least valuable thing available right now. The gaps are structural,
and three of them are the kind that fail silently.

---

## Tier 1 — structural risk. Do these before any new feature.

### 1. The coordinator has zero tests

`coordinator.py` is ~900 lines orchestrating fourteen sources, per-source
throttles, staggered startup, multi-coordinate request bundling, ingestion,
routing and persistence. Every pure module around it is well covered. It is not
covered at all, and neither are `sensor.py`, `binary_sensor.py`, `calendar.py`,
`__init__.py` or `event_state.py`.

This is where the next silent breakage comes from: a refactor that reorders the
update cycle, drops a source, or breaks the forecast bundle shape will pass all
284 tests.

**Done looks like:** a fake `hass` + fake `aiohttp` session harness in
`tests/`, and tests covering — one source failing does not fail the cycle;
throttles actually prevent a re-fetch inside the interval; cold start defers the
scrapers; the forecast bundle keeps its `{local, upstream}` shape; Follow/Skip
survives a reload; a source that raises is recorded as failed and retried on the
backoff, not on the next tick.

**Do not** import Home Assistant into the pure-module tests to achieve this —
keep the HA-touching tests in a separate file that skips cleanly when HA is
absent, so `python3 -m unittest discover` still runs anywhere.

### 2. A source can die silently, and nothing tells anybody

Fourteen sources. If the Theodore Payne page is redesigned, an eBird key
expires, or an NDBC station is retired, the integration keeps working and simply
produces fewer rows. The user sees a quieter calendar and concludes nothing is
happening. For a project whose entire thesis is *never be silently wrong*, this
is the sharpest remaining edge.

`sources` is already published in the sensor attributes. Nothing consumes it.

**Done looks like:** a source failing N consecutive times raises a Home
Assistant **Repair issue** naming the source, when it last succeeded, and what
is consequently missing ("wildflower hotlines unreachable since 3 Sept —
bloom windows are running on calendar estimates alone"). Plus a compact health
strip on the card: last success per source, and an explicit "degraded" marker on
any row whose evidence depends on a source that is currently down.

That last clause is the important half. A window that *would* be corroborated
except its feed is broken must not look identical to one nobody has confirmed.

### 3. The card is one 3,875-line, 164 KB file

It is past the size where an agent can edit it safely. Two concrete incidents:
an identical `"cloud_cover"` block appeared in both the meteor and Milky Way
builders and a scripted replace hit the wrong one; and a whole-file rewrite
flipped every line ending, burying a 40-line change in a 2,815-line diff.

**Done looks like:** the card split into modules under `www/` (astronomy, card
modes, formatting helpers, styles) loaded as ES modules from the same static
path, or concatenated by a trivial `scripts/build-card.mjs` that CI verifies is
in sync. No bundler, no dependencies — that constraint stays.

Keep `CARD_VERSION` and `scripts/check-version.mjs` working across the split.

---

## Tier 2 — finishing what is already there

### 4. Ship a notification blueprint

The drop-everything sensor exists; acting on it is still hand-written YAML in
the README. A blueprint at `blueprints/automation/photography_events/` turns
that into one click, and can carry the things people get wrong: quiet hours, not
re-firing for the same occurrence, and including the *setup-by* time rather than
a relative countdown in the push body.

### 5. Run hassfest in CI

`validate.yml` runs the HACS action but not `home-assistant/actions/hassfest`.
Hassfest is the official validator and catches manifest, translation and
dependency problems that HACS does not.

### 6. Submit the brand icon upstream

A local `brand/icon.png` was added to satisfy HACS. The real fix is a PR to
`home-assistant/brands`, after which the local copy can go.

### 7. Three UI items proposed and never actioned

- **Collapse `watching` rows** behind a toggle. Several windows are real but
  unconfirmed — useful for planning, noise for deciding.
- **Sort by score ÷ drive time.** A 78 forty minutes away beats a 90 six hours
  out, and the list currently cannot express that.
- **A `this_week` mode** — possibly now covered by the compact hero; check
  before building.

---

## Tier 3 — data reach, once the above is done

### 8. The eclipse table ends in 2028

Nine entries, none of whose solar paths reach California. Extend from an
authoritative catalogue (NASA/EclipseWise) and — this is the blocking part for
the user's actual request — add **path centreline coordinates** so "visible
within a six-hour drive" can be computed instead of guessed. Source them. Do not
derive them from the prose `region` strings.

### 9. Meteor radiants are fixed points

Stored RA/Dec is the position at maximum. The planner now shows adjacent nights,
across which a radiant drifts roughly a degree a day. It is a small effect at a
30° altitude gate — verify whether it changes any night's verdict before
spending effort on it. If it does not, write that down and close it.

### 10. The five remaining `static` windows

Both bighorn subspecies, and the rest. These are deliberately static — sparse,
cryptic animals nobody reliably reports. Only revisit if a real feed appears;
promoting them without one is the failure mode the evidence model exists to
prevent.

---

## Blocked on the user, not on work

- **Whale Safe API** — needs the endpoint list, whether a key is required, and
  one example response body. `api.whalesafe.com` is unreachable from the review
  sandbox and is not indexed anywhere searchable.
- **Solar eclipse path geometry** — see item 8. Must be sourced.
