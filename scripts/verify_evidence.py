#!/usr/bin/env python3
"""Offline integrity and statistical verification for the published case study."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METRICS = ("area_total_mwta", "critical_path_delay_ns", "energy_per_block_nj")


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log_confidence(values: list[float]) -> dict[str, float]:
    if len(values) != 64:
        raise AssertionError(f"expected 64 paired values, got {len(values)}")
    mean = statistics.mean(values)
    stdev = statistics.stdev(values)
    # Student-t critical values frozen by the evaluator for df=63.
    two_sided = 1.9983405425207417
    one_sided = 1.6694022215079607
    standard_error = stdev / math.sqrt(len(values))
    return {
        "estimate": math.exp(mean),
        "ci95_low": math.exp(mean - two_sided * standard_error),
        "ci95_high": math.exp(mean + two_sided * standard_error),
        "one_sided_low": math.exp(mean - one_sided * standard_error),
        "one_sided_high": math.exp(mean + one_sided * standard_error),
    }


def close(actual: float, expected: float, *, tolerance: float = 5e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise AssertionError(f"value mismatch: {actual!r} != {expected!r}")


def main() -> int:
    baseline = load("results/baseline-certification.json")
    accepted = load("results/accepted-certification.json")
    formal = load("evidence/formal-proof.json")
    manifest = load("contract/sha_vtr_manifest.json")

    baseline_rtl = ROOT / "rtl/baseline/sha.v"
    accepted_rtl = ROOT / "rtl/accepted/sha.v"
    assert sha256(baseline_rtl) == manifest["source"]["golden_seed_sha256"]
    assert sha256(accepted_rtl) == accepted["candidate_sha256"]
    assert accepted["candidate_id"] == "accepted-rtl"
    assert formal["candidate_id"] == "accepted-rtl"
    assert formal["candidate_sha256"] == accepted["candidate_sha256"]
    assert formal["formal_status"] == "pass"
    assert accepted["correctness"]["functional_pass"] == 1.0
    assert accepted["correctness"]["formal_pass"] == 1.0
    assert accepted["correctness"]["nist_short_long_cases"] == 129
    assert accepted["valid"] and accepted["certified"]
    assert accepted["accepted_improvement"] and accepted["acceptance_decision"]

    baseline_rows = {int(row["seed"]): row for row in baseline["per_seed"]}
    accepted_rows = {int(row["seed"]): row for row in accepted["per_seed"]}
    assert tuple(sorted(baseline_rows)) == tuple(sorted(accepted_rows))
    assert len(baseline_rows) == 64

    composite_logs: list[float] = []
    metric_confidence: dict[str, dict[str, float]] = {}
    for metric in METRICS:
        logs = [
            math.log(float(accepted_rows[seed][metric]) / float(baseline_rows[seed][metric]))
            for seed in sorted(baseline_rows)
        ]
        metric_confidence[metric] = log_confidence(logs)
        published = accepted["statistical_confidence"]["metrics"][metric]
        close(metric_confidence[metric]["estimate"], published["estimate"])
        close(metric_confidence[metric]["ci95_low"], published["ci95_two_sided"][0])
        close(metric_confidence[metric]["ci95_high"], published["ci95_two_sided"][1])

    for seed in sorted(baseline_rows):
        composite_logs.append(
            statistics.mean(
                math.log(float(accepted_rows[seed][metric]) / float(baseline_rows[seed][metric]))
                for metric in METRICS
            )
        )
    composite = log_confidence(composite_logs)
    published_composite = accepted["statistical_confidence"]["composite"]
    close(composite["estimate"], accepted["score"])
    close(composite["estimate"], published_composite["estimate"])
    close(composite["ci95_low"], published_composite["ci95_two_sided"][0])
    close(composite["ci95_high"], published_composite["ci95_two_sided"][1])

    assert composite["one_sided_high"] < 1.0
    assert all(item["one_sided_low"] <= 1.0 for item in metric_confidence.values())
    print("Evidence verification: PASS")
    print(f"baseline_sha256={sha256(baseline_rtl)}")
    print(f"accepted_sha256={sha256(accepted_rtl)}")
    print(f"paired_seed_count={len(baseline_rows)}")
    print(f"score={composite['estimate']:.12f}")
    print(
        "score_ci95="
        f"[{composite['ci95_low']:.12f}, {composite['ci95_high']:.12f}]"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError) as exc:
        print(f"Evidence verification: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
