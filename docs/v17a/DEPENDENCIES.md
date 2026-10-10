# V17A verified dependency inventory

Audited HA `c76726ece1e485ece03810087927da344289fba7`; Core `b14014760beee2c18d02a2b1f36756f6faee93a0` on 2026-10-09 (America/Los_Angeles). Both remote main heads matched the supplied anchors. Clean HA main checkout; no pre-existing changes. Core reference is read-only. This table is extracted from AST, including imports inside functions; it is an import inventory, not proof that every import executes.

All Python paths below are relative to `custom_components/photography_events/`. Each requested root and its direct local imports was inspected. Imported helper dependencies are also listed so network/provider code is not inferred from a module name.

## `__init__.py` (requested root)

| Line | Import |
| --- | --- |
| 3 | `from __future__ import annotations` |
| 5 | `import logging` |
| 6 | `from pathlib import Path` |
| 8 | `import voluptuous as vol` |
| 9 | `from homeassistant.config_entries import ConfigEntry` |
| 10 | `from homeassistant.const import Platform` |
| 11 | `from homeassistant.core import HomeAssistant, ServiceCall` |
| 12 | `from homeassistant.helpers import config_validation as cv` |
| 13 | `from homeassistant.util import dt as dt_util` |
| 15 | `from .const import ALL_CATEGORIES, DOMAIN` |
| 16 | `from .coordinator import PhotographyEventsCoordinator` |
| 118 | `from .email_reports import parse_email_report` |
| 161 | `from homeassistant.components.frontend import add_extra_js_url` |
| 162 | `from homeassistant.components.http import StaticPathConfig` |

## `binary_sensor.py` (requested root)

| Line | Import |
| --- | --- |
| 3 | `from __future__ import annotations` |
| 5 | `from homeassistant.components.binary_sensor import BinarySensorEntity` |
| 6 | `from homeassistant.config_entries import ConfigEntry` |
| 7 | `from homeassistant.core import HomeAssistant` |
| 8 | `from homeassistant.helpers.entity_platform import AddEntitiesCallback` |
| 9 | `from homeassistant.helpers.update_coordinator import CoordinatorEntity` |
| 11 | `from .const import DOMAIN` |
| 12 | `from .event_state import event_id` |
| 13 | `from .coordinator import PhotographyEventsCoordinator` |

## `birds.py` (direct helper)

| Line | Import |
| --- | --- |
| 26 | `from __future__ import annotations` |
| 28 | `from datetime import datetime, timedelta` |
| 30 | `from .events import MARINE_DRAW, PHOTOGRAPHY_BIRDS, Opportunity` |
| 31 | `from .gear import LAND_NPS, LAND_REFUGE, LAND_UNKNOWN, recommend` |
| 32 | `from .observations import admissible` |
| 33 | `from .wildlife import estimate_drive_hours, haversine_km` |
| 37 | `from .curation import definition` |
| 191 | `from .const import ZONES_BY_ID` |
| 309 | `from .curation import definition` |
| 310 | `from .observations import admissible, report_point` |

## `calendar.py` (requested root)

| Line | Import |
| --- | --- |
| 3 | `from __future__ import annotations` |
| 5 | `from datetime import datetime, timedelta` |
| 7 | `from homeassistant.components.calendar import CalendarEntity, CalendarEvent` |
| 8 | `from homeassistant.config_entries import ConfigEntry` |
| 9 | `from homeassistant.core import HomeAssistant` |
| 10 | `from homeassistant.helpers.entity_platform import AddEntitiesCallback` |
| 11 | `from homeassistant.helpers.update_coordinator import CoordinatorEntity` |
| 12 | `from homeassistant.util import dt as dt_util` |
| 14 | `from .const import DOMAIN` |
| 15 | `from .coordinator import PhotographyEventsCoordinator` |

## `conditions.py` (direct helper)

