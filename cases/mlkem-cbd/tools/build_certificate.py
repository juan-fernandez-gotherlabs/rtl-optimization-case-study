#!/usr/bin/env python3
"""Build the public ML-KEM CBD certificate from frozen source-domain records."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any


PRIMARY_METRICS = (
    "area_total_mwta",
    "critical_path_delay_ns",
    "active_total_power_w",
)
ONE_SIDED_T_95_DF63 = 1.6694022217068127
TWO_SIDED_T_95_DF63 = 1.9983405425207417


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def geometric_mean(values: list[float]) -> float:
    return math.exp(statistics.mean(math.log(value) for value in values))


def log_interval(values: list[float], critical: float) -> dict[str, float]:
    mean = statistics.mean(values)
    standard_error = statistics.stdev(values) / math.sqrt(len(values))
    lower = mean - critical * standard_error
    upper = mean + critical * standard_error
    return {
        "mean_log_ratio": mean,
        "standard_error": standard_error,
        "lower_log_ratio": lower,
        "upper_log_ratio": upper,
        "lower_improvement_percent": (1.0 - math.exp(upper)) * 100.0,
        "upper_improvement_percent": (1.0 - math.exp(lower)) * 100.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-domain", required=True, type=Path)
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    domain = args.source_domain.resolve()
    case = args.case_root.resolve()
    baseline = load_json(domain / "benchmarks/baseline_publication.json")
    optimized = load_json(domain / "evidence/publication_result.json")
    initial = load_json(domain / "evidence/result.json")
    protocol = load_json(domain / "benchmarks/publication_protocol.json")
    source_manifest = load_json(domain / "benchmarks/manifest.json")

    expected_seeds = protocol["publication_confirmation"]["seeds"]
    expected_evaluator = protocol["measurement"]["evaluator_version"]
    expected_image = protocol["measurement"]["image"]
    if baseline.get("valid") is not True:
        raise ValueError("publication baseline is not valid")
    if baseline.get("authority") != "frozen_baseline_measurement":
        raise ValueError("publication baseline has the wrong authority")
    if optimized.get("valid") is not True or optimized.get("tier") != "publication":
        raise ValueError("publication candidate record is not valid")
    if optimized.get("evidence_root") != "<SANITIZED_SOURCE_EVIDENCE_ROOT>":
        raise ValueError("publication candidate record exposes its execution path")
    if baseline.get("evaluator_version") != expected_evaluator:
        raise ValueError("baseline evaluator differs from the frozen protocol")
    if optimized.get("evaluator_version") != expected_evaluator:
        raise ValueError("optimized evaluator differs from the frozen protocol")
    if baseline.get("image") != expected_image:
        raise ValueError("baseline image differs from the frozen protocol")
    if optimized.get("acceptance_decision") not in {
        "evidence_improvement",
        "evidence_regression",
        "inconclusive",
    }:
        raise ValueError("optimized record has no recognized decision")
    if baseline.get("seeds") != expected_seeds:
        raise ValueError("baseline seed pool differs from prospective protocol")
    if [row["seed"] for row in optimized.get("per_seed", [])] != expected_seeds:
        raise ValueError("optimized seed pool differs from prospective protocol")
    if optimized.get("candidate_sha256") != protocol["candidate"]["sha256"]:
        raise ValueError("optimized RTL differs from frozen candidate")
    if baseline.get("candidate_sha256") != protocol["baseline"]["sha256"]:
        raise ValueError("baseline RTL differs from frozen baseline")

    baseline_rows = {int(row["seed"]): row for row in baseline["per_seed"]}
    optimized_rows = {int(row["seed"]): row for row in optimized["per_seed"]}
    metric_logs: dict[str, list[float]] = {metric: [] for metric in PRIMARY_METRICS}
    composite_logs: list[float] = []
    pairs: list[dict[str, Any]] = []
    for index, seed in enumerate(expected_seeds, 1):
        before = baseline_rows[seed]
        after = optimized_rows[seed]
        ratios = {
            metric: float(after[metric]) / float(before[metric])
            for metric in PRIMARY_METRICS
        }
        for metric, ratio in ratios.items():
            if not math.isfinite(ratio) or ratio <= 0.0:
                raise ValueError(f"invalid {metric} ratio for seed {seed}")
            metric_logs[metric].append(math.log(ratio))
        composite = math.exp(
            statistics.mean(math.log(value) for value in ratios.values())
        )
        composite_logs.append(math.log(composite))
        pairs.append(
            {
                "pair_id": f"publication-{index:02d}",
                "seed": seed,
                "baseline": {
                    key: before[key]
                    for key in (
                        *PRIMARY_METRICS,
                        "used_logic_area_mwta",
                        "routing_area_mwta",
                        "clb_count",
                    )
                },
                "optimized": {
                    key: after[key]
                    for key in (
                        *PRIMARY_METRICS,
                        "used_logic_area_mwta",
                        "routing_area_mwta",
                        "clb_count",
                    )
                },
                "ratio": {**ratios, "composite": composite},
            }
        )

    paired_ratio = {
        metric: math.exp(statistics.mean(values))
        for metric, values in metric_logs.items()
    }
    score = math.exp(statistics.mean(composite_logs))
    one_sided = {
        "composite": log_interval(composite_logs, ONE_SIDED_T_95_DF63),
        **{
            metric: log_interval(values, ONE_SIDED_T_95_DF63)
            for metric, values in metric_logs.items()
        },
    }
    two_sided = {
        "composite": log_interval(composite_logs, TWO_SIDED_T_95_DF63),
        **{
            metric: log_interval(values, TWO_SIDED_T_95_DF63)
            for metric, values in metric_logs.items()
        },
    }
    improvement = one_sided["composite"]["upper_log_ratio"] < 0.0 and all(
        one_sided[metric]["lower_log_ratio"] <= 0.0 for metric in PRIMARY_METRICS
    )
    regression = one_sided["composite"]["lower_log_ratio"] > 0.0 or any(
        one_sided[metric]["lower_log_ratio"] > 0.0 for metric in PRIMARY_METRICS
    )
    decision = (
        "evidence_improvement"
        if improvement
        else ("evidence_regression" if regression else "inconclusive")
    )
    if optimized["acceptance_decision"] != decision:
        raise ValueError("recomputed decision differs from the evaluator record")
    if optimized.get("certified") is not True:
        raise ValueError("publication evaluator did not certify the fixed pool")

    def aggregates(rows: dict[int, dict[str, Any]]) -> dict[str, float]:
        result = {
            metric: geometric_mean(
                [float(rows[seed][metric]) for seed in expected_seeds]
            )
            for metric in PRIMARY_METRICS
        }
        result["clb_count"] = statistics.median(
            float(rows[seed]["clb_count"]) for seed in expected_seeds
        )
        return result

    baseline_rtl = case / "rtl/baseline/cbd.v"
    optimized_rtl = case / "rtl/optimized/cbd.v"
    patch = case / "rtl/changes.patch"
    license_path = case / "LICENSE"
    correctness = optimized["correctness"]
    initial_certification = initial["certification"]
    certificate = {
        "schema_version": 1,
        "case_id": "mlkem-cbd-vtr45",
        "authority": "prospectively_frozen_64_pair_publication_confirmation",
        "status": "accepted" if decision == "evidence_improvement" else decision,
        "decision": decision,
        "source": {
            "project": source_manifest["benchmark"]["name"],
            "repository": source_manifest["benchmark"]["source_url"],
            "commit": source_manifest["benchmark"]["upstream_commit"],
            "path": source_manifest["benchmark"]["upstream_path"],
            "upstream_sha256": source_manifest["benchmark"]["upstream_sha256"],
            "license": source_manifest["benchmark"]["license"],
            "license_sha256": sha256(license_path),
        },
        "rtl": {
            "module": "CBD",
            "interface": "CBD(clk, rst, load, start, eta[1:0], scnd, in_shake[1087:0], end_op, en_write, data_in_1[23:0], data_in_2[23:0], addr_1[7:0], addr_2[7:0])",
            "baseline": {"path": "rtl/baseline/cbd.v", "sha256": sha256(baseline_rtl)},
            "optimized": {
                "path": "rtl/optimized/cbd.v",
                "sha256": sha256(optimized_rtl),
            },
            "patch": {"path": "rtl/changes.patch", "sha256": sha256(patch)},
        },
        "correctness": {
            "functional_passed": correctness["cycle_regression"] == "pass",
            "functional_cycles": correctness["cycles"],
            "functional_checks": correctness["checks"],
            "formal_passed": correctness["formal_status"] == "pass",
            "formal_scope": correctness["formal_engine"],
            "formal_tool": "EQY v0.67-1-g6734d8c",
            "synthesis_tool": "Yosys 0.55 (git 60f126cd0)",
            "simulation_tool": "Verilator 5.020",
            "cycle_test_sha256": source_manifest["correctness"][
                "cycle_regression_sha256"
            ],
            "formal_config_sha256": source_manifest["correctness"][
                "equivalence_config_sha256"
            ],
        },
        "measurement": {
            "publication_pair_count": len(expected_seeds),
            "publication_seeds": expected_seeds,
            "pools_disjoint": True,
            "protocol_sha256": sha256(domain / "benchmarks/publication_protocol.json"),
            "evaluator_sha256": source_manifest["publication_confirmation"][
                "evaluator_sha256"
            ],
            "baseline_record_sha256": sha256(
                domain / "benchmarks/baseline_publication.json"
            ),
            "optimized_record_sha256": sha256(
                domain / "evidence/publication_result.json"
            ),
            "protocol_frozen_at_utc": protocol["frozen_at_utc"],
            "evaluator_version": baseline["evaluator_version"],
            "toolchain": {
                "image": baseline["image"],
                "image_id": source_manifest["toolchain"]["image_id"],
                "vtr_commit": "95f5c6de9e158371ba7185bf97c07a84153735d6",
                "architecture": baseline["architecture"],
                "architecture_sha256": source_manifest["toolchain"][
                    "architecture_sha256"
                ],
                "technology": baseline["technology"],
                "technology_sha256": source_manifest["toolchain"]["technology_sha256"],
                "platform": source_manifest["toolchain"]["platform"],
                "network": source_manifest["toolchain"]["network"],
                "cpu_limit": source_manifest["toolchain"]["cpu_limit"],
                "memory_limit_gib": source_manifest["toolchain"]["memory_limit_gib"],
            },
            "activity": baseline["activity"],
        },
        "score_definition": {
            "primary_metrics": list(PRIMARY_METRICS),
            "formula": "equal-weight geometric mean of paired optimized/baseline area, delay, and active-total-power ratios",
            "direction": "lower_is_better",
            "acceptance_rule": "composite one-sided 95% upper log-ratio bound < 0 and no primary metric one-sided 95% lower log-ratio bound > 0",
        },
        "pairs": pairs,
        "summary": {
            "baseline": aggregates(baseline_rows),
            "optimized": aggregates(optimized_rows),
            "paired_ratio": {**paired_ratio, "composite": score},
            "improvement_percent": {
                **{
                    metric: (1.0 - ratio) * 100.0
                    for metric, ratio in paired_ratio.items()
                },
                "composite": (1.0 - score) * 100.0,
                "fmax": (1.0 / paired_ratio["critical_path_delay_ns"] - 1.0) * 100.0,
                "clb": (
                    1.0
                    - aggregates(optimized_rows)["clb_count"]
                    / aggregates(baseline_rows)["clb_count"]
                )
                * 100.0,
            },
            "confidence": {
                "acceptance_one_sided_95": one_sided,
                "descriptive_two_sided_95": two_sided,
            },
        },
        "prior_confirmation": {
            "role": "initial fixed 12-pair result observed before the publication protocol",
            "candidate_sha256": initial["candidate_sha256"],
            "pair_count": len(initial_certification["seeds"]),
            "score": initial_certification["score"],
            "improvement_percent": initial_certification["improvement_percent"],
            "result_sha256": sha256(domain / "evidence/result.json"),
        },
        "claim_boundary": [
            "relative academic VTR/PTM45 FPGA estimates under the exact published contract",
            "ACE probabilistic activity estimate rather than application-workload energy",
            "not ASIC signoff, commercial-FPGA characterization, board measurement, or manufactured-silicon evidence",
            "not side-channel analysis or certification of the complete ML-KEM implementation",
            "project-contract certification rather than accredited or third-party certification",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(certificate, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"decision={decision}")
    print(f"pairs={len(pairs)}")
    print(f"score={score:.12f}")
    print(f"improvement={(1.0 - score) * 100.0:.6f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
