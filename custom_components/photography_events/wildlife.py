"""Live wildlife sightings from eBird and iNaturalist.

Request building and payload parsing only - no Home Assistant, no network, no
scoring policy that cannot be exercised from a test. The coordinator owns the
HTTP; everything here is a pure function over the decoded JSON.

Two things drive the design:

*Neither API knows about the target zones, and they should not have to.* The
zones are destinations you choose to drive to; animals turn up where they like,
and the most valuable thing this can tell you is about the vagrant twenty
minutes down the road that no zone covers. So a sighting is placed by its own
coordinates - drive time estimated from home, calibrated against the zone
table's known drive times - and a zone is named only when one is genuinely
nearby, as context rather than as the location.

*A single report is weak evidence; a repeated one is strong.* Vagrant birds
leave and whales move, so what matters is not that something was seen but that
it is still being seen. Reports are therefore collapsed per species and
location, and the number of independent observers is scored directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .const import (
    CATEGORY_BIRDS,
    CATEGORY_MARINE,
    DEFAULT_HOME,
    EBIRD_NOTABLE_URL,
    MARINE_TAXA,
    TARGET_ZONES,
)

EBIRD_API_KEY_HEADER = "x-ebirdapitoken"

# iNaturalist asks API users to identify themselves so they can contact you
# before blocking a misbehaving client.
USER_AGENT = "home-assistant-photography-events (+https://github.com/Tmatz27/Home-assistant-photography-events)"

# How far back each source is asked to look. Longer than the scoring horizon on
# purpose: an older report is not an alert, but it is the evidence that a bird
# is staked out rather than a one-off flyover.
EBIRD_LOOKBACK_DAYS = 5
INATURALIST_LOOKBACK_DAYS = 7

# Close enough to a zone that naming the zone helps you place the sighting.
# Beyond it the reported place name stands on its own.
NEARBY_ZONE_KM = 60.0

# Sightings this stale are dropped outright - past this point you are not
# chasing an animal, you are reading history.
MAX_SIGHTING_AGE_HOURS = 96

EARTH_RADIUS_KM = 6371.0


@dataclass
class Sighting:
    """One or more reports of one species at one place."""

    species: str
    scientific_name: str
    place: str
    latitude: float
    longitude: float
    latest: datetime
    earliest: datetime
    source: str
    category: str
    reports: int = 1
    count: int | None = None
    confirmed: bool = False
    url: str | None = None
    observers: list[str] = field(default_factory=list)

    @property
    def cluster_key(self) -> tuple[str, str]:
        return (self.scientific_name or self.species, self.place)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two decimal-degree points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def nearest_zone(
    latitude: float,
    longitude: float,
    zones: tuple[dict, ...] = TARGET_ZONES,
    max_km: float = NEARBY_ZONE_KM,
) -> tuple[dict, float] | None:
    """The closest target zone, or None when nothing is close enough."""
    best: tuple[dict, float] | None = None
    for zone in zones:
        distance = haversine_km(latitude, longitude, zone["latitude"], zone["longitude"])
        if best is None or distance < best[1]:
            best = (zone, distance)
    if best is None or best[1] > max_km:
        return None
    return best


def _median_effective_speed(home: tuple[float, float] = DEFAULT_HOME) -> float:
    """Calibrate straight-line-to-drive-time against the known zone drive times.

    The zone table pairs twelve destinations with their real drive times, which
    is a free calibration set: dividing each by its great-circle distance gives
    an effective road speed, and the median of those is a far better estimator
    than any winding factor picked out of the air.

    Its spread is honest about what it can do - the twelve zones run from 43 to
    88 km/h effective, so the median predicts most of them within about half an
    hour and Lake Tahoe by an hour and a half. Good enough to answer "can I be
    there before dark", not good enough to quote to the minute, which is why
    ``describe_drive`` rounds it coarsely.
    """
    speeds = sorted(
        haversine_km(home[0], home[1], zone["latitude"], zone["longitude"]) / zone["drive_hours"]
        for zone in TARGET_ZONES
        if zone.get("drive_hours")
    )
    if not speeds:
        return 65.0
    middle = len(speeds) // 2
    if len(speeds) % 2:
        return speeds[middle]
    return (speeds[middle - 1] + speeds[middle]) / 2


MEDIAN_EFFECTIVE_SPEED_KMH = _median_effective_speed()


def estimate_drive_hours(
    latitude: float,
    longitude: float,
    home: tuple[float, float] = DEFAULT_HOME,
) -> float:
    """Roughly how long it takes to reach a point that is not a target zone.

    Rare birds and whales turn up wherever they like, and the most useful
    sighting this integration can report is the one twenty minutes away that no
    zone covers. Zones exist to answer "how far is the drive"; for a sighting
    that question is answerable directly from its coordinates, so it is.
    """
    distance = haversine_km(home[0], home[1], latitude, longitude)
    return max(0.25, distance / MEDIAN_EFFECTIVE_SPEED_KMH)


def describe_drive(hours: float) -> str:
    """Round hard enough that the number cannot be mistaken for a routed time."""
    if hours < 1:
        return f"about {int(round(hours * 60 / 15) * 15)} min away"
    return f"roughly {round(hours * 2) / 2:g} h away"


# --- eBird ------------------------------------------------------------------


def build_ebird_url(region: str) -> str:
    return EBIRD_NOTABLE_URL.format(region=region)


def build_ebird_params(back_days: int = EBIRD_LOOKBACK_DAYS, max_results: int = 100) -> dict:
    """`detail=full` is what carries locName and the review flags."""
    return {"back": back_days, "detail": "full", "maxResults": max_results}


def build_ebird_headers(api_key: str) -> dict:
    return {EBIRD_API_KEY_HEADER: api_key, "User-Agent": USER_AGENT}


def parse_ebird(payload, tz: timezone | None = None) -> list[Sighting]:
    """Turn a notable-observations payload into sightings.

    eBird reports ``obsDt`` in the *observation's* local time with no offset, so
    the caller passes the timezone the regions sit in. Getting this wrong only
    ever shifts a sighting by hours, but hours are exactly the resolution the
    recency score works at.
    """
    if not isinstance(payload, list):
        return []

    zone = tz or timezone.utc
    found: list[Sighting] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        latitude = _as_float(entry.get("lat"))
        longitude = _as_float(entry.get("lng"))
        observed = _parse_ebird_time(entry.get("obsDt"), zone)
        species = entry.get("comName") or entry.get("sciName")
        if latitude is None or longitude is None or observed is None or not species:
            continue

        # obsValid is eBird's own filter flag and obsReviewed says a regional
        # editor has looked. Only the pair together means "a human confirmed
        # this", which is the distinction that matters before a two-hour drive.
        confirmed = bool(entry.get("obsValid")) and bool(entry.get("obsReviewed"))
        sub_id = entry.get("subId")

        found.append(
            Sighting(
                species=species,
                scientific_name=entry.get("sciName") or "",
                place=entry.get("locName") or "Unnamed location",
                latitude=latitude,
                longitude=longitude,
                latest=observed,
                earliest=observed,
                source="eBird",
                category=CATEGORY_BIRDS,
                count=_as_int(entry.get("howMany")),
                confirmed=confirmed,
                url=f"https://ebird.org/checklist/{sub_id}" if sub_id else None,
                observers=[sub_id] if sub_id else [],
            )
        )
    return found


def _parse_ebird_time(value, tz: timezone) -> datetime | None:
    """eBird sends `YYYY-MM-DD HH:MM`, or just the date when no time was given."""
    if not isinstance(value, str):
        return None
    for pattern in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), pattern).replace(tzinfo=tz)
        except ValueError:
            continue
    return None


# --- iNaturalist ------------------------------------------------------------


def marine_bounding_box(margin_deg: float = 0.6) -> dict:
    """A single box covering every zone that could plausibly hold a whale.

    One bounded request per species beats one request per species per zone, and
    deriving the box from the zone table means it keeps up with the zones
    instead of drifting out of date as a hardcoded rectangle would.
    """
    coastal = [zone for zone in TARGET_ZONES if CATEGORY_MARINE in zone["specialties"]] or list(TARGET_ZONES)
    lats = [zone["latitude"] for zone in coastal]
    lons = [zone["longitude"] for zone in coastal]
    return {
        "nelat": round(max(lats) + margin_deg, 4),
        "nelng": round(max(lons) + margin_deg, 4),
        "swlat": round(min(lats) - margin_deg, 4),
        "swlng": round(min(lons) - margin_deg, 4),
    }


def build_inaturalist_params(
    taxon_name: str,
    now: datetime,
    lookback_days: int = INATURALIST_LOOKBACK_DAYS,
    per_page: int = 50,
) -> dict:
    """Recent, georeferenced, non-captive observations of one taxon."""
    since = (now - timedelta(days=lookback_days)).date().isoformat()
    params = {
        "taxon_name": taxon_name,
        "d1": since,
        "geo": "true",
        "captive": "false",
        "order_by": "observed_on",
        "order": "desc",
        "per_page": per_page,
    }
    params.update(marine_bounding_box())
    return params


def build_inaturalist_headers() -> dict:
    return {"User-Agent": USER_AGENT, "Accept": "application/json"}


def parse_inaturalist(payload, tz: timezone | None = None) -> list[Sighting]:
    """Turn an observations payload into sightings.

    Coordinates and timestamps are each read from several possible fields. That
    is not defensiveness for its own sake: iNaturalist returns the position as
    geojson, as a "lat,lng" string, or obscured entirely for sensitive taxa, and
    which one you get varies by observation.
    """
    if not isinstance(payload, dict):
        return []
    results = payload.get("results")
    if not isinstance(results, list):
        return []

    zone = tz or timezone.utc
    found: list[Sighting] = []
    for entry in results:
        if not isinstance(entry, dict):
            continue
        position = _inaturalist_position(entry)
        observed = _inaturalist_time(entry, zone)
        if position is None or observed is None:
            continue

        taxon = entry.get("taxon") if isinstance(entry.get("taxon"), dict) else {}
        scientific = taxon.get("name") or ""
        common = taxon.get("preferred_common_name") or MARINE_TAXA.get(scientific) or scientific
        if not common:
            continue

        user = entry.get("user") if isinstance(entry.get("user"), dict) else {}
        identifier = user.get("login") or str(entry.get("id") or "")

        found.append(
            Sighting(
                species=common,
                scientific_name=scientific,
                place=entry.get("place_guess") or "Coastal waters",
                latitude=position[0],
                longitude=position[1],
                latest=observed,
                earliest=observed,
                source="iNaturalist",
                category=CATEGORY_MARINE,
                # Research grade means the community agreed on the ID, which is
                # the closest analogue to eBird's reviewer confirmation.
                confirmed=entry.get("quality_grade") == "research",
                url=entry.get("uri") or (f"https://www.inaturalist.org/observations/{entry['id']}" if entry.get("id") else None),
                observers=[identifier] if identifier else [],
            )
        )
    return found


def _inaturalist_position(entry: dict) -> tuple[float, float] | None:
    geojson = entry.get("geojson")
    if isinstance(geojson, dict):
        coords = geojson.get("coordinates")
        # GeoJSON is longitude-first, which is the opposite of every other
        # field in this payload.
        if isinstance(coords, (list, tuple)) and len(coords) == 2:
            longitude, latitude = _as_float(coords[0]), _as_float(coords[1])
            if latitude is not None and longitude is not None:
                return latitude, longitude

    location = entry.get("location")
    if isinstance(location, str) and "," in location:
        raw_lat, _, raw_lon = location.partition(",")
        latitude, longitude = _as_float(raw_lat), _as_float(raw_lon)
        if latitude is not None and longitude is not None:
            return latitude, longitude

    latitude, longitude = _as_float(entry.get("latitude")), _as_float(entry.get("longitude"))
    if latitude is not None and longitude is not None:
        return latitude, longitude
    return None


def _inaturalist_time(entry: dict, tz: timezone) -> datetime | None:
    raw = entry.get("time_observed_at")
    if isinstance(raw, str):
        moment = _parse_iso(raw)
        if moment is not None:
            return moment

    raw = entry.get("observed_on")
    if isinstance(raw, str):
        try:
            return datetime.strptime(raw.strip()[:10], "%Y-%m-%d").replace(tzinfo=tz)
        except ValueError:
            return None
    return None


def _parse_iso(value: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


# --- Shared -----------------------------------------------------------------


def cluster(sightings: list[Sighting]) -> list[Sighting]:
    """Collapse repeat reports of one species at one place into one sighting.

    Ten checklists for the same vagrant is one thing to drive to, not ten. The
    count of distinct observers survives the merge because it is the strongest
    signal available that the animal is still there.
    """
    merged: dict[tuple[str, str], Sighting] = {}
    for item in sightings:
        existing = merged.get(item.cluster_key)
        if existing is None:
            merged[item.cluster_key] = Sighting(**vars(item))
            continue

        existing.reports += item.reports
        existing.confirmed = existing.confirmed or item.confirmed
        if item.latest > existing.latest:
            existing.latest = item.latest
            # Keep the freshest report's link, so the URL matches the timestamp.
            existing.url = item.url or existing.url
            existing.place = item.place or existing.place
        if item.earliest < existing.earliest:
            existing.earliest = item.earliest
        if item.count is not None:
            existing.count = max(existing.count or 0, item.count)
        for observer in item.observers:
            if observer not in existing.observers:
                existing.observers.append(observer)
    return list(merged.values())


def fresh(sightings: list[Sighting], now: datetime, max_age_hours: int = MAX_SIGHTING_AGE_HOURS) -> list[Sighting]:
    """Drop stale sightings and anything reported in the future."""
    cutoff = now - timedelta(hours=max_age_hours)
    return [item for item in sightings if cutoff <= item.latest <= now + timedelta(hours=1)]


def digest(sightings: list[Sighting], now: datetime, max_age_hours: int = MAX_SIGHTING_AGE_HOURS) -> list[Sighting]:
    """Filter, then cluster - and never the other way round.

    Clustering first lets one bad timestamp decide the age of the whole group:
    a single report dated tomorrow pulls the cluster's ``latest`` into the
    future and the freshness filter then discards every good report with it.
    """
    return cluster(fresh(sightings, now, max_age_hours))


def _as_float(value) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
