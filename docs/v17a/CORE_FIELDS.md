# Exact Core field ledger at b140147

P = available, production-defined API field (not a claim that the phenomenon is production-supported). S = available shadow/provisional field. F = forbidden from the normal frontend. M = missing; see CONTRACT.md feature ledger. Field names/types below come from actual source, not an invented v1 replacement.

Normal endpoint mapping: `/health/ready` -> Health; `/api/v1/opportunities` -> OpportunityList; `/api/v1/opportunities/{occurrence_key}` -> Opportunity; `/api/v1/sources/health` -> SourceHealthList. Version inherits Contract and has core_version/api_version/schema_version. OpportunityList and health lists inherit Version. Debug source-contracts -> ContractResponse; live/calibration -> CalibrationResponse; patterns -> PatternResponse. Debug responses do not uniformly inherit Version or supply timestamps; never assume they share the normal envelope.

## `Version` — `src/pec/schemas.py:14`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `core_version` | `str` | P; explicit allowlist only |
| `api_version` | `str` | P; explicit allowlist only |
| `schema_version` | `str` | P; explicit allowlist only |

## `Health` — `src/pec/schemas.py:20`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `status` | `Literal['alive', 'ready']` | P; explicit allowlist only |

## `PublicLocation` — `src/pec/schemas.py:24`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `key` | `str` | P; coordinates/name/key only for verified curated destination; withheld serializes no identifying location |
| `name` | `str` | P; coordinates/name/key only for verified curated destination; withheld serializes no identifying location |
| `latitude` | `float | None = Field(default=None, ge=-90, le=90)` | P; coordinates/name/key only for verified curated destination; withheld serializes no identifying location |
| `longitude` | `float | None = Field(default=None, ge=-180, le=180)` | P; coordinates/name/key only for verified curated destination; withheld serializes no identifying location |
| `policy` | `Literal['curated_public_site', 'withheld'] = 'curated_public_site'` | P; coordinates/name/key only for verified curated destination; withheld serializes no identifying location |

## `Gear` — `src/pec/schemas.py:32`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `take` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |
| `optional` | `list[str] = Field(default_factory=list)` | P; bounded reviewed public text; never arbitrary raw provider text |
| `skip` | `list[str] = Field(default_factory=list)` | P; bounded reviewed public text; never arbitrary raw provider text |
| `start` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |
| `support` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |
| `technique` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |
| `video` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |
| `drone` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |
| `drone_status` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |

## `Opportunity` — `src/pec/schemas.py:44`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `assessment_id` | `int | None = None` | P; backend snapshot identity; not occurrence identity |
| `pattern_episode_id` | `int | None = None` | S; F internal database identity; no frontend choice identity |
| `occurrence_key` | `str` | P; explicit allowlist only |
| `phenomenon_key` | `str` | P; explicit allowlist only |
| `title` | `str` | P; explicit allowlist only |
| `category` | `Literal['mammals', 'birds', 'insects']` | P; explicit allowlist only |
| `location` | `PublicLocation` | P; explicit allowlist only |
| `starts_at` | `AwareDatetime` | P; explicit allowlist only |
| `ends_at` | `AwareDatetime` | P; explicit allowlist only |
| `presentation` | `Presentation` | P; explicit allowlist only |
| `eligibility` | `bool` | P; explicit allowlist only |
| `significance` | `int = Field(ge=0, le=100)` | P; explicit allowlist only |
| `confidence` | `int = Field(ge=0, le=100)` | P; explicit allowlist only |
| `urgency` | `int = Field(ge=0, le=100)` | P; explicit allowlist only |
| `evidence_state` | `str` | P; explicit allowlist only |
| `access_state` | `str` | P; explicit allowlist only |
| `safety_state` | `Literal['safe', 'caution', 'unsafe', 'unknown']` | P; explicit allowlist only |
| `condition_state` | `Literal['not_required', 'unknown'] = 'not_required'` | P; explicit allowlist only |
| `drive_minutes` | `float | None = Field(default=None, ge=0)` | P; explicit allowlist only |
| `drive_basis` | `str` | P; explicit allowlist only |
| `reason` | `str` | P; bounded reviewed public text; never arbitrary raw provider text |
| `awaiting` | `str` | P; bounded reviewed public text; never arbitrary raw provider text |
| `blockers` | `list[str]` | P; bounded reviewed public text; never arbitrary raw provider text |
| `held` | `bool` | P; explicit allowlist only |
| `watching` | `bool` | P; explicit allowlist only |
| `bird_classification` | `Literal['spectacle', 'encounter'] | None = None` | P; explicit allowlist only |
| `gear` | `Gear` | P; explicit allowlist only |
| `ethics` | `str` | P; bounded reviewed public text; never arbitrary raw provider text |
| `safety_summary` | `str` | P; bounded reviewed public text; never arbitrary raw provider text |
| `safety_notes` | `list[str]` | P; bounded reviewed public text; never arbitrary raw provider text |
| `best_time_of_day` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |
| `detail` | `str = ''` | P; bounded reviewed public text; never arbitrary raw provider text |
| `data_as_of` | `AwareDatetime` | P; explicit allowlist only |
| `valid_until` | `AwareDatetime` | P; explicit allowlist only |
| `definition_key` | `str` | P; explicit allowlist only |
| `definition_version` | `str` | P; explicit allowlist only |
| `definition_hash` | `str` | P; explicit allowlist only |
| `engine_version` | `str` | P; explicit allowlist only |

