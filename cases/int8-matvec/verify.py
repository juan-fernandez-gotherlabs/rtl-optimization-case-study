#!/usr/bin/env python3
"""Fail-closed verification of the public INT8 MatVec compact certificate."""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import re
import statistics
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "certificate.json"
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

REQUIRED_MANIFEST = {
    "LICENSE",
    "Makefile",
    "README.md",
    "certificate.json",
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
    return sha256_bytes(path.read_bytes())


def reject_constant(value: str) -> None:
    raise VerificationError(f"non-finite JSON constant: {value}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(
            path.read_bytes(),
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {path.name}: {exc}") from exc
    require(type(value) is dict, f"{path.name} must contain an object")
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
            require("agent" not in key.lower() and "prompt" not in key.lower(), f"private campaign field leaked at {where}.{key}")
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
    require(data["status"] == "certified_and_independently_reproduced", "certificate is not independently reproduced")
    require(data["decision"] == "evidence_improvement", "certificate did not accept an improvement")
    require(data["claim_boundary"] == "Blinded paired statistical certification using academic VTR PTM 45 nm post-route estimates; not physical, commercial FPGA, ASIC, silicon, board, signoff, measured-power, or measured-energy evidence.", "claim boundary drift")
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
    require(type(correctness["functional_test_set_sha256"]) is str and HEX64.fullmatch(correctness["functional_test_set_sha256"]), "invalid functional test identity")
    require("every 160-bit input assignment" in correctness["formal_scope"], "formal scope is not explicit")

    measurement = data["measurement"]
    exact_keys(measurement, {"toolchain", "fpga_architecture", "activity", "search_pair_count", "certification_pair_count", "pools_disjoint", "pair_identity_policy"}, "measurement")
    require(measurement["search_pair_count"] == 5 and measurement["certification_pair_count"] == 64, "wrong search/certification counts")
    require(measurement["pools_disjoint"] is True, "measurement pools are not disjoint")
    require(measurement["toolchain"]["platform"] == "linux/amd64", "wrong measurement platform")
    require(measurement["fpga_architecture"]["nominal_voltage_v"] == 0.9, "wrong nominal voltage")
    require(measurement["fpga_architecture"]["temperature_c"] == 85, "wrong temperature")

    score = data["score_definition"]
    exact_keys(score, {"direction", "baseline", "primary_metrics", "formula", "acceptance_rule"}, "score_definition")
    require(score["direction"] == "lower_is_better" and score["baseline"] == 1.0, "wrong score direction")
    require(score["primary_metrics"] == list(PRIMARY), "wrong primary metrics")

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
    require(maxima["logic_elements"] <= limits["maximum_logic_elements"], "logic-element validity limit failed")
    require(maxima["multiplier_blocks"] <= limits["maximum_multiplier_blocks"], "multiplier-block validity limit failed")

    replay = data["independent_replay"]
    exact_keys(replay, {"baseline_exact", "optimized_exact", "source_evidence_sha256"}, "independent_replay")
    require(replay["baseline_exact"] is True and replay["optimized_exact"] is True, "independent replay failed")
    exact_keys(replay["source_evidence_sha256"], {"baseline_primary", "baseline_replay", "optimized_primary", "optimized_replay"}, "source evidence")
    require(all(type(value) is str and HEX64.fullmatch(value) for value in replay["source_evidence_sha256"].values()), "invalid source evidence identity")
    return calculated["composite"]["estimate"]


def main() -> int:
    verify_checksums()
    verify_patch()
    score = verify_certificate(load_json(RESULT))
    print("INT8 MatVec compact evidence: PASS")
    print("functional_tests=151")
    print("formal_equivalence=PASS")
    print("held_out_pairs=64")
    print(f"composite_score={score:.12f}")
    print(f"improvement={100.0 * (1.0 - score):.4f}%")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VerificationError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"Verification: FAIL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1) from exc
