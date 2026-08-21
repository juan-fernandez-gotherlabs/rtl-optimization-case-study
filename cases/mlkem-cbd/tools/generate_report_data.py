#!/usr/bin/env python3
"""Generate deterministic LaTeX inputs from the ML-KEM CBD certificate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "report/latex/generated"
PRIMARY = ("area_total_mwta", "critical_path_delay_ns", "active_total_power_w")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def improvement(ratio: float) -> float:
    return 100.0 * (1.0 - ratio)


def geometric_mean(values: list[float]) -> float:
    return math.exp(statistics.mean(math.log(value) for value in values))


def metric_macro(name: str, value: str) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


def outcome_counts(rows: list[dict], key: str) -> tuple[int, int, int]:
    values = [float(row["ratio"][key]) for row in rows]
    return (
        sum(value < 1.0 for value in values),
        sum(value == 1.0 for value in values),
        sum(value > 1.0 for value in values),
    )


def main() -> int:
    data = json.loads((ROOT / "certificate.json").read_text(encoding="utf-8"))
    full_evidence = json.loads((ROOT / "full-evidence.json").read_text(encoding="utf-8"))
    summary = data["summary"]
    before = summary["baseline"]
    after = summary["optimized"]
    paired = summary["paired_ratio"]
    improvements = summary["improvement_percent"]
    descriptive = summary["confidence"]["descriptive_two_sided_95"]
    acceptance = summary["confidence"]["acceptance_one_sided_95"]
    initial = data["prior_confirmation"]
    measurement = data["measurement"]
    rows = data["pairs"]
    if len(rows) != 64:
        raise SystemExit("publication evidence is not an exact 64-pair sample")
    GENERATED.mkdir(parents=True, exist_ok=True)

    labels = {
        "Area": "area_total_mwta",
        "Timing": "critical_path_delay_ns",
        "Power": "active_total_power_w",
        "Composite": "composite",
    }
    with (GENERATED / "executive-ci.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("x", "estimate", "plus", "minus"),
            lineterminator="\n",
        )
        writer.writeheader()
        for x, (label, key) in enumerate(labels.items(), 1):
            estimate = improvement(float(paired[key]))
            low = float(descriptive[key]["lower_improvement_percent"])
            high = float(descriptive[key]["upper_improvement_percent"])
            writer.writerow(
                {
                    "x": x,
                    "estimate": f"{estimate:.9f}",
                    "plus": f"{high - estimate:.9f}",
                    "minus": f"{estimate - low:.9f}",
                }
            )

    baseline_reference = {
        metric: geometric_mean([float(row["baseline"][metric]) for row in rows])
        for metric in PRIMARY
    }
    with (GENERATED / "pair-clouds.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fields = ["pair", "jitter"]
        for side in ("baseline", "optimized"):
            fields.extend(
                f"{side}_{name}" for name in ("area", "timing", "power", "composite")
            )
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for index, row in enumerate(rows, 1):
            output: dict[str, str] = {
                "pair": row["pair_id"],
                "jitter": f"{((index * 37) % 83) / 83.0:.6f}",
            }
            for side in ("baseline", "optimized"):
                ratios = {
                    "area": float(row[side]["area_total_mwta"])
                    / baseline_reference["area_total_mwta"],
                    "timing": float(row[side]["critical_path_delay_ns"])
                    / baseline_reference["critical_path_delay_ns"],
                    "power": float(row[side]["active_total_power_w"])
                    / baseline_reference["active_total_power_w"],
                }
                ratios["composite"] = geometric_mean(list(ratios.values()))
                output.update(
                    {
                        f"{side}_{name}": f"{improvement(value):.9f}"
                        for name, value in ratios.items()
                    }
                )
            writer.writerow(output)

    per_pair_composite = [float(row["ratio"]["composite"]) for row in rows]
    used_logic_before = geometric_mean(
        [float(row["baseline"]["used_logic_area_mwta"]) for row in rows]
    )
    used_logic_after = geometric_mean(
        [float(row["optimized"]["used_logic_area_mwta"]) for row in rows]
    )
    routing_before = geometric_mean(
        [float(row["baseline"]["routing_area_mwta"]) for row in rows]
    )
    routing_after = geometric_mean(
        [float(row["optimized"]["routing_area_mwta"]) for row in rows]
    )

    macros = {
        "EvidenceDate": "21 August 2026",
        "AreaHigh": f"{descriptive['area_total_mwta']['upper_improvement_percent']:.4f}",
        "AreaImprovement": f"{improvements['area_total_mwta']:.4f}",
        "AreaLow": f"{descriptive['area_total_mwta']['lower_improvement_percent']:.4f}",
        "AreaAcceptanceLow": f"{acceptance['area_total_mwta']['lower_improvement_percent']:.4f}",
        "BaselineArea": f"{before['area_total_mwta']:,.0f}",
        "BaselineClb": f"{before['clb_count']:.0f}",
        "BaselineDelay": f"{before['critical_path_delay_ns']:.4f}",
        "BaselineFmax": f"{1000.0 / before['critical_path_delay_ns']:.4f}",
        "BaselineHash": data["rtl"]["baseline"]["sha256"],
        "BaselinePower": f"{before['active_total_power_w'] * 1000.0:.3f}",
        "BaselineRecordHash": measurement["baseline_record_sha256"],
        "BaselineRoutingArea": f"{routing_before:,.0f}",
        "BaselineUsedLogicArea": f"{used_logic_before:,.0f}",
        "CertificateHash": sha256(ROOT / "certificate.json"),
        "ClbImprovement": f"{improvements['clb']:.4f}",
        "CompositeAcceptanceLow": f"{acceptance['composite']['lower_improvement_percent']:.4f}",
        "CompositeHigh": f"{descriptive['composite']['upper_improvement_percent']:.4f}",
        "CompositeImprovement": f"{improvements['composite']:.4f}",
        "CompositeLow": f"{descriptive['composite']['lower_improvement_percent']:.4f}",
        "CompositeMedian": f"{statistics.median(per_pair_composite):.6f}",
        "CompositeScore": f"{paired['composite']:.6f}",
        "CycleTestHash": data["correctness"]["cycle_test_sha256"],
        "DelayHigh": f"{descriptive['critical_path_delay_ns']['upper_improvement_percent']:.4f}",
        "DelayImprovement": f"{improvements['critical_path_delay_ns']:.4f}",
        "DelayLow": f"{descriptive['critical_path_delay_ns']['lower_improvement_percent']:.4f}",
        "DelayAcceptanceLow": f"{acceptance['critical_path_delay_ns']['lower_improvement_percent']:.4f}",
        "EvaluatorHash": measurement["evaluator_sha256"],
        "EvidenceArchiveHash": full_evidence["archive_sha256"],
        "EvidenceArchiveMembers": str(full_evidence["member_count"]),
        "EvidenceArchiveName": full_evidence["asset_name"].replace("_", r"\_"),
        "FmaxImprovement": f"{improvements['fmax']:.4f}",
        "FormalConfigHash": data["correctness"]["formal_config_sha256"],
        "FunctionalChecks": str(data["correctness"]["functional_checks"]),
        "FunctionalCycles": str(data["correctness"]["functional_cycles"]),
        "InitialImprovement": f"{initial['improvement_percent']:.4f}",
        "InitialPairCount": str(initial["pair_count"]),
        "OptimizedArea": f"{after['area_total_mwta']:,.0f}",
        "OptimizedClb": f"{after['clb_count']:.0f}",
        "OptimizedDelay": f"{after['critical_path_delay_ns']:.4f}",
        "OptimizedFmax": f"{1000.0 / after['critical_path_delay_ns']:.4f}",
        "OptimizedHash": data["rtl"]["optimized"]["sha256"],
        "OptimizedPower": f"{after['active_total_power_w'] * 1000.0:.3f}",
        "OptimizedRecordHash": measurement["optimized_record_sha256"],
        "OptimizedRoutingArea": f"{routing_after:,.0f}",
        "OptimizedUsedLogicArea": f"{used_logic_after:,.0f}",
        "PairCount": str(measurement["publication_pair_count"]),
        "PatchHash": data["rtl"]["patch"]["sha256"],
        "PowerHigh": f"{descriptive['active_total_power_w']['upper_improvement_percent']:.4f}",
        "PowerImprovement": f"{improvements['active_total_power_w']:.4f}",
        "PowerLow": f"{descriptive['active_total_power_w']['lower_improvement_percent']:.4f}",
        "PowerAcceptanceLow": f"{acceptance['active_total_power_w']['lower_improvement_percent']:.4f}",
        "ProtocolHash": measurement["protocol_sha256"],
        "SourceCommit": data["source"]["commit"],
        "SourceUpstreamHash": data["source"]["upstream_sha256"],
        "TechnologyHash": measurement["toolchain"]["technology_sha256"],
        "ArchitectureHash": measurement["toolchain"]["architecture_sha256"],
        "UsedLogicImprovement": f"{improvement(used_logic_after / used_logic_before):.4f}",
    }
    for label, key in labels.items():
        wins, ties, losses = outcome_counts(rows, key)
        macros[f"{label}Wins"] = str(wins)
        macros[f"{label}Ties"] = str(ties)
        macros[f"{label}Losses"] = str(losses)

    (GENERATED / "metrics.tex").write_text(
        "% Generated from certificate.json and full-evidence.json. Do not edit by hand.\n"
        + "".join(metric_macro(name, value) for name, value in sorted(macros.items())),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
