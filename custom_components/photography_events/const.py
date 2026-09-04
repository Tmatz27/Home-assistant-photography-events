"""Constants, target zones, and gear profiles for Photography Events."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "photography_events"

CONF_HOME_LATITUDE: Final = "home_latitude"
CONF_HOME_LONGITUDE: Final = "home_longitude"
CONF_MAX_DRIVE_HOURS: Final = "max_drive_hours"
CONF_ALERT_SCORE: Final = "alert_score"
CONF_SUNSET_SCORE: Final = "sunset_score"
CONF_EBIRD_API_KEY: Final = "ebird_api_key"
CONF_GOOGLE_API_KEY: Final = "google_api_key"
CONF_ROUTING_MODE: Final = "routing_mode"
CONF_ENABLE_FIELD_REPORTS: Final = "enable_field_reports"
CONF_ENABLED_CATEGORIES: Final = "enabled_categories"

DEFAULT_MAX_DRIVE_HOURS: Final = 6.0
DEFAULT_ALERT_SCORE: Final = 75
DEFAULT_SUNSET_SCORE: Final = 85

# The coordinator cycle. Every network source carries its own minimum interval
# on top of this, so raising the cadence here cannot make any single service be
# polled harder than its own limit allows.
DEFAULT_UPDATE_MINUTES: Final = 60

# Minimum minutes between calls to each service, enforced per source.
# Open-Meteo, eBird and iNaturalist are all free and all rate limited; the
# hotlines are small volunteer sites that update weekly at best.
MIN_INTERVAL_WEATHER: Final = 60
MIN_INTERVAL_EBIRD: Final = 60
MIN_INTERVAL_INATURALIST: Final = 60
MIN_INTERVAL_ROUTING: Final = 30
MIN_INTERVAL_FIELD_REPORTS: Final = 60 * 24

# Google routing strategy. "auto" tries the current Routes API first and falls
# back to the legacy Distance Matrix API, which is the only combination that
# works across both old and new Google Cloud projects.
ROUTING_AUTO: Final = "auto"
ROUTING_ROUTES: Final = "routes"
ROUTING_LEGACY: Final = "distance_matrix"
ROUTING_OFF: Final = "off"
ROUTING_MODES: Final = (ROUTING_AUTO, ROUTING_ROUTES, ROUTING_LEGACY, ROUTING_OFF)

# Vandenberg Space Force Base, the default origin for drive-time gating.
DEFAULT_HOME: Final = (34.7420, -120.5724)

CATEGORY_ASTRO: Final = "astronomy"
CATEGORY_SUNSET: Final = "sunset"
CATEGORY_MARINE: Final = "marine"
CATEGORY_MAMMALS: Final = "mammals"
CATEGORY_BIRDS: Final = "birds"
CATEGORY_BLOOMS: Final = "blooms"
CATEGORY_FOLIAGE: Final = "foliage"
CATEGORY_RARE: Final = "rare_phenomena"
CATEGORY_PARKS: Final = "parks"

ALL_CATEGORIES: Final = (
    CATEGORY_ASTRO,
    CATEGORY_SUNSET,
    CATEGORY_MARINE,
    CATEGORY_MAMMALS,
    CATEGORY_BIRDS,
    CATEGORY_BLOOMS,
    CATEGORY_FOLIAGE,
    CATEGORY_RARE,
    CATEGORY_PARKS,
)

# Gear profiles keyed by category. Deliberately described by focal length and
# capability rather than by a specific body, so the advice survives a kit
# change; override any of it from the integration options.
GEAR_PROFILES: Final[dict[str, dict[str, str]]] = {
    CATEGORY_ASTRO: {
        "glass": "Ultra-wide fast prime or zoom (16-35mm f/2.8 or faster)",
        "support": "Sturdy tripod, intervalometer, lens heater",
        "settings": "High ISO, 10-20s exposures, manual focus on a bright star",
    },
    CATEGORY_SUNSET: {
        "glass": "Wide for the sweep, 70-200mm to compress layers and isolate colour",
        "support": "Tripod, circular polariser, graduated ND",
        "settings": "Bracket exposures; the best colour often lands 10-20 min after the sun is down",
    },
    CATEGORY_MARINE: {
        "glass": "Super-telephoto (100-400mm, 200-600mm)",
        "support": "Monopod or gimbal, circular polariser to cut sea glare",
        "settings": "1/2000s or faster for breaches, continuous AF, high burst",
    },
    CATEGORY_MAMMALS: {
        "glass": "Super-telephoto (400mm+), plus a wide for habitat context",
        "support": "Monopod or gimbal head",
        "settings": "Fast shutter for sparring and rutting behaviour, animal-eye AF",
    },
    CATEGORY_BIRDS: {
        "glass": "Super-telephoto (400mm+) with good close focus",
        "support": "Monopod, beanbag for car-window work",
        "settings": "1/2000s+, continuous AF, high burst",
    },
    CATEGORY_BLOOMS: {
        "glass": "16-35mm for sweeping fields, 70-200mm to compress hillsides, macro for single blossoms",
        "support": "Circular polariser, ND filters, extension tubes",
        "settings": "Shoot early or late; midday flattens the colour",
    },
    CATEGORY_FOLIAGE: {
        "glass": "70-200mm to compress aspen stands, wide for canyon context",
        "support": "Circular polariser to saturate leaves and cut glare",
        "settings": "Backlight the leaves; overcast is fine and often better",
    },
    CATEGORY_RARE: {
        "glass": "Whatever the phenomenon needs - these range from 24mm at night to 600mm on a roost",
        "support": "Per event; most of these are tripod or gimbal work",
        "settings": "Read the event's own notes - these are one-shot-a-year situations",
    },
    CATEGORY_PARKS: {
        "glass": "Wide for the landscape, 70-200mm for detail, fast prime if you will be out after dark",
        "support": "Tripod, circular polariser, spare batteries for the cold",
        "settings": "Shoot the edges of the day; most of these are brutal at midday",
    },
}

# Fixed target zones. drive_hours is the free-flowing baseline from the default
# home location - the zones and the origin are both fixed, so this only changes
# with traffic and closures, which is what the optional routing API adjusts.
# bortle is an approximate dark-sky class used to rank astro targets.
TARGET_ZONES: Final[tuple[dict, ...]] = (
    {
        "id": "carrizo_plain",
        "name": "Carrizo Plain",
        "latitude": 35.1914,
        "longitude": -119.7929,
        "drive_hours": 2.0,
        "bortle": 2,
        "specialties": (CATEGORY_BLOOMS, CATEGORY_MAMMALS, CATEGORY_ASTRO),
    },
    {
        "id": "piedras_blancas",
        "name": "Piedras Blancas (San Simeon)",
        "latitude": 35.6664,
        "longitude": -121.2571,
        "drive_hours": 1.5,
        "bortle": 3,
        "specialties": (CATEGORY_MAMMALS, CATEGORY_MARINE, CATEGORY_SUNSET),
    },
    {
        "id": "channel_islands",
        "name": "Channel Islands (Ventura Harbor)",
        "latitude": 34.2486,
        "longitude": -119.2642,
        "drive_hours": 1.5,
        "bortle": 4,
        "specialties": (CATEGORY_MARINE, CATEGORY_BIRDS, CATEGORY_BLOOMS),
    },
    {
        "id": "big_sur",
        "name": "Big Sur Coastline",
        "latitude": 36.3715,
        "longitude": -121.9018,
        "drive_hours": 3.0,
        "bortle": 3,
        "specialties": (CATEGORY_SUNSET, CATEGORY_MARINE),
    },
    {
        "id": "antelope_valley",
        "name": "Antelope Valley",
        "latitude": 34.7258,
        "longitude": -118.3972,
        "drive_hours": 3.0,
        "bortle": 4,
        "specialties": (CATEGORY_BLOOMS, CATEGORY_ASTRO),
    },
    {
        "id": "pinnacles",
        "name": "Pinnacles National Park",
        "latitude": 36.4906,
        "longitude": -121.1825,
        "drive_hours": 3.5,
        "bortle": 3,
        "specialties": (CATEGORY_BIRDS, CATEGORY_ASTRO),
    },
    {
        "id": "sequoia_kings",
        "name": "Sequoia & Kings Canyon",
        "latitude": 36.5647,
        "longitude": -118.7734,
        "drive_hours": 4.5,
        "bortle": 2,
        "specialties": (CATEGORY_MAMMALS, CATEGORY_ASTRO, CATEGORY_FOLIAGE),
    },
    {
        "id": "santa_cruz_redwoods",
        "name": "Santa Cruz Mountains Redwoods",
        "latitude": 37.1716,
        "longitude": -122.2222,
        "drive_hours": 4.0,
        "bortle": 5,
        "specialties": (CATEGORY_FOLIAGE,),
    },
    {
        "id": "death_valley",
        "name": "Death Valley",
        "latitude": 36.5054,
        "longitude": -117.0794,
        "drive_hours": 6.0,
        "bortle": 1,
        "specialties": (CATEGORY_ASTRO, CATEGORY_BLOOMS, CATEGORY_MAMMALS),
    },
    {
        "id": "yosemite_valley",
        "name": "Yosemite Valley",
        "latitude": 37.7456,
        "longitude": -119.5936,
        "drive_hours": 6.0,
        "bortle": 3,
        "specialties": (CATEGORY_MAMMALS, CATEGORY_ASTRO, CATEGORY_FOLIAGE),
    },
    {
        "id": "eastern_sierra",
        "name": "Eastern Sierra (Bishop / June Lake)",
        "latitude": 37.3614,
        "longitude": -118.3997,
        "drive_hours": 6.0,
        "bortle": 2,
        "specialties": (CATEGORY_FOLIAGE, CATEGORY_ASTRO, CATEGORY_MAMMALS),
    },
    {
        "id": "lake_tahoe",
        "name": "Lake Tahoe Basin",
        "latitude": 39.0968,
        "longitude": -120.0324,
        "drive_hours": 6.0,
        "bortle": 4,
        "specialties": (CATEGORY_MAMMALS, CATEGORY_FOLIAGE, CATEGORY_SUNSET),
    },
)

ZONES_BY_ID: Final = {zone["id"]: zone for zone in TARGET_ZONES}

# eBird region codes covering the drivable zones.
EBIRD_REGIONS: Final = ("US-CA-083", "US-CA-079", "US-CA-053", "US-CA-029")

OPEN_METEO_URL: Final = "https://api.open-meteo.com/v1/forecast"
EBIRD_NOTABLE_URL: Final = "https://api.ebird.org/v2/data/obs/{region}/recent/notable"
INATURALIST_URL: Final = "https://api.inaturalist.org/v1/observations"

# Marine species tracked through iNaturalist, keyed by taxon name.
MARINE_TAXA: Final = {
    "Orcinus orca": "Orca",
    "Balaenoptera musculus": "Blue whale",
    "Balaenoptera physalus": "Fin whale",
    "Megaptera novaeangliae": "Humpback whale",
}
