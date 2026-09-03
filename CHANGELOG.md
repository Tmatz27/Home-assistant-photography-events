# Changelog

## 0.1.0

- Initial HACS-ready release
- Golden/blue hour, sunrise/sunset, computed directly rather than read from
  `sun.sun`
- Moon phase, illumination %, moonrise/moonset, with New Moon and Full Moon
  (Supermoon-flagged when notably close) called out specifically
- The eleven major annual meteor showers, scored by radiant altitude and
  moonlight interference
- Solar and lunar eclipses from a sourced table through 2028, with a real
  computed local-visibility check for lunar eclipses
- Milky Way core season detection
- A coarse bird migration season heuristic
- A near-term 24/48/72 hour snapshot plus a configurable 7-30 day outlook
- Optional weather-entity-driven sky-quality scoring for sunset/sunrise and
  meteor showers
- Visual card editor and full test suite
