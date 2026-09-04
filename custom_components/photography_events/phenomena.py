"""Concrete peak photography windows, replacing the old broad seasons.

The rule this module exists to enforce: **a background season and an actionable
window are different facts, and only the second one may trigger anything.**

"Gray whales, December to May" is true and useless. It is true on 150 days, and
on most of them you will stand on a headland and see nothing. The southbound
adults stream past the coastal points in a three-week pulse in January, and the
northbound mothers hug the surfline in a five-week pulse in April and May. Those
are the windows worth a drive, and they are what this table stores.

So every entry carries both:

- ``season_range`` - informational only. Never scored, never alerted on. It is
  the sentence you want on a card a hundred days out, when "April to November"
  is genuinely the most honest thing anyone can say.
- ``peak_start`` / ``peak_end`` - the concrete window. This is what scores, and
  it is the only thing that can raise an alert.

Alongside those, each entry carries what you actually need to decide and to
pack: the specific overlooks rather than a region, real focal lengths and
support, and the behavioural or tidal detail that decides whether you get the
shot. Coordinates are the primary location, approximate to a parking area
rather than a spot, and are what drive times are computed from.

Timing that genuinely moves year to year - the rain-dependent blooms above all
- is flagged ``confirm``, and the live hotline scrapers in ``field_reports``
remain the authority for those. This table gives you the window to plan around;
it never claims to know that this year's bloom happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .const import (
    CATEGORY_BLOOMS,
    CATEGORY_FOLIAGE,
    CATEGORY_MAMMALS,
    CATEGORY_MARINE,
    CATEGORY_RARE,
)

# --- Evidence basis ---------------------------------------------------------
#
# The question that matters is not "is my calendar date right" but "is it
# actually happening", and those need different answers. So every entry states
# what its dates rest on, and that decides what it is allowed to do.
#
# No API publishes peak windows. Nobody serves "gray whale southbound peak =
# 5-25 January" as data; it does not exist in machine-readable form anywhere.
# What can be verified is whether something is being seen right now - and for
# anything biological that is the better question anyway.

# Derived from geometry. Verifiable to the minute, alerts freely.
EVIDENCE_COMPUTED = "computed"
# A search season, not a promise. May plan, and may only alert once live
# sightings corroborate it.
EVIDENCE_LIVE = "live"
# A calendar estimate with no live source. Plans only, never alerts.
EVIDENCE_STATIC = "static"

# A window longer than this is a season wearing a peak's clothes. The rule it
# triggers is about verifiability rather than length: a window this broad may
# never alert on its date alone, whether because a live source can confirm it
# (EVIDENCE_LIVE) or because nothing can and it stays planning-only
# (EVIDENCE_STATIC). Tightening these dates by guesswork would be worse than
# admitting their width - a confidently wrong three-week window is exactly how
# somebody books a trip and misses the thing.
MAX_TRUE_PEAK_DAYS = 40

# How fresh and how near a sighting has to be to corroborate a window.
LIVE_CORROBORATION_DAYS = 14
LIVE_CORROBORATION_KM = 120.0

# Inside this many days the calendar stops speaking in seasons and starts
# giving concrete windows, locations and gear. Beyond it, a vague answer is the
# honest one - weather models do not reach, and animals do not read calendars.
PRECISION_HORIZON_DAYS = 30


@dataclass(frozen=True)
class PeakWindow:
    """One phenomenon: its background season, and the window that matters."""

    key: str
    name: str
    category: str
    season_range: str
    peak_start: tuple[int, int]
    peak_end: tuple[int, int]
    latitude: float
    longitude: float
    primary_locations: tuple[str, ...]
    recommended_gear: str
    photo_tips: str
    best_time_of_day: str = ""
    confirm: bool = False
    lunar_dependent: bool = False
    evidence: str = EVIDENCE_STATIC
    # Scientific names whose recent sightings corroborate this window.
    live_taxa: tuple[str, ...] = ()

    @property
    def peak_days(self) -> int:
        start = date(2001, *self.peak_start)
        end = date(2001, *self.peak_end)
        return (end - start).days if end >= start else (date(2002, *self.peak_end) - start).days

    @property
    def is_search_season(self) -> bool:
        """Whether these dates say "start watching" rather than "go"."""
        return self.evidence == EVIDENCE_LIVE

    def occurrences(self, year: int) -> list[tuple[date, date]]:
        """Concrete dates, splitting a window that crosses New Year."""
        start = date(year, *self.peak_start)
        end = date(year, *self.peak_end)
        if end >= start:
            return [(start, end)]
        return [
            (date(year, 1, 1), date(year, *self.peak_end)),
            (date(year, *self.peak_start), date(year, 12, 31)),
        ]


PEAK_WINDOWS: tuple[PeakWindow, ...] = (
    # --- Rare annual phenomena ---------------------------------------------
    PeakWindow(
        key="horsetail_firefall",
        name="Yosemite Horsetail Fall firefall",
        category=CATEGORY_RARE,
        season_range="Mid-February only",
        peak_start=(2, 12),
        peak_end=(2, 26),
        latitude=37.7175,
        longitude=-119.6339,
        primary_locations=(
            "El Capitan Picnic Area",
            "Southside Drive viewing areas",
        ),
        recommended_gear="70-200mm or 100-400mm telephoto, sturdy tripod, remote release",
        photo_tips=(
            "Everything depends on two things holding at once: a clear western horizon at "
            "sunset, and enough snowpack actively melting to keep water on the face. Either "
            "one failing means no glow at all. The light lands roughly 17:15-17:40 and lasts "
            "about ten minutes. Expect crowds and reservation requirements."
        ),
        best_time_of_day="Sunset, roughly 17:15-17:40",
        confirm=True,
        evidence=EVIDENCE_STATIC,
    ),
    PeakWindow(
        key="grunion_run",
        name="California grunion run",
        category=CATEGORY_RARE,
        season_range="March to August",
        peak_start=(4, 1),
        peak_end=(6, 15),
        latitude=34.4180,
        longitude=-119.6700,
        primary_locations=(
            "East Beach, Santa Barbara",
            "Silver Strand, Ventura",
            "Pismo State Beach",
        ),
        recommended_gear=(
            "Fast wide-angle (24mm or 35mm, f/1.4-f/2.8), weather-sealed body, "
            "red-filtered headlamp, waterproof knee pads"
        ),
        photo_tips=(
            "Runs happen on the 2-4 nights following a full or new moon, starting one to two "
            "hours after high tide, and the fish are only on the sand for a half-hour or so. "
            "White light ends the run - use red only. Shoot low and wide; the spectacle is "
            "the density of fish, not any single one."
        ),
        best_time_of_day="Late night, 1-2 hours after high tide",
        # Runs are not spread across the season: they fall on the nights after
        # a full or new moon, at a tide-determined hour. The season below is the
        # search range; ``events.build_grunion_runs`` computes the actual nights.
        lunar_dependent=True,
        confirm=True,
        # The season is static and cannot alert. The *runs* inside it are
        # computed from moon phase by ``events.build_grunion_runs`` and alert
        # on their own, which is the only honest way to represent a phenomenon
        # that happens on four nights a month, not across seventy-five days.
        evidence=EVIDENCE_STATIC,
    ),
    PeakWindow(
        key="pismo_monarchs",
        name="Pismo monarch butterfly roost",
        category=CATEGORY_RARE,
        season_range="Late October to February",
        peak_start=(11, 1),
        peak_end=(12, 15),
        latitude=35.1310,
        longitude=-120.6350,
        primary_locations=("Pismo State Beach Monarch Butterfly Grove",),
        recommended_gear="100-400mm or 200-600mm telephoto, monopod or tripod",
        photo_tips=(
            "Peak counts come before the first winter storms break the clusters up. Cold "
            "mornings keep them clustered and still; by afternoon warmth they fly and the "
            "boughs empty. Backlight the clusters to separate wings from eucalyptus."
        ),
        best_time_of_day="Cold mornings before the roost warms and disperses",
        evidence=EVIDENCE_LIVE,
        live_taxa=("Danaus plexippus",),
    ),
    PeakWindow(
        key="sandhill_crane_flyin",
        name="Sandhill crane sunset fly-in",
        category=CATEGORY_RARE,
        season_range="October to February",
        peak_start=(11, 15),
        peak_end=(1, 15),
        latitude=38.1560,
        longitude=-121.4160,
        primary_locations=(
            "Woodbridge Ecological Reserve, Lodi",
            "Merced National Wildlife Refuge",
        ),
        recommended_gear="400-600mm telephoto, gimbal head, high continuous burst",
        photo_tips=(
            "The birds come in to the flooded roost in waves through the last hour of light "
            "and past it. Set up facing the sunset and shoot them against the colour rather "
            "than trying to light them. Woodbridge runs docent tours; check access first."
        ),
        best_time_of_day="Last hour of light and the half hour after",
        evidence=EVIDENCE_LIVE,
        live_taxa=("Antigone canadensis",),
    ),
    # --- Marine -------------------------------------------------------------
    PeakWindow(
        key="gray_whale_southbound",
        name="Gray whale southbound migration",
        category=CATEGORY_MARINE,
        season_range="December to February",
        peak_start=(1, 5),
        peak_end=(1, 25),
        latitude=35.6664,
        longitude=-121.2871,
        primary_locations=("Point Piedras Blancas", "Point Conception", "Point Sal"),
        recommended_gear="100-400mm or 200-600mm telephoto, monopod, circular polariser",
        photo_tips=(
            "Adults pass closest to the coastal promontories on this leg. Watch for the blow "
            "first and pre-focus on the water rather than chasing. A polariser cuts the glare "
            "off the swell and is the difference between a grey lump and a visible animal."
        ),
        best_time_of_day="Morning, before the afternoon wind builds chop",
        evidence=EVIDENCE_LIVE,
        live_taxa=("Eschrichtius robustus",),
    ),
    PeakWindow(
        key="gray_whale_northbound",
        name="Gray whale mothers and calves northbound",
        category=CATEGORY_MARINE,
        season_range="March to May",
        peak_start=(4, 5),
        peak_end=(5, 10),
        latitude=35.1560,
        longitude=-120.6720,
        primary_locations=("Shell Beach", "Morro Bay bluffs", "Big Sur coastal turnouts"),
        recommended_gear="100-400mm telephoto, polariser, tripod or monopod on the bluff",
        photo_tips=(
            "Mothers hug the shallows and the surf kelp to keep calves away from orcas, which "
            "puts them far closer to shore than the southbound adults. This is the best "
            "land-based whale photography of the year on this coast."
        ),
        best_time_of_day="Morning through early afternoon",
        evidence=EVIDENCE_LIVE,
        live_taxa=("Eschrichtius robustus",),
    ),
    PeakWindow(
        key="transient_orca_hunt",
        name="Bigg's transient orcas hunting",
        category=CATEGORY_MARINE,
        season_range="April to June",
        peak_start=(4, 20),
        peak_end=(5, 25),
        latitude=36.6050,
        longitude=-121.8910,
        primary_locations=("Monterey Bay Canyon edge (boat from Monterey)",),
        recommended_gear="100-400mm on a fast body, second body wide, no tripod on a boat",
        photo_tips=(
            "Transients ambush gray whale cow/calf pairs where the migration crosses the "
            "submarine canyon. This is a boat trip, not a headland - the action is miles out. "
            "Shutter 1/2000s or faster, continuous AF, and keep both eyes open."
        ),
        best_time_of_day="Full-day boat charter; hunts run late morning onward",
        evidence=EVIDENCE_LIVE,
        live_taxa=("Orcinus orca",),
    ),
    PeakWindow(
        key="blue_whale_feeding",
        name="Blue whale feeding aggregation",
        category=CATEGORY_MARINE,
        season_range="June to October; watch window mid-Jul to mid-Sep",
        peak_start=(7, 15),
        peak_end=(9, 10),
        latitude=34.2486,
        longitude=-119.2642,
        primary_locations=("Santa Barbara Channel drop-offs (boat from Ventura or Santa Barbara)",),
        recommended_gear="70-200mm is usually enough; they surface closer than you expect",
        photo_tips=(
            "Deep krill aggregations at the channel drop-offs hold the largest animal that has "
            "ever lived, sometimes within metres of the boat. Shoot wider than instinct says - "
            "a 600mm frame of a blue whale is a photograph of grey skin."
        ),
        best_time_of_day="Full-day boat charter",
        evidence=EVIDENCE_LIVE,
        live_taxa=("Balaenoptera musculus",),
    ),
    PeakWindow(
        key="humpback_lunge_feeding",
        name="Humpback lunge feeding",
        category=CATEGORY_MARINE,
        season_range="May to November; watch window Aug-mid Oct",
        peak_start=(8, 1),
        peak_end=(10, 15),
        latitude=35.1780,
        longitude=-120.7400,
        primary_locations=("Avila Beach and Port San Luis", "Monterey Bay", "Channel Islands"),
        recommended_gear="100-400mm, fast continuous burst, polariser",
        photo_tips=(
            "Massive baitfish schools bring cooperative bubble-net feeding right into the bays, "
            "sometimes close enough to shoot from the Avila pier. Watch the birds - diving "
            "gulls and pelicans mark the bait ball seconds before the lunge."
        ),
        best_time_of_day="Morning, calm water",
        evidence=EVIDENCE_LIVE,
        live_taxa=("Megaptera novaeangliae",),
    ),
    # --- Terrestrial mammals ------------------------------------------------
    PeakWindow(
        key="tule_elk_rut",
        name="Tule elk rut",
        category=CATEGORY_MAMMALS,
        season_range="August to October",
        peak_start=(8, 20),
        peak_end=(9, 30),
        latitude=35.1914,
        longitude=-119.7929,
        primary_locations=(
            "Carrizo Plain, Soda Lake Road foothills",
            "Tomales Point, Point Reyes",
        ),
        recommended_gear="200-600mm telephoto, beanbag for car-window work or a gimbal head",
        photo_tips=(
            "Bugling, sparring and harem defence, and the whole thing runs on first light. "
            "Shoot from the vehicle where possible - it is a far better hide than standing, "
            "and keeps you the legal distance back. Backlit dust and breath in dawn light is "
            "the shot worth driving for."
        ),
        best_time_of_day="Dawn, 06:00-08:30",
        evidence=EVIDENCE_STATIC,
        live_taxa=("Cervus canadensis nannodes",),
    ),
    PeakWindow(
        key="desert_bighorn_rut",
        name="Desert bighorn sheep rut",
        category=CATEGORY_MAMMALS,
        season_range="July to October",
        peak_start=(8, 1),
        peak_end=(9, 15),
        latitude=36.4600,
        longitude=-116.8660,
        primary_locations=(
            "Death Valley: Furnace Creek washes, Titus Canyon springs",
            "Anza-Borrego",
        ),
        recommended_gear="400-600mm telephoto, tripod, plenty of water",
        photo_tips=(
            "Rams clash for dominance near the reliable water. Working the springs at first "
            "light is both the coolest and the most productive time. August heat here is "
            "genuinely dangerous - treat the trip as a desert expedition, not a drive."
        ),
        best_time_of_day="First light at the springs",
        evidence=EVIDENCE_STATIC,
        live_taxa=("Ovis canadensis nelsoni",),
    ),
    PeakWindow(
        key="sierra_bighorn_rut",
        name="Sierra bighorn sheep rut",
        category=CATEGORY_MAMMALS,
        season_range="October to December",
        peak_start=(10, 20),
        peak_end=(11, 30),
        latitude=37.9500,
        longitude=-119.2200,
        primary_locations=("Lee Vining Canyon", "Pine Creek canyon bluffs"),
        recommended_gear="500-600mm telephoto, tripod, spotting scope to find them first",
        photo_tips=(
            "An endangered population on steep ground - find them with a scope from the road "
            "and shoot long rather than approaching. Morning light on the east-facing canyon "
            "walls is the window."
        ),
        best_time_of_day="Morning, east-facing slopes",
        evidence=EVIDENCE_STATIC,
        live_taxa=("Ovis canadensis sierrae",),
    ),
    PeakWindow(
        key="elephant_seal_battles",
        name="Elephant seal bull battles and pupping",
        category=CATEGORY_MAMMALS,
        season_range="December to March",
        peak_start=(12, 25),
        peak_end=(1, 31),
        latitude=35.6640,
        longitude=-121.2570,
        primary_locations=("Piedras Blancas Rookery, San Simeon",),
        recommended_gear="100-400mm telephoto, circular polariser to cut wet sand and spray glare",
        photo_tips=(
            "Alpha bulls fight violently for beach dominance while newborn pups are underfoot - "
            "the most reliably dramatic wildlife on this coast, from a boardwalk, with no hike. "
            "Overcast is your friend; harsh sun blows out the wet hides."
        ),
        best_time_of_day="Any daylight; overcast preferred",
        evidence=EVIDENCE_STATIC,
        live_taxa=("Mirounga angustirostris",),
    ),
    PeakWindow(
        key="black_bear_cubs",
        name="Black bear sows with new cubs",
        category=CATEGORY_MAMMALS,
        season_range="April to July",
        peak_start=(5, 10),
        peak_end=(6, 10),
        latitude=37.7460,
        longitude=-119.5930,
        primary_locations=(
            "Yosemite Valley: Cook's Meadow, El Capitan Meadow",
            "Sequoia: Crescent Meadow",
        ),
        recommended_gear="400mm+ telephoto; keep the legal 50 yards and let the lens close it",
        photo_tips=(
            "Sows bring newborn cubs onto the fresh meadow sedge to graze. Shoot from the "
            "boardwalks and roads at dawn before the meadows fill with people. Never position "
            "yourself between a sow and her cubs."
        ),
        best_time_of_day="Dawn, before the meadows fill",
        evidence=EVIDENCE_STATIC,
        live_taxa=("Ursus americanus",),
    ),
    # --- Autumn colour, by elevation tier -----------------------------------
    PeakWindow(
        key="aspen_tier1_high",
        name="Eastern Sierra aspen, high elevation",
        category=CATEGORY_FOLIAGE,
        season_range="Late September to mid October",
        peak_start=(9, 25),
        peak_end=(10, 5),
        latitude=37.2270,
        longitude=-118.6260,
        primary_locations=(
            "Bishop Creek: North Lake",
            "Bishop Creek: South Lake",
            "Lake Sabrina",
        ),
        recommended_gear="70-200mm to compress stands, 16-35mm for canyon context, polariser",
        photo_tips=(
            "8,500-9,500 ft turns first and drops fastest - a hard freeze or one wind event "
            "ends it. North Lake's reflection is the classic frame and needs still air at dawn. "
            "Backlight the leaves rather than front-lighting them."
        ),
        best_time_of_day="Dawn for still reflections, backlight late afternoon",
        confirm=True,
        evidence=EVIDENCE_LIVE,
    ),
    PeakWindow(
        key="aspen_tier2_mid",
        name="Eastern Sierra aspen, mid elevation",
        category=CATEGORY_FOLIAGE,
        season_range="Early to mid October",
        peak_start=(10, 5),
        peak_end=(10, 18),
        latitude=37.7830,
        longitude=-119.0800,
        primary_locations=("June Lake Loop", "Convict Lake", "Lundy Canyon"),
        recommended_gear="70-200mm, 24-70mm, polariser, tripod for the lake reflections",
        photo_tips=(
            "7,000-8,500 ft, and the most reliably photogenic tier - the June Lake Loop puts "
            "colour, water and granite in one frame. Convict Lake at dawn with still water is "
            "the shot; by mid-morning the wind ruins the reflection."
        ),
        best_time_of_day="Dawn for reflections",
        confirm=True,
        evidence=EVIDENCE_LIVE,
    ),
    PeakWindow(
        key="aspen_tier3_north",
        name="Northern passes aspen",
        category=CATEGORY_FOLIAGE,
        season_range="Mid to late October",
        peak_start=(10, 10),
        peak_end=(10, 25),
        latitude=38.7500,
        longitude=-119.9500,
        primary_locations=("Hope Valley", "Carson Pass"),
        recommended_gear="70-200mm, wide for the valley sweep, polariser",
        photo_tips=(
            "The last tier to turn, and the most forgiving to time. Hope Valley's meadow stands "
            "photograph well in flat overcast, which is worth knowing when the Bishop Creek "
            "forecast falls apart."
        ),
        best_time_of_day="Overcast is fine; backlit late afternoon is better",
        confirm=True,
        evidence=EVIDENCE_LIVE,
    ),
    # --- Blooms -------------------------------------------------------------
    PeakWindow(
        key="bloom_anza_borrego",
        name="Anza-Borrego desert bloom",
        category=CATEGORY_BLOOMS,
        season_range="February to April, entirely rainfall dependent",
        peak_start=(2, 20),
        peak_end=(3, 15),
        latitude=33.2560,
        longitude=-116.3750,
        primary_locations=("Coyote Canyon", "Henderson Canyon Road", "Borrego Palm Canyon"),
        recommended_gear="16-35mm for fields, 70-200mm to compress, macro, polariser",
        photo_tips=(
            "The earliest of the desert blooms and the most rain-dependent. Shoot the first and "
            "last hour; midday flattens the colour completely. Check the live reports before "
            "committing - in a dry year there is nothing here at all."
        ),
        best_time_of_day="First and last hour of light",
        confirm=True,
        evidence=EVIDENCE_LIVE,
    ),
    PeakWindow(
        key="bloom_death_valley",
        name="Death Valley superbloom",
        category=CATEGORY_BLOOMS,
        season_range="February to April, only in superbloom years",
        peak_start=(3, 1),
        peak_end=(3, 25),
        latitude=36.4600,
        longitude=-116.8660,
        primary_locations=("Badwater Road", "Jubilee Pass", "Ashford Mill"),
        recommended_gear="16-35mm, 70-200mm, macro, polariser, ND for long exposures",
        photo_tips=(
            "A true superbloom here needs a specific sequence of autumn and winter rain and "
            "happens perhaps once a decade - most years this window produces scattered flowers "
            "and nothing more. Treat the live reports as the deciding vote, not this date."
        ),
        best_time_of_day="First and last hour of light",
        confirm=True,
        evidence=EVIDENCE_LIVE,
    ),
    PeakWindow(
        key="bloom_antelope_valley",
        name="Antelope Valley poppy bloom",
        category=CATEGORY_BLOOMS,
        season_range="March to May",
        peak_start=(3, 20),
        peak_end=(4, 15),
        latitude=34.7250,
        longitude=-118.4000,
        primary_locations=(
            "Antelope Valley California Poppy Reserve",
            "Lancaster Road hillsides",
        ),
        recommended_gear="70-200mm to compress hillsides, 16-35mm wide, polariser",
        photo_tips=(
            "Poppies close in wind and cloud, so a still, sunny mid-morning actually beats "
            "golden hour for open flowers - then shoot the hillsides backlit at the end of the "
            "day. Stay on the trails; the reserve is heavily and rightly patrolled."
        ),
        best_time_of_day="Still mid-morning for open flowers, backlit at sunset",
        confirm=True,
        evidence=EVIDENCE_LIVE,
    ),
    PeakWindow(
        key="bloom_carrizo_plain",
        name="Carrizo Plain valley and Temblor Range bloom",
        category=CATEGORY_BLOOMS,
        season_range="March to May",
        peak_start=(3, 25),
        peak_end=(4, 20),
        latitude=35.1914,
        longitude=-119.7929,
        primary_locations=(
            "Soda Lake Road",
            "Temblor Range ridgelines",
            "Elkhorn Road",
        ),
        recommended_gear="70-200mm for the ridge bands, 16-35mm wide, polariser, drone if permitted",
        photo_tips=(
            "The Temblor ridges band into colour stripes visible from Soda Lake Road - the "
            "signature Carrizo frame, and it wants a telephoto, not a wide. Roads turn to "
            "impassable clay when wet. Two hours from home and the nearest true dark sky, so "
            "it pairs well with a Milky Way night."
        ),
        best_time_of_day="First and last hour; the ridges band best in low side light",
        confirm=True,
        evidence=EVIDENCE_LIVE,
    ),
)

WINDOWS_BY_KEY = {window.key: window for window in PEAK_WINDOWS}


def active_windows(moment: datetime, horizon_days: int) -> list[dict]:
    """Peak windows overlapping the period ahead, nearest first.

    Each entry is tagged with a ``precision``: ``peak`` once the window is
    close enough to plan concretely, ``season`` while it is still far enough
    out that only the background range is honest. The card shows the vague
    sentence for the far ones and the full brief for the near ones.
    """
    today = moment.date()
    horizon = today + timedelta(days=horizon_days)
    found: list[dict] = []

    for window in PEAK_WINDOWS:
        for year in {today.year, horizon.year, today.year + 1}:
            for start, end in window.occurrences(year):
                if end < today or start > horizon:
                    continue
                days_away = (start - today).days
                found.append(
                    {
                        "key": f"{window.key}-{start.isoformat()}",
                        "window": window,
                        "start": start,
                        "end": end,
                        "days_away": days_away,
                        "underway": start <= today <= end,
                        "precision": "peak" if days_away <= PRECISION_HORIZON_DAYS else "season",
                    }
                )

    unique = {entry["key"]: entry for entry in found}
    return _stitch_year_crossings(sorted(unique.values(), key=lambda entry: entry["start"]), today)


def _stitch_year_crossings(entries: list[dict], today: date) -> list[dict]:
    """Rejoin a window that was split at New Year.

    ``occurrences`` cuts a window like 15 Nov - 15 Jan into two calendar-year
    halves so it can be generated per year. Left that way the crane fly-in
    shows up twice in a 365-day view - once ending 31 December and once
    starting 1 January - which reads as two separate events and is simply
    wrong. Halves that touch across the boundary are put back together.
    """
    by_window: dict[str, list[dict]] = {}
    for entry in entries:
        by_window.setdefault(entry["window"].key, []).append(entry)

    merged: list[dict] = []
    for group in by_window.values():
        group.sort(key=lambda entry: entry["start"])
        current = dict(group[0])
        for entry in group[1:]:
            if entry["start"] - current["end"] == timedelta(days=1):
                current["end"] = entry["end"]
                current["underway"] = current["start"] <= today <= current["end"]
                continue
            merged.append(current)
            current = dict(entry)
        merged.append(current)

    for entry in merged:
        entry["days_away"] = (entry["start"] - today).days
        entry["precision"] = "peak" if entry["days_away"] <= PRECISION_HORIZON_DAYS else "season"
        entry["key"] = f"{entry['window'].key}-{entry['start'].isoformat()}"
    return sorted(merged, key=lambda entry: entry["start"])