| Line | Import |
| --- | --- |
| 14 | `from __future__ import annotations` |
| 16 | `import math` |
| 17 | `from datetime import datetime, timedelta` |
| 19 | `from . import astronomy, weather_scoring` |
| 227 | `from . import curation, verification` |

## `config_flow.py` (requested root)

| Line | Import |
| --- | --- |
| 19 | `from __future__ import annotations` |
| 21 | `from typing import Any` |
| 23 | `import voluptuous as vol` |
| 24 | `from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow` |
| 25 | `from homeassistant.core import callback` |
| 26 | `from homeassistant.data_entry_flow import FlowResult` |
| 27 | `from homeassistant.helpers import selector` |
| 29 | `from .const import ALL_CATEGORIES, CONF_ALERT_SCORE, CONF_EBIRD_API_KEY, CONF_ENABLE_FIELD_REPORTS, CONF_ENABLED_CATEGORIES, CONF_GOOGLE_API_KEY, CONF_NPS_API_KEY, CONF_MAX_DRIVE_HOURS, CONF_ROUTING_MODE, CONF_SUNSET_DRIVE_HOURS, CONF_SUNSET_SCORE, CONF_SUNSETWX_CLIENT_ID, CONF_SUNSETWX_CLIENT_SECRET, DEFAULT_ALERT_SCORE, DEFAULT_MAX_DRIVE_HOURS, DEFAULT_SUNSET_DRIVE_HOURS, DEFAULT_SUNSET_SCORE, DOMAIN, ROUTING_AUTO, ROUTING_MODES` |

## `const.py` (requested root)

| Line | Import |
| --- | --- |
| 3 | `from __future__ import annotations` |
| 5 | `from typing import Final` |

## `coordinator.py` (requested root)

| Line | Import |
| --- | --- |
| 24 | `from __future__ import annotations` |
| 26 | `import asyncio` |
| 27 | `import logging` |
| 28 | `import math` |
| 29 | `import json` |
| 30 | `from copy import deepcopy` |
| 31 | `from pathlib import Path` |
| 32 | `from datetime import datetime, timedelta, timezone` |
| 33 | `from typing import Any, Awaitable, Callable` |
| 35 | `from homeassistant.config_entries import ConfigEntry` |
| 36 | `from homeassistant.core import HomeAssistant` |
| 37 | `from homeassistant.helpers.aiohttp_client import async_get_clientsession` |
| 38 | `from homeassistant.helpers.update_coordinator import DataUpdateCoordinator` |
| 39 | `from homeassistant.helpers import issue_registry as ir` |
| 40 | `from homeassistant.util import dt as dt_util` |
| 42 | `from . import events as event_builder` |
| 43 | `from .event_state import EventState, event_id` |
| 44 | `from . import waves, spectacles, grunion, source_health, eclipses` |
| 45 | `from . import birds as birds_module, conditions, eligibility, lunar, signals as signals_module, sunburst, weather_hazards` |
| 46 | `from homeassistant.helpers.storage import Store` |
| 47 | `from . import field_reports as reports_module` |
| 53 | `from . import routing as routing_module` |
| 54 | `from . import verification as verify_module` |
| 55 | `from . import wildlife as wildlife_module` |
| 56 | `from .const import ALL_CATEGORIES, CATEGORY_ASTRO, CATEGORY_BIRDS, CATEGORY_BLOOMS, CATEGORY_FOLIAGE, CATEGORY_MARINE, CATEGORY_PARKS, CATEGORY_RARE, CATEGORY_SUNSET, CONF_ALERT_SCORE, CONF_EBIRD_API_KEY, CONF_ENABLE_FIELD_REPORTS, CONF_ENABLED_CATEGORIES, CONF_GOOGLE_API_KEY, CONF_HOME_LATITUDE, CONF_HOME_LONGITUDE, CONF_MAX_DRIVE_HOURS, CONF_NPS_API_KEY, CONF_ROUTING_MODE, CONF_SUNSET_SCORE, CONF_SUNSETWX_CLIENT_ID, CONF_SUNSETWX_CLIENT_SECRET, DEFAULT_ALERT_SCORE, DEFAULT_HOME, DEFAULT_MAX_DRIVE_HOURS, DEFAULT_SUNSET_SCORE, DEFAULT_UPDATE_MINUTES, DOMAIN, EBIRD_REGIONS, INATURALIST_URL, MARINE_TAXA, MIN_INTERVAL_EBIRD, MIN_INTERVAL_EBIRD_SPECIES, MIN_INTERVAL_SUNSETWX, MIN_INTERVAL_FIELD_REPORTS, MIN_INTERVAL_INATURALIST, MIN_INTERVAL_PARK_ALERTS, MIN_INTERVAL_ROUTING, MIN_INTERVAL_TIDES, MIN_INTERVAL_AIR_QUALITY, CONF_SUNSET_DRIVE_HOURS, DEFAULT_SUNSET_DRIVE_HOURS, MIN_INTERVAL_WEATHER, OPEN_METEO_AIR_QUALITY_URL, OPEN_METEO_URL, ROUTING_AUTO, ROUTING_LEGACY, ROUTING_OFF, ROUTING_ROUTES, TARGET_ZONES` |
| 108 | `from .throttle import Source` |
| 109 | `from . import phenomena as phenomena_module` |
| 110 | `from . import streamflow as streamflow_module` |
| 111 | `from . import weather_scoring` |
| 112 | `from .weather_scoring import build_air_quality_params, build_open_meteo_params` |

