"""Static seasonal windows for wildlife and botanical events.

These behaviours are driven by daylight, temperature, and breeding cycles, so
they repeat within a week or two every year. That makes a curated table more
reliable than scraping - and unlike the live APIs, it still works when a
service is down or an endpoint changes shape.

Windows that shift year to year with rainfall (super blooms above all) are
marked ``confirm``: the calendar shows the window so a trip can be planned, but
the text says plainly that it needs confirming closer to the date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .const import (
    CATEGORY_BLOOMS,
    CATEGORY_FOLIAGE,
    CATEGORY_MAMMALS,
    CATEGORY_MARINE,
)


@dataclass(frozen=True)
class SeasonalWindow:
    """A recurring annual window at a fixed zone."""

    key: str
    title: str
    category: str
    zone_id: str
    start: tuple[int, int]
    end: tuple[int, int]
    detail: str
    peak: tuple[int, int] | None = None
    confirm: bool = False

    def occurrences(self, year: int) -> list[tuple[date, date]]:
        """Concrete start/end dates, handling windows that cross New Year."""
        start = date(year, *self.start)
        end = date(year, *self.end)
        if end >= start:
            return [(start, end)]
        # Wraps the year end, so it appears twice in any 12-month view.
        return [
            (date(year, 1, 1), date(year, *self.end)),
            (date(year, *self.start), date(year, 12, 31)),
        ]


SEASONAL_WINDOWS: tuple[SeasonalWindow, ...] = (
    # --- Marine -------------------------------------------------------------
    SeasonalWindow(
        key="gray_whales_south",
        title="Gray whale southbound migration",
        category=CATEGORY_MARINE,
        zone_id="piedras_blancas",
        start=(12, 1),
        end=(2, 28),
        peak=(1, 15),
        detail="Adults cruise 1-3 miles offshore. Shoot from the bluffs with a long lens; "
        "look for blows backlit against low winter sun.",
    ),
    SeasonalWindow(
        key="gray_whales_north",
        title="Gray whale northbound migration (cow/calf pairs)",
        category=CATEGORY_MARINE,
        zone_id="piedras_blancas",
        start=(3, 1),
        end=(5, 31),
        peak=(4, 10),
        detail="Mothers and calves hug the kelp line, often within a few hundred yards of shore - "
        "the closest gray whale photography of the year.",
    ),
    SeasonalWindow(
        key="blue_whales",
        title="Blue whale feeding season",
        category=CATEGORY_MARINE,
        zone_id="channel_islands",
        start=(6, 1),
        end=(10, 31),
        peak=(8, 15),
        detail="The Santa Barbara Channel holds one of the densest blue whale feeding "
        "aggregations on Earth. Boat trip out of Ventura; long lens and fast shutter.",
    ),
    SeasonalWindow(
        key="humpbacks",
        title="Humpback whale feeding",
        category=CATEGORY_MARINE,
        zone_id="big_sur",
        start=(4, 1),
        end=(11, 30),
        peak=(9, 1),
        detail="Lunge feeding and breaching near submarine canyons. Monterey Bay and "
        "Avila are the reliable spots.",
    ),
    SeasonalWindow(
        key="orcas",
        title="Bigg's orca peak (hunting gray whale calves)",
        category=CATEGORY_MARINE,
        zone_id="big_sur",
        start=(4, 15),
        end=(6, 10),
        peak=(5, 10),
        detail="Transient pods intercept northbound gray whale calves in Monterey Bay. "
        "The most dramatic marine mammal behaviour of the year here.",
    ),
    # --- Terrestrial mammals -------------------------------------------------
    SeasonalWindow(
        key="elephant_seal_battles",
        title="Elephant seal bull battles and pupping",
        category=CATEGORY_MAMMALS,
        zone_id="piedras_blancas",
        start=(12, 15),
        end=(2, 28),
        peak=(1, 25),
        detail="Four-thousand-pound alpha bulls fight for beach territory while pups are born "
        "and nursed. Boardwalk access, so a 100-400mm is plenty.",
    ),
    SeasonalWindow(
        key="elephant_seal_molt",
        title="Elephant seal molting haul-out",
        category=CATEGORY_MAMMALS,
        zone_id="piedras_blancas",
        start=(4, 1),
        end=(5, 31),
        detail="Females and juveniles haul out en masse to molt. Less drama than winter, "
        "far more bodies on the sand.",
    ),
    SeasonalWindow(
        key="tule_elk_rut",
        title="Tule elk rut",
        category=CATEGORY_MAMMALS,
        zone_id="carrizo_plain",
        start=(8, 1),
        end=(10, 31),
        peak=(9, 15),
        detail="Bulls bugling, sparring, and holding harems on the open plain. Golden hour "
        "backlight through dust is the shot.",
    ),
    SeasonalWindow(
        key="pronghorn_rut",
        title="Pronghorn rut",
        category=CATEGORY_MAMMALS,
        zone_id="carrizo_plain",
        start=(8, 1),
        end=(9, 30),
        detail="Bucks running harems across open grassland. Long glass and patience; "
        "they spook at distance.",
    ),
    SeasonalWindow(
        key="desert_bighorn_rut",
        title="Desert bighorn rut",
        category=CATEGORY_MAMMALS,
        zone_id="death_valley",
        start=(7, 1),
        end=(10, 31),
        detail="Head-clashing ram battles in extreme heat. Carry far more water than you think, "
        "and shoot the early hours.",
    ),
    SeasonalWindow(
        key="sierra_bighorn_rut",
        title="Sierra bighorn rut",
        category=CATEGORY_MAMMALS,
        zone_id="eastern_sierra",
        start=(10, 1),
        end=(12, 31),
        detail="High-elevation rocky ridges above Lee Vining and the Baxter/Williamson area. "
        "Endangered subspecies - keep well back and use the longest glass you own.",
    ),
    SeasonalWindow(
        key="bear_cubs",
        title="Black bear cub emergence",
        category=CATEGORY_MAMMALS,
        zone_id="yosemite_valley",
        start=(4, 20),
        end=(6, 15),
        detail="Sows emerge with cubs of the year into valley meadows and river drainages. "
        "Also good around Tahoe and in Sequoia.",
    ),
    SeasonalWindow(
        key="bear_hyperphagia",
        title="Black bear autumn hyperphagia",
        category=CATEGORY_MAMMALS,
        zone_id="lake_tahoe",
        start=(9, 1),
        end=(11, 30),
        detail="Bears feeding hard on berries and acorns before denning, often in the open "
        "for hours at a time.",
    ),
    SeasonalWindow(
        key="sea_otter_pups",
        title="Sea otter pupping peak",
        category=CATEGORY_MAMMALS,
        zone_id="piedras_blancas",
        start=(1, 1),
        end=(4, 30),
        detail="Mothers rafting with pups on their chests. Morro Bay harbour and Elkhorn Slough "
        "give the closest, calmest water.",
    ),
    # --- Botanical -----------------------------------------------------------
    SeasonalWindow(
        key="death_valley_bloom",
        title="Death Valley desert bloom",
        category=CATEGORY_BLOOMS,
        zone_id="death_valley",
        start=(2, 1),
        end=(4, 15),
        confirm=True,
        detail="Entirely rainfall dependent - a true super bloom here is roughly a once-a-decade "
        "event. Confirm against current park reports before committing to the drive.",
    ),
    SeasonalWindow(
        key="antelope_valley_poppies",
        title="Antelope Valley poppy bloom",
        category=CATEGORY_BLOOMS,
        zone_id="antelope_valley",
        start=(3, 1),
        end=(4, 30),
        peak=(4, 5),
        confirm=True,
        detail="Sheets of California poppies at the reserve. Petals close in wind and cloud, "
        "so go on a still, sunny day - the opposite of most landscape advice.",
    ),
    SeasonalWindow(
        key="carrizo_bloom",
        title="Carrizo Plain wildflower bloom",
        category=CATEGORY_BLOOMS,
        zone_id="carrizo_plain",
        start=(3, 20),
        end=(5, 10),
        peak=(4, 12),
        confirm=True,
        detail="Valley floor and the Temblor Range in hillside daisies, goldfields, and phacelia. "
        "The closest big bloom to home and the best odds most years.",
    ),
    # --- Fall colour ---------------------------------------------------------
    SeasonalWindow(
        key="bishop_creek_aspens",
        title="Bishop Creek Canyon aspens",
        category=CATEGORY_FOLIAGE,
        zone_id="eastern_sierra",
        start=(9, 25),
        end=(10, 10),
        peak=(10, 2),
        detail="South Lake, North Lake, and Lake Sabrina at 8,500-9,500 ft turn first. "
        "North Lake is the classic - go at dawn for still water reflections.",
    ),
    SeasonalWindow(
        key="june_lake_aspens",
        title="June Lake Loop and Mono Basin colour",
        category=CATEGORY_FOLIAGE,
        zone_id="eastern_sierra",
        start=(10, 5),
        end=(10, 20),
        peak=(10, 12),
        detail="7,000-8,500 ft, so it peaks a week or so after Bishop Creek. Pair it with "
        "Mono Lake tufa at sunrise.",
    ),
    SeasonalWindow(
        key="hope_valley_aspens",
        title="Hope Valley and Carson Pass colour",
        category=CATEGORY_FOLIAGE,
        zone_id="lake_tahoe",
        start=(10, 10),
        end=(10, 25),
        peak=(10, 17),
        detail="The last of the Sierra colour, at around 7,000 ft. Big meadow stands that "
        "photograph well in flat light.",
    ),
)


def active_windows(moment: datetime, horizon_days: int) -> list[dict]:
    """Seasonal windows overlapping the period ahead, sorted by start date."""
    today = moment.date()
    horizon = today + timedelta(days=horizon_days)
    found: list[dict] = []

    for window in SEASONAL_WINDOWS:
        for year in {today.year, horizon.year}:
            for start, end in window.occurrences(year):
                if end < today or start > horizon:
                    continue
                peak = None
                if window.peak:
                    candidate = date(start.year, *window.peak)
                    if start <= candidate <= end:
                        peak = candidate
                found.append(
                    {
                        "key": f"{window.key}-{start.isoformat()}",
                        "title": window.title,
                        "category": window.category,
                        "zone_id": window.zone_id,
                        "start": start,
                        "end": end,
                        "peak": peak,
                        "detail": window.detail,
                        "confirm": window.confirm,
                        "underway": start <= today <= end,
                    }
                )

    unique = {entry["key"]: entry for entry in found}
    return sorted(unique.values(), key=lambda entry: entry["start"])
