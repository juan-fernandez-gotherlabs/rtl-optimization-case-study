"""Compute the nondominated PPA frontier from public evaluator results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PRIMARY = ("area_total_mwta", "critical_path_delay_ns", "energy_per_block_nj")


def pareto_front(results: list[dict]) -> list[dict]:
    """Return valid nondominated results for three minimization objectives."""
    valid = [
        result
        for result in results
        if result.get("valid")
        and all(
            isinstance(result.get("metrics", {}).get(name), int | float)
            for name in PRIMARY
        )
    ]
    frontier: list[dict] = []
    for candidate in valid:
        values = tuple(float(candidate["metrics"][name]) for name in PRIMARY)
        dominated = False
        for other in valid:
            if other is candidate:
                continue
            other_values = tuple(float(other["metrics"][name]) for name in PRIMARY)
            if all(
                left <= right for left, right in zip(other_values, values, strict=True)
            ) and any(
                left < right for left, right in zip(other_values, values, strict=True)
            ):
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return frontier


def main() -> int:
    """Load evaluator JSON files and print their Pareto frontier."""
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", type=Path)
    args = parser.parse_args()
    payloads = [json.loads(path.read_text(encoding="utf-8")) for path in args.results]
    print(json.dumps(pareto_front(payloads), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
