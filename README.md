# Photography Events

Photography Events is a Home Assistant integration and Lovelace card that acts as a regret-prevention system for photographers:

> Is something happening soon enough, close enough, unusual enough, and well-supported enough that I would regret missing it?

It is not an encyclopedia of every event or sighting. It keeps a short list of opportunities worth changing plans for, with a separate year planner and bird view for exploring further.

**0.16.0 is the first stable snapshot of this architecture.** It is intentionally published before broader installed-Home-Assistant and live-provider iteration, so real-world testing has a fixed version to work against. Automated validation and code review do not establish that every live source works in every installation.

The curated places and wildlife coverage focus on California, particularly trips from the Central Coast. Changing your home location changes the origin for calculations; it does not turn the catalog into worldwide coverage.

[Release notes](RELEASE_NOTES.md) · [Source validation and evidence limits](SOURCE_VALIDATION.md) · [Tracked phenomena](TRACKING.md)

## Signal → Phenomenon → Opportunity

| Stage | Meaning |
| --- | --- |
| **Signal** | Raw evidence: a sighting, field report, forecast, tide prediction, email or operator report. |
| **Phenomenon** | A curated photographic experience with a trigger policy: feeding behavior, a mass gathering, a bloom, a distinctive sky or a computed astronomical event. |
| **Opportunity** | That phenomenon at a time and place, assessed for evidence, conditions, access, safety and drive time. |

A sighting is evidence. A season is context. A photographic phenomenon is an event. Only a sufficiently assessed opportunity becomes **Can't Miss**. Species presence alone cannot confirm feeding, calving or another named behavior, and a high score cannot bypass the eligibility checks.

## Views

| View | What it is for |
| --- | --- |
| **Can't Miss** | The next seven days, usually 0–5 displayed rows. Eligibility is checked before ranking. A fully assessed empty week says **“Nothing worth changing plans for this week.”** Missing required data instead shows **assessment incomplete**, with reasons and held opportunities where available. |
| **Year Planner** | Long-range seasons, astronomy, tides, park windows and planning-only candidates. Broad seasons remain broad; available shooting windows retain their times and alternatives. |
| **Birds** | Separate Bird Spectacle, Bird Encounter and Bird Chase lists. |
| **Background signals** | Collapsed evidence and watch material beneath Can't Miss. A raw sighting is not promoted just because something was seen. |

Follow, Skip and **Seen it · Got the shot** apply to an occurrence and persist across dashboards and restarts. Skip and Seen suppress that occurrence; a future year's occurrence remains separate. Calendar views retain full date ranges, and the card distinguishes stale data from an empty result.

## Install with HACS

This repository is **one HACS Integration install**, including the card. Its `hacs.json` declares **Home Assistant 2024.11.0 or newer**; your installed HACS version may have its own requirements.

1. In HACS, open **Custom repositories** and add `https://github.com/Tmatz27/Home-assistant-photography-events` with type **Integration**.
2. Find **Photography Events** and install version **0.16.0**.
3. Restart Home Assistant.
4. Open **Settings → Devices & services → Add integration**.
5. Search for **Photography Events**.
6. Complete setup. API credentials are optional for loading the integration; their absence affects the evidence and checks described below.
7. Edit a dashboard, add a card and choose **Photography Events Card**.

