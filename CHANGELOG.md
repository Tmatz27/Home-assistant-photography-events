# Changelog

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
