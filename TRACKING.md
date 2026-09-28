# What this integration actually tracks

_Generated from the code by `tools/generate_tracking_inventory.py`. Every date,
evidence level and link below is read out of the modules that run, so this file
cannot drift from the thing it describes._

Generated 2026-09-28.

## How to read this

Everything tracked carries an **evidence level**, and that decides what it is
allowed to do. This is the whole design: a date being on a calendar is not a
reason to drive anywhere.

| Evidence | What the dates rest on | May it raise an alert? |
| --- | --- | --- |
| **computed** | Orbital geometry. Verifiable to the minute against any ephemeris. | Yes, on its own. |
| **calendar_reliable** | A documented, highly repeatable annual cycle published by the site's managers or monitors. | Inside its documented core window only (≤ 40 days, sourced). |
| **live** | A *search season* - when to start watching. The dates alone are an estimate. | Only once evidence satisfies its trigger policy (species presence is not behaviour). |
| **static** | A calendar estimate. No feed anywhere publishes this. | Never by date or presence; only a dated, located report of the behaviour itself. |

Since 0.16.0 the evidence level is only half the rule. Each curated phenomenon also
has a **trigger policy** and a **product class** (section 3a), and nothing reaches the
Can't Miss dashboard without passing a hard gate: curated class, policy satisfied,
inside seven days, inside the drive limit (planning-only rows are not exempt),
significance at or above the floor, and no active NWS warning at the place.

Corroboration means a reported sighting of the named species within **120 km** in the last **14 days**. Without one, a live window is capped at 60 and marked planning-only.

Inside **60 days** every window switches from its background season to concrete
dates, locations, gear, and a plain statement of what has and has not been confirmed.
Beyond it you get the broad season, because that is genuinely all anyone can say.

## 1. Computed from geometry

Nothing here needs a network. It is solved from the ephemeris in `astronomy.py`,
which is Meeus chapters 25 (solar) and 47 (lunar, 60 periodic terms).

### Meteor showers

Stored as **solar longitude**, not as a date. A stream sits at a fixed point in the
Earth's orbit; the calendar date it falls on slides by up to a day with the leap
cycle. Longitudes are the IMO Working List values, which the IMO publishes for the
equinox J2000.0, so the code precesses them to the equinox of date before solving -
worth about 0.35 degrees today, which is eight hours of Sun.

| Shower | λ☉ (J2000) | Published ZHR | Peak 2026 (UT) | Peak 2027 (UT) | Alerts? |
| --- | --- | --- | --- | --- | --- |
| Quadrantids | 283.15° | 120/hr | 03 Jan 21:18 | 04 Jan 03:26 | yes |
| Perseids | 140.0° | 100/hr | 13 Aug 02:05 | 13 Aug 08:12 | yes |
| Geminids | 262.2° | 150/hr | 14 Dec 13:45 | 14 Dec 19:53 | yes |
| Lyrids | 32.32° | 18/hr | 22 Apr 19:35 | 23 Apr 01:42 | planning only |
| Eta Aquariids | 45.5° | 50/hr | 06 May 09:06 | 06 May 15:13 | planning only |
| Orionids | 208.0° | 20/hr | 21 Oct 18:28 | 22 Oct 00:35 | planning only |
| Leonids | 235.27° | 15/hr | 17 Nov 23:50 | 18 Nov 05:58 | planning only |
| Ursids | 270.66° | 10/hr | 22 Dec 21:15 | 23 Dec 03:22 | planning only |

The quoted rate on the card is **not** the ZHR. ZHR assumes the radiant at the
zenith and perfect skies; the card scales it by the sine of the radiant altitude at
your site, so the Geminids' 150 becomes roughly 79/hr with the radiant at 32°.

Verify against: <https://www.imo.net/resources/calendar/>

### Milky Way core

Galactic centre at RA 266.4168°, Dec -29.0078° (Sgr A*).
A night is reported as the **intersection** of three independent conditions, not as
the span of astronomical darkness:

- sun below -18°,
- core above 15°,
- moon down, or under 20% illuminated.

There is also a **lunar look-ahead**: a cloudless night with a bright moon is capped
at 75 when a night inside the next 10 days has the moon under
25%. Moon phase next week is far more certain than cloud tonight, and
without this the model says "go now" on the worse of the two.

