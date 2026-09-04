# Photography Events

![Photography Events](banner.svg)

> **v0.3 splits this into two halves.** A Python integration does the polling,
> scoring, and notifying; the Lovelace card visualises it. Both ship in this
> one HACS install. See [Architecture](#architecture) and, if you installed
> v0.2, [Upgrading from the card-only version](#upgrading-from-the-card-only-version).

## Architecture

A Lovelace card only runs while someone is looking at a dashboard, cannot hold
API keys, and is blocked by the browser from calling third-party APIs. None of
that works for "tell me to get in the car." So the work is split:

| | Runs | Does |
| --- | --- | --- |
| **`photography_events` integration** | Home Assistant, in the background | Polls Open-Meteo, eBird, iNaturalist and the wildflower hotlines, computes ephemeris, scores opportunities, gates on real drive time, publishes entities |
| **`photography-events-card`** | The browser | Renders the timeline, alerts, and planning view |

Because the integration publishes real entities
(`binary_sensor.photography_events_action_opportunity`,
`sensor.photography_events_best_sky_score`,
`calendar.photography_events_planning_calendar`), ordinary Home Assistant
automations can push to your phone whether or not any dashboard is open - which
is the whole point.

### What the backend needs from you

- **Nothing, to start.** Open-Meteo, iNaturalist and the three hotline pages
  need no key and no account, so sunset scoring, meteor showers, Milky Way
  windows, whale sightings and bloom reports all work the moment it is
  installed.
- **An eBird API key** ([free, instant](https://ebird.org/api/keygen)) for
  rare-bird alerts. Without it the bird category simply produces nothing.
- **A Google Maps API key** (optional) for real, traffic-aware drive times.
  Without one, drive times come from the per-zone baselines and, for sightings
  that are not at a zone, from a distance estimate calibrated against those
  baselines. See [Drive times](#drive-times).

### Live data sources

| Source | Key | Polled | Feeds |
| --- | --- | --- | --- |
| [Open-Meteo](https://open-meteo.com/) | none | hourly | Layered-cloud sunset scoring, astro cloud checks |
| [eBird API v2](https://documenter.getpostman.com/view/664302/S1ENwy59) | free | hourly | Locally rare birds across four counties |
| [iNaturalist API v1](https://api.inaturalist.org/v1/docs/) | none | hourly | Orca, blue, fin and humpback whale reports |
| Theodore Payne Wildflower Hotline | none | daily | Bloom reports |
| DesertUSA Wildflower Reports | none | daily | Desert bloom reports |
| California Fall Color | none | daily | Autumn colour reports |
| [Google Routes / Distance Matrix](https://developers.google.com/maps/documentation/routes) | yours | on demand, ≤2×/hour | Traffic-aware drive times |

Every service carries its own minimum interval, independent of the coordinator
cycle, so raising the update frequency cannot make any one of them be polled
harder than it allows. On a restart the sources are fetched in staggered groups
rather than all at once, and the daily scrapers are deferred to a background
task so setup never waits on them. A service that fails keeps serving its last
good payload and retries on a short backoff.

### Drive times

Two paths, and you can use either:

- **Default, no key.** The twelve zones carry measured baseline drive times.
  Sightings do not land on zones - a vagrant turns up at whatever lagoon it
  likes - so those are estimated from straight-line distance divided by an
  effective road speed *calibrated against the zone table itself*. Across the
  twelve known zones that estimator lands within about half an hour, worst case
  an hour and a half (Lake Tahoe). Displayed times are rounded coarsely so they
  cannot be mistaken for routed ones.
- **With a Google Maps API key.** Real routed, traffic-aware times replace both.
  Only opportunities inside the 48-hour action window are routed, deduplicated
  by location, so a dozen events at one zone cost one billable element.

Google split this API in half mid-life: **Distance Matrix cannot be enabled on
any Google Cloud project created after 1 March 2025**, and the current
replacement is the Routes API. Which one your key can call is a property of
your project, not of this integration, so both are implemented. Leave the
routing mode on `auto` and it tries Routes first, falls back to Distance
Matrix, and remembers which one answered.

A Home Assistant Lovelace card that looks out from your location (or an
overridden one) for photography-worthy sky and nature events: golden and blue
hour, moon phases, planets and their conjunctions, meteor shower peaks, solar
and lunar eclipses, Milky Way windows, comets you add as they are announced,
and a coarse bird migration season heuristic.

Its main job is to tell an ordinary sunset apart from the rare one where the
whole sky catches fire, and to say so loudly enough to get you out of the
house - see [Scoring the sky](#scoring-the-sky).

> The banner above is an illustration of the card's layout, not a screenshot.

It shows a near-term **24/48/72 hour** snapshot plus a longer **7-30 day**
outlook (21 days by default) in one scrollable timeline, grouped by day.

## What this card computes

- **Golden hour, blue hour, sunrise, and sunset** - computed directly, not read
  from `sun.sun`, so twilight and golden/blue hour boundaries are all available,
  each scored for how likely the sky is to actually light up (see
  [Scoring the sky](#scoring-the-sky))
- **Moon phase, illumination %, moonrise/moonset** - with New Moon ("dark sky,
  good for stars") and Full Moon ("moonrise-over-the-landscape", flagged as a
  Supermoon when notably close) called out specifically
- **Planets** - Mercury, Venus, Mars, Jupiter and Saturn, surfacing oppositions,
  greatest elongations, planet-planet and Moon-planet conjunctions, and a
  nightly "what's up" summary. Positions are computed, not tabulated
- **Meteor shower peaks** - the eleven major annual showers, scored by radiant
  altitude and moonlight interference on the peak night
- **Solar and lunar eclipses** - a curated table of upcoming eclipses (see
  [Data accuracy](#data-accuracy-and-limitations) below) with a local-visibility
  check computed from real moon/sun geometry for your location
- **Milky Way core season** - runs of dark, moonless nights when the galactic
  core clears a usable altitude, grouped into a window naming the best night
- **Comets and anything else announced rather than predicted** - via
  [`custom_events`](#comets-and-other-one-off-events)
- **Bird migration season** - a general spring/fall seasonal window for your
  hemisphere (see the caveat below - this is not live migration data)

Sky-quality scoring needs a `weather_entity` with a cloud-coverage forecast
(see Configuration). Without one, the card still shows every event, just
without a score.

## Scoring the sky

Most sunsets are pleasant. A few times a year the cloud is exactly right and
the whole sky goes up in colour. This card tries to tell those apart rather
than reporting "sunset: 7:14pm" every night.

Vivid sunsets need the low sun's light to reach cloud from underneath without
first crossing the hazy air near the ground, and they need mid- or high-level
cloud up there to catch it (NOAA's Storm Prediction Center has a good write-up
in "The Colors of Twilight and Sunset"). So the ingredients are: a clear path
to the horizon, **broken** rather than flat cloud, no rain-bearing deck, and
clean air - haze and smoke mute colour rather than enhancing it, contrary to
the popular belief.

Almost every Home Assistant weather integration reports a single aggregate
cloud percentage rather than per-layer cloud, so the card infers structure from
how much that number *moves* across the hours either side of the event:

| Signal | Effect |
| --- | --- |
| Mean cloud cover in the broken sweet spot (~25-65%) | Best base score; empty and overcast skies both score low |
| Large spread across the sampled hours | Bonus - broken, dynamic cloud is what catches light |
| Flat, unchanging cloud | Penalty - a uniform deck rarely lights up |
| High precipitation probability | Penalty - rain-bearing low cloud blocks the show |
| Unsettled earlier, clearing by sunset | Bonus - the classic "sky on fire" setup |
| Very high humidity | Penalty - haze mutes saturation |

Scores land in five tiers. The top one, **epic**, needs several signals to line
up at once, gets its own alert banner at the top of the card, and is meant to
be rare - if it fired every week it would not be worth acting on. Each score
also shows its reasoning ("47% cloud, clearing after an unsettled afternoon"),
so you can start recognising the pattern yourself.

## Get notified when the sky is worth chasing

A Lovelace card only tells you something while you are looking at a dashboard,
which is no use for a sky that peaks for fifteen minutes. Custom cards cannot
publish state back into Home Assistant, so the notification has to be a normal
automation reading your weather entity directly. This one mirrors the card's
core heuristic in a deliberately simpler form - moderate, broken cloud with low
rain chance - and fires a couple of hours before sunset:

```yaml
automation:
  - alias: Sunset could be worth chasing
    trigger:
      - platform: sun
        event: sunset
        offset: "-02:00:00"
    condition:
      - condition: template
        value_template: >-
          {% set f = state_attr('weather.home', 'forecast') or [] %}
          {% set near = f[:3] | map(attribute='cloud_coverage') | select('is_number') | list %}
          {% set rain = f[:3] | map(attribute='precipitation_probability')
                                | select('is_number') | list %}
          {{ near | length > 1
             and 25 <= (near | sum / near | length) <= 70
             and (near | max) - (near | min) >= 20
             and (rain | length == 0 or (rain | max) < 40) }}
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: Get to the beach
          message: >-
            Broken cloud and low rain chance into sunset - this one could go off.
```

Replace `weather.home` and `notify.mobile_app_your_phone` with your own
entities. Some integrations expose the hourly forecast through the
`weather.get_forecasts` action rather than a `forecast` attribute; if the
template comes back empty, fetch it in the automation with that action first.

This is intentionally a rough approximation - it cannot see the clearing-trend
or haze signals the card weighs. If you would rather have the card's exact
scoring available to automations, that needs a companion Home Assistant
integration publishing real sensor entities, which is a much larger piece of
work than a dashboard card; say the word and it can be built.

## Requirements

1. Home Assistant 2024.6 or newer
2. HACS
3. No API keys are required to start. An eBird key unlocks rare-bird alerts and
   a Google Maps key unlocks traffic-aware drive times; both are optional.

The integration installs one Python dependency, `beautifulsoup4`, used to parse
the three hotline pages. The card itself still stores no credentials, and its
only network request is to your own Home Assistant instance.

## Install with HACS

1. Open **HACS**
2. Open the three-dot menu and choose **Custom repositories**
3. Add `https://github.com/Tmatz27/Home-assistant-photography-events`
4. Choose the **Integration** category
5. Install **Photography Events**, then restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration** and pick
   **Photography Events**

The card is bundled inside the integration and registers itself as a dashboard
resource on setup, so there is no second install and no manual resource entry.

### "already_in_progress" when adding the integration

Versions before 0.5.1 shipped a config flow whose schema Home Assistant could
not render. The attempt failed but stayed registered, so every retry aborted
with `already_in_progress`.

Update to 0.5.1 or later, then **restart Home Assistant once**. In-progress
flows are held in memory, so the stale one clears only on a restart - after
which **Settings → Devices & services → Add integration → Photography Events**
works normally.

### Upgrading from the card-only version

v0.2 was a Dashboard-category repository; v0.3 is an Integration. HACS pins one
category per repository, so the old entry has to be removed and re-added:

1. In HACS, uninstall the old **Photography Events Card**
2. Remove `/hacsfiles/.../photography-events-card.js` from
   **Settings → Dashboards → ⋮ → Resources** if it is still listed
3. Re-add this repository as an **Integration** and follow the steps above

Existing `custom:photography-events-card` dashboard cards keep working - the
card is the same element, just served from the integration now.

## Configuration

Set up in the UI. Everything can be changed later from the integration's
**Configure** button:

| Option | Default | Description |
| --- | --- | --- |
| Enabled categories | all | Astronomy, sunsets, marine, mammals, birds, blooms, foliage |
| Max drive hours | `6.0` | Zones beyond this are dropped entirely |
| Sunset score threshold | `85` | Minimum colour score before a sunset is surfaced |
| Alert score threshold | `75` | Minimum score to trip the drop-everything flag |
| eBird API key | *(none)* | Optional, for rare-bird alerts |

### Target zones

Twelve fixed zones are evaluated on every update, each with a baseline drive
time and an approximate Bortle dark-sky class:

| Zone | Drive | Bortle | Specialities |
| --- | --- | --- | --- |
| Piedras Blancas (San Simeon) | 1.5 h | 3 | Elephant seals, otters, coastal sunsets |
| Channel Islands (Ventura) | 1.5 h | 4 | Pelagic whales, island endemics |
| Carrizo Plain | 2.0 h | 2 | Super blooms, tule elk, pronghorn, dark skies |
| Big Sur Coastline | 3.0 h | 3 | Fog inversions, gray whales, orcas |
| Antelope Valley | 3.0 h | 4 | Poppy bloom, desert astronomy |
| Pinnacles | 3.5 h | 3 | Condors, dark skies |
| Santa Cruz Redwoods | 4.0 h | 5 | Old-growth redwoods, coastal fog |
| Sequoia & Kings Canyon | 4.5 h | 2 | Sequoias, black bears |
| Death Valley | 6.0 h | 1 | Bighorn rut, salt flats, the darkest skies in reach |
| Yosemite Valley | 6.0 h | 3 | Granite, clearing storms, bears |
| Eastern Sierra (Bishop/June) | 6.0 h | 2 | Aspen colour, alpine lakes, Sierra bighorn |
| Lake Tahoe Basin | 6.0 h | 4 | Bear cubs, autumn colour |

## Notifications

The integration exposes everything an automation needs as attributes, so the
automation itself stays short:

```yaml
automation:
  - alias: "Photography: drop-everything alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.photography_events_action_opportunity
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          title: >-
            {{ state_attr('binary_sensor.photography_events_action_opportunity',
                          'event_name') }}
          message: >-
            {{ state_attr('binary_sensor.photography_events_action_opportunity',
                          'target_zone') }}
            ({{ state_attr('binary_sensor.photography_events_action_opportunity',
                           'drive_time') }} drive) ·
            {{ state_attr('binary_sensor.photography_events_action_opportunity',
                          'condition_summary') }}
            Pack: {{ state_attr('binary_sensor.photography_events_action_opportunity',
                                'gear_glass') }}
```

The flag only turns on when the score clears your alert threshold *and* the
zone is inside your drive limit, so it stays quiet unless it is genuinely worth
going.

## Add the card

Use the dashboard visual editor and choose **Photography Events Card**, or add:

```yaml
type: custom:photography-events-card
```

### The card is not in the "Add card" list

Work through these in order. Step 1 tells you which half of the problem you have.

**1. Did the file load?** Open the browser console (F12 → Console) on a
dashboard page and look for the version banner:

```
Photography Events Card v0.2.0
```

- **Banner present** → the card is registered. Skip to step 4.
- **Banner missing** → the browser never ran the file. Continue with step 2.

**2. Is the resource registered?** Go to **Settings → Dashboards → ⋮ (top
right) → Resources**. You need an entry of type **JavaScript Module**:

```
/hacsfiles/Home-assistant-photography-events/photography-events-card.js
```

If it is missing, add it with **+ Add Resource** using exactly that URL and the
**JavaScript Module** type. HACS adds this automatically only for
storage-mode dashboards.

**3. Running Lovelace in YAML mode?** HACS cannot register the resource for
you. Add it to `configuration.yaml` and restart:

```yaml
lovelace:
  mode: yaml
  resources:
    - url: /hacsfiles/Home-assistant-photography-events/photography-events-card.js
      type: module
```

**4. Clear the frontend cache.** The dashboard caches resources aggressively:

- Desktop: hard refresh with `Ctrl+Shift+R` (`Cmd+Shift+R` on macOS)
- Mobile app: **Settings → Companion App → Debugging → Reset frontend cache**,
  then fully close and reopen the app

**5. Search rather than scroll.** In the card picker, type `Photography` in
the search box. Custom cards are grouped near the bottom of the list, below
every built-in card, so they are easy to miss when scrolling.

If the console shows an error mentioning `photography-events-card` instead of
the version banner, please open an issue with that message.

## Card modes

The card has three modes. Two of them read the integration's entities; the third
computes everything in the browser and needs no integration at all.

```yaml
type: custom:photography-events-card
mode: action_hero          # timeline | action_hero | calendar_outlook
```

### `action_hero` - the drop-everything card

Renders **nothing at all** - no border, no empty box, no space in the layout -
until `binary_sensor.photography_events_action_opportunity` turns on. When it
does, it shows the event, the drive time, the confidence score and what to pack.

```yaml
type: custom:photography-events-card
mode: action_hero
# Optional. Left blank, the card finds the integration's sensor by name.
hero_entity: binary_sensor.photography_events_action_opportunity
show_gear: true
```

The drive time says where it came from. A figure Google routed reads
**"live traffic"**; the calibrated distance estimate reads **"estimated"**. They
are not the same claim and the card does not present them as though they were.

Put it at the top of a dashboard and forget about it - it is silent until it
is not.

### `calendar_outlook` - the year ahead

A scrollable, month-grouped timeline of everything the backend knows about,
out to 365 days: meteor showers, Milky Way windows, whale and rut seasons, bloom
and colour reports, and the national parks calendar below.

```yaml
type: custom:photography-events-card
mode: calendar_outlook
title: Planning
outlook_from_days: 0        # 0 keeps seasons that are already underway
outlook_through_days: 365
filter_toggles:
  astronomy: input_boolean.photo_show_astro
  marine: input_boolean.photo_show_marine
  mammals: input_boolean.photo_show_mammals
  birds: input_boolean.photo_show_birds
  blooms: input_boolean.photo_show_blooms
  foliage: input_boolean.photo_show_foliage
  parks: input_boolean.photo_show_parks
  sunset: input_boolean.photo_show_skies
```

Each entry in `filter_toggles` becomes a chip you tap to show or hide that
category. A category with no toggle configured is **always shown** - a
half-configured card can never silently swallow half your calendar.

Create the helpers once in `configuration.yaml` (or via
**Settings → Devices & services → Helpers**):

```yaml
input_boolean:
  photo_show_astro:
    name: Show astro
    icon: mdi:telescope
    initial: true
  photo_show_marine:
    name: Show whales
    icon: mdi:whale
    initial: true
  photo_show_mammals:
    name: Show mammals
    icon: mdi:paw
    initial: true
  photo_show_birds:
    name: Show birds
    icon: mdi:bird
    initial: true
  photo_show_blooms:
    name: Show blooms
    icon: mdi:flower
    initial: true
  photo_show_foliage:
    name: Show autumn colour
    icon: mdi:leaf-maple
    initial: true
  photo_show_parks:
    name: Show parks
    icon: mdi:pine-tree
    initial: true
  photo_show_skies:
    name: Show skies
    icon: mdi:weather-sunset
    initial: true
```

### `timeline` - the standalone view

The original mode, and still the default. It computes sun, moon, planet and
meteor geometry in the browser from your coordinates, needs no integration, and
makes no third-party requests. Everything under
[What this card computes](#what-this-card-computes) describes this mode.

### Why the backend modes hold no logic

A browser tab cannot keep an API key, cannot call eBird or Google past CORS, and
only runs while a dashboard is open. Anything sourced from a live service has to
arrive as entity state - so in these two modes the card draws what the
integration worked out, and does no computing of its own. They are also
push-driven: they start no timers and redraw only when one of the entities they
read actually changes.

## National parks and monuments

Twenty-one California parks and monuments are in the planning calendar, each
with its best and merely-good months, its distance and drive time from home, and
its dog rules.

The dog rules are there because they decide whether a trip happens at all: three
of these ban dogs outright, and most of the rest allow them only on pavement.
That is worth knowing before a five-hour drive rather than at the gate.

Parks behave differently from everything else in two ways, both deliberate:

- **They are never a drop-everything alert.** A park is a trip you plan, not a
  sky you chase, so park windows score below the alert threshold by
  construction and never enter the 48-hour action window.
- **They ignore the drive-time limit.** Half the list is further than any sane
  day trip - Redwood is nine and a half hours - and gating those out at six
  hours would defeat the point of listing them.

Drive times and distances are the measured ones for the Vandenberg origin rather
than anything computed. Coordinates are approximate main-area or visitor-centre
positions: good enough to put a park on a map or hand to a router, not a
trailhead. Edit the table at the top of
`custom_components/photography_events/parks.py` to add your own.

## Configuration

Every setting is available in the visual editor.

```yaml
type: custom:photography-events-card
title: Photography Events
location_name: Home
weather_entity: weather.home
outlook_days: 21
show_sun_events: true
show_moon_events: true
show_meteor_showers: true
show_eclipses: true
show_milky_way: true
show_bird_migration: true
```

| Option | Default | Description |
| --- | --- | --- |
| `title` | `Photography Events` | Card header text |
| `location_name` | *(none)* | Optional label shown under the title |
| `latitude` / `longitude` | *(your HA location)* | Override the observing point - see below |
| `elevation` | *(your HA elevation)* | Meters; refines rise/set for a horizon dip |
| `weather_entity` | *(none)* | A `weather.*` entity with forecast cloud coverage, used to score sunset/sunrise/meteor-shower conditions |
| `outlook_days` | `21` | How far ahead to look, from 7 to 30 days. The 24/48/72 hour snapshot always shows regardless of this setting |
| `show_sun_events` | `true` | Golden/blue hour, sunrise/sunset |
| `show_moon_events` | `true` | Moon phase, moonrise/moonset |
| `show_planets` | `true` | Oppositions, elongations, conjunctions, nightly planet summary |
| `show_meteor_showers` | `true` | Meteor shower peaks |
| `show_eclipses` | `true` | Solar/lunar eclipses |
| `show_milky_way` | `true` | Milky Way core windows |
| `show_bird_migration` | `true` | Bird migration season banner |
| `custom_events` | `[]` | Comets and other one-off targets - see below |

### Comets and other one-off events

Meteor showers recur every year and eclipses are computed centuries ahead, but
a bright comet is usually only known to be worth chasing a few months out. A
hardcoded comet list would be stale or wrong more often than right, so instead
you add one when it is announced and the card runs it through the same
visibility and moonlight scoring as everything else - how high it gets during
true darkness, and whether the Moon will wash it out:

```yaml
custom_events:
  - name: Comet C/2026 X1
    ra_deg: 250.4
    dec_deg: 20.1
    start: 2026-10-01
    end: 2026-11-15
    note: Expected around magnitude 4 near perihelion.
```

`name`, `ra_deg` and `dec_deg` are required (right ascension and declination in
degrees, as published in any comet ephemeris); `start`, `end` and `note` are
optional. Entries missing coordinates are skipped rather than breaking the
card. Coordinates are treated as fixed, which is fine over a week or two of a
slow-moving comet - for a fast one, update the entry as it moves.

### Why there's no "search within a 30 minute drive"

Every event type this card computes - golden hour, moon phases, meteor
showers, eclipse visibility - is essentially identical across a 30 minute
driving radius; astronomy doesn't change much over a few tens of kilometers.
What *does* change over that radius is which specific spot has a clear view
(an unobstructed ocean horizon, a dark sky away from streetlights), and that's
local geography this card can't know on its own.

Today, the `latitude`/`longitude`/`elevation` overrides are the tool for that:
point the card at your favorite nearby overlook instead of your house.
Letting you name and switch between several saved locations (e.g. for an
upcoming trip) is a natural next step but is intentionally not built yet -
tracked as a future enhancement.

## Data accuracy and limitations

- **Sun and Moon are computed locally**, not read from an external ephemeris
  service. The Sun uses Meeus chapter 25 apparent longitude (better than a
  hundredth of a degree) and the Moon the chapter 47 truncated ELP series with
  sixty periodic terms. Checked against published full-moon instants, the Moon
  lands within a minute on 2026-01-03 and two minutes on 2026-03-03. Rise, set
  and twilight times are good to a minute or two - reliable for planning a
  shoot, not survey-grade
- **Planet positions use two-body Keplerian propagation** from mean elements.
  Jupiter's 2026-01-10 and 2027-02-11 oppositions come out on the published
  instant; **Mars and Saturn run about a day late** (2027-02-19 and 2026-10-04
  respectively), because the mutual perturbations between the giant planets are
  not modelled. That is immaterial for deciding which nights to shoot - a
  planet is equally well placed for weeks either side of opposition - but read
  a quoted Moon-planet conjunction separation as approximate for those two
- **Sky-quality scoring is a heuristic, not a forecast model.** The backend
  reads Open-Meteo's low, mid and high cloud decks separately and scores the
  actual mechanism - high cloud as the canvas, low cloud as the blocker,
  humidity as the mute. The card, used standalone against a `weather_entity`,
  still only sees a single aggregate percentage and is correspondingly
  blunter. Treat "epic" as "worth looking outside", not a guarantee
- **Rare-bird alerts are eBird's "notable" feed**, which flags anything locally
  unusual - that includes genuinely out-of-range vagrants and merely
  out-of-season regulars. Reports are grouped per species and location, and the
  score rewards recent, repeated and reviewer-confirmed reports, because a bird
  seen by four people this morning is a very different proposition from one
  person's unreviewed report on Tuesday. It cannot tell you the bird is still
  there
- **Whale sightings come from iNaturalist**, which is presence-only data from
  whoever happened to be looking. No reports does not mean no whales; it often
  means nobody was on the headland with a phone
- **Bloom and autumn-colour reports are scraped from prose.** The parser reads
  the phrases these hotlines actually use, checks for negation ("past peak"
  contains "peak"), and attaches each to the nearest recognised place name.
  It is capped below the alert threshold on purpose: somebody wrote that
  sentence days ago, and it can never on its own tell you to get in the car.
  If a site is redesigned, the CSS selectors are collected in one table at the
  top of `field_reports.py`
- **Drive times are estimates unless you supply a Google Maps key** - see
  [Drive times](#drive-times) for the error bars
- **Meteor shower peak dates recur annually** and are hardcoded to their
  well-known average calendar date, which can drift by about a day year to
  year
- **The eclipse table is a manually curated, static list** (compiled from
  NASA/Wikipedia/EclipseWise eclipse predictions) covering upcoming eclipses
  into 2028. It needs periodic updates for eclipses further out, and you
  should verify exact timing and, for solar eclipses, whether your specific
  location falls in the path, against an authoritative source before making
  travel plans. Lunar eclipse visibility is a real computed check (is the
  Moon above your horizon); solar eclipse visibility only rules out the
  night side of Earth - it cannot tell you whether you're inside the actual
  path of totality/annularity
- **Bird migration is a coarse seasonal heuristic** (a general spring/fall
  date range for your hemisphere), not live migration data. For real-time
  nocturnal migration intensity, check Cornell Lab's BirdCast

## Privacy and security

- **No telemetry.** Nothing here reports back to the author or anyone else.
- **The card** makes no third-party requests at all. All its astronomy is
  computed in the browser, and its only network activity is the
  `weather/get_forecasts` websocket call to your own Home Assistant instance.
- **The integration does make third-party requests**, which is the point of it.
  It sends the target zones' coordinates to Open-Meteo, county codes to eBird,
  a coastal bounding box to iNaturalist, and plain GETs to the three hotline
  pages. If you configure a Google Maps key it also sends your home coordinates
  and the destinations being scored. Nothing else leaves your instance, and
  every source can be switched off by disabling its category.
- **API keys are stored by Home Assistant** in its config entry storage, the
  same place every other integration keeps them, and are never written to logs
  or entity attributes.
- Card-editor text inputs are escaped before rendering
- **No inline event handlers**, which keeps the card compatible with strict
  Content-Security-Policy setups

## Development

```bash
npm test
```

No build step is required. `photography-events-card.js` is the HACS release
file.

## Credits

Sun/moon position formulas follow well-known low-precision astronomical
algorithms described publicly on references such as aa.quae.nl - not copied
from any single library, but the same standard, widely-implemented math.

## License

MIT
