# Photography Events 0.16.0

Photography Events now centers on the photographs you would regret missing. A short **Can't Miss** view answers what deserves attention soon, while the Year Planner, Birds and background signals keep longer-range ideas and supporting evidence available.

**0.16.0 is intentionally being published as a stable snapshot before broader installed/live-provider iteration.** Real Home Assistant installation and field testing can now use a fixed version. This release does not claim that every live source has been verified.

## What ships

- **Signal → Phenomenon → Opportunity.** Sightings, forecasts and reports supply evidence for curated photographic experiences. Only sufficiently assessed opportunities pass the eligibility gate; scores rank the survivors instead of substituting for evidence.
- **Can't Miss.** A brief next-seven-days view, usually 0–5 rows, with a healthy empty state when nothing warrants changing plans. Missing required data produces assessment incomplete and visible reasons, rather than a falsely quiet week.
- **Bird Spectacle, Encounter and Chase.** Behavior and meaningful concentrations are distinguished from repeat presence and individual notable reports. Private or sensitive places are not presented as destinations; chase ranking is not encounter probability.
- **Lunar and astronomical planning.** Full-Moon distance/size ranking, horizon bearings, low-altitude timing and twilight context join meteor, Milky Way, eclipse and planetary planning. Published King Tide windows receive station-specific NOAA enrichment when available.
- **Safety and park access.** Readable NWS warnings remain effective even when other records are malformed. Incomplete coverage cannot establish safety. Dependent park opportunities require complete, current, interpretable NPS access data; unknown access is held and a closure blocks.
- **Conservative report normalization.** Behavior, count, place and observation date stay attached to the correct assertion. Negation, cancelled trips, ambiguous multi-animal grammar and conflicting dates do not confirm a phenomenon. A regional report keeps its real geographic precision.
- **Forecast and source completeness.** An HTTP success is not proof that a forecast covers the event. Missing, duplicated, reversed or expired time coverage is unassessed; valid unfavorable weather is an assessed answer. Weather health is tracked by location and light-path input. Optional air quality cannot suppress an otherwise valid sunset; optional SunsetWx falls back to the local model and must have a current model timestamp.
- **Route provenance.** Drive estimates distinguish current traffic, older routes and distance estimates. Route age is visible. An older route alone cannot bring an otherwise over-limit drive into Can't Miss.
- **Gear with clear ownership.** Take, Optional and Skip use the owned kit. Worth adding/renting lists at most two unowned suggestions with reasons, and Required identifies safety equipment. Solar guidance distinguishes front-aperture optics filters from ISO 12312-2 eye viewers.
- **Calendar and saved choices.** Full opportunity ranges, shooting times and alternatives remain accessible. Follow, Skip and Seen persist across restarts; occurrence identity keeps next year's window separate. The card preserves expanded detail during updates and distinguishes an unavailable backend from an empty calendar.

## Install or upgrade

Add this repository to HACS as an **Integration**, install **0.16.0**, restart Home Assistant, then add Photography Events under **Settings → Devices & services**. Existing installations should restart and refresh their dashboard after updating. The repository declares Home Assistant **2024.11.0+**.

One install includes the backend and card. The integration automatically serves/registers `/photography_events/photography-events-card.js`; there is no separate frontend HACS repository. The release also includes `photography-events-card.js` as an asset.

New cards added from the picker start on Can't Miss when the integration is present. Existing YAML without a mode keeps the planner; select `action_hero`, `calendar_outlook` or `birds` explicitly to change views.

Saved categories are preserved literally, including an empty selection. If you installed before Waves existed, enable `waves` in options to include it. API keys remain optional for setup, but missing credentials can leave dependent evidence or access checks unavailable. See the [rewritten README](https://github.com/Tmatz27/Home-assistant-photography-events/blob/v0.16.0/README.md) for configuration, entities and services.

## Validation and known limitations

The implementation passed the complete automated test/CI process and multiple independent adversarial code reviews. The final independent review reported **no material code findings — ready for installed HA / live validation**. Automated coverage includes the production Home Assistant pipeline exercised with synthetic provider payloads; it is not blanket live-provider verification.

- Marine-zone warning coverage is not connected. Boat phenomena are intentionally held with marine safety unknown.
- Some sources require credentials, and live-provider wording, pagination and payload behavior still need broader installed-system testing.
- Moonbows remain candidates until viewpoint-validated predictions can be consumed. Basin flow is not confirmation of spray or viewing duration.
- Regional evidence is not turned into a fake precise destination, and long-range weather is not invented.
- Places and wildlife coverage are curated around California. Astronomical geometry does not establish road access, terrain visibility or an exact composition.

The [source validation register](https://github.com/Tmatz27/Home-assistant-photography-events/blob/v0.16.0/SOURCE_VALIDATION.md) records source-specific limits, including outstanding live checks for SunsetWx, eBird species, statewide NWS alerts, real Open-Meteo bundles, NPS pagination, operator wording, CDFW, NOAA enrichment and routing. Installed-HA and live-source refinement continue after this release; no Phase 2 features are included.
