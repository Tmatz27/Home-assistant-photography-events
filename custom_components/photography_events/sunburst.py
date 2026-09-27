"""SunsetWx's Sunburst API: a purpose-built sunrise/sunset quality forecast.

Why an external source at all: the local model in ``weather_scoring`` is a
careful heuristic (canvas overhead, light path ~200 km upstream, clarity), but
it is still a homemade model. SunsetWx publishes a model built for exactly this
question, so when the photographer supplies credentials it becomes the primary
source and the local model is kept as a comparison and fallback.

What is and is not verified (see SOURCE_VALIDATION.md):

- Base URL, the ``/login`` token exchange with HTTP Basic client credentials
  (``grant_type=client_credentials``, scope ``predictions``) and the
  ``/quality?geo=lat,lon&type=sunset|sunrise`` endpoint come from SunsetWx's
  own open-source client (sunburst.js) and third-party wrappers. The response
  is GeoJSON; features carry ``type``, ``quality`` (Poor/Fair/Good/Great),
  ``quality_percent``, ``valid_at``, ``last_updated`` and ``source`` (the
  weather model), as shown in the PySunsetWx README.
- None of it could be exercised from the development environment (egress
  blocked), and plan/rate limits are not published beyond "register and pick
  the non-commercial plan". So this polls at most every three hours, two
  requests per poll, and fails soft to the local model on any error.

A quality percentage is SunsetWx's forecast score. It is never presented as the
probability of a spectacular photograph.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

BASE_URL = "https://sunburst.sunsetwx.com/v1"
LOGIN_URL = f"{BASE_URL}/login"
QUALITY_URL = f"{BASE_URL}/quality"
SCOPE = "predictions"
# Their top tier. Eligibility uses the provider's own label, not a number we
# picked, so a change in their scale cannot silently move our gate.
TOP_TIER = "Great"
ATTRIBUTION = "Sunrise/sunset quality forecast by SunsetWx (sunsetwx.com)"
# How far a forecast's valid_at may sit from our computed sunset and still be
# the same event.
MATCH_MINUTES = 90


def login_request(client_id: str, client_secret: str) -> tuple[str, dict, dict]:
    token = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/x-www-form-urlencoded"}
    return LOGIN_URL, headers, {"grant_type": "client_credentials", "scope": SCOPE}


def parse_login(payload, now: datetime) -> tuple[str, datetime] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("access_token"), str):
        return None
    try:
        lifetime = int(payload.get("expires_in") or 3600)
    except (TypeError, ValueError):
        lifetime = 3600
    return payload["access_token"], now + timedelta(seconds=max(60, lifetime - 120))


def quality_request(latitude: float, longitude: float, kind: str, token: str) -> tuple[str, dict, dict]:
    return QUALITY_URL, {"geo": f"{latitude:.4f},{longitude:.4f}", "type": kind}, {"Authorization": f"Bearer {token}"}


def _time(value):
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def parse_quality(payload) -> list[dict]:
    """Feature properties we can trust, or nothing.

    A feature with no parseable ``valid_at`` or no numeric percentage is
    dropped: an undated score cannot be matched to an evening, and a label
    without its number cannot be checked.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        return []
    found = []
    for feature in payload["features"]:
        props = feature.get("properties") if isinstance(feature, dict) else None
        if not isinstance(props, dict):
            continue
        valid = _time(props.get("valid_at"))
        percent = props.get("quality_percent")
        if valid is None or not isinstance(percent, (int, float)) or isinstance(percent, bool) or not 0 <= percent <= 100:
            continue
        found.append({
            "kind": str(props.get("type") or "").lower(),
            "quality": str(props.get("quality") or ""),
            "percent": round(float(percent), 1),
            "valid_at": valid,
            "last_updated": _time(props.get("last_updated")),
            "model": props.get("source") or "",
        })
    return found


def match(predictions: list[dict], kind: str, moment: datetime) -> dict | None:
    """The provider forecast for one of our computed sunsets/sunrises."""
    best = None
    for entry in predictions or []:
        if entry.get("kind") and entry["kind"] != kind:
            continue
        gap = abs((entry["valid_at"] - moment).total_seconds()) / 60
        if gap <= MATCH_MINUTES and (best is None or gap < best[0]):
            best = (gap, entry)
    return best[1] if best else None
