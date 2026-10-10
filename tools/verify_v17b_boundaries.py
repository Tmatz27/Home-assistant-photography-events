"""Audit every local import reachable from the shipped HA entry points."""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "custom_components/photography_events"
ROOTS = {"__init__", "config_flow", "repairs", "sensor", "binary_sensor", "calendar", "websocket"}
ALLOWED = ROOTS | {"const", "coordinator", "core_client", "core_bridge", "projection"}
FORBIDDEN_CALLS = {"async_fire", "async_set_event_choice", "async_add_ingested_reports", "_build", "_apply_routing"}


def audit():
    pending, seen, graph = list(ROOTS), set(), {}
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        if name not in ALLOWED:
            raise ValueError("Retired module is reachable: " + name)
        seen.add(name)
        tree = ast.parse((PACKAGE / (name + ".py")).read_text(encoding="utf-8"))
        local = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                local.update([node.module.split(".")[0]] if node.module else [a.name for a in node.names])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in FORBIDDEN_CALLS:
                raise ValueError("Retired side-effect call is reachable: " + node.func.attr)
        graph[name] = sorted(local)
        pending.extend(local - seen)
    card = (PACKAGE / "www/photography-events-card.js").read_text(encoding="utf-8")
    for value in ("weather/get_forecasts", "buildEvents(", "METEOR_SHOWERS", "BIRD_MIGRATION_WINDOWS", "set_event_choice"):
        if value in card:
            raise ValueError("Retired browser path is assembled: " + value)
    return {"active_local_modules": sorted(seen), "imports": graph, "legacy_side_effect_calls": 0,
            "assembled_sources": json.loads((ROOT / "scripts/card-sources.json").read_text())}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
