"""What to take, chosen from the kit the photographer actually owns.

The old gear advice was written for nobody in particular - "super-telephoto
(400mm+)", "fast prime or zoom" - which is shopping advice, not packing advice.
This integration is built for one photographer with one bag, so every
recommendation here names a lens in that bag, and says what to leave behind.

Two pieces of reasoning are load-bearing and easy to get wrong:

- **More reach is not automatically better.** The 2x teleconverter costs two
  stops on the 200-600 (f/6.3 becomes f/12.6), slows autofocus, magnifies heat
  shimmer and camera shake, and pushes the lens past the diffraction point of a
  61 MP sensor. The A7R IV can instead crop to APS-C and still deliver about
  26 MP. So the teleconverter is always *optional*, offered only where extreme
  compression is the photograph (a large Moon on the horizon) and light allows,
  and explicitly skipped for moving subjects in dim light.
- **The drone is guilty until proven innocent.** National parks prohibit it
  (NPS Policy Memorandum 14-05 under 36 CFR 1.5), wildlife refuges prohibit it
  (50 CFR 27.34 and 27.51), flying near marine mammals or roosting wildlife is
  harassment, and Vandenberg sits under restricted military airspace. A drone
  is only ever suggested where the land status allows it *and* the subject is
  not wildlife *and* the wind is inside the DJI Mini 3's published 10.7 m/s
  wind resistance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

# --- The bag ---------------------------------------------------------------
BODY = "Sony α7R IV (61 MP full frame)"
WIDE = "Sony FE 16-35mm f/2.8 GM"
MID = "Sony FE 70-200mm f/2.8 GM OSS II"
LONG = "Sony FE 200-600mm f/5.6-6.3 G OSS"
TC2X = "Sony FE 2x Teleconverter"
DRONE = "DJI Mini 3"
POCKET = "DJI Osmo Pocket 3"

OWNED = (BODY, WIDE, MID, LONG, TC2X, DRONE, POCKET)

# DJI's published maximum wind speed resistance for the Mini 3 (Level 5).
DRONE_MAX_WIND_MS = 10.7

# Why a 2x is usually the wrong answer, stated once and reused.
TC_COST = (
    "The 2x costs two stops (f/12.6 on the 200-600), slows autofocus and "
    "magnifies shimmer and shake; an APS-C crop of the 61 MP file keeps about 26 MP."
)

# --- Land status decides whether the drone is even a question --------------
LAND_NPS = "nps"
LAND_REFUGE = "usfws_refuge"
LAND_STATE_PARK = "state_park"
LAND_BLM = "blm"
LAND_USFS = "usfs"
LAND_MARINE = "marine_wildlife"
LAND_MILITARY = "military_airspace"
LAND_CITY = "city_beach"
LAND_UNKNOWN = "unknown"

DRONE_RULES = {
    LAND_NPS: ("prohibited", "Prohibited: drones may not launch, land or operate in national parks (NPS PM 14-05, 36 CFR 1.5)."),
    LAND_REFUGE: ("prohibited", "Prohibited on national wildlife refuges (50 CFR 27.34, 27.51)."),
    LAND_MARINE: ("not_appropriate", "Not appropriate: flying over marine mammals or wildlife colonies risks harassment under the MMPA."),
    LAND_MILITARY: ("prohibited", "Prohibited: Vandenberg SFB lies under restricted military airspace."),
    LAND_STATE_PARK: ("check", "Check first: many California State Parks restrict drones; confirm the unit's current rule and any TFR."),
    LAND_CITY: ("check", "Check first: local ordinance and any temporary flight restriction apply."),
    LAND_BLM: ("allowed_with_limits", "Possible under FAA rules on open BLM land; never over wildlife or designated wilderness."),
    LAND_USFS: ("allowed_with_limits", "Possible under FAA rules on National Forest land outside wilderness; check TFRs."),
    LAND_UNKNOWN: ("check", "Land status not verified; do not assume a drone is allowed."),
}


@dataclass
class GearPlan:
    """A packing decision, not a catalogue."""

    take: str
    optional: list[str] = field(default_factory=list)
    skip: list[str] = field(default_factory=list)
    start: str = ""
    support: str = ""
    technique: str = ""
    video: str = ""
    drone: str = ""
    drone_status: str = "not_recommended"

    def as_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value not in ("", [], None)}


# --- Shot profiles -----------------------------------------------------------
# Keyed by what the photograph physically needs: subject distance, motion,
# light and whether the frame is about the subject or its setting.
PROFILES: dict[str, dict] = {
    "sunset_local": dict(
        take=WIDE, optional=[f"{MID} to compress lit cloud layers"],
        skip=[f"{TC2X}: nothing in a sky this wide needs it"],
        start="ISO 100, f/8-f/11, bracket 3 frames at ±1.5 EV; colour often peaks 10-20 min after sunset.",
        support="Tripod", technique="Bracket through the afterglow; keep shooting after the sun is down.",
        video=f"{POCKET} for a time-lapse of the colour building",
    ),
    "astro_wide": dict(
        take=WIDE, skip=[MID, LONG, TC2X],
        start="16mm f/2.8, ISO 3200-6400, 15-20 s; focus manually on a bright star.",
        support="Sturdy tripod, remote release, lens heater against dew",
        technique="Stack several frames for noise; shoot a separate blue-hour foreground.",
    ),
    "meteor": dict(
        take=WIDE, skip=[MID, LONG, TC2X],
        start="16mm f/2.8, ISO 3200, 15-20 s continuous intervals for hours.",
        support="Tripod, intervalometer, spare batteries (cold drains them)",
        technique="Point 30-45° from the radiant, not at it; composite the hits later.",
    ),
    "moon_horizon": dict(
        take=LONG, optional=[f"{TC2X} only if the air is clear and steady and you want extreme compression (1200mm)", f"{MID} for Moon plus landscape"],
        start="Meter the Moon: roughly ISO 400, f/8-f/11, 1/250 s at moonrise; blend with a longer landscape frame if needed.",
        support="Tripod with the lens foot; remote release; turn stabilisation off on a tripod",
        technique="Be set up before moonrise at the azimuth given; the first few degrees carry the colour and the size illusion.",
    ),
    "wildlife_dawn": dict(
        take=LONG, optional=[f"{MID} for animals in their landscape"],
        skip=[f"{TC2X}: dawn light and moving animals need shutter speed more than reach. {TC_COST}"],
        start="1/1000 s or faster, f/6.3, auto ISO; animal-eye AF, continuous.",
        support="Beanbag on the car window or a gimbal head; stay in or beside the vehicle",
        technique="Burst for sparring; backlit breath and dust at first light is the frame.",
        video=f"{POCKET} for bugling audio",
    ),
    "wildlife_colony": dict(
        take=LONG, optional=[f"{MID} for animals plus the beach or rookery for context"],
        skip=[f"{TC2X}: the viewpoints are close enough; crop instead. {TC_COST}"],
        start="1/1000 s for fights, 1/250 s for resting pups; f/8 for two animals in focus.",
        support="Handheld from the viewing rail, or a monopod",
        technique="Burst for fights; wait for eye contact between mother and pup.",
        video=f"{POCKET} for sound and behaviour clips",
    ),
    "birds_in_flight_low_light": dict(
        take=LONG, optional=[f"{MID} for the flock against the sunset sky"],
        skip=[f"{TC2X}: at dusk shutter speed and autofocus matter more than reach. {TC_COST}"],
        start="1/2000 s while the light allows, then accept motion blur or pan at 1/60 s; auto ISO with a high ceiling.",
        support="Handheld or gimbal", technique="Silhouette the lines against the brightest sky; track, do not chase.",
    ),
    "raptor": dict(
        take=LONG, optional=[f"{TC2X} only for a perched bird in good light"],
        skip=[f"{TC2X} for birds in flight: autofocus and shutter speed suffer. {TC_COST}"],
        start="1/3200 s for flight, f/6.3-f/8, auto ISO; wide-area tracking AF.",
        support="Handheld for flight, monopod for perched birds",
        technique="Shoot on the thermals late morning or at the roost at dusk; keep the sun behind you.",
    ),
    "marine_boat": dict(
        take=MID, optional=[f"{LONG} for distant blows and breaches"],
        skip=[f"{TC2X}: a moving deck makes it unusable", "Tripod: useless on a boat"],
        start="1/2000 s, f/5.6-f/8, auto ISO; continuous AF, high burst.",
        support="Handheld", technique="Shoot wider than instinct says; the animal is often closer than it looks.",
        video=f"{POCKET} for deck-level video",
    ),
    "marine_shore": dict(
        take=LONG, optional=[f"{MID} when bait balls come close to the pier"],
        skip=[f"{TC2X}: heat shimmer over water softens it. {TC_COST}"],
        start="1/2000 s, f/7.1, auto ISO; pre-focus on the diving birds.",
        support="Monopod", technique="Watch the gulls and pelicans; they mark the lunge seconds ahead.",
    ),
    "landscape_colour": dict(
        take=MID, optional=[f"{WIDE} for canyon or valley context"],
        skip=[TC2X],
        start="f/8-f/11, ISO 100; polariser to saturate leaves and cut glare.",
        support="Tripod", technique="Backlight the colour; still dawn water for reflections.",
    ),
    "waterfall_night": dict(
        take=WIDE, skip=[LONG, TC2X],
        start="16-24mm, f/2.8, ISO 1600-3200, 10-20 s; protect the front element from spray.",
        support="Sturdy tripod, remote release, lens cloth", technique="Frame the bow opposite the Moon; check the dated viewpoint timetable.",
    ),
    "firefall": dict(
        take=MID, optional=[f"{LONG} to isolate the glowing streak"],
        skip=[f"{TC2X}: ten minutes of light, no time to fumble"],
        start="Spot-meter the lit water; underexpose 1 stop to hold the orange.",
        support="Tripod, remote release", technique="Be in position an hour early; shoot continuously through the last light.",
    ),
    "storm_surf": dict(
        take=MID, optional=[f"{LONG} for isolated breaking lips from a safe distance", f"{WIDE} only from high, set-back ground"],
        skip=[f"{TC2X}: spray and haze kill the detail"],
        start="1/1000 s to freeze spray, or 1/4 s for motion; f/8.",
        support="Tripod with rain cover", technique="Stay high and far back; never on beaches, rocks or jetties.",
    ),
    "eclipse_lunar": dict(
        take=LONG, optional=[f"{TC2X} on a steady tripod for a frame-filling Moon", f"{WIDE} for a composite over the landscape"],
        start="Partial phases around 1/250 s at f/8 ISO 400; totality needs about 1-4 s at ISO 1600 - bracket widely.",
        support="Tripod", technique="Exposure changes by many stops; bracket through every phase.",
    ),
    "aurora": dict(
        take=WIDE, skip=[LONG, TC2X],
        start="16mm f/2.8, ISO 3200, 5-15 s; low-latitude aurora is faint and red, often only visible to the camera.",
        support="Tripod", technique="Aim north over a dark horizon.",
    ),
    "tidepool": dict(
        take=WIDE, optional=[f"{MID} close focus for individual animals"],
        skip=[LONG, TC2X],
        start="f/11, polariser to see through the water surface.",
        support="Handheld; low tripod for long exposures", technique="Arrive an hour before low water; walk only on bare rock.",
    ),
    "monarch_cluster": dict(
        take=MID, optional=[f"{LONG} for clusters high in the eucalyptus"],
        skip=[f"{TC2X}: under the canopy the light is too low. {TC_COST}"],
        start="f/5.6-f/8 for depth through the cluster, 1/250 s, auto ISO.",
        support="Monopod on the boardwalk", technique="Backlight the clusters so wings separate from the leaves; cold mornings keep them still.",
    ),
    "night_beach": dict(
        take=WIDE, skip=[LONG, TC2X],
        start="16mm f/2.8, ISO 3200-6400, 2-8 s.",
        support="Tripod above the wash line", technique="Red light only; no white light near fish or glowing surf.",
    ),
    "general_wildlife": dict(
        take=LONG, optional=[MID],
        skip=[f"{TC2X} unless the subject is still and the light is strong. {TC_COST}"],
        start="1/1000 s, f/6.3-f/8, auto ISO.", support="Monopod",
    ),
    "landscape": dict(take=WIDE, optional=[MID], skip=[TC2X], start="f/8-f/11, ISO 100.", support="Tripod"),
}


def recommend(profile: str, *, land: str = LAND_UNKNOWN, wildlife: bool = False,
              wind_ms: float | None = None, drone_useful: bool = False) -> GearPlan:
    """A packing plan for one opportunity, with an honest drone verdict."""
    spec = PROFILES.get(profile) or PROFILES["landscape"]
    plan = GearPlan(**{key: (list(value) if isinstance(value, list) else value) for key, value in spec.items()})
    plan.drone_status, plan.drone = drone_verdict(land, wildlife=wildlife, wind_ms=wind_ms, useful=drone_useful)
    return plan


def drone_verdict(land: str, *, wildlife: bool = False, wind_ms: float | None = None,
                  useful: bool = False) -> tuple[str, str]:
    """Whether the Mini 3 belongs in this plan, and why not when it does not."""
    status, text = DRONE_RULES.get(land, DRONE_RULES[LAND_UNKNOWN])
    if status == "prohibited":
        return status, f"{DRONE}: {text}"
    if wildlife:
        return "not_appropriate", f"{DRONE}: not appropriate - wildlife is the subject, and a drone disturbs it."
    if wind_ms is not None and wind_ms > DRONE_MAX_WIND_MS:
        return "not_safe", f"{DRONE}: not safe - forecast wind {wind_ms:.0f} m/s exceeds its {DRONE_MAX_WIND_MS} m/s rating."
    if not useful:
        return "not_recommended", f"{DRONE}: not needed for this subject."
    return status, f"{DRONE}: {text}" + ("" if wind_ms is not None else f" Wind not forecast here; the Mini 3 is rated to {DRONE_MAX_WIND_MS} m/s.")


def uses_only_owned(plan: GearPlan) -> bool:
    """Whether every lens named in take/optional is one that is in the bag."""
    named = [plan.take, *plan.optional]
    return all(any(item in text for item in OWNED) for text in named)
