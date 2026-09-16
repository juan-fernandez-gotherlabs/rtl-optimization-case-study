#!/usr/bin/env python3
"""Run static checks that do not require Quartus."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT.parents[1] / "cases" / "int8-matvec"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def test_summarizer() -> None:
    with tempfile.TemporaryDirectory(prefix="quartus-summary-test-") as temporary:
        output = Path(temporary)
        for variant in ("baseline", "optimized"):
            for mapping in ("dsp_auto", "lut_only"):
                run_dir = output / variant / mapping
                run_dir.mkdir(parents=True)
                optimized = variant == "optimized"
                payload = {
                    "schema_version": 1,
                    "status": "complete",
                    "variant": variant,
                    "mapping": mapping,
                    "family": "MAX 10",
                    "device": "10M50DAF484C7G",
                    "clock_period_ns": 5.0,
                    "quartus_version": "Version 25.1std.0",
                    "resources": {
                        "logic_elements": 90 if optimized else 100,
                        "registers": 288,
                        "embedded_multiplier_blocks": 8 if mapping == "dsp_auto" else 0,
                        "embedded_multiplier_9bit_elements": 16 if mapping == "dsp_auto" else 0,
                    },
                    "timing": {
                        "wns_ns": 0.2 if optimized else 0.1,
                        "datapath_delay_ns": 4.8 if optimized else 4.9,
                        "estimated_fmax_mhz": 208.333 if optimized else 204.082,
                        "target_met": True,
                        "unconstrained_clocks": 0,
                        "unconstrained_input_ports": 160,
                        "unconstrained_output_ports": 128,
                        "method": "quartus_fmax_summary",
                    },
                    "power": {
                        "status": "complete",
                        "method": "quartus_vectorless_estimate",
                        "confidence": "low_insufficient_toggle_rate_data",
                        "total_thermal_w": 0.95 if optimized else 1.0,
                        "core_dynamic_w": 0.45 if optimized else 0.5,
                        "static_w": 0.5,
                    },
                }
                (run_dir / "summary.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "summarize_results.py"), str(output)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        combined = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        require(len(combined["runs"]) == 4, "summarizer did not preserve all runs")
        require(
            combined["comparisons"][0]["resource_reduction_percent"]["logic_elements"] == 10.0,
            "wrong logic-element reduction",
        )


def main() -> int:
    required = (
        CASE_ROOT / "rtl" / "baseline" / "int8_matvec_4x4.sv",
        CASE_ROOT / "rtl" / "optimized" / "int8_matvec_4x4.sv",
        ROOT / "rtl" / "int8_matvec_registered_top.sv",
        ROOT / "tools" / "run_matrix.py",
        ROOT / "tools" / "parse_run.py",
    )
    for path in required:
        require(path.is_file(), f"missing required file: {path}")
    runner = (ROOT / "tools" / "run_matrix.py").read_text(encoding="utf-8")
    for token in (
        "dsp_auto", "lut_only", "AUTO_DSP_RECOGNITION", "quartus_sh",
        "quartus_pow", "10M50DAF484C7G", "VIRTUAL_PIN",
    ):
        require(token in runner, f"Quartus flow is missing required operation: {token}")
    test_summarizer()
    print("Quartus transfer flow static checks: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Quartus transfer flow static checks: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
