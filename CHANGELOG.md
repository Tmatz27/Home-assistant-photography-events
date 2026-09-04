# Changelog

## 0.6.0

A trust release. Three things were wrong enough to make the rest not worth
believing, and all three are fixed.

**The Milky Way window was the span of darkness, not the span you can shoot.**
From California in September those differ by a factor of five: darkness runs 503
minutes on 5 September, the galactic core is above 15 degrees inside that
darkness for 105 of them, and it is gone by 22:36. The window is now the true
intersection of three conditions - sun below -18 degrees, target above 15
degrees, moon below the horizon or under 20% lit - solved as intervals and
intersected, with `duration_minutes` and a note saying *what* closes it, because
"the core sets at 22:36" and "dawn" are different instructions.

**A cloudless night with a 72% moon scored in the nineties.** Cloud is a
forecast about tonight; moon phase is near-certain about next week, and a model
that only weighs tonight will always mis-rank them. A night with more than a
quarter-lit moon is now capped at 75 when a new moon falls inside ten days, and
it names the night to wait for. Ninety-plus is reserved for within three days of
new moon, or a moon down for the whole window, *and* cloud under 15%. An unknown
forecast can never reach it.

**Seasons were being reported as if they were appointments.** Every entry now
carries a background season *and* a concrete peak window, and only the second
scores or alerts. Beyond thirty days you get "gray whales, December to May";
inside thirty you get the three-week January pulse past the coastal points, with
the specific overlooks, real focal lengths and the behaviour or tide that
decides the shot. An alert fires as a window opens, not on each of its days.

Also:

- Meteor showers are single peak nights gated on radiant altitude, not
  multi-week ranges. Quadrantids corrected to ZHR 120
- Twenty-one California phenomena including the Horsetail Fall firefall, grunion
  runs, the Pismo monarch roost and the Central Valley crane fly-in; aspen colour
  split by elevation tier; blooms flagged rain-dependent with the live scrapers
  still the authority
- **Hero card**: an absolute start time instead of a countdown, the window
  spelled out with what closes it and how long is left, the duplicate tag row
  removed, and a strip naming what else is peaking now
- **Planning card**: filters are card state - no `input_boolean` helpers to
  create - plus a readable score badge instead of a coloured bar, and every row
  expands to peak-vs-season, gear, locations, time of day and why it scored
- **Timeline**: ordinary golden hours, lunar quarters, nightly planet summaries
  and eclipses that miss this location are hidden, with a legend explaining the
  colours and what is suppressed. `hide_routine: false` restores them
- Parks pruned to ten
- 104 Python tests and 73 JavaScript ones

Breaking: `filter_toggles` is gone from the card config - the chips need no
helper entities now. Any `input_boolean`s created for it can be deleted.

## 0.5.1

Fixes a bug that made the integration impossible to set up at all.

- **The config flow could not render its form.** Home Assistant serialises a
  flow's schema to JSON to draw it, and the categories field was written as a
  bare `[vol.In(...)]` list - which `voluptuous_serialize` cannot convert. The
  conversion raised inside `async_show_form`, so the flow failed while staying
  registered as in progress, and every later attempt aborted with
  `already_in_progress`. **If you hit this, restart Home Assistant once after
  updating**: in-progress flows live in memory, so the stale one only clears on
  a restart
- Every field is now a Home Assistant **selector** - a multi-select list for
  categories, sliders for the thresholds, a box with units for the drive limit,
  and masked password fields for both API keys. Those are the shapes Home
  Assistant guarantees it can serialise
- The single-instance guard no longer depends on `async_set_unique_id`'s
  in-progress check, which is what turned one failed attempt into a permanent
  block. It checks for an existing entry before building anything
- **Added `strings.json` and `translations/en.json`**, which were missing
  entirely. That is why the error appeared as the raw key `already_in_progress`
  rather than a sentence - and why every field would have shown as a raw name.
  Each field now has a label and an explanation, and the categories and routing
  modes have readable option labels
- Five regression tests, including one that reintroduces the original schema and
  confirms it is caught
- Minimum Home Assistant raised to 2024.11, the version whose `OptionsFlow`
  exposes `config_entry` as a property

## 0.5.0

The frontend half. The card can now render what the integration worked out
instead of recomputing a weaker version of it in the browser.

- **`mode: action_hero`** - the drop-everything card. It renders *nothing*
  until the binary sensor fires: no border, no empty box, no slot in the
  layout. When it does fire it shows the event, the drive time, the confidence
  score and the gear to pack. The drive time states its own provenance, so a
  figure Google routed reads "live traffic" and the calibrated distance
  estimate reads "estimated" - they are different claims and the card no longer
  presents them identically