## `core_bridge.py` (requested root)

| Line | Import |
| --- | --- |
| 6 | `import copy` |
| 7 | `import hashlib` |
| 8 | `from datetime import datetime, timezone, timedelta` |
| 10 | `from .core_client import CoreAssessment, CoreError, aware_timestamp, PhotographyEventsCoreClient` |
| 64 | `from homeassistant.helpers.aiohttp_client import async_get_clientsession` |
| 65 | `from homeassistant.helpers.storage import Store` |

## `core_client.py` (requested root)

| Line | Import |
| --- | --- |
| 6 | `from __future__ import annotations` |
| 8 | `import asyncio` |
| 9 | `import json` |
| 10 | `from dataclasses import dataclass, field` |
| 11 | `from datetime import datetime` |
| 12 | `from urllib.parse import urlencode, urlsplit` |
| 14 | `import aiohttp` |

## `eclipses.py` (direct helper)

| Line | Import |
| --- | --- |
| 7 | `from datetime import datetime, timedelta` |
| 8 | `import math` |
| 10 | `from . import astronomy as astro` |
| 11 | `from .const import CATEGORY_ASTRO` |
| 12 | `from .events import Opportunity` |
| 13 | `from .wildlife import haversine_km, estimate_drive_hours` |

## `eligibility.py` (direct helper)

| Line | Import |
| --- | --- |
| 30 | `from __future__ import annotations` |
| 32 | `from datetime import datetime, timedelta` |
| 34 | `from . import conditions, curation, gear, weather_hazards` |
| 35 | `from .const import CATEGORY_FOLIAGE` |
| 36 | `from .curation import CLASS_BIRD_CHASE, CLASS_BIRD_ENCOUNTER, CLASS_BIRD_SPECTACLE, CLASS_CANT_MISS, CLASS_PLANNER, CLASS_WATCH, SIGNIFICANCE_FLOOR` |
| 116 | `from .events import MAX_ASTRO_CLOUD` |
| 428 | `from .wildlife import haversine_km` |
| 471 | `from .event_state import event_id` |
| 536 | `from .event_state import event_id` |
| 537 | `from .signals import background` |

## `email_reports.py` (direct helper)