### Grunion runs

Run nights are the 4 nights beginning the night after each new and full moon,
inside the CDFW season. The **hour** comes from live NOAA tide predictions -
runs start one to two hours after the night high tide, and without a tide table the
card says the hour is unknown rather than inventing one.

Verify against: <https://wildlife.ca.gov/Fishing/Ocean/Regulations/Grunion>

### Eclipses

45 events from NASA's catalogues covering 2026-2035, 16 of them with published central-path coordinates. Times are the NASA
catalogue's TD less its published Delta T, so approximate UT to about a minute.

A **solar** eclipse is only ever reported at a *vetted* site - your Home Assistant
location or one of the zones - that falls inside the published central path. A
centreline coordinate in the middle of an ocean or on a roadless ridge is not
somewhere anybody can stand, and treating one as a destination is how a calendar
sends you to a point in the sea.

**No central solar path in this catalogue is drivable from here.** The nearest any
of them comes is **4,101 km** (2031-11-14, hybrid) -
a flight, not a drive. So an empty solar-eclipse list is the correct answer for the
whole of this catalogue's range, not a broken feed. Extending the catalogue past
2035 is what changes that.

Lunar eclipses are unaffected: they are visible from wherever the Moon is up, and
the umbral phase is intersected with local Moon altitude. Penumbral eclipses are
excluded - the Moon only grazes the outer shadow and a camera records a full Moon.

Verify against: <https://eclipse.gsfc.nasa.gov/SEcat5/SE2001-2100.html>

## 2. Sky quality (sunset, sunrise, and cloud gating for astro)

Rebuilt around where the light actually comes from. A sunset has two separate
requirements in two separate places:

- **The canvas**, overhead - high and mid cloud to catch the light.
- **The light path**, upstream - a gap roughly 200 km toward the sun, where the
  beam grazes the surface. This one is a gate: if it is shut, nothing overhead
  matters. On this coast it is usually the offshore marine layer, and it is invisible
  from your own forecast.

Two extra probe points per zone are fetched for this, on the sun's own azimuth at the
event, mirrored for sunrise. Without them the score falls back to the local deck, is
capped at 88, and is labelled so on the card.

Measured inputs, all from Open-Meteo (free, no key):

- `cloud_cover`
- `cloud_cover_low`
- `cloud_cover_mid`
- `cloud_cover_high`
- `relative_humidity_2m`
- `precipitation_probability`
- `visibility`
- `weather_code`
- `snowfall`
- `temperature_2m`
- `wind_speed_10m`
- `aerosol_optical_depth`, `dust` (air-quality endpoint) - decides saturation.

A sky only raises an alert when it is a **standout**: at least 82, and within
3 points of the best in the forecast window, with a modelled light path.
"Is this a good sunset" is the wrong question; "is this the one to go out for" is
the right one, and it is comparative.

Verify against: <https://open-meteo.com/en/docs> and <https://open-meteo.com/en/docs/air-quality-api>

## 3. Biological windows

24 entries. Each carries a background season (informational, never scored)
and a concrete peak window (the only thing that scores).

### Documented annual cycles (`calendar_reliable`)

The core window of a cycle the site's managers publish. Species presence is not needed for the behaviour; the tule elk rut additionally needs a recent report near the site for the encounter.

