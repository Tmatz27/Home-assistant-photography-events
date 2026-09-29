# Source validation and evidence limits — 2026-09-06

Public feeds were downloaded and parsed during this release. This supersedes the older handoff's statement that every network source is inaccessible from the development environment. No live Home Assistant instance was available for a full installed-system test.

| Source | What is connected | What it cannot establish |
| --- | --- | --- |
| [NOAA NDBC](https://www.ndbc.noaa.gov/station_page.php?station=46011) | Significant wave height, dominant period, mean direction and observation time | Coastal breakers or a safe tripod position |
| [CDIP](https://cdip.ucsd.edu/?nav=recent&sub=forecast) | Experimental B1500 nearshore model; metadata coordinates checked against 34.75812, -120.64311; QC flag 1 only; model creation age <=24h | Actual breaker height or a verified photographic viewpoint |
| [NWS](https://api.weather.gov/alerts/active?area=CA) | Coastal/surf advisories mentioning Santa Barbara | All access restrictions or the safety of a viewpoint |
| [Condor Express RSS](https://www.condorexpress.com/blog-feed.xml) | Explicit trip observation date, named regional location and strict sized-megapod statement | Current animal position; daily totals cannot prove a single pod |
| [NOAA OVATION](https://www.swpc.noaa.gov/products/aurora-30-minute-forecast) | Recent solar-wind input and short-term local aurora model cell, with darkness check | A photographer's visibility probability; distant horizon aurora is not modelled here |
| [CDFW grunion](https://wildlife.ca.gov/Fishing/Ocean/Grunion) | Published year and two-hour expected intervals, Pacific timezone; Santa Barbara +25 minutes | Whether fish actually appear at the chosen beach |
| [NPS moonbows](https://www.nps.gov/yose/learn/photosmultimedia/ynn15-moonbows.htm) | Basis for a spring full-Moon search target | Viewpoint-specific times, live waterfall/spray confirmation |
| [Scripps bioluminescence](https://scripps.ucsd.edu/news/everything-you-wanted-know-about-red-tides) | Reference explaining the phenomenon | A current glowing-water report or dependable seasonal date |
| [Sacramento NWR](https://www.fws.gov/refuge/sacramento) | Winter waterfowl search target and official access reference | The time of a mass flight; no automated count or webcam interpretation is implemented |
| [NPS condor viewing](https://www.nps.gov/pinn/learn/nature/condor-viewing-tips.htm) | Year-round Pinnacles viewing target | A guaranteed sighting |

## Wave calibration

The reproducible script is `tools/backtest_waves.py`. It reads public NDBC annual standard meteorological files named `46011hYYYY.txt`, plus a CDIP B1500 hindcast ASCII projection. Large downloaded archives are deliberately not bundled into the integration.

NDBC historical URL pattern:
`https://www.ndbc.noaa.gov/view_text_file.php?filename=46011h2025.txt.gz&dir=data/historical/stdmet/`

CDIP hindcast projection:
`https://thredds.cdip.ucsd.edu/thredds/dodsC/cdip/model/MOP_alongshore/B1500_hindcast.nc.ascii?waveTime,waveHs,waveTp,waveDp,waveFlagPrimary,metaLatitude,metaLongitude`

Training: 2020–2023. Separate validation years: 2024–2025 where available. Every qualifying observation must satisfy size, period >=14s and direction 240–330 degrees. Gaps greater than 48h split episodes. Candidate thresholds were drawn from the 99th, 99.5th, 99.75th and 99.9th percentiles, rounded upward to 0.1m. The first candidate with no more than three episodes per training year was selected.

| Series | Threshold | Training episode counts 2020 / 2021 / 2022 / 2023 | Validation |
| --- | --- | --- | --- |
| Offshore NDBC 46011 | 6.5m | 0 / 1 / 0 / 2 | 2024: 0; 2025: 0 |
| Nearshore CDIP B1500 hindcast | 5.2m | 0 / 2 / 0 / 3 | 2024: 2; 2025: 0 through March 31 only |

Full candidate results, data coverage and event timestamps are in `wave_calibration.json`. A Monterey series was also inspected and retained in that audit, but is not used by the runtime because matching coastal calibration is not implemented and its 2024–2025 annual files were unavailable.

These are separate series backtests, not a validation of the combined operational alert system. Missing observations can hide events or split them. The partial 2025 CDIP record is not an entire quiet year. Hindcast frequency does not measure forecast accuracy. Zero to three training episodes is not a promise of future annual frequency.

## Evidence rules

- An explicit observation date is required; download and publication timestamps do not renew an observation.
- Generic species presence cannot confirm feeding, calving, fighting or aggregation.
- Unlocatable reports confirm nothing. Operator regional reports remain regional.
- The CDIP model point is not an approved shooting position. Check the official access links; a surf advisory is not an access closure.
- Long-range dates remain planning information. Missing or stale data remains a gap instead of becoming confidence.
- Email is parsed against fixed vocabulary without an LLM. No instruction in an email is executed.

## Deferred source work

Whale Safe access, reliable dated foliage/bloom entries, behavior-specific wildlife reporting, observed glowing surf, waterfall flow and moonbow viewing geometry still need source work. An authoritative reference link is not presented as an automatically polled confirmation feed. Eclipse path geometry remains unsourced in this release.

## 0.12.0 source verification — 2026-09-08

NASA's solar and lunar 2001–2100 catalogs supply 45 eclipse records for 2026–2035. The central-path index supplies published timed coordinates and widths for all 16 central solar eclipses. The importer stores provenance hashes and converts catalog TD to UT using each published Delta T. These supersede the earlier unsourced-path limitation above.

- Solar catalog: https://eclipse.gsfc.nasa.gov/SEcat5/SE2001-2100.html
- Lunar catalog: https://eclipse.gsfc.nasa.gov/LEcat5/LE2001-2100.html
- Central paths: https://eclipse.gsfc.nasa.gov/SEpath/SEpath.html

Central-path screening covers known sites, with a conservative edge margin and approximate driving budget. It does not establish road access, exact solar contacts, partial-only visibility or exhaustive reachable land coverage. Lunar viewing intervals use umbral phases and local altitude rather than visibility at an unrelated part of the night.

Meteor drift rates come from Table 6 of the author's 2026 IMO Meteor Shower Calendar, DOI 10.13140/RG.2.2.36179.08480, available at https://www.researchgate.net/publication/393092133_2026_IMO_Meteor_Shower_Calendar . A 1,920-night comparison found one usable-night verdict and one preferred-night change; the published near-peak drift is therefore applied through each night instead of dismissed as immaterial.

Whale Safe's public get-involved page lists API inquiries, but endpoint, authentication and example-response requirements remain unverified. No speculative client was added. Source retrieval success never refreshes an observation's date or proves that a named wildlife behavior is occurring.


## 2026-09-17 — USGS migration and viewpoint checks (0.14.0)

- [USGS v1 release](https://waterdata.usgs.gov/blog/api-v1-release/) and [migration documentation](https://api.waterdata.usgs.gov/docs/ogcapi/migration/) checked. Runtime now uses `/ogcapi/v1/collections/continuous/items`, bounded to 72 hours with limit 1000.
- A real unauthenticated response for USGS-11264500, discharge 00060, 2026-09-14 through 2026-09-17 UTC contained 289 observations with no next page. The production parser accepted it. Fields included statistic 00011, ft^3/s, Provisional, null qualifier and an explicit UTC observation time. The recorded sample is historical, not a current trip recommendation. Non-finite values, wrong identity/units/quality, naive times and partial pages fail validation.
- [YosemiteMoonbow.com](https://www.yosemitemoonbow.com/) carried a May 11, 2026 update and viewpoint timetable images. The Lower Fall table's May 29 ideal was 22:20 PDT, ending 22:50. Our generic sky interval extended hours beyond it: a cross-check of the model's limit, not validation of actual moonbow duration. The May 28 ideal was also five minutes outside our 20-minute sampled interval. The release explicitly calls these sky candidates and never reuses the old table for future years.
- Lower Fall footbridge, Sentinel Bridge parking area (Upper Fall), and Glacier Point have distinct guidance and timing. The card links the specialist predictions and [NPS current conditions](https://www.nps.gov/yose/planyourvisit/conditions.htm). These guides do not establish current spray or open roads.
- [Point Sal State Beach](https://www.parks.ca.gov/?page_id=605) documents public trail access and links County closure information. That establishes a place to research, not a verified storm shooting position or calibration of the Vandenberg coastal model at Point Sal. Runtime wave coverage was not expanded.
- Firefall's previous backlog claim of solved geometry and wired basin flow was incorrect. The builder remains a seasonal lead with manual flow/light-path verification; Merced discharge does not measure Horsetail Fall.


## 0.16.0 source register — 2026-09-27

Every source the integration reads, what it is, and what its absence means. "Missing means" is the rule the code follows: a failed feed is reported through source health and **never** read as "nothing happened". Live access to these hosts was blocked from the development container this round; shapes below come from each provider's documentation or published client libraries and earlier saved responses, and are named as such.

| Source | Authority / URL | Supplies | Cadence (min poll) | Basis | Auth · limits | Failure detected by | Missing means |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Open-Meteo forecast | Open-Meteo, api.open-meteo.com | Layered cloud (home, zones, light-path probes, the Pismo grove condition point), weather code, snowfall, temperature, wind (m/s), precipitation probability | 60 min | Forecast (model; ≤7 d "forecast", beyond "outlook") | None · free tier | Incomplete multi-location answer → partial failure | **Required** for local sunsets, sky events, firefall, snow clearing and the monarch dawn: a failed or stale forecast blocks those from Can't Miss |
| Open-Meteo air quality | Open-Meteo | Aerosol optical depth at home | 3 h | Forecast | None | Wrong location count | **Optional**: sunset clarity falls back to humidity/visibility; never removes a sunset |
| SunsetWx Sunburst | SunsetWx LLC, sunburst.sunsetwx.com/v1 ([docs](https://sunburst.sunsetwx.com/v1/docs/), [sunburst.js](https://github.com/sunsetwx/sunburst.js), [PySunsetWx example response](https://github.com/salvoventura/PySunsetWx)) | Sunset/sunrise quality label + percent, valid time, source model | 3 h, 2 requests (+login) | Forecast (their model) | Client ID/secret from a SunsetWx account; plan per their terms; no public rate limit found | Login or empty/invalid features → failed; a fetch older than 6 h is not used; a prediction whose own `last_updated` is missing, in the future or older than 12 h is not used (a current download of an old model run fails) | **Preferred source with fallback**: the local sky model decides alone and the row says "SunsetWx unavailable; the built-in local model decided". Never blocks a valid local result |
| NWS active alerts | NOAA/NWS, api.weather.gov/alerts/active?area=CA | Every California warning/advisory: event, polygon or county SAME codes, onset/ends | 1 h | Official warnings | User-Agent only | Non-collection → failed. Every feature validated (event, parseable expiry, and geography the resolver can place: a closed, nondegenerate numeric polygon or a list of recognized full-county California SAME codes; UGC-only, malformed or scalar SAME and non-list UGC are unusable); any unusable feature → failed *and* incomplete: readable warnings still block, nothing is called safe. Older than 3 h → not checked | **Required for travel**: safety is *unknown*; Can't Miss holds rows that need travel and says so. Never "all clear". Marine-zone alerts are not matched: every boat phenomenon has marine safety *unknown* and is held, never safe |
| NOAA NDBC 46011 / CDIP B1500 | NOAA, CDIP | Measured offshore swell; nearshore model | 30 min / 3 h | Observed / forecast | None | QC flags, stale run time (see above) | No swell row; swell forecast alone is only a watch |
| NOAA CO-OPS tides | NOAA, api.tidesandcurrents.noaa.gov | High/low predictions at four stations, now attributed per station | 12 h | Computed prediction | None | No predictions from any station | King Tide rows remain as published planning dates without times; no minus-tide rows (they exist only where NOAA predicts, about 45 days ahead); grunion hour unknown. The grunion hour uses the station nearest the beach only |
| California Coastal Commission King Tides | [coastal.ca.gov/kingtides](https://www.coastal.ca.gov/kingtides/) | Published statewide dates (2026-27: 24–26 Nov, 23–25 Dec, 21–22 Jan) | Static table | Published | — | — | Later seasons not guessed; added when published |
| eBird notable | Cornell Lab, api.ebird.org v2 | Notable reports, count, reviewer flags, `locationPrivate` | 60 min | Observed (presence) | Free key | Non-list answer per region → partial failure | Bird Chase may be incomplete |
| eBird species | Cornell Lab, `/data/obs/{region}/recent/{species}` | Condor, bald eagle, crane, Ross's and snow goose reports and counts in their viewing counties | 6 h, 6 requests | Observed | Same key | As above | Bird Spectacle/Encounter may be incomplete. eBird may withhold sensitive species; absence is not absence of birds |
| iNaturalist | iNaturalist, api.inaturalist.org v1 | Presence of every species a curated window names; box now covers all windows, not only the coast | 60 min | Observed (presence) | None; ~1 req/s | Error object per taxon → partial failure | Presence corroboration missing; never proves behaviour |
| Hotlines (Theodore Payne, DesertUSA, California Fall Color) | Scraped public pages | Bloom/colour text; a date stated in the text becomes the observation date | 24 h | Reported | None | Layout/topic check (see above) | Phenomenon stays "watching"; undated text is labelled undated |
| Emailed reports (`ingest_report`) | Whoever the user subscribes to | Fixed-vocabulary phenomenon, place, count; dated only by an explicit date or "today/this morning" | On arrival | Reported | User's IMAP | No match → discarded | Nothing inferred |
| Condor Express RSS | Operator | Dated, explicitly sized megapods; dated, non-negated orca sightings (trusted operator report) | 3 h | Reported | None | Non-RSS → failed | No megapod or operator orca row; community orca reports still need two observers within 25 km |
| NOAA OVATION | NOAA SWPC | Local aurora nowcast | 15 min | Model nowcast | None | Missing coordinates | No aurora row |
| NASA eclipse catalog | NASA GSFC (bundled) | Eclipse geometry 2026–2035 | Static | Computed | — | — | — |
| Friends of the Elephant Seal | [elephantseal.org](https://elephantseal.org/birthing-and-breeding/) | Documented breeding cycle (calendar basis) | Documentation | Published cycle | — | — | "What's happening now" page structure could not be inspected here; no scraper. Use `ingest_report` for docent updates |
| City of Carpinteria / Seal Watch | [City rookery page](https://carpinteriaca.gov/parks-and-recreation/carpinteria-harbor-seal-rookery/), [Seal Watch](https://carpinteriasealwatch.org/information/) | Closure 1 Dec–31 May; births mostly Feb–Mar; ~60 pups | Documentation | Published cycle | — | — | Counts not machine-readable |
| USFWS Merced NWR | [fws.gov/refuge/merced](https://www.fws.gov/refuge/merced) | Up to 20,000 cranes, 60,000 geese; sunset fly-in "predictable daily spectacle"; best Dec–Feb | Documentation | Published cycle | — | — | — |
| Xerces Society / State Parks (monarchs) | [Xerces visiting guidance](https://xerces.org/blog/everything-you-need-to-know-about-visiting-overwintering-monarchs), [Pismo grove](https://www.parks.ca.gov/?page_id=30273) | Monarchs do not fly below ~55 °F; Pismo season Nov–mid-Feb | Documentation | Published | — | — | Current counts must be supplied by report; recent early-season counts were in the hundreds |

### Final R1/R2/R3/R5 interpretation rules (0.16.0, unreleased)

- NPS access needs interpretable records for the requested parks, as well as complete pagination. Unknown categories and unrequested/unresolvable park codes make access unknown. Information and Caution are nonblocking; Park Closure, legacy Closure and Danger retain their blocking behavior. A valid zero-result response remains a successful check.
- NWS geometry must have closed rings, at least three distinct points, nonzero area, numeric finite coordinates (not booleans), and valid longitude/latitude ranges. A malformed polygon may fall back to valid county SAME codes. SAME support is restricted to the 58 full-county California codes in the [NWS county table](https://www.weather.gov/hnx/cafips); subdivisions, impossible counties and UGC-only geography are not resolved. Any unusable feature makes coverage incomplete while readable warnings still block. Ring/position conventions follow [RFC 7946](https://www.rfc-editor.org/rfc/rfc7946.html#section-3.1.6).
- Report behavior and count belong to an assertion with one unambiguous animal. Multi-animal and relational grammar is held rather than resolved by noun distance. Only genuine place/date headers lend metadata; another animal's assertion, cancelled trip or plan cannot. Distinct precise places remain ambiguous even inside one zone. Conflicting dates are undated; the explicit continuation "last night and today" still states an observation today. The existing monitored-rookery rule for first pups remains.
- A forecast time axis must be valid, strictly increasing and unique. Event samples must be inside that axis, at an exact sample or between samples at most one hour apart. Missing/invalid values are not replaced by a different hour. Near-term meteor, Milky Way and full-Moon conditions with no cloud sample are unassessed; long-range planner dates do not require operational weather.
- A snow report can qualify on a valid future clear hour within 48 hours. Concluding that there is *no* clearing requires hourly coverage and readable cloud over the entire remaining 48-hour search window. Duplicate hours, gaps and expired coverage cannot establish that negative result. A meteor recommendation additionally needs cloud at or below the existing 25% astronomy threshold, even when Moon/radiant geometry would otherwise keep its score high.

These are conservative product rules, verified with synthetic inputs through the production functions and HA coordinator. They are not live-provider certification.

### Thresholds and where they come from

| Threshold | Value | Basis |
| --- | --- | --- |
| Monarch cold dawn | ≤ 55 °F forecast at 07:00 local at the Pismo grove forecast point | **Product heuristic** built on the Xerces statement that monarchs generally cannot fly below about 55 °F. Wind and rain are shown for context only; no threshold is claimed |
| Monarch meaningful count | ≥ 1,000 | Product threshold |
| Goose/crane mass count | ≥ 1,000 | Product threshold, against USFWS wintering numbers in the tens of thousands |
| Condor concentration | ≥ 3 birds in one report | Product threshold |
| Bird encounter repetition | ≥ 3 independent reports on ≥ 2 days in 7 days within 15 km of a public site | Product threshold |
| Orca exceptional presence | ≥ 2 independent observers in a cluster whose every pair is within 25 km (complete linkage: 25 km is the diameter), each observation itself inside the last 72 h; or one dated operator report in 36 h. Obscured/private points never form a cluster. A single community observation (even research grade) is a signal only | Product threshold |
| Bioluminescence | Report ≤ 3 days old, Moon < 50 % lit | Product threshold |
| Minus tide | ≤ −1.0 ft MLLW, daylight | Common tidepooling guidance; product threshold |
| Photogenic moonrise | Within 60 min of sunset | Product threshold |
| Fresh snow watch | ≥ 10 cm modelled in 24 h, then ≤ 30 % cloud within 18 h | Product threshold; watch only |
| Fresh snow Can't Miss | A dated snow report ≤ 2 days old *and* a forecast hour ≤ 30 % cloud within the next 48 h at the same zone; the photograph window is 12 h from the clearing; in Yosemite or Sequoia/Kings Canyon, a current complete NPS read with no closure there | Product thresholds |
| Firefall evening | Local cloud ≤ 25 % at sunset, upstream light-path gate ≥ 0.75 computed from *both* upstream low and mid layers present, finite, 0-100 and time-matched (missing = unknown, never open), a dated water report ≤ 3 days old, and a current complete NPS read with no closure naming the valley or viewing area; inside the published mid-February window | Product thresholds on the NPS conditions (clear western horizon, flowing water). Merced discharge is never used |
| Moonbow | Actionable only with a viewpoint-validated prediction, which nothing supplies yet; a flow report ≤ 7 days old makes a supported candidate (watch) | Product rule |
| NWS alert freshness | 3 h | Product threshold (feed polled hourly) |
| SunsetWx freshness | Fetch ≤ 6 h old *and* model `last_updated` ≤ 12 h old | Product thresholds (two poll intervals; two provider update cycles) |
| Dolphin megapod | ≥ 1,000 dolphins written against one pod | Product threshold |
| Park access freshness | NPS read ≤ 12 h old and complete: every record has a nonempty string id and title, a requested/resolvable park code and a recognized category; ids are distinct, pages agree on `total` and the distinct count equals it | Product threshold (two poll intervals); unknown category/park association means unknown access |
| Evidence merges into a calendar site | Within 15 km of that site | Product threshold (the bird viewing-area radius) |
| Route freshness | "Current traffic" ≤ 60 min; refresh after 3 h; expired after 7 days. A recent (1 h to 7 days) route may decide the drive limit, except when the distance estimate is over the limit and only the old route is under it: then the row is held until a current route. The card shows the basis and route age | Product thresholds |
| Unassessed conditions | A condition value the forecast should cover but is missing or invalid (light-path layer, local sky at sunset, clearing hours, dawn temperature, night cloud) holds the row and makes the week's assessment incomplete. A valid unfavourable value is an answer and does not. Each home sunset/sunrise is assessed by a current provider prediction for that event, or by the local model with current home and light-path inputs | Product rule |
| Report location | A report naming a place keeps that place even when filed under another zone. Glowing surf reported only for a region is a watch, never a destination | Product rule |
| Orca operator backing | An operator report backs a community cluster only within 25 km of every member; otherwise it is its own occurrence at its own point | Product threshold |
| Weather point staleness | 3 h | Product threshold |
| Message context | A place or date is borrowed only from the subject line, an automation's explicit zone, or a header statement of ≤ 6 words naming no subject or behaviour | Product rule |
| Implied subjects | Piedras Blancas → elephant seals; Carpinteria → harbor seals; "sow with cubs" → bears | Product rule (monitored colonies; self-identifying phrases) |
| Drone wind | 10.7 m/s | Sourced: DJI Mini 3 specification (Level 5) |
| Significance floor | 70 | Product threshold |

### Evidence freshness per phenomenon (product thresholds)

How long a dated report stays evidence (`curation.PhenomenonDefinition.evidence_days`, never more than the 14-day corroboration limit). Chosen by how fast the photograph moves, not sourced:

| Days | Phenomena |
| --- | --- |
| 2 | Dolphin megapod, frazil ice, fresh snow |
| 3 | Humpback lunge feeding, blue whale aggregation, orcas (hunting and presence), common dolphin calving, bioluminescent surf, firefall water |
| 5 | Gray whale mothers and calves, bald eagles fishing, mass goose lift-off |
| 7 | Tule elk behaviour report, black bear sows with cubs, condors, aspen colour, moonbow flow |
| 10 | Wildflower blooms |
| 14 | Elephant seals, harbor seals, sandhill cranes, monarch counts (the cold-dawn condition is still checked each morning) |

### Moonbow viewpoint timetables

YosemiteMoonbow.com publishes its Lower Fall and Upper Fall predictions as page images, so no timetable can be read programmatically, and no future date is copied from a past table. Moonbows therefore stay candidates (watch) at most.

### Not yet production-verified

These are implemented against documentation, published clients or earlier saved responses, and **have not been confirmed against a live response** from this environment: SunsetWx login and quality responses (including `last_updated`); eBird species responses; the statewide NWS active-alerts payload (including polygon versus county-only alerts and real malformed features); the Friends of the Elephant Seal "what's happening now" page (no scraper exists); the Condor Express feed's real wording; real Open-Meteo condition bundles; NPS pagination and access (`total`, `start`, category names); current CDFW grunion parsing; NOAA station/timezone enrichment.

Drone legality: NPS Policy Memorandum 14-05 under 36 CFR 1.5 (national parks); 50 CFR 27.34 and 27.51 (national wildlife refuges).