| Line | Import |
| --- | --- |
| 30 | `from __future__ import annotations` |
| 32 | `import logging` |
| 33 | `import re` |
| 34 | `from datetime import datetime` |
| 36 | `from .const import CATEGORY_BIRDS, CATEGORY_BLOOMS, CATEGORY_FOLIAGE, CATEGORY_MAMMALS, CATEGORY_MARINE, CATEGORY_RARE, ZONES_BY_ID` |
| 40 | `from .field_reports import BLOOM_SIGNALS, FOLIAGE_SIGNALS, FieldReport, best_sentence, build_snippet, explicit_date, is_negated, place_point, signal_strength, zones_in` |
| 277 | `from .observations import observe, positive` |

## `event_state.py` (requested root)

| Line | Import |
| --- | --- |
| 6 | `from __future__ import annotations` |
| 8 | `from datetime import datetime, timedelta, timezone` |

## `events.py` (direct helper)

| Line | Import |
| --- | --- |
| 7 | `from __future__ import annotations` |
| 9 | `import math` |
| 10 | `from dataclasses import asdict, dataclass, field` |
| 11 | `from datetime import datetime, timedelta` |
| 13 | `from . import astronomy as astro` |
| 14 | `from .event_state import event_id` |
| 15 | `from .const import CATEGORY_ASTRO, CATEGORY_FOLIAGE, CATEGORY_PARKS, CATEGORY_SUNSET, DEFAULT_HOME, GEAR_PROFILES, TARGET_ZONES, ZONES_BY_ID` |
| 25 | `from .parks import active_windows as active_park_windows` |
| 26 | `from .phenomena import WINDOWS_BY_KEY, EVIDENCE_CALENDAR, EVIDENCE_COMPUTED, EVIDENCE_LIVE, EVIDENCE_STATIC, LIVE_CORROBORATION_DAYS, LIVE_CORROBORATION_KM, PRECISION_HORIZON_DAYS, active_windows` |
| 37 | `from .weather_scoring import SkyScore, cloud_confidence, cloud_is_scorable, layer_at, light_path_gate_checked, mark_standouts, score_sky` |
| 46 | `from .verification import grunion_run_window` |
| 47 | `from .wildlife import estimate_drive_hours, haversine_km` |
| 355 | `from . import sunburst` |
| 402 | `from . import sunburst` |
| 911 | `from . import curation, gear as gear_module` |
| 1054 | `from . import curation` |
| 1055 | `from .phenomena import PEAK_WINDOWS` |
| 1116 | `import hashlib` |
| 1140 | `from .observations import report_phenomena` |
| 1149 | `from . import curation` |
| 1156 | `from .observations import admissible` |
| 1494 | `from .verification import closure_coverage` |
| 1508 | `from .verification import NPS_PARK_CODES, alerts_for` |

## `field_reports.py` (direct helper)

| Line | Import |
| --- | --- |
| 38 | `from __future__ import annotations` |
| 40 | `import html as html_module` |
| 41 | `import logging` |
| 42 | `import re` |
| 43 | `from dataclasses import dataclass` |
| 44 | `from datetime import datetime, timedelta` |
| 46 | `from .const import CATEGORY_BLOOMS, CATEGORY_FOLIAGE` |
| 370 | `from bs4 import BeautifulSoup` |
| 588 | `from .observations import observe, positive` |

## `grunion.py` (direct helper)

| Line | Import |
| --- | --- |
| 2 | `import re` |
| 3 | `from datetime import datetime, timedelta` |
| 4 | `from zoneinfo import ZoneInfo` |
| 6 | `from .events import Opportunity` |
| 7 | `from .wildlife import estimate_drive_hours` |
| 13 | `from bs4 import BeautifulSoup` |

## `lunar.py` (direct helper)

