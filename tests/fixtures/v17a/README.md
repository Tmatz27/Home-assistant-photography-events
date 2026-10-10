# V17A synthetic contract fixtures

These are public DTO-shaped examples at Core b140147 / API v1 / schema 0008.
No actual observation, observer, source report, private point or token is used.
The approved location `(0, 0)` is a synthetic Core-derived policy example,
not a wildlife sighting or a usable California destination. IDs and all public
prose are synthetic. Adversarial sentinels are injected by tests, not live data.

| Fixture | Actual response shape / purpose |
| --- | --- |
| complete_empty | OpportunityList, complete current published generation with zero rows. It cannot prove category/horizon coverage alone. |
| never_assessed | OpportunityList with null assessment_id/data_as_of and incomplete state. |
| incomplete | OpportunityList with missing required safety source. |
| degraded | OpportunityList with degraded source. |
| approved_public | OpportunityList + every current Opportunity and nested Gear/PublicLocation field; synthetic eligible public row. |
| stale | OpportunityList with held expired product and old data_as_of even though generated_at is recent. |
| withheld | OpportunityList + withheld location with no coordinates; nonactionable. |
| unknown_safety_access | OpportunityList + held product with unknown safety/access/conditions. |
| incompatible | Deliberate API v2 compatibility failure; schema Version strings alone do not reject it. |
| shadow_patterns | Exact PatternResponse envelope with held preview_opportunities; never a normal opportunity list. |
| source_health | SourceHealthList and exact SourceHealth fields; UP does not prove assessment coverage. |

`tests/v17a_contract_model.py` is an executable example of the proposed boundary,
loaded only by tests. `coverage='verified'` is a hypothetical independently
reviewed test witness, never an invented upstream field or an assertion that the
current Core production product has full coverage. The default is unverified.
Likewise `origin='shadow'` comes from the authenticated route selected by HA, not
from a browser assertion. Synthetic actionable flags exercise the proposed
read-only display gate; notifications_enabled is always false.

Tests check distinct states, exact approved destination pairs, withheld prose,
unknown nested fields/credentials/geometry, nonfinite values, versions, bounds,
expiry, stable identities and input immutability. They also load normal fixtures
through the existing HA CoreAssessment parser without changing its assertions.
They do not implement WebSocket auth, paging, HA migration, persistence or live
Core publication. Those are explicit V17B test gates, not a V17A pass claim.

Correction fixtures under `policy/` are outside the 11 upstream DTO examples:
`core-destinations.json` simulates a Core-curated definition artifact; separate
`destination-review.json` pins its canonical SHA-256, Core reference and policy
revision. Both explicitly say synthetic; neither is an actual b140147 export.
The model loads these instead of owning a hand-maintained PUBLIC dictionary.
Changed source/revision/content or product definition provenance fails closed;
changing the loaded artifact never automatically updates the review witness.

The corrected model requires explicit HA fetched_at and accepts saved_at solely
as cache provenance. Named limits are 15 minutes from fetched_at, a provisional
six hours from envelope data_as_of, and each row's unchanged valid_until.
Generated_at is provenance only. Tests isolate all three expiry mechanisms,
including exact boundaries, mixed expired/current rows and cached/offline status.
