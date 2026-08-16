#!/usr/bin/env python3
"""Generate all numeric LaTeX inputs from the compact public certification."""

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


def ci_values(item: dict) -> tuple[float, float, float]:
    estimate = improvement(float(item["estimate"]))
    low = improvement(float(item["ci95_two_sided"][1]))
    high = improvement(float(item["ci95_two_sided"][0]))
    return estimate, low, high


def median(rows: list[dict], side: str, metric: str) -> float:
    return statistics.median(float(row[side][metric]) for row in rows)


def main() -> None:
    data = json.loads((ROOT / "results/certification.json").read_text(encoding="utf-8"))
    rows = data["per_seed"]
    if len(rows) != 64:
        raise SystemExit("certification evidence is not an exact 64-seed pair")
    OUT.mkdir(parents=True, exist_ok=True)

    paired_names = {
        "area": "area_total_mwta",
        "timing": "critical_path_delay_ns",
        "power": "active_total_power_w",
        "energy": "energy_per_block_nj",
    }
    with (OUT / "paired-improvements.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("seed", "jitter", *paired_names, "composite"), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            ratios = {
                name: float(row["accepted"][metric]) / float(row["baseline"][metric])
                for name, metric in paired_names.items()
            }
            ratios["composite"] = math.exp(statistics.mean(math.log(ratios[name]) for name in ("area", "timing", "power")))
            writer.writerow(
                {
                    "seed": row["seed"],
                    "jitter": f"{((int(row['seed']) * 37) % 83) / 83.0:.6f}",
                    **{name: f"{improvement(value):.9f}" for name, value in ratios.items()},
                }
            )

    baseline_medians = {name: median(rows, "baseline", metric) for name, metric in paired_names.items()}
    with (OUT / "seed-clouds.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["seed", "jitter"]
        for side in ("baseline", "accepted"):
            fields.extend(f"{side}_{name}" for name in (*paired_names, "composite"))
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            output = {"seed": row["seed"], "jitter": f"{((int(row['seed']) * 37) % 83) / 83.0:.6f}"}
            for side in ("baseline", "accepted"):
                ratios = {
                    name: float(row[side][metric]) / baseline_medians[name]
                    for name, metric in paired_names.items()
                }
                ratios["composite"] = math.exp(statistics.mean(math.log(ratios[name]) for name in ("area", "timing", "power")))
                output.update({f"{side}_{name}": f"{improvement(value):.9f}" for name, value in ratios.items()})
            writer.writerow(output)

    paired = data["summary"]["paired_ratio"]
    confidence_rows = {
        "Area": paired["area_total_mwta"],
        "Timing": paired["critical_path_delay_ns"],
        "Power": paired["active_total_power_w"],
        "Composite": paired["composite"],
        "Energy": paired["energy_per_block_nj"],
    }
    with (OUT / "executive-ci.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("x", "estimate", "plus", "minus"), lineterminator="\n")
        writer.writeheader()
        for x, name in enumerate(("Area", "Timing", "Power", "Composite"), 1):
            estimate, low, high = ci_values(confidence_rows[name])
            writer.writerow({"x": x, "estimate": f"{estimate:.9f}", "plus": f"{high-estimate:.9f}", "minus": f"{estimate-low:.9f}"})

    baseline = data["summary"]["baseline"]
    accepted = data["summary"]["accepted"]
    evidence = data["full_evidence"]
    macros: dict[str, str] = {
        "EvidenceDate": "9 August 2026",
        "BaselineHash": sha256(ROOT / "rtl/baseline/sha.v"),
        "AcceptedHash": sha256(ROOT / "rtl/accepted/sha.v"),
        "BaselineArea": f'{baseline["area_total_mwta"]:,.0f}',
        "AcceptedArea": f'{accepted["area_total_mwta"]:,.0f}',
        "BaselineDelay": f'{baseline["critical_path_delay_ns"]:.4f}',
        "AcceptedDelay": f'{accepted["critical_path_delay_ns"]:.4f}',
        "BaselinePower": f'{1000*baseline["active_total_power_w"]:.4f}',
        "AcceptedPower": f'{1000*accepted["active_total_power_w"]:.4f}',
        "BaselineEnergy": f'{baseline["energy_per_block_nj"]:.4f}',
        "AcceptedEnergy": f'{accepted["energy_per_block_nj"]:.4f}',
        "BaselineScore": "1.000000",
        "AcceptedScore": f'{accepted["score"]:.6f}',
        "AcceptedCompositeMedian": f'{accepted["composite_per_seed_median"]:.6f}',
        "BaselineFmax": f'{baseline["fmax_mhz"]:.4f}',
        "AcceptedFmax": f'{accepted["fmax_mhz"]:.4f}',
        "BaselineClb": f'{baseline["clb_blocks"]:.0f}',
        "AcceptedClb": f'{accepted["clb_blocks"]:.0f}',
        "BaselineRegisters": f'{baseline["registers"]:.0f}',
        "AcceptedRegisters": f'{accepted["registers"]:.0f}',
        "BaselineIdle": f'{1000*baseline["idle_total_power_w"]:.4f}',
        "AcceptedIdle": f'{1000*accepted["idle_total_power_w"]:.4f}',
        "EvidenceArchiveHash": evidence["archive_sha256"],
        "EvidenceArchiveBytes": f'{evidence["archive_bytes"]:,}',
        "CertificationRecordHash": evidence["certification_result_sha256"],
        "FormalDriverHash": evidence["formal_driver_log_sha256"],
        "EqyPassHash": data["contract"]["eqy_pass_marker_sha256"],
    }
    for prefix, item in confidence_rows.items():
        estimate, low, high = ci_values(item)
        macros[f"{prefix}Estimate"] = f"{estimate:.2f}"
        macros[f"{prefix}Low"] = f"{low:.2f}"
        macros[f"{prefix}High"] = f"{high:.2f}"
        macros[f"{prefix}Wins"] = str(item["wins"])
        macros[f"{prefix}Ties"] = str(item["ties"])
        macros[f"{prefix}Losses"] = str(item["losses"])

    lines = ["% Generated by scripts/generate_latex_data.py. Do not edit by hand."]
    for name, value in sorted(macros.items()):
        lines.append(rf"\newcommand{{\{name}}}{{{value}}}")
    (OUT / "metrics.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
