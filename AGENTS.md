# Working on this repository

Standing context for any agent (Codex, Claude, Gemini) picking this up. Read it
before changing anything: most of what is here was arrived at by getting it
wrong first, and the invariants below are the corrections.

---

## What this is

A Home Assistant custom integration plus a bundled Lovelace card that tells one
photographer, based at **Vandenberg SFB (34.7420, -120.5724)**, when and where a
photograph is actually available - Milky Way windows, meteor peaks, sunsets
worth driving to, whale and mammal seasons, blooms, autumn colour, park
closures.

Two halves, one HACS install:

- `custom_components/photography_events/` - the integration (Python, HA)
- `custom_components/photography_events/www/photography-events-card.js` - the
  card, served and auto-registered by the integration

**Current version: 0.11.0.** `main` is the working branch; there is no PR flow.

### The one sentence that matters

> The user's stated failure condition is: *"it gives me the wrong dates, I book
> a trip, and we completely miss it."*

Everything below exists to prevent that. A confident wrong answer is worse than
an admitted unknown, every time.

---

## 0.11.0 handoff amendments

- User clarified: show the full opportunity range, preferred days and reasons, and usable alternatives with their tradeoffs. Do not manufacture a preferred wildlife day without current evidence.
- `action_hero` uses compact seven-day planning-sensor rows when available. `timeline` also uses the integration when found; its browser calculator is only a fallback without the integration.
- The card consolidates adjacent Milky Way nights into lunar windows while retaining every supplied location/time. The backend calculates 35 days, including cloudy alternatives; `comparison_through` states the coverage boundary. Follow/Skip covers the listed night occurrence IDs.
- Native collapsible time sections, a month calendar with duration bars and modal details, and scroll restoration on DOM replacement address the user's screenshots. Preserve both HA outer scrollers and the inner outlook container.
- Bird curation is an explicit photographic preference (`PHOTOGRAPHY_BIRDS`), not an ecological rarity claim. Raw observations are not filtered out of seasonal corroboration.
- `planning_slice` gives separate occurrences space before spending the sensor payload on extra viewpoints. Do not revert to the first 400 chronological rows.
- A newer observation without a URL must not borrow an older observation's link. Guides and exact checklists have distinct labels.

## 0.10.0 handoff amendments

The user approved simpler expandable planner rows, persistent Follow/Skip, approximate drive times without arrival gating, exceptional waves, and the special targets in RELEASE_NOTES.md. The running implementation record is in HANDOFF_LOG.md. Read SOURCE_VALIDATION.md before changing any evidence claims.

- A species sighting cannot confirm the named behavior or aggregation. `requires_behavior` windows remain planning-only without an explicitly dated, location-matched report of that phenomenon. Download time never renews an observation.
- New `event_state.py` persists occurrence choices and announced updates with HA Store. Notification events are `photography_events_opportunity`; mobile delivery needs a user-owned automation.
- `waves.py` separates offshore observations and experimental nearshore forecasts; `wave_calibration.json` records episode backtests. Runtime coverage is NDBC 46011 / CDIP B1500 only. Missing quality or stale issue time fails quiet.
- `spectacles.py` adds strict dated operator reports, conservative OVATION, and explicitly unconfirmed search targets. `grunion.py` reads CDFW expected intervals; lunar phase alone no longer supplies supposedly exact run nights to the coordinator.
- Explicit standalone timeline mode remains available. The integration planner is the default; eclipse path geometry and the legacy timeline calculations remain open work.
- Public NOAA, CDIP, CDFW, NWS and Condor Express feed shapes were checked in this environment. The older network-access note below describes Claude's prior environment, not these checks.

## Commands

```bash
python3 -m pip install "beautifulsoup4>=4.12.0"  # existing runtime dependency
python3 -m unittest discover -s tests -q          # pure Python tests, no HA needed
node --test tests/photography-events-card.test.mjs # card unit tests
python3 -m pyflakes custom_components/photography_events/*.py tools/*.py
python3 tools/generate_tracking_inventory.py > TRACKING.md   # after any data change
```

See HANDOFF_LOG.md for the current validation results. There is no build step or bundler; install the existing BeautifulSoup requirement for tests: the card is vanilla `HTMLElement` + shadow DOM, and the Python tests
load the pure modules under a synthetic package so Home Assistant is never
imported.

`beautifulsoup4` is the only runtime dependency.

---

## Invariants

