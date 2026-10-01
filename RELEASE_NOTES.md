# Photography Events 0.16.1

A focused usability and bugfix release. Installed-Home-Assistant verification remains outstanding.

- Fix dashboard scroll jumps during card interactions by retaining the card host and preserving the initiating control's visual position across layout updates.
- Navigate within one card: **Can't Miss | Watching | Year Planner | Birds**. Existing `action_hero`, `calendar_outlook`, `birds` and no-mode YAML keep their initial-view behavior.
- Make tracked but non-actionable phenomena visible in **Watching**, with report context, missing evidence, dates, place, drive information and backend reasons. Can't Miss includes a compact Watching summary.
- Display foliage as **Fall Color** with a leaf icon. In-window foliage awaiting its first report is visible in Watching. Confirmed foliage beyond the drive limit stays in Year Planner with the drive reason. Undated reports remain context, never confirmation.
- Can't Miss retains its evidence, significance, safety/access and six-hour drive gates. Healthy empty, incomplete, held and Watch remain distinct.
- No new geographic coverage, map, destination alerts, source expansion or Phase 2 work.

Restart Home Assistant and refresh the dashboard after upgrading. Synthetic browser and HA tests do not establish that the user's installed dashboard or live providers have been verified.
