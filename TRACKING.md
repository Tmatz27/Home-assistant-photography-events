# What this integration actually tracks

_Generated from the code by `tools/generate_tracking_inventory.py`. Every date,
evidence level and link below is read out of the modules that run, so this file
cannot drift from the thing it describes._

Generated 2026-09-05.

## How to read this

Everything tracked carries an **evidence level**, and that decides what it is
allowed to do. This is the whole design: a date being on a calendar is not a
reason to drive anywhere.

| Evidence | What the dates rest on | May it raise an alert? |
| --- | --- | --- |
| **computed** | Orbital geometry. Verifiable to the minute against any ephemeris. | Yes, on its own. |
| **live** | A *search season* - when to start watching. The dates alone are an estimate. | Only once a live sighting corroborates it. |
| **static** | A calendar estimate. No feed anywhere publishes this. | **Never**, at any score. |

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
- `aerosol_optical_depth`, `dust` (air-quality endpoint) - decides saturation.

A sky only raises an alert when it is a **standout**: at least 82, and within
3 points of the best in the forecast window, with a modelled light path.
"Is this a good sunset" is the wrong question; "is this the one to go out for" is
the right one, and it is comparative.

Verify against: <https://open-meteo.com/en/docs> and <https://open-meteo.com/en/docs/air-quality-api>

## 3. Biological windows

22 entries. Each carries a background season (informational, never scored)
and a concrete peak window (the only thing that scores).

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
| Tule elk rut | 15 Sep – 10 Oct | 25 | August to October | _Cervus canadensis nannodes_ | [1](https://www.blm.gov/visit/carrizo-plain-national-monument) |
| Eastern Sierra aspen, high elevation ⚠︎ moves year to year | 25 Sep – 5 Oct | 10 | Late September to mid October | — | [1](https://www.californiafallcolor.com/) |
| Eastern Sierra aspen, mid elevation ⚠︎ moves year to year | 5 Oct – 18 Oct | 13 | Early to mid October | — | [1](https://www.californiafallcolor.com/) |
| Northern passes aspen ⚠︎ moves year to year | 10 Oct – 25 Oct | 15 | Mid to late October | — | [1](https://www.californiafallcolor.com/) |
| Pismo monarch butterfly roost | 1 Nov – 15 Dec | 44 | Late October to February | _Danaus plexippus_ | [1](https://westernmonarchcount.org/) |
| Sandhill crane sunset fly-in | 15 Nov – 15 Jan | 61 | October to February | _Antigone canadensis_ | [1](https://wildlife.ca.gov/Lands/Places-to-Visit/Woodbridge-ER) [2](https://ebird.org/species/sancra) |
| Common dolphin calving in the mega-pods | 15 Dec – 28 Feb | 75 | Winter, after a 10-11 month gestation | _Delphinus delphis_, _Delphinus capensis_ | [1](https://pacificwhale.org/what-we-do/research/learn-about-marine-life/whale-dolphin-tracker-live-sightins-map/) [2](https://www.fisheries.noaa.gov/resource/tool-app/whale-alert) |
| Elephant seal bull battles and pupping | 25 Dec – 31 Jan | 37 | December to March | _Mirounga angustirostris_ | [1](https://elephantseal.org/whats-happening-now/) |

### Estimates nothing can confirm (`static`)

**These never alert.** No feed publishes them. They are in the calendar so you can plan around them, and they are flagged on the card as estimates - check the sources yourself before booking anything.

| Phenomenon | Peak window | Days | Background season | Corroborated by | Where to verify |
| --- | --- | --- | --- | --- | --- |
| Yosemite Horsetail Fall firefall ⚠︎ moves year to year | 12 Feb – 26 Feb | 14 | Mid-February only | — | [1](https://www.nps.gov/yose/planyourvisit/horsetailfall.htm) |
| California grunion run ⚠︎ moves year to year | 1 Apr – 15 Jun (season gate only) | see §1 | March to August | — | [1](https://wildlife.ca.gov/Fishing/Ocean/Regulations/Grunion) |
| Black bear sows with new cubs | 15 Apr – 10 Jun | 56 | March to July; CDFW puts den emergence at March-May | _Ursus americanus_ | [1](https://wildlife.ca.gov/Conservation/Mammals/Black-Bear) [2](https://keepbearswild.org/bear-tracker/) [3](https://www.tahoebears.org/learn-more) |
| Desert bighorn sheep rut | 1 Aug – 15 Sep | 45 | July to October | _Ovis canadensis nelsoni_ | [1](https://wildlife.ca.gov/Conservation/Mammals/Bighorn-Sheep/Desert/Natural-History/life-history) |
| Sierra bighorn sheep rut | 1 Nov – 10 Dec | 39 | October to December | _Ovis canadensis sierrae_ | [1](https://wildlife.ca.gov/Conservation/Mammals/Bighorn-Sheep/Sierra-Nevada/Recovery-Program) |

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
| Open-Meteo forecast | Layered cloud at each zone and both light-path probes | none | every 60 min |
| Open-Meteo air quality | Aerosol optical depth and dust - colour saturation | none | every 3 h |
| eBird notable observations | Rare birds, and crane corroboration | free, instant | every 60 min |
| iNaturalist observations | Whale, dolphin and mammal corroboration | none | every 60 min |
| Theodore Payne Wildflower Hotline | Whether a bloom is actually happening | none (scraped) | every 24 h |
| DesertUSA wildflower reports | Desert bloom reports | none (scraped) | every 24 h |
| California Fall Color | Aspen colour reports | none (scraped) | every 24 h |
| NOAA CO-OPS tide predictions | The hour of a grunion run | none | every 12 h |
| NPS alerts API | Road and area closures - the trip-killer nothing else sees | free | every 6 h |
| Google Routes API | Traffic-aware drive times | yours, optional | every 30 min |
| Any subscription email | Whatever a mailing list reports, via the IMAP integration and `photography_events.ingest_report` | none | whenever it arrives |

Requests are staggered into groups on startup so a Home Assistant restart does not
fire everything at once, and each source backs off on its own after a failure.

## 6. Known gaps

Written down rather than papered over.

- **Whale Safe** (<https://whalesafe.com/>) is the best corroboration
  source on this coast - a daily whale-presence rating for the Santa Barbara Channel
  built from hydrophones, observers and a habitat model. Its API is by request only
  (`boi-whalesafe@ucsb.edu`). The code is shaped for a key to drop straight in; it
  links out rather than inventing an endpoint.
- The 5 `static` entries above have no live feed anywhere. That is a fact
  about the world, not a shortcut - nobody publishes machine-readable rut or
  pupping data. They are flagged, capped, and never alert.
- Planet positions come from a two-body solution, so opposition dates can be up to
  about a day off. Fine for planning, not an ephemeris.
- Bloom timing depends on winter rainfall and cannot be computed at all. The three
  hotline scrapers are the only real source, and they describe the past.
