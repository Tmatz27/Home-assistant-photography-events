# Photography Events 0.16.0

The main card is now **Can't miss**: usually zero to five rows, and "Nothing worth changing plans for this week." when that is the truth. Everything else is still collected, classified and kept - it just no longer competes for the same five rows.

## Signal → Phenomenon → Opportunity

- **Signals** are raw evidence: eBird and iNaturalist sightings, hotline and emailed reports, operator reports, buoy measurements, forecasts. They corroborate phenomena, feed the bird view and fill one collapsed "Watching N background signals" section. A humpback sighting is no longer a row.
- **Phenomena** are curated photographic experiences (`curation.py`): humpback lunge feeding, elephant seal breeding and pupping, the tule elk rut, the Pismo monarch clusters, the largest full Moon of the year. Each has a significance, a trigger policy (computed, calendar-reliable, behaviour report, aggregation, count, conditions, exceptional presence, live confirmation, forecast plus confirmation) and a written reason.
- **Opportunities** reach Can't Miss only through a hard gate: curated class, policy satisfied, inside seven days, inside the drive limit (planning-only rows are not exempt), significance at or above the floor, and no active NWS warning at the place. Only then is anything ranked.

Significance, confidence, urgency, encounter, access and condition quality are separate fields. The planner score is unchanged and only ranks planner rows.

## What changed for you

- A hotline "Go now" or an emailed "lunge feeding off Avila this morning" now **merges into** the phenomenon it describes instead of appearing beside it. Emails and hotline pages are dated only from dates or "today/this morning" wording in their own text; download time never counts.
- **Birds** get their own optional view: Spectacle (behaviour or concentrations, can reach Can't Miss), Encounter (repeated reports at a public viewing area) and Bird Chase (notable individual birds, ranked by how findable they still are). Private locations are never listed. Add it with `mode: birds`.
- **Sunsets are a home feature.** Tonight's sky over Vandenberg only. Optional SunsetWx (Sunburst API) credentials make its forecast the primary source; the local model stays as fallback and comparison.
- **Lunar engine.** Every full Moon, ranked by distance within its year, with moonrise/moonset, azimuths, the time at 0/1/2/5/10°, sunset and twilight overlap. The closest full Moon of 2026 (24 Dec, rising near sunset, on a published King Tide date) can reach Can't Miss; ordinary full Moons are planner facts.
- **Gear from your own bag**: A7R IV, 16-35 GM, 70-200 GM II, 200-600 G, 2x TC (optional, never the default), Osmo Pocket 3, and a drone verdict that says "Prohibited" in national parks, refuges and Vandenberg airspace.
- **New curated phenomena:** Carpinteria harbor seal pupping, Cachuma Lake eagles, condor concentrations, mass goose lift-offs, bioluminescent surf and frazil ice (report-activated), King Tides and minus tides (planner), fresh snow and thunder (watch only).
- The year-long "search target" rows are gone; parks stay in the planner.

## Compatibility

Entity IDs are unchanged; `sensor.photography_events_can_t_miss` is new. The drop-everything binary sensor now turns on only for an eligible Can't Miss occurrence within 48 hours, so it fires less often. Existing `action_hero` cards show Can't Miss automatically and fall back to the 0.15 week view against an older backend. Follow/Skip/Seen choices are unchanged.

See DISCOVERY_AUDIT.md for the audit and sources, and SOURCE_VALIDATION.md for what each source can and cannot establish.