- **`mode: calendar_outlook`** - the year ahead as a scrollable, month-grouped
  timeline, with filter chips bound to `input_boolean` helpers. A category with
  no toggle configured is always shown, so a half-configured card cannot
  silently swallow half the calendar
- Both modes are **push-driven**: they start no timers and redraw only when an
  entity they actually read changes. `mode: timeline` keeps the original
  browser-computed view, unchanged and still the default
- The visual editor asks different questions per mode, including a per-category
  picker for the filter helpers
- **Twenty-one California national parks and monuments** in the planning
  calendar, each with its best and good months, distance and drive time from
  home, and its dog rules - three ban dogs outright and most of the rest allow
  them only on pavement, which decides whether a trip happens at all. Parks are
  never a drop-everything alert and deliberately ignore the drive-time limit,
  because a nine-hour trip to Redwood is a long weekend, not an evening
- New `sensor.photography_events_planning_outlook` publishes the whole year as
  one attribute for the card to render. It is declared unrecorded, so a few
  hundred events are not written to the database on every update, and the rows
  are compacted against reference maps for gear and park rules - a year of
  events went from 102 KB of repeated prose to 43 KB
- 81 Python tests alongside the 67 JavaScript ones

## 0.4.0

Adds the live data sources - the ones that answer "is it happening *right now*",
which no amount of ephemeris can.

- **Rare birds from the eBird API v2.** Notable observations across Santa
  Barbara, San Luis Obispo, Monterey and Kern counties, grouped per species and
  location. Scoring rewards recency, repeat reports from separate observers, and
  reviewer confirmation, because a bird four people saw this morning is a
  different proposition from one unreviewed report on Tuesday
- **Whales from the iNaturalist API.** Orca, blue, fin and humpback reports
  inside a coastal bounding box derived from the zone table. Marine scores decay
  more slowly than bird scores - whales stay while the food does, vagrants leave
- **Real bloom and autumn-colour scrapers**, with BeautifulSoup, against the
  Theodore Payne Wildflower Hotline, DesertUSA and California Fall Color. Bloom
  timing depends on winter rainfall and cannot be computed, so these are the
  authority on blooms; the curated seasonal windows stay in the 365-day view as
  planning context only. Per-source CSS selectors live in one table at the top
  of the module so a site redesign is a small edit. The parser reads negation,
  so "the poppies are past peak" is not filed as good news
- **Traffic-aware drive times from Google.** Distance Matrix cannot be enabled
  on Google Cloud projects created after March 2025 and the Routes API is its
  replacement, so both are implemented: `auto` tries Routes, falls back to
  Distance Matrix, and remembers which one answered. Add the key in the
  integration's options
- **Sightings are placed by their own coordinates, not by zone.** A vagrant
  turns up wherever it likes, and the most actionable report this can produce is
  the one twenty minutes away that no target zone covers. Without a Google key
  those drive times are estimated from distance divided by an effective road
  speed calibrated against the zone table's own measured times
- **Per-service rate limiting.** Every source carries its own minimum interval
  independent of the coordinator cycle - hourly for Open-Meteo, eBird and
  iNaturalist, daily for the scrapers - so raising the update frequency cannot
  make any one service be polled harder than it allows. Sources are fetched in
  staggered groups so a restart cannot stampede, the daily scrapers are deferred
  to a background task so setup never waits on them, and a failed source keeps
  serving its last good payload while it retries on a backoff
- **A far more accurate Moon.** The single-term lunar series is replaced by the
  Meeus chapter 47 truncated ELP series (sixty periodic terms), and the Sun by
  the chapter 25 apparent longitude. Measured against published full-moon
  instants the old series was 124 minutes early on 2026-01-03; the new one is
  within a minute there and within two on 2026-03-03
- **Corrected an overstated accuracy claim.** The planet test was passing on a
  coarse proxy - the maximum Sun-planet angular separation sampled daily, which
  is neither the definition of opposition nor precise. Measured properly, in
  right ascension, Jupiter lands on the published instant but Mars and Saturn
  run about a day late, because the perturbations between the giant planets are
  not modelled. The README said "a few arcminutes"; it now says what is true
- 70 Python tests alongside the 41 JavaScript ones

Not yet implemented: the card's dedicated hero and calendar display modes. The
card still computes its own view client-side rather than reading the new backend
entities.

