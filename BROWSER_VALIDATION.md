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

### 0.16.0 hardening pass — same day, same three viewports

The fixture gained a synthetic solar-eclipse row (required kit, caution state, fallback note, condition states) and a "Toggle NWS outage (held)" control. Verified at desktop, phone and HA-Android widths:
- The collapsed eclipse row shows "Required: Certified solar filter … over the FRONT of the lens" and a "Caution ·" status prefix.
- Its "Gear & technique" section lists Required and Safety first, then the owned Take/Optional/Skip, and "Worth adding or renting (not in your bag)" last and separately labelled.
- Evidence shows "Fallback in use" and each condition state as its own row.
- With the alert feed "down", the card says "Nothing cleared to recommend: safety could not be checked for the rows held below." and lists the held rows with their reason; it does not show the green "Nothing worth changing plans" state.
- No horizontal overflow in any of these states; no page errors.

### 0.16.0 correction pass — 2026-09-28, same three viewports

Playwright with the pre-installed Chromium against `tests/cant-miss-browser-fixture.html` (synthetic rows only). The fixture gained a marine-held orca row, the corrected solar-filter wording and a "Toggle required source outage (incomplete)" control. At desktop 1280×900, phone 390×844 (DPR 3, touch) and HA-Android-like 412×915 (DPR 2.625, touch, HA app user agent):
- The collapsed eclipse row reads "Required: Solar filter for cameras"; no camera label mentions ISO 12312-2; the expanded gear section lists Required first and says eye viewers are never used as a camera filter.
- With a required source down and no rows, the card shows "Can't Miss assessment incomplete: required data unavailable." with the failed sources listed, not the green quiet-week state; with rows present, a collapsed "Assessment incomplete" note sits above them.
- Held rows are headed "Held: a required check could not be made" and include the marine reason.
- No horizontal document overflow in default, incomplete, held or expanded-gear states; no page errors.