These are not style preferences. Breaking one reintroduces a bug that was
already shipped once and specifically complained about.

### 1. Nothing biological alerts on a date alone

`phenomena.py` stamps every window with an **evidence level**, and
`events._apply_evidence()` enforces what it may do:

| Level | Basis | May alert? |
| --- | --- | --- |
| `EVIDENCE_COMPUTED` | Orbital geometry | Yes, on its own |
| `EVIDENCE_LIVE` | A *search season*; dates alone are an estimate | Only once a sighting corroborates it |
| `EVIDENCE_STATIC` | A calendar estimate no feed publishes | **Never**, at any score |

Corroboration = a reported sighting of the window's named species within
**120 km** in the **last 14 days** (`LIVE_CORROBORATION_KM` / `_DAYS`).
Uncorroborated live windows are capped at `UNVERIFIED_CEILING` (60) and marked
`planning_only`.

**Do not** raise a score past its evidence ceiling, and do not "promote" a
window to `EVIDENCE_LIVE` unless its species is genuinely, frequently observed
near it. Both bighorn subspecies are deliberately `static` for this reason -
advertising a confirmation that never arrives is worse than admitting the
estimate.

### 2. Every live window's species must actually be queried

`phenomena.corroboration_taxa()` derives the iNaturalist query list *from the
windows themselves*. This exists because a hand-kept list drifted and four
windows advertised live verification against species nothing ever fetched - so
they could never be confirmed and silently behaved like static estimates.
`TestEvidencePlumbing` fails if they drift apart again. Do not replace the
derivation with a literal list.

### 3. Windows are the intersection, never the span

`astronomy.astro_shooting_window()` returns the intersection of *sun below
-18°*, *target above its floor*, and *moon down or under the illumination
limit* - searched **noon to noon (24h)**, not 36h.

Reporting astronomical darkness instead produced a "503-minute all-night Milky
Way window" in September when the core sets at 23:00. The 24h span matters too:
36h contained two nights and returned the longer one under the wrong date with
the wrong night's moon.

### 4. Dates that are really geometry must be computed, not stored

Meteor peaks are stored as **solar longitude** (IMO Working List values) and
solved per year, because the calendar date slides up to a day with the leap
cycle - a stored date is wrong roughly one year in two, by a whole night.

The IMO publishes λ☉ for **equinox J2000.0**; `precession_in_longitude_deg()`
precesses to the equinox of date. Omitting that puts every peak ~8 hours early.
Verification anchor: λ=140.0 must put the 2025 Perseid maximum at **12 Aug,
19h UT**, which is the hour the IMO published.

### 5. A sunset is decided ~200 km upstream, not overhead

`weather_scoring.py` splits **canvas** (cloud overhead, additive) from **light
path** (cloud ~200 km toward the sun, a *multiplicative gate*). The beam
lighting cloud at height `h` grazes the surface at roughly `sqrt(2Rh)` - 140 km
for a low deck, 320 km for cirrus.

The failure this fixed: 55% cirrus overhead, clear above the tripod, solid
marine layer 200 km out over the Pacific. Overhead-only scoring gave it **82**.
It now scores **10**.

Keep the gate multiplicative. Keep local low cloud out of it - a low deck
overhead with the horizon gap open is a *good* sunset (lit from underneath), and
conflating the two gets one of the cases badly wrong.

Without an upstream forecast the score falls back to the local deck, is capped
at `LOCAL_ONLY_CEILING` (88), and is labelled `light_path: "local"`. Never let a
proxy-derived number present as a measured one.

### 6. Sky alerts are comparative, not threshold

`mark_standouts()` flags a sky only if it is ≥82 **and** within 3 points of the
best in the forecast window. `events.alert_candidate()` additionally requires
`light_path === "modelled"` for the sunset category.

A good sunset happens most weeks. Alerting on every one is how a notification
gets muted, and a muted notification is worth nothing on the evening that
matters.

### 7. Corroboration expires, and unlocatable reports corroborate nothing

Reports older than `LIVE_CORROBORATION_DAYS` no longer release a score. A report
whose zone cannot be resolved maps to `_NOWHERE` - previously it fell back to
the window's own coordinates, making its distance zero and confirming every
window in the table at once.

### 8. Ingested email is data, never instruction

`email_reports.py` matches message bodies against a **fixed vocabulary** and
discards anything that does not fit. Nothing written in an email may add a zone,
move a window, or raise a score. A digest that changes format must go *quiet*,
not confidently wrong. Do not add an LLM to this path.