## 0.3.0

Splits the project into a Python backend plus the card, because a Lovelace card
cannot hold API keys, cannot call third-party APIs past the browser's CORS
rules, and only runs while someone is looking at a dashboard - none of which
suits "tell me to get in the car now".

- Add the **`photography_events` custom integration**, publishing real entities
  so ordinary automations can push to a phone with no dashboard open:
  `binary_sensor` for the drop-everything flag, `sensor` for the next
  opportunity and the best sky score, and a `calendar` for the planning view
- **Layered-cloud sunset scoring via Open-Meteo.** The card had to infer
  structure from a single aggregate cloud percentage; the backend reads the
  low, mid, and high decks separately and scores the actual mechanism - high
  cloud as the canvas, low cloud as the blocker, humidity as the mute. Needs no
  API key or account
- **Twelve fixed target zones** scored independently, each with a baseline
  drive time and Bortle class, gated on a configurable drive limit
- **Seasonal calendar** covering marine migrations, rut and pupping windows,
  super blooms, and Eastern Sierra aspen colour, with rainfall-dependent bloom
  timing explicitly flagged as needing confirmation rather than presented as
  fact
- **Gear advice per category** attached to every opportunity, described by
  focal length and capability rather than a specific body
- Meteor showers cross-checked against radiant altitude, moon illumination, and
  forecast cloud, with a ZHR floor so minor showers inform the calendar without
  raising alerts
- The card now ships inside the integration and registers itself, so one HACS
  install covers both halves. **This changes the HACS category from Dashboard
  to Integration** - see the upgrade note in the README
- No heavy dependencies: the ephemeris is a port of the already-verified
  JavaScript, so there is no astropy, numpy, or downloaded kernel. It
  reproduces the same published opposition dates to the day
- 28 Python tests alongside the 41 JavaScript ones

Not yet implemented, and deliberately called out rather than stubbed: the eBird
and iNaturalist clients, the wildflower and fall-colour scrapers, and the
card's dedicated hero/calendar display modes.

## 0.2.0

- Rebuild sunset/sunrise scoring around what actually makes a sky catch fire.
  Instead of reading a single cloud-cover number, it now samples the hours
  either side of the event and weighs how *broken* the cloud is (a sky that
  moves 20/55/35/60 is structured; 95/96/94 is a lid), penalises rain-bearing
  cloud and haze, and rewards the classic setup of an unsettled afternoon
  clearing right at sunset
- Add an **epic** tier above "excellent", reserved for when several of those
  signals line up, plus a top-of-card alert banner for one within 36 hours -
  the "go now" case rather than another badge in a list
- Every score now shows its reasoning ("47% cloud, clearing after an unsettled
  afternoon") so the pattern is learnable rather than a black box
- Add planets: Mercury, Venus, Mars, Jupiter and Saturn are computed from
  Keplerian elements, surfacing oppositions, greatest elongations, planet-planet
  and Moon-planet conjunctions, and a nightly "what's up" row. Verified against
  published opposition dates (Mars 2027-02-19, Jupiter 2026-01-10 and
  2027-02-11, Saturn 2026-10-04), which it reproduces to the day
- Add `custom_events` for comets and anything else that gets announced rather
  than predicted, scored for altitude and moonlight like every other target
- Collapse runs of consecutive Milky Way nights into a single window naming the
  best night, instead of one near-identical row per night
- Fix a real bug: a night was assembled by pairing a dusk with the *next
  calendar day's* dawn, which silently produced a 30-hour "night" spanning full
  daylight whenever the browser's timezone disagreed with the configured
  coordinates. Nights are now built from the dawn that actually follows the
  dusk
- Conjunctions now say which twilight to look in, rather than assuming evening

## 0.1.0

- Initial HACS-ready release
- Golden/blue hour, sunrise/sunset, computed directly rather than read from
  `sun.sun`
- Moon phase, illumination %, moonrise/moonset, with New Moon and Full Moon
  (Supermoon-flagged when notably close) called out specifically
- The eleven major annual meteor showers, scored by radiant altitude and
  moonlight interference
- Solar and lunar eclipses from a sourced table through 2028, with a real
  computed local-visibility check for lunar eclipses
- Milky Way core season detection
- A coarse bird migration season heuristic
- A near-term 24/48/72 hour snapshot plus a configurable 7-30 day outlook
- Optional weather-entity-driven sky-quality scoring for sunset/sunrise and
  meteor showers
- Visual card editor and full test suite
