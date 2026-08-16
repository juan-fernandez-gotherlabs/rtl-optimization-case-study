#!/usr/bin/env python3
"""Generate INT8 report macros from the public certificate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report/latex/generated/metrics.tex"


def improvement(ratio: float) -> float:
    return 100.0 * (1.0 - ratio)


def main() -> int:
    data = json.loads((ROOT / "certificate.json").read_text(encoding="utf-8"))
    baseline = data["summary"]["baseline"]
    optimized = data["summary"]["optimized"]
    ratios = data["summary"]["paired_ratio"]
    macros: dict[str, str] = {
        "BaselineHash": data["rtl"]["baseline_sha256"],
        "OptimizedHash": data["rtl"]["optimized_sha256"],
        "CertificateHash": hashlib.sha256((ROOT / "certificate.json").read_bytes()).hexdigest(),
        "BaselineArea": f'{baseline["area_total_mwta"]:,.0f}',
        "OptimizedArea": f'{optimized["area_total_mwta"]:,.0f}',
        "BaselineDelay": f'{baseline["critical_path_delay_ns"]:.4f}',
        "OptimizedDelay": f'{optimized["critical_path_delay_ns"]:.4f}',
        "BaselineFmax": f'{baseline["fmax_mhz"]:.4f}',
        "OptimizedFmax": f'{optimized["fmax_mhz"]:.4f}',
        "BaselinePower": f'{1000.0 * baseline["active_total_power_w"]:.4f}',
        "OptimizedPower": f'{1000.0 * optimized["active_total_power_w"]:.4f}',
        "OptimizedScore": f'{data["summary"]["score"]:.6f}',
        "CompositeImprovement": f'{100.0 * data["summary"]["improvement"]:.4f}',
        "FunctionalTests": str(data["correctness"]["functional_test_count"]),
        "CertificationPairs": str(data["measurement"]["certification_pair_count"]),
        "SearchPairs": str(data["measurement"]["search_pair_count"]),
    }
    for label, metric in (
        ("Area", "area_total_mwta"),
        ("Delay", "critical_path_delay_ns"),
        ("Power", "active_total_power_w"),
        ("Composite", "composite"),
    ):
        item = ratios[metric]
        macros[f"{label}Improvement"] = f'{improvement(item["estimate"]):.4f}'
        macros[f"{label}Low"] = f'{improvement(item["ci95_two_sided"][1]):.4f}'
        macros[f"{label}High"] = f'{improvement(item["ci95_two_sided"][0]):.4f}'
        macros[f"{label}Wins"] = str(item["wins"])
        macros[f"{label}Losses"] = str(item["losses"])
    lines = ["% Generated from certificate.json. Do not edit by hand."]
    lines.extend(rf"\newcommand{{\{name}}}{{{value}}}" for name, value in sorted(macros.items()))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"generated={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
