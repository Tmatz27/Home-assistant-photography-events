"""California national parks and monuments, as a trip-planning layer.

Unlike everything else here, these are not events - a park does not happen. What
each entry carries is a *season*: the months the place is worth the drive, and
the months it is merely good. Death Valley in January and Death Valley in July
are different propositions, and the calendar should say so a year out.

Two properties separate parks from every other category:

- **They are never drop-everything.** A park is a trip you plan, not a sky you
  chase, so park windows stay out of the action window entirely and score below
  the alert threshold by construction.
- **They ignore the drive-time gate.** Half of this list is further away than
  any sane day trip, and gating Redwood out at six hours would defeat the point
  of listing it - you go there for a long weekend, not an evening.

Drive times and distances are the ones supplied for this specific origin
(Vandenberg Space Force Base) rather than anything computed, so they already
account for the routes actually taken. Coordinates are approximate main-area or
visitor-centre positions, good enough to place a park on a map and to hand to a
router, not a trailhead.

Dog rules are recorded because they decide whether a trip happens at all: three
of these ban dogs outright and most of the rest allow them only on pavement,
which is worth knowing before a five-hour drive rather than at the gate.
"""

from __future__ import annotations

import calendar as calendar_module
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# Dog access classes, in the order a trip-planner cares about them.
DOGS_FULL = "full"
DOGS_LIMITED = "limited"
DOGS_NONE = "none"


@dataclass(frozen=True)
class Park:
    """One park or monument, its seasons, and its dog rules."""

    key: str
    name: str
    latitude: float
    longitude: float
    miles: int
    drive_hours: float
    dogs: str
    dog_label: str
    dog_detail: str
    optimal: tuple[tuple[int, int], ...]
    good: tuple[tuple[int, int], ...] = ()

    @property
    def drive_label(self) -> str:
        return f"{self.miles} mi, about {self.drive_hours:g} h"