See the [HACS custom-repository instructions](https://www.hacs.dev/docs/faq/custom_repositories/) for the repository dialog.

The integration automatically serves and registers `/photography_events/photography-events-card.js`. **No separate frontend HACS repository is needed.** If automatic registration fails, add that URL as a **JavaScript module** under the dashboard's resources, then refresh the browser. Manual registration is a fallback, not a normal installation step.

When upgrading an older installation, restart Home Assistant and refresh the dashboard. Saved category selections are preserved exactly. If you installed before Waves existed, enable `waves` once in the integration's options if you want it.

## Configuration

Setup and integration options expose the same fields. Home uses Home Assistant's configured latitude/longitude; if that location is unavailable, the packaged fallback is **Vandenberg SFB (34.7420, −120.5724)**.

| Field | Default / behavior |
| --- | --- |
| Enabled categories | All categories for a new setup. An explicit empty list means **none**. |
| Maximum drive hours | **6 hours**; the general drive budget. |
| Sunset drive hours | **1 hour**; can tighten, never expand, the general limit. Current sunset forecasting is at home. |
| Sunset score threshold | **85**; filters built-in sky candidates. Preferred-provider quality and the eligibility gate also matter. |
| Alert score threshold | **75**; retained for compatibility with unassessed score-based candidates. In the current assessed pipeline, eligibility decides the action flag; this slider cannot override it. |
| eBird API key | Optional; enables eBird evidence. |
| Google API key | Optional; enables routed drive times. |
| NPS API key | Optional at setup; needed to affirmatively clear dependent park access. |
| SunsetWx client ID | Optional provider credential, used with the client secret. |
| SunsetWx client secret | Optional provider credential, used with the client ID. |
| Routing mode | `auto` by default: try Google Routes, then legacy Distance Matrix. Other choices: `routes`, `distance_matrix`, `off`. |
| Field reports enabled | **On**; enables the public field-report sources. |

Available categories: `astronomy`, `sunset`, `marine`, `mammals`, `birds`, `blooms`, `foliage`, `rare_phenomena`, `parks`, `waves`.

### Optional credentials and drive estimates

- **eBird:** needed for eBird-powered bird evidence and features. Missing or withheld observations do not prove that birds are absent.
- **Google:** supplies routed travel times. Without it, the integration uses its calibrated distance/baseline estimates. The card identifies the basis and age of a route. An older route is not current traffic, and cannot alone keep an opportunity under the limit when the distance estimate disagrees.
- **NPS:** required to affirmatively clear park access for phenomena that depend on it. Without a key, affected opportunities may be held with access unknown.
- **SunsetWx:** an optional preferred sunset/sunrise forecast provider. The built-in local weather model remains the fallback.

None of these keys is required for the integration itself to load. Clearing a credential in options removes its effective value. A preferred or optional source failure does not automatically block a row; the outcome depends on which inputs that phenomenon requires.

## Add the card

A new card from the picker starts on **Can't Miss** when the integration's entities are available. For compatibility, an older YAML card without `mode` renders the planner. Set the mode explicitly when choosing a view:

```yaml
type: custom:photography-events-card
mode: action_hero
```

```yaml
type: custom:photography-events-card
mode: calendar_outlook
```

```yaml
type: custom:photography-events-card
mode: birds
```

The card normally discovers its entities. If yours were renamed, select them in the editor or set `cant_miss_entity` for Can't Miss/Birds and `outlook_entity` for the planner.

## Home Assistant entities

These are the default entity IDs; Home Assistant may retain a renamed ID or add a suffix if an ID is already in use.

| Entity | Purpose |
| --- | --- |
| `sensor.photography_events_next_opportunity` | The next listed opportunity and its time, place, score and source. |
| `sensor.photography_events_best_sky_score` | The highest generated local sunrise/sunset score and its context. |
| `sensor.photography_events_planning_outlook` | Planning count and the event payload used by the year planner. |
| `sensor.photography_events_can_t_miss` | Eligible occurrence count, short-list rows, assessment coverage, held rows, watches, signals and bird views. |
| `binary_sensor.photography_events_action_opportunity` | An eligible, unsuppressed opportunity in the nearer 48-hour action window. |
| `calendar.photography_events_planning_calendar` | Planning events with day ranges or actual shooting times as appropriate. |

The large planner and Can't Miss payload attributes are excluded from recorder history. They remain available to the card over Home Assistant's state connection. The backend continues calculating and updating entities even when no dashboard is open.

## Services / actions

### `photography_events.set_event_choice`

Supply `event_id` from an existing occurrence and a `choice`:

| Choice | Effect |
| --- | --- |
| `default` | Clear the saved preference. |
| `follow` | Mark the occurrence to follow. |
| `skip` | Suppress the occurrence because you are not going. |
| `seen` | Suppress it because you already got the shot. |

```yaml
action: photography_events.set_event_choice
data:
  event_id: "<event_id copied from an entity's event attributes>"
  choice: follow
```

### `photography_events.ingest_report`

Pass a field report or subscription email from a Home Assistant automation. The integration does not connect to your mailbox itself.

| Field | Meaning |
| --- | --- |
| `source` | Required: who supplied the report. |
| `body` | Required: the report's text. |
| `subject` | Optional message subject. |
| `category` | Optional category; otherwise inferred from the text. |
| `zone_id` | Optional zone context; it does not replace a precise place actually named in the report. |
| `received` | Optional ISO timestamp, defaulting to arrival now; anchors relative words such as “today.” It does not make old or undated evidence fresh. |
| `url` | Optional source link. |

Parsing is conservative. Animal, behavior, count, place and observation date must belong to the correct assertion. A plan, a negated report, an unrelated animal's behavior or a newly downloaded old report cannot confirm a phenomenon. Only unambiguous context is inherited; broad regional reports remain regional. Email content is parsed as evidence, never executed as instructions.

## Safety and access

NWS checks distinguish **safe**, **caution**, **unsafe** and **unknown** for the relevant exposure. Here, safe means the implemented warning check completed without an applicable hazard being flagged; it is not a guarantee that a location is safe to visit. Unreadable, incomplete or stale coverage cannot establish safety. Readable warnings still apply when another feature in the same response is malformed.

**Boat trips are intentionally held.** Marine-zone warning coverage is not integrated yet, so a boat phenomenon has marine safety unknown even when the land-alert feed is healthy.

Relevant Firefall, Yosemite and Sequoia-type phenomena need usable, current NPS access data. Incomplete pagination, stale or malformed records, unrecognized park associations or no key mean **access unknown**, not open. A usable closure blocks the opportunity. Check the linked official conditions before traveling.

## Forecast integrity and sunsets

A successful HTTP response is not enough. Near-term actionable opportunities need forecast timestamps and values that cover the actual event or required condition window. Duplicate or reversed timestamps, expired coverage, missing hours and unreadable required values leave that condition **unassessed**.

- **Valid unfavorable weather:** assessed, but the opportunity does not qualify on that condition.
- **Missing required weather:** assessment incomplete; it cannot masquerade as a quiet week.
- **Long-range planning:** remains available beyond operational forecast coverage, without inventing weather.

Conditions are checked at the relevant forecast point. Snow needs a dated observation and a usable future clearing hour; saying there is no clearing requires the full relevant 48-hour search coverage. Firefall's valley and evening light path are assessed separately from an unrelated sunrise probe.

Sunsets and sunrises are a **home/local feature**. A current SunsetWx prediction is preferred when configured, and covers only the sunrise or sunset it actually predicts. Its model timestamp is checked separately from the fetch timestamp; a fresh download cannot rescue an old model run. Otherwise the local weather model evaluates cloud layers and the light path. Provider percentages are quality scores, not encounter probabilities. Missing or stale optional air-quality data must not suppress an otherwise valid sunset.

## Astronomy and tides

The planner includes:

- Full-Moon instants, illumination, distance and apparent-size ranking within the year.
- Moonrise/moonset, azimuth, low-altitude timing and overlap with twilight.
- Meteor showers with changing peak dates and radiant geometry, and usable Milky Way shooting windows.
- Solar and lunar eclipses from a bundled NASA catalog for 2026–2035, plus planetary events.
- Published King Tide planning windows, with NOAA station-specific time/height enrichment when available, and predicted minus tides.

Actionable near-term meteor, Milky Way and full-Moon opportunities require weather that covers the relevant time. Geometry alone does not bypass that check. Long-range rows remain planning information. Lunar horizon bearings do not model terrain or guarantee a composition; eclipse screening does not provide exhaustive drivable sites or exact solar contacts, and planetary timings are approximate.

### Solar safety

**Camera or telescope optics need a special-purpose solar filter mounted securely over the front aperture. Unaided-eye viewing needs ISO 12312-2 eclipse glasses or a handheld solar viewer. These are different protections.**

Never use eclipse glasses as a camera filter, or look through optics while wearing them. Ordinary photographic ND filters and sunglasses are not solar protection. Only during actual totality, while inside the path of totality, may solar protection be removed; restore it before the bright Sun reappears. Partial and annular phases always require protection. Read [NASA's eclipse safety guidance](https://science.nasa.gov/eclipses/safety/).

## Birds

- **Bird Spectacle:** the behavior or concentration that makes an exceptional photograph, with sufficient evidence. It can reach Can't Miss only after the shared eligibility checks.
- **Bird Encounter:** repeated reports of an iconic bird around a public viewing area, without the evidence needed for a spectacle. It stays in the bird view.
- **Bird Chase:** a notable individual report, ranked as a lead worth investigating. The ranking is not a measured probability of finding or photographing the bird.

Private and sensitive locations are excluded as destinations. Obscured coordinates are not treated as precise places to travel to. Source privacy protections and missing reports limit what can be inferred.

## Gear

Packing plans separate ownership from suggestions:

| Label | Meaning |
| --- | --- |
| **Take / Optional / Skip** | Owned kit only. |
| **Worth adding or renting** | Unowned suggestions, at most two, each with a reason. |
| **Required** | Safety equipment, whether owned or not. |

The current owned-kit profile is **Sony A7R IV, 16–35 GM, 70–200 GM II, 200–600 G, 2× TC, DJI Osmo Pocket 3 and DJI Mini 3**. It is a packaged profile, not a configurable inventory in the setup form. The 2× teleconverter costs two stops and is not automatically preferred for wildlife. Drone guidance considers land restrictions, wildlife and wind; a recommendation is not permission to fly.

## Data sources and evidence limits

**Read [SOURCE_VALIDATION.md](SOURCE_VALIDATION.md) for the source-by-source register, freshness rules, product thresholds and explicit live-verification gaps.** Historical checks in that document are not certification of today's feeds.

| Source family | Role |
| --- | --- |
| Open-Meteo; optional SunsetWx | Weather, cloud layers and local sunset/sunrise quality. |
| NWS; NPS | Implemented warning checks and park-access information. |
| NOAA CO-OPS; published California King Tide dates | Tide predictions and longer-range planning windows. |
| NOAA NDBC; CDIP; NOAA OVATION | Offshore measurements, coastal wave-model guidance and an aurora nowcast. |
| eBird; iNaturalist | Bird and wildlife evidence with source privacy and observation dates. |
| Condor Express/operator reports; ingested reports | Dated reports of specified phenomena, subject to conservative parsing. |
| CDFW | Published expected grunion intervals; a schedule does not prove fish appeared. |
| Theodore Payne, DesertUSA, California Fall Color | Bloom and foliage reports, with each statement's own observation date. |
| USGS; bundled NASA catalogs | Basin-flow context and astronomical source data, within documented limits. |
| Optional Google routing | Routed travel time with provenance and age. |

## Known 0.16.0 limitations and validation status

- Marine-zone warnings are not integrated; boat phenomena remain held with safety unknown.
- Some evidence depends on credentials, and several live provider payloads still need installed-system confirmation.
- Moonbows remain candidates until viewpoint-validated predictions can be consumed. Basin flow is not proof of waterfall spray or exact viewing duration.
- Broad regional reports are not converted into invented precise destinations.
- Long-range weather is not invented. Published planning windows may lack operational times, access checks or weather until those inputs are available.
- The catalog and coverage are geographically curated, not universal.

The 0.16.0 implementation passed the repository's complete automated test/CI process and multiple independent adversarial code reviews. The final independent review reported **no material code findings — ready for installed HA / live validation**. This does **not** claim that every live provider has been verified. Tests include synthetic payloads through real Home Assistant coordinator cycles; installed-HA and live-source refinement continue after release.

## Architecture

```text
sources / geometry → signals → phenomena → evidence / conditions
  → safety / access / drive → eligibility → Can't Miss / Planner
  → Home Assistant entities → card
```

The backend runs independently of the dashboard. Source health, evidence freshness and event choices belong to the integration; the card presents the resulting assessments.

## Development and releases

Development is **main-only**. Pushes to `main` run **Validate**; publishing is a separate, explicit version-tag push or manual **Release** workflow. The release workflow reruns its checks, reads `RELEASE_NOTES.md`, attaches `photography-events-card.js` and preserves existing releases.

Keep `VERSION`, `manifest.json`, `package.json`, the source/generated card version, `CHANGELOG.md` and `RELEASE_NOTES.md` aligned. Edit card source under `custom_components/photography_events/www/src/`, then rebuild the bundled artifact.

With the existing test dependencies installed in a suitable environment:

```sh
python -m unittest discover -s tests -q
python -m pyflakes custom_components/photography_events/*.py tools/*.py
node --test tests/photography-events-card.test.mjs
node scripts/build-card.mjs
node scripts/build-card.mjs --check
node scripts/check-version.mjs
git diff --check
```

The full Python run includes Home Assistant tests when HA is installed; otherwise those tests skip. CI runs them separately on Python 3.12/HA 2024.11.3 and Python 3.13/HA 2025.3.4 using [the test constraints](tests/ha-constraints.txt). See [AGENTS.md](AGENTS.md) for repository invariants and [BROWSER_VALIDATION.md](BROWSER_VALIDATION.md) for the browser checks and their limits.
