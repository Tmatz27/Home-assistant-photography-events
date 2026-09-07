"""Calibrate distinct exceptional swell episodes from downloaded NDBC archives.

Usage: python tools/backtest_waves.py DIRECTORY --output REPORT.json
Training: 2020-2023. Held-out validation: 2024-2025. Missing years stay explicit.
No historical inputs are downloaded by this script.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path
from collections import Counter

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wave_backtest", root / "custom_components/photography_events/waves.py")
waves = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = waves
spec.loader.exec_module(waves)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {}
    for station in ("46011", "46042"):
        by_year = {}
        for year in range(2020, 2026):
            path = args.directory / f"{station}-{year}.txt"
            if path.exists():
                by_year[year] = waves.parse_ndbc(path.read_text())
        training = [r for year, rows in by_year.items() if year <= 2023 for r in rows]
        heights = sorted(r.height for r in training)
        if not heights:
            continue
        candidates = []
        for percentile in (.99, .995, .9975, .999):
            threshold = max(4.0, math.ceil(heights[int((len(heights) - 1) * percentile)] * 10) / 10)
            grouped = waves.episodes(training, threshold)
            counts = Counter(g[0].time.year for g in grouped)
            candidates.append({"percentile": percentile, "threshold_m": threshold,
                               "training_episodes_by_year": {str(y): counts[y] for y in by_year if y <= 2023}})
        chosen = next((c for c in candidates if max(c["training_episodes_by_year"].values(), default=0) <= 3), candidates[-1])
        validation = [r for year, rows in by_year.items() if year >= 2024 for r in rows]
        heldout = waves.episodes(validation, chosen["threshold_m"])
        # Coverage counts unique hours, since recent buoys report every 10 min.
        report[station] = {**chosen, "min_period_s": 14, "direction_deg": [240, 330],
            "episode_separation_hours": 48, "candidates": candidates,
            "valid_observation_hours": {str(y): len({r.time.replace(minute=0) for r in rows}) for y, rows in by_year.items()},
            "missing_years": [y for y in range(2020, 2026) if y not in by_year],
            "validation_episodes": [{"start": e[0].time.isoformat(), "end": e[-1].time.isoformat(),
                                    "max_height_m": max(r.height for r in e)} for e in heldout],
            "validation_counts": {str(y): sum(e[0].time.year == y for e in heldout) for y in by_year if y >= 2024},
            "limitations": "Counts cover available valid observations, not missing periods. This is offshore rarity, not breaker height or a guarantee of future event frequency."}
    coastal = args.directory / 'B1500-history.ascii'
    if coastal.exists():
        all_rows = waves.parse_cdip(coastal.read_text(), (34.75812, -120.64311))
        train = [r for r in all_rows if 2020 <= r.time.year <= 2023]
        validate = [r for r in all_rows if 2024 <= r.time.year <= 2025]
        heights = sorted(r.height for r in train)
        candidates = []
        for p in (.99, .995, .9975, .999):
            threshold = math.ceil(heights[int((len(heights)-1)*p)]*10)/10
            groups = waves.episodes(train, threshold)
            counts = {str(y): sum(g[0].time.year == y for g in groups) for y in range(2020, 2024)}
            candidates.append({'threshold_m': threshold, 'percentile': p, 'training_episodes_by_year': counts})
        chosen = next((c for c in candidates if max(c['training_episodes_by_year'].values()) <= 3), candidates[-1])
        groups = waves.episodes(validate, chosen['threshold_m'])
        report['B1500'] = {**chosen, 'candidates': candidates,
            'measurement': 'CDIP nearshore model hindcast, not observations or breaker height',
            'validation_counts': {str(y): sum(g[0].time.year == y for g in groups) for y in {r.time.year for r in validate}},
            'valid_observation_hours': {str(y): len({r.time for r in all_rows if r.time.year == y}) for y in range(2020, 2026)},
            'calibration_last_time': max(r.time for r in all_rows).isoformat(),
            'limitations': 'Hindcast rarity; forecast skill is not measured by this backtest. Coverage may be partial.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: {k: v for k, v in value.items() if k in ("threshold_m", "training_episodes_by_year", "validation_counts", "missing_years")} for key, value in report.items()}, indent=2))


if __name__ == "__main__":
    main()
