# Changelog

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
