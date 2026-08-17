#!/usr/bin/env python3
"""Fail-closed verification of the public INT8 MatVec evidence package.

Without arguments this verifies the compact Git package and recomputes all
published statistics.  With ``--evidence-archive`` it additionally audits the
complete blinded raw VTR archive and re-extracts every published PPA row.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import re
import statistics
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "certificate.json"
FULL_EVIDENCE = ROOT / "full-evidence.json"
BUNDLE_ROOT = "int8-matvec-vtr45-full-evidence-v1"
PRIMARY = ("area_total_mwta", "critical_path_delay_ns", "active_total_power_w")
ROW_METRICS = (
    "area_total_mwta",
    "logic_block_area_mwta",
    "routing_area_mwta",
    "critical_path_delay_ns",
    "fmax_mhz",
    "active_total_power_w",
    "active_dynamic_power_w",
    "active_static_power_w",
    "idle_total_power_w",
    "clb_blocks",
    "logic_elements",
    "registers",
    "multiplier_blocks",
    "timing_channel_width",
)
TWO_SIDED_T_95_DF63 = 1.9983405425207417
ONE_SIDED_T_95_DF63 = 1.6694022217068127
HEX64 = re.compile(r"^[0-9a-f]{64}$")
CLAIM_BOUNDARY = "Blinded paired statistical certification using academic VTR PTM 45 nm post-route estimates; not physical, commercial FPGA, ASIC, silicon, board, signoff, measured-power, or measured-energy evidence."
FUNCTIONAL_TEST_SET_SHA256 = "87abb71f1542981919fb62e299e0c19ff4cfacae20f41d50d0a41756d345c513"
FORMAL_SCOPE = "Unbounded combinational equivalence of all four outputs for every 160-bit input assignment against the owned frozen baseline."
TOOLCHAIN = {
    "docker_image": "evolther-vtr-ppa45:95f5c6de-linux-amd64",
    "docker_image_id": "sha256:c0badc2d2bb57364ff37477b3d2c482ef01f7d3df6211e9802e2c54367c33baf",
    "network_during_evaluation": "disabled",
    "platform": "linux/amd64",
    "vtr_commit": "95f5c6de9e158371ba7185bf97c07a84153735d6",
}
FPGA_ARCHITECTURE = {
    "classification": "VTR academic homogeneous FPGA architecture",
    "lut_inputs": 6,
    "nominal_voltage_v": 0.9,
    "selection_rationale": "Use the exact non-fracturable LUT6 architecture and PTM point qualified by the repository's SHA-1 workflow.",
    "sha256": "262792caef81931ae09b77d252158bde03c78954175d4b761e6d437317575307",
    "technology_path": "vtr_flow/tech/PTM_45nm/45nm.xml",
    "technology_sha256": "3080dea13bf7134109f8a83c79426ec0965e07639a61866fe9ae4bd05b5227cb",
    "temperature_c": 85,
    "vtr_path": "vtr_flow/arch/power/k6_N10_I40_Fi6_L4_frac0_ff1_45nm.xml",
}
ACTIVITY = {
    "cycles": 2048,
    "profiles": [
        "active deterministic signed-INT8 extremes plus xorshift64 workload",
        "idle all-zero data with active clock",
    ],
    "workload_seed_hex": "0x1a184d475eed",
}
SCORE_FORMULA = "paired geometric mean of area, critical-path delay, and active-total-power ratios"
ACCEPTANCE_RULE = "Composite upper one-sided 95% bound < 1.0 and no primary metric lower one-sided 95% bound > 1.0."
VALIDITY_LIMITS = {
    "maximum_active_power_ratio": 2.0,
    "maximum_area_ratio": 2.0,
    "maximum_critical_path_ratio": 2.0,
    "maximum_logic_elements": 6000,
    "maximum_multiplier_blocks": 0,
    "maximum_multiplier_operand_width": 64,
}
SOURCE_EVIDENCE_SHA256 = {
    "baseline_primary": "bf4f024891eec15a19a22ff0ea0e4609bfa7613deb758681f864a7c2d2f158b7",
    "baseline_replay": "25efb7578ed201bab9b7bac6ae043821b583cd7e9143d2c4ad23ce02a065d8ec",
    "optimized_primary": "5f42601df61768be36b23594205c8d61d138bb4ed760443af0bbef0b43948a7d",
    "optimized_replay": "441b9da134214162176d16a79e740dc50c1cdb1c9a244e6a1fa640b906304a6d",
}
FLOW_SHA256 = {
    "flow/Dockerfile.vtr-ppa45-linux-amd64": "4ad557b059853351308ab4b9138be265b6328a34252fddc9c940dac3545f9327",
    "flow/activity_vectors.py": "118945c313b05bec478341c6adda7c110dc5026094dee66073bad0aa173d28cd",
    "flow/benchmark.py": "c3d5d703ceebe37b1df887c53af07314b6cbcd478b34daec5a7c28cad216b3a2",
    "flow/certification_contract.public.json": "84399097c4d40385907903ee41458c27d504e7fbaf375fb2bdcb8a32c4abafff",
    "flow/ppa_manifest.json": "9e64620a0a54e82a2c0fd1216f221b10d00b59dbcfda252478d12a7c66e51762",
    "flow/vtr_ppa.py": "ac6305d6aa4a2945bf51224035cc9926c1eba68275f6d79c125f516e9400bec8",
}
FUNCTIONAL_TESTBENCH_SHA256 = "78047436c27ae524b1614b303312def364313cf4ab8bcfa7ca5c48e2f64557ee"

REQUIRED_MANIFEST = {
    "LICENSE",
    "Makefile",
    "README.md",
    "certificate.json",
    "full-evidence.json",
    "report/latex/generated/executive-ci.csv",
    "report/latex/generated/metrics.tex",
    "report/latex/generated/pair-clouds.csv",
    "report/latex/technical-report.tex",
    "rtl/baseline/int8_matvec_4x4.sv",
    "rtl/changes.patch",
    "rtl/optimized/int8_matvec_4x4.sv",
    "technical-report.pdf",
    "tests/test_verify.py",
    "tools/generate_report_data.py",
    "tools/build_evidence_bundle.py",
    "tools/normalize_pdf_id.py",
    "tools/write_manifest.py",
    "verify.py",
}


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def reject_constant(value: str) -> None:
    raise VerificationError(f"non-finite JSON constant: {value}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    return load_json_bytes(path.read_bytes(), path.name)


def load_json_bytes(payload: bytes, source: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {source}: {exc}") from exc
    require(type(value) is dict, f"{source} must contain an object")
    return value


def strict_int(value: Any, where: str) -> int:
    require(type(value) is int, f"{where} must be an integer")
    return value


def exact_keys(value: Any, expected: set[str], where: str) -> None:
    require(type(value) is dict, f"{where} must be an object")
    require(set(value) == expected, f"{where} keys differ")


def finite(value: Any, where: str, *, zero: bool = False) -> float:
    require(type(value) in (int, float), f"{where} must be numeric")
    number = float(value)
    require(math.isfinite(number), f"{where} must be finite")
    require(number >= 0.0 if zero else number > 0.0, f"{where} has an invalid sign")
    return number


def close(actual: float, expected: Any, where: str, tolerance: float = 5e-12) -> None:
    target = finite(expected, where, zero=True)
    require(
        math.isclose(actual, target, rel_tol=tolerance, abs_tol=tolerance),
        f"{where} mismatch: calculated {actual!r}, published {target!r}",
    )


def confidence(log_values: list[float]) -> dict[str, Any]:
    require(len(log_values) == 64, "confidence calculation requires 64 pairs")
    mean = statistics.mean(log_values)
    stdev = statistics.stdev(log_values)
    error = stdev / math.sqrt(64)
    return {
        "estimate": math.exp(mean),
        "ci95_two_sided": [
            math.exp(mean - TWO_SIDED_T_95_DF63 * error),
            math.exp(mean + TWO_SIDED_T_95_DF63 * error),
        ],
        "lower_one_sided_95": math.exp(mean - ONE_SIDED_T_95_DF63 * error),
        "upper_one_sided_95": math.exp(mean + ONE_SIDED_T_95_DF63 * error),
        "log_stdev": stdev,
        "wins": sum(value < 0.0 for value in log_values),
        "ties": sum(value == 0.0 for value in log_values),
        "losses": sum(value > 0.0 for value in log_values),
    }


def verify_checksums() -> None:
    manifest = ROOT / "SHA256SUMS"
    require(manifest.is_file(), "missing SHA256SUMS")
    seen: dict[str, str] = {}
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\n]+)", line)
        require(match is not None, f"malformed SHA256SUMS line {line_number}")
        expected, relative = match.groups()
        path = PurePosixPath(relative)
        require(not path.is_absolute() and ".." not in path.parts, f"unsafe checksum path: {relative}")
        require(relative not in seen, f"duplicate checksum entry: {relative}")
        seen[relative] = expected
    require(set(seen) == REQUIRED_MANIFEST, "SHA256SUMS does not cover the exact INT8 package")
    for relative, expected in seen.items():
        path = ROOT / relative
        require(path.is_file(), f"missing checksummed file: {relative}")
        require(sha256(path) == expected, f"checksum mismatch: {relative}")


def verify_patch() -> None:
    baseline = ROOT / "rtl/baseline/int8_matvec_4x4.sv"
    optimized = ROOT / "rtl/optimized/int8_matvec_4x4.sv"
    generated = "".join(
        difflib.unified_diff(
            baseline.read_text(encoding="utf-8").splitlines(keepends=True),
            optimized.read_text(encoding="utf-8").splitlines(keepends=True),
            fromfile="rtl/baseline/int8_matvec_4x4.sv",
            tofile="rtl/optimized/int8_matvec_4x4.sv",
        )
    )
    published = (ROOT / "rtl/changes.patch").read_text(encoding="utf-8")
    require(generated == published, "published patch differs from the two RTL files")


def reject_private_fields(value: Any, where: str = "root") -> None:
    if type(value) is dict:
        for key, child in value.items():
            require(key != "seed", f"held-out seed identity leaked at {where}")
            require("prompt" not in key.lower() and "credential" not in key.lower(), f"private campaign field leaked at {where}.{key}")
            reject_private_fields(child, f"{where}.{key}")
    elif type(value) is list:
        for index, child in enumerate(value):
            reject_private_fields(child, f"{where}[{index}]")


def verify_certificate(data: dict[str, Any]) -> float:
    exact_keys(
        data,
        {"schema_version", "case_id", "status", "decision", "claim_boundary", "rtl", "correctness", "measurement", "score_definition", "summary", "independent_replay", "pairs"},
        "root",
    )
    require(data["schema_version"] == 1 and data["case_id"] == "int8-matvec-vtr45-v1", "wrong certificate identity")
    require(data["status"] == "certified_and_independently_reproduced", "certificate lacks the required replay status")
    require(data["decision"] == "evidence_improvement", "certificate did not accept an improvement")
    require(data["claim_boundary"] == CLAIM_BOUNDARY, "claim boundary drift")
    reject_private_fields(data)

    rtl = data["rtl"]
    exact_keys(rtl, {"baseline_sha256", "optimized_sha256"}, "rtl")
    require(sha256(ROOT / "rtl/baseline/int8_matvec_4x4.sv") == rtl["baseline_sha256"], "baseline RTL hash mismatch")
    require(sha256(ROOT / "rtl/optimized/int8_matvec_4x4.sv") == rtl["optimized_sha256"], "optimized RTL hash mismatch")

    correctness = data["correctness"]
    exact_keys(correctness, {"functional_passed", "functional_test_count", "functional_test_set_sha256", "formal_passed", "formal_scope"}, "correctness")
    require(correctness["functional_passed"] is True, "functional verification did not pass")
    require(correctness["formal_passed"] is True, "formal equivalence did not pass")
    require(correctness["functional_test_count"] == 151, "wrong functional test count")
    require(correctness["functional_test_set_sha256"] == FUNCTIONAL_TEST_SET_SHA256, "wrong functional test identity")
    require(correctness["formal_scope"] == FORMAL_SCOPE, "formal scope drift")

    measurement = data["measurement"]
    exact_keys(measurement, {"toolchain", "fpga_architecture", "activity", "search_pair_count", "certification_pair_count", "pools_disjoint", "pair_identity_policy"}, "measurement")
    exact_keys(measurement["toolchain"], set(TOOLCHAIN), "measurement.toolchain")
    exact_keys(measurement["fpga_architecture"], set(FPGA_ARCHITECTURE), "measurement.fpga_architecture")
    exact_keys(measurement["activity"], set(ACTIVITY), "measurement.activity")
    require(measurement["toolchain"] == TOOLCHAIN, "toolchain authority drift")
    require(measurement["fpga_architecture"] == FPGA_ARCHITECTURE, "FPGA architecture authority drift")
    require(measurement["activity"] == ACTIVITY, "activity authority drift")
    require(measurement["search_pair_count"] == 5 and measurement["certification_pair_count"] == 64, "wrong search/certification counts")
    require(measurement["pools_disjoint"] is True, "measurement pools are not disjoint")
    require(measurement["pair_identity_policy"] == "Held-out VTR seed identities are replaced by stable pair labels in the public compact certificate.", "pair identity policy drift")

    score = data["score_definition"]
    exact_keys(score, {"direction", "baseline", "primary_metrics", "formula", "acceptance_rule"}, "score_definition")
    require(score["direction"] == "lower_is_better" and score["baseline"] == 1.0, "wrong score direction")
    require(score["primary_metrics"] == list(PRIMARY), "wrong primary metrics")
    require(score["formula"] == SCORE_FORMULA, "score formula drift")
    require(score["acceptance_rule"] == ACCEPTANCE_RULE, "acceptance rule drift")

    pairs = data["pairs"]
    require(type(pairs) is list and len(pairs) == 64, "certificate must contain exactly 64 pairs")
    values = {side: {metric: [] for metric in ROW_METRICS} for side in ("baseline", "optimized")}
    metric_logs = {metric: [] for metric in PRIMARY}
    composite_logs: list[float] = []
    for index, row in enumerate(pairs, 1):
        exact_keys(row, {"pair_id", "baseline", "optimized"}, f"pair {index}")
        require(row["pair_id"] == f"held-out-{index:02d}", f"wrong pair label at {index}")
        row_logs = []
        for side in ("baseline", "optimized"):
            exact_keys(row[side], set(ROW_METRICS), f"pair {index}.{side}")
            for metric in ROW_METRICS:
                number = finite(row[side][metric], f"pair {index}.{side}.{metric}", zero=metric == "multiplier_blocks")
                values[side][metric].append(number)
            close(row[side]["logic_block_area_mwta"] + row[side]["routing_area_mwta"], row[side]["area_total_mwta"], f"pair {index}.{side}.area")
            close(1000.0 / row[side]["critical_path_delay_ns"], row[side]["fmax_mhz"], f"pair {index}.{side}.fmax", tolerance=8e-6)
            close(row[side]["active_dynamic_power_w"] + row[side]["active_static_power_w"], row[side]["active_total_power_w"], f"pair {index}.{side}.power", tolerance=2e-12)
        for metric in PRIMARY:
            log_ratio = math.log(row["optimized"][metric] / row["baseline"][metric])
            metric_logs[metric].append(log_ratio)
            row_logs.append(log_ratio)
        composite_logs.append(statistics.mean(row_logs))

    summary = data["summary"]
    exact_keys(summary, {"baseline", "optimized", "paired_ratio", "score", "improvement", "resource_maxima", "validity_limits"}, "summary")
    aggregate_metrics = {"active_dynamic_power_w", "active_static_power_w", "active_total_power_w", "area_total_mwta", "critical_path_delay_ns", "fmax_mhz", "idle_total_power_w"}
    for side in ("baseline", "optimized"):
        exact_keys(summary[side], aggregate_metrics, f"summary.{side}")
        for metric in aggregate_metrics:
            aggregate = math.exp(statistics.mean(math.log(value) for value in values[side][metric]))
            close(aggregate, summary[side][metric], f"summary.{side}.{metric}")

    ratios = summary["paired_ratio"]
    exact_keys(ratios, set(PRIMARY) | {"composite"}, "paired_ratio")
    calculated = {metric: confidence(logs) for metric, logs in metric_logs.items()}
    calculated["composite"] = confidence(composite_logs)
    ratio_keys = {"estimate", "ci95_two_sided", "lower_one_sided_95", "upper_one_sided_95", "log_stdev", "wins", "ties", "losses"}
    for metric, result in calculated.items():
        exact_keys(ratios[metric], ratio_keys, f"paired_ratio.{metric}")
        require(type(ratios[metric]["ci95_two_sided"]) is list and len(ratios[metric]["ci95_two_sided"]) == 2, f"invalid interval: {metric}")
        for key in ("estimate", "lower_one_sided_95", "upper_one_sided_95", "log_stdev"):
            close(result[key], ratios[metric][key], f"paired_ratio.{metric}.{key}")
        close(result["ci95_two_sided"][0], ratios[metric]["ci95_two_sided"][0], f"paired_ratio.{metric}.ci_low")
        close(result["ci95_two_sided"][1], ratios[metric]["ci95_two_sided"][1], f"paired_ratio.{metric}.ci_high")
        require((ratios[metric]["wins"], ratios[metric]["ties"], ratios[metric]["losses"]) == (result["wins"], result["ties"], result["losses"]), f"wrong win/tie/loss counts: {metric}")

    close(calculated["composite"]["estimate"], summary["score"], "summary.score")
    close(1.0 - calculated["composite"]["estimate"], summary["improvement"], "summary.improvement")
    require(calculated["composite"]["upper_one_sided_95"] < 1.0, "composite acceptance bound failed")
    for metric in PRIMARY:
        require(calculated[metric]["lower_one_sided_95"] <= 1.0, f"primary non-regression bound failed: {metric}")

    maxima = summary["resource_maxima"]
    exact_keys(maxima, {"clb_blocks", "logic_elements", "multiplier_blocks", "registers", "timing_channel_width"}, "resource_maxima")
    for metric in maxima:
        require(max(values["optimized"][metric]) == maxima[metric], f"wrong resource maximum: {metric}")
    limits = summary["validity_limits"]
    exact_keys(limits, set(VALIDITY_LIMITS), "validity_limits")
    require(limits == VALIDITY_LIMITS, "validity-limit authority drift")
    require(maxima["logic_elements"] <= limits["maximum_logic_elements"], "logic-element validity limit failed")
    require(maxima["multiplier_blocks"] <= limits["maximum_multiplier_blocks"], "multiplier-block validity limit failed")
    require(max(row["optimized"]["area_total_mwta"] / row["baseline"]["area_total_mwta"] for row in pairs) <= limits["maximum_area_ratio"], "area-ratio validity limit failed")
    require(max(row["optimized"]["critical_path_delay_ns"] / row["baseline"]["critical_path_delay_ns"] for row in pairs) <= limits["maximum_critical_path_ratio"], "delay-ratio validity limit failed")
    require(max(row["optimized"]["active_total_power_w"] / row["baseline"]["active_total_power_w"] for row in pairs) <= limits["maximum_active_power_ratio"], "power-ratio validity limit failed")

    replay = data["independent_replay"]
    exact_keys(replay, {"baseline_exact", "optimized_exact", "source_evidence_sha256"}, "independent_replay")
    require(replay["baseline_exact"] is True and replay["optimized_exact"] is True, "independent replay failed")
    exact_keys(replay["source_evidence_sha256"], {"baseline_primary", "baseline_replay", "optimized_primary", "optimized_replay"}, "source evidence")
    require(replay["source_evidence_sha256"] == SOURCE_EVIDENCE_SHA256, "source evidence identity drift")
    return calculated["composite"]["estimate"]


def _last(pattern: str, text: str, where: str, cast: type[float] | type[int] = float) -> float | int:
    matches = re.findall(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
    require(bool(matches), f"missing raw metric: {where}")
    raw = matches[-1]
    if isinstance(raw, tuple):
        raw = raw[0]
    value = cast(str(raw).strip().rstrip("."))
    require(math.isfinite(float(value)) and float(value) >= 0.0, f"invalid raw metric: {where}")
    return value


def parse_power_report(payload: bytes, where: str) -> dict[str, float]:
    text = payload.decode("utf-8", errors="replace")
    require(re.search(r"^-+ Errors -+$", text, re.MULTILINE) is None, f"VPR power errors: {where}")
    match = re.search(r"^Total\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s*$", text, re.MULTILINE)
    require(match is not None, f"missing VPR Total power row: {where}")
    total = float(match.group(1))
    dynamic_fraction = float(match.group(3))
    require(math.isfinite(total) and total > 0.0, f"invalid VPR total power: {where}")
    require(math.isfinite(dynamic_fraction) and 0.0 <= dynamic_fraction <= 1.0, f"invalid VPR dynamic fraction: {where}")
    result = {
        "total": total,
        "dynamic": total * dynamic_fraction,
        "static": total * (1.0 - dynamic_fraction),
        "technology_nm": float(_last(r"^Technology \(nm\):\s*([^\s]+)", text, f"{where}.technology")),
        "voltage_v": float(_last(r"^Voltage:\s*([^\s]+)", text, f"{where}.voltage")),
        "temperature_c": float(_last(r"^Temperature:\s*([^\s]+)", text, f"{where}.temperature")),
        "critical_path_s": float(_last(r"^Critical Path:\s*([^\s]+)", text, f"{where}.critical_path")),
        "channel_width": float(_last(r"^Channel Width:\s*(\d+)", text, f"{where}.channel", int)),
    }
    require(
        (result["technology_nm"], result["voltage_v"], result["temperature_c"]) == (45.0, 0.9, 85.0),
        f"wrong VTR/PTM operating point: {where}",
    )
    return result


def derive_raw_metrics(files: dict[str, bytes], where: str) -> dict[str, float]:
    require(set(files) == {"vpr.crit_path.out", "active.power", "idle.power"}, f"incomplete raw PPA tree: {where}")
    timing = files["vpr.crit_path.out"].decode("utf-8", errors="replace")
    require("Circuit successfully routed" in timing, f"VPR did not route successfully: {where}")
    logic = float(_last(r"Total logic block area .*?:\s*([^\s]+)", timing, f"{where}.logic"))
    routing = float(_last(r"Total routing area:\s*([^,]+),", timing, f"{where}.routing"))
    delay = float(_last(r"Final critical path delay \(least slack\):\s*([^\s]+) ns", timing, f"{where}.delay"))
    fmax = float(_last(r"Final critical path delay \(least slack\):.*Fmax:\s*([^\s]+) MHz", timing, f"{where}.fmax"))
    channel = int(_last(r"Circuit successfully routed with a channel width factor of (\d+)", timing, f"{where}.channel", int))
    clbs = int(_last(r"Netlist clb blocks:\s*(\d+)\. ?", timing, f"{where}.clbs", int))
    lut_rows = re.findall(r"^\s+[0-6]-LUT:\s*(\d+)\s*$", timing, re.MULTILINE)
    require(bool(lut_rows), f"missing mapped LUT utilization: {where}")
    registers = int(_last(r"^\s+ff\s*:\s*(\d+)\s*$", timing, f"{where}.registers", int))
    multiplier = re.search(r"^\s*(\d+)\s+blocks of type: mult_36\s*$", timing, re.MULTILINE)
    require(multiplier is not None, f"missing multiplier utilization: {where}")
    active = parse_power_report(files["active.power"], f"{where}/active.power")
    idle = parse_power_report(files["idle.power"], f"{where}/idle.power")
    for profile, power in (("active", active), ("idle", idle)):
        require(int(power["channel_width"]) == channel, f"{profile} channel differs from timing: {where}")
        require(
            math.isclose(power["critical_path_s"] * 1e9, delay, rel_tol=1e-3, abs_tol=1e-4),
            f"{profile} critical path differs from timing: {where}",
        )
    return {
        "area_total_mwta": logic + routing,
        "logic_block_area_mwta": logic,
        "routing_area_mwta": routing,
        "critical_path_delay_ns": delay,
        "fmax_mhz": fmax,
        "active_total_power_w": active["total"],
        "active_dynamic_power_w": active["dynamic"],
        "active_static_power_w": active["static"],
        "idle_total_power_w": idle["total"],
        "clb_blocks": float(clbs),
        "logic_elements": float(sum(int(value) for value in lut_rows)),
        "multiplier_blocks": float(int(multiplier.group(1))),
        "registers": float(registers),
        "timing_channel_width": float(channel),
    }


def raw_close(actual: float, expected: Any, where: str) -> None:
    target = finite(expected, where, zero=True)
    require(
        math.isclose(actual, target, rel_tol=1e-9, abs_tol=1e-8),
        f"{where} is not derived from raw evidence: calculated {actual!r}, published {target!r}",
    )


def verify_public_payload(payload: bytes, relative: str) -> None:
    require(re.search(rb"/Users/[^/\s]+/", payload) is None, f"unsanitized host path: {relative}")
    require(re.search(rb"(?i)(?:seed_\d+|--seed\s+\d+|\bseed\s*[:=]\s*\d+|\bseed\s+\d+)", payload) is None, f"held-out seed identity leaked: {relative}")
    for marker in (
        b"api_key",
        b"access_token",
        b"refresh_token",
        b"auth.json",
        b"credential",
    ):
        require(marker.lower() not in payload.lower(), f"private execution marker leaked: {relative}")


def verify_full_evidence_metadata() -> dict[str, Any]:
    metadata = load_json(FULL_EVIDENCE)
    exact_keys(
        metadata,
        {"schema_version", "asset_name", "archive_sha256", "archive_bytes", "bundle_root", "member_count", "release_tag", "download_url"},
        "full-evidence metadata",
    )
    require(metadata["schema_version"] == 1 and metadata["bundle_root"] == BUNDLE_ROOT, "wrong full-evidence identity")
    require(metadata["asset_name"] == f"{BUNDLE_ROOT}.tar.gz", "wrong full-evidence asset name")
    require(type(metadata["archive_sha256"]) is str and HEX64.fullmatch(metadata["archive_sha256"]), "invalid full-evidence archive hash")
    require(metadata["archive_sha256"] != "0" * 64, "placeholder full-evidence archive hash")
    require(strict_int(metadata["archive_bytes"], "archive_bytes") > 0, "full-evidence archive must be non-empty")
    require(strict_int(metadata["member_count"], "member_count") > 0, "full-evidence manifest must be non-empty")
    require(metadata["release_tag"] == "v2.0.1", "wrong full-evidence release tag")
    require(
        metadata["download_url"]
        == f"https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/{metadata['release_tag']}/{metadata['asset_name']}",
        "wrong full-evidence download URL",
    )
    return metadata


def verify_full_evidence(data: dict[str, Any], metadata: dict[str, Any], archive_path: Path) -> None:
    require(archive_path.is_file(), f"missing evidence archive: {archive_path}")
    require(archive_path.name == metadata["asset_name"], "wrong evidence archive filename")
    require(archive_path.stat().st_size == strict_int(metadata["archive_bytes"], "archive_bytes"), "evidence archive byte count mismatch")
    require(sha256(archive_path) == metadata["archive_sha256"], "evidence archive SHA-256 mismatch")

    with tarfile.open(archive_path, "r:gz") as archive:
        file_members: dict[str, tarfile.TarInfo] = {}
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and ".." not in path.parts, f"unsafe archive member: {member.name}")
            require(member.isfile(), f"non-regular archive member: {member.name}")
            require(member.name not in file_members, f"duplicate archive member: {member.name}")
            file_members[member.name] = member
        manifest_name = f"{BUNDLE_ROOT}/MANIFEST.json"
        require(manifest_name in file_members, "missing internal evidence manifest")
        stream = archive.extractfile(file_members[manifest_name])
        require(stream is not None, "cannot read internal evidence manifest")
        manifest = load_json_bytes(stream.read(), "evidence MANIFEST.json")
        exact_keys(
            manifest,
            {"schema_version", "bundle", "purpose", "member_count", "members", "legs", "pairs_per_leg", "seed_identity_policy", "sanitization", "transformations"},
            "evidence manifest",
        )
        require(manifest["schema_version"] == 1 and manifest["bundle"] == BUNDLE_ROOT, "wrong internal manifest identity")
        require(manifest["legs"] == ["baseline-primary", "baseline-replay", "accepted-primary", "accepted-replay"], "wrong evidence legs")
        require(manifest["pairs_per_leg"] == 64 and manifest["seed_identity_policy"] == "blinded_stable_pair_labels", "wrong pair blinding policy")
        entries = manifest["members"]
        require(type(entries) is list and len(entries) == strict_int(manifest["member_count"], "member_count"), "invalid evidence member count")
        require(len(entries) == strict_int(metadata["member_count"], "full-evidence member_count"), "outer/inner member count mismatch")
        expected_names = {manifest_name}
        public_hashes: dict[str, str] = {}
        records: dict[str, dict[str, Any]] = {}
        candidates: dict[str, bytes] = {}
        bundled_certificate: bytes | None = None
        functional_artifacts: dict[str, dict[str, bytes]] = {}
        formal_logs: dict[str, bytes] = {}
        raw_runs: dict[tuple[str, str], dict[str, bytes]] = {}
        for index, entry in enumerate(entries):
            require(type(entry) is dict, f"manifest member {index} must be an object")
            provenance = entry.get("provenance")
            expected_entry_keys = (
                {"path", "bytes", "sha256", "provenance", "source_sha256"}
                if provenance == "byte_exact_source"
                else {"path", "bytes", "sha256", "provenance"}
            )
            exact_keys(entry, expected_entry_keys, f"manifest member {index}")
            require(provenance in {"byte_exact_source", "public_sanitized_or_blinded"}, f"invalid provenance class: {index}")
            relative = entry["path"]
            require(type(relative) is str, f"manifest path {index} must be a string")
            path = PurePosixPath(relative)
            require(not path.is_absolute() and ".." not in path.parts, f"unsafe internal path: {relative}")
            name = f"{BUNDLE_ROOT}/{relative}"
            require(name not in expected_names, f"duplicate manifest path: {relative}")
            expected_names.add(name)
            require(name in file_members, f"manifest references missing member: {relative}")
            stream = archive.extractfile(file_members[name])
            require(stream is not None, f"cannot read evidence member: {relative}")
            payload = stream.read()
            require(len(payload) == strict_int(entry["bytes"], f"{relative}.bytes"), f"byte count mismatch: {relative}")
            require(sha256_bytes(payload) == entry["sha256"], f"hash mismatch: {relative}")
            verify_public_payload(payload, relative)
            public_hashes[relative] = entry["sha256"]
            if provenance == "byte_exact_source":
                require(type(entry["source_sha256"]) is str and HEX64.fullmatch(entry["source_sha256"]), f"invalid source hash: {relative}")
                require(entry["source_sha256"] == entry["sha256"], f"byte-exact member source/public hash mismatch: {relative}")
            if relative == "certificate.json":
                bundled_certificate = payload
            record_match = re.fullmatch(r"records/(baseline-primary|baseline-replay|accepted-primary|accepted-replay)\.json", relative)
            if record_match:
                records[record_match.group(1)] = load_json_bytes(payload, relative)
            candidate_match = re.fullmatch(r"runs/(baseline-primary|baseline-replay|accepted-primary|accepted-replay)/candidate\.sv", relative)
            if candidate_match:
                candidates[candidate_match.group(1)] = payload
            functional_match = re.fullmatch(
                r"runs/(baseline-primary|baseline-replay|accepted-primary|accepted-replay)/functional/(candidate\.sv|functional_testbench\.sv|functional_run\.stdout\.log|functional_run\.stderr\.log)",
                relative,
            )
            if functional_match:
                functional_artifacts.setdefault(functional_match.group(1), {})[functional_match.group(2)] = payload
            formal_match = re.fullmatch(r"runs/(baseline-primary|baseline-replay|accepted-primary|accepted-replay)/results/formal\.log", relative)
            if formal_match:
                formal_logs[formal_match.group(1)] = payload
            raw_match = re.fullmatch(
                r"runs/(baseline-primary|baseline-replay|accepted-primary|accepted-replay)/(held-out-\d{2})/(vpr\.crit_path\.out|active\.power|idle\.power)",
                relative,
            )
            if raw_match:
                leg, pair_id, filename = raw_match.groups()
                raw_runs.setdefault((leg, pair_id), {})[filename] = payload
        require(set(file_members) == expected_names, "archive contains unmanifested members")

        transformed_paths = {
            entry["path"]
            for entry in entries
            if entry["provenance"] == "public_sanitized_or_blinded"
        }
        declared: set[str] = set()
        for section_name in ("sanitization", "transformations"):
            section = manifest[section_name]
            exact_keys(section, {"modified_member_count", "modified_members"}, f"evidence {section_name}")
            items = section["modified_members"]
            require(type(items) is list and len(items) == strict_int(section["modified_member_count"], f"{section_name}.count"), f"invalid {section_name} records")
            for item in items:
                expected = {"path", "replacements", "public_sha256"} if section_name == "sanitization" else {"path", "description", "public_sha256"}
                exact_keys(item, expected, f"{section_name} record")
                path = item["path"]
                require(type(path) is str and path not in declared, f"duplicate transformation path: {path}")
                declared.add(path)
                if section_name == "sanitization":
                    require(strict_int(item["replacements"], f"{path}.replacements") > 0, f"invalid sanitization count: {path}")
                else:
                    require(type(item["description"]) is str and bool(item["description"]), f"missing transformation description: {path}")
                require(item["public_sha256"] == public_hashes.get(path), f"public transformation hash mismatch: {path}")
        require(transformed_paths == declared, "source/public hash differences are not completely explained")

    legs = {"baseline-primary", "baseline-replay", "accepted-primary", "accepted-replay"}
    require(bundled_certificate is not None and sha256_bytes(bundled_certificate) == sha256(RESULT), "bundle compact certificate mismatch")
    require(set(records) == legs and set(candidates) == legs, "archive does not contain all four evidence records and RTL inputs")
    require(set(functional_artifacts) == legs and set(formal_logs) == legs, "archive does not contain all functional/formal evidence legs")
    for relative, expected_hash in FLOW_SHA256.items():
        require(public_hashes.get(relative) == expected_hash, f"flow authority identity mismatch: {relative}")
    require(set(raw_runs) == {(leg, f"held-out-{index:02d}") for leg in legs for index in range(1, 65)}, "archive does not contain exactly four blinded 64-pair PPA sets")
    baseline_hash = data["rtl"]["baseline_sha256"]
    accepted_hash = data["rtl"]["optimized_sha256"]
    for leg in legs:
        expected_hash = baseline_hash if leg.startswith("baseline-") else accepted_hash
        require(sha256_bytes(candidates[leg]) == expected_hash, f"wrong candidate RTL identity: {leg}")
        functional = functional_artifacts[leg]
        require(
            set(functional) == {"candidate.sv", "functional_testbench.sv", "functional_run.stdout.log", "functional_run.stderr.log"},
            f"incomplete functional evidence: {leg}",
        )
        require(functional["candidate.sv"] == candidates[leg], f"functional candidate differs from measured candidate: {leg}")
        require(sha256_bytes(functional["functional_testbench.sv"]) == FUNCTIONAL_TESTBENCH_SHA256, f"functional testbench identity mismatch: {leg}")
        stdout = functional["functional_run.stdout.log"]
        require(stdout.count(b"FUNCTIONAL_PASS cases=151") == 1, f"functional pass marker is not unique: {leg}")
        require(functional["functional_run.stderr.log"] == b"", f"functional stderr is not empty: {leg}")
        require(re.search(rb"(?i)(?:FUNCTIONAL_FAIL|ASSERTION FAILED|%Error|fatal)", stdout) is None, f"functional failure marker present: {leg}")
        formal = formal_logs[leg]
        require(formal.count(b"Found 384 $equiv cells") == 1, f"formal equivalence-cell count mismatch: {leg}")
        require(formal.count(b"384 are proven and 0 are unproven") == 1, f"formal proof closure mismatch: {leg}")
        require(formal.count(b"Equivalence successfully proven!") == 1, f"formal success marker mismatch: {leg}")
        record = records[leg]
        exact_keys(
            record,
            {
                "active_vector_sha256", "activity_blif_sha256", "aggregates", "artifact",
                "artifact_rtl_sha256", "certification_manifest_sha256", "claim_boundary",
                "contract_revision", "docker_image_id", "elapsed_seconds", "evidence_role",
                "formal_passed", "functional_passed", "functional_test_count",
                "functional_test_set_sha256", "idle_vector_sha256", "pair_identity_policy",
                "per_seed", "schema_version", "search_contract_manifest_sha256", "seed_count",
                "seed_workers", "status",
            },
            f"record.{leg}",
        )
        expected_artifact = "baseline" if leg.startswith("baseline-") else "campaign_best"
        expected_role = "primary" if leg.endswith("-primary") else "independent_reproduction"
        require(record["schema_version"] == 1 and record["status"] == "qualified", f"unqualified evidence record: {leg}")
        require(record["artifact"] == expected_artifact and record["evidence_role"] == expected_role, f"record role drift: {leg}")
        require(record["functional_passed"] is True and record["formal_passed"] is True, f"correctness record failed: {leg}")
        require(record["functional_test_count"] == 151 and record["functional_test_set_sha256"] == FUNCTIONAL_TEST_SET_SHA256, f"functional authority mismatch: {leg}")
        require(record["claim_boundary"] == CLAIM_BOUNDARY, f"record claim boundary drift: {leg}")
        require(record["contract_revision"] == "int8-matvec-vtr45-held-out-certification64-v1", f"record contract revision drift: {leg}")
        require(record["docker_image_id"] == TOOLCHAIN["docker_image_id"], f"record image identity drift: {leg}")
        require(record["certification_manifest_sha256"] == "2a988ca82d46fb72631880899f5f2686a4b0274b1b17afd58379437ed59c5441", f"certification manifest drift: {leg}")
        require(record["search_contract_manifest_sha256"] == FLOW_SHA256["flow/ppa_manifest.json"], f"search manifest drift: {leg}")
        require(record["pair_identity_policy"] == "Held-out seed identities replaced by stable pair labels.", f"record pair policy drift: {leg}")
        require(record["idle_vector_sha256"] == "9734f9350c07b82aac0b6082b4cb75efd863934c758b9195b5e692a935715e34", f"idle activity identity drift: {leg}")
        expected_active = "0792b04f00e89c7d837b8016a6e119baf61c5e36453f1bbfbb89025b97e7a62e" if leg.startswith("baseline-") else "8dae31a5e9084ac483a65f836fdad05c2913bbe8958e8f072947f27333cca463"
        expected_blif = "7edb883c23691ab07b73f9de0f96445542d2f4e4384cd0d766544072c2494a0a" if leg.startswith("baseline-") else "b6b697a00d92970d164a039b07231c739c1bb5723dcc5a95950b420fc667e098"
        require(record["active_vector_sha256"] == expected_active and record["activity_blif_sha256"] == expected_blif, f"active activity identity drift: {leg}")
        require(record["artifact_rtl_sha256"] == expected_hash, f"record RTL identity mismatch: {leg}")
        require(record["seed_count"] == 64 and record["seed_workers"] == 2, f"wrong held-out execution shape: {leg}")
        finite(record["elapsed_seconds"], f"record.{leg}.elapsed_seconds")
        reject_private_fields(record, f"record.{leg}")
        rows = record.get("per_seed")
        require(type(rows) is list and len(rows) == 64, f"wrong record rows: {leg}")
        for index, row in enumerate(rows, 1):
            require(type(row) is dict and row.get("pair_id") == f"held-out-{index:02d}", f"wrong blinded pair ordering: {leg}/{index}")
            exact_keys(row, set(ROW_METRICS) | {"pair_id"}, f"record.{leg}.{index}")
        expected_summary_side = "baseline" if leg.startswith("baseline-") else "optimized"
        exact_keys(record["aggregates"], set(data["summary"][expected_summary_side]), f"record.{leg}.aggregates")
        for metric, value in record["aggregates"].items():
            raw_close(value, data["summary"][expected_summary_side][metric], f"record {leg} aggregate {metric}")

    for index, compact in enumerate(data["pairs"], 1):
        pair_id = f"held-out-{index:02d}"
        for leg in sorted(legs):
            side = "baseline" if leg.startswith("baseline-") else "optimized"
            raw = derive_raw_metrics(raw_runs[(leg, pair_id)], f"{leg}/{pair_id}")
            record_row = records[leg]["per_seed"][index - 1]
            for metric in ROW_METRICS:
                raw_close(raw[metric], record_row[metric], f"record {leg}/{pair_id}/{metric}")
                raw_close(raw[metric], compact[side][metric], f"compact {leg}/{pair_id}/{metric}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-archive", type=Path)
    args = parser.parse_args(argv)
    verify_checksums()
    verify_patch()
    data = load_json(RESULT)
    score = verify_certificate(data)
    metadata = verify_full_evidence_metadata()
    print("INT8 MatVec compact evidence: PASS")
    print("functional_tests=151")
    print("formal_equivalence=PASS")
    print("held_out_pairs=64")
    print(f"composite_score={score:.12f}")
    print(f"improvement={100.0 * (1.0 - score):.4f}%")
    if args.evidence_archive is None:
        print("Full raw evidence: NOT CHECKED (pass --evidence-archive)")
    else:
        verify_full_evidence(data, metadata, args.evidence_archive.expanduser().resolve())
        print("Full raw evidence: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VerificationError, KeyError, TypeError, ValueError, OSError, tarfile.TarError) as exc:
        print(f"Verification: FAIL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1) from exc
