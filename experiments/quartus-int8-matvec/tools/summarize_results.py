#!/usr/bin/env python3
"""Validate and combine the four Quartus run summaries."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any


RUNS = (
    ("baseline", "dsp_auto"),
    ("optimized", "dsp_auto"),
    ("baseline", "lut_only"),
    ("optimized", "lut_only"),
)
RESOURCE_KEYS = (
    "logic_elements",
    "registers",
    "embedded_multiplier_blocks",
    "embedded_multiplier_9bit_elements",
)
TIMING_KEYS = ("wns_ns", "datapath_delay_ns", "estimated_fmax_mhz")
POWER_KEYS = ("total_thermal_w", "core_dynamic_w", "static_w")


class SummaryError(RuntimeError):
    pass


def format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f} percent"


def load_run(root: Path, variant: str, mapping: str) -> dict[str, Any]:
    path = root / variant / mapping / "summary.json"
    if not path.is_file():
        raise SummaryError(f"missing run summary: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("status") != "complete":
        raise SummaryError(f"incomplete or unknown summary schema: {path}")
    if data.get("variant") != variant or data.get("mapping") != mapping:
        raise SummaryError(f"run identity mismatch: {path}")
    for section, keys in (
        ("resources", RESOURCE_KEYS),
        ("timing", TIMING_KEYS),
        ("power", POWER_KEYS),
    ):
        if not isinstance(data.get(section), dict):
            raise SummaryError(f"missing {section} section: {path}")
        for key in keys:
            if key not in data[section]:
                raise SummaryError(f"missing {section}.{key}: {path}")
    return data


def reduction(baseline: float | int | None, optimized: float | int | None) -> float | None:
    if baseline in (None, 0) or optimized is None:
        return None
    return round(100.0 * (baseline - optimized) / baseline, 12)


def improvement(baseline: float | int | None, optimized: float | int | None) -> float | None:
    if baseline in (None, 0) or optimized is None:
        return None
    return round(100.0 * (optimized - baseline) / baseline, 12)


def compare(mapping: str, baseline: dict[str, Any], optimized: dict[str, Any]) -> dict[str, Any]:
    return {
        "mapping": mapping,
        "resource_reduction_percent": {
            key: reduction(baseline["resources"][key], optimized["resources"][key])
            for key in RESOURCE_KEYS
        },
        "timing": {
            "datapath_delay_reduction_percent": reduction(
                baseline["timing"]["datapath_delay_ns"],
                optimized["timing"]["datapath_delay_ns"],
            ),
            "estimated_fmax_improvement_percent": improvement(
                baseline["timing"]["estimated_fmax_mhz"],
                optimized["timing"]["estimated_fmax_mhz"],
            ),
            "wns_delta_ns": (
                None
                if baseline["timing"]["wns_ns"] is None or optimized["timing"]["wns_ns"] is None
                else round(
                    optimized["timing"]["wns_ns"] - baseline["timing"]["wns_ns"],
                    12,
                )
            ),
        },
        "power": {
            f"{key}_reduction_percent": reduction(
                baseline["power"][key], optimized["power"][key]
            )
            for key in POWER_KEYS
        },
    }


def validate_contract(runs: list[dict[str, Any]]) -> None:
    reference = runs[0]
    for run in runs[1:]:
        for key in (
            "family",
            "device",
            "clock_period_ns",
            "quartus_version",
            "fitter_seed",
            "threads",
            "execution_environment",
        ):
            if run[key] != reference[key]:
                raise SummaryError(
                    f"mixed run contract for {key}: {reference[key]!r} != {run[key]!r}"
                )


def write_csv(path: Path, runs_by_id: dict[tuple[str, str], dict[str, Any]]) -> None:
    fieldnames = [
        "variant", "mapping", "family", "device", "quartus_version", "clock_period_ns",
        *RESOURCE_KEYS, *TIMING_KEYS, *POWER_KEYS,
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for identity in RUNS:
            run = runs_by_id[identity]
            row = {key: run[key] for key in fieldnames[:6]}
            row.update(run["resources"])
            row.update({key: run["timing"][key] for key in TIMING_KEYS})
            row.update({key: run["power"][key] for key in POWER_KEYS})
            writer.writerow(row)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        raise SummaryError("usage: summarize_results.py <output_root>")
    root = Path(args[0]).expanduser().resolve()
    runs_by_id = {identity: load_run(root, *identity) for identity in RUNS}
    runs = [runs_by_id[identity] for identity in RUNS]
    validate_contract(runs)
    comparisons = [
        compare(mapping, runs_by_id[("baseline", mapping)], runs_by_id[("optimized", mapping)])
        for mapping in ("dsp_auto", "lut_only")
    ]
    combined = {
        "schema_version": 1,
        "status": "complete",
        "contract": {
            "family": runs[0]["family"],
            "device": runs[0]["device"],
            "clock_period_ns": runs[0]["clock_period_ns"],
            "quartus_version": runs[0]["quartus_version"],
            "fitter_seed": runs[0]["fitter_seed"],
            "threads": runs[0]["threads"],
            "execution_environment": runs[0]["execution_environment"],
            "timing_corner": "slow_1200mv_85c_post_fit",
        },
        "runs": runs,
        "comparisons": comparisons,
        "claim_boundary": (
            "Quartus implementation evidence for the exact device, tool version, constraints, "
            "wrapper, and mapping mode; not board measurement or a cross-vendor comparison."
        ),
    }
    (root / "summary.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_csv(root / "summary.csv", runs_by_id)
    for comparison in comparisons:
        print(f"{comparison['mapping']}:")
        print(
            "  logic-element reduction: "
            f"{format_percent(comparison['resource_reduction_percent']['logic_elements'])}"
        )
        print(
            "  physical multiplier-block reduction: "
            f"{format_percent(comparison['resource_reduction_percent']['embedded_multiplier_blocks'])}"
        )
        print(
            "  Fmax improvement: "
            f"{format_percent(comparison['timing']['estimated_fmax_improvement_percent'])}"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, json.JSONDecodeError, SummaryError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
