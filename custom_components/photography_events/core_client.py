"""Private bounded Core v1 transport for the read-only v17 runtime.

No token is part of a response object, log message, entity or websocket payload.
The caller owns the aiohttp session (normally HA's async_get_clientsession).
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlencode, urlsplit

from .projection import InvalidProjection, validate_row, validate_envelope, text, timestamp, SAFE_SOURCES, SUPPORTED_CORE_SCHEMAS

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
        try:
            payload = validate_row(row)
        except InvalidProjection:
            raise CoreProtocolError() from None
        return cls(payload["occurrence_key"], payload["phenomenon_key"], payload)



@dataclass(frozen=True)
class CoreAssessment:
    payload: dict = field(repr=False)
    items: tuple[CoreProduct, ...]

    @classmethod
    def parse(cls, data):
        validate_version(data)
        try:
            payload = validate_envelope(data)
        except InvalidProjection:
            raise CoreProtocolError() from None
        return cls(payload, tuple(CoreProduct(r["occurrence_key"], r["phenomenon_key"], r) for r in payload["items"]))



def validate_version(data):
    if not isinstance(data, dict):
        raise CoreProtocolError()
    if data.get("api_version") != "v1" or data.get("schema_version") not in SUPPORTED_CORE_SCHEMAS or data.get("core_version") != "0.1.0-dev":
        raise CoreVersionError()
    if not all(isinstance(data.get(k), str) for k in ("core_version", "schema_version")):
        raise CoreProtocolError()


class PhotographyEventsCoreClient:
    def __init__(self, session, url, token, timeout=5.0):
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("Core URL must be an HTTP(S) origin without credentials")
        if not isinstance(token, str) or not token.strip() or len(token) > 4096 or "\n" in token or "\r" in token or not 0 < timeout <= 30:
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

    async def source_health(self):
        data = await self._get("/api/v1/sources/health")
        validate_version(data)
        try:
            generated = timestamp(data.get("generated_at")).isoformat()
            rows = data.get("items")
            if not isinstance(rows, list) or len(rows) > 64:
                raise InvalidProjection("invalid_list")
            safe = []
            for row in rows:
                if not isinstance(row, dict) or row.get("state") not in {"UP", "STALE", "DOWN"}:
                    raise InvalidProjection("invalid_source")
                key = text(row.get("key"), 256)
                if row.get("error_code") is not None:
                    text(row["error_code"], 256)
                source = {"key": key if key in SAFE_SOURCES else "core", "state": row["state"],
                          "error_code": None if row.get("error_code") is None else "source_unavailable"}
                for stamp_key in ("last_attempt_at", "last_success_at", "provider_updated_at"):
                    source[stamp_key] = timestamp(row[stamp_key]).isoformat() if row.get(stamp_key) is not None else None
                safe.append(source)
            return {"generated_at": generated, "items": safe}
        except (InvalidProjection, TypeError, KeyError):
            raise CoreProtocolError() from None
