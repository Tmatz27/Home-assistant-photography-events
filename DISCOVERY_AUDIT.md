# Discovery audit — regret prevention, not an encyclopedia

Written 2026-09-27 for the 0.16.0 overhaul, **before** the architecture was
changed. Read it with AGENTS.md. It records what the code actually produced,
what each output really represented, where the model was overloaded, which
phenomena exist within roughly six hours of Vandenberg SFB (34.7420,
-120.5724), and what each is allowed to do.

## Research method and its limits

- Live web research used the agent's search tool. Direct HTTP from the
  development container was blocked for every data host tried
  (api.weather.gov, NPS, FWS, eBird, iNaturalist, Open-Meteo, elephantseal.org,
  sunsetwx.com, sunsethue.com, carpinteriasealwatch.org). Nothing below was
  fetched and parsed by the integration from here; where a page could not be
  opened its content is described only as far as search results quoted it.
- Sources are ranked: managing agency (NPS, USFWS, CDFW, California State
  Parks, city ordinance, NOAA/NWS, NASA/JPL, USGS) first; recognised
  conservation or research organisations with field presence (Friends of the
  Elephant Seal, Carpinteria Seal Watch, Xerces Society / Western Monarch
  Count, Scripps) second; journalism only to date a specific count.
  Tourism blogs were not used as evidence.
- Every drive time here is an **approximate free-flow estimate from
  Vandenberg**, not a routed figure.
- Thresholds are either **sourced** (cited) or **product thresholds** — tunable
  choices about what is worth a photographer's attention, labelled as such.
  A product threshold is never presented as an ecological fact.

---

## 1. Every source that could generate an Opportunity (before 0.16.0)

| Builder | What it emitted | What it really was |
| --- | --- | --- |
| `events.build_sunset_opportunities` | Sunset/sunrise rows per zone with a sunset specialty (Piedras Blancas, Big Sur, Tahoe) | A **forecast-conditions model** for a local sky. With the 1 h sunset radius every sunset zone (≥1.5 h) was gated out, so the category was effectively dead for the home area it matters to. |
| `events.build_meteor_opportunities` | One peak night per shower per zone, 365 days | **Computed geometry** + cloud. Correct engine; twelve zone copies rolled up by `roll`. |
| `events.build_milky_way_opportunities` | Every usable night × every zone, 35 days | **Computed geometry** + cloud. A recurring monthly condition, not a rare event. |
| `events.build_seasonal_opportunities` | 22 `PeakWindow` rows (seasons beyond 60 days, peaks inside) | **Phenomena** with calendar windows. Mixed biological behaviours, blooms and foliage. |
| `events.build_wildlife_opportunities` | A row per clustered eBird notable / iNaturalist sighting (curated bird list + all marine taxa) | **Signals.** Raw presence reports scored on freshness/observer count, reaching 80–95 — *freshness was being scored as importance*. |
| `events.build_field_report_opportunities` | "Wildflowers reported – X", "Autumn colour reported – X" rows | **Signals** (hotline prose). Duplicated the matching curated window. |
| `events.build_park_opportunities` | "Channel Islands NP – best window" etc. | **Planning context.** A park is not an event. |
| `grunion.opportunities` | CDFW expected two-hour intervals | **Published schedule** (expected, not observed). |
| `spectacles.watch_opportunities` | Year-long rows: bioluminescent surf, waterfowl flights, Pinnacles condors; plus moonbow nights | Search targets (**watch**), plus **computed** moonbow sky geometry. |
| `spectacles.report_opportunities` | "Dolphin megapod reported" (Condor Express, dated) | **Operator report (signal)** proving an aggregation — the only true behaviour feed. |
| `spectacles.aurora_opportunities` | Local OVATION ≥30% at a dark zone | **Model nowcast.** |
| `waves.build_opportunities` | Exceptional swell (NDBC measured / CDIP forecast) | **Measurement + forecast**, calibrated. |
| `eclipses.opportunities` | Lunar umbral windows; solar central-path sites | **Computed** from the NASA catalog. |
| `events.build_grunion_runs` | Lunar-heuristic run nights | Legacy; not called by the coordinator. |

## 2. What each output really represents → its new role

