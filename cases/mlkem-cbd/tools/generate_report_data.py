#!/usr/bin/env python3
"""Generate deterministic LaTeX inputs from the ML-KEM CBD certificate."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "report/latex/generated"


def metric_macro(name: str, value: str) -> str:
    return f"\\newcommand{{\\{name}}}{{{value}}}\n"


def main() -> int:
    data = json.loads((ROOT / "certificate.json").read_text(encoding="utf-8"))
    summary = data["summary"]
    before = summary["baseline"]
    after = summary["optimized"]
    improvement = summary["improvement_percent"]
    ratio = summary["paired_ratio"]
    ci = summary["confidence"]["descriptive_two_sided_95"]
    initial = data["prior_confirmation"]
    GENERATED.mkdir(parents=True, exist_ok=True)
    macros = {
        "BaselineArea": f"{before['area_total_mwta']:,.0f}",
        "OptimizedArea": f"{after['area_total_mwta']:,.0f}",
        "AreaImprovement": f"{improvement['area_total_mwta']:.3f}",
        "BaselineDelay": f"{before['critical_path_delay_ns']:.4f}",
        "OptimizedDelay": f"{after['critical_path_delay_ns']:.4f}",
        "DelayImprovement": f"{improvement['critical_path_delay_ns']:.3f}",
        "BaselinePower": f"{before['active_total_power_w'] * 1000.0:.3f}",
        "OptimizedPower": f"{after['active_total_power_w'] * 1000.0:.3f}",
        "PowerImprovement": f"{improvement['active_total_power_w']:.3f}",
        "CompositeScore": f"{ratio['composite']:.6f}",
        "CompositeImprovement": f"{improvement['composite']:.3f}",
        "FmaxImprovement": f"{improvement['fmax']:.3f}",
        "BaselineClb": f"{before['clb_count']:.0f}",
        "OptimizedClb": f"{after['clb_count']:.0f}",
        "ClbImprovement": f"{improvement['clb']:.3f}",
        "CompositeLow": f"{ci['composite']['lower_improvement_percent']:.3f}",
        "CompositeHigh": f"{ci['composite']['upper_improvement_percent']:.3f}",
        "AreaLow": f"{ci['area_total_mwta']['lower_improvement_percent']:.3f}",
        "AreaHigh": f"{ci['area_total_mwta']['upper_improvement_percent']:.3f}",
        "DelayLow": f"{ci['critical_path_delay_ns']['lower_improvement_percent']:.3f}",
        "DelayHigh": f"{ci['critical_path_delay_ns']['upper_improvement_percent']:.3f}",
        "PowerLow": f"{ci['active_total_power_w']['lower_improvement_percent']:.3f}",
        "PowerHigh": f"{ci['active_total_power_w']['upper_improvement_percent']:.3f}",
        "PairCount": str(data["measurement"]["publication_pair_count"]),
        "FunctionalCycles": str(data["correctness"]["functional_cycles"]),
        "FunctionalChecks": str(data["correctness"]["functional_checks"]),
        "InitialPairCount": str(initial["pair_count"]),
        "InitialImprovement": f"{initial['improvement_percent']:.3f}",
        "BaselineHash": data["rtl"]["baseline"]["sha256"],
        "OptimizedHash": data["rtl"]["optimized"]["sha256"],
        "CertificateHash": hashlib.sha256(
            (ROOT / "certificate.json").read_bytes()
        ).hexdigest(),
    }
    (GENERATED / "metrics.tex").write_text(
        "".join(metric_macro(name, value) for name, value in sorted(macros.items())),
        encoding="utf-8",
    )
    with (GENERATED / "executive-ci.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            ("metric", "estimate_improvement_percent", "lower_95", "upper_95")
        )
        for label, key in (
            ("Composite", "composite"),
            ("Area", "area_total_mwta"),
            ("Delay", "critical_path_delay_ns"),
            ("Power", "active_total_power_w"),
        ):
            writer.writerow(
                (
                    label,
                    f"{(1.0 - ratio[key]) * 100.0:.12f}",
                    f"{ci[key]['lower_improvement_percent']:.12f}",
                    f"{ci[key]['upper_improvement_percent']:.12f}",
                )
            )
    with (GENERATED / "pair-clouds.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            (
                "pair",
                "seed",
                "area_ratio",
                "delay_ratio",
                "power_ratio",
                "composite_ratio",
            )
        )
        for pair in data["pairs"]:
            writer.writerow(
                (
                    pair["pair_id"],
                    pair["seed"],
                    f"{pair['ratio']['area_total_mwta']:.12f}",
                    f"{pair['ratio']['critical_path_delay_ns']:.12f}",
                    f"{pair['ratio']['active_total_power_w']:.12f}",
                    f"{pair['ratio']['composite']:.12f}",
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
