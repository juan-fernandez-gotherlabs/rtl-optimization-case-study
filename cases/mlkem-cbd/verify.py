#!/usr/bin/env python3
"""Fail-closed verification of the public ML-KEM CBD RTL comparison."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import math
import re
import statistics
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parent
CERTIFICATE = ROOT / "certificate.json"
FULL_EVIDENCE = ROOT / "full-evidence.json"
BUNDLE_ROOT = "mlkem-cbd-vtr45-full-evidence-v1"
SEEDS = tuple(range(101, 165))
PRIMARY_METRICS = ("area_total_mwta", "critical_path_delay_ns", "active_total_power_w")
ONE_SIDED_T_95_DF63 = 1.6694022217068127
TWO_SIDED_T_95_DF63 = 1.9983405425207417
EXPECTED_BASELINE_SHA256 = (
    "c152f96a682ea390c610dc32ee00a317c0ad990f9b082451325cdaf12f2218b0"
)
EXPECTED_OPTIMIZED_SHA256 = (
    "da0b4e79beb9cf9cc24c3ce949068c3a29316273a6320e283f4201fbd884c9ef"
)
EXPECTED_UPSTREAM_SHA256 = (
    "95a12bbae8ad4c255c6d8b0bce862d3593e960e1d754fefe46378a32340f00d0"
)
EXPECTED_IMAGE_ID = (
    "sha256:c0badc2d2bb57364ff37477b3d2c482ef01f7d3df6211e9802e2c54367c33baf"
)
EXPECTED_ARCH_SHA256 = (
    "262792caef81931ae09b77d252158bde03c78954175d4b761e6d437317575307"
)
EXPECTED_TECH_SHA256 = (
    "3080dea13bf7134109f8a83c79426ec0965e07639a61866fe9ae4bd05b5227cb"
)
EXPECTED_PROTOCOL_SHA256 = (
    "cce84fcc54e048137b5a3a89bb0a4e3b92141106ec8330bccb344812b0b02a2c"
)
EXPECTED_EVALUATOR_SHA256 = (
    "b91dc19ab42285d4477d6ca9f1d97c9216bb9725e114026a8c123e71713c1106"
)
EXPECTED_INITIAL_RESULT_SHA256 = (
    "cb446b6a1962f6341fb79151e8713c7cd55053cfac7150449587fc6841c64390"
)
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
    "rtl/baseline/cbd.v",
    "rtl/changes.patch",
    "rtl/optimized/cbd.v",
    "technical-report.pdf",
    "tests/test_verify.py",
    "tools/build_certificate.py",
    "tools/build_evidence_bundle.py",
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


def exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    require(set(value) == expected, f"{where} keys differ")


def reject_constant(value: str) -> None:
    raise VerificationError(f"non-finite JSON constant: {value}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(payload: bytes, source: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload,
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON: {source}") from exc
    require(isinstance(value, dict), f"JSON root must be an object: {source}")
    return value


def load_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"missing JSON file: {path.name}")
    return load_json_bytes(path.read_bytes(), str(path))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def finite(value: Any, where: str, *, zero: bool = False) -> float:
    require(type(value) in (int, float), f"{where} must be numeric")
    result = float(value)
    require(math.isfinite(result), f"{where} must be finite")
    require(result >= 0.0 if zero else result > 0.0, f"{where} outside valid range")
    return result


def close(
    actual: float, expected: Any, where: str, *, tolerance: float = 1e-10
) -> None:
    require(type(expected) in (int, float), f"{where} must be numeric")
    target = float(expected)
    require(math.isfinite(target), f"{where} must be finite")
    require(
        math.isclose(actual, target, rel_tol=tolerance, abs_tol=tolerance),
        f"{where} differs",
    )


def log_interval(values: list[float], critical: float) -> dict[str, float]:
    mean = statistics.mean(values)
    standard_error = statistics.stdev(values) / math.sqrt(len(values))
    lower = mean - critical * standard_error
    upper = mean + critical * standard_error
    return {
        "mean_log_ratio": mean,
        "standard_error": standard_error,
        "lower_log_ratio": lower,
        "upper_log_ratio": upper,
        "lower_improvement_percent": (1.0 - math.exp(upper)) * 100.0,
        "upper_improvement_percent": (1.0 - math.exp(lower)) * 100.0,
    }


def verify_manifest() -> None:
    path = ROOT / "SHA256SUMS"
    require(path.is_file(), "missing SHA256SUMS")
    seen: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\n]+)", line)
        require(match is not None, f"malformed checksum line {number}")
        expected, relative = match.groups()
        pure = PurePosixPath(relative)
        require(
            not pure.is_absolute() and ".." not in pure.parts,
            f"unsafe checksum path: {relative}",
        )
        require(relative not in seen, f"duplicate checksum path: {relative}")
        seen[relative] = expected
    require(set(seen) == REQUIRED_MANIFEST, "case checksum coverage differs")
    for relative, expected in seen.items():
        require(sha256(ROOT / relative) == expected, f"checksum mismatch: {relative}")


def verify_patch() -> None:
    baseline = (
        (ROOT / "rtl/baseline/cbd.v")
        .read_text(encoding="utf-8")
        .splitlines(keepends=True)
    )
    optimized = (
        (ROOT / "rtl/optimized/cbd.v")
        .read_text(encoding="utf-8")
        .splitlines(keepends=True)
    )
    expected = "".join(
        difflib.unified_diff(
            baseline,
            optimized,
            fromfile="rtl/baseline/cbd.v",
            tofile="rtl/optimized/cbd.v",
        )
    )
    actual = (ROOT / "rtl/changes.patch").read_text(encoding="utf-8")
    require(
        actual == expected,
        "published patch is not the exact baseline-to-optimized diff",
    )


def verify_certificate() -> dict[str, Any]:
    data = load_json(CERTIFICATE)
    exact_keys(
        data,
        {
            "schema_version",
            "case_id",
            "authority",
            "status",
            "decision",
            "source",
            "rtl",
            "correctness",
            "measurement",
            "score_definition",
            "pairs",
            "summary",
            "prior_confirmation",
            "claim_boundary",
        },
        "certificate",
    )
    require(
        data.get("schema_version") == 1 and data.get("case_id") == "mlkem-cbd-vtr45",
        "wrong case identity",
    )
    require(
        data.get("authority")
        == "prospectively_frozen_64_pair_publication_confirmation",
        "wrong authority",
    )
    require(
        data.get("decision") == "evidence_improvement"
        and data.get("status") == "accepted",
        "result is not accepted",
    )
    require(
        data["source"]["upstream_sha256"] == EXPECTED_UPSTREAM_SHA256,
        "wrong upstream identity",
    )
    require(
        data["source"]["commit"] == "72a90d80484d45d0bed1e0f9903bd0fb78cceb47",
        "wrong upstream commit",
    )
    require(data["source"]["license"] == "MIT", "wrong source license")
    require(
        sha256(ROOT / "LICENSE") == data["source"]["license_sha256"],
        "license identity drift",
    )
    require(
        data["rtl"]["baseline"]["sha256"] == EXPECTED_BASELINE_SHA256,
        "wrong baseline authority",
    )
    require(
        data["rtl"]["optimized"]["sha256"] == EXPECTED_OPTIMIZED_SHA256,
        "wrong optimized authority",
    )
    require(
        sha256(ROOT / data["rtl"]["baseline"]["path"]) == EXPECTED_BASELINE_SHA256,
        "baseline RTL drift",
    )
    require(
        sha256(ROOT / data["rtl"]["optimized"]["path"]) == EXPECTED_OPTIMIZED_SHA256,
        "optimized RTL drift",
    )
    require(
        sha256(ROOT / data["rtl"]["patch"]["path"]) == data["rtl"]["patch"]["sha256"],
        "patch identity drift",
    )
    require(
        data["correctness"]["functional_passed"] is True,
        "functional evidence did not pass",
    )
    require(
        data["correctness"]["functional_cycles"] == 239
        and data["correctness"]["functional_checks"] == 239,
        "wrong functional evidence scope",
    )
    require(
        data["correctness"]["formal_passed"] is True, "formal evidence did not pass"
    )
    require(
        data["correctness"]["formal_tool"] == "EQY v0.67-1-g6734d8c",
        "wrong formal tool",
    )
    require(
        data["correctness"]["synthesis_tool"] == "Yosys 0.55 (git 60f126cd0)",
        "wrong synthesis tool",
    )
    require(
        data["correctness"]["simulation_tool"] == "Verilator 5.020",
        "wrong simulation tool",
    )
    measurement = data["measurement"]
    require(
        measurement["publication_pair_count"] == 64
        and measurement["publication_seeds"] == list(SEEDS),
        "wrong publication pool",
    )
    require(measurement["pools_disjoint"] is True, "measurement pools are not disjoint")
    require(
        measurement["evaluator_version"] == "rtl-mlkem-cbd-vtr-publication-v1",
        "wrong evaluator",
    )
    require(
        measurement["protocol_sha256"] == EXPECTED_PROTOCOL_SHA256,
        "wrong publication protocol identity",
    )
    require(
        measurement["protocol_frozen_at_utc"] == "2026-08-21T09:02:28Z",
        "wrong protocol freeze time",
    )
    require(
        measurement["evaluator_sha256"] == EXPECTED_EVALUATOR_SHA256,
        "wrong evaluator identity",
    )
    toolchain = measurement["toolchain"]
    require(toolchain["image_id"] == EXPECTED_IMAGE_ID, "wrong image identity")
    require(
        toolchain["vtr_commit"] == "95f5c6de9e158371ba7185bf97c07a84153735d6",
        "wrong VTR commit",
    )
    require(
        toolchain["architecture_sha256"] == EXPECTED_ARCH_SHA256,
        "wrong architecture identity",
    )
    require(
        toolchain["technology_sha256"] == EXPECTED_TECH_SHA256,
        "wrong technology identity",
    )
    require(
        toolchain["network"] == "none"
        and toolchain["cpu_limit"] == 2
        and toolchain["memory_limit_gib"] == 7,
        "wrong resource contract",
    )
    activity = measurement["activity"]
    require(activity["method"] == "ACE probabilistic activity", "wrong activity method")
    require(
        (
            activity["primary_input_static_probability"],
            activity["primary_input_switch_probability"],
            activity["clock_probability"],
            activity["ace_seed"],
        )
        == (0.5, 0.2, 0.2, 1),
        "wrong activity contract",
    )
    score_definition = data["score_definition"]
    require(
        score_definition["primary_metrics"] == list(PRIMARY_METRICS)
        and score_definition["direction"] == "lower_is_better",
        "wrong score definition",
    )
    require(
        score_definition["formula"]
        == "equal-weight geometric mean of paired optimized/baseline area, delay, and active-total-power ratios",
        "wrong score formula",
    )

    pairs = data["pairs"]
    require(isinstance(pairs, list) and len(pairs) == 64, "wrong pair count")
    require([pair["seed"] for pair in pairs] == list(SEEDS), "wrong pair order")
    metric_logs: dict[str, list[float]] = {metric: [] for metric in PRIMARY_METRICS}
    composite_logs: list[float] = []
    for index, pair in enumerate(pairs, 1):
        require(
            pair["pair_id"] == f"publication-{index:02d}", f"wrong pair label {index}"
        )
        logs: list[float] = []
        for metric in PRIMARY_METRICS:
            ratio = finite(
                pair["optimized"][metric], f"pair {index} optimized {metric}"
            ) / finite(pair["baseline"][metric], f"pair {index} baseline {metric}")
            close(ratio, pair["ratio"][metric], f"pair {index} ratio {metric}")
            value = math.log(ratio)
            metric_logs[metric].append(value)
            logs.append(value)
        composite = math.exp(statistics.mean(logs))
        close(composite, pair["ratio"]["composite"], f"pair {index} composite")
        composite_logs.append(math.log(composite))

    summary = data["summary"]
    score = math.exp(statistics.mean(composite_logs))
    close(score, summary["paired_ratio"]["composite"], "composite score")
    for metric, values in metric_logs.items():
        close(
            math.exp(statistics.mean(values)),
            summary["paired_ratio"][metric],
            f"paired ratio {metric}",
        )
    for design in ("baseline", "optimized"):
        for metric in PRIMARY_METRICS:
            aggregate = math.exp(
                statistics.mean(
                    math.log(finite(pair[design][metric], f"{design}.{metric}"))
                    for pair in pairs
                )
            )
            close(aggregate, summary[design][metric], f"{design} {metric}")
        clb = statistics.median(
            finite(pair[design]["clb_count"], f"{design}.clb_count") for pair in pairs
        )
        close(clb, summary[design]["clb_count"], f"{design} clb_count")
    improvement = summary["improvement_percent"]
    for metric in PRIMARY_METRICS:
        close(
            (1.0 - summary["paired_ratio"][metric]) * 100.0,
            improvement[metric],
            f"improvement {metric}",
        )
    close((1.0 - score) * 100.0, improvement["composite"], "improvement composite")
    close(
        (1.0 / summary["paired_ratio"]["critical_path_delay_ns"] - 1.0) * 100.0,
        improvement["fmax"],
        "improvement fmax",
    )
    close(
        (1.0 - summary["optimized"]["clb_count"] / summary["baseline"]["clb_count"])
        * 100.0,
        improvement["clb"],
        "improvement clb",
    )
    calculated = {
        "acceptance_one_sided_95": {
            "composite": log_interval(composite_logs, ONE_SIDED_T_95_DF63),
            **{
                metric: log_interval(values, ONE_SIDED_T_95_DF63)
                for metric, values in metric_logs.items()
            },
        },
        "descriptive_two_sided_95": {
            "composite": log_interval(composite_logs, TWO_SIDED_T_95_DF63),
            **{
                metric: log_interval(values, TWO_SIDED_T_95_DF63)
                for metric, values in metric_logs.items()
            },
        },
    }
    for family, intervals in calculated.items():
        for metric, interval in intervals.items():
            for field, value in interval.items():
                close(
                    value,
                    summary["confidence"][family][metric][field],
                    f"{family}.{metric}.{field}",
                    tolerance=1e-9,
                )
    acceptance = calculated["acceptance_one_sided_95"]
    require(
        acceptance["composite"]["upper_log_ratio"] < 0.0,
        "composite acceptance bound is not improved",
    )
    require(
        all(acceptance[metric]["lower_log_ratio"] <= 0.0 for metric in PRIMARY_METRICS),
        "a primary metric is significantly regressed",
    )
    require(
        data["prior_confirmation"]["pair_count"] == 12,
        "initial confirmation is not disclosed",
    )
    require(
        data["prior_confirmation"]["candidate_sha256"] == EXPECTED_OPTIMIZED_SHA256
        and data["prior_confirmation"]["result_sha256"]
        == EXPECTED_INITIAL_RESULT_SHA256,
        "wrong initial confirmation identity",
    )
    close(
        0.9053481513813109,
        data["prior_confirmation"]["score"],
        "initial confirmation score",
    )
    close(
        9.465184861868913,
        data["prior_confirmation"]["improvement_percent"],
        "initial confirmation improvement",
    )
    require(len(data["claim_boundary"]) >= 5, "claim boundary is incomplete")
    return data


def verify_full_evidence_metadata() -> dict[str, Any]:
    data = load_json(FULL_EVIDENCE)
    require(
        data.get("schema_version") == 1 and data.get("bundle_root") == BUNDLE_ROOT,
        "wrong evidence metadata",
    )
    require(
        data.get("asset_name") == f"{BUNDLE_ROOT}.tar.gz", "wrong evidence asset name"
    )
    require(
        isinstance(data.get("archive_sha256"), str)
        and HEX64.fullmatch(data["archive_sha256"]),
        "invalid archive hash",
    )
    require(data["archive_sha256"] != "0" * 64, "placeholder archive hash")
    require(
        finite(data.get("archive_bytes"), "archive_bytes") > 0, "empty evidence archive"
    )
    require(data.get("release_tag") == "v2.2.0", "wrong release tag")
    require(
        data.get("download_url")
        == "https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/v2.2.0/mlkem-cbd-vtr45-full-evidence-v1.tar.gz",
        "wrong evidence download URL",
    )
    return data


def number(pattern: str, text: str, where: str) -> float:
    match = re.search(pattern, text, re.MULTILINE)
    require(match is not None, f"missing {where}")
    return finite(float(match.group(1)), where)


def raw_metrics(files: dict[str, bytes], where: str) -> dict[str, float]:
    report = files["vpr.crit_path.out"].decode("utf-8", errors="replace")
    power = files["active.power"].decode("utf-8", errors="replace")
    require("Circuit successfully routed" in report, f"route did not pass: {where}")
    total_line = next(
        (line for line in power.splitlines() if line.strip().startswith("Total")), None
    )
    require(total_line is not None, f"missing power Total row: {where}")
    power_values = re.findall(
        r"(?<![A-Za-z])[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?", total_line
    )
    require(bool(power_values), f"malformed power Total row: {where}")
    require(
        number(r"^Technology \(nm\):\s*([0-9.eE+-]+)", power, f"{where}.technology")
        == 45.0,
        f"wrong technology: {where}",
    )
    require(
        number(r"^Voltage:\s*([0-9.eE+-]+)", power, f"{where}.voltage") == 0.9,
        f"wrong voltage: {where}",
    )
    require(
        number(r"^Temperature:\s*([0-9.eE+-]+)", power, f"{where}.temperature") == 85.0,
        f"wrong temperature: {where}",
    )
    used = number(
        r"Total used logic block area:\s*([0-9.eE+-]+)", report, f"{where}.used_logic"
    )
    routing = number(r"Total routing area:\s*([0-9.eE+-]+)", report, f"{where}.routing")
    clb = re.search(r"^\s*clb\s*:\s*(\d+)\s*$", report, re.MULTILINE)
    require(clb is not None, f"missing CLB count: {where}")
    return {
        "area_total_mwta": used + routing,
        "used_logic_area_mwta": used,
        "routing_area_mwta": routing,
        "critical_path_delay_ns": number(
            r"Final critical path delay \(least slack\):\s*([0-9.eE+-]+) ns",
            report,
            f"{where}.delay",
        ),
        "active_total_power_w": finite(float(power_values[0]), f"{where}.power"),
        "clb_count": float(int(clb.group(1))),
    }


def verify_public_payload(payload: bytes, relative: str) -> None:
    require(
        re.search(rb"/Users/[^/\s]+/", payload) is None,
        f"unsanitized host path: {relative}",
    )
    for marker in (
        b"api_key",
        b"access_token",
        b"refresh_token",
        b"auth.json",
        b"credential",
    ):
        require(marker not in payload.lower(), f"private execution marker: {relative}")


def verify_full_evidence(
    certificate: dict[str, Any], metadata: dict[str, Any], archive_path: Path
) -> None:
    require(archive_path.is_file(), f"missing evidence archive: {archive_path}")
    require(
        archive_path.name == metadata["asset_name"], "wrong evidence archive filename"
    )
    require(
        archive_path.stat().st_size == metadata["archive_bytes"],
        "archive byte count mismatch",
    )
    require(sha256(archive_path) == metadata["archive_sha256"], "archive hash mismatch")
    with tarfile.open(archive_path, "r:gz") as archive:
        files: dict[str, bytes] = {}
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            require(
                not path.is_absolute() and ".." not in path.parts,
                f"unsafe archive member: {member.name}",
            )
            require(member.isfile(), f"non-regular archive member: {member.name}")
            require(
                member.name not in files, f"duplicate archive member: {member.name}"
            )
            stream = archive.extractfile(member)
            require(stream is not None, f"cannot read archive member: {member.name}")
            payload = stream.read()
            verify_public_payload(payload, member.name)
            files[member.name] = payload
    require(len(files) == metadata["member_count"], "archive member count mismatch")
    manifest_name = f"{BUNDLE_ROOT}/MANIFEST.json"
    require(manifest_name in files, "missing internal evidence manifest")
    manifest = load_json_bytes(files[manifest_name], manifest_name)
    entries = manifest["members"]
    require(
        manifest["bundle"] == BUNDLE_ROOT and manifest["pair_count"] == 64,
        "wrong internal manifest",
    )
    require(manifest["seeds"] == list(SEEDS), "wrong raw seed pool")
    require(
        len(entries) == manifest["member_count_excluding_manifest"],
        "wrong internal member count",
    )
    expected = {manifest_name}
    payloads: dict[str, bytes] = {}
    for entry in entries:
        relative = entry["path"]
        name = f"{BUNDLE_ROOT}/{relative}"
        require(name not in expected, f"duplicate internal path: {relative}")
        expected.add(name)
        require(name in files, f"manifested member missing: {relative}")
        payload = files[name]
        require(
            len(payload) == entry["bytes"], f"member byte count mismatch: {relative}"
        )
        require(
            sha256_bytes(payload) == entry["sha256"],
            f"member hash mismatch: {relative}",
        )
        payloads[relative] = payload
    require(set(files) == expected, "archive contains unmanifested members")
    require(
        payloads["certificate.json"] == CERTIFICATE.read_bytes(),
        "archive/local certificate mismatch",
    )
    local_contract = {
        "contract/LICENSE": ROOT / "LICENSE",
        "contract/cbd_baseline.v": ROOT / "rtl/baseline/cbd.v",
        "contract/cbd_optimized.v": ROOT / "rtl/optimized/cbd.v",
        "contract/changes.patch": ROOT / "rtl/changes.patch",
    }
    for relative, local in local_contract.items():
        require(
            payloads[relative] == local.read_bytes(),
            f"archive/local contract mismatch: {relative}",
        )
    require(
        sha256_bytes(payloads["contract/publication_protocol.json"])
        == certificate["measurement"]["protocol_sha256"],
        "publication protocol identity differs",
    )
    require(
        sha256_bytes(payloads["contract/evaluator.py"])
        == certificate["measurement"]["evaluator_sha256"],
        "evaluator identity differs",
    )
    require(
        sha256_bytes(payloads["contract/cbd_equivalence_tb.sv"])
        == certificate["correctness"]["cycle_test_sha256"],
        "cycle contract identity differs",
    )
    require(
        sha256_bytes(payloads["contract/cbd_cycle.eqy"])
        == certificate["correctness"]["formal_config_sha256"],
        "formal contract identity differs",
    )
    require(
        sha256_bytes(payloads["contract/prepare_ace_probabilistic.py"])
        == certificate["measurement"]["activity"]["driver_transform_sha256"],
        "activity transform identity differs",
    )
    baseline_record = load_json_bytes(
        payloads["records/baseline-publication.json"],
        "records/baseline-publication.json",
    )
    optimized_record = load_json_bytes(
        payloads["records/optimized-publication.json"],
        "records/optimized-publication.json",
    )
    require(
        sha256_bytes(payloads["records/baseline-publication.json"])
        == certificate["measurement"]["baseline_record_sha256"],
        "archived baseline record identity differs",
    )
    require(
        sha256_bytes(payloads["records/optimized-publication.json"])
        == certificate["measurement"]["optimized_record_sha256"],
        "archived optimized record identity differs",
    )
    require(
        baseline_record.get("valid") is True
        and baseline_record.get("authority") == "frozen_baseline_measurement",
        "archived baseline record is not authoritative",
    )
    require(
        baseline_record.get("candidate_sha256") == EXPECTED_BASELINE_SHA256,
        "archived baseline record has the wrong RTL",
    )
    require(
        baseline_record.get("evaluator_version")
        == certificate["measurement"]["evaluator_version"]
        and baseline_record.get("seeds") == list(SEEDS),
        "archived baseline record has the wrong measurement contract",
    )
    require(
        optimized_record.get("valid") is True
        and optimized_record.get("tier") == "publication"
        and optimized_record.get("certified") is True
        and optimized_record.get("acceptance_decision") == certificate["decision"],
        "archived optimized record is not authoritative",
    )
    require(
        optimized_record.get("candidate_sha256") == EXPECTED_OPTIMIZED_SHA256
        and optimized_record.get("evaluator_version")
        == certificate["measurement"]["evaluator_version"],
        "archived optimized record has the wrong identity",
    )
    require(
        optimized_record.get("evidence_root") == "<SANITIZED_SOURCE_EVIDENCE_ROOT>",
        "archived optimized record was not sanitized as declared",
    )
    require(
        sha256_bytes(payloads["toolchain/k6_N10_I40_Fi6_L4_frac0_ff1_45nm.xml"])
        == EXPECTED_ARCH_SHA256,
        "archived architecture identity differs",
    )
    require(
        sha256_bytes(payloads["toolchain/45nm.xml"]) == EXPECTED_TECH_SHA256,
        "archived technology identity differs",
    )
    for design in ("baseline", "optimized"):
        cycle = payloads[f"correctness/{design}/cycle_run.log"]
        formal = payloads[f"correctness/{design}/formal.log"]
        require(
            b"CBD_EQUIVALENCE_CONTRACT_PASS cycles=239 checks=239" in cycle,
            f"cycle evidence failed: {design}",
        )
        require(
            b"Successfully proved designs equivalent" in formal,
            f"formal evidence failed: {design}",
        )
    pairs = {int(pair["seed"]): pair for pair in certificate["pairs"]}
    require(
        [row.get("seed") for row in baseline_record.get("per_seed", [])] == list(SEEDS),
        "archived baseline rows have the wrong seed pool",
    )
    require(
        [row.get("seed") for row in optimized_record.get("per_seed", [])]
        == list(SEEDS),
        "archived optimized rows have the wrong seed pool",
    )
    records = {
        "baseline": {int(row["seed"]): row for row in baseline_record["per_seed"]},
        "optimized": {int(row["seed"]): row for row in optimized_record["per_seed"]},
    }
    for design in ("baseline", "optimized"):
        for seed in SEEDS:
            prefix = f"runs/{design}/seed_{seed}/"
            selected = {
                name: payloads[prefix + name]
                for name in (
                    "vpr.crit_path.out",
                    "active.power",
                    "flow.time",
                    "flow_driver.log",
                )
            }
            derived = raw_metrics(selected, f"{design}.seed_{seed}")
            for metric, value in derived.items():
                close(
                    value,
                    records[design][seed][metric],
                    f"raw/record {design} seed {seed} {metric}",
                    tolerance=1e-8,
                )
                close(
                    value,
                    pairs[seed][design][metric],
                    f"raw {design} seed {seed} {metric}",
                    tolerance=1e-8,
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-archive", type=Path)
    args = parser.parse_args(argv)
    verify_manifest()
    verify_patch()
    certificate = verify_certificate()
    metadata = verify_full_evidence_metadata()
    print("ML-KEM CBD compact evidence: PASS")
    print("functional_cycles=239")
    print("formal_equivalence=PASS")
    print("held_out_pairs=64")
    print(f"composite_score={certificate['summary']['paired_ratio']['composite']:.12f}")
    print(
        f"improvement={certificate['summary']['improvement_percent']['composite']:.4f}%"
    )
    if args.evidence_archive is None:
        print("Full raw evidence: NOT CHECKED (pass --evidence-archive)")
    else:
        verify_full_evidence(certificate, metadata, args.evidence_archive)
        print("Full raw evidence: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VerificationError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"ML-KEM CBD evidence: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
