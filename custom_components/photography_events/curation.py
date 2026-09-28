"""Curated phenomena and the evidence each one needs before it may interrupt.

The table in ``phenomena.py`` says *when* to look. This one says *what would
have to be true* for a photographer to regret not going, and how extraordinary
the photograph is. The two are different questions: a humpback season is five
months long; a humpback bait-ball feeding event is an afternoon, and only a
report of the behaviour can tell you it is happening.

Every entry declares:

- ``significance`` - how photographically extraordinary the experience is,
  independent of whether it is happening. A fresh common-dolphin sighting has
  high confidence and low significance; it must never outrank a lunar eclipse.
- ``policy`` - the trigger policy that decides when a phenomenon is actionable.
  One universal rule does not fit nature: elephant seals pup on a published
  annual cycle, humpbacks lunge-feed wherever the anchovies are this week.
- ``product_class`` - the most prominent place it can ever appear. Parks and
  seasons are planner material by construction.
- ``policy_reason`` - why that policy, so the next person to tune it knows what
  evidence it rests on.

Thresholds are either sourced (the source is named) or product thresholds -
choices about what deserves attention - and are labelled as such. None of the
product thresholds is presented to the photographer as an ecological fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .const import (
    CATEGORY_ASTRO, CATEGORY_BIRDS, CATEGORY_BLOOMS, CATEGORY_FOLIAGE, CATEGORY_MAMMALS,
    CATEGORY_MARINE, CATEGORY_PARKS, CATEGORY_RARE, CATEGORY_SUNSET, CATEGORY_WAVES,
)
from . import gear
from .gear import (
    LAND_BLM, LAND_CITY, LAND_MARINE, LAND_MILITARY, LAND_NPS, LAND_REFUGE,
    LAND_STATE_PARK, LAND_UNKNOWN, LAND_USFS,
)

# --- Trigger policies --------------------------------------------------------
POLICY_COMPUTED = "computed"
POLICY_CALENDAR = "calendar_reliable"
POLICY_BEHAVIOR = "behavior_report_required"
POLICY_AGGREGATION = "aggregation_required"
POLICY_COUNT = "count_threshold"
POLICY_CONDITIONS = "conditions_required"
POLICY_EXCEPTIONAL_PRESENCE = "exceptional_presence"
POLICY_LIVE = "live_confirmation_required"
POLICY_FORECAST_CONFIRM = "forecast_plus_confirmation"
POLICY_NONE = "planning_context"

# --- Product classes ---------------------------------------------------------
CLASS_CANT_MISS = "cant_miss"
CLASS_BIRD_SPECTACLE = "bird_spectacle"
CLASS_BIRD_ENCOUNTER = "bird_encounter"
CLASS_BIRD_CHASE = "bird_chase"
CLASS_PLANNER = "planner"
CLASS_WATCH = "watch"

# The least a phenomenon must matter to reach the main dashboard. A product
# threshold: below it sit things that are pleasant, not regrettable to miss.
SIGNIFICANCE_FLOOR = 70

# Evidence states the builders stamp on an opportunity, from strongest down.
STATE_COMPUTED = "computed"
STATE_MEASURED = "measured"
STATE_CONFIRMED = "behavior_confirmed"
STATE_CALENDAR = "calendar"
STATE_CALENDAR_PRESENCE = "calendar_presence"
STATE_NOWCAST = "nowcast"
STATE_FORECAST = "forecast"
STATE_SCHEDULE = "schedule"
STATE_REPEATED_PRESENCE = "repeated_presence"
STATE_PRESENCE = "presence_only"
STATE_UNDATED = "reported_undated"
STATE_WATCHING = "watching"
STATE_UNVERIFIED = "unverified"
STATE_SEASON = "season"
STATE_CANDIDATE = "computed_candidate"
# A computed sky candidate plus a dated report of strong flow: still a watch.
STATE_CANDIDATE_SUPPORTED = "candidate_supported"
# A dated, viewpoint-specific prediction from a source that models the valley
# skyline. No consumable source exists yet (see SOURCE_VALIDATION.md), so
# nothing produces this state today, and a moonbow cannot reach Can't Miss.
STATE_VIEWPOINT_VALIDATED = "viewpoint_validated"


@dataclass(frozen=True)
class PhenomenonDefinition:
    key: str
    name: str
    category: str
    significance: int
    policy: str
    product_class: str
    policy_reason: str
    # Evidence states that make this phenomenon actionable.
    actionable: frozenset = frozenset()
    # Fixed vocabulary that states the behaviour/aggregation has been seen.
    behavior_terms: tuple[str, ...] = ()
    # Place words that tie a report to this phenomenon rather than a sibling.
    location_terms: tuple[str, ...] = ()
    gear_profile: str = "landscape"
    land: str = LAND_UNKNOWN
    wildlife: bool = False
    drone_useful: bool = False
    encounter: str = "unknown"
    # Where the photographer stands; decides which NWS alerts apply
    # (weather_hazards.HAZARDS). "home" means no travel.
    exposure: str = "general"
    ethics: str = ""
    safety: str = ""
    # How long a dated report stays evidence, in days. Product thresholds, set
    # per phenomenon by how fast the photograph moves: a humpback feeding
    # event follows the bait and is gone in days; a crane roost or the
    # elephant seal rookery is stable for weeks. Capped at the 14-day
    # corroboration limit. Listed in SOURCE_VALIDATION.md.
    evidence_days: int = 14
    # A count, where a reliable count decides the photograph (product threshold).
    min_count: int | None = None
    # Behaviour-driven biology whose typical dates are search guidance, not a
    # physical limit: a fresh, located, trusted report of the behaviour opens a
    # bounded occurrence even outside the usual window (events.live_occurrences).
    # False for anything calendar-, migration- or physics-bound.
    live_outside_window: bool = False
    # The conditions are judged at a place (darkness at a beach, a drive to
    # it). A report that names only a region gives no such place, so it is
    # evidence for a watch, never a destination.
    needs_site: bool = False
    sources: tuple[str, ...] = field(default_factory=tuple)


def _d(**kwargs) -> PhenomenonDefinition:
    kwargs["actionable"] = frozenset(kwargs.get("actionable", ()))
    return PhenomenonDefinition(**kwargs)


BLOOM_TERMS = ("peak bloom", "superbloom", "super bloom", "carpets", "carpeting", "carpeted",
               "in full bloom", "blanketed", "best display")
FOLIAGE_TERMS = ("go now", "peak color", "peak colour", "near peak", "75-100%", "75%-100%")
MARINE_ETHICS = "Stay at least 100 yards from whales; never pursue, box in or separate animals (NOAA guidance). No drone over marine mammals."
BOAT_SAFETY = "Boat trip; sea state decides. Go with an operator."

CATALOG: dict[str, PhenomenonDefinition] = {d.key: d for d in (
    # --- Marine ---------------------------------------------------------------
    _d(key="humpback_lunge_feeding", live_outside_window=True, name="Humpback lunge feeding", category=CATEGORY_MARINE,
       significance=85, policy=POLICY_BEHAVIOR, evidence_days=3, product_class=CLASS_CANT_MISS, exposure="coastal",
       policy_reason="Humpbacks are common here for months; the photograph is the bait-ball lunge, which only a dated behaviour report can establish. Presence corroborates the watch, never the behaviour.",
       actionable={STATE_CONFIRMED},
       behavior_terms=("lunge feeding", "lunge-feeding", "bubble net", "bubble-net", "bait ball", "humpbacks feeding", "feeding frenzy"),
       gear_profile="marine_shore", land=LAND_MARINE, wildlife=True, encounter="moderate",
       ethics=MARINE_ETHICS, safety="Piers and bluff edges; boats per operator."),
    _d(key="blue_whale_feeding", live_outside_window=True, name="Blue whale feeding aggregation", category=CATEGORY_MARINE,
       significance=90, policy=POLICY_AGGREGATION, evidence_days=3, product_class=CLASS_CANT_MISS, exposure="boat",
       policy_reason="A single blue whale is intrinsically notable, but the photograph worth a trip is the krill aggregation that holds several close to boats; that needs a dated aggregation report.",
       actionable={STATE_CONFIRMED},
       behavior_terms=("blue whales feeding", "blue whale feeding", "multiple blue whales", "several blue whales", "blue whale aggregation"),
       gear_profile="marine_boat", land=LAND_MARINE, wildlife=True, encounter="moderate",
       ethics=MARINE_ETHICS, safety=BOAT_SAFETY),
    _d(key="transient_orca_hunt", live_outside_window=True, name="Orcas hunting", category=CATEGORY_MARINE,
       significance=95, policy=POLICY_BEHAVIOR, product_class=CLASS_CANT_MISS, exposure="boat",
       policy_reason="Hunting needs a behaviour report. Orca presence alone may qualify separately as exceptional presence (see orca_presence).",
       actionable={STATE_CONFIRMED, STATE_REPEATED_PRESENCE},
       behavior_terms=("orcas hunting", "orca predation", "killer whale predation", "killer whales hunting", "attack on a gray whale", "hunting a gray whale"),
       gear_profile="marine_boat", land=LAND_MARINE, wildlife=True, encounter="low",
       ethics=MARINE_ETHICS, safety=BOAT_SAFETY, evidence_days=3),
    _d(key="orca_presence", name="Orcas reported", category=CATEGORY_MARINE,
       significance=88, policy=POLICY_EXCEPTIONAL_PRESENCE, product_class=CLASS_CANT_MISS, exposure="boat",
       policy_reason="Orcas are rare enough off this coast that coherent recent presence is itself worth a boat trip. Product thresholds: two independent observers within 25 km of each other inside 72 h, or one dated operator report within 36 h. A single community observation, even research grade, is a background signal and at most a watch: reports far apart are different places, not stronger evidence.",
       actionable={STATE_REPEATED_PRESENCE},
       gear_profile="marine_boat", land=LAND_MARINE, wildlife=True, encounter="low",
       ethics=MARINE_ETHICS, safety=BOAT_SAFETY, evidence_days=3),
    _d(key="gray_whale_northbound", name="Gray whale mothers and calves", category=CATEGORY_MARINE,
       significance=78, policy=POLICY_BEHAVIOR, evidence_days=5, product_class=CLASS_CANT_MISS, exposure="coastal",
       policy_reason="Gray whales pass for months; the mother-calf pairs hugging the surf line are the photograph, and only a report of pairs close in says they are.",
       actionable={STATE_CONFIRMED},
       behavior_terms=("mother and calf", "mother-calf", "cow and calf", "cow-calf", "cow/calf", "mom and calf"),
       gear_profile="marine_shore", land=LAND_MARINE, wildlife=True, encounter="moderate", ethics=MARINE_ETHICS),
    _d(key="gray_whale_southbound", name="Gray whale southbound migration", category=CATEGORY_MARINE,
       significance=55, policy=POLICY_LIVE, product_class=CLASS_PLANNER, exposure="coastal",
       policy_reason="Distant blows from a headland are planning context, not a regret event.",
       gear_profile="marine_shore", land=LAND_MARINE, wildlife=True, encounter="moderate", ethics=MARINE_ETHICS),
    _d(key="common_dolphin_calving", live_outside_window=True, name="Common dolphin calving", category=CATEGORY_MARINE,
       significance=72, policy=POLICY_BEHAVIOR, evidence_days=3, product_class=CLASS_CANT_MISS, exposure="boat",
       policy_reason="Common dolphins are present most days; newborn calves in the pods need a report.",
       actionable={STATE_CONFIRMED},
       behavior_terms=("dolphin calves", "newborn dolphins", "baby dolphins", "calves in the pod"),
       gear_profile="marine_boat", land=LAND_MARINE, wildlife=True, encounter="moderate",
       ethics=MARINE_ETHICS, safety=BOAT_SAFETY),
    _d(key="dolphin_megapod", name="Common dolphin megapod", category=CATEGORY_MARINE,
       significance=80, policy=POLICY_AGGREGATION, product_class=CLASS_CANT_MISS, exposure="boat",
       policy_reason="Presence is ordinary; a dated operator report of one explicitly sized pod of thousands is the aggregation. Product threshold: at least 1,000 dolphins written against one pod; the word 'megapod' alone, or a pod of 20, is not it.",
       actionable={STATE_CONFIRMED}, min_count=1000,
       behavior_terms=("megapod", "mega-pod", "mega pod", "superpod", "super pod"),
       gear_profile="marine_boat", land=LAND_MARINE, wildlife=True, encounter="moderate",
       ethics=MARINE_ETHICS, safety=BOAT_SAFETY, evidence_days=2),
    # --- Pinnipeds and land mammals -------------------------------------------
    _d(key="elephant_seal_battles", name="Elephant seal breeding & pupping", category=CATEGORY_MAMMALS,
       significance=90, policy=POLICY_CALENDAR, evidence_days=14, product_class=CLASS_CANT_MISS, exposure="coastal",
       policy_reason="Friends of the Elephant Seal document a stable annual cycle: bulls from November, births mid-December to early February, peak births late January, fights December-January. Inside that core window the calendar is reliable; a dated docent report can open it earlier.",
       actionable={STATE_CALENDAR, STATE_CONFIRMED},
       behavior_terms=("pups", "pupping", "first pup", "bulls fighting", "bull fights", "births", "mating"),
       gear_profile="wildlife_colony", land=LAND_MARINE, wildlife=True, encounter="high",
       ethics="View only from the boardwalk and vista points; stay behind barriers (MMPA).",
       safety="Roadside parking on Highway 1.",
       sources=("https://elephantseal.org/birthing-and-breeding/",)),
    _d(key="harbor_seal_pupping", name="Harbor seal pupping", category=CATEGORY_MAMMALS,
       significance=72, policy=POLICY_CALENDAR, evidence_days=14, product_class=CLASS_CANT_MISS, exposure="coastal",
       policy_reason="Carpinteria Seal Watch: births mostly February-March at a monitored rookery (~60 pups a year) below a public overlook; the beach is closed 1 Dec-31 May by City Ordinance 470.",
       actionable={STATE_CALENDAR, STATE_CONFIRMED},
       behavior_terms=("harbor seal pups", "seal pups", "pupping", "nursing"),
       gear_profile="wildlife_colony", land=LAND_CITY, wildlife=True, encounter="high",
       ethics="Bluff overlook only; the beach below is closed during pupping. Disturbance violates the MMPA.",
       safety="Stay back from the bluff edge.",
       sources=("https://carpinteriaca.gov/parks-and-recreation/carpinteria-harbor-seal-rookery/",)),
    _d(key="tule_elk_rut", name="Tule elk rut", category=CATEGORY_MAMMALS,
       significance=85, policy=POLICY_CALENDAR, evidence_days=7, product_class=CLASS_CANT_MISS,
       policy_reason="NPS: the rut runs August-October, peaking late August-September, so behaviour is reliable in the peak window. Encounter at Carrizo is not - the herd is dispersed - so a recent elk report near the site is also required (product rule).",
       actionable={STATE_CALENDAR_PRESENCE, STATE_CONFIRMED},
       behavior_terms=("bugling", "sparring", "rut is underway", "harem"),
       gear_profile="wildlife_dawn", land=LAND_BLM, wildlife=True, encounter="moderate",
       ethics="Stay in or beside the vehicle; keep well back from bulls.",
       safety="Carrizo roads are impassable clay when wet.",
       sources=("https://www.nps.gov/thingstodo/tule-elk-viewing-point-reyes.htm",)),
    _d(key="black_bear_cubs", live_outside_window=True, name="Black bear sows with cubs", category=CATEGORY_MAMMALS,
       significance=85, policy=POLICY_BEHAVIOR, evidence_days=7, product_class=CLASS_CANT_MISS, exposure="mountain",
       policy_reason="Bears are seen year-round; a generic bear sighting is not evidence of cubs. Only a report of a sow with cubs in a public area qualifies. Den locations are never used.",
       actionable={STATE_CONFIRMED},
       behavior_terms=("sow with cubs", "sow and cubs", "sow and cub", "mother bear with cubs", "bear cubs", "with cubs"),
       gear_profile="general_wildlife", land=LAND_NPS, wildlife=True, encounter="low",
       ethics="Never position yourself between a sow and her cubs; keep 50 yards; never approach a den.",
       safety="Bear country food storage rules apply."),
    _d(key="desert_bighorn_rut", name="Desert bighorn rut", category=CATEGORY_MAMMALS,
       significance=75, policy=POLICY_BEHAVIOR, product_class=CLASS_PLANNER, exposure="desert",
       policy_reason="Sparse animals on rough ground; no source reports it. Planning only.",
       gear_profile="general_wildlife", land=LAND_NPS, wildlife=True, encounter="low",
       safety="August heat in Death Valley is dangerous."),
    _d(key="sierra_bighorn_rut", name="Sierra bighorn rut", category=CATEGORY_MAMMALS,
       significance=75, policy=POLICY_BEHAVIOR, product_class=CLASS_PLANNER, exposure="mountain",
       policy_reason="Endangered, few hundred animals on steep ground; positions are not published and should not be. Planning only.",
       gear_profile="general_wildlife", land=LAND_USFS, wildlife=True, encounter="low",
       ethics="Endangered population: do not share locations; view from roads with a scope."),
    # --- Birds ---------------------------------------------------------------
    _d(key="sandhill_crane_flyin", name="Sandhill crane fly-in", category=CATEGORY_RARE,
       significance=85, policy=POLICY_CALENDAR, evidence_days=14, product_class=CLASS_BIRD_SPECTACLE,
       policy_reason="USFWS Merced NWR: up to 20,000 cranes and 60,000 geese winter there, and the sunset fly-in is 'a predictable daily spectacle', best December-February.",
       actionable={STATE_CALENDAR, STATE_CONFIRMED},
       behavior_terms=("fly-in", "flying in to roost", "thousands of cranes"),
       gear_profile="birds_in_flight_low_light", land=LAND_REFUGE, wildlife=True, encounter="high",
       ethics="Stay on the auto tour route and in the vehicle; refuge rules apply.",
       safety="Tule fog on Valley highways in winter.",
       sources=("https://www.fws.gov/refuge/merced",)),
    _d(key="bald_eagle_cachuma", live_outside_window=True, name="Bald eagles fishing at Cachuma Lake", category=CATEGORY_BIRDS,
       significance=75, policy=POLICY_BEHAVIOR, evidence_days=5, product_class=CLASS_BIRD_SPECTACLE,
       policy_reason="Wintering eagles are reliably present; eagles actively fishing, or several together, is the photograph and needs a report.",
       actionable={STATE_CONFIRMED},
       behavior_terms=("eagles fishing", "eagle fishing", "catching fish", "multiple eagles", "several eagles"),
       gear_profile="raptor", land=LAND_UNKNOWN, wildlife=True, encounter="moderate",
       ethics="Naturalist cruises keep their distance from perches and nests; do not approach nests."),
    _d(key="condor_activity", name="California condors", category=CATEGORY_BIRDS,
       significance=85, policy=POLICY_EXCEPTIONAL_PRESENCE, evidence_days=7, product_class=CLASS_BIRD_SPECTACLE,
       policy_reason="NPS says there is no guarantee of a sighting. Repeated reports at a public viewing area make an encounter plausible (bird encounter); several birds together or a behaviour report make it a spectacle. Product thresholds.",
       actionable={STATE_CONFIRMED},
       behavior_terms=("roosting", "soaring together", "feeding", "several condors", "multiple condors"),
       gear_profile="raptor", land=LAND_NPS, wildlife=True, encounter="moderate",
       ethics="Never approach roosts or nest areas; stay on trails.",
       safety="High Peaks trails are strenuous and hot.",
       sources=("https://www.nps.gov/pinn/learn/nature/condor-viewing-tips.htm",)),
    _d(key="waterfowl_mass_flight", name="Mass goose lift-off", category=CATEGORY_BIRDS,
       significance=80, policy=POLICY_COUNT, evidence_days=5, product_class=CLASS_BIRD_SPECTACLE,
       policy_reason="Tens of thousands of geese winter at Merced NWR, but a lift-off is not predictable; a count of thousands at the refuge (product threshold 1,000) or a lift-off report is required.",
       actionable={STATE_CONFIRMED}, min_count=1000,
       behavior_terms=("lift-off", "blast-off", "thousands of geese"),
       gear_profile="birds_in_flight_low_light", land=LAND_REFUGE, wildlife=True, encounter="moderate"),
    # --- Insects ---------------------------------------------------------------
    _d(key="pismo_monarchs", name="Pismo monarch clusters", category=CATEGORY_RARE,
       significance=82, policy=POLICY_AGGREGATION, evidence_days=14, product_class=CLASS_CANT_MISS, exposure="general",
       policy_reason="The season is predictable, the numbers are not: recent Pismo counts have been in the hundreds. Requires a dated count of at least 1,000 at the grove (product threshold), plus a cold dawn: Xerces notes monarchs cannot fly below about 55 °F, so they stay clustered.",
       actionable={STATE_CONFIRMED}, min_count=1000,
       behavior_terms=("clusters", "clustering", "clustered"),
       gear_profile="monarch_cluster", land=LAND_STATE_PARK, wildlife=True, encounter="high",
       ethics="Never touch clusters or shake branches; stay on the boardwalk.",
       sources=("https://xerces.org/blog/everything-you-need-to-know-about-visiting-overwintering-monarchs",
                "https://www.parks.ca.gov/?page_id=30273")),
    # --- Landscapes, water, ice -------------------------------------------------
    _d(key="horsetail_firefall", name="Horsetail Fall firefall", category=CATEGORY_RARE,
       significance=90, policy=POLICY_CONDITIONS, evidence_days=3, product_class=CLASS_CANT_MISS, exposure="mountain",
       policy_reason="Needs every condition at once: an evening inside the published mid-February alignment window; a dated report of water on Horsetail Fall (Merced discharge is a different drainage and is never used); local cloud at sunset of 25% or less and an open upstream light path (product thresholds); no reported closure of the viewing area. NWS warnings block through the safety gate.",
       actionable={STATE_CONFIRMED},
       behavior_terms=("firefall", "horsetail fall is flowing", "water on horsetail", "horsetail is flowing"),
       gear_profile="firefall", land=LAND_NPS, encounter="moderate",
       safety="Winter roads; follow NPS firefall parking and access rules."),
    _d(key="moonbow", name="Yosemite moonbow", category=CATEGORY_RARE,
       significance=85, policy=POLICY_CONDITIONS, product_class=CLASS_CANT_MISS, exposure="mountain",
       policy_reason="Sky geometry is computed; spray and the viewpoint light path are not. A dated flow report makes a sky night a supported candidate (watch). Only a viewpoint-validated prediction - the published Lower/Upper Fall timetables model the valley skyline - plus a clear-sky forecast could make it actionable, and no such timetable can be consumed yet (they are published as page images).",
       actionable={STATE_VIEWPOINT_VALIDATED}, evidence_days=7,
       behavior_terms=("moonbow", "heavy spray", "yosemite falls roaring", "falls are raging"),
       gear_profile="waterfall_night", land=LAND_NPS, encounter="moderate",
       safety="Wet, icy footing near the falls at night."),
    _d(key="frazil_ice", name="Yosemite frazil ice", category=CATEGORY_RARE,
       significance=78, policy=POLICY_FORECAST_CONFIRM, product_class=CLASS_CANT_MISS, exposure="mountain",
       policy_reason="NPS: needs high waterfall flow and nights below freezing, mostly April, usually before 9 am. A freezing forecast is only a watch; a dated report confirms.",
       actionable={STATE_CONFIRMED}, evidence_days=2,
       behavior_terms=("frazil ice", "frazil"),
       gear_profile="landscape", land=LAND_NPS, encounter="moderate",
       safety="Never step on frazil ice: it is not solid, and people have become trapped beneath it.",
       sources=("https://www.nps.gov/yose/planyourvisit/frazilice.htm",)),
    _d(key="aspen_tier1_high", name="Eastern Sierra aspen, high elevation", category=CATEGORY_FOLIAGE,
       significance=80, policy=POLICY_LIVE, product_class=CLASS_CANT_MISS, exposure="mountain",
       policy_reason="Timing moves with temperature and wind; a dated peak report is required. Undated hotline text is shown as reported, date unknown.",
       actionable={STATE_CONFIRMED}, behavior_terms=FOLIAGE_TERMS, evidence_days=7,
       location_terms=("bishop creek", "north lake", "south lake", "sabrina", "rock creek", "mcgee"),
       gear_profile="landscape_colour", land=LAND_USFS, drone_useful=True, encounter="high"),
    _d(key="aspen_tier2_mid", name="Eastern Sierra aspen, mid elevation", category=CATEGORY_FOLIAGE,
       significance=80, policy=POLICY_LIVE, product_class=CLASS_CANT_MISS, exposure="mountain",
       policy_reason="As above.", actionable={STATE_CONFIRMED}, behavior_terms=FOLIAGE_TERMS, evidence_days=7,
       location_terms=("june lake", "convict", "lundy", "conway", "virginia lakes"),
       gear_profile="landscape_colour", land=LAND_USFS, drone_useful=True, encounter="high"),
    _d(key="aspen_tier3_north", name="Northern passes aspen", category=CATEGORY_FOLIAGE,
       significance=70, policy=POLICY_LIVE, product_class=CLASS_CANT_MISS, exposure="mountain",
       policy_reason="As above; beyond six hours in most traffic.", actionable={STATE_CONFIRMED},
       behavior_terms=FOLIAGE_TERMS, evidence_days=7, location_terms=("hope valley", "carson pass"),
       gear_profile="landscape_colour", land=LAND_USFS, drone_useful=True, encounter="high"),
    _d(key="bloom_carrizo_plain", name="Carrizo Plain superbloom", category=CATEGORY_BLOOMS,
       significance=85, policy=POLICY_LIVE, product_class=CLASS_CANT_MISS,
       policy_reason="Entirely rainfall-dependent; a dated strong bloom report is required.",
       actionable={STATE_CONFIRMED}, behavior_terms=BLOOM_TERMS, evidence_days=10,
       gear_profile="landscape_colour", land=LAND_BLM, drone_useful=True, encounter="high",
       ethics="Stay on roads and trails; do not trample flowers.", safety="Roads impassable when wet."),
    _d(key="bloom_antelope_valley", name="Antelope Valley poppy bloom", category=CATEGORY_BLOOMS,
       significance=78, policy=POLICY_LIVE, product_class=CLASS_CANT_MISS, exposure="desert", policy_reason="As above.",
       actionable={STATE_CONFIRMED}, behavior_terms=BLOOM_TERMS, evidence_days=10,
       gear_profile="landscape_colour", land=LAND_STATE_PARK, encounter="high",
       ethics="Stay on the reserve trails."),
    _d(key="bloom_death_valley", name="Death Valley superbloom", category=CATEGORY_BLOOMS,
       significance=90, policy=POLICY_LIVE, product_class=CLASS_CANT_MISS, exposure="desert", policy_reason="As above; perhaps once a decade.",
       actionable={STATE_CONFIRMED}, behavior_terms=BLOOM_TERMS, evidence_days=10,
       gear_profile="landscape_colour", land=LAND_NPS, encounter="high"),
    _d(key="bloom_anza_borrego", name="Anza-Borrego desert bloom", category=CATEGORY_BLOOMS,
       significance=78, policy=POLICY_LIVE, product_class=CLASS_CANT_MISS, exposure="desert", policy_reason="As above.",
       actionable={STATE_CONFIRMED}, behavior_terms=BLOOM_TERMS, evidence_days=10,
       gear_profile="landscape_colour", land=LAND_STATE_PARK, encounter="high"),
    # --- Coast and ocean -------------------------------------------------------
    _d(key="exceptional_swell", name="Exceptional Pacific swell", category=CATEGORY_WAVES,
       significance=80, policy=POLICY_FORECAST_CONFIRM, product_class=CLASS_CANT_MISS, exposure="coastal",
       policy_reason="The CDIP forecast is a watch; the calibrated NDBC 46011 measurement confirms the swell is here.",
       actionable={STATE_MEASURED},
       gear_profile="storm_surf", land=LAND_MILITARY, encounter="high",
       safety="Photograph only from high, set-back ground. Never on beaches, rocks or jetties during high surf."),
    _d(key="bioluminescent_surf", needs_site=True, name="Bioluminescent surf", category=CATEGORY_RARE,
       significance=85, policy=POLICY_LIVE, product_class=CLASS_CANT_MISS, exposure="beach",
       policy_reason="No dependable date exists. A credible report within three days, darkness and a Moon under half lit are all required.",
       actionable={STATE_CONFIRMED}, evidence_days=3,
       behavior_terms=("bioluminescence", "bioluminescent", "glowing waves", "glowing surf", "blue glow"),
       gear_profile="night_beach", land=LAND_STATE_PARK, encounter="moderate",
       safety="Night surf: stay above the wash line."),
    _d(key="grunion_run", name="Grunion run", category=CATEGORY_RARE,
       significance=60, policy=POLICY_LIVE, product_class=CLASS_PLANNER, exposure="beach",
       policy_reason="CDFW publishes expected runs, not observed ones; fish may not appear on a given beach.",
       gear_profile="night_beach", land=LAND_CITY, wildlife=True, encounter="low",
       ethics="Red light only; do not handle fish outside the open season rules."),
    _d(key="king_tide", name="King Tide", category=CATEGORY_WAVES,
       significance=55, policy=POLICY_COMPUTED, product_class=CLASS_PLANNER, exposure="coastal",
       policy_reason="Published Coastal Commission dates; a compound note for swell and full-Moon events.",
       gear_profile="storm_surf", land=LAND_UNKNOWN, encounter="high",
       safety="Waves over seawalls; stay off jetties."),
    _d(key="minus_tide", name="Minus tide", category=CATEGORY_WAVES,
       significance=50, policy=POLICY_COMPUTED, product_class=CLASS_PLANNER, exposure="beach",
       policy_reason="Tide predictions are exact; a monthly condition, so planning only.",
       gear_profile="tidepool", land=LAND_STATE_PARK, encounter="high",
       ethics="Never remove or turn over animals and rocks.", safety="Watch for sneaker waves; skip on High Surf advisories."),
    # --- Sky ---------------------------------------------------------------
    _d(key="sunset_local", name="Exceptional sunset", category=CATEGORY_SUNSET,
       significance=72, policy=POLICY_CONDITIONS, product_class=CLASS_CANT_MISS, exposure="home",
       policy_reason="Local to home only. A purpose-built provider's top tier, or the local model's modelled-light-path standout, is required; ordinary good sunsets happen most weeks.",
       actionable={STATE_FORECAST},
       gear_profile="sunset_local", land=LAND_MILITARY, encounter="high"),
    _d(key="meteor_major", name="Major meteor shower", category=CATEGORY_ASTRO,
       significance=82, policy=POLICY_COMPUTED, product_class=CLASS_CANT_MISS,
       policy_reason="Peak is computed from solar longitude; conditions (moon, radiant, cloud) decide.",
       actionable={STATE_COMPUTED}, gear_profile="meteor", land=LAND_UNKNOWN, encounter="high"),
    _d(key="meteor_minor", name="Minor meteor shower", category=CATEGORY_ASTRO,
       significance=45, policy=POLICY_COMPUTED, product_class=CLASS_PLANNER,
       policy_reason="Rates too low to change plans.", gear_profile="meteor"),
    _d(key="milky_way", name="Milky Way core night", category=CATEGORY_ASTRO,
       significance=70, policy=POLICY_COMPUTED, product_class=CLASS_CANT_MISS,
       policy_reason="A recurring monthly condition; only a drop-everything night (new Moon, forecast clear, dark site) reaches the dashboard.",
       actionable={STATE_COMPUTED}, gear_profile="astro_wide", encounter="high"),
    _d(key="eclipse_lunar_total", name="Total lunar eclipse", category=CATEGORY_ASTRO,
       significance=92, policy=POLICY_COMPUTED, product_class=CLASS_CANT_MISS,
       policy_reason="NASA catalog geometry with local visibility.", actionable={STATE_COMPUTED},
       gear_profile="eclipse_lunar", encounter="high"),
    _d(key="eclipse_lunar_partial", name="Partial lunar eclipse", category=CATEGORY_ASTRO,
       significance=60, policy=POLICY_COMPUTED, product_class=CLASS_PLANNER,
       policy_reason="Visible but modest.", gear_profile="eclipse_lunar"),
    _d(key="eclipse_solar", name="Solar eclipse", category=CATEGORY_ASTRO,
       significance=95, policy=POLICY_COMPUTED, product_class=CLASS_PLANNER,
       policy_reason="Central-path sites need their own contact calculation and road check; planner until then.",
       gear_profile="eclipse_solar", safety=gear.SOLAR_SAFETY),
    _d(key="aurora_local", name="Local aurora", category=CATEGORY_ASTRO,
       significance=95, policy=POLICY_CONDITIONS, product_class=CLASS_CANT_MISS,
       policy_reason="OVATION nowcast at the local cell with darkness; short notice by nature.",
       actionable={STATE_NOWCAST}, gear_profile="aurora", encounter="moderate"),
    _d(key="full_moon_closest", name="Largest full Moon of the year", category=CATEGORY_ASTRO,
       significance=75, policy=POLICY_CONDITIONS, product_class=CLASS_CANT_MISS, exposure="home",
       policy_reason="The year's closest full Moon is a computed fact; it earns the dashboard only when the moonrise falls near sunset (a lit landscape and a low, large-looking Moon) and the forecast is not overcast.",
       actionable={STATE_COMPUTED}, gear_profile="moon_horizon", land=LAND_MILITARY, encounter="high"),
    _d(key="full_moon", name="Full Moon", category=CATEGORY_ASTRO,
       significance=40, policy=POLICY_COMPUTED, product_class=CLASS_PLANNER, exposure="home",
       policy_reason="Monthly; planning facts only.", gear_profile="moon_horizon", land=LAND_MILITARY),
    # --- Weather (watch signals only unless observed) ---------------------------
    _d(key="fresh_snow_clearing", name="Fresh snow then clearing", category=CATEGORY_RARE,
       significance=85, policy=POLICY_FORECAST_CONFIRM, evidence_days=2, product_class=CLASS_CANT_MISS, exposure="mountain",
       policy_reason="Watch: a snowfall forecast (product threshold: 10 cm modelled in 24 h, then 30 % cloud or less within 18 h) is a background signal only. Confirmation: a dated report of fresh snow at this place from the last 2 days, plus a current forecast hour of 30 % cloud or less within the next 48 h at the same place; the opportunity is the 12 h from that clearing. Park access must be checked.",
       actionable={STATE_CONFIRMED}, behavior_terms=("fresh snow", "inches of snow", "snow on the valley floor"),
       gear_profile="landscape", land=LAND_NPS, encounter="high",
       safety="Chain controls and closures; never drive into a Winter Storm Warning."),
    _d(key="thunderstorm_watch", name="Thunderstorm potential", category=CATEGORY_RARE,
       significance=75, policy=POLICY_FORECAST_CONFIRM, product_class=CLASS_WATCH,
       policy_reason="No lightning detection feed is connected; forecast thunder is a watch only.",
       gear_profile="landscape", safety="Photograph lightning only from a vehicle or building; never from ridges or open ground."),
    # --- Planning context -------------------------------------------------------
    _d(key="park_season", name="Park season", category=CATEGORY_PARKS,
       significance=30, policy=POLICY_NONE, product_class=CLASS_PLANNER,
       policy_reason="A park is a place, not an event.", land=LAND_NPS),
    _d(key="hotline_report", name="Hotline report", category=CATEGORY_BLOOMS,
       significance=50, policy=POLICY_LIVE, product_class=CLASS_PLANNER,
       policy_reason="A report that names no curated phenomenon stays planning context."),
)}

# Phenomena a report can activate on its own, without a seasonal window.
REPORT_ACTIVATED = frozenset({"dolphin_megapod", "bioluminescent_surf", "frazil_ice", "moonbow",
                              "horsetail_firefall", "fresh_snow_clearing"})

# Park access a phenomenon depends on, by where it happens. Only these need a
# current, complete NPS read before Can't Miss may act; the others do not wait
# on a feed that says nothing about them. (park code, words that tie a closure
# to this place). Terms are matched against closure/danger alerts only.
YOSEMITE_VALLEY_TERMS = ("yosemite valley", "valley floor", "northside drive", "southside drive",
                         "el portal road", "big oak flat road", "wawona road", "highway 140", "hwy 140",
                         "highway 41", "hwy 41", "highway 120", "hwy 120")
ACCESS_REQUIREMENTS = {
    "horsetail_firefall": ("yose", ("firefall", "horsetail", "el capitan", *YOSEMITE_VALLEY_TERMS)),
    "moonbow": ("yose", ("yosemite fall", "yosemite falls", "lower yosemite", "sentinel bridge", "glacier point",
                         *YOSEMITE_VALLEY_TERMS)),
}
# Report-activated phenomena whose access depends on the zone they were reported in.
ZONE_ACCESS = {
    "yosemite_valley": ("yose", ("tioga", "glacier point", *YOSEMITE_VALLEY_TERMS)),
    "sequoia_kings": ("seki", ("generals highway", "highway 180", "hwy 180", "kings canyon road",
                               "mineral king", "giant forest", "grant grove")),
}
ZONE_ACCESS_PHENOMENA = frozenset({"fresh_snow_clearing", "frazil_ice"})


def access_requirement(item) -> tuple[str, tuple[str, ...]] | None:
    """(park code, place terms) when this occurrence needs a current NPS access check."""
    phenomenon = getattr(item, "phenomenon", "")
    if phenomenon in ACCESS_REQUIREMENTS:
        return ACCESS_REQUIREMENTS[phenomenon]
    if phenomenon in ZONE_ACCESS_PHENOMENA:
        return ZONE_ACCESS.get(getattr(item, "zone_id", ""))
    return None


# When both are eligible, the first is shown inside the second, never beside
# it: orcas seen hunting *are* the orca presence.
SUBSUMED_BY = {"orca_presence": "transient_orca_hunt"}

CATEGORY_FALLBACK = {
    CATEGORY_PARKS: "park_season",
}


def definition(key: str, category: str = "") -> PhenomenonDefinition | None:
    """The curated definition for a phenomenon key, or a category fallback."""
    found = CATALOG.get(key)
    if found is None and category in CATEGORY_FALLBACK:
        found = CATALOG[CATEGORY_FALLBACK[category]]
    return found


def behaviors_in(text: str, terms: tuple[str, ...]) -> tuple[str, ...]:
    """Every behaviour phrase present in a piece of text."""
    lowered = (text or "").lower()
    return tuple(term for term in terms if term in lowered)


def phenomena_named(text: str, category: str | None = None) -> list[str]:
    """Curated phenomena whose fixed vocabulary appears in a report.

    Fixed vocabulary only: an email or hotline sentence can *match* a
    phenomenon, never create one, move one, or raise its significance.
    """
    lowered = (text or "").lower()
    found = []
    for item in CATALOG.values():
        if not item.behavior_terms:
            continue
        if category and item.category != category and not (
                category == CATEGORY_RARE and item.category in (CATEGORY_RARE, CATEGORY_BIRDS)):
            continue
        if any(term in lowered for term in item.behavior_terms):
            if item.location_terms and any(other.location_terms and any(t in lowered for t in other.location_terms)
                                           for other in CATALOG.values() if other.key != item.key
                                           and other.behavior_terms == item.behavior_terms) \
                    and not any(t in lowered for t in item.location_terms):
                continue
            found.append(item.key)
    return found