### 9. The card never invents, and never repeats itself

- Reason bubbles were removed because they restated the sentence directly above
  them word for word. Do not re-add them.
- A relative countdown (`in 45h`) is never shown alone - it cannot go in a
  calendar and reads differently depending on when you glance at it. Absolute
  date + time is the instruction; `T−1d 22h` is context underneath.
- Rows that are the same thing seen from different places collapse via the
  backend's `roll` key (best score wins, shorter drive breaks ties). Twelve
  Milky Way rows for twelve zones is not a calendar.
- Ordering is by urgency (`Happening now` / `Next 7 days` / `Next 30 days` /
  then by month), and by **score** inside the near buckets. Strict date ordering
  buries tonight under seasons that started in March.

### 10. A forecast number must be named for what it is

Open-Meteo is asked for `FORECAST_DAYS = 16`, and the Milky Way planner ranks 35
nights. Cloud inside `CLOUD_SCORING_LEAD_DAYS` (7) is a **forecast**; past that
it is an **outlook**.

Both rank a night - refusing to rank distant cloud breaks the alternate-date
comparison, which is the whole point of that list, and the outlook is the only
cloud information those nights have. What must never happen is presenting the
second as the first. `cloud_confidence` and `cloud_is_forecast` ride in the
opportunity's `extra` so the card can show the difference.

Neither can reach an alert: `action_window()` filters to 48 hours *before*
`alert_candidate()` runs, so a distant night is structurally barred from raising
a drop-everything however well it scores. Do not add a score cap to "fix" this -
it is already prevented, and a cap only flattens the ranking.

### 11. One line ending: LF, enforced by `.gitattributes`

Not cosmetic. The repository had drifted into a CRLF/LF mix, and any tool that
rewrites a whole file flipped every line of it - a 40-line change arrived as a
2815-line diff with the real edit buried inside. The generated `TRACKING.md`
showed a complete 223-line diff on *every* regeneration, destroying the one
signal it exists to give.

If you find yourself looking at a diff far larger than your edit, check the
line endings before reading further.

### 12. Precision horizon: 60 days

