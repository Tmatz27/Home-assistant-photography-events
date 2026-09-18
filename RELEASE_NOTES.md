# Photography Events 0.14.1

A reliability fix to the USGS migration shipped in 0.14.0.

The move off the legacy WaterServices API is right — it is decommissioned in the first quarter of 2027, and the `/continuous` collection is USGS's documented replacement for `/iv`. What could not be checked from the development sandbox, which has no route to the host, was which version path is actually serving. Everything USGS publishes points at `v0` as live, with no retirement date announced for it; `v1` is the obvious successor and may already be up.

- **Both versions are now tried, in order.** Pinning one and guessing wrong loses the river gauge silently, because a 404 is indistinguishable from an outage — the source-health panel would report a service problem that no amount of waiting fixes. Trying both costs one extra request on the first cycle after a version disappears.
- **A schema change no longer reads as an outage.** If USGS answers and every reading fails the station, unit, statistic or approval filters, the integration now says so in as many words. One of those is waited out and the other is a code fix, and they were indistinguishable.

Checked and deliberately left unchanged from 0.14.0: the strict field filtering is correct — the continuous collection does carry `statistic_id` alongside `monitoring_location_id`, `parameter_code`, `time`, `value`, `unit_of_measure`, `approval_status` and `qualifier` — and so is the pagination guard, which catches a truncated window that the legacy service was never able to produce.

Nothing else changed. The river gauge annotates Yosemite moonbow and firefall rows with basin flow; it still never claims to have measured either waterfall.