## `OpportunityList` — `src/pec/schemas.py:85`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `assessment_id` | `int | None = None` | P; backend snapshot identity; not occurrence identity |
| `generated_at` | `AwareDatetime` | P; explicit allowlist only |
| `data_as_of` | `AwareDatetime | None` | P; explicit allowlist only |
| `assessment_state` | `Literal['complete', 'incomplete', 'degraded']` | P; explicit allowlist only |
| `missing_required_sources` | `list[str]` | P; explicit allowlist only |
| `degraded_sources` | `list[str]` | P; explicit allowlist only |
| `items` | `list[Opportunity]` | P; explicit allowlist only |

## `SourceHealth` — `src/pec/schemas.py:95`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `key` | `str` | P; explicit allowlist only |
| `state` | `Literal['UP', 'STALE', 'DOWN']` | P; explicit allowlist only |
| `last_attempt_at` | `AwareDatetime | None` | P; explicit allowlist only |
| `last_success_at` | `AwareDatetime | None` | P; explicit allowlist only |
| `provider_updated_at` | `AwareDatetime | None` | P; explicit allowlist only |
| `error_code` | `str | None` | P; explicit allowlist only |

## `SourceHealthList` — `src/pec/schemas.py:104`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `generated_at` | `AwareDatetime` | P; explicit allowlist only |
| `items` | `list[SourceHealth]` | P; explicit allowlist only |

## `ErrorDetail` — `src/pec/schemas.py:109`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `code` | `str` | P; explicit allowlist only |
| `message` | `str` | P; explicit allowlist only |

## `Error` — `src/pec/schemas.py:114`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `error` | `ErrorDetail` | P; explicit allowlist only |

## `Volume` — `src/pec/sources/debug.py:18`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `requests` | `int` | S; F from normal card; backend audit only |
| `received` | `int` | S; F from normal card; backend audit only |
| `accepted` | `int` | S; F from normal card; backend audit only |
| `rejected` | `int` | S; F from normal card; backend audit only |
| `bytes` | `int` | S; F from normal card; backend audit only |
| `corrections` | `int` | S; F from normal card; backend audit only |
| `duplicates` | `int` | S; F from normal card; backend audit only |
| `reinstated` | `int` | S; F from normal card; backend audit only |
| `obscured` | `int` | S; F from normal card; backend audit only |
| `private` | `int` | S; F from normal card; backend audit only |
| `rate_limits` | `int` | S; F from normal card; backend audit only |
| `unique_records` | `int` | S; F from normal card; backend audit only |
| `obscured_percentage` | `float | None` | S; F from normal card; backend audit only |
| `private_percentage` | `float | None` | S; F from normal card; backend audit only |

