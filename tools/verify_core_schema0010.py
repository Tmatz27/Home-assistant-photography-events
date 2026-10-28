"""Reproduce actual API routes from accepted Core, without a DB or app lifespan.

Test-only pinned source/fixture verification; no installed HA/Core connection,
collector, release or publication. Run with Core's development dependencies.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

PIN = "10bde5f0dcb57821f36a971af9e3dc4183271202"
PREVIOUS = "1b59779831e96bbff32e8a4547a4f0d577fdb537"


async def verify(core):
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=core).decode().strip() == PIN
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=core).strip()
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/core-schema0010.json"
    capture = json.loads(fixture.read_text(encoding="utf-8"))
    assert capture["provenance"]["commit"] == PIN
    for name, expected in capture["provenance"]["source_sha256"].items():
        assert hashlib.sha256((core / name).read_bytes()).hexdigest() == expected, name
    assert not subprocess.check_output(["git", "diff", PREVIOUS, PIN, "--", "src/pec/schemas.py"], cwd=core).strip()
    sys.path.insert(0, str(core / "src"))
    spec = importlib.util.spec_from_file_location("upstream_api_tests", core / "tests/test_api.py")
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    app = upstream.create_app(upstream.SETTINGS, upstream.FakeDatabase(), lambda: upstream.NOW)
    responses = {}
    paths = {"health": "/health/ready", "opportunities": "/api/v1/opportunities", "sources": "/api/v1/sources/health"}
    for key, path in paths.items():
        response = await upstream.get(app, path)
        assert response.status_code == 200
        responses[key] = response.json()
        assert responses[key]["schema_version"] == "0010"
    for path in (paths["opportunities"], paths["sources"]):
        assert (await upstream.get(app, path, None)).status_code == 401
        assert (await upstream.get(app, path, "wrong")).status_code == 401
    for key, options in (("empty", {"empty": True}), ("incomplete", {"empty": True, "stale": True})):
        app = upstream.create_app(upstream.SETTINGS, upstream.FakeDatabase(**options), lambda: upstream.NOW)
        responses[key] = (await upstream.get(app, paths["opportunities"])).json()
    assert responses == capture["responses"]
    print(json.dumps(dict(core_sha=PIN, schema="0010", matching_route_responses=len(responses),
                         protected_endpoint_auth_checks=4, public_models_unchanged_from_0009=True,
                         test_only=True, installed_services_accessed=False)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-source", type=Path, required=True)
    asyncio.run(verify(parser.parse_args().core_source.resolve()))