| Phenomenon | Peak window | Days | Background season | Corroborated by | Where to verify |
| --- | --- | --- | --- | --- | --- |
| Harbor seal pupping, Carpinteria | 15 Feb – 25 Mar | 38 | Beach closed 1 December to 31 May; births mostly February and March | _Phoca vitulina_ | [1](https://carpinteriaca.gov/parks-and-recreation/carpinteria-harbor-seal-rookery/) [2](https://carpinteriasealwatch.org/information/) |
| Tule elk rut | 15 Sep – 10 Oct | 25 | August to October | _Cervus canadensis nannodes_ | [1](https://www.blm.gov/visit/carrizo-plain-national-monument) [2](https://www.nps.gov/thingstodo/tule-elk-viewing-point-reyes.htm) |
| Sandhill crane sunset fly-in | 10 Dec – 18 Jan | 39 | October to February; USFWS says December to February is best | _Antigone canadensis_ | [1](https://www.fws.gov/refuge/merced) [2](https://wildlife.ca.gov/Lands/Places-to-Visit/Woodbridge-ER) [3](https://ebird.org/species/sancra) |
| Elephant seal bull battles and pupping | 25 Dec – 31 Jan | 37 | December to March | _Mirounga angustirostris_ | [1](https://elephantseal.org/whats-happening-now/) [2](https://elephantseal.org/birthing-and-breeding/) |

### Live-verified windows (`live`)

These may alert, but only once a sighting corroborates them. Until then they are shown as watch windows and capped at planning level.

| Phenomenon | Peak window | Days | Background season | Corroborated by | Where to verify |
| --- | --- | --- | --- | --- | --- |
| Gray whale southbound migration | 5 Jan – 25 Jan | 20 | December to February | _Eschrichtius robustus_ | [1](https://www.fisheries.noaa.gov/west-coast/science-data/gray-whale-population-abundance) [2](https://whalesafe.com/) [3](https://www.fisheries.noaa.gov/resource/tool-app/whale-alert) |
| Anza-Borrego desert bloom ⚠︎ moves year to year | 20 Feb – 15 Mar | 23 | February to April, entirely rainfall dependent | — | [1](https://theodorepayne.org/wildflower-hotline/) |
| Death Valley superbloom ⚠︎ moves year to year | 1 Mar – 25 Mar | 24 | February to April, only in superbloom years | — | [1](https://theodorepayne.org/wildflower-hotline/) |
| Antelope Valley poppy bloom ⚠︎ moves year to year | 20 Mar – 15 Apr | 26 | March to May | — | [1](https://theodorepayne.org/wildflower-hotline/) |
| Carrizo Plain valley and Temblor Range bloom ⚠︎ moves year to year | 25 Mar – 20 Apr | 26 | March to May | — | [1](https://theodorepayne.org/wildflower-hotline/) |
| Gray whale mothers and calves northbound | 5 Apr – 10 May | 35 | March to May | _Eschrichtius robustus_ | [1](https://www.fisheries.noaa.gov/west-coast/science-data/gray-whale-condition-and-calf-production) [2](https://www.fisheries.noaa.gov/west-coast/science-data/gray-whale-population-abundance) [3](https://www.fisheries.noaa.gov/resource/tool-app/whale-alert) |
| Bigg's transient orcas hunting | 20 Apr – 25 May | 35 | April to June | _Orcinus orca_ | [1](https://whalesafe.com/) [2](https://www.fisheries.noaa.gov/resource/tool-app/whale-alert) [3](https://pacificwhale.org/what-we-do/research/learn-about-marine-life/whale-dolphin-tracker-live-sightins-map/) |
| Blue whale feeding aggregation | 15 Jul – 10 Sep | 57 | May to October (NOAA feeding season); watch window mid-Jul to mid-Sep | _Balaenoptera musculus_ | [1](https://whalesafe.com/) [2](https://www.fisheries.noaa.gov/west-coast/marine-mammal-protection/whalewatch) [3](https://www.fisheries.noaa.gov/resource/tool-app/whale-alert) |
| Humpback lunge feeding | 1 Aug – 15 Oct | 75 | March to November (NOAA feeding season); watch window Aug-mid Oct | _Megaptera novaeangliae_ | [1](https://whalesafe.com/) [2](https://www.fisheries.noaa.gov/resource/tool-app/whale-alert) [3](https://pacificwhale.org/what-we-do/research/learn-about-marine-life/whale-dolphin-tracker-live-sightins-map/) |
| Eastern Sierra aspen, high elevation ⚠︎ moves year to year | 25 Sep – 5 Oct | 10 | Late September to mid October | — | [1](https://www.californiafallcolor.com/) |
| Eastern Sierra aspen, mid elevation ⚠︎ moves year to year | 5 Oct – 18 Oct | 13 | Early to mid October | — | [1](https://www.californiafallcolor.com/) |
| Northern passes aspen ⚠︎ moves year to year | 10 Oct – 25 Oct | 15 | Mid to late October | — | [1](https://www.californiafallcolor.com/) |
| Pismo monarch butterfly roost | 15 Nov – 31 Dec | 46 | November to mid-February; historically peaks Thanksgiving to Christmas | _Danaus plexippus_ | [1](https://westernmonarchcount.org/) [2](https://www.parks.ca.gov/?page_id=30273) [3](https://xerces.org/blog/everything-you-need-to-know-about-visiting-overwintering-monarchs) |
| Bald eagles fishing, Cachuma Lake | 1 Dec – 10 Feb | 71 | November to February (county naturalist eagle cruises) | _Haliaeetus leucocephalus_ | [1](https://www.countyofsb.org/parks) |
| Common dolphin calving in the mega-pods | 15 Dec – 28 Feb | 75 | Winter, after a 10-11 month gestation | _Delphinus delphis_, _Delphinus capensis_ | [1](https://pacificwhale.org/what-we-do/research/learn-about-marine-life/whale-dolphin-tracker-live-sightins-map/) [2](https://www.fisheries.noaa.gov/resource/tool-app/whale-alert) |

### Estimates nothing can confirm (`static`)

**These never alert on a date or on species presence.** No feed publishes them. Only a dated, located report of the behaviour itself (for example a sow with cubs) can activate one; otherwise they stay in the planner as estimates.

| Phenomenon | Peak window | Days | Background season | Corroborated by | Where to verify |
| --- | --- | --- | --- | --- | --- |
| Yosemite Horsetail Fall firefall ⚠︎ moves year to year | 12 Feb – 26 Feb | 14 | Mid-February only | — | [1](https://www.nps.gov/yose/planyourvisit/horsetailfall.htm) |
| California grunion run ⚠︎ moves year to year | 1 Apr – 15 Jun (season gate only) | see §1 | March to August | — | [1](https://wildlife.ca.gov/Fishing/Ocean/Regulations/Grunion) |
| Black bear sows with new cubs | 15 Apr – 10 Jun | 56 | March to July; CDFW puts den emergence at March-May | _Ursus americanus_ | [1](https://wildlife.ca.gov/Conservation/Mammals/Black-Bear) [2](https://keepbearswild.org/bear-tracker/) [3](https://www.tahoebears.org/learn-more) |
| Desert bighorn sheep rut | 1 Aug – 15 Sep | 45 | July to October | _Ovis canadensis nelsoni_ | [1](https://wildlife.ca.gov/Conservation/Mammals/Bighorn-Sheep/Desert/Natural-History/life-history) |
| Sierra bighorn sheep rut | 1 Nov – 10 Dec | 39 | October to December | _Ovis canadensis sierrae_ | [1](https://wildlife.ca.gov/Conservation/Mammals/Bighorn-Sheep/Sierra-Nevada/Recovery-Program) |

### 3a. Trigger policies and product classes

Curated in `curation.py`. Significance floor for Can't Miss: **70**.
Thresholds are sourced or labelled product thresholds; see DISCOVERY_AUDIT.md.

| Phenomenon | Significance | Policy | Best class | Why this policy |
| --- | --- | --- | --- | --- |
| Local aurora | 95 | `conditions_required` | cant miss | OVATION nowcast at the local cell with darkness; short notice by nature. |
| Orcas hunting | 95 | `behavior_report_required` | cant miss | Hunting needs a behaviour report. Orca presence alone may qualify separately as exceptional presence (see orca_presence). |
| Solar eclipse | 95 | `computed` | planner | Central-path sites need their own contact calculation and road check; planner until then. |
| Total lunar eclipse | 92 | `computed` | cant miss | NASA catalog geometry with local visibility. |
| Blue whale feeding aggregation | 90 | `aggregation_required` | cant miss | A single blue whale is intrinsically notable, but the photograph worth a trip is the krill aggregation that holds several close to boats; that needs a dated aggregation report. |
| Death Valley superbloom | 90 | `live_confirmation_required` | cant miss | As above; perhaps once a decade. |
| Elephant seal breeding & pupping | 90 | `calendar_reliable` | cant miss | Friends of the Elephant Seal document a stable annual cycle: bulls from November, births mid-December to early February, peak births late January, fights December-January. Inside that core window the calendar is reliable; a dated docent report can open it earlier. |
| Horsetail Fall firefall | 90 | `conditions_required` | cant miss | Needs every condition at once: an evening inside the published mid-February alignment window; a dated report of water on Horsetail Fall (Merced discharge is a different drainage and is never used); local cloud at sunset of 25% or less and an open upstream light path (product thresholds); no reported closure of the viewing area. NWS warnings block through the safety gate. |
| Orcas reported | 88 | `exceptional_presence` | cant miss | Orcas are rare enough off this coast that coherent recent presence is itself worth a boat trip. Product thresholds: two independent observers within 25 km of each other inside 72 h, or one dated operator report within 36 h. A single community observation, even research grade, is a background signal and at most a watch: reports far apart are different places, not stronger evidence. |
| Bioluminescent surf | 85 | `live_confirmation_required` | cant miss | No dependable date exists. A credible report within three days, darkness and a Moon under half lit are all required. |
| Black bear sows with cubs | 85 | `behavior_report_required` | cant miss | Bears are seen year-round; a generic bear sighting is not evidence of cubs. Only a report of a sow with cubs in a public area qualifies. Den locations are never used. |
| California condors | 85 | `exceptional_presence` | bird spectacle | NPS says there is no guarantee of a sighting. Repeated reports at a public viewing area make an encounter plausible (bird encounter); several birds together or a behaviour report make it a spectacle. Product thresholds. |
| Carrizo Plain superbloom | 85 | `live_confirmation_required` | cant miss | Entirely rainfall-dependent; a dated strong bloom report is required. |
| Fresh snow then clearing | 85 | `forecast_plus_confirmation` | cant miss | A snowfall forecast is a watch; observed accumulation (a dated report) plus a clearing forecast confirms. Product threshold: 10 cm modelled in 24 h followed by 30 % cloud or less within 18 h. |
| Humpback lunge feeding | 85 | `behavior_report_required` | cant miss | Humpbacks are common here for months; the photograph is the bait-ball lunge, which only a dated behaviour report can establish. Presence corroborates the watch, never the behaviour. |
| Sandhill crane fly-in | 85 | `calendar_reliable` | bird spectacle | USFWS Merced NWR: up to 20,000 cranes and 60,000 geese winter there, and the sunset fly-in is 'a predictable daily spectacle', best December-February. |
| Tule elk rut | 85 | `calendar_reliable` | cant miss | NPS: the rut runs August-October, peaking late August-September, so behaviour is reliable in the peak window. Encounter at Carrizo is not - the herd is dispersed - so a recent elk report near the site is also required (product rule). |
| Yosemite moonbow | 85 | `conditions_required` | cant miss | Sky geometry is computed; spray and the viewpoint light path are not. A dated flow report makes a sky night a supported candidate (watch). Only a viewpoint-validated prediction - the published Lower/Upper Fall timetables model the valley skyline - plus a clear-sky forecast could make it actionable, and no such timetable can be consumed yet (they are published as page images). |
| Major meteor shower | 82 | `computed` | cant miss | Peak is computed from solar longitude; conditions (moon, radiant, cloud) decide. |
| Pismo monarch clusters | 82 | `aggregation_required` | cant miss | The season is predictable, the numbers are not: recent Pismo counts have been in the hundreds. Requires a dated count of at least 1,000 at the grove (product threshold), plus a cold dawn: Xerces notes monarchs cannot fly below about 55 °F, so they stay clustered. |
| Common dolphin megapod | 80 | `aggregation_required` | cant miss | Presence is ordinary; a dated operator report of one explicitly sized pod of thousands is the aggregation. Product threshold: at least 1,000 dolphins written against one pod; the word 'megapod' alone, or a pod of 20, is not it. |
| Eastern Sierra aspen, high elevation | 80 | `live_confirmation_required` | cant miss | Timing moves with temperature and wind; a dated peak report is required. Undated hotline text is shown as reported, date unknown. |
| Eastern Sierra aspen, mid elevation | 80 | `live_confirmation_required` | cant miss | As above. |
| Exceptional Pacific swell | 80 | `forecast_plus_confirmation` | cant miss | The CDIP forecast is a watch; the calibrated NDBC 46011 measurement confirms the swell is here. |
| Mass goose lift-off | 80 | `count_threshold` | bird spectacle | Tens of thousands of geese winter at Merced NWR, but a lift-off is not predictable; a count of thousands at the refuge (product threshold 1,000) or a lift-off report is required. |
| Antelope Valley poppy bloom | 78 | `live_confirmation_required` | cant miss | As above. |
| Anza-Borrego desert bloom | 78 | `live_confirmation_required` | cant miss | As above. |
| Gray whale mothers and calves | 78 | `behavior_report_required` | cant miss | Gray whales pass for months; the mother-calf pairs hugging the surf line are the photograph, and only a report of pairs close in says they are. |
| Yosemite frazil ice | 78 | `forecast_plus_confirmation` | cant miss | NPS: needs high waterfall flow and nights below freezing, mostly April, usually before 9 am. A freezing forecast is only a watch; a dated report confirms. |
| Bald eagles fishing at Cachuma Lake | 75 | `behavior_report_required` | bird spectacle | Wintering eagles are reliably present; eagles actively fishing, or several together, is the photograph and needs a report. |
| Desert bighorn rut | 75 | `behavior_report_required` | planner | Sparse animals on rough ground; no source reports it. Planning only. |
| Largest full Moon of the year | 75 | `conditions_required` | cant miss | The year's closest full Moon is a computed fact; it earns the dashboard only when the moonrise falls near sunset (a lit landscape and a low, large-looking Moon) and the forecast is not overcast. |
| Sierra bighorn rut | 75 | `behavior_report_required` | planner | Endangered, few hundred animals on steep ground; positions are not published and should not be. Planning only. |
| Thunderstorm potential | 75 | `forecast_plus_confirmation` | watch | No lightning detection feed is connected; forecast thunder is a watch only. |
| Common dolphin calving | 72 | `behavior_report_required` | cant miss | Common dolphins are present most days; newborn calves in the pods need a report. |
| Exceptional sunset | 72 | `conditions_required` | cant miss | Local to home only. A purpose-built provider's top tier, or the local model's modelled-light-path standout, is required; ordinary good sunsets happen most weeks. |
| Harbor seal pupping | 72 | `calendar_reliable` | cant miss | Carpinteria Seal Watch: births mostly February-March at a monitored rookery (~60 pups a year) below a public overlook; the beach is closed 1 Dec-31 May by City Ordinance 470. |
| Milky Way core night | 70 | `computed` | cant miss | A recurring monthly condition; only a drop-everything night (new Moon, forecast clear, dark site) reaches the dashboard. |
| Northern passes aspen | 70 | `live_confirmation_required` | cant miss | As above; beyond six hours in most traffic. |
| Grunion run | 60 | `live_confirmation_required` | planner | CDFW publishes expected runs, not observed ones; fish may not appear on a given beach. |
| Partial lunar eclipse | 60 | `computed` | planner | Visible but modest. |
| Gray whale southbound migration | 55 | `live_confirmation_required` | planner | Distant blows from a headland are planning context, not a regret event. |
| King Tide | 55 | `computed` | planner | Published Coastal Commission dates; a compound note for swell and full-Moon events. |
| Hotline report | 50 | `live_confirmation_required` | planner | A report that names no curated phenomenon stays planning context. |
| Minus tide | 50 | `computed` | planner | Tide predictions are exact; a monthly condition, so planning only. |
| Minor meteor shower | 45 | `computed` | planner | Rates too low to change plans. |
| Full Moon | 40 | `computed` | planner | Monthly; planning facts only. |
| Park season | 30 | `planning_context` | planner | A park is a place, not an event. |

## 4. National parks and monuments

Trips rather than evenings: never gated on drive time, never eligible for a
drop-everything alert. Seasons are about road access, heat and snow rather than
biology, which is genuinely a matter of months. Closures are live.

| Unit | Best months | Closure feed |
| --- | --- | --- |
| Channel Islands NP | Sep–Oct | NPS alerts API |
| Carrizo Plain NM | Mar–Apr | **not covered** – Bureau of Land Management |
| Pinnacles NP | Mar–May | NPS alerts API |
| Sequoia NP | Jun–Aug | NPS alerts API |
| Kings Canyon NP | Jun–Aug | NPS alerts API |
| Giant Sequoia NM | Jun–Aug | **not covered** – US Forest Service |
| Joshua Tree NP | Feb–Apr | NPS alerts API |
| Yosemite NP | May, Sep–Oct | NPS alerts API |
| Death Valley NP | Jan–Feb | NPS alerts API |
| Devils Postpile NM | Jul–Aug | NPS alerts API |

## 5. Every external source, and what it is for

| Source | Used for | Key | Polled no more than |
| --- | --- | --- | --- |
| NOAA NDBC 46011 | Measured offshore significant wave height, period and direction | none | 30 min |
| CDIP B1500 | Experimental nearshore forecast; run age checked | none | 3 h |
| NWS active alerts (California) | Safety gate on every Can't Miss row; coastal advisories for swell | none | 1 h |
| SunsetWx Sunburst API | Home sunset/sunrise quality (primary when configured) | yours, optional | every 3 h |
| NOAA OVATION | Conservative local aurora model signal | none | 15 min |
| Condor Express RSS | Explicitly dated and sized megapod reports only | none | 3 h |
| CDFW grunion schedule | Published expected intervals at Santa Barbara | none | 24 h |
| Open-Meteo forecast | Layered cloud at each zone and both light-path probes | none | every 60 min |
| Open-Meteo air quality | Aerosol optical depth and dust - colour saturation | none | every 3 h |
| eBird notable observations | Bird Chase list; corroboration | free, instant | every 60 min |
| eBird species observations | Condor, bald eagle, crane and goose counts for bird spectacles | same key | every 6 h |
| iNaturalist observations | Whale, dolphin and mammal corroboration | none | every 60 min |
| Theodore Payne Wildflower Hotline | Whether a bloom is actually happening | none (scraped) | every 24 h |
| DesertUSA wildflower reports | Desert bloom reports | none (scraped) | every 24 h |
| California Fall Color | Aspen colour reports | none (scraped) | every 24 h |
| NOAA CO-OPS tide predictions | Tidal context; CDFW is the authority for expected grunion intervals | none | every 12 h |
| NPS alerts API | Road and area closures - the trip-killer nothing else sees | free | every 6 h |
| Google Routes API | Traffic-aware drive times | yours, optional | every 30 min |
| Any subscription email | Whatever a mailing list reports, via the IMAP integration and `photography_events.ingest_report` | none | whenever it arrives |

Requests are staggered into groups on startup so a Home Assistant restart does not
fire everything at once, and each source backs off on its own after a failure.

## 6. Known gaps

Written down rather than papered over.

- **Whale Safe's public API does not carry whale data.** Checked against its
  OpenAPI spec: all nine endpoints are ship-side - operator scorecards,
  vessel-speed-reduction compliance grades, AIS track segments. The near-real-time
  whale-presence rating (acoustic detections + sightings + habitat model) reaches
  the shipping industry privately and everyone else through the website map. The
  only route to it as data is a request to boi-whalesafe@ucsb.edu. The VSR data is
  not a substitute: speed-reduction seasons are declared in advance, so they encode
  an expectation of whales rather than an observation of them.
- The 5 `static` entries above have no connected live confirmation feed. No claim is made
  that all possible sources have been exhausted. Species presence cannot establish rut or
  pupping data. They are flagged, capped, and never alert.
- Planet positions come from a two-body solution, so opposition dates can be up to
  about a day off. Fine for planning, not an ephemeris.
- Bloom timing depends on winter rainfall and cannot be computed at all. The three
  hotline scrapers are the only real source, and they describe the past.

## Search guidance (no calendar rows)

These used to be year-long rows. They are now curated phenomena that only appear when live
evidence activates them; the guidance is kept here.

- **Bioluminescent surf** — No dependable annual date. Requires a recent report of visibly glowing water, not just a red tide. Source: https://scripps.ucsd.edu/news/everything-you-wanted-know-about-red-tides
- **Mass winter waterfowl flights** — Sacramento National Wildlife Refuge is a longer-trip target. Seasonal abundance is established; the timing of a mass lift-off is not predictable. Check refuge counts and access. Source: https://www.fws.gov/refuge/sacramento
- **California condors at Pinnacles** — Year-round personal target. High Peaks and the park's current viewing guidance are the starting points; individual sightings do not guarantee a repeat encounter. Source: https://www.nps.gov/pinn/learn/nature/condor-viewing-tips.htm
- **Yosemite moonbows** — spring full-Moon candidate nights; no viewpoint-specific time or live waterfall confirmation.
- **Exceptional swells** — NDBC 46011 and CDIP B1500, with calibration and limits in SOURCE_VALIDATION.md.
- **Aurora and dolphin megapods** — report/model-driven only; never inferred from an annual date.
