# Photography Events 0.17.0-dev.3

Engineering compatibility fix only; no release or tag is published. Private Core connection now accepts API v1 with schema 0008 or 0009 and engine 0.1.0-dev. Future schemas remain rejected. Bearer authentication, URL-origin binding, strict response/privacy validation, pending destination review and all read-only boundaries remain active. Dashboard changes are limited to the synchronized build version.

See `docs/v17b/SCHEMA_COMPATIBILITY.md` for pinned Core response verification and test reproduction. Existing entries can reconnect or reauthenticate without adding another integration. No PostgreSQL, Core service, collector or live HA changes are required by this code change.

# Photography Events 0.17.0-dev.2

See `docs/v17b/CORRECTIONS.md` for the narrow independent-review fixes. This is not a production release or live installation.

# Photography Events 0.17.0-dev.1

Development build for isolated Home Assistant testing only. No release or tag is published.

The active integration now reads Photography Events Core v1/schema 0008 privately. It retains entry/entity identity and the familiar four-view card, while replacing local intelligence with explicit Core status and supported normal products. Coverage remains unverified. Public locations are withheld pending independent review; Birds/year-wide planning/calendar precision and choices are unavailable. All notifications remain cancelled.

Back up the isolated HA configuration before migration. Config entries become version 3; rollback requires matching old code and the pre-migration configuration backup. Core failures never reactivate the old engine.

See docs/v17b/IMPLEMENTATION.md for installation, supported limits and verification.

---

Historical release notes:

# Photography Events 0.16.1

A focused usability and bugfix release. Installed-Home-Assistant verification remains outstanding.

- Fix dashboard scroll jumps during card interactions by retaining the card host and preserving the initiating control's visual position across layout updates.
- Navigate within one card: **Can't Miss | Watching | Year Planner | Birds**. Existing `action_hero`, `calendar_outlook`, `birds` and no-mode YAML keep their initial-view behavior.
- Make tracked but non-actionable phenomena visible in **Watching**, with report context, missing evidence, dates, place, drive information and backend reasons. Can't Miss includes a compact Watching summary.
- Display foliage as **Fall Color** with a leaf icon. In-window foliage awaiting its first report is visible in Watching. Confirmed foliage beyond the drive limit stays in Year Planner with the drive reason. Undated reports remain context, never confirmation.
- Can't Miss retains its evidence, significance, safety/access and six-hour drive gates. Healthy empty, incomplete, held and Watch remain distinct.
- No new geographic coverage, map, destination alerts, source expansion or Phase 2 work.

Restart Home Assistant and refresh the dashboard after upgrading. Synthetic browser and HA tests do not establish that the user's installed dashboard or live providers have been verified.