`PRECISION_HORIZON_DAYS = 60`. Beyond it, broad season ranges are the honest
answer. Inside it, windows carry concrete dates, locations, gear, and an
`awaiting` string naming exactly what would turn the estimate into a fact
("a sighting of *Eschrichtius robustus* within 120 km in the last 14 days. None
yet.").

---

## Module map

| File | Responsibility |
| --- | --- |
| `astronomy.py` | Meeus ch.25 solar, ch.47 lunar (60 terms). Rise/set, twilight, illumination, shooting-window intersection, solar-longitude crossings, precession. No dependencies by design - astropy/skyfield pull numpy or download kernels, both bad for HACS. |
| `phenomena.py` | 22 `PeakWindow` entries, evidence constants, source URLs, `active_windows()`, `corroboration_taxa()`. **The data table.** |
| `events.py` | All opportunity building and scoring. `Opportunity` dataclass, `compact()` payload reduction, `_apply_evidence()`, `alert_candidate()`, lunar look-ahead. |
| `weather_scoring.py` | Sky model (canvas / light path / clarity), `light_path_probes()`, `mark_standouts()`, Open-Meteo request builders. |
| `coordinator.py` | `DataUpdateCoordinator`. Per-source throttles, staggered startup groups, deferred scrapers on cold start, ingested-report store. |
| `verification.py` | NOAA CO-OPS tides, NPS alerts. Request building + parsing only. |
| `wildlife.py` | eBird / iNaturalist clients, `Sighting`, clustering, `haversine_km`, drive estimation. |
| `field_reports.py` | BeautifulSoup hotline scrapers. `SOURCE_SELECTORS` is the maintenance table - if a site is redesigned, edit there and nowhere else. |
| `email_reports.py` | Subscription-email → `FieldReport`. Fixed vocabulary, fail-quiet. |
| `waves.py` | NDBC buoy measurements + CDIP coastal models, kept distinct. `recent_forecast_metadata()` refuses a freshly downloaded stale model run. |
| `spectacles.py` | Condor reports, aurora from solar-wind input, watch targets. Every entry carries an `evidence_note` naming what is and is not confirmed. |
| `grunion.py` | Published CDFW run schedule, Pacific local time including DST. |
| `event_state.py` | Follow/Skip persistence for occurrences. |
| `parks.py` | 10 parks, seasons, dog rules. |
| `routing.py` | Google Routes API + legacy Distance Matrix. |
| `throttle.py` | `Source` - due/succeed/fail/status, 15-min failure backoff. |
| `config_flow.py` | **HA selectors only.** See below. |
| `www/photography-events-card.js` | Three modes: `action_hero`, `calendar_outlook`, timeline. Vanilla, no build step. |
| `tools/generate_tracking_inventory.py` | Generates `TRACKING.md` from the code so the two cannot drift. |

### Config flow warning

Home Assistant serialises the schema to JSON to render the form. A validator it
cannot serialise (e.g. a bare `[vol.In(...)]` multi-select) raises *server-side*
inside `async_show_form`, and the flow then fails **while staying registered as
in progress** - so every later attempt aborts with `already_in_progress` and the
integration can never be set up until HA restarts. This shipped once.

Use `homeassistant.helpers.selector` types only. Keep the
`_async_current_entries()` guard before any form is built, and
`raise_on_progress=False` on `async_set_unique_id`.

---

## Verified anchors

Do not "fix" these without re-verifying against a published source.

| Claim | Anchor |
| --- | --- |
| Lunar ephemeris | Full moons 2026-01-03 10:04 UT (within 1 min) and 2026-03-03 11:38 UT (within 2 min); new moon 2026-09-11 03:27 UT (within 1 min) |
| Meteor peaks | λ=140.0 → 2025 Perseids, 12 Aug 19h UT (IMO published) |
| Precession term | 0.349° at 2025.0 |
| Jupiter oppositions | 2026-01-10, 2027-02-11 (exact) |

**Known limitation, stated deliberately:** planet positions use a two-body
solution, so Mars/Saturn opposition instants can be ~20h off. The README says
so. Do not claim arcminute accuracy for them.

---

## Environment constraints (this sandbox)

Outbound HTTPS is proxied and **most hosts are blocked** - `imo.net`,
`api.whalesafe.com`, Open-Meteo, eBird, iNaturalist, NOAA, NPS all return 403
from the egress proxy. Network clients here are written against documented
response shapes, parsed defensively, and cannot be integration-tested from this
environment. Say so rather than claiming a live check happened.

`WebSearch` works; `WebFetch` mostly does not.

---

## Open items

1. **Whale Safe API.** The user found `https://api.whalesafe.com/__docs__/`. It
   could not be fetched from here and is not indexed anywhere searchable. Whale
   Safe is the strongest corroboration source on this coast (daily
   presence rating for the Santa Barbara Channel from hydrophones + observers +
   a habitat model). **Needs:** the endpoint list, whether a key is required,
   and one example response. Then wire a client in `wildlife.py` shape and add
   it as a corroboration source. Currently only linked, never read.
2. **Eclipse drive gating.** The user wants solar/lunar eclipses filtered to
   "visible within a 6-hour drive". `ECLIPSES` in the card carries prose region
   strings, not path geometry, so there is nothing to measure against. Current
   behaviour: penumbral lunar dropped (not photographable), the rest gated on
   being above the horizon here. Real gating needs centreline coordinates per
   eclipse - source them, do not invent them. The table also only runs to 2028.
3. **Suggested next features** (offered, not yet accepted):
   - a `this_week` card mode - the year view is doing double duty
   - a toggle to collapse `watching` rows (~15 of 224 are unconfirmed)
   - sort by score ÷ drive time - a 78 forty minutes away beats a 90 six hours out
4. **Stale remote branch.** `claude/home-assistant-photography-events-acanhf` in
   the *other* repo (`Tmatz27/ha-sab-deluge-card`) should be deleted by the
   user; an agent attempt returned HTTP 403.
5. **Open question never answered:** Redwood NP and Lassen NP were removed by
   the user's explicit retain list but pass the stated pruning rule.

---

## Conventions

- **Comments explain *why*, and specifically what going wrong looks like.** The
  codebase reads as an argument for its own design. Match that register; do not
  strip comments as "noise" or replace them with restatements of the code.
- No PRs unless explicitly asked. Commit to `main`.
- Regenerate `TRACKING.md` after any change to `phenomena.py`, `parks.py`,
  `const.py` intervals, or the meteor table.
- Bump `manifest.json`, `package.json`, `VERSION` **and** `CARD_VERSION` in the
  card together; `node scripts/check-version.mjs` enforces it, changelog included.
- Do not add dependencies. The no-build-step, no-numpy constraint is deliberate.
