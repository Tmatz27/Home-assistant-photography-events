# V17B narrow independent-review corrections

Reviewed starting main: `bfe7db4d7f8b2f808d515d92cbfb0ff222b2626b`.
Correction build: `0.17.0-dev.2`, still API `ha.v17.1`, Core v1/schema0008.
No production release, tag, Core/Unraid changes or live HA deployment.

## Reproductions and corrected behavior

- **Birds/Planner:** a sanitized M1 Tule elk row previously survived both views
  despite their `unsupported` coverage. Production projections now emit no
  ordinary rows under unsupported coverage, while keeping Core assessment
  state, connection, freshness, unknown counts and occurrence identity intact.
  The card independently hides unsupported rows and excludes non-birds from
  Birds. No reviewed bird/planner coverage is invented. Verified planner-range
  rendering remains tested with explicitly synthetic, test-only scope witnesses.
- **Shared-user scheduling:** two cards requesting one view on one HA account
  previously turned `rate_limited` into an offline state. Rate limits now show
  busy scheduling; retained snapshots keep their original timestamps and age
  normally. Up to four delayed retries per read series use 1.1–3.1 s jittered
  delays, with one request in flight and summary pushes coalesced. Exhaustion
  stays busy until a later refresh. No cache yields busy/unknown, not Core offline.
  Detach, entry/user/view changes and incompatible projection cancel delayed
  work; stale in-flight responses cannot populate a different context. The
  server's shared-user one-second limit remains unchanged.
- **Bearer origin binding:** blank reconfigure tokens reuse stored credentials
  only for the same canonical scheme, IDNA-normalized hostname and effective
  port. Host case, default port spelling and a terminal slash do not create an
  origin change. Changed origins require an explicit new token before even
  readiness is requested. Invalid responses preserve the old entry/configuration.
  A real two-server test captures Authorization at both endpoints, proving no
  old bearer reaches the replacement server; same-origin reuse and explicitly
  supplied replacement tokens still validate through HA's shared HTTP session.
- **Cursor validity:** saved pages recheck original common deadlines plus every
  row's remaining `valid_until` and any actionable row's end time against the
  current bridge clock. Expired saved eligibility returns `snapshot_expired`,
  even if a coordinator reports the same revision. No cursor renews evidence,
  safety or transport; normal entry/user/view/revision limits remain intact.

## Test preservation

All historical tests remain. Three V17B tests had fixtures encoding the defects:
the row-freshness test now uses supported held Watching context; the month-bar
positive uses a verified current test scope rather than unsupported coverage;
blank-token retention uses the same origin. Their original assertions remain,
with new negative tests covering the rejected cases. Actual shipped-card tests
exercise competing clients, bounded/coalesced retries, aging, cancellation,
incompatibility, navigation, host, expansion, focus and inner scroll. Real HA
tests independently enforce the shared limiter and cursor expiry.

## Product and migration boundaries

Destination approval is still false and production coverage remains unverified.
Birds, broad Planner coverage and calendar precision remain unsupported. Choices
and notifications remain disabled, including `photography_events_opportunity`.
User-owned HA automations with unrestricted state triggers may react once when
old entities become unavailable during migration; the integration cannot prevent
all external automations. Review those automations in the isolated test instance.

Authenticated actual-Unraid-to-HA deployment remains untested. HTTP security
proof uses two disposable loopback servers; render fixtures are synthetic.
Install/rollback instructions remain in `IMPLEMENTATION.md`; do not edit the
user's running HA or manually change `.storage`.

Full counts, exact changed files, final published SHA and final-head CI are in
the delivery receipt. Run all existing Python, real-HA, frontend, build/version,
pyflakes and active-boundary suites; no historical suite is removed or bypassed.

READY FOR V17B CORRECTION INDEPENDENT CLAUDE REVIEW