| Line | Import |
| --- | --- |
| 24 | `from __future__ import annotations` |
| 26 | `import math` |
| 27 | `from dataclasses import dataclass, field` |
| 28 | `from datetime import date, datetime, timedelta, timezone` |
| 30 | `from . import astronomy as astro` |
| 244 | `from .events import Opportunity` |
| 245 | `from .weather_scoring import cloud_confidence, cloud_is_scorable` |
| 316 | `from .verification import TIDE_STATIONS` |
| 317 | `from .wildlife import haversine_km` |
| 333 | `from .events import Opportunity` |
| 334 | `from .wildlife import estimate_drive_hours` |
| 400 | `from .events import Opportunity` |
| 401 | `from .wildlife import estimate_drive_hours` |

## `parks.py` (direct helper)

| Line | Import |
| --- | --- |
| 28 | `from __future__ import annotations` |
| 30 | `import calendar as calendar_module` |
| 31 | `from dataclasses import dataclass` |
| 32 | `from datetime import date, datetime, timedelta` |

## `phenomena.py` (direct helper)

| Line | Import |
| --- | --- |
| 32 | `from __future__ import annotations` |
| 34 | `from dataclasses import dataclass` |
| 35 | `from datetime import date, datetime, timedelta` |
| 37 | `from .const import CATEGORY_BIRDS, CATEGORY_BLOOMS, CATEGORY_FOLIAGE, CATEGORY_MAMMALS, CATEGORY_MARINE, CATEGORY_RARE` |

## `routing.py` (direct helper)

| Line | Import |
| --- | --- |
| 21 | `from __future__ import annotations` |
| 23 | `import logging` |
| 24 | `from dataclasses import dataclass` |
| 25 | `from datetime import datetime` |

## `sensor.py` (requested root)

| Line | Import |
| --- | --- |
| 3 | `from __future__ import annotations` |
| 5 | `from homeassistant.components.sensor import SensorEntity` |
| 6 | `from homeassistant.config_entries import ConfigEntry` |
| 7 | `from homeassistant.core import HomeAssistant` |
| 8 | `from homeassistant.helpers.entity_platform import AddEntitiesCallback` |
| 9 | `from homeassistant.helpers.update_coordinator import CoordinatorEntity` |
| 11 | `from .const import ALL_CATEGORIES, GEAR_PROFILES, CATEGORY_SUNSET, DOMAIN` |
| 12 | `from .parks import PARKS` |
| 13 | `from .phenomena import PRECISION_HORIZON_DAYS` |
| 14 | `from .events import planning_slice` |
| 15 | `from .coordinator import PhotographyEventsCoordinator` |

## `signals.py` (direct helper)

| Line | Import |
| --- | --- |
| 17 | `from __future__ import annotations` |
| 19 | `import hashlib` |
| 20 | `from dataclasses import dataclass, field` |
| 21 | `from datetime import datetime` |

## `source_health.py` (direct helper)

| Line | Import |
| --- | --- |
| 8 | `from datetime import timedelta` |
| 10 | `from .phenomena import EVIDENCE_STATIC` |
| 11 | `from .const import CATEGORY_ASTRO` |

## `spectacles.py` (direct helper)

| Line | Import |
| --- | --- |
| 7 | `from __future__ import annotations` |
| 9 | `import math` |
| 10 | `import re` |
| 11 | `from datetime import datetime, timedelta, timezone` |
| 12 | `from xml.etree import ElementTree` |
| 14 | `from . import astronomy` |
| 15 | `from .const import ZONES_BY_ID` |
| 16 | `from .events import Opportunity` |
| 17 | `from .weather_scoring import CLOUD_SCORING_LEAD_DAYS` |
| 18 | `from .field_reports import FieldReport, strip_html` |
| 19 | `from .wildlife import estimate_drive_hours` |
| 67 | `from .curation import phenomena_named` |
| 91 | `from .curation import REPORT_ACTIVATED, definition` |
| 92 | `from .observations import admissible, report_phenomena` |
| 341 | `from .curation import definition` |

## `streamflow.py` (direct helper)

| Line | Import |
| --- | --- |
| 33 | `from __future__ import annotations` |
| 35 | `from dataclasses import dataclass` |
| 36 | `from datetime import datetime, timedelta, timezone` |
| 37 | `import math` |