# Ordered by drive time from Vandenberg, closest first.
#
# Deliberately short. Monuments without a visitor centre or a real photographic
# draw were cut - listing every BLM and USFS unit in southern California padded
# the calendar with places nobody was going to drive to, and a planning list you
# scroll past is worse than a shorter one you read.
PARKS: tuple[Park, ...] = (
    Park(
        key="channel_islands_np",
        name="Channel Islands NP",
        latitude=34.2486,
        longitude=-119.2642,
        miles=85,
        drive_hours=1.5,
        dogs=DOGS_NONE,
        dog_label="Banned on the islands",
        dog_detail=(
            "Strictly prohibited on all islands to protect the endemic island foxes. "
            "Dogs are allowed only on the mainland visitor centre grounds in Ventura."
        ),
        optimal=((9, 10),),
        good=((3, 5), (6, 8)),
    ),
    Park(
        key="carrizo_plain_nm",
        name="Carrizo Plain NM",
        latitude=35.1914,
        longitude=-119.7929,
        miles=95,
        drive_hours=2.0,
        dogs=DOGS_FULL,
        dog_label="Full trail access",
        dog_detail="BLM managed: dogs on all dirt roads, trails and dispersed campsites on a 6 ft leash.",
        optimal=((3, 4),),
        good=((5, 5),),
    ),
    Park(
        key="pinnacles_np",
        name="Pinnacles NP",
        latitude=36.4906,
        longitude=-121.1825,
        miles=145,
        drive_hours=2.5,
        dogs=DOGS_LIMITED,
        dog_label="Paved and campgrounds only",
        dog_detail="Parking lots, picnic areas and paved campground roads. Prohibited on all trails and in the caves.",
        optimal=((3, 5),),
        good=((1, 2), (10, 12)),
    ),
    Park(
        key="sequoia_np",
        name="Sequoia NP",
        latitude=36.5647,
        longitude=-118.7734,
        miles=235,
        drive_hours=4.0,
        dogs=DOGS_LIMITED,
        dog_label="Paved and campgrounds only",
        dog_detail="Within 100 ft of roads, paved parking and campgrounds. Prohibited on all dirt trails.",
        optimal=((6, 8),),
        good=((5, 5), (9, 10)),
    ),
    Park(
        key="kings_canyon_np",
        name="Kings Canyon NP",
        latitude=36.7876,
        longitude=-118.6690,
        miles=245,
        drive_hours=4.25,
        dogs=DOGS_LIMITED,
        dog_label="Paved and campgrounds only",
        dog_detail="Paved roads and developed campgrounds. Prohibited on all trails, including the Cedar Grove canyon floor.",
        optimal=((6, 8),),
        good=((5, 5), (9, 10)),
    ),
    Park(
        key="giant_sequoia_nm",
        name="Giant Sequoia NM",
        latitude=35.9236,
        longitude=-118.5847,
        miles=240,
        drive_hours=4.25,
        dogs=DOGS_FULL,
        dog_label="Full trail access",
        dog_detail="USFS managed: dogs on all trails including the Trail of 100 Giants, and in campgrounds, on a 6 ft leash.",
        optimal=((6, 8),),
        good=((9, 10),),
    ),
    Park(
        key="joshua_tree_np",
        name="Joshua Tree NP",
        latitude=33.8734,
        longitude=-115.9010,
        miles=275,
        drive_hours=4.5,
        dogs=DOGS_LIMITED,
        dog_label="Roads and campgrounds only",
        dog_detail="Unpaved backcountry vehicle roads, campgrounds and within 100 ft of roads. Prohibited on all trails.",
        optimal=((2, 4),),
        good=((1, 1), (5, 5), (10, 12)),
    ),
    Park(
        key="yosemite_np",
        name="Yosemite NP",
        latitude=37.7456,
        longitude=-119.5936,
        miles=310,
        drive_hours=5.5,
        dogs=DOGS_LIMITED,
        dog_label="Paved paths only",
        dog_detail=(
            "Fully paved roads, sidewalks, Valley bicycle paths and developed campgrounds. "
            "Prohibited on all dirt trails, unpaved paths and in wilderness."
        ),
        optimal=((5, 5), (9, 10)),
        good=((6, 8),),
    ),
    Park(
        key="death_valley_np",
        name="Death Valley NP",
        latitude=36.5054,
        longitude=-117.0794,
        miles=340,
        drive_hours=6.0,
        dogs=DOGS_LIMITED,
        dog_label="Roads and campgrounds only",
        dog_detail="Developed roads, backcountry dirt roads and campgrounds. Prohibited on single-track trails and off-road wilderness.",
        optimal=((1, 2),),
        good=((3, 3), (11, 12)),
    ),
    Park(
        key="devils_postpile_nm",
        name="Devils Postpile NM",
        latitude=37.6300,
        longitude=-119.0850,
        miles=350,
        drive_hours=6.5,
        dogs=DOGS_FULL,
        dog_label="Full trail access",
        dog_detail="Exceptionally pet-friendly: all trails on a 6 ft leash, and dogs are allowed on the mandatory Reds Meadow shuttle.",
        optimal=((7, 8),),
        good=((9, 9),),
    ),
)

PARKS_BY_KEY = {park.key: park for park in PARKS}


def _month_range(year: int, months: tuple[int, int]) -> tuple[date, date]:
    first, last = months
    return (
        date(year, first, 1),
        date(year, last, calendar_module.monthrange(year, last)[1]),
    )


def active_windows(moment: datetime, horizon_days: int) -> list[dict]:
    """Park seasons overlapping the period ahead, sorted by start date.

    A 365-day horizon crosses a year boundary, so each season is generated for
    both the current year and the horizon's year and then deduplicated - the
    same approach the seasonal wildlife windows use, for the same reason.
    """
    today = moment.date()
    horizon = today + timedelta(days=horizon_days)
    found: list[dict] = []

    for park in PARKS:
        for tier, ranges in (("optimal", park.optimal), ("good", park.good)):
            for months in ranges:
                for year in {today.year, horizon.year}:
                    start, end = _month_range(year, months)
                    if end < today or start > horizon:
                        continue
                    found.append(
                        {
                            "key": f"park-{park.key}-{tier}-{start.isoformat()}",
                            "park": park,
                            "tier": tier,
                            "start": start,
                            "end": end,
                            "underway": start <= today <= end,
                        }
                    )

    unique = {entry["key"]: entry for entry in found}
    return sorted(unique.values(), key=lambda entry: (entry["start"], entry["park"].drive_hours))
