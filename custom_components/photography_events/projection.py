"""The sole rich-output boundary for Core products, cache, WS and calendar.

This adapter can withhold authority; it never creates ecological decisions.
The six-hour cap is provisional. No debug record is accepted as a normal list.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

VERSION = "ha.v17.1"
TRANSPORT_MAX_AGE = timedelta(minutes=15)
ASSESSMENT_MAX_AGE = timedelta(hours=6)
MAX_CLOCK_SKEW = timedelta(seconds=60)
MAX_CACHE_AGE = timedelta(days=7)
MAX_ITEMS = 500
WITHHELD = {"policy": "withheld", "key": None, "name": "Location withheld", "latitude": None, "longitude": None}
PRESENTATIONS = {"cant_miss", "watching", "planner", "held", "bird_spectacle", "bird_encounter"}
TEXT_FIELDS = ("occurrence_key", "phenomenon_key", "title", "category", "presentation", "evidence_state",
               "access_state", "safety_state", "condition_state", "drive_basis", "reason", "awaiting", "ethics",
               "safety_summary", "best_time_of_day", "detail", "definition_key", "definition_version",
               "definition_hash", "engine_version")
GEAR_FIELDS = ("take", "start", "support", "technique", "video", "drone", "drone_status")
SAFE_SOURCES = {"fixture", "inaturalist", "nws", "wfigs", "core"}


class InvalidProjection(ValueError):
    """A fixed error only: never place upstream bytes in an exception."""


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (TypeError, AttributeError, ValueError, OverflowError):
        raise InvalidProjection("invalid_timestamp") from None


def text(value, limit=2048):
    if not isinstance(value, str) or len(value) > limit:
        raise InvalidProjection("invalid_text")
    return value


def texts(value, limit=32):
    if not isinstance(value, list) or len(value) > limit:
        raise InvalidProjection("invalid_list")
    return [text(v, 512) for v in value]


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class DestinationPolicy:
    """Core-derived artifact, separately pinned review; never auto-approve drift.

    Default shipped review is pending: coordinates and identifying prose remain
    withheld until independent destination review. Health cannot prove a live
    source commit; per-product hashes bind to the reviewed source artifact.
    """

    def __init__(self, artifact=None, review=None):
        self.destinations = {}
        self.definitions = {}
        self.state = "unverified"
        try:
            if (not isinstance(artifact, dict) or not isinstance(review, dict)
                    or artifact.get("format_version") != "core.destinations.1"
                    or artifact.get("authority") != "core_curated_definitions"
                    or artifact.get("synthetic") is not False or review.get("reviewed") is not True
                    or review.get("content_sha256") != canonical_digest(artifact)
                    or artifact.get("core_reference_commit") != review.get("core_reference_commit")
                    or artifact.get("core_reference_commit") != "b14014760beee2c18d02a2b1f36756f6faee93a0"
                    or artifact.get("policy_revision") != review.get("policy_revision")
                    or artifact.get("schema_version") != "0008"):
                return
            expected_sources = {"src/pec/definitions/tule_elk_rut.json", "src/pec/phenomena.py", "src/pec/legacy_safety.py",
                                "src/pec/spatial.py", "src/pec/ingestion.py"}
            sources = artifact.get("sources")
            if (not isinstance(sources, list) or len(sources) != len(expected_sources)
                    or {s.get("path") for s in sources if isinstance(s, dict)} != expected_sources
                    or any(not isinstance(s, dict) or not re.fullmatch("[a-f0-9]{64}", text(s.get("sha256"), 64)) for s in sources)):
                return
            if not text(artifact.get("policy_revision"), 256):
                return
            for d in artifact["destinations"]:
                pair = d["latitude"], d["longitude"]
                if (d["policy"] != "curated_public_site" or not all(finite(v) for v in pair)
                        or not -90 <= pair[0] <= 90 or not -180 <= pair[1] <= 180 or d["key"] in self.destinations):
                    return
                definitions = set()
                for definition in d["definitions"]:
                    identity = tuple(text(definition[k], 256) for k in ("key", "version", "hash"))
                    if not re.fullmatch("[a-f0-9]{64}", identity[2]) or definition.get("path") != "src/pec/definitions/tule_elk_rut.json":
                        return
                    # Exact reviewed occurrence grammar is an identity boundary,
                    # not a heuristic for stripping provider IDs from free text.
                    pattern = definition["occurrence_pattern"]
                    if pattern != r"tule_elk_rut-\d{4}-\d{2}-\d{2}" or identity[0] != "tule_elk_rut":
                        return
                    definitions.add(identity)
                    self.definitions[identity] = pattern
                if not definitions:
                    return
                if d.get("public_visitor_listings") != ["https://www.blm.gov/visit/carrizo-plain-national-monument"]:
                    return
                prose = set(texts(d.get("public_text", []), 64))
                self.destinations[text(d["key"], 256)] = {"name": text(d["name"], 256), "pair": pair, "definitions": definitions, "prose": prose}
            self.state = "verified"
        except (TypeError, KeyError, ValueError):
            self.destinations = {}
            self.definitions = {}
        if self.state != "verified":
            self.destinations = {}
            self.definitions = {}

    @classmethod
    def load(cls):
        try:
            root = Path(__file__).parent / "policy"
            return cls(json.loads((root / "core-destinations.json").read_text()),
                       json.loads((root / "destination-review.json").read_text()))
        except (OSError, ValueError):
            return cls()

    def permits(self, row):
        loc = row["location"]
        d = self.destinations.get(loc.get("key")) if self.state == "verified" else None
        identity = tuple(row[k] for k in ("definition_key", "definition_version", "definition_hash"))
        return (d is not None and loc.get("policy") == "curated_public_site"
                and all(finite(loc.get(k)) for k in ("latitude", "longitude"))
                and (loc["latitude"], loc["longitude"]) == d["pair"] and identity in d["definitions"])


def validate_row(row):
    if not isinstance(row, dict):
        raise InvalidProjection("invalid_row")
    defaults = {"condition_state": "not_required", "detail": "", "best_time_of_day": ""}
    out = {k: text(row.get(k, defaults.get(k)), 256 if k in {"title", "occurrence_key", "phenomenon_key"} else 2048)
           for k in TEXT_FIELDS}
    if (out["category"] not in {"mammals", "birds", "insects"} or out["presentation"] not in PRESENTATIONS
            or out["safety_state"] not in {"safe", "caution", "unsafe", "unknown"}
            or out["condition_state"] not in {"not_required", "unknown"}):
        raise InvalidProjection("unsupported_enum")
    if not re.fullmatch("[a-f0-9]{64}", out["definition_hash"]):
        raise InvalidProjection("invalid_provenance")
    if (out["definition_version"] != "legacy-0.16.1-1" or out["engine_version"] != "0.1.0-dev"
            or out["evidence_state"] not in {"calendar", "calendar_presence", "season"}
            or out["access_state"] not in {"public", "unsafe", "unknown"}
            or out["drive_basis"] not in {"estimate", "withheld"}):
        raise InvalidProjection("unreviewed_provenance")
    # Only the normal Core M1 identity is reviewed at b140147. Unknown opaque
    # IDs are rejected, rather than risk exporting a location-bearing ID.
    if (out["phenomenon_key"] != "tule_elk_rut" or out["definition_key"] != "tule_elk_rut"
            or out["category"] != "mammals"
            or not re.fullmatch(r"tule_elk_rut-\d{4}-\d{2}-\d{2}", out["occurrence_key"])):
        raise InvalidProjection("unreviewed_identity")
    for key in ("eligibility", "held", "watching"):
        if type(row.get(key)) is not bool:
            raise InvalidProjection("invalid_boolean")
        out[key] = row[key]
    for key in ("significance", "confidence", "urgency"):
        if type(row.get(key)) is not int or not 0 <= row[key] <= 100:
            raise InvalidProjection("invalid_score")
        out[key] = row[key]
    for key in ("starts_at", "ends_at", "data_as_of", "valid_until"):
        out[key] = timestamp(row.get(key)).isoformat()
    if timestamp(out["starts_at"]) > timestamp(out["ends_at"]):
        raise InvalidProjection("invalid_time_order")
    for key in ("blockers", "safety_notes"):
        out[key] = texts(row.get(key))
    gear = row.get("gear")
    if not isinstance(gear, dict):
        raise InvalidProjection("invalid_gear")
    out["gear"] = {k: text(gear.get(k, ""), 512) for k in GEAR_FIELDS}
    out["gear"].update({k: texts(gear.get(k, [])) for k in ("optional", "skip")})
    out["bird_classification"] = row.get("bird_classification")
    if out["bird_classification"] not in (None, "spectacle", "encounter"):
        raise InvalidProjection("unsupported_enum")
    drive = row.get("drive_minutes")
    if drive is not None and (not finite(drive) or drive < 0):
        raise InvalidProjection("invalid_drive")
    out["drive_minutes"] = drive
    loc = row.get("location")
    if not isinstance(loc, dict):
        raise InvalidProjection("invalid_location")
    out["location"] = {k: loc.get(k) for k in ("key", "name", "latitude", "longitude", "policy")}
    if ((not isinstance(loc.get("key"), str) and not (loc.get("policy") == "withheld" and loc.get("key") is None)) or not isinstance(loc.get("name"), str)
            or loc.get("policy", "curated_public_site") not in {"curated_public_site", "withheld"}):
        raise InvalidProjection("invalid_location")
    for key, maximum in (("latitude", 90), ("longitude", 180)):
        if loc.get(key) is not None and (not finite(loc[key]) or not -maximum <= loc[key] <= maximum):
            raise InvalidProjection("invalid_location")
    aid = row.get("assessment_id")
    if aid is not None and (type(aid) is not int or aid < 1):
        raise InvalidProjection("invalid_assessment")
    out["assessment_id"] = aid
    return out


def validate_envelope(data):
    if not isinstance(data, dict) or data.get("mode") in {"shadow", "off"} or "preview_opportunities" in data:
        raise InvalidProjection("normal_endpoint_required")
    if data.get("api_version") != "v1" or data.get("schema_version") != "0008" or data.get("core_version") != "0.1.0-dev":
        raise InvalidProjection("unsupported_api_version")
    out = {k: text(data.get(k), 256) for k in ("core_version", "api_version", "schema_version")}
    out["generated_at"] = timestamp(data.get("generated_at")).isoformat()
    out["data_as_of"] = timestamp(data["data_as_of"]).isoformat() if data.get("data_as_of") is not None else None
    out["assessment_id"] = data.get("assessment_id")
    if out["assessment_id"] is not None and (type(out["assessment_id"]) is not int or out["assessment_id"] < 1):
        raise InvalidProjection("invalid_assessment")
    if data.get("assessment_state") not in {"complete", "incomplete", "degraded"}:
        raise InvalidProjection("invalid_assessment")
    out["assessment_state"] = data["assessment_state"]
    for key in ("missing_required_sources", "degraded_sources"):
        values = texts(data.get(key), 64)
        out[key] = sorted({v if v in SAFE_SOURCES else "core" for v in values})
    if len(data["missing_required_sources"]) + len(data["degraded_sources"]) > 64:
        raise InvalidProjection("invalid_list")
    if out["assessment_state"] == "complete" and (out["missing_required_sources"] or out["degraded_sources"]):
        raise InvalidProjection("contradictory_assessment")
    if not isinstance(data.get("items"), list) or len(data["items"]) > MAX_ITEMS:
        raise InvalidProjection("invalid_list")
    out["items"] = [validate_row(r) for r in data["items"]]
    keys = [r["occurrence_key"] for r in out["items"]]
    if len(set(keys)) != len(keys) or any(r["assessment_id"] not in (None, out["assessment_id"]) for r in out["items"]):
        raise InvalidProjection("invalid_identity")
    return out


def sanitize_envelope(data, policy):
    out = validate_envelope(data)
    for row in out["items"]:
        if policy.permits(row):
            d = policy.destinations[row["location"]["key"]]
            row["location"] = {"policy": "curated_public_site", "key": row["location"]["key"],
                               "name": d["name"], "latitude": d["pair"][0], "longitude": d["pair"][1]}
            # Even recognized prose fields are not a provider-data tunnel.
            # Only separately reviewed source-controlled public strings survive.
            for key in ("title", "reason", "awaiting", "ethics", "detail", "best_time_of_day", "safety_summary"):
                if row[key] not in d["prose"]:
                    row[key] = "Core opportunity" if key == "title" else ""
            for key in ("blockers", "safety_notes"):
                # Unknown blockers still block; replace their text, never drop a gate.
                row[key] = [v if v in d["prose"] else "Core check unresolved" for v in row[key]]
            for key, value in row["gear"].items():
                row["gear"][key] = [v for v in value if v in d["prose"]] if isinstance(value, list) else value if value in d["prose"] else ""
        else:
            row.update(location=dict(WITHHELD), title="Opportunity location withheld", drive_minutes=None,
                       drive_basis="withheld", reason="Location withheld.", awaiting="Reviewed public destination required.",
                       blockers=["location withheld"], detail="", ethics="", best_time_of_day="", safety_notes=[],
                       safety_summary="Travel checks unavailable.", safety_state="unknown", access_state="unknown",
                       condition_state="unknown", eligibility=False, held=True, watching=False,
                       gear={k: [] if k in {"optional", "skip"} else "" for k in row["gear"]})
        if len(json.dumps(row, ensure_ascii=False).encode()) > 32768:
            raise InvalidProjection("oversized_row")
    return out


def project(data, *, now, fetched_at, saved_at=None, availability="online", error_code=None,
            cached_context=False, coverage="unverified", view="cant_miss"):
    """Age a sanitized snapshot only. No request or timestamp mutation here."""
    data = copy.deepcopy(data) if data else None
    if availability == "offline" and saved_at is not None and now >= saved_at + MAX_CACHE_AGE:
        data, cached_context = None, False
    transport = "unknown" if fetched_at is None else "stale" if now >= fetched_at + TRANSPORT_MAX_AGE else "current"
    asof = timestamp(data["data_as_of"]) if data and data.get("data_as_of") else None
    assessment = "unknown" if asof is None else "stale" if now >= asof + ASSESSMENT_MAX_AGE else "current"
    state = data["assessment_state"] if data else "not_assessed"
    scope = "unsupported" if view in {"birds", "planner"} else coverage
    freshness = "unknown" if "unknown" in (transport, assessment) else "stale" if "stale" in (transport, assessment) else "current"
    if availability != "online":
        primary = "offline_stale" if availability == "offline" and data and cached_context else "unavailable"
    elif scope == "unsupported":
        primary = "unsupported"
    elif not data or not data.get("assessment_id") or asof is None or fetched_at is None:
        primary = "not_assessed"
    elif state != "complete":
        primary = state
    elif freshness != "current":
        primary = "stale"
    elif data["items"] and all(timestamp(r["valid_until"]) <= now for r in data["items"]):
        primary = "stale"
        freshness = "stale"
    elif scope != "verified":
        primary = "coverage_unknown"
    else:
        primary = "current" if data["items"] else "empty_assessed"
    rows = []
    hidden = availability != "online" and not (availability == "offline" and cached_context)
    if data and not hidden:
        for row in data["items"]:
            expired = timestamp(row["valid_until"]) <= now
            current = primary in {"current", "empty_assessed"} and not expired
            action = (current and row["eligibility"] and not row["held"] and not row["watching"] and not row["blockers"]
                      and row["presentation"] == "cant_miss" and row["location"]["policy"] == "curated_public_site"
                      and row["safety_state"] in {"safe", "caution"} and row["access_state"] == "public"
                      and row["condition_state"] == "not_required" and timestamp(row["ends_at"]) > now)
            row.update(event_id=row["occurrence_key"], actionable=bool(action), choice="default",
                       row_freshness="stale" if expired else "current", row_state="stale" if expired else "current" if current and not row["held"] else "held")
            if not current:
                row.update(eligibility=False, held=True, watching=False, presentation="held", safety_state="unknown", access_state="unknown",
                           condition_state="unknown", reason="Current scoped Core assessment unavailable.", awaiting="A current reviewed Core assessment.",
                           safety_summary="Travel checks unavailable.", safety_notes=[], blockers=["current assessment unavailable"])
            if view == "cant_miss" and not action:
                continue
            if view == "watching" and action:
                continue
            rows.append(row)
    deadline = min(fetched_at + TRANSPORT_MAX_AGE, asof + ASSESSMENT_MAX_AGE) if fetched_at and asof else None
    return {"projection_version": VERSION, "assessment_id": data.get("assessment_id") if data else None,
            "generated_at": data.get("generated_at") if data else None,
            "data_as_of": asof.isoformat() if asof else None, "fetched_at": fetched_at.isoformat() if fetched_at else None,
            "saved_at": saved_at.isoformat() if saved_at else None, "expires_at": deadline.isoformat() if deadline else None,
            "availability": availability, "assessment_state": state, "freshness": freshness,
            "transport_freshness": transport, "assessment_freshness": assessment,
            "view_state": primary, "error_code": error_code,
            "coverage": {"state": scope, "scope": [], "through": None, "basis": "unknown"},
            "problems": [{"code": "required_source_unavailable", "source": v} for v in (data or {}).get("missing_required_sources", [])]
                        + [{"code": "source_degraded", "source": v} for v in (data or {}).get("degraded_sources", [])],
            "counts": {"available": len(rows) if primary in {"current", "empty_assessed"} else None,
                       "returned": len(rows), "suppressed": 0},
            "choices": {"available": False, "authority": "pending_core"}, "notifications_enabled": False,
            "items": rows, "next_cursor": None, "truncated": False}