## `sunburst.py` (direct helper)

| Line | Import |
| --- | --- |
| 27 | `from __future__ import annotations` |
| 29 | `import base64` |
| 30 | `from datetime import datetime, timedelta, timezone` |

## `throttle.py` (direct helper)

| Line | Import |
| --- | --- |
| 14 | `from __future__ import annotations` |
| 16 | `from dataclasses import dataclass` |
| 17 | `from datetime import datetime, timedelta` |
| 18 | `from typing import Any` |

## `verification.py` (direct helper)

| Line | Import |
| --- | --- |
| 26 | `from __future__ import annotations` |
| 28 | `from dataclasses import dataclass` |
| 29 | `from datetime import date, datetime, timedelta` |
| 195 | `from .wildlife import haversine_km` |

## `waves.py` (direct helper)

| Line | Import |
| --- | --- |
| 2 | `from __future__ import annotations` |
| 4 | `import math` |
| 5 | `import re` |
| 6 | `from dataclasses import dataclass` |
| 7 | `from datetime import datetime, timedelta, timezone` |
| 116 | `from .events import Opportunity` |
| 117 | `from .wildlife import estimate_drive_hours` |

## `weather_hazards.py` (direct helper)

| Line | Import |
| --- | --- |
| 51 | `from __future__ import annotations` |
| 53 | `import math` |
| 54 | `from dataclasses import dataclass, field` |
| 55 | `from datetime import datetime, timedelta, timezone` |
| 57 | `from .signals import BASIS_FORECAST, Signal` |
| 58 | `from .wildlife import haversine_km` |

## `weather_scoring.py` (direct helper)

| Line | Import |
| --- | --- |
| 38 | `from __future__ import annotations` |
| 40 | `import math` |
| 41 | `from bisect import bisect_left` |
| 42 | `from dataclasses import dataclass, field` |
| 43 | `from datetime import datetime, timedelta, timezone` |
| 45 | `from . import astronomy as astro` |

## `wildlife.py` (direct helper)

| Line | Import |
| --- | --- |
| 23 | `from __future__ import annotations` |
| 25 | `import math` |
| 26 | `from dataclasses import dataclass, field` |
| 27 | `from datetime import datetime, timedelta, timezone` |
| 29 | `from .const import CATEGORY_BIRDS, CATEGORY_MARINE, DEFAULT_HOME, EBIRD_NOTABLE_URL, EBIRD_SPECIES_URL, MARINE_TAXA, TARGET_ZONES` |
| 284 | `from .phenomena import PEAK_WINDOWS` |
| 327 | `from .phenomena import PEAK_WINDOWS` |

## Frontend assembly and existing tests

The generated `www/photography-events-card.js` is concatenated in the order recorded by `scripts/card-sources.json`, by `scripts/build-card.mjs`; it has no module-loader imports. Direct source dependencies:

```json
[
  "header",
  "astronomy",
  "catalog",
  "sky-scoring",
  "timeline",
  "formatting",
  "editor",
  "styles",
  "modes",
  "cant-miss",
  "card",
  "register"
]
```

Third-party Python runtime: manifest requires `beautifulsoup4>=4.12.0`; HA supplies aiohttp, voluptuous, selectors, coordinator, registry, Store, datetime, HTTP/frontend and entity APIs. Core itself uses FastAPI, Pydantic, SQLAlchemy/asyncpg and PostGIS; these do not become HA dependencies.

