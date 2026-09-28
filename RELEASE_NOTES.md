# Photography Events 0.16.0

The main card is now **Can't miss**: usually zero to five rows, and "Nothing worth changing plans for this week." when that is the truth. Everything else is still collected, classified and kept - it just no longer competes for the same five rows.

## Signal → Phenomenon → Opportunity

- **Signals** are raw evidence: eBird and iNaturalist sightings, hotline and emailed reports, operator reports, buoy measurements, forecasts. They corroborate phenomena, feed the bird view and fill one collapsed "Watching N background signals" section. A humpback sighting is no longer a row.
- **Phenomena** are curated photographic experiences (`curation.py`): humpback lunge feeding, elephant seal breeding and pupping, the tule elk rut, the Pismo monarch clusters, the largest full Moon of the year. Each has a significance, a trigger policy (computed, calendar-reliable, behaviour report, aggregation, count, conditions, exceptional presence, live confirmation, forecast plus confirmation) and a written reason.
- **Opportunities** reach Can't Miss only through a hard gate: curated class, policy and place-specific conditions satisfied, inside seven days, inside the drive limit (planning-only rows are not exempt), significance at or above the floor, required data sources current, and NWS safety checked with no blocking warning. Only then is anything ranked. A trip whose safety cannot be checked is shown as **held**, never as clear.

Significance, confidence, urgency, encounter, access and condition quality are separate fields. The planner score is unchanged and only ranks planner rows.

## What changed for you

