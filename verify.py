#!/usr/bin/env python3
"""Verify the published RTL comparison using only the Python standard library."""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "results" / "certification.json"
PRIMARY_METRICS = ("area_total_mwta", "critical_path_delay_ns", "active_total_power_w")
SECONDARY_METRICS = ("energy_per_block_nj",)
TWO_SIDED_T_95_DF63 = 1.9983405425207417
ONE_SIDED_T_95_DF63 = 1.6694022215079607


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(actual: float, expected: float, tolerance: float = 5e-12) -> None:
    if not math.isclose(actual, expected, rel_tol=tolerance, abs_tol=tolerance):
        raise AssertionError(f"value mismatch: {actual!r} != {expected!r}")


def confidence(log_values: list[float]) -> dict[str, float]:
    if len(log_values) != 64:
        raise AssertionError(f"expected 64 paired values, got {len(log_values)}")
    mean = statistics.mean(log_values)
    error = statistics.stdev(log_values) / math.sqrt(len(log_values))
    return {
        "estimate": math.exp(mean),
        "low": math.exp(mean - TWO_SIDED_T_95_DF63 * error),
        "high": math.exp(mean + TWO_SIDED_T_95_DF63 * error),
        "one_sided_high": math.exp(mean + ONE_SIDED_T_95_DF63 * error),
    }


def verify_checksums() -> None:
    seen: set[str] = set()
    for line in (ROOT / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if relative in seen:
            raise AssertionError(f"duplicate checksum entry: {relative}")
        seen.add(relative)
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise AssertionError(f"checksum mismatch: {relative}")


def verify_patch() -> None:
    baseline_path = ROOT / "rtl" / "baseline" / "sha.v"
    accepted_path = ROOT / "rtl" / "accepted" / "sha.v"
    generated = "".join(
        difflib.unified_diff(
            baseline_path.read_text(encoding="utf-8").splitlines(keepends=True),
            accepted_path.read_text(encoding="utf-8").splitlines(keepends=True),
            fromfile="rtl/baseline/sha.v",
            tofile="rtl/accepted/sha.v",
        )
    )
    published = (ROOT / "rtl" / "baseline-to-accepted.patch").read_text(encoding="utf-8")
    if generated != published:
        raise AssertionError("published patch does not match the two RTL files")


def main() -> int:
    verify_checksums()
    verify_patch()
    data = json.loads(RESULT.read_text(encoding="utf-8"))

    baseline_path = ROOT / "rtl" / "baseline" / "sha.v"
    accepted_path = ROOT / "rtl" / "accepted" / "sha.v"
    assert sha256(baseline_path) == data["source"]["corrected_baseline_sha256"]
    assert sha256(accepted_path) == data["source"]["accepted_rtl_sha256"]
    assert data["result"] == "accepted"
    assert data["contract"]["formal_status"] == "pass"
    assert data["contract"]["nist_short_long_cases"] == 129
    assert all(data["correctness"].values())

    rows = data["per_seed"]
    seeds = [int(row["seed"]) for row in rows]
    assert seeds == data["contract"]["seeds"]
    assert len(seeds) == len(set(seeds)) == data["contract"]["seed_count"] == 64

    metric_logs: dict[str, list[float]] = {}
    for metric in (*PRIMARY_METRICS, *SECONDARY_METRICS):
        baseline_values = [float(row["baseline"][metric]) for row in rows]
        accepted_values = [float(row["accepted"][metric]) for row in rows]
        close(statistics.median(baseline_values), data["summary"]["baseline"][metric])
        close(statistics.median(accepted_values), data["summary"]["accepted"][metric])

        logs = [math.log(accepted / baseline) for baseline, accepted in zip(baseline_values, accepted_values)]
        metric_logs[metric] = logs
        calculated = confidence(logs)
        published = data["summary"]["paired_ratio"][metric]
        close(calculated["estimate"], published["estimate"])
        close(calculated["low"], published["ci95_two_sided"][0])
        close(calculated["high"], published["ci95_two_sided"][1])

        comparisons = [accepted < baseline for baseline, accepted in zip(baseline_values, accepted_values)]
        ties = [accepted == baseline for baseline, accepted in zip(baseline_values, accepted_values)]
        assert sum(comparisons) == published["wins"]
        assert sum(ties) == published["ties"]
        assert len(rows) - sum(comparisons) - sum(ties) == published["losses"]

    composite_logs = [
        statistics.mean(metric_logs[metric][index] for metric in PRIMARY_METRICS)
        for index in range(len(rows))
    ]
    composite = confidence(composite_logs)
    published_composite = data["summary"]["paired_ratio"]["composite"]
    close(composite["estimate"], data["summary"]["accepted"]["score"])
    close(composite["estimate"], published_composite["estimate"])
    close(composite["low"], published_composite["ci95_two_sided"][0])
    close(composite["high"], published_composite["ci95_two_sided"][1])
    assert tuple(data["score_definition"]["primary_metrics"]) == PRIMARY_METRICS
    assert data["score_definition"]["formula"] == (
        "geometric_mean(area_ratio, critical_path_delay_ratio, active_total_power_ratio)"
    )
    assert all(data["summary"]["paired_ratio"][metric]["ci95_two_sided"][1] < 1.0 for metric in PRIMARY_METRICS)
    assert composite["one_sided_high"] < 1.0

    improvement = 100.0 * (1.0 - composite["estimate"])
    low_improvement = 100.0 * (1.0 - composite["high"])
    high_improvement = 100.0 * (1.0 - composite["low"])
    print("Verification: PASS")
    print(f"paired_seeds={len(rows)}")
    print(f"composite_score={composite['estimate']:.12f}")
    print(f"improvement={improvement:.2f}% (95% CI {low_improvement:.2f}% to {high_improvement:.2f}%)")
    print(f"formal_status={data['contract']['formal_status']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, ValueError, OSError) as exc:
        print(f"Verification: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
