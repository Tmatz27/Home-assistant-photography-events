# Photography Events 0.10.0

The planner now uses short, expandable rows with persistent Follow and Not going / Skip controls. Skipping an occurrence hides all of its viewpoints and suppresses its opportunity notifications; Show skipped allows restoration. The hero shows the actual window opening and leaves travel decisions to you. Scores are labelled as priorities, not probabilities.

New data paths:

- Exceptional swell near Vandenberg: NOAA buoy 46011 observations, experimental CDIP B1500 coastal forecasts, and Santa Barbara NWS coastal advisories. Offshore significant wave height, nearshore model height, and breaker height are explicitly distinguished. An initial historical calibration counts distinct episodes, not individual readings. Coverage is currently this coast only.
- NOAA OVATION provides a conservative local, dark-sky aurora signal with strict timestamp checks. It can miss aurora visible on the distant horizon; it is not a guarantee of seeing aurora.
- Condor Express RSS can surface explicitly dated, explicitly sized dolphin megapod reports. Daily trip totals and publication dates do not qualify. The parser intentionally stays quiet when the feed lacks the required detail.
- CDFW's published expected grunion schedule replaces the coordinator's lunar-date heuristic. The Santa Barbara adjustment comes from CDFW; fish presence remains unconfirmed.
- Moonbow candidate nights, bioluminescent surf, winter waterfowl flights and Pinnacles condors are added as clearly labelled search targets. These do not pretend to have automatic live confirmation.
- Major meteor planning extends to a year using the existing solar-longitude solver. Local visibility and weather remain separate.

Reliability fixes include behavior-specific evidence gates, expired sighting removal, correct iNaturalist categories, the full fourteen-day corroboration query, visible closure information, and persistent notification deduplication. Forecast refreshes and small score changes do not repeatedly notify. A meaningful timing shift, new confirmation, or substantial comparable wave-height increase can produce an update.

## Updating and notifications

Update through HACS and restart Home Assistant. Refresh the dashboard to load the card. Select **Planning calendar** for existing cards; explicit **Timeline** configurations retain the older standalone browser view. New cards default to the planner. Existing installations with all previous categories enabled also enable Waves; otherwise enable it in the integration options.

The integration emits `photography_events_opportunity` events. Mobile delivery requires an automation targeting your own notification service; use the example in README. Existing automations triggered by the binary sensor still work, but should be switched to the event trigger to receive meaningful updates without refresh noise. No notification destination is configured automatically.

## Limits that remain visible

Whale Safe credentials/endpoints are still unavailable. Rutting, cubs, pupping, monarch aggregation, blooms, foliage, glowing surf and waterfall conditions do not all have connected dated behavior reports. A recent species observation is not proof of the named spectacle. Getting inside sixty days never promotes a seasonal guess into confirmed timing.

Solar eclipse drive filtering still needs sourced path geometry; the retained standalone eclipse table ends in 2028. Moonbow viewpoint geometry, current waterfall flow, additional coastal calibrations, and verified elevated wave viewpoints remain future work. The wave backtest measures historical episode frequency, not operational forecast skill or future annual frequency. See SOURCE_VALIDATION.md for the evidence and limits.