- A hotline "Go now" or an emailed "lunge feeding off Avila this morning" now **merges into** the phenomenon it describes instead of appearing beside it. Emails and hotline pages are dated only from dates or "today/this morning" wording in their own text; download time never counts.
- **Birds** get their own optional view: Spectacle (behaviour or concentrations, can reach Can't Miss), Encounter (repeated reports at a public viewing area) and Bird Chase (notable individual birds, ranked by how findable they still are). Private locations are never listed. Add it with `mode: birds`.
- **Sunsets are a home feature.** Tonight's sky over Vandenberg only. Optional SunsetWx (Sunburst API) credentials make its forecast the primary source while it is healthy and recent; when it fails, the local model decides on its own terms and the row says a fallback was used. An air-quality outage never removes a sunset.
- **Lunar engine.** Every full Moon, ranked by distance within its year, with moonrise/moonset, azimuths, the time at 0/1/2/5/10°, sunset and twilight overlap. The closest full Moon of 2026 (24 Dec, rising near sunset, on a published King Tide date) can reach Can't Miss; ordinary full Moons are planner facts.
- **Gear**: take/optional/skip from your own bag (A7R IV, 16-35 GM, 70-200 GM II, 200-600 G, 2x TC - optional, never the default - Osmo Pocket 3), a separate *worth adding or renting* list (at most two unowned items with reasons, e.g. a 1.4x TC for eagles, a 14mm f/1.8 for the Milky Way), and *required* safety kit - for every solar eclipse, a special-purpose solar filter made for camera optics over the front of the lens, plus ISO 12312-2 eclipse glasses or a handheld viewer for your eyes (never used as a camera filter). The drone verdict says "Prohibited" in national parks, refuges and Vandenberg airspace.
- **Safety states**: safe, caution, unsafe or unknown, per place and exposure. A High Surf Warning keeps you off the beach and on high ground for swell; a Red Flag Warning is a caution, not a block.
- **New curated phenomena:** Carpinteria harbor seal pupping, Cachuma Lake eagles, condor concentrations, mass goose lift-offs, bioluminescent surf and frazil ice (report-activated), King Tides (published dates all season, NOAA times once predicted) and minus tides (NOAA predictions, about 45 days ahead), fresh snow (a dated report plus a clearing forecast), thunder (watch only). Moonbows stay candidates until a viewpoint-specific prediction can be read.
- The year-long "search target" rows are gone; parks stay in the planner.

## Correction pass before release (still 0.16.0)

Two independent reviews found places where the rules above were not what the running pipeline did. The fixes below are covered by tests that run the real Home Assistant coordinator on synthetic HTTP payloads; they have not been verified against every live feed (see SOURCE_VALIDATION.md for what is and is not live-verified):

- **Boat trips are never "safe" yet.** Land alerts say nothing about the sea and marine-zone warnings are not connected, so boat phenomena are held with "Marine conditions not checked" until they are.
- **Park access is checked for the phenomena that need it** (Firefall, Yosemite moonbows, Yosemite/Sequoia snow) even with the Parks view off; NPS alerts are read to their full `total`; no key or no current read means held, and NPS's own "Park Closure" category now blocks.
- **An incomplete NWS response is not an all-clear**, and **an outage never looks like a quiet week**: the card says "Can't Miss assessment incomplete: required data unavailable." and names the sources.
- **Reports are read statement by statement.** "No lunge feeding at Avila today" confirms nothing; a count belongs to the animal it is written against; a place or date in one sentence is never borrowed by another. A megapod needs 1,000 dolphins; birds' counts and behaviour reports keep their own dates; Woodbridge cranes are not Merced cranes; a report from Pismo stays at Pismo.
- **Orca presence** uses each observation's own place and time: observations older than 72 h do not count, and every pair in a group is within 25 km.
- **Out-of-season behaviour**: a fresh report of blue whales feeding (or humpbacks lunge feeding, orcas hunting, bear cubs, fishing eagles, dolphin calves) now opens a short occurrence even outside the usual season.
- **Forecast integrity**: missing upstream cloud layers are unknown, never an open light path; SunsetWx must be a current model run, not just a current download; one failed forecast point no longer blocks rows at other places; route times age and say so.
- **Timed planning rows** (grunion runs, moonbow candidates) keep their times in the calendar; winter seasons keep their identity across 1 January; a skipped Milky Way night no longer represents its group; opportunity events pick the best *eligible* viewpoint.
- **Settings**: clearing an API key in the options really clears it; selecting no categories means none; switching Waves off stays off. A saved category list is never rewritten on upgrade, because nothing records whether an older "everything but Waves" list was a default or a choice. If you installed before Waves existed and want it, turn it on once in the options.
- **Park alerts are read record by record.** An NPS page whose records lack an id, park, title or category, or that repeats records from an earlier page, makes access unknown rather than open.
- **NWS warnings must be placeable.** A warning with only zone (UGC) codes, malformed or non-list county codes, or a polygon with invalid coordinates makes the safety check incomplete; it no longer matches nowhere and reads as safe.
- **Each report sentence speaks only for its own animal.** "Humpbacks passed Avila today and dolphins were lunge feeding" confirms nothing about humpbacks; "2,000 geese and monarchs" is not a monarch count; "sea lions feeding" is not condor behaviour; a short first sentence such as "Trip cancelled at Avila today." no longer lends its place and date to the next one, and a header naming two places gives no place. Hotline pages keep each statement's own date instead of the page heading's.
- **Unassessed is not unfavourable.** When a forecast value a candidate needs is missing or invalid (a light-path layer, the local sky at sunset, a clearing forecast, dawn at the grove, night cloud), the row is held and the week reads "Can't Miss assessment incomplete". A SunsetWx prediction covers only the sunset or sunrise it predicts.
- **Forecast inputs are tracked separately.** A broken sunrise light-path probe no longer removes a Firefall that reads only the valley and the sunset path.
- **A region is not a destination.** Glowing surf reported for "the Santa Barbara Channel" is a watch, not a trip to the Channel's centre; a report from Pismo stays at Pismo even when an automation files it under another zone.
- **Orca operator reports** back a community cluster only within the same 25 km bound; otherwise they stand at their own place, and their point is listed with the other contributions.
- **Drive times say what they rest on.** The Can't Miss card shows "current traffic", "routed 6 days ago; not current traffic" or "estimated from distance". An old route that is the only thing keeping a trip under the drive limit (the distance estimate is over it) holds the row until a current route settles it.
- **Solar safety wording** now distinguishes the camera's solar filter from ISO 12312-2 eye viewers.

## Compatibility

Entity IDs are unchanged; `sensor.photography_events_can_t_miss` is new. The drop-everything binary sensor now turns on only for an eligible Can't Miss occurrence within 48 hours, so it fires less often. Existing `action_hero` cards show Can't Miss automatically and fall back to the 0.15 week view against an older backend. Follow/Skip/Seen choices are unchanged.

See DISCOVERY_AUDIT.md for the audit and sources, and SOURCE_VALIDATION.md for what each source can and cannot establish.
