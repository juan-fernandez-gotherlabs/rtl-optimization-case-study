#!/usr/bin/env python3
"""Run the frozen four-leg Quartus Prime Lite transfer matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT.parents[1] / "cases" / "int8-matvec"
RUNS = (
    ("baseline", "dsp_auto"),
    ("optimized", "dsp_auto"),
    ("baseline", "lut_only"),
    ("optimized", "lut_only"),
)
DATA_PORT_WIDTHS = {
    "x0": 8, "x1": 8, "x2": 8, "x3": 8,
    "w00": 8, "w01": 8, "w02": 8, "w03": 8,
    "w10": 8, "w11": 8, "w12": 8, "w13": 8,
    "w20": 8, "w21": 8, "w22": 8, "w23": 8,
    "w30": 8, "w31": 8, "w32": 8, "w33": 8,
    "y0": 32, "y1": 32, "y2": 32, "y3": 32,
}
DEFAULT_FITTER_SEED = 1
DEFAULT_THREADS = 4


def positive_number(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def positive_integer(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_executable(value: str, label: str) -> str:
    if "/" in value:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"{label} executable not found: {path}")
        return str(path)
    resolved = shutil.which(value)
    if resolved is None:
        raise FileNotFoundError(
            f"{label} executable '{value}' is not on PATH; pass its absolute path"
        )
    return resolved


def qsf_quote(path: Path, *, relative_to: Path) -> str:
    value = os.path.relpath(path.resolve(), relative_to.resolve())
    value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{value}"'


def write_project(
    run_dir: Path,
    *,
    variant: str,
    mapping: str,
    family: str,
    device: str,
    period_ns: float,
    fitter_seed: int,
    threads: int,
) -> str:
    project = f"int8_{variant}_{mapping}"
    dut = CASE_ROOT / "rtl" / variant / "int8_matvec_4x4.sv"
    wrapper = ROOT / "rtl" / "int8_matvec_registered_top.sv"
    for path in (dut, wrapper):
        if not path.is_file():
            raise FileNotFoundError(f"missing RTL input: {path}")

    sdc = run_dir / f"{project}.sdc"
    sdc.write_text(
        "# Fixed register-to-register timing boundary.\n"
        f"create_clock -name clk -period {period_ns:.9f} [get_ports {{clk}}]\n"
        "set_clock_uncertainty -rise_from [get_clocks {clk}] "
        "-rise_to [get_clocks {clk}] 0.100\n",
        encoding="utf-8",
    )

    dsp_setting = "ON" if mapping == "dsp_auto" else "OFF"
    qsf_lines = [
        f'set_global_assignment -name FAMILY "{family}"',
        f"set_global_assignment -name DEVICE {device}",
        "set_global_assignment -name TOP_LEVEL_ENTITY int8_matvec_registered_top",
        f"set_global_assignment -name SYSTEMVERILOG_FILE {qsf_quote(dut, relative_to=run_dir)}",
        f"set_global_assignment -name SYSTEMVERILOG_FILE {qsf_quote(wrapper, relative_to=run_dir)}",
        f"set_global_assignment -name SDC_FILE {qsf_quote(sdc, relative_to=run_dir)}",
        "set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files",
        f"set_global_assignment -name NUM_PARALLEL_PROCESSORS {threads}",
        f"set_global_assignment -name SEED {fitter_seed}",
        "set_location_assignment PIN_M8 -to clk",
        'set_instance_assignment -name IO_STANDARD "3.3-V LVTTL" -to clk',
        f"set_global_assignment -name AUTO_DSP_RECOGNITION {dsp_setting}",
        f"set_instance_assignment -name AUTO_DSP_RECOGNITION {dsp_setting} -to dut",
    ]
    if mapping == "lut_only":
        # AUTO_DSP_RECOGNITION=OFF alone does not prevent Quartus Standard
        # from mapping inferred multipliers into MAX 10 DSP blocks.  The
        # family-supported balancing assignment forces those slices into LEs.
        qsf_lines.append(
            'set_global_assignment -name DSP_BLOCK_BALANCING "LOGIC ELEMENTS"'
        )
    # Quartus 25.1 Standard rejects a braced bus wildcard here as a literal
    # node name.  Emit exact bit names, matching the syntax in Altera's own
    # installed qdesign examples, so every boundary signal is unambiguous.
    qsf_lines.extend(
        f"set_instance_assignment -name VIRTUAL_PIN ON -to {port}[{bit}]"
        for port, width in DATA_PORT_WIDTHS.items()
        for bit in range(width)
    )
    (run_dir / f"{project}.qsf").write_text("\n".join(qsf_lines) + "\n", encoding="utf-8")
    (run_dir / f"{project}.qpf").write_text(
        f"PROJECT_REVISION = {project}\n", encoding="utf-8"
    )
    return project


def run_logged(command: list[str], *, cwd: Path, log_path: Path, check: bool) -> int:
    with log_path.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, command)
    return result.returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quartus-sh", default="quartus_sh")
    parser.add_argument("--quartus-pow", default="quartus_pow")
    parser.add_argument("--family", default="MAX 10")
    parser.add_argument("--device", default="10M50DAF484C7G")
    parser.add_argument("--period-ns", type=positive_number, default=5.0)
    parser.add_argument("--fitter-seed", type=positive_integer, default=DEFAULT_FITTER_SEED)
    parser.add_argument("--threads", type=positive_integer, default=DEFAULT_THREADS)
    parser.add_argument(
        "--execution-environment",
        default="unspecified",
        help="stable provenance label such as native_x86_64 or colima_qemu_x86_64",
    )
    parser.add_argument("--output-root", type=Path, default=ROOT / "output")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="reuse a completed summary.json for a matching matrix leg",
    )
    return parser.parse_args(argv)


def can_resume(
    summary_path: Path,
    *,
    variant: str,
    mapping: str,
    family: str,
    device: str,
    period_ns: float,
    dut_sha256: str,
    wrapper_sha256: str,
    fitter_seed: int,
    threads: int,
    execution_environment: str,
) -> bool:
    if not summary_path.is_file():
        return False
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return (
        payload.get("status") == "complete"
        and payload.get("variant") == variant
        and payload.get("mapping") == mapping
        and payload.get("family") == family
        and payload.get("device") == device
        and payload.get("clock_period_ns") == period_ns
        and payload.get("source_sha256", {}).get("dut") == dut_sha256
        and payload.get("source_sha256", {}).get("wrapper") == wrapper_sha256
        and payload.get("fitter_seed") == fitter_seed
        and payload.get("threads") == threads
        and payload.get("execution_environment") == execution_environment
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    quartus_sh = resolve_executable(args.quartus_sh, "quartus_sh")
    quartus_pow = resolve_executable(args.quartus_pow, "quartus_pow")
    output_root = args.output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    version_text = subprocess.run(
        [quartus_sh, "--version"],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ).stdout.strip()
    version_lines = [line.strip() for line in version_text.splitlines() if line.strip()]
    version = next(
        (line.removeprefix("Version ") for line in version_lines if line.startswith("Version ")),
        version_lines[0],
    )
    print(f"Quartus: {version}")
    print(f"Device: {args.device} ({args.family})")
    print(f"Clock period: {args.period_ns:.3f} ns")

    for variant, mapping in RUNS:
        run_dir = output_root / variant / mapping
        run_dir.mkdir(parents=True, exist_ok=True)
        summary_path = run_dir / "summary.json"
        dut_sha256 = sha256_file(
            CASE_ROOT / "rtl" / variant / "int8_matvec_4x4.sv"
        )
        wrapper_sha256 = sha256_file(
            ROOT / "rtl" / "int8_matvec_registered_top.sv"
        )
        if args.resume and can_resume(
            summary_path,
            variant=variant,
            mapping=mapping,
            family=args.family,
            device=args.device,
            period_ns=args.period_ns,
            dut_sha256=dut_sha256,
            wrapper_sha256=wrapper_sha256,
            fitter_seed=args.fitter_seed,
            threads=args.threads,
            execution_environment=args.execution_environment,
        ):
            print(f"\nReusing completed {variant}/{mapping} ...", flush=True)
            continue
        project = write_project(
            run_dir,
            variant=variant,
            mapping=mapping,
            family=args.family,
            device=args.device,
            period_ns=args.period_ns,
            fitter_seed=args.fitter_seed,
            threads=args.threads,
        )
        print(f"\nRunning {variant}/{mapping} ...", flush=True)
        run_logged(
            [quartus_sh, "--flow", "compile", project],
            cwd=run_dir,
            log_path=run_dir / "quartus_compile.log",
            check=True,
        )
        power_status = run_logged(
            [quartus_pow, project, "--read_settings_files=on", "--write_settings_files=off"],
            cwd=run_dir,
            log_path=run_dir / "quartus_power.log",
            check=False,
        )
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "parse_run.py"),
                str(run_dir),
                "--variant", variant,
                "--mapping", mapping,
                "--family", args.family,
                "--device", args.device,
                "--period-ns", f"{args.period_ns:.9f}",
                "--quartus-version", version,
                "--power-status", str(power_status),
                "--fitter-seed", str(args.fitter_seed),
                "--threads", str(args.threads),
                "--execution-environment", args.execution_environment,
            ],
            check=True,
        )

    subprocess.run(
        [sys.executable, str(ROOT / "tools" / "summarize_results.py"), str(output_root)],
        check=True,
    )
    metadata = {
        "quartus_version": version,
        "family": args.family,
        "device": args.device,
        "clock_period_ns": args.period_ns,
        "fitter_seed": args.fitter_seed,
        "threads": args.threads,
        "execution_environment": args.execution_environment,
        "timing_corner": "slow_1200mv_85c_post_fit",
        "source_sha256": {
            "baseline": sha256_file(
                CASE_ROOT / "rtl" / "baseline" / "int8_matvec_4x4.sv"
            ),
            "optimized": sha256_file(
                CASE_ROOT / "rtl" / "optimized" / "int8_matvec_4x4.sv"
            ),
            "wrapper": sha256_file(
                ROOT / "rtl" / "int8_matvec_registered_top.sv"
            ),
        },
    }
    (output_root / "run_contract.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"\nComplete matrix: {output_root / 'summary.json'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
