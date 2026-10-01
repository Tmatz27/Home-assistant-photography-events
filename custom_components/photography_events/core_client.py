"""Isolated async Core v1 client; unused by the default local engine.

No token is part of a response object, log message, entity or websocket payload.
The caller owns the aiohttp session (normally HA's async_get_clientsession).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlencode, urlsplit

import aiohttp

MAX_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 500


class CoreError(Exception):
    """Safe machine-readable errors; never include URLs, headers or bodies."""
    code = "core_unavailable"


class CoreAuthenticationError(CoreError):
    code = "authentication_failed"


class CoreVersionError(CoreError):
    code = "unsupported_api_version"


class CoreProtocolError(CoreError):
    code = "invalid_core_response"


class CoreNotReady(CoreError):
    code = "core_not_ready"


def aware_timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed
    except (TypeError, ValueError, AttributeError):
        raise CoreProtocolError() from None


@dataclass(frozen=True)
class CoreHealth:
    core_version: str
    api_version: str
    schema_version: str
    status: str


@dataclass(frozen=True)
class CoreProduct:
    """Validated rich product data. Additive Core fields are ignored safely."""
    occurrence_key: str
    phenomenon_key: str
    payload: dict = field(repr=False)

    @classmethod
    def parse(cls, row):
        if not isinstance(row, dict):
            raise CoreProtocolError()
        for key in ("occurrence_key", "phenomenon_key", "title", "category", "presentation",
                    "safety_state", "access_state", "evidence_state", "reason", "awaiting"):
            if not isinstance(row.get(key), str):
                raise CoreProtocolError()
        for key in ("starts_at", "ends_at", "data_as_of", "valid_until"):
            aware_timestamp(row.get(key))
        if type(row.get("eligibility")) is not bool or type(row.get("held")) is not bool:
            raise CoreProtocolError()
        for key in ("significance", "confidence", "urgency"):
            if type(row.get(key)) is not int or not 0 <= row[key] <= 100:
                raise CoreProtocolError()
        if row["presentation"] not in {"cant_miss", "watching", "planner", "held", "bird_spectacle", "bird_encounter"}:
            raise CoreProtocolError()
        if row["safety_state"] not in {"safe", "caution", "unsafe", "unknown"}:
            raise CoreProtocolError()
        if not isinstance(row.get("location"), dict) or not isinstance(row.get("gear"), dict):
            raise CoreProtocolError()
        allowed = {"occurrence_key", "phenomenon_key", "title", "category", "location", "starts_at", "ends_at",
                   "presentation", "eligibility", "significance", "confidence", "urgency", "evidence_state",
                   "access_state", "safety_state", "condition_state", "drive_minutes", "drive_basis", "reason",
                   "awaiting", "blockers", "held", "watching", "bird_classification", "gear", "ethics",
                   "safety_summary", "safety_notes", "best_time_of_day", "detail", "data_as_of", "valid_until",
                   "definition_key", "definition_version", "definition_hash", "engine_version"}
        payload = {k: row[k] for k in allowed if k in row}
        # Nested whitelists prevent a future upstream raw-evidence field or
        # connection metadata from being persisted and later sent to a card.
        payload["location"] = {k: row["location"][k] for k in ("key", "name", "latitude", "longitude", "policy") if k in row["location"]}
        payload["gear"] = {k: row["gear"][k] for k in ("take", "optional", "skip", "start", "support", "technique", "video", "drone", "drone_status") if k in row["gear"]}
        return cls(row["occurrence_key"], row["phenomenon_key"], payload)


@dataclass(frozen=True)
class CoreAssessment:
    payload: dict = field(repr=False)
    items: tuple[CoreProduct, ...]

    @classmethod
    def parse(cls, data):
        validate_version(data)
        aware_timestamp(data.get("generated_at"))
        if data.get("data_as_of") is not None:
            aware_timestamp(data["data_as_of"])
        if data.get("assessment_state") not in {"complete", "incomplete", "degraded"}:
            raise CoreProtocolError()
        for key in ("missing_required_sources", "degraded_sources"):
            if not isinstance(data.get(key), list) or not all(isinstance(k, str) for k in data[key]):
                raise CoreProtocolError()
        rows = data.get("items")
        if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
            raise CoreProtocolError()
        items = tuple(CoreProduct.parse(row) for row in rows)
        keys = ("core_version", "api_version", "schema_version", "generated_at", "data_as_of",
                "assessment_state", "missing_required_sources", "degraded_sources")
        return cls({**{k: data.get(k) for k in keys}, "items": [item.payload for item in items]}, items)


def validate_version(data):
    if not isinstance(data, dict):
        raise CoreProtocolError()
    if data.get("api_version") != "v1":
        raise CoreVersionError()
    if not all(isinstance(data.get(k), str) for k in ("core_version", "schema_version")):
        raise CoreProtocolError()


class PhotographyEventsCoreClient:
    def __init__(self, session, url, token, timeout=5.0):
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("Core URL must be an HTTP(S) origin without credentials")
        if not token or not 0 < timeout <= 30:
            raise ValueError("Core token and bounded timeout required")
        self._session, self._url, self._token, self._timeout = session, url.rstrip("/"), token, timeout

    async def _get(self, path):
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.get(self._url + path,
                        headers={"Authorization": "Bearer " + self._token},
                        timeout=aiohttp.ClientTimeout(total=self._timeout), allow_redirects=False) as response:
                    if response.status in (401, 403):
                        raise CoreAuthenticationError()
                    if response.status == 503:
                        raise CoreNotReady()
                    if response.status != 200:
                        raise CoreError()
                    body = bytearray()
                    async for chunk in response.content.iter_chunked(65536):
                        body.extend(chunk)
                        if len(body) > MAX_BYTES:
                            raise CoreProtocolError()
                    try:
                        return json.loads(body)
                    except (ValueError, UnicodeError):
                        raise CoreProtocolError() from None
        except (TimeoutError, aiohttp.ClientError, OSError):
            raise CoreError() from None

    async def health(self):
        data = await self._get("/health/ready")
        validate_version(data)
        if data.get("status") != "ready":
            raise CoreNotReady()
        return CoreHealth(data["core_version"], data["api_version"], data["schema_version"], data["status"])

    async def opportunities(self, *, presentation=None, category=None):
        query = {k: v for k, v in (("presentation", presentation), ("category", category)) if v is not None}
        return CoreAssessment.parse(await self._get("/api/v1/opportunities" + ("?" + urlencode(query) if query else "")))
