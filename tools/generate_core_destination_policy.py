"""Reproduce a candidate from pinned Core sources; NEVER generate approval.

The separate review file is deliberately not written by this tool. A source
listing is not independent destination review or live-service attestation.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

CORE_REFERENCE = "b14014760beee2c18d02a2b1f36756f6faee93a0"
SOURCES = ["definitions/tule_elk_rut.json", "phenomena.py", "legacy_safety.py", "spatial.py", "ingestion.py"]


def generate(source):
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if sha != CORE_REFERENCE or subprocess.check_output(["git", "status", "--porcelain"], cwd=source):
        raise ValueError("A clean pinned Core checkout is required")
    root = source / "src/pec"
    definition = json.loads((root / SOURCES[0]).read_text())
    digest = hashlib.sha256()
    files = []
    for name in SOURCES:
        data = (root / name).read_bytes().replace(b"\r\n", b"\n")
        digest.update(Path(name).name.encode())
        digest.update(data)
        files.append({"path": "src/pec/" + name, "sha256": hashlib.sha256(data).hexdigest()})
    prose = [definition[k] for k in ("name", "photo_tips", "best_time_of_day", "ethics", "safety")]
    for value in definition["gear"].values():
        prose.extend(value if isinstance(value, list) else [value])
    return {"format_version": "core.destinations.1", "authority": "core_curated_definitions", "synthetic": False,
            "core_reference_commit": sha, "schema_version": "0008", "policy_revision": "b140147-candidate-1",
            "sources": files,
            "destinations": [{"key": definition["location_key"], "name": definition["location_name"],
                              "latitude": definition["latitude"], "longitude": definition["longitude"],
                              "policy": "curated_public_site", "public_visitor_listings": [definition["verify_urls"][0]],
                              "public_text": sorted(set(prose)),
                              "definitions": [{"key": definition["key"], "version": definition["version"],
                                               "hash": digest.hexdigest(), "path": "src/pec/" + SOURCES[0],
                                               "occurrence_pattern": r"tule_elk_rut-\d{4}-\d{2}-\d{2}"}]}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(generate(args.core_source), indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
