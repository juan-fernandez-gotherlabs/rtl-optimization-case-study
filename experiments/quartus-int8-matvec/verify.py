#!/usr/bin/env python3
"""Verify the compact and report-level Quartus transfer evidence."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
CASE_ROOT = ROOT.parents[1] / "cases" / "int8-matvec"
EVIDENCE = ROOT / "evidence" / "quartus-lite-25.1std-max10"
RESULT = ROOT / "results" / "quartus-lite-25.1std-max10-summary.json"
RUNS = (
    ("baseline", "dsp_auto"),
    ("optimized", "dsp_auto"),
    ("baseline", "lut_only"),
    ("optimized", "lut_only"),
)


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing JSON file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def public_files() -> set[str]:
    return {
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.relative_to(ROOT).as_posix() != "SHA256SUMS"
        and not any(
            part == "__pycache__"
            or part == "output"
            or part.startswith("output-")
            for part in path.relative_to(ROOT).parts
        )
        and path.name != ".DS_Store"
    }


def verify_package_manifest() -> None:
    path = ROOT / "SHA256SUMS"
    require(path.is_file(), "missing experiment SHA256SUMS")
    seen: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\n]+)", line)
        require(match is not None, f"malformed SHA256SUMS line {line_number}")
        expected, relative = match.groups()
        pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts, f"unsafe path: {relative}")
        require(relative not in seen, f"duplicate checksum path: {relative}")
        seen[relative] = expected
    require(set(seen) == public_files(), "experiment checksum coverage differs")
    for relative, expected in seen.items():
        require(sha256(ROOT / relative) == expected, f"checksum mismatch: {relative}")


def verify_evidence_manifest() -> None:
    manifest = load_json(EVIDENCE / "MANIFEST.json")
    require(manifest.get("schema_version") == 1, "wrong evidence manifest schema")
    require(
        manifest.get("experiment") == "quartus-int8-matvec-max10-transfer-v1",
        "wrong evidence identity",
    )
    entries = manifest.get("files")
    require(isinstance(entries, list) and entries, "empty evidence manifest")
    expected_paths = {
        path.relative_to(EVIDENCE).as_posix()
        for path in EVIDENCE.rglob("*")
        if path.is_file() and path.name not in {"MANIFEST.json", "SHA256SUMS"}
    }
    seen: set[str] = set()
    for entry in entries:
        require(isinstance(entry, dict), "malformed evidence entry")
        relative = entry.get("path")
        require(isinstance(relative, str), "evidence entry has no path")
        pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts, f"unsafe evidence path: {relative}")
        require(relative not in seen, f"duplicate evidence path: {relative}")
        seen.add(relative)
        path = EVIDENCE / relative
        require(path.is_file(), f"missing evidence file: {relative}")
        require(path.stat().st_size == entry.get("size_bytes"), f"size mismatch: {relative}")
        require(sha256(path) == entry.get("sha256"), f"evidence checksum mismatch: {relative}")
    require(seen == expected_paths, "evidence manifest coverage differs")


def run_command(command: list[str], *, cwd: Path) -> None:
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode != 0:
        raise VerificationError(
            f"command failed: {' '.join(command)}\n{result.stdout}{result.stderr}"
        )


def verify_result_and_reports() -> dict[str, Any]:
    published = load_json(RESULT)
    require(published == load_json(EVIDENCE / "summary.json"), "result snapshot differs from evidence")
    contract = published.get("contract", {})
    require(contract.get("family") == "MAX 10", "wrong FPGA family")
    require(contract.get("device") == "10M50DAF484C7G", "wrong FPGA device")
    require(contract.get("clock_period_ns") == 5.0, "wrong clock period")
    require(contract.get("fitter_seed") == 1, "wrong fitter seed")
    require(contract.get("threads") == 4, "wrong thread count")
    require(
        contract.get("execution_environment") == "apple_silicon_colima_qemu_x86_64",
        "wrong execution environment",
    )

    runs = published.get("runs")
    require(isinstance(runs, list) and len(runs) == 4, "expected four complete runs")
    runs_by_id = {(run.get("variant"), run.get("mapping")): run for run in runs}
    require(set(runs_by_id) == set(RUNS), "run matrix is incomplete or duplicated")
    source_hashes = {
        "baseline": sha256(CASE_ROOT / "rtl/baseline/int8_matvec_4x4.sv"),
        "optimized": sha256(CASE_ROOT / "rtl/optimized/int8_matvec_4x4.sv"),
    }
    wrapper_hash = sha256(ROOT / "rtl/int8_matvec_registered_top.sv")

    with tempfile.TemporaryDirectory(prefix="quartus-evidence-verify-") as temporary:
        regenerated = Path(temporary) / "runs"
        for variant, mapping in RUNS:
            expected = runs_by_id[(variant, mapping)]
            require(expected.get("status") == "complete", f"incomplete run: {variant}/{mapping}")
            require(expected["source_sha256"]["dut"] == source_hashes[variant], f"DUT hash mismatch: {variant}")
            require(expected["source_sha256"]["wrapper"] == wrapper_hash, "wrapper hash mismatch")
            require(expected["power"]["confidence"] == "low_insufficient_toggle_rate_data", "power confidence drift")
            require(expected["timing"]["target_met"] is False, "unexpected 200 MHz closure claim")
            source_run = EVIDENCE / variant / mapping
            compile_log = (source_run / "quartus_compile.log").read_text(encoding="utf-8")
            power_log = (source_run / "quartus_power.log").read_text(encoding="utf-8")
            require("Quartus Prime Full Compilation was successful. 0 errors" in compile_log, f"compile did not pass: {variant}/{mapping}")
            require("Quartus Prime Power Analyzer was successful. 0 errors" in power_log, f"power analysis did not pass: {variant}/{mapping}")
            destination_run = regenerated / variant / mapping
            shutil.copytree(source_run, destination_run)
            run_command(
                [
                    sys.executable,
                    str(ROOT / "tools/parse_run.py"),
                    str(destination_run),
                    "--variant", variant,
                    "--mapping", mapping,
                    "--family", expected["family"],
                    "--device", expected["device"],
                    "--period-ns", str(expected["clock_period_ns"]),
                    "--quartus-version", expected["quartus_version"],
                    "--power-status", "0",
                    "--fitter-seed", str(expected["fitter_seed"]),
                    "--threads", str(expected["threads"]),
                    "--execution-environment", expected["execution_environment"],
                ],
                cwd=ROOT,
            )
            require(load_json(destination_run / "summary.json") == expected, f"report extraction mismatch: {variant}/{mapping}")
        run_command(
            [sys.executable, str(ROOT / "tools/summarize_results.py"), str(regenerated)],
            cwd=ROOT,
        )
        require(load_json(regenerated / "summary.json") == published, "combined result does not recompute")

    dsp_baseline = runs_by_id[("baseline", "dsp_auto")]
    dsp_optimized = runs_by_id[("optimized", "dsp_auto")]
    lut_baseline = runs_by_id[("baseline", "lut_only")]
    lut_optimized = runs_by_id[("optimized", "lut_only")]
    require(dsp_baseline["resources"]["embedded_multiplier_blocks"] == 8, "wrong baseline DSP count")
    require(dsp_optimized["resources"]["embedded_multiplier_blocks"] == 8, "wrong optimized DSP count")
    require(lut_baseline["resources"]["embedded_multiplier_blocks"] == 0, "logic-only baseline uses DSP")
    require(lut_optimized["resources"]["embedded_multiplier_blocks"] == 0, "logic-only optimized uses DSP")
    require(dsp_optimized["timing"]["estimated_fmax_mhz"] > dsp_baseline["timing"]["estimated_fmax_mhz"], "DSP timing did not improve")
    require(lut_optimized["timing"]["estimated_fmax_mhz"] > lut_baseline["timing"]["estimated_fmax_mhz"], "logic-only timing did not improve")
    return published


def main() -> int:
    verify_package_manifest()
    verify_evidence_manifest()
    result = verify_result_and_reports()
    comparisons = {item["mapping"]: item for item in result["comparisons"]}
    print("Quartus INT8 MatVec compact evidence: PASS")
    print("rtl_hashes=PASS")
    print("runs=4")
    print(f"dsp_auto_fmax_improvement={comparisons['dsp_auto']['timing']['estimated_fmax_improvement_percent']:.4f}%")
    print(f"lut_only_fmax_improvement={comparisons['lut_only']['timing']['estimated_fmax_improvement_percent']:.4f}%")
    print("power_claim=NOT_SUPPORTED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VerificationError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Quartus INT8 MatVec compact evidence: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
