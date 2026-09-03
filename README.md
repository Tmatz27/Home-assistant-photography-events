# Photography Events Card

![Photography Events Card](banner.svg)

A Home Assistant Lovelace card that looks out from your location (or an
overridden one) for photography-worthy sky and nature events: golden and blue
hour, sunrise/sunset color potential, moon phases, meteor shower peaks, solar
and lunar eclipses, Milky Way core season, and a coarse bird migration season
heuristic.

> The banner above is an illustration of the card's layout, not a screenshot.

It shows a near-term **24/48/72 hour** snapshot plus a longer **7-30 day**
outlook (21 days by default) in one scrollable timeline, grouped by day.

## What this card computes

- **Golden hour, blue hour, sunrise, and sunset** - computed directly, not read
  from `sun.sun`, so twilight and golden/blue hour boundaries are all available
- **Moon phase, illumination %, moonrise/moonset** - with New Moon ("dark sky,
  good for stars") and Full Moon ("moonrise-over-the-landscape", flagged as a
  Supermoon when notably close) called out specifically
- **Meteor shower peaks** - the eleven major annual showers, scored by radiant
  altitude and moonlight interference on the peak night
- **Solar and lunar eclipses** - a curated table of upcoming eclipses (see
  [Data accuracy](#data-accuracy-and-limitations) below) with a local-visibility
  check computed from real moon/sun geometry for your location
- **Milky Way core season** - nights the galactic core clears a usable altitude
  during astronomical darkness with a dark enough moon
- **Bird migration season** - a general spring/fall seasonal window for your
  hemisphere (see the caveat below - this is not live migration data)

Sunset/sunrise and meteor-shower quality badges only appear once you configure
a `weather_entity` that reports forecast cloud coverage (see Configuration).
Without one, the card still shows every event, just without a quality score.

## Requirements

1. Home Assistant 2024.6 or newer (for the `weather/get_forecasts` websocket
   command used for optional sky-quality scoring)
2. HACS
3. Nothing else - no external API keys, no companion integration

The card does not store credentials and does not call any external service.
The only network request it makes is to your own Home Assistant instance
(the `weather/get_forecasts` websocket command, and only if you configure a
`weather_entity`).

## Install with HACS

1. Open **HACS**
2. Open the three-dot menu and choose **Custom repositories**
3. Add `https://github.com/Tmatz27/Home-assistant-photography-events`
4. Choose the **Dashboard** category
5. Install **Photography Events Card**
6. Refresh the browser

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
Photography Events Card v0.1.0
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
| `show_meteor_showers` | `true` | Meteor shower peaks |
| `show_eclipses` | `true` | Solar/lunar eclipses |
| `show_milky_way` | `true` | Milky Way core season |
| `show_bird_migration` | `true` | Bird migration season banner |

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

- **Sun/moon positions are computed locally** with well-known low-precision
  formulas (the same family described on public references like aa.quae.nl's
  "Position of the Sun/Moon" pages), not read from an external ephemeris
  service. Expect rise/set and twilight times to be accurate to within a
  minute or two - reliable enough for planning a shoot, not survey-grade
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

- **No telemetry, no third-party requests.** All astronomy is computed in the
  browser. The only network activity is the `weather/get_forecasts` websocket
  call to your own Home Assistant instance, and only if you configure
  `weather_entity`
- **No credentials of any kind** are stored or required
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
