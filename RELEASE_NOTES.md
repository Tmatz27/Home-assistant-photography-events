# Photography Events 0.11.0

The main dashboard now shows compact, expandable briefs for every opportunity overlapping the next seven days. Milky Way nights share one event row with all supplied locations, a preferred date, the full supplied date range, and night-by-night alternatives. The closest listed approximate drive is shown in the details.

## Choosing dates

Milky Way calculations now look 35 days ahead. Cloudy alternatives remain visible for comparison. Each night explains usable darkness, moon illumination, core altitude, cloud forecast availability, and how it compares with the preferred option. Tied priorities are identified as comparable alternatives. The end of calculated coverage is explicitly distinguished from the end of the season.

This is a best-among-the-available-options ranking, not a guarantee of the season's best photograph. Seasonal wildlife and spectacle windows retain their broader season and typical peak. Where current evidence cannot distinguish an ideal day from an alternate day, the details say so and identify the missing evidence.

## Planner and calendar

- Collapse Happening now, Next 7 days, and other time sections independently.
- Switch between List and a month calendar. Color-coded bars span the supplied dates; click a bar to open an event dialog.
- Astronomy blue and all other category colors match the row accents and legend. Evidence labels remain separate from priority scores.
- Expanding or collapsing an event preserves the card and page scroll positions.
- Locations use consistent detail panels, each with its own dates, evidence and source link. Guides are labelled as guides; eBird observations link to their original checklists. Multiple species can legitimately share one checklist.
- Standalone bird rows use a small photography shortlist rather than every eBird regional rarity. Raw bird evidence remains available to corroborate seasonal windows. A species sighting is labelled Species reported, never confirmation of the named behavior.
- Payload limiting reserves space for separate occurrences before extra viewpoints, keeping future targets from being crowded out by astronomy locations.

Existing Timeline cards now use the integration planner when its planning sensor is available. A standalone installation still uses the browser calculator; unverified solar-eclipse visibility is excluded from its default local notable list. Sourced solar-path geometry remains unavailable.

Yosemite firefall and moonbow targets remain in the year view under Rare. Firefall's unsupported Southside Drive viewing recommendation has been removed. Their seasonal/light windows do not confirm flowing water, clear weather, access, or viewpoint-specific moonbow timing.

## Update

Update with HACS, restart Home Assistant, then refresh the dashboard. Use **Next seven days (compact)** for the main dashboard and **Planning calendar** for the year view. Both use the planning outlook sensor, auto-detected by default. Existing mode names and saved occurrence choices remain supported. Follow/Skip on a grouped Milky Way entry applies to its currently listed nights.

The integration scores sunsets from Open-Meteo low, middle and high cloud forecasts and upstream light-path conditions when available. It does not require a Pirate Weather entity. These are forecast layers, not measured cloud heights or a guarantee of sunset color.

## Remaining data limits

This release does not add live waterfall-flow or behavior feeds. Firefall, moonbows, rutting, cubs, glowing surf and other seasonal targets remain explicit planning leads where current local evidence is missing. Whale Safe access and solar-eclipse path geometry remain open. See SOURCE_VALIDATION.md for existing feed coverage and limitations.