| Output | New role |
| --- | --- |
| eBird notable sighting (any species) | **Signal**; Bird Chase if within 6 h and not a private location |
| eBird/iNat sighting of an iconic bird (condor, eagles, cranes, geese, grebes) | **Signal**; Bird Encounter when repeated at one public place; Bird Spectacle only with count/behaviour |
| iNaturalist marine mammal sighting | **Signal**; corroborates presence of a curated marine phenomenon, never its behaviour |
| iNaturalist terrestrial mammal sighting (elk, bear, bighorn, elephant seal) | **Signal**; encounter evidence only |
| Hotline bloom/colour report | **Signal** merged into the curated bloom/foliage phenomenon it names; standalone planner row only when no phenomenon matches |
| Emailed report | **Signal**; fixed vocabulary now tags the phenomenon and behaviour it states |
| Condor Express megapod statement | **Signal** that satisfies the `dolphin_megapod` aggregation policy → **Opportunity** |
| PeakWindow | **Phenomenon** (curated), with a trigger policy |
| Meteor peak, lunar eclipse, aurora nowcast | **Direct computed Opportunity**, still gated on significance and conditions |
| Milky Way night | **Planner** by default; Can't Miss only on a drop-everything night |
| Park season | **Planning only**, never Can't Miss |
| Moonbow sky candidate | **Planner / watch**; Can't Miss only with a dated flow/spray report plus forecast |
| Bioluminescent-surf year row | **Removed** as a row; kept as a phenomenon that activates only on a recent credible report |
| Waterfowl / condor year rows | **Removed** as rows; replaced by bird-view classification from live signals |
| Unmatched species presence (fin whale, harbor porpoise…) | **Background signal** |

## 3. Where `planning_only` was overloaded

`planning_only` meant five different things at once:

1. "This is a season, not a peak" (seasonal windows beyond 60 days).
2. "Evidence has not confirmed this" (score ≤ 60 after `_apply_evidence`).
3. "This is a place, not an event" (parks).
4. "This is a search target" (watch rows, moonbow).
5. "Ignore the drive-time limit" (`within_drive` let every planning row through).

Consequence 5 is the dangerous one: anything that was *unconfirmed* was also
*exempt from the six-hour gate*. 0.16.0 keeps `planning_only` for the planner
payload (all-day rendering, calendar semantics) but Can't Miss eligibility is
now decided by `eligibility.assess`, which applies its **own** drive gate
regardless of `planning_only`.

## 4. Where `score` was overloaded

One integer carried significance, confidence, urgency, freshness and weather
quality:

- Sightings: 55 base + 22 freshness + 12 observer count + 8 reviewer → a fresh
  humpback reached 89 and a fresh common Vermilion Flycatcher 95 — above most
  meteor showers. Freshness is **confidence**, not **significance**.
- Seasonal windows: the score was an **evidence ceiling** (60 unverified, 82
  corroborated).
- Sky/astro: the score was **condition quality**.
- Parks: a fixed **planning rank** (40/55).
- Waves/aurora/megapod: a hand-set constant (85–92) standing in for
  significance.
- `alert_candidate` and the card's likelihood colours then read that number
  as "how likely is this worth going out for", which it never measured.

0.16.0 keeps `score` as the planner's ranking value for backward compatibility
and adds a separate `Assessment` (significance, confidence, urgency,
encounter, access, condition quality, actionable, eligible, priority).

## 5. Shared lists mixing incompatible product types

- `data["opportunities"]` fed the week card, the planner, the calendar entity,
  `next_opportunity` and the action window: sightings, parks, seasons, sky
  forecasts and geometry in one list.
- The action_hero week view listed **every** event intersecting seven days
  (the test *"compact week includes every intersecting event…"* protected it).
- `best_sky_score` compared sunset scores across regional zones.
- `action_events` sorted every non-planning row by the overloaded score.

## 6. Duplicate / evidence problems found

| Problem | Example |
| --- | --- |
| Sighting row beside the phenomenon it should corroborate | "Humpback whale at Avila" + "Humpback lunge feeding" |
| Hotline row beside the curated window | "Autumn colour reported – Eastern Sierra" + "Eastern Sierra aspen, high elevation" |
| Megapod row separate from the dolphin phenomenon | "Dolphin megapod reported" + "Common dolphin calving" |
| Watch row beside the live row | "California condors at Pinnacles" (year-long) + a condor sighting row |
| **Ingested emails could never corroborate anything** | `parse_email_report` never set `observed_at` or `phenomenon_key`, and `_apply_evidence` required both. Only tests that set them by hand passed. |
| **Hotline reports could never corroborate anything** | Scraped reports carry no `observed_at`, so the same filter rejected them. |
| Undated hotline text shown as "reported today" risk | `age_label` correctly said "as read", but the row still looked current. |

## 7. Known phenomena before 0.16.0 (and their new policy)

