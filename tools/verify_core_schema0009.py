"""Read-only reproduction of the schema 0009 API compatibility capture.

In a disposable development venv, install Core rc.2's FastAPI/SQLAlchemy/
asyncpg/Pydantic dependencies plus httpx and pytest, then run:
python tools/verify_core_schema0009.py --core-source /path/to/core-rc2
Uses actual ASGI routes and the upstream test database, without PostgreSQL,
app lifespan, collectors, installed Core services or HA runtime dependencies.
"""
import argparse
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

PIN = "1b59779831e96bbff32e8a4547a4f0d577fdb537"


async def verify(core):
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=core).decode().strip() == PIN, "Use pinned Core rc.2"
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=core).strip(), "Core must be unmodified"
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/core-schema0009.json"
    capture = json.loads(fixture.read_text(encoding="utf-8"))
    assert capture["provenance"]["commit"] == PIN
    for name, expected in capture["provenance"]["source_sha256"].items():
        assert hashlib.sha256((core / name).read_bytes()).hexdigest() == expected, name
    # The reviewed 0008 and deployed 0009 public response models are identical.
    assert not subprocess.check_output(["git", "diff", "b14014760beee2c18d02a2b1f36756f6faee93a0", PIN,
                                        "--", "src/pec/schemas.py"], cwd=core).strip()
    sys.path.insert(0, str(core / "src"))
    spec = importlib.util.spec_from_file_location("upstream_api_tests", core / "tests/test_api.py")
    upstream = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(upstream)
    paths = {"health": "/health/ready", "opportunities": "/api/v1/opportunities", "sources": "/api/v1/sources/health"}
    app = upstream.create_app(upstream.SETTINGS, upstream.FakeDatabase(), lambda: upstream.NOW)
    responses = {}
    for key, path in paths.items():
        response = await upstream.get(app, path)
        assert response.status_code == 200
        responses[key] = response.json()
        assert responses[key]["schema_version"] == "0009"
    for path in (paths["opportunities"], paths["sources"]):
        assert (await upstream.get(app, path, None)).status_code == 401
        assert (await upstream.get(app, path, "wrong")).status_code == 401
    for key, options in (("empty", {"empty": True}), ("incomplete", {"empty": True, "stale": True})):
        app = upstream.create_app(upstream.SETTINGS, upstream.FakeDatabase(**options), lambda: upstream.NOW)
        response = await upstream.get(app, paths["opportunities"])
        assert response.status_code == 200
        responses[key] = response.json()
    assert responses == capture["responses"], "API capture changed"
    print(json.dumps({"core_sha": PIN, "schema": "0009", "matching_route_responses": len(responses),
                      "protected_endpoint_auth_checks": 4, "public_models_unchanged_from_0008": True}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-source", type=Path, required=True)
    asyncio.run(verify(parser.parse_args().core_source.resolve()))
