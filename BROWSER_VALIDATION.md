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


# Browser validation — 0.16.0

2026-09-27, Playwright with the pre-installed Chromium, against `tests/cant-miss-browser-fixture.html` served from the repository root. Synthetic rows only; not the user's Home Assistant.

Viewports: desktop 1280×900; phone 390×844 (DPR 3, touch); Home Assistant Android app-like 412×915 (DPR 2.625, touch, HA app user agent).

Verified at all three:
- No horizontal document overflow collapsed, expanded, or with the background section open.
- Collapsed rows show title, place · drive, why now, when/best time, evidence status and "Take:" lens only; the drone verdict and full technique stay in the details.
- Expanding a row and opening "Gear & technique" survives a pushed state update (row still expanded, section still open).
- Empty week shows "Nothing worth changing plans for this week."; aged data shows "Can't Miss is not up to date … not evidence of a quiet week" instead.
- Eight eligible rows render five plus "Show 3 more".
- Background signals are one closed `<details>` until opened (11 items in the fixture); the bird view keeps Encounters and Bird Chase subordinate to Spectacle.
- No page errors.

A contrast issue was found and fixed: default-blue links in the background and bird lists were hard to read on the dark theme; they now use the theme's primary colour.
