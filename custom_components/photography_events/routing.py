"""Real driving times from the Google Maps platform.

Two endpoints, because Google split this one in half mid-life:

- **Routes API** (``computeRouteMatrix``) is the current product and the only
  one a project enabled after 1 March 2025 can turn on.
- **Distance Matrix API** is the legacy product. Projects that already had it
  keep working; new ones cannot enable it at all.

Which one a given key can call is a property of the Google Cloud project, not
of this code, so both are implemented and the client tries the modern one
first. A key that only carries the legacy entitlement falls through to it
automatically, and a key that carries neither degrades to the calibrated
straight-line estimate in ``wildlife.estimate_drive_hours`` rather than
blocking the update.

Request building and response parsing only - the coordinator owns the HTTP and
the quota discipline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

ROUTES_URL = "https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix"
LEGACY_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"

# Ask only for the fields we use. Routes API rejects a request with no field
# mask outright, and a wildcard mask is both slower and billed at a higher tier.
ROUTES_FIELD_MASK = "originIndex,destinationIndex,duration,distanceMeters,status,condition"

# Routes allows 625 elements per call and the legacy API 100, with a hard cap of
# 25 destinations per request. One origin means elements == destinations, so 25
# keeps both inside their limits.
MAX_DESTINATIONS_PER_REQUEST = 25


@dataclass(frozen=True)
class DriveTime:
    """A routed travel time to one destination."""

    hours: float
    meters: int | None
    in_traffic: bool
    source: str

    @property
    def minutes(self) -> int:
        return int(round(self.hours * 60))


def chunk_destinations(destinations: list, size: int = MAX_DESTINATIONS_PER_REQUEST) -> list[list]:
    return [destinations[i : i + size] for i in range(0, len(destinations), size)]


# --- Routes API (current) ---------------------------------------------------


def build_routes_request(
    origin: tuple[float, float],
    destinations: list[tuple[float, float]],
    api_key: str,
    depart_at: datetime | None = None,
) -> tuple[str, dict, dict]:
    """URL, headers, and JSON body for one computeRouteMatrix call.

    ``TRAFFIC_AWARE`` is the point of using Google at all here - the static
    baselines in the zone table already answer the free-flowing case. It costs
    more per element than ``TRAFFIC_UNAWARE`` and is worth it: a Friday
    afternoon run up the 101 is not the same drive as a Tuesday morning one.
    """
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": ROUTES_FIELD_MASK,
    }
    body: dict = {
        "origins": [_routes_waypoint(origin)],
        "destinations": [_routes_waypoint(point) for point in destinations],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    if depart_at is not None:
        # Google rejects a departure time in the past, so only future
        # departures are sent; omitting it means "now", which is what we want.
        body["departureTime"] = depart_at.isoformat().replace("+00:00", "Z")
    return ROUTES_URL, headers, body


def _routes_waypoint(point: tuple[float, float]) -> dict:
    return {"waypoint": {"location": {"latLng": {"latitude": point[0], "longitude": point[1]}}}}


def parse_routes_response(payload) -> dict[int, DriveTime]:
    """Map destinationIndex to a drive time, skipping unreachable pairs.

    computeRouteMatrix answers with a flat list rather than a matrix, and the
    entries are not guaranteed to arrive in request order - the response is
    designed to be streamed - so the index carried on each element is the only
    safe way to line results back up with destinations.
    """
    if not isinstance(payload, list):
        return {}

    found: dict[int, DriveTime] = {}
    for element in payload:
        if not isinstance(element, dict):
            continue
        # `status` is an empty object on success; anything in it is an error.
        if element.get("status"):
            continue
        if element.get("condition") not in (None, "ROUTE_EXISTS"):
            continue
        index = element.get("destinationIndex")
        seconds = _duration_seconds(element.get("duration"))
        if not isinstance(index, int) or seconds is None:
            continue
        found[index] = DriveTime(
            hours=seconds / 3600,
            meters=_as_int(element.get("distanceMeters")),
            in_traffic=True,
            source="Routes API",
        )
    return found


def _duration_seconds(value) -> float | None:
    """Routes returns protobuf durations as a string of seconds: "3456s"."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.endswith("s"):
        try:
            return float(value[:-1])
        except ValueError:
            return None
    return None


# --- Distance Matrix API (legacy) -------------------------------------------


def build_legacy_request(
    origin: tuple[float, float],
    destinations: list[tuple[float, float]],
    api_key: str,
) -> tuple[str, dict]:
    """URL and query parameters for one Distance Matrix call."""
    return LEGACY_URL, {
        "origins": _legacy_point(origin),
        "destinations": "|".join(_legacy_point(point) for point in destinations),
        "mode": "driving",
        "units": "metric",
        # duration_in_traffic only comes back when a departure time is given,
        # and "now" is the only value that does not need a future timestamp.
        "departure_time": "now",
        "traffic_model": "best_guess",
        "key": api_key,
    }


def _legacy_point(point: tuple[float, float]) -> str:
    return f"{point[0]:.6f},{point[1]:.6f}"


def parse_legacy_response(payload) -> dict[int, DriveTime]:
    """Map destination index to a drive time from a Distance Matrix payload."""
    if not isinstance(payload, dict) or payload.get("status") != "OK":
        if isinstance(payload, dict) and payload.get("status"):
            _LOGGER.debug(
                "Distance Matrix returned %s: %s",
                payload.get("status"),
                payload.get("error_message", "no detail"),
            )
        return {}

    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        return {}
    elements = rows[0].get("elements") if isinstance(rows[0], dict) else None
    if not isinstance(elements, list):
        return {}

    found: dict[int, DriveTime] = {}
    for index, element in enumerate(elements):
        if not isinstance(element, dict) or element.get("status") != "OK":
            continue
        # Prefer the traffic-aware figure; it is absent outside driving mode
        # and in regions where Google has no traffic data.
        traffic = _legacy_seconds(element.get("duration_in_traffic"))
        plain = _legacy_seconds(element.get("duration"))
        seconds = traffic if traffic is not None else plain
        if seconds is None:
            continue
        distance = element.get("distance")
        found[index] = DriveTime(
            hours=seconds / 3600,
            meters=_as_int(distance.get("value")) if isinstance(distance, dict) else None,
            in_traffic=traffic is not None,
            source="Distance Matrix API",
        )
    return found


def _legacy_seconds(value) -> float | None:
    if isinstance(value, dict):
        return _as_float(value.get("value"))
    return None


def _as_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
