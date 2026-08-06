#!/usr/bin/env python3
"""Generate the numeric LaTeX inputs from the certified evidence records."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report" / "latex" / "generated"


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def improvement(ratio: float) -> float:
    return 100.0 * (1.0 - ratio)


def ci_values(item: dict) -> tuple[float, float, float]:
    estimate = improvement(float(item["estimate"]))
    # Ratio order reverses when expressed as an improvement.
    low = improvement(float(item["ci95_two_sided"][1]))
    high = improvement(float(item["ci95_two_sided"][0]))
    return estimate, low, high


def tex_number(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def main() -> None:
    baseline = load("results/baseline-certification.json")
    accepted = load("results/accepted-certification.json")
    netlist = load("results/netlist-seed20-summary.json")
    OUT.mkdir(parents=True, exist_ok=True)

    base_by_seed = {int(row["seed"]): row for row in baseline["per_seed"]}
    accepted_by_seed = {int(row["seed"]): row for row in accepted["per_seed"]}
    if set(base_by_seed) != set(accepted_by_seed) or len(base_by_seed) != 64:
        raise SystemExit("certification evidence is not an exact 64-seed pair")

    with (OUT / "paired-improvements.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("seed", "jitter", "area", "timing", "energy", "composite"),
            lineterminator="\n",
        )
        writer.writeheader()
        for seed in sorted(base_by_seed):
            base = base_by_seed[seed]
            cand = accepted_by_seed[seed]
            ratios = {
                "area": float(cand["area_total_mwta"]) / float(base["area_total_mwta"]),
                "timing": float(cand["critical_path_delay_ns"]) / float(base["critical_path_delay_ns"]),
                "energy": float(cand["energy_per_block_nj"]) / float(base["energy_per_block_nj"]),
            }
            ratios["composite"] = math.exp(statistics.mean(math.log(value) for value in ratios.values()))
            writer.writerow(
                {
                    "seed": seed,
                    "jitter": f"{((seed * 37) % 83) / 83.0:.6f}",
                    **{name: f"{improvement(value):.9f}" for name, value in ratios.items()},
                }
            )

    baseline_medians = {
        "area": float(baseline["aggregate"]["area_total_mwta"]["median"]),
        "timing": float(baseline["aggregate"]["critical_path_delay_ns"]["median"]),
        "energy": float(baseline["aggregate"]["energy_per_block_nj"]["median"]),
    }
    with (OUT / "seed-clouds.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "seed",
                "jitter",
                "baseline_area",
                "accepted_area",
                "baseline_timing",
                "accepted_timing",
                "baseline_energy",
                "accepted_energy",
                "baseline_composite",
                "accepted_composite",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        for seed in sorted(base_by_seed):
            base = base_by_seed[seed]
            accepted_row = accepted_by_seed[seed]
            baseline_ratios = {
                "area": float(base["area_total_mwta"]) / baseline_medians["area"],
                "timing": float(base["critical_path_delay_ns"]) / baseline_medians["timing"],
                "energy": float(base["energy_per_block_nj"]) / baseline_medians["energy"],
            }
            accepted_ratios = {
                "area": float(accepted_row["area_total_mwta"]) / baseline_medians["area"],
                "timing": float(accepted_row["critical_path_delay_ns"]) / baseline_medians["timing"],
                "energy": float(accepted_row["energy_per_block_nj"]) / baseline_medians["energy"],
            }
            baseline_ratios["composite"] = math.exp(
                statistics.mean(math.log(value) for value in baseline_ratios.values())
            )
            accepted_ratios["composite"] = math.exp(
                statistics.mean(math.log(value) for value in accepted_ratios.values())
            )
            writer.writerow(
                {
                    "seed": seed,
                    "jitter": f"{((seed * 37) % 83) / 83.0:.6f}",
                    **{f"baseline_{name}": f"{improvement(value):.9f}" for name, value in baseline_ratios.items()},
                    **{f"accepted_{name}": f"{improvement(value):.9f}" for name, value in accepted_ratios.items()},
                }
            )

    confidence = accepted["statistical_confidence"]
    confidence_rows = {
        "Area": confidence["metrics"]["area_total_mwta"],
        "Timing": confidence["metrics"]["critical_path_delay_ns"],
        "Energy": confidence["metrics"]["energy_per_block_nj"],
        "Composite": confidence["composite"],
    }
    with (OUT / "executive-ci.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("x", "estimate", "plus", "minus"),
            lineterminator="\n",
        )
        writer.writeheader()
        for x, item in enumerate(confidence_rows.values(), 1):
            estimate, low, high = ci_values(item)
            writer.writerow(
                {
                    "x": x,
                    "estimate": f"{estimate:.9f}",
                    "plus": f"{high - estimate:.9f}",
                    "minus": f"{estimate - low:.9f}",
                }
            )
    macros: dict[str, str] = {
        "EvidenceDate": "5 August 2026",
        "BaselineHash": sha256(ROOT / "rtl" / "baseline" / "sha.v"),
        "AcceptedHash": sha256(ROOT / "rtl" / "accepted" / "sha.v"),
        "BaselineArea": f'{baseline["aggregate"]["area_total_mwta"]["median"]:,.0f}',
        "AcceptedArea": f'{accepted["metrics"]["area_total_mwta"]:,.0f}',
        "BaselineDelay": tex_number(baseline["aggregate"]["critical_path_delay_ns"]["median"], 4),
        "AcceptedDelay": tex_number(accepted["metrics"]["critical_path_delay_ns"], 5),
        "BaselineEnergy": tex_number(baseline["aggregate"]["energy_per_block_nj"]["median"], 4),
        "AcceptedEnergy": tex_number(accepted["metrics"]["energy_per_block_nj"], 4),
        "BaselineScore": "1.000000",
        "AcceptedScore": tex_number(accepted["metrics"]["score"], 6),
        "BaselineFmax": "66.6426",
        "AcceptedFmax": tex_number(accepted["metrics"]["fmax_mhz"], 4),
        "BaselinePower": "9.9125",
        "AcceptedPower": tex_number(1000.0 * accepted["metrics"]["active_total_power_w"], 4),
        "BaselineDynamic": "5.0713",
        "AcceptedDynamic": tex_number(1000.0 * accepted["metrics"]["active_dynamic_power_w"], 4),
        "BaselineStatic": "4.8394",
        "AcceptedStatic": tex_number(1000.0 * accepted["metrics"]["active_static_power_w"], 4),
        "BaselineIdle": "4.4670",
        "AcceptedIdle": tex_number(1000.0 * accepted["metrics"]["idle_total_power_w"], 4),
        "NetlistBaselineNames": str(netlist["baseline"]["abc_names_nodes"]),
        "NetlistAcceptedNames": str(netlist["accepted"]["abc_names_nodes"]),
        "NetlistBaselineClb": str(netlist["baseline"]["clb_blocks"]),
        "NetlistAcceptedClb": str(netlist["accepted"]["clb_blocks"]),
        "NetlistBaselineLevels": str(netlist["baseline"]["timing_graph_levels"]),
        "NetlistAcceptedLevels": str(netlist["accepted"]["timing_graph_levels"]),
        "NetlistNamesRatio": tex_number(netlist["accepted"]["abc_names_nodes"] / netlist["baseline"]["abc_names_nodes"], 6),
        "NetlistClbRatio": tex_number(netlist["accepted"]["clb_blocks"] / netlist["baseline"]["clb_blocks"], 6),
        "NetlistLevelsRatio": tex_number(netlist["accepted"]["timing_graph_levels"] / netlist["baseline"]["timing_graph_levels"], 6),
    }
    for prefix, item in confidence_rows.items():
        estimate, low, high = ci_values(item)
        macros[f"{prefix}Estimate"] = tex_number(estimate)
        macros[f"{prefix}Low"] = tex_number(low)
        macros[f"{prefix}High"] = tex_number(high)
        macros[f"{prefix}Minus"] = tex_number(estimate - low)
        macros[f"{prefix}Plus"] = tex_number(high - estimate)
        macros[f"{prefix}Wins"] = str(item["wins"])
        macros[f"{prefix}Ties"] = str(item["ties"])
        macros[f"{prefix}Losses"] = str(item["losses"])

    lines = ["% Generated by scripts/generate_latex_data.py. Do not edit by hand."]
    for name, value in sorted(macros.items()):
        lines.append(rf"\newcommand{{\{name}}}{{{value}}}")
    (OUT / "metrics.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
