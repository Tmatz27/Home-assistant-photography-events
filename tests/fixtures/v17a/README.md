# V17A synthetic contract fixtures

These are public DTO-shaped examples at Core b140147 / API v1 / schema 0008.
No actual observation, observer, source report, private point or token is used.
The approved location `(0, 0)` is a synthetic visitor-destination registry entry,
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
