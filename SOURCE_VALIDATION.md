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
