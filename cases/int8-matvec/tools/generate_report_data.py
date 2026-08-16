#!/usr/bin/env python3
"""Generate all INT8 report inputs from the public compact certificate."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "latex" / "generated"
PRIMARY = ("area_total_mwta", "critical_path_delay_ns", "active_total_power_w")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def improvement(ratio: float) -> float:
    return 100.0 * (1.0 - ratio)


def geometric_mean(values: list[float]) -> float:
    return math.exp(statistics.mean(math.log(value) for value in values))


def ci_values(item: dict) -> tuple[float, float, float]:
    estimate = improvement(float(item["estimate"]))
    low = improvement(float(item["ci95_two_sided"][1]))
    high = improvement(float(item["ci95_two_sided"][0]))
    return estimate, low, high


def main() -> int:
    data = json.loads((ROOT / "certificate.json").read_text(encoding="utf-8"))
    rows = data["pairs"]
    if len(rows) != 64:
        raise SystemExit("certification evidence is not an exact 64-pair sample")
    OUT.mkdir(parents=True, exist_ok=True)

    paired = data["summary"]["paired_ratio"]
    confidence_rows = {
        "Area": paired["area_total_mwta"],
        "Timing": paired["critical_path_delay_ns"],
        "Power": paired["active_total_power_w"],
        "Composite": paired["composite"],
    }
    with (OUT / "executive-ci.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("x", "estimate", "plus", "minus"),
            lineterminator="\n",
        )
        writer.writeheader()
        for x, name in enumerate(("Area", "Timing", "Power", "Composite"), 1):
            estimate, low, high = ci_values(confidence_rows[name])
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
    with (OUT / "pair-clouds.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["pair", "jitter"]
        for side in ("baseline", "optimized"):
            fields.extend(f"{side}_{name}" for name in ("area", "timing", "power", "composite"))
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for index, row in enumerate(rows, 1):
            output = {
                "pair": row["pair_id"],
                "jitter": f"{((index * 37) % 83) / 83.0:.6f}",
            }
            for side in ("baseline", "optimized"):
                ratios = {
                    "area": float(row[side]["area_total_mwta"]) / baseline_reference["area_total_mwta"],
                    "timing": float(row[side]["critical_path_delay_ns"]) / baseline_reference["critical_path_delay_ns"],
                    "power": float(row[side]["active_total_power_w"]) / baseline_reference["active_total_power_w"],
                }
                ratios["composite"] = geometric_mean(list(ratios.values()))
                output.update(
                    {f"{side}_{name}": f"{improvement(value):.9f}" for name, value in ratios.items()}
                )
            writer.writerow(output)

    baseline = data["summary"]["baseline"]
    optimized = data["summary"]["optimized"]
    measurement = data["measurement"]
    evidence = data["independent_replay"]["source_evidence_sha256"]
    baseline_clb = max(int(row["baseline"]["clb_blocks"]) for row in rows)
    optimized_clb = max(int(row["optimized"]["clb_blocks"]) for row in rows)
    baseline_logic = max(int(row["baseline"]["logic_elements"]) for row in rows)
    optimized_logic = max(int(row["optimized"]["logic_elements"]) for row in rows)
    baseline_registers = max(int(row["baseline"]["registers"]) for row in rows)
    optimized_registers = max(int(row["optimized"]["registers"]) for row in rows)
    idle_ratio = geometric_mean(
        [float(row["optimized"]["idle_total_power_w"]) / float(row["baseline"]["idle_total_power_w"]) for row in rows]
    )
    per_pair_composite = []
    for row in rows:
        ratios = [float(row["optimized"][metric]) / float(row["baseline"][metric]) for metric in PRIMARY]
        per_pair_composite.append(geometric_mean(ratios))

    macros: dict[str, str] = {
        "EvidenceDate": "16 August 2026",
        "BaselineHash": data["rtl"]["baseline_sha256"],
        "OptimizedHash": data["rtl"]["optimized_sha256"],
        "CertificateHash": sha256(ROOT / "certificate.json"),
        "FunctionalTestHash": data["correctness"]["functional_test_set_sha256"],
        "ArchitectureHash": measurement["fpga_architecture"]["sha256"],
        "TechnologyHash": measurement["fpga_architecture"]["technology_sha256"],
        "BaselinePrimaryHash": evidence["baseline_primary"],
        "BaselineReplayHash": evidence["baseline_replay"],
        "OptimizedPrimaryHash": evidence["optimized_primary"],
        "OptimizedReplayHash": evidence["optimized_replay"],
        "BaselineArea": f'{baseline["area_total_mwta"]:,.0f}',
        "OptimizedArea": f'{optimized["area_total_mwta"]:,.0f}',
        "BaselineDelay": f'{baseline["critical_path_delay_ns"]:.4f}',
        "OptimizedDelay": f'{optimized["critical_path_delay_ns"]:.4f}',
        "BaselinePower": f'{1000.0 * baseline["active_total_power_w"]:.4f}',
        "OptimizedPower": f'{1000.0 * optimized["active_total_power_w"]:.4f}',
        "BaselineDynamic": f'{1000.0 * baseline["active_dynamic_power_w"]:.4f}',
        "OptimizedDynamic": f'{1000.0 * optimized["active_dynamic_power_w"]:.4f}',
        "BaselineStatic": f'{1000.0 * baseline["active_static_power_w"]:.4f}',
        "OptimizedStatic": f'{1000.0 * optimized["active_static_power_w"]:.4f}',
        "BaselineIdle": f'{1000.0 * baseline["idle_total_power_w"]:.4f}',
        "OptimizedIdle": f'{1000.0 * optimized["idle_total_power_w"]:.4f}',
        "IdleImprovement": f'{improvement(idle_ratio):.4f}',
        "BaselineFmax": f'{baseline["fmax_mhz"]:.4f}',
        "OptimizedFmax": f'{optimized["fmax_mhz"]:.4f}',
        "FmaxImprovement": f'{100.0 * (optimized["fmax_mhz"] / baseline["fmax_mhz"] - 1.0):.4f}',
        "BaselineClb": str(baseline_clb),
        "OptimizedClb": str(optimized_clb),
        "ClbImprovement": f'{improvement(optimized_clb / baseline_clb):.4f}',
        "BaselineLogic": str(baseline_logic),
        "OptimizedLogic": str(optimized_logic),
        "LogicImprovement": f'{improvement(optimized_logic / baseline_logic):.4f}',
        "BaselineRegisters": str(baseline_registers),
        "OptimizedRegisters": str(optimized_registers),
        "OptimizedScore": f'{data["summary"]["score"]:.6f}',
        "CompositeMedian": f'{statistics.median(per_pair_composite):.6f}',
        "CompositeImprovement": f'{100.0 * data["summary"]["improvement"]:.4f}',
        "FunctionalTests": str(data["correctness"]["functional_test_count"]),
        "CertificationPairs": str(measurement["certification_pair_count"]),
        "SearchPairs": str(measurement["search_pair_count"]),
        "ActivityCycles": f'{measurement["activity"]["cycles"]:,}',
    }
    for label, item in confidence_rows.items():
        estimate, low, high = ci_values(item)
        macros[f"{label}Improvement"] = f"{estimate:.4f}"
        macros[f"{label}Low"] = f"{low:.4f}"
        macros[f"{label}High"] = f"{high:.4f}"
        macros[f"{label}Wins"] = str(item["wins"])
        macros[f"{label}Ties"] = str(item["ties"])
        macros[f"{label}Losses"] = str(item["losses"])

    lines = ["% Generated from certificate.json. Do not edit by hand."]
    lines.extend(rf"\newcommand{{\{name}}}{{{value}}}" for name, value in sorted(macros.items()))
    (OUT / "metrics.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"generated={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