| Key | Phenomenon | Old evidence | New policy | Product class |
| --- | --- | --- | --- | --- |
| horsetail_firefall | Yosemite firefall | static | conditions_required (dated flow report + clear west forecast) | Can't Miss when met; else planner |
| grunion_run | Grunion runs | static + CDFW schedule | live_confirmation_required | planner (watch) |
| pismo_monarchs | Pismo monarch roost | live (species) | aggregation_required + conditions_required | Can't Miss when met |
| sandhill_crane_flyin | Crane fly-in | live + behaviour | calendar_reliable (USFWS) at Merced NWR core window | Bird Spectacle |
| gray_whale_southbound | Gray whale migration | live | live_confirmation_required (presence) | planner |
| gray_whale_northbound | Gray whale mothers/calves | live + behaviour | behavior_report_required | Can't Miss when met |
| transient_orca_hunt | Orcas hunting | live + behaviour | behavior_report_required; presence → exceptional_presence | Can't Miss when met |
| blue_whale_feeding | Blue whale aggregation | live + behaviour | aggregation_required | Can't Miss when met |
| humpback_lunge_feeding | Humpback lunge feeding | live + behaviour | behavior_report_required | Can't Miss when met |
| common_dolphin_calving | Dolphin calving | live + behaviour | behavior_report_required | planner unless met |
| tule_elk_rut | Tule elk rut | live + behaviour | calendar_reliable + recent presence for encounter | Can't Miss when met |
| desert_bighorn_rut | Desert bighorn rut | static | behavior_report_required | planner |
| sierra_bighorn_rut | Sierra bighorn rut | static | behavior_report_required | planner |
| elephant_seal_battles | Elephant seal breeding & pupping | live + behaviour | calendar_reliable in core window; behaviour report earlier | Can't Miss |
| black_bear_cubs | Sows with cubs | static | behavior_report_required (sow+cub) | Can't Miss when met |
| aspen_tier1/2/3 | Eastern Sierra / passes aspen | live | live_confirmation_required (dated peak report) | Can't Miss when met |
| bloom_* (4) | Desert/valley blooms | live | live_confirmation_required (dated strong report) | Can't Miss when met |
| meteor showers | Major peaks | computed | computed + conditions | Can't Miss (major only) |
| milky way | Core nights | computed | computed + conditions (drop-everything only) | planner; rarely Can't Miss |
| eclipses | Lunar/solar | computed | computed | total lunar Can't Miss; others planner |
| aurora | Local OVATION | model | conditions_required (nowcast) | Can't Miss |
| exceptional swell | Waves | measured/forecast | forecast_plus_confirmation | Can't Miss when measured |
| moonbow | Yosemite moonbow | computed sky candidate | conditions_required (dated spray report + forecast) | planner unless met |
| dolphin megapod | Operator report | report | aggregation_required | Can't Miss |
| bioluminescent surf | Watch row | watch | live_confirmation_required + darkness + moon | Can't Miss only on report |
| waterfowl flights | Watch row | watch | count_threshold / behaviour report | Bird Spectacle |
| Pinnacles condors | Watch row | watch | exceptional_presence (repeated) → Bird Encounter; concentration → Bird Spectacle | Bird views, Can't Miss when spectacle |
| sunset/sunrise | Regional | forecast | conditions_required, **home only** | Can't Miss when exceptional |
| parks | Park seasons | — | none | planner only |

## 8. Discovery candidates (known, under-modelled and new)

Format per candidate: **category · locations · drive · payoff · encounter ·
predictability · season / peak · best time · conditions · official source ·
live source · behaviour verifiable? · access · ethics · safety · class ·
policy · decision**.

### Marine mammals and pinnipeds