## `OutcomeCounts` — `src/pec/sources/debug.py:35`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `accepted` | `int` | S; F from normal card; backend audit only |
| `duplicate` | `int` | S; F from normal card; backend audit only |
| `reinstated` | `int` | S; F from normal card; backend audit only |
| `rejected_invalid` | `int` | S; F from normal card; backend audit only |
| `skipped_stale_version` | `int` | S; F from normal card; backend audit only |
| `skipped_replay` | `int` | S; F from normal card; backend audit only |
| `ignored_out_of_order_poll` | `int` | S; F from normal card; backend audit only |
| `incomplete_snapshot` | `int` | S; F from normal card; backend audit only |

## `Operational` — `src/pec/sources/debug.py:46`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `status` | `str` | S; F from normal card; backend audit only |
| `provider_updated_at` | `datetime | None` | S; F from normal card; backend audit only |
| `records_received` | `int` | S; F from normal card; backend audit only |
| `records_accepted` | `int` | S; F from normal card; backend audit only |
| `records_rejected` | `int` | S; F from normal card; backend audit only |
| `parser_error_counts` | `dict[str, int]` | S; F from normal card; backend audit only |
| `error_code` | `str | None` | S; F from normal card; backend audit only |
| `incomplete` | `bool` | S; F from normal card; backend audit only |
| `latency_ms` | `int` | S; F from normal card; backend audit only |
| `next_allowed_at` | `datetime | None` | S; F from normal card; backend audit only |
| `consecutive_failures` | `int | None` | S; F from normal card; backend audit only |
| `last_successful_fetch` | `datetime | None` | S; F from normal card; backend audit only |
| `requests_reserved_today` | `int` | S; F from normal card; backend audit only |
| `alert_native_asof` | `str | None` | S; F from normal card; backend audit only |
| `skip_reason_counts` | `dict[str, int] = Field(default_factory=dict)` | S; F from normal card; backend audit only |
| `outcome_counts` | `OutcomeCounts | None = None` | S; F from normal card; backend audit only |
| `poll_outcome` | `Literal['complete', 'incomplete', 'ignored_out_of_order_poll'] | None = None` | S; F from normal card; backend audit only |

## `ContractView` — `src/pec/sources/debug.py:66`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `contract` | `SourceContract` | S; F from normal card; backend audit only |
| `contract_hash` | `str` | S; F from normal card; backend audit only |
| `freshness` | `Literal['current', 'stale', 'unknown']` | S; F from normal card; backend audit only |
| `operational` | `Operational | None` | S; F from normal card; backend audit only |
| `utc_day_volume` | `Volume` | S; F from normal card; backend audit only |

## `ContractResponse` — `src/pec/sources/debug.py:74`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `mode` | `Literal['shadow'] = 'shadow'` | S; F from normal card; backend audit only |
| `production_promotion` | `Literal[False] = False` | S; F from normal card; backend audit only |
| `generated_at` | `datetime` | S; F from normal card; backend audit only |
| `items` | `list[ContractView]` | S; F from normal card; backend audit only |

## `CalibrationView` — `src/pec/sources/debug.py:81`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `phenomenon_key` | `str` | S; F from normal card; backend audit only |
| `level` | `Literal['none', 'signal', 'developing_watch']` | S; F from normal card; backend audit only |
| `provenance_kind` | `Literal['CORE_INTERPRETATION'] = 'CORE_INTERPRETATION'` | S; F from normal card; backend audit only |
| `policy_basis` | `str` | S; F from normal card; backend audit only |
| `policy_provenance` | `Literal['PHENOMENON_POLICY'] = 'PHENOMENON_POLICY'` | S; F from normal card; backend audit only |
| `production_eligibility` | `Literal[False] = False` | S; F from normal card; backend audit only |
| `animal_count` | `None = None` | S; F from normal card; backend audit only |
| `major_aggregation_confirmed` | `Literal[False] = False` | S; F from normal card; backend audit only |
| `behavior_confirmation` | `Literal[False] = False` | S; F from normal card; backend audit only |
| `condition` | `str` | S; F from normal card; backend audit only |
| `safety` | `Literal['hold_candidate', 'no_intersection', 'unknown', 'not_assessed']` | S; F from normal card; backend audit only |
| `destination_key` | `str | None` | S; F from normal card; backend audit only |

