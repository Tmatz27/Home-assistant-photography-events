# Photography Events 0.14.0

The dashboard now starts with a short list of upcoming photography opportunities. Open an event for a brief overview, then choose Dates & alternatives, Locations & access, Evidence & source reports or Photography gear.

- Five-row previews keep busy lists and calendar weeks readable, with explicit controls to see every remaining event. Later months start collapsed and show a preview of their subjects. Filters and the color legend are tucked away until needed.
- Related moonbow nights share one row per occurrence. Changing the highest-ranked night preserves the event's identity. Full supplied ranges, location-specific hours and alternate-night comparisons remain available.
- Saved information stays visible during outages, with the last calendar update and clear disconnected, unavailable or overdue labels. A local timer ages data even when Home Assistant sends no updates.
- Expanded detail sections, keyboard focus and scroll position survive updates. Calendar popups refresh their evidence in place, support Escape and return focus to the event. Failed Follow/Skip saves remain visible and do not claim success.
- Fixed USGS health wiring and rare-only weather fetching. Repeated streamflow failures now reach HA Repairs and affected moonbow rows without changing evidence confidence.
- Migrated discharge requests to USGS OGC v1. Strict station, parameter, units, quality and timestamp checks reject malformed/non-finite data and partial pages. River readings are dated regional context, never waterfall-flow confirmation or future-flow forecasts.
- Replaced the misleading moonbow condition count with separate cloud, flow, spray and terrain states. Preserved candidate hours through the compact sensor payload and labelled longer-range clouds as outlooks. Added distinct Lower Fall, Sentinel Bridge and Glacier Point guidance.

Moonbow sky intervals are candidates, not viewpoint predictions. Current waterfall spray and terrain lighting still need verification; published 2026 timetables are not recycled for 2027. Firefall remains a seasonal alignment lead with flow and western-horizon conditions unconfirmed. Wave calibration remains limited to the Vandenberg data points; a verified storm-access viewpoint and other coastlines need further sourcing. Whale Safe's public API has ship/compliance data, not whale presence.

No phone notifications or cancelled Tier 2 features were added. After updating in HACS, restart the integration/Home Assistant as needed and reload the dashboard resource. The user's installed HA version and upgrade have not yet been inspected.
