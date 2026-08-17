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
        functional_passes: set[str] = set()
        formal_passes: set[str] = set()
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
            functional_match = re.fullmatch(r"runs/(baseline-primary|baseline-replay|accepted-primary|accepted-replay)/functional/functional_run\.stdout\.log", relative)
            if functional_match and b"FUNCTIONAL_PASS cases=151" in payload:
                functional_passes.add(functional_match.group(1))
            formal_match = re.fullmatch(r"runs/(baseline-primary|baseline-replay|accepted-primary|accepted-replay)/results/formal\.log", relative)
            if formal_match and b"Equivalence successfully proven" in payload:
                formal_passes.add(formal_match.group(1))
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
    require(functional_passes == legs, "one or more functional replay logs did not pass 151 cases")
    require(formal_passes == legs, "one or more exhaustive formal-equivalence logs did not pass")
    require(set(raw_runs) == {(leg, f"held-out-{index:02d}") for leg in legs for index in range(1, 65)}, "archive does not contain exactly four blinded 64-pair PPA sets")
    baseline_hash = data["rtl"]["baseline_sha256"]
    accepted_hash = data["rtl"]["optimized_sha256"]
    for leg in legs:
        expected_hash = baseline_hash if leg.startswith("baseline-") else accepted_hash
        require(sha256_bytes(candidates[leg]) == expected_hash, f"wrong candidate RTL identity: {leg}")
        record = records[leg]
        require(record.get("status") == "qualified" and record.get("functional_passed") is True and record.get("formal_passed") is True, f"unqualified evidence record: {leg}")
        require(record.get("artifact_rtl_sha256") == expected_hash, f"record RTL identity mismatch: {leg}")
        require(record.get("seed_count") == 64, f"wrong held-out count: {leg}")
        reject_private_fields(record, f"record.{leg}")
        rows = record.get("per_seed")
        require(type(rows) is list and len(rows) == 64, f"wrong record rows: {leg}")
        for index, row in enumerate(rows, 1):
            require(type(row) is dict and row.get("pair_id") == f"held-out-{index:02d}", f"wrong blinded pair ordering: {leg}/{index}")
            exact_keys(row, set(ROW_METRICS) | {"pair_id"}, f"record.{leg}.{index}")

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