| Existing test file | Tests/classes and coverage anchors |
| --- | --- |
| `test_cant_miss.py` | `TestWildlifeSignalsAreNotEvents`, `TestBirds`, `TestReportsMergeIntoPhenomena`, `TestGate`, `TestSunset`, `TestLunarEngine`, `TestGear`, `TestCatalogIntegrity`, `TestFoliageVisibilityScope` |
| `test_codex_review.py` | `TestC1MarineSafety`, `TestC2ParkAccess`, `TestC3SolarFilterStandard`, `TestC4OrcaLocality`, `TestC5StatementNormalization`, `TestR3SubjectBinding`, `TestR4HotlineStatementDates`, `TestC6MalformedAlerts`, `TestH1SpectacleCountFreshness`, `TestH2SiteIdentity`, `TestH3ExactCoordinates`, `TestH4LightPathLayers`, `TestH5ProviderModelFreshness`, `TestH6InputsResolvedBeforeScoring`, `TestH7PerPointWeather`, `TestH8AssessmentCoverage`, `TestH9OwnershipIsNotPresentation`, `TestH10OutOfSeasonLiveEvidence`, `TestH11RouteBasisSurfaces`, `TestM1TimePrecision`, `TestM2YearBoundaryIdentity`, `TestM3SuppressionBeforeRepresentative`, `TestM4QualifyBeforeRank`, `TestPayloadSize` |
| `test_core_client.py` | `Response`, `Session`, `CoreClientContracts` |
| `test_eclipses.py` | `EclipseTests`, `MeteorDriftTests` |
| `test_final_residuals.py` | `SemanticAlerts`, `ConservativeStatements`, `ForecastChronology` |
| `test_finish_reliability.py` | `FinishReliability` |
| `test_ha_core_bridge.py` | `CoreStoreContracts` |
| `test_ha_final_residuals.py` | `FinalResidualPipeline` |
| `test_ha_integration.py` | `Response`, `Session`, `HomeAssistantContracts` |
| `test_ha_pipeline.py` | `Response`, `Router`, `PipelineContracts` |
| `test_ha_watching.py` | `FoliageWatchingPipeline` |
| `test_hardening.py` | `TestSourceRoles`, `TestSafetyStates`, `TestFreshSnowClearing`, `TestMoonbow`, `TestFirefall`, `TestEvidenceFreshness`, `TestOrcaClustering`, `TestMonarchLocation`, `TestKingTides`, `TestGrunionStation`, `TestBirdViews`, `TestGearSemantics`, `TestSolarEclipseGear`, `TestWeatherIsNotCantMiss`, `TestFractionsAreNotDates` |
| `test_integration.py` | `TestAstronomy`, `TestSkyScoring`, `TestLightPathScoring`, `TestOpportunities`, `TestPeakWindows`, `TestZonesAndGear`, `TestWildlifeParsing`, `TestSightingClustering`, `TestDriveEstimation`, `TestSightingsAreSignals`, `TestFieldReportScraping`, `TestRoutingClients`, `TestRateLimiting`, `TestNationalParks`, `TestConfigFlowSchema`, `TestAstroShootingWindow`, `TestLunarLookAhead`, `TestMeteorPeakNights`, `TestPrunedParks`, `TestLunarPhaseFinding`, `TestGrunionRuns`, `TestTideVerification`, `TestParkClosures`, `TestVerificationSources`, `TestEvidencePlumbing`, `TestEmailIngestion`, `TestForecastReach` |
| `test_source_health.py` | `SourceHealthTests` |
| `test_special_events.py` | `TestPersistentEvents`, `TestWaves`, `TestSpecialSources`, `TestCardEvidenceRegression`, `TestStreamflow`, `TestMoonbowGeometry`, `TestMoonbowOpportunities`, `TestEclipseReachability`, `TestSeenThisSeason`, `TestPerCategoryDriveLimits` |

`tests/photography-events-card.test.mjs` covers card registration, geometry, grouping, source/freshness presentation, choices, navigation, focus/scroll and fallback behavior. Three synthetic card/browser fixtures and the navigation fixture exist; no browser fixture was changed. CI runs pure tests plus a real HA matrix (2024.11.3/Python 3.12, 2025.3.4/Python 3.13), HACS validation, card assembly/version checks, and pyflakes. See RESULTS.md for what was actually run locally.