**Elephant seal breeding & pupping** — pinniped · Piedras Blancas vista points,
Hwy 1 · ~1.5–2 h · bulls fighting beside newborn pups from a boardwalk ·
very high · highly predictable annual cycle · bulls arrive Nov, births mid-Dec
to early Feb, peak births late Jan, fighting Dec–Jan, molt peak ~1 May · any
daylight, overcast helps · none beyond open access · [Friends of the Elephant
Seal, birthing & breeding](https://elephantseal.org/birthing-and-breeding/) ·
[FoES "What's happening now"](https://elephantseal.org/whats-happening-now/)
(could not be opened from this environment; page structure unverified, so no
scraper — use `ingest_report`) · yes, by the docent report · public boardwalk,
parking on Hwy 1 · stay behind barriers, MMPA · roadside parking · **Can't
Miss** · `calendar_reliable` in the core window 25 Dec–31 Jan, earlier with a
dated behaviour report · **accepted**. Phases (arrival, pupping, dominance,
combat, mating, weaning, molt) are carried as detail, not rows.

**Carpinteria harbor seal pupping** — pinniped · Carpinteria Bluffs harbor
seal rookery overlook (blufftop trail from 499 Linden Ave, ~1.3 mi) · ~1.5 h ·
mother–pup pairs on the beach below a public overlook · high in peak ·
predictable · beach closed 1 Dec–31 May by City Ordinance 470; births mostly
February–March, a few Dec–May; ~60 pups a year · low tide (the colony hauls
out and Seal Watch monitors at low tide) · none · [City of Carpinteria rookery
page](https://carpinteriaca.gov/parks-and-recreation/carpinteria-harbor-seal-rookery/),
[Carpinteria Seal Watch](https://carpinteriasealwatch.org/information/) ·
Seal Watch counts (not machine-readable; ingest) · yes by docent count ·
bluff overlook only; beach closed · MMPA; never go onto the closed beach;
no drone · bluff edge · **Can't Miss** (modest significance) ·
`calendar_reliable` 15 Feb–31 Mar core · **accepted** as a first-class
phenomenon.

**Humpback lunge feeding** — cetacean · Avila/Port San Luis, Monterey Bay,
Channel Islands · 0.75–3 h · bait-ball lunges near shore · moderate once
reported · stochastic within a season · Mar–Nov, watch Aug–mid-Oct · calm
mornings · bait fish inshore · [NOAA Fisheries](https://www.fisheries.noaa.gov/west-coast/marine-mammal-protection/whalewatch) ·
operator reports / email · yes only by report · piers, bluffs, boats ·
100 yd approach guidance; no drone over whales · boat/cliff edges · **Can't
Miss when behaviour reported** · `behavior_report_required` · accepted.
Humpback presence alone → background signal and "species present" state.

**Blue whale feeding aggregation** — Santa Barbara Channel (boat) · ~1.5 h ·
largest animal alive, often close · moderate on trips in season · stochastic ·
May–Oct, watch mid-Jul–mid-Sep · boat · krill · NOAA · operator reports ·
yes by report · boat only · approach rules · sea state · **Can't Miss when
aggregation reported** · `aggregation_required` · accepted.

**Orcas (Bigg's transient) hunting / presence** — Monterey Bay canyon (boat) ·
~3 h · predation · low–moderate · stochastic · Apr–Jun · boat · — · NOAA ·
operator/iNat · behaviour by report · boat · keep distance · sea state ·
**Can't Miss** for hunting; presence may qualify as `exceptional_presence`
(product threshold: ≥2 independent reports within 72 h, or one research-grade
report within 36 h) · accepted.

**Common dolphin megapod / calving** — Santa Barbara Channel (boat) · ~1.5 h ·
thousands of animals, calves in echelon · moderate on a trip once reported ·
stochastic · megapods any season, calving winter · boat · — · — · Condor
Express dated reports (parsed, strict) · yes (explicit sized pod) · boat ·
no pursuit · sea state · **Can't Miss** only on a dated sized-pod report ·
`aggregation_required` · accepted. Common dolphin **presence** → signal only.

**Gray whale mothers & calves northbound** — Shell Beach, Morro Bay bluffs,
Big Sur turnouts · 0.75–3 h · pairs in the surf line · moderate · semi-
predictable · Apr–May · mornings · — · [NOAA calf counts](https://www.fisheries.noaa.gov/west-coast/science-data/gray-whale-condition-and-calf-production) ·
reports · behaviour by report · bluffs · distance · cliff edges ·
**Can't Miss when reported** · `behavior_report_required` · accepted.
Southbound migration presence → planner (distant blows are not a regret event).

**Southern sea otter mother–pup concentrations** — Elkhorn Slough / Moss
Landing · ~3 h · mother–pup rafts at close range · high presence, pups
year-round · pupping year-round; sources disagree on the peak
(Feb–Jun vs Oct–Jan) · morning calm · — · Aquarium of the Pacific species
card; no single agency peak published that was reachable here · no live source
· pups visible but "pup present" is not reported by any feed · harbor/slough
public areas, kayak tours · otters are ESA-threatened; MMPA; kayaks are a
documented disturbance source — keep distance · — · **planning only** ·
`behavior_report_required` · **deferred**: add when a dated pup-count report
can be ingested; the conflicting peak statements are not a basis for dates.

### Terrestrial mammals

**Tule elk rut** — Carrizo Plain (Windmill Road/Soda Lake Road area), Tomales
Point · 2 h / ~6 h · bugling, sparring, harems · high at Tomales, moderate at
Carrizo (herd dispersed) · rut timing highly predictable, encounter not ·
Aug–Oct, peak late Aug–Sep ([NPS Point Reyes tule elk viewing](https://www.nps.gov/thingstodo/tule-elk-viewing-point-reyes.htm)) ·
dawn · — · NPS, BLM Carrizo · iNaturalist presence · behaviour inferred from
timing, encounter from presence · public roads · stay in vehicle; distance ·
dirt roads impassable wet · **Can't Miss** · `calendar_reliable` with a
product requirement of a recent elk report near the site for encounter ·
accepted.

**Black bear sows with cubs** — Yosemite Valley meadows, Sequoia Crescent
Meadow · 5.5–4 h · cubs in meadows · low unless reported · stochastic ·
Apr–Jun · dawn · — · [CDFW black bear](https://wildlife.ca.gov/Conservation/Mammals/Black-Bear) ·
Bear Tracker; reports · only by a report saying sow + cub · roads/boardwalks ·
never between sow and cubs; no den locations; 50 yd · — · **Can't Miss when
reported** · `behavior_report_required` · accepted. Generic bear presence →
signal.

**Bighorn ruts (desert, Sierra)** — Death Valley springs / Lee Vining canyon ·
6 h+ · rams clashing · very low · stochastic · Aug–Sep / Nov–Dec · first
light · — · CDFW · none reliable · report only · rugged · endangered Sierra
population; no positions · heat, terrain · **planning only** ·
`behavior_report_required` · accepted as planner.

**Tarantula mating walk** — Pinnacles NP (roads/trails at dusk) · ~3 h ·
males wandering in daylight/dusk · moderate in season · predictable season ·
Sep–Oct ([NPS Pinnacles tarantulas](https://www.nps.gov/pinn/learn/nature/tarantula.htm)) ·
late afternoon/dusk · warm evenings · NPS · none · no · park roads · never
handle; drive slowly · heat · **planning only** · `calendar_reliable` season
note · **accepted as planner** (niche macro subject; not a regret event).

### Birds

**Sandhill crane fly-in (and Ross's/snow goose lift-offs)** — Merced NWR auto
tour and Sandhill Crane fly-in programme; Woodbridge ER · ~4 h / ~5 h ·
thousands of cranes landing in the last light · high Dec–Feb · highly
predictable daily behaviour in season · Oct–Feb, best Dec–Feb; "as many as
20,000 cranes and 60,000 arctic-nesting geese"; "predictable daily spectacle"
at sunset ([USFWS Merced NWR](https://www.fws.gov/refuge/merced)) · sunset;
geese lift off at dawn · — · USFWS · eBird counts (species query) · the
behaviour is the documented daily cycle · auto tour route, stay in vehicle ·
refuge rules; drones prohibited (50 CFR 27.34/27.51) · tule fog driving ·
**Bird Spectacle** (Can't Miss eligible) · `calendar_reliable` Dec 1–Jan 31
core, count evidence raises confidence · accepted. Sacramento NWR geese are
~6 h+ → planner only.

**California condor activity** — Pinnacles High Peaks / campground ridge; Big
Sur coast · ~3 h · condors on thermals and at roost · moderate ("no guarantee"
per NPS) · stochastic · year-round · early morning / evening roost, thermals
late morning ([NPS condor viewing tips](https://www.nps.gov/pinn/learn/nature/condor-viewing-tips.htm)) ·
— · NPS · eBird/iNat sightings · repetition yes; behaviour via counts/reports ·
High Peaks strenuous · no roost/nest positions; stay on trails; drones
prohibited (NPS) · heat on High Peaks · **Bird Encounter** when repeated;
**Bird Spectacle** with concentration · `exceptional_presence` (product
threshold: ≥3 independent reports over ≥2 days within 7 days within 15 km of a
known public viewing area; spectacle at ≥3 birds in one report or a behaviour
report) · accepted.

**Bald eagles, Cachuma Lake** — Cachuma Lake eagle cruises · ~1 h · wintering
eagles fishing · moderate on naturalist cruises · predictable season ·
Nov–Feb cruises (Santa Barbara County Parks naturalists); one resident pair
plus migrants · morning cruise · — · County Parks (via news listings; county
page not reachable here) · eBird/iNat presence · fishing by report · boat
cruise, reservations · no nest approach · — · **Bird Encounter**, Spectacle
when fishing/multiple eagles reported · `behavior_report_required` · accepted.

**Golden eagle courtship/display** — no public, predictable concentration
identified within 6 h from an authoritative source · **deferred / bird
encounter only from live signals**.

**Western/Clark's grebe rushing** — Clear Lake (≥6 h), Lake Hodges (~5 h) ·
courtship running on water · moderate in season · predictable season, not
day · late spring–summer · calm mornings · — · Cornell All About Birds
(species); no agency timing page found · eBird presence · no feed reports the
display · boat tours / shore · nesting colonies — do not approach · — ·
**Bird Spectacle only on a dated behaviour report**; otherwise planner ·
`behavior_report_required` · **deferred** as a curated window: no sourced
dates within 6 h.

**Bird chase (vagrants, locally notable)** — anywhere · any · a rare bird ·
low per trip · stochastic · any · per report · — · eBird notable · eBird ·
presence · per report · private locations hidden (eBird `locationPrivate`) ·
— · **Bird Chase** dashboard only · n/a · accepted.

### Insects

**Pismo monarch overwintering roost** — Pismo State Beach Monarch Butterfly
Grove · ~45 min · dense clusters in eucalyptus · depends entirely on this
year's numbers · season predictable, numbers not · Nov–mid-Feb; historical
peak Thanksgiving–Christmas ([California State Parks grove](https://www.parks.ca.gov/?page_id=30273)) ·
cold mornings — monarchs cannot fly below about **55 °F** and stay clustered
([Xerces Society visiting guidance](https://xerces.org/blog/everything-you-need-to-know-about-visiting-overwintering-monarchs)) ·
counts meaningful + cold dawn · Western Monarch Count (Xerces) · grove
docent counts (ingest); recent early-season counts were in the **hundreds**
(235 on 2 Nov 2025; ~400 in a later season), so current numbers cannot be
assumed · aggregation yes by count · public grove boardwalk · never touch
clusters or shake branches; no drone · — · **Can't Miss** · `aggregation_required`
(product threshold: a dated count ≥1,000 at the grove) + `conditions_required`
(dawn ≤55 °F forecast) · accepted. A single *Danaus plexippus* iNaturalist
observation is a signal, never proof of an active roost.

### Ocean and coast

**King Tides** — coastal viewpoints, Morro Rock, Avila, Santa Barbara ·
0.5–1.5 h · extreme high water · certain · predictable (published) ·
2026–27 statewide dates **24–26 Nov 2026, 23–25 Dec 2026, 21–22 Jan 2027**
([California Coastal Commission King Tides Project](https://www.coastal.ca.gov/kingtides/)) ·
high-tide hour from NOAA CO-OPS · — · CCC, NOAA · NOAA predictions (fetched) ·
n/a · public · — · waves over seawalls; never on jetties · **planner**, compound
with swell or full Moon noted · `computed` (published dates + tide table) ·
accepted.

**Extreme negative low tides for tidepools** — Montaña de Oro, Shell Beach,
Point Sal area · ~1 h · exposed intertidal · certain · predictable ·
winter afternoons / spring mornings · low water ≤ −1.0 ft MLLW (commonly
recommended "−1.0 to −1.4 ft" and "anything below 0.0" per tidepooling
guidance aggregated from California State Parks/Cal Academy search results) ·
— · NOAA CO-OPS · fetched · n/a · public · Good Tidepooler rules ·
sneaker waves; High Surf advisories cancel · **planner** ·
`computed` (product threshold −1.0 ft) · **accepted as planner**; not Can't
Miss (monthly).

**King Tide + major swell** — Vandenberg coast / Point Sal bluffs · dramatic
overwash · rare · compound · **Can't Miss only via the swell phenomenon** with
a King Tide note and strict safety text · accepted as a compound note, not a
separate row.

**Exceptional Pacific swell** — existing calibrated NDBC 46011/CDIP B1500 ·
accepted; `forecast_plus_confirmation`: CDIP forecast = watch, buoy-measured =
Can't Miss.

**Bioluminescent surf** — SLO/SB beaches · glowing breakers · stochastic ·
red-tide dependent · dark, moonless · [Scripps red tide explainer](https://scripps.ucsd.edu/news/everything-you-wanted-know-about-red-tides) ·
dated reports only (ingest) · yes by report · public beaches · — · night surf ·
**Can't Miss** only with a report ≤3 days old + darkness + Moon < 50 % lit
(product) · `live_confirmation_required` · accepted; the annual row is removed.

**Grunion runs** — CDFW schedule · accepted as planner (`live_confirmation_required`).

**La Jolla leopard shark aggregation** — La Jolla Shores · ~5 h · hundreds of
sharks in knee-to-waist water · high in season · predictable summer–fall
aggregation (Scripps/Birch Aquarium) · summer, pregnant females · calm,
clear water, snorkel · — · Scripps · none · no · public beach, guided snorkels ·
harmless to people; do not touch · surf · **planning only** · `calendar_reliable` ·
**accepted as planner** (underwater subject; Osmo Pocket 3 is the only owned
waterproof-capable camera only with a housing — not recommended).

### Waterfalls, ice and snow

**Yosemite frazil ice** — Yosemite Creek below Lower Fall · ~6 h · lava-like
slush flow · moderate when conditions hold · conditions-driven ·
fall–spring, most commonly April, sometimes March/May; high flow + overnight
lows below freezing; usually before 9 am ([NPS frazil ice](https://www.nps.gov/yose/planyourvisit/frazilice.htm)) ·
early morning · freezing night + high flow · NPS · none (Merced gauge is a
different drainage and must not be used) · by report · paved paths · — ·
**dangerous: never step on frazil ice** · **Can't Miss only on a dated
report**; forecast freeze = watch · `forecast_plus_confirmation` · accepted
as a watch phenomenon.

**Exceptional spring waterfall runoff** — Yosemite Valley · ~6 h · peak
falls · conditions-driven · May–June · — · NPS current conditions · USGS
Merced (basin proxy only) · no direct measure of a fall · **planner**
(annotated with basin proxy) · `conditions_required` · deferred until a
fall-specific source exists.

**Yosemite firefall** — existing; `conditions_required` · accepted.

**Yosemite moonbow** — existing; `conditions_required` · accepted.

**Yosemite clearing storm / first major Sierra snow + clearing** —
Yosemite Valley, Eastern Sierra · 5.5–6 h · fresh snow on granite in
clearing light · stochastic · Nov–Apr · clearing hours · forecast snowfall
followed by clearing · NWS forecasts · Open-Meteo snowfall/cloud (model) ·
observed accumulation needs a report · chain controls, closures · — · winter
driving; chain controls; never into a Winter Storm Warning · **watch signal**
· `forecast_plus_confirmation` (product threshold: ≥10 cm modelled snowfall
in 24 h followed by ≤30 % cloud within 18 h) · accepted as watch only.

**Yosemite ice cones / unusual ice** — NPS mentions snow cones under Upper
Fall · no source to time it · **deferred**.

### Weather and atmospheric optics

| Candidate | Decision | Why |
| --- | --- | --- |
| Lightning / thunderstorm | **watch** from forecast thunder codes; Can't Miss needs observed lightning — **no detection feed connected** | GOES GLM needs netCDF tooling; third-party networks have restrictive terms. Documented gap. |
| Lenticular / mountain-wave clouds | **deferred** | needs satellite/webcam evidence; forecast wave setups are only a watch |
| Mammatus, shelf clouds, rain shafts, virga | **reject for automation** | not forecastable with available sources |
| Rainbows / fogbows | **deferred** | geometry is computable (Sun <42°, rain opposite the Sun) but no radar source connected |
| Marine-layer spillover / fog waterfalls / ridge-top inversions | **deferred** | requires a validated elevated public viewpoint above the deck; none verified |
| Tule fog | **reject** as a subject; noted as a driving hazard to Merced NWR |
| Sun/moon pillars, halos, parhelia, CZA/CHA, iridescence | **reject for alerting** | watch-only at best; observed evidence rarely arrives in time |
| Crepuscular/anticrepuscular rays | covered implicitly by the local sunset model |
| Superior mirage | **deferred**; no evidence source |
| Waterspouts | **reject** | safety and rarity |
| Storm surf / coastal spray | via exceptional swell |
| Wildfire-smoke sunsets | **reject as a positive signal**; smoke/AQI is a safety constraint, never an invitation |

### Sky

| Candidate | Decision |
| --- | --- |
| Major meteor peaks (Quadrantids, Perseids, Geminids) | Can't Miss when conditions hold |
| Minor showers | planner |
| Total lunar eclipse visible | Can't Miss |
| Partial lunar / solar central path sites | planner |
| **Closest / largest full Moon of the year** | Can't Miss when the rise is photogenic (new lunar engine). Published anchor: closest full Moon of 2026 is **24 Dec 2026, 356,758 km**, with 24 Nov (360,800 km) and 22 Jan 2027 (357,661 km) close behind ([EarthSky supermoon list](https://earthsky.org/astronomy-essentials/what-is-a-supermoon/), [NASA supermoons](https://science.nasa.gov/moon/supermoons/)). It coincides with the 23–25 Dec King Tides. |
| Ordinary full Moons | planner facts only |
| Micromoon | planner fact |
| Planetary conjunctions / Moon–planet pairings / oppositions | **deferred to backend**; the standalone card computes them. Two-body positions are ~20 h off for Mars/Saturn (AGENTS), adequate for a planner note but not a Can't Miss claim. |
| Occultations | **deferred** (needs sub-arcminute ephemeris) |
| Bright comets | **deferred**: no authoritative brightness feed wired. JPL Horizons gives ephemerides, not reliable magnitude forecasts; observed magnitudes (COBS) would be the evidence. Never treat a predicted magnitude as fact. |
| Zodiacal light | planner candidate (spring evenings/autumn mornings, dark new-Moon); deferred |
| Local aurora | Can't Miss (nowcast) |

### Parks

All ten parks remain **planning only**. Park-specific spectacles (firefall,
moonbow, frazil ice, condors, tarantulas, bear cubs, elk at Carrizo NM) are
their own phenomena.

## 9. Summary of classification

- **Can't Miss eligible (when their policy is met):** elephant seal breeding &
  pupping, Carpinteria harbor seal pupping, tule elk rut, humpback lunge
  feeding, blue whale aggregation, orca hunting/presence, dolphin megapod,
  gray whale mother–calf, sows with cubs, Pismo monarchs, aspen peaks,
  superblooms, firefall, moonbow, exceptional swell, bioluminescent surf,
  major meteor peaks, total lunar eclipse, local aurora, largest full Moon,
  exceptional local sunset/sunrise, drop-everything Milky Way night.
- **Bird Spectacle:** crane fly-in, condor concentration, bald eagle fishing,
  mass waterfowl flights (by report/count).
- **Bird Encounter:** repeated iconic-bird presence at a public site.
- **Bird Chase:** eBird notable reports.
- **Planning only:** parks, seasons beyond 60 days, bighorn ruts, grunion,
  sea otters, leopard sharks, tarantulas, King Tides, minus tides, Milky Way
  nights, minor showers, ordinary full Moons, partial eclipses.
- **Watch signal:** forecast swell, forecast snow + clearing, thunderstorms,
  species presence without behaviour, undated hotline reports.
- **Rejected for automation:** mammatus/shelf clouds, waterspouts, smoke
  sunsets, tule fog as a subject.

## 10. Data model (implemented in 0.16.0)

```
Signal (signals.py)            raw evidence: sighting, report, measurement,
  kind, source, url,           forecast, computed geometry, alert
  observed_at / valid_at,
  basis (observed|reported|forecast|computed), taxon, place, lat/lon,
  count, reports, days, confirmed, private_location, behaviors, phenomenon

PhenomenonDefinition (curation.py)
  key, name, significance, policy, product_class, policy_reason,
  behavior_terms, taxa, land (drone policy), ethics, safety, gear_profile,
  encounter, sources

Opportunity (events.py, unchanged identity)   a phenomenon at a time/place
  + phenomenon key, extra.evidence_state, extra.signals

Assessment (eligibility.py)
  significance, confidence (+basis), urgency, encounter, access,
  condition_quality, evidence_state, actionable, eligible, blockers,
  priority, presentation, why_now, status, safety, unsafe

Presentation: cant_miss | bird_spectacle | bird_encounter | bird_chase |
              planner | watch | background
```

Flow: collectors → **signals** → merged into **phenomena** (`_apply_evidence`
with behaviour vocabulary) → Opportunities → `eligibility.assess` (hard gate:
curated class, policy satisfied, seven-day window, six-hour drive, significance
floor, not unsafe) → rank eligible by priority → Can't Miss (≤5 shown).
The planner keeps every row.

## 11. Migration strategy

- Entity IDs unchanged; a new `sensor.photography_events_can_t_miss` is added.
- `binary_sensor…action_opportunity` now turns on only for an **eligible**
  Can't Miss opportunity in 48 h (previously any row over the alert score).
  Existing automations keep working and will fire less often — intended.
- Planner payload unchanged in shape; rows gain `presentation`,
  `evidence_state`, `significance`.
- Stored Follow/Skip/Seen choices are keyed by occurrence id, which is
  unchanged for every surviving row. Rows that no longer exist (raw sightings,
  hotline duplicates) expire from the Store on their own date.
- `action_hero` cards render the Can't Miss view when the new sensor exists
  and fall back to the 0.15 week view against an older backend.
- The alert-score option remains and still gates the sunset local model's
  display threshold; it no longer decides Can't Miss eligibility.

## 12. Tests that must change

- JS *"compact week includes every intersecting event with its own details,
  not bare chips"* — protects the overload; replaced by Can't Miss tests.
- Python `TestSightingOpportunities` scored raw sightings as opportunities
  ("a staked-out confirmed rarity clears the alert bar", "humpbacks rank below
  orcas") — replaced by signal/bird-class tests; the ranking intent moves to
  significance.
- `test_ordinary_birds_do_not_become_standalone_photography_targets` —
  reframed: no bird becomes a standalone row; notable birds are Bird Chase.
- `test_sightings_far_from_any_zone…` — now asserts the Bird Chase drive gate.
- `test_action_window_is_sorted_by_score…` — action window now uses priority
  among eligible rows.
- Email corroboration tests — now pass without hand-setting
  `observed_at`/`phenomenon_key` where the text states it.

New regression tests cover the full list in the 0.16.0 brief; see
HANDOFF_LOG.md for counts.
