# Browser validation — 0.14.0

2026-09-17, Codex in-app Chromium browser. This is a real-DOM test with synthetic events, not the user's installed Home Assistant or live sightings.

Fixture: `tests/card-browser-fixture.html`. Serve the repository root with a local HTTP server and open `/tests/card-browser-fixture.html?stress`. The fixture labels its events synthetic and provides buttons for a push update, periodic updates, disconnection, stale timestamps, unavailable entity, failed saves and a 400-row payload. Stop periodic updates when finished.

Verified:

- Collapsed dashboard rows omit long explanations. Opening a row exposes an overview and closed Dates, Locations, Evidence and Gear sections. Full dates and alternative-night tradeoffs remain reachable.
- List previews show five events and an explicit remaining count. Later month headers name example subjects, including firefall and moonbows. Calendar weeks also offer remaining bars explicitly.
- A 400-row payload rendered both cards in approximately 16–20 ms of synchronous fixture work on this machine. This measures JavaScript/render assignment, not total paint, network time or a real phone.
- Opening Dates then pushing a new state retains the open section. Calendar popup Dates/Gear remain open during repeated updates that change the preferred location. Popup scroll stayed at 373.7 px and keyboard focus remained on Photography gear across updates.
- Escape closes the native dialog and returns focus to the originating calendar bar.
- A failed Skip produces an error inside the still-open dialog and does not hide the event.
- Disconnection produces a dated saved-information notice on both cards. Stale and unavailable fixtures retain the calendar with an explicit warning.
- At a 390×844 viewport, both cards fit without horizontal document overflow. Card width was approximately 319 px within the fixture margins. Expanded sections and the native popup remain keyboard-accessible. This is responsive layout testing, not validation on a physical phone.

Still required: inspect the user's actual HA version/upgrade, resource caching, logs, options/restart and a full live update cycle. The local fixture does not establish those outcomes.