## `CalibrationResponse` — `src/pec/sources/debug.py:96`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `mode` | `Literal['off', 'shadow']` | S; F from normal card; backend audit only |
| `production_promotion` | `Literal[False] = False` | S; F from normal card; backend audit only |
| `pattern_analysis_state` | `str` | S; F from normal card; backend audit only |
| `sources` | `dict[str, Literal['current', 'stale', 'unknown']] = Field(default_factory=dict)` | S; F from normal card; backend audit only |
| `items` | `list[CalibrationView]` | S; F from normal card; backend audit only |
| `monarch_count_confirmation` | `str` | S; F from normal card; backend audit only |

## `SourceContract` — `src/pec/sources/contracts.py:10`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `source_key` | `str` | S; F from normal card; backend audit only |
| `provider_name` | `str` | S; F from normal card; backend audit only |
| `interface` | `str` | S; F from normal card; backend audit only |
| `roles` | `tuple[str, ...]` | S; F from normal card; backend audit only |
| `authentication` | `str` | S; F from normal card; backend audit only |
| `polling_seconds` | `int` | S; F from normal card; backend audit only |
| `request_spacing_seconds` | `float` | S; F from normal card; backend audit only |
| `requests_per_day` | `int` | S; F from normal card; backend audit only |
| `pagination` | `str` | S; F from normal card; backend audit only |
| `identity` | `str` | S; F from normal card; backend audit only |
| `corrections` | `str` | S; F from normal card; backend audit only |
| `deletion` | `str` | S; F from normal card; backend audit only |
| `evidence_time` | `str` | S; F from normal card; backend audit only |
| `provider_time` | `str` | S; F from normal card; backend audit only |
| `location` | `str` | S; F from normal card; backend audit only |
| `precision` | `str` | S; F from normal card; backend audit only |
| `geoprivacy` | `str` | S; F from normal card; backend audit only |
| `counts` | `str` | S; F from normal card; backend audit only |
| `behavior` | `str` | S; F from normal card; backend audit only |
| `quality` | `str` | S; F from normal card; backend audit only |
| `freshness_seconds` | `int` | S; F from normal card; backend audit only |
| `malformed` | `str` | S; F from normal card; backend audit only |
| `can_prove` | `tuple[str, ...]` | S; F from normal card; backend audit only |
| `cannot_prove` | `tuple[str, ...]` | S; F from normal card; backend audit only |
| `retention` | `str` | S; F from normal card; backend audit only |
| `parser_version` | `str = 'public-contract-3'` | S; F from normal card; backend audit only |
| `version` | `str = 'm3a-3'` | S; F from normal card; backend audit only |
| `provider_clock_skew_seconds` | `int = 3600` | S; F from normal card; backend audit only |

## `Metrics` — `src/pec/patterns/api.py:12`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `provider_record_count` | `int` | S; F from normal card; backend audit only |
| `observation_count` | `int` | S; F from normal card; backend audit only |
| `independent_report_count` | `int` | S; F from normal card; backend audit only |
| `independent_source_count` | `int` | S; F from normal card; backend audit only |
| `max_single_report_count` | `int | None` | S; F from normal card; backend audit only |
| `behaviors` | `list[str]` | S; F from normal card; backend audit only |

