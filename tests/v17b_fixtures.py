"""Synthetic runtime scenarios. Never installed or shown as live Core data."""
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

NOW = datetime(2026, 10, 10, 18, tzinfo=timezone.utc)


def payload(now=NOW):
    data = json.loads((Path(__file__).parent / "fixtures/v17a/approved_public.json").read_text())
    data.update(generated_at=now.isoformat(), data_as_of=(now - timedelta(minutes=30)).isoformat())
    row = data["items"][0]
    row.update(occurrence_key="tule_elk_rut-2026-09-15", phenomenon_key="tule_elk_rut", definition_key="tule_elk_rut",
               definition_version="legacy-0.16.1-1", evidence_state="calendar_presence", title="Synthetic test opportunity",
               starts_at=(now-timedelta(hours=1)).isoformat(), ends_at=(now+timedelta(days=1)).isoformat(),
               data_as_of=data["data_as_of"], valid_until=(now+timedelta(hours=2)).isoformat())
    return data


def policy_documents():
    row = payload()["items"][0]
    prose = [row[k] for k in ("title", "reason", "awaiting", "ethics", "detail", "best_time_of_day", "safety_summary")]
    prose += [v for v in row["gear"].values() if isinstance(v, str)]
    artifact = {"format_version": "core.destinations.1", "authority": "core_curated_definitions", "synthetic": False,
                "core_reference_commit": "b14014760beee2c18d02a2b1f36756f6faee93a0", "schema_version": "0008",
                "policy_revision": "synthetic-runtime-test-witness", "sources": [{"path": "src/pec/"+p, "sha256": "a"*64} for p in
                    ("definitions/tule_elk_rut.json", "phenomena.py", "legacy_safety.py", "spatial.py", "ingestion.py")],
                "destinations": [{**copy.deepcopy(row["location"]), "public_text": prose,
                                  "public_visitor_listings": ["https://www.blm.gov/visit/carrizo-plain-national-monument"],
                                  "definitions": [{"key": row["definition_key"], "version": row["definition_version"], "hash": row["definition_hash"],
                                                   "path": "src/pec/definitions/tule_elk_rut.json",
                                                   "occurrence_pattern": r"tule_elk_rut-\d{4}-\d{2}-\d{2}"}]}]}
    review = {"reviewed": True, "core_reference_commit": artifact["core_reference_commit"],
              "policy_revision": artifact["policy_revision"],
              "content_sha256": "75c712476c0bc1af8480210b2f1db80cf0fc62ca953dc5ae8b52eb43ba03eb99"}
    return artifact, review
