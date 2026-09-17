#!/usr/bin/env python3
"""Extract a stable JSON summary from one Quartus compilation."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


class ParseError(RuntimeError):
    pass


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT.parents[1] / "cases" / "int8-matvec"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def first_number(text: str, patterns: tuple[str, ...], label: str) -> int:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return int(match.group(1).replace(",", ""))
    raise ParseError(f"could not find {label} in Quartus reports")


def optional_float(text: str, patterns: tuple[str, ...]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def power_watts(text: str, label: str) -> float | None:
    match = re.search(
        rf"{label}\s*:\s*([0-9.,]+)\s*(mW|W)", text, flags=re.IGNORECASE
    )
    if not match:
        return None
    value = float(match.group(1).replace(",", ""))
    watts = value / 1000.0 if match.group(2).lower() == "mw" else value
    return round(watts, 12)


def read_reports(run_dir: Path) -> tuple[str, str]:
    report_paths = (
        sorted(run_dir.glob("*.rpt"))
        + sorted(run_dir.glob("*.summary"))
        + sorted((run_dir / "output_files").glob("*.rpt"))
        + sorted((run_dir / "output_files").glob("*.summary"))
    )
    if not report_paths:
        raise ParseError(f"no Quartus reports found in {run_dir}")
    texts = []
    power_texts = []
    for path in report_paths:
        value = path.read_text(encoding="utf-8", errors="replace")
        texts.append(f"\n--- {path.name} ---\n{value}")
        if ".pow." in path.name or path.name.endswith(".pow.rpt"):
            power_texts.append(value)
    return "".join(texts), "\n".join(power_texts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--variant", required=True, choices=("baseline", "optimized"))
    parser.add_argument("--mapping", required=True, choices=("dsp_auto", "lut_only"))
    parser.add_argument("--family", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--period-ns", required=True, type=float)
    parser.add_argument("--quartus-version", required=True)
    parser.add_argument("--power-status", required=True, type=int)
    parser.add_argument("--fitter-seed", required=True, type=int)
    parser.add_argument("--threads", required=True, type=int)
    parser.add_argument("--execution-environment", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    text, power_text = read_reports(run_dir)

    logic_elements = first_number(
        text,
        (
            r"Total logic elements\s*:\s*([0-9,]+)",
            r"Logic utilization \(in ALMs\)\s*:\s*([0-9,]+)",
        ),
        "logic utilization",
    )
    registers = first_number(
        text,
        (
            r"Total registers\s*:\s*([0-9,]+)",
            r"Dedicated logic registers\s*:\s*([0-9,]+)",
        ),
        "register count",
    )
    embedded_multiplier_9bit_elements = first_number(
        text,
        (
            r"Embedded Multiplier 9-bit elements\s*[:;]\s*([0-9,]+)",
            r"DSP block 18-bit elements\s*:\s*([0-9,]+)",
        ),
        "embedded multiplier element count",
    )
    try:
        embedded_multiplier_blocks = first_number(
            text,
            (
                r"Total DSP Blocks\s*:\s*([0-9,]+)",
                r"Embedded Multiplier Blocks\s*;\s*([0-9,]+)",
            ),
            "physical embedded multiplier block count",
        )
    except ParseError:
        if embedded_multiplier_9bit_elements != 0:
            raise
        embedded_multiplier_blocks = 0

    fmax_mhz = optional_float(
        text,
        (
            r"Slow 1200mV 85C Model Fmax Summary[\s\S]*?;\s*([0-9.]+)\s*MHz\s*;\s*[0-9.]+\s*MHz\s*;\s*clk\s*;",
            r"([0-9.]+)\s*MHz[^\n]*\bclk\b",
        ),
    )
    wns_ns = optional_float(
        text,
        (
            r"Slow 1200mV 85C Model Setup 'clk'\s*Slack\s*:\s*(-?[0-9.]+)",
            r"Worst-case setup slack is\s*(-?[0-9.]+)",
        ),
    )
    hold_slack_ns = optional_float(
        text,
        (
            r"Slow 1200mV 85C Model Hold 'clk'\s*Slack\s*:\s*(-?[0-9.]+)",
            r"Worst-case hold slack is\s*(-?[0-9.]+)",
        ),
    )
    delay_ns = None if wns_ns is None else round(args.period_ns - wns_ns, 12)

    unconstrained_clocks = first_number(
        text, (r"Unconstrained Clocks\s*;\s*([0-9,]+)",), "unconstrained clock count"
    )
    unconstrained_input_ports = first_number(
        text,
        (r"Unconstrained Input Ports\s*;\s*([0-9,]+)",),
        "unconstrained input port count",
    )
    unconstrained_output_ports = first_number(
        text,
        (r"Unconstrained Output Ports\s*;\s*([0-9,]+)",),
        "unconstrained output port count",
    )

    total_w = power_watts(power_text, "Total Thermal Power Dissipation")
    dynamic_w = power_watts(power_text, "Core Dynamic Thermal Power Dissipation")
    static_w = power_watts(power_text, "Static Thermal Power Dissipation")
    dut = CASE_ROOT / "rtl" / args.variant / "int8_matvec_4x4.sv"
    wrapper = ROOT / "rtl" / "int8_matvec_registered_top.sv"
    payload = {
        "schema_version": 1,
        "status": "complete",
        "variant": args.variant,
        "mapping": args.mapping,
        "family": args.family,
        "device": args.device,
        "clock_period_ns": args.period_ns,
        "quartus_version": args.quartus_version,
        "fitter_seed": args.fitter_seed,
        "threads": args.threads,
        "execution_environment": args.execution_environment,
        "source_sha256": {
            "dut": sha256_file(dut),
            "wrapper": sha256_file(wrapper),
        },
        "resources": {
            "logic_elements": logic_elements,
            "registers": registers,
            "embedded_multiplier_blocks": embedded_multiplier_blocks,
            "embedded_multiplier_9bit_elements": embedded_multiplier_9bit_elements,
        },
        "timing": {
            "wns_ns": wns_ns,
            "hold_slack_ns": hold_slack_ns,
            "datapath_delay_ns": delay_ns,
            "estimated_fmax_mhz": fmax_mhz,
            "target_met": wns_ns is not None and wns_ns >= 0.0,
            "unconstrained_clocks": unconstrained_clocks,
            "unconstrained_input_ports": unconstrained_input_ports,
            "unconstrained_output_ports": unconstrained_output_ports,
            "method": "quartus_slow_1200mv_85c_post_fit",
        },
        "power": {
            "status": "complete" if args.power_status == 0 and total_w is not None else "unavailable",
            "method": "quartus_vectorless_estimate",
            "confidence": "low_insufficient_toggle_rate_data",
            "total_thermal_w": total_w,
            "core_dynamic_w": dynamic_w,
            "static_w": static_w,
        },
    }
    (run_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ParseError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