## `PatternView` — `src/pec/patterns/api.py:21`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `episode_key` | `str` | S; F from normal card; backend audit only |
| `phenomenon_key` | `str` | S; F from normal card; backend audit only |
| `state` | `Literal['developing', 'qualified', 'ended']` | S; F from normal card; backend audit only |
| `policy_version` | `str` | S; F from normal card; backend audit only |
| `policy_hash` | `str` | S; F from normal card; backend audit only |
| `transition` | `str` | S; F from normal card; backend audit only |
| `redacted` | `bool` | S; F from normal card; backend audit only |
| `summary` | `str` | S; F from normal card; backend audit only |
| `metrics` | `Metrics | None = None` | S; F from normal card; backend audit only |
| `location` | `PublicLocation | None = None` | S; F from normal card; backend audit only |

## `ClusterView` — `src/pec/patterns/api.py:34`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `cluster_id` | `int` | S; F from normal card; backend audit only |
| `phenomenon_key` | `str` | S; F from normal card; backend audit only |
| `policy_version` | `str` | S; F from normal card; backend audit only |
| `policy_hash` | `str` | S; F from normal card; backend audit only |
| `redacted` | `bool` | S; F from normal card; backend audit only |
| `metrics` | `Metrics | None = None` | S; F from normal card; backend audit only |

## `CoherenceMetrics` — `src/pec/patterns/api.py:43`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `candidate_observation_count` | `int` | S; F from normal card; backend audit only |
| `independent_report_count` | `int` | S; F from normal card; backend audit only |
| `candidate_radius_meters` | `float` | S; F from normal card; backend audit only |
| `candidate_diameter_meters` | `float` | S; F from normal card; backend audit only |
| `recovered_cluster_count` | `int` | S; F from normal card; backend audit only |

## `CoherenceView` — `src/pec/patterns/api.py:51`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `phenomenon_key` | `str` | S; F from normal card; backend audit only |
| `state` | `Literal['coherence_rejected'] = 'coherence_rejected'` | S; F from normal card; backend audit only |
| `policy_version` | `str` | S; F from normal card; backend audit only |
| `policy_hash` | `str` | S; F from normal card; backend audit only |
| `primary_eps_meters` | `float` | S; F from normal card; backend audit only |
| `maximum_diameter_meters` | `float` | S; F from normal card; backend audit only |
| `fallback_eps_meters` | `float | None` | S; F from normal card; backend audit only |
| `fallback_attempted` | `bool` | S; F from normal card; backend audit only |
| `fallback_result` | `str` | S; F from normal card; backend audit only |
| `redacted` | `bool` | S; F from normal card; backend audit only |
| `metrics` | `CoherenceMetrics | None = None` | S; F from normal card; backend audit only |

## `PatternResponse` — `src/pec/patterns/api.py:65`

| Field | Actual type/default | Classification and frontend disposition |
| --- | --- | --- |
| `core_version` | `str` | S; F from normal card; backend audit only |
| `api_version` | `str` | S; F from normal card; backend audit only |
| `schema_version` | `str` | S; F from normal card; backend audit only |
| `assessment_id` | `int | None` | S; F from normal card; backend audit only |
| `mode` | `Literal['off', 'shadow']` | S; F from normal card; backend audit only |
| `analysis_state` | `Literal['disabled', 'unassessed', 'current', 'outdated']` | S; F from normal card; backend audit only |
| `items` | `list[PatternView]` | S; F from normal card; backend audit only |
| `clusters` | `list[ClusterView]` | S; F from normal card; backend audit only |
| `preview_opportunities` | `list[Opportunity]` | S; F from normal card; backend audit only |
| `coherence_rejections` | `list[CoherenceView] = Field(default_factory=list)` | S; F from normal card; backend audit only |
| `identity_rejected_count` | `int = 0` | S; F from normal card; backend audit only |

## Forbidden data, whether or not future APIs add it

Credentials, connection origins/headers, raw observation identifiers/descriptions, provider geometry, protected/obscured points, private observer locations, analysis centroids, cluster membership, arbitrary destinations and numeric internal evidence IDs are F. Discard additive unknown fields recursively. No geographic hint or offset is derived for a withheld sighting.

Debug aggregate metrics and summaries remain S even where already redacted. A qualified pattern is not a production opportunity. The existence of a curated Pismo destination in shadow calibration does not promote monarch opportunities. Normal publication is separate from pattern computation.
