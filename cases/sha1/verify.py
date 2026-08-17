#!/usr/bin/env python3
"""Fail-closed verification of the published SHA-1 RTL comparison.

Without arguments this command verifies the compact Git package and recomputes
all published statistics.  With ``--evidence-archive`` it additionally hashes
and audits every member of the public raw-evidence release asset.
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
RESULT = ROOT / "results" / "certification.json"
PRIMARY_METRICS = ("area_total_mwta", "critical_path_delay_ns", "active_total_power_w")
SECONDARY_METRICS = (
    "energy_per_block_nj",
    "logic_block_area_mwta",
    "routing_area_mwta",
    "active_dynamic_power_w",
    "active_static_power_w",
    "idle_total_power_w",
    "fmax_mhz",
    "clb_blocks",
    "registers",
    "memories",
    "timing_channel_width",
)
ROW_METRICS = (*PRIMARY_METRICS, *SECONDARY_METRICS)
PAIRED_METRICS = (*PRIMARY_METRICS, "energy_per_block_nj")
METRIC_RANGES = {
    "area_total_mwta": (1_000_000.0, 1_000_000_000.0),
    "logic_block_area_mwta": (1_000_000.0, 1_000_000_000.0),
    "routing_area_mwta": (1_000.0, 1_000_000_000.0),
    "critical_path_delay_ns": (0.1, 10_000.0),
    "active_total_power_w": (1e-6, 1.0),
    "active_dynamic_power_w": (1e-6, 1.0),
    "active_static_power_w": (1e-6, 1.0),
    "idle_total_power_w": (1e-6, 1.0),
    "energy_per_block_nj": (1e-6, 1_000_000.0),
    "fmax_mhz": (0.01, 10_000.0),
    "clb_blocks": (1.0, 10_000_000.0),
    "registers": (1.0, 100_000_000.0),
    "memories": (0.0, 10_000_000.0),
    "timing_channel_width": (1.0, 1_000_000.0),
}
SEARCH_SEEDS = [1, 7, 19, 43, 97]
CERTIFICATION_SEEDS = [seed for seed in range(1, 69) if seed not in SEARCH_SEEDS]
TWO_SIDED_T_95_DF63 = 1.9983405425207417
ONE_SIDED_T_95_DF63 = 1.6694022217068127
BUNDLE_ROOT = "rtl-sha-vtr-primary-ppa-evidence-v2"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PROTECTED_ENGINE_MARKER = bytes.fromhex("636f646578")
EXPECTED_MODULE_PORTS = ("clk_i", "rst_i", "text_i", "text_o", "cmd_i", "cmd_w_i", "cmd_o")
EXPECTED_INTERFACE = "sha1(clk_i, rst_i, text_i[31:0], text_o[31:0], cmd_i[2:0], cmd_w_i, cmd_o[3:0])"
VTR_COMMIT = "95f5c6de9e158371ba7185bf97c07a84153735d6"
IMAGE_ID = "sha256:c0badc2d2bb57364ff37477b3d2c482ef01f7d3df6211e9802e2c54367c33baf"
ARCHITECTURE = "vtr_flow/arch/power/k6_N10_I40_Fi6_L4_frac0_ff1_45nm.xml"
ARCHITECTURE_SHA256 = "262792caef81931ae09b77d252158bde03c78954175d4b761e6d437317575307"
TECHNOLOGY = "vtr_flow/tech/PTM_45nm/45nm.xml"
TECHNOLOGY_SHA256 = "3080dea13bf7134109f8a83c79426ec0965e07639a61866fe9ae4bd05b5227cb"
NIST_CORPUS_SHA256 = "80bdcf3dabd50da28367f8c6e5d818c13d40d67cc8da897ce7efac553ed13df0"
EQY_COMMIT = "6734d8c2df366be50ea9e734c6cb10609b5f32c2"
EQY_PASS_MARKER_SHA256 = "9aeb6fa6171b28a9ae33345754b973b407317736d6ac333dd1e4a45d07c575be"
ACCEPTANCE_POLICY = {
    "validity": "all structural, functional, NIST, formal, route, power and evidence-integrity gates pass",
    "improvement": "composite one-sided 95% upper confidence bound < 1.0",
    "non_regression": "every primary metric one-sided 95% lower confidence bound <= 1.0",
    "sample": "fixed disjoint 64-seed pool; never extended after observing the result",
}
FULL_EVIDENCE_AUTHORITY = {
    "distribution": "GitHub release asset; public-only baseline and accepted raw evidence",
    "asset_name": "sha1-vtr45-full-evidence-v2.tar.gz",
    "release_url": "https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/tag/v2.1.0",
    "download_url": "https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/v2.1.0/sha1-vtr45-full-evidence-v2.tar.gz",
    "archive_sha256": "3c1d8badd0b8409da212857a07bcbe9f7e99fde74474f056b1a54f6392b01eff",
    "archive_bytes": 145891493,
    "bundle_manifest_path": "MANIFEST.json",
    "baseline_record_path": "records/baseline.json",
    "accepted_record_path": "records/accepted-certification.json",
    "certification_result_sha256": "49e9b983d5ede369e3b7e701a9e3866c14e1d119462b496768fdfc8439b163bf",
    "formal_driver_log_sha256": "2836ffc302152cb420ca6b2855205460ce6e6b5b1d8312c1ec6fa02e9f4f810a",
    "evidence_file_count": 5018,
}

REQUIRED_MANIFEST = {
    "Makefile",
    "README.md",
    "report/latex/generated/executive-ci.csv",
    "report/latex/generated/metrics.tex",
    "report/latex/generated/paired-improvements.csv",
    "report/latex/generated/seed-clouds.csv",
    "report/latex/technical-report.tex",
    "results/certification.json",
    "rtl/accepted/sha.v",
    "rtl/baseline-to-accepted.patch",
    "rtl/baseline/sha.v",
    "scripts/build_evidence_bundle.py",
    "scripts/generate_latex_data.py",
    "scripts/normalize_pdf_id.py",
    "scripts/reissue_v1_3_1_evidence.py",
    "scripts/reissue_public_evidence.py",
    "scripts/write_manifest.py",
    "technical-report.pdf",
    "tests/test_verify.py",
    "verify.py",
}


class VerificationError(RuntimeError):
    """A public claim or integrity condition failed verification."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_constant(value: str) -> None:
    raise VerificationError(f"non-finite JSON constant: {value}")


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json_bytes(payload: bytes, source: str) -> dict[str, Any]:
    try:
        value = json.loads(
            payload,
            object_pairs_hook=reject_duplicate_keys,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"invalid JSON in {source}: {exc}") from exc
    require(type(value) is dict, f"{source} must contain a JSON object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    return load_json_bytes(path.read_bytes(), str(path.relative_to(ROOT)))


def exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    actual = set(value)
    require(actual == expected, f"{where} keys differ: missing={sorted(expected-actual)}, extra={sorted(actual-expected)}")


def strict_bool(value: Any, where: str) -> bool:
    require(type(value) is bool, f"{where} must be Boolean")
    return value


def strict_int(value: Any, where: str) -> int:
    require(type(value) is int, f"{where} must be an integer")
    return value


def finite_number(value: Any, where: str, *, positive: bool = True) -> float:
    require(type(value) in (int, float), f"{where} must be numeric")
    number = float(value)
    require(math.isfinite(number), f"{where} must be finite")
    if positive:
        require(number > 0.0, f"{where} must be positive")
    return number


def close(actual: float, expected: Any, where: str, tolerance: float = 5e-12) -> None:
    target = finite_number(expected, where, positive=False)
    require(
        math.isclose(actual, target, rel_tol=tolerance, abs_tol=tolerance),
        f"{where} mismatch: calculated {actual!r}, published {target!r}",
    )


def confidence(log_values: list[float]) -> dict[str, float]:
    require(len(log_values) == 64, f"expected 64 paired values, got {len(log_values)}")
    mean = statistics.mean(log_values)
    stdev = statistics.stdev(log_values)
    error = stdev / math.sqrt(len(log_values))
    return {
        "estimate": math.exp(mean),
        "low": math.exp(mean - TWO_SIDED_T_95_DF63 * error),
        "high": math.exp(mean + TWO_SIDED_T_95_DF63 * error),
        "one_low": math.exp(mean - ONE_SIDED_T_95_DF63 * error),
        "one_high": math.exp(mean + ONE_SIDED_T_95_DF63 * error),
        "log_stdev": stdev,
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
    require(set(seen) == REQUIRED_MANIFEST, "SHA256SUMS does not cover the exact required public package")
    for relative, expected in seen.items():
        path = ROOT / relative
        require(path.is_file(), f"missing checksummed file: {relative}")
        require(sha256(path) == expected, f"checksum mismatch: {relative}")


def verify_patch() -> None:
    baseline_path = ROOT / "rtl" / "baseline" / "sha.v"
    accepted_path = ROOT / "rtl" / "accepted" / "sha.v"
    generated = "".join(
        difflib.unified_diff(
            baseline_path.read_text(encoding="utf-8").splitlines(keepends=True),
            accepted_path.read_text(encoding="utf-8").splitlines(keepends=True),
            fromfile="rtl/baseline/sha.v",
            tofile="rtl/accepted/sha.v",
        )
    )
    published = (ROOT / "rtl" / "baseline-to-accepted.patch").read_text(encoding="utf-8")
    require(generated == published, "published patch does not match the two RTL files")


def extract_rtl_interface(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    modules = list(re.finditer(r"\bmodule\s+sha1\s*\(([^)]*)\)\s*;", text, re.DOTALL))
    require(len(modules) == 1, f"expected one sha1 module declaration in {path.name}")
    module_ports = tuple(part.strip() for part in modules[0].group(1).split(","))
    require(module_ports == EXPECTED_MODULE_PORTS, f"wrong sha1 module port order in {path.name}")

    declarations: dict[str, tuple[str, str | None]] = {}
    pattern = re.compile(
        r"^\s*(input|output)\s*(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?([A-Za-z_]\w*)\s*;",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        direction, high, low, name = match.groups()
        if name not in EXPECTED_MODULE_PORTS:
            continue
        require(name not in declarations, f"duplicate port declaration for {name} in {path.name}")
        width = None if high is None else f"{high}:{low}"
        declarations[name] = (direction, width)
    require(set(declarations) == set(EXPECTED_MODULE_PORTS), f"incomplete sha1 port declarations in {path.name}")
    expected_directions = {
        "clk_i": "input",
        "rst_i": "input",
        "text_i": "input",
        "text_o": "output",
        "cmd_i": "input",
        "cmd_w_i": "input",
        "cmd_o": "output",
    }
    require(
        all(declarations[name][0] == expected_directions[name] for name in EXPECTED_MODULE_PORTS),
        f"wrong sha1 port direction in {path.name}",
    )
    rendered = [name if declarations[name][1] is None else f"{name}[{declarations[name][1]}]" for name in EXPECTED_MODULE_PORTS]
    return f"sha1({', '.join(rendered)})"


def verify_contract(data: dict[str, Any]) -> None:
    exact_keys(
        data,
        {"schema_version", "authority", "result", "source", "contract", "correctness", "score_definition", "acceptance_policy", "summary", "per_seed", "full_evidence"},
        "root",
    )
    require(data["schema_version"] == 2, "unsupported schema version")
    require(data["authority"] == "published_corrected_baseline_vs_accepted_primary_ppa_certification", "wrong authority")
    require(data["result"] == "accepted", "published result is not accepted")

    source = data["source"]
    require(type(source) is dict, "source must be an object")
    exact_keys(source, {"upstream_repository", "upstream_commit", "upstream_path", "corrected_baseline_sha256", "accepted_rtl_sha256"}, "source")
    require(source["upstream_repository"] == "https://github.com/verilog-to-routing/vtr-verilog-to-routing", "wrong upstream repository")
    require(source["upstream_commit"] == VTR_COMMIT, "wrong upstream commit")
    require(source["upstream_path"] == "vtr_flow/benchmarks/verilog/sha.v", "wrong upstream path")
    for name in ("corrected_baseline_sha256", "accepted_rtl_sha256"):
        require(type(source[name]) is str and HEX64.fullmatch(source[name]) is not None, f"invalid {name}")
    require(sha256(ROOT / "rtl/baseline/sha.v") == source["corrected_baseline_sha256"], "baseline RTL hash mismatch")
    require(sha256(ROOT / "rtl/accepted/sha.v") == source["accepted_rtl_sha256"], "accepted RTL hash mismatch")
    baseline_interface = extract_rtl_interface(ROOT / "rtl/baseline/sha.v")
    accepted_interface = extract_rtl_interface(ROOT / "rtl/accepted/sha.v")
    require(baseline_interface == accepted_interface, "baseline and accepted RTL interfaces differ")

    contract = data["contract"]
    require(type(contract) is dict, "contract must be an object")
    exact_keys(
        contract,
        {"editable_artifact", "interface", "busy_cycles_per_block", "nist_short_long_cases", "nist_corpus_sha256", "formal_status", "eqy_commit", "eqy_pass_marker_sha256", "vtr_commit", "image_id", "platform", "architecture", "architecture_sha256", "technology", "technology_sha256", "nominal_voltage_v", "temperature_c", "seed_count", "seeds", "search_seeds", "certification_seed_policy", "formal_semantics"},
        "contract",
    )
    require(contract["editable_artifact"] == "sha.v", "wrong editable artifact")
    require(contract["interface"] == baseline_interface, "published interface does not match the RTL declarations")
    require(contract["interface"] == EXPECTED_INTERFACE, "wrong interface contract")
    require(contract["busy_cycles_per_block"] == 80.0, "wrong busy-cycle count")
    require(strict_int(contract["nist_short_long_cases"], "nist_short_long_cases") == 129, "wrong NIST case count")
    require(contract["nist_corpus_sha256"] == NIST_CORPUS_SHA256, "wrong NIST corpus identity")
    require(contract["formal_status"] == "pass", "formal status is not pass")
    require(contract["eqy_commit"] == EQY_COMMIT, "wrong EQY commit")
    require(contract["eqy_pass_marker_sha256"] == EQY_PASS_MARKER_SHA256, "wrong EQY pass-marker identity")
    require(contract["formal_semantics"] == "two_state_defined_inputs_after_declared_reset", "formal semantics are not explicit")
    require(contract["vtr_commit"] == VTR_COMMIT, "wrong VTR commit")
    require(contract["image_id"] == IMAGE_ID, "wrong container image identity")
    require(contract["platform"] == "linux/amd64", "wrong measurement platform")
    require(contract["architecture"] == ARCHITECTURE, "wrong architecture path")
    require(contract["architecture_sha256"] == ARCHITECTURE_SHA256, "wrong architecture identity")
    require(contract["technology"] == TECHNOLOGY, "wrong technology path")
    require(contract["technology_sha256"] == TECHNOLOGY_SHA256, "wrong technology identity")
    require(contract["nominal_voltage_v"] == 0.9 and contract["temperature_c"] == 85, "wrong operating point")
    require(contract["search_seeds"] == SEARCH_SEEDS, "wrong search-seed pool")
    require(contract["seeds"] == CERTIFICATION_SEEDS, "wrong certification-seed pool")
    require(strict_int(contract["seed_count"], "seed_count") == 64, "wrong seed count")
    policy = contract["certification_seed_policy"]
    require(type(policy) is dict, "certification seed policy must be an object")
    exact_keys(policy, {"authority", "disjoint_from_search", "stopping_rule", "confidence_level"}, "certification_seed_policy")
    require(policy["authority"] == "fixed_sample_statistical_acceptance", "wrong certification authority")
    require(strict_bool(policy["disjoint_from_search"], "disjoint_from_search"), "seed pools are not disjoint")
    require(policy["stopping_rule"] == "fixed_n_64_no_extension", "wrong stopping rule")
    close(float(policy["confidence_level"]), 0.95, "confidence_level")

    correctness = data["correctness"]
    require(type(correctness) is dict, "correctness must be an object")
    exact_keys(correctness, {"functional_pass", "formal_pass", "certified", "accepted_improvement"}, "correctness")
    for key, value in correctness.items():
        require(strict_bool(value, f"correctness.{key}"), f"correctness gate failed: {key}")

    score = data["score_definition"]
    exact_keys(score, {"baseline", "direction", "primary_metrics", "formula", "energy_per_block_nj"}, "score_definition")
    require(score["baseline"] == 1.0 and score["direction"] == "lower_is_better", "wrong score baseline or direction")
    require(score["primary_metrics"] == list(PRIMARY_METRICS), "wrong primary metrics")
    require(score["formula"] == "geometric_mean(area_ratio, critical_path_delay_ratio, active_total_power_ratio)", "wrong score formula")
    require(score["energy_per_block_nj"] == "secondary_informative_metric", "energy is not marked secondary")

    acceptance = data["acceptance_policy"]
    exact_keys(acceptance, {"validity", "improvement", "non_regression", "sample"}, "acceptance_policy")
    require(acceptance == ACCEPTANCE_POLICY, "acceptance policy drift")

    evidence = data["full_evidence"]
    exact_keys(evidence, set(FULL_EVIDENCE_AUTHORITY), "full_evidence")
    require(evidence == FULL_EVIDENCE_AUTHORITY, "full-evidence authority drift")


def verify_statistics(data: dict[str, Any]) -> dict[str, float]:
    rows = data["per_seed"]
    require(type(rows) is list and len(rows) == 64, "per_seed must contain exactly 64 rows")
    seeds: list[int] = []
    by_metric: dict[str, tuple[list[float], list[float]]] = {name: ([], []) for name in ROW_METRICS}
    for index, row in enumerate(rows):
        require(type(row) is dict, f"per_seed[{index}] must be an object")
        exact_keys(row, {"seed", "baseline", "accepted"}, f"per_seed[{index}]")
        seed = strict_int(row["seed"], f"per_seed[{index}].seed")
        seeds.append(seed)
        for side in ("baseline", "accepted"):
            metrics = row[side]
            require(type(metrics) is dict, f"per_seed[{index}].{side} must be an object")
            exact_keys(metrics, set(ROW_METRICS), f"per_seed[{index}].{side}")
            for metric in ROW_METRICS:
                value = finite_number(metrics[metric], f"per_seed[{index}].{side}.{metric}", positive=metric != "memories")
                if metric == "memories":
                    require(value >= 0.0, "memory count cannot be negative")
                lower, upper = METRIC_RANGES[metric]
                require(lower <= value <= upper, f"per_seed[{index}].{side}.{metric} is outside the declared unit range")
                by_metric[metric][0 if side == "baseline" else 1].append(value)
        for side in ("baseline", "accepted"):
            metrics = row[side]
            expected_energy = float(metrics["active_total_power_w"]) * float(metrics["critical_path_delay_ns"]) * 5000.0 / 60.0
            close(expected_energy, metrics["energy_per_block_nj"], f"per_seed[{index}].{side}.energy_formula", tolerance=2e-10)
            expected_fmax = 1000.0 / float(metrics["critical_path_delay_ns"])
            close(expected_fmax, metrics["fmax_mhz"], f"per_seed[{index}].{side}.fmax", tolerance=8e-6)

    require(seeds == CERTIFICATION_SEEDS, "rows are not the fixed ordered certification pool")
    require(len(set(seeds)) == 64, "duplicate certification seed")

    summary = data["summary"]
    require(type(summary) is dict, "summary must be an object")
    exact_keys(summary, {"baseline", "accepted", "paired_ratio"}, "summary")
    baseline_summary = summary["baseline"]
    accepted_summary = summary["accepted"]
    require(type(baseline_summary) is dict and type(accepted_summary) is dict, "summary sides must be objects")
    exact_keys(baseline_summary, set(ROW_METRICS) | {"score"}, "summary.baseline")
    exact_keys(accepted_summary, set(ROW_METRICS) | {"score", "composite_per_seed_median"}, "summary.accepted")
    for metric in ROW_METRICS:
        close(statistics.median(by_metric[metric][0]), baseline_summary[metric], f"summary.baseline.{metric}")
        close(statistics.median(by_metric[metric][1]), accepted_summary[metric], f"summary.accepted.{metric}")
    close(1.0, baseline_summary["score"], "summary.baseline.score")

    paired = summary["paired_ratio"]
    require(type(paired) is dict, "paired_ratio must be an object")
    exact_keys(paired, set(PAIRED_METRICS) | {"composite"}, "summary.paired_ratio")
    metric_logs: dict[str, list[float]] = {}
    for metric in PAIRED_METRICS:
        baseline_values, accepted_values = by_metric[metric]
        logs = [math.log(candidate / reference) for reference, candidate in zip(baseline_values, accepted_values, strict=True)]
        metric_logs[metric] = logs
        calculated = confidence(logs)
        published = paired[metric]
        require(type(published) is dict, f"paired_ratio.{metric} must be an object")
        exact_keys(published, {"estimate", "ci95_two_sided", "lower_one_sided_95", "upper_one_sided_95", "log_stdev", "wins", "ties", "losses"}, f"paired_ratio.{metric}")
        require(type(published["ci95_two_sided"]) is list and len(published["ci95_two_sided"]) == 2, f"invalid CI for {metric}")
        close(calculated["estimate"], published["estimate"], f"paired_ratio.{metric}.estimate")
        close(calculated["low"], published["ci95_two_sided"][0], f"paired_ratio.{metric}.ci_low")
        close(calculated["high"], published["ci95_two_sided"][1], f"paired_ratio.{metric}.ci_high")
        close(calculated["one_low"], published["lower_one_sided_95"], f"paired_ratio.{metric}.one_low")
        close(calculated["one_high"], published["upper_one_sided_95"], f"paired_ratio.{metric}.one_high")
        close(calculated["log_stdev"], published["log_stdev"], f"paired_ratio.{metric}.log_stdev")
        wins = sum(value < 0.0 for value in logs)
        ties = sum(value == 0.0 for value in logs)
        losses = sum(value > 0.0 for value in logs)
        require((strict_int(published["wins"], "wins"), strict_int(published["ties"], "ties"), strict_int(published["losses"], "losses")) == (wins, ties, losses), f"wrong W/T/L for {metric}")

    composite_logs = [statistics.mean(metric_logs[metric][index] for metric in PRIMARY_METRICS) for index in range(64)]
    calculated = confidence(composite_logs)
    published = paired["composite"]
    require(type(published) is dict, "paired_ratio.composite must be an object")
    exact_keys(published, {"estimate", "ci95_two_sided", "lower_one_sided_95", "upper_one_sided_95", "log_stdev", "wins", "ties", "losses"}, "paired_ratio.composite")
    require(type(published["ci95_two_sided"]) is list and len(published["ci95_two_sided"]) == 2, "invalid composite CI")
    close(calculated["estimate"], accepted_summary["score"], "summary.accepted.score")
    close(calculated["estimate"], published["estimate"], "paired_ratio.composite.estimate")
    close(statistics.median(math.exp(value) for value in composite_logs), accepted_summary["composite_per_seed_median"], "summary.accepted.composite_per_seed_median")
    close(calculated["low"], published["ci95_two_sided"][0], "paired_ratio.composite.ci_low")
    close(calculated["high"], published["ci95_two_sided"][1], "paired_ratio.composite.ci_high")
    close(calculated["one_low"], published["lower_one_sided_95"], "paired_ratio.composite.one_low")
    close(calculated["one_high"], published["upper_one_sided_95"], "paired_ratio.composite.one_high")
    close(calculated["log_stdev"], published["log_stdev"], "paired_ratio.composite.log_stdev")
    require((published["wins"], published["ties"], published["losses"]) == (sum(v < 0 for v in composite_logs), sum(v == 0 for v in composite_logs), sum(v > 0 for v in composite_logs)), "wrong composite W/T/L")

    require(calculated["one_high"] < 1.0, "composite improvement gate failed")
    for metric in PRIMARY_METRICS:
        require(float(paired[metric]["lower_one_sided_95"]) <= 1.0, f"primary non-regression gate failed: {metric}")
    return calculated


def unique_text_match(pattern: str, text: str, where: str, flags: int = 0) -> re.Match[str]:
    matches = list(re.finditer(pattern, text, flags))
    require(len(matches) == 1, f"expected exactly one {where} record, found {len(matches)}")
    return matches[0]


def decode_evidence_text(payload: bytes, where: str) -> str:
    try:
        return payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise VerificationError(f"invalid UTF-8 in {where}: {exc}") from exc


def parse_vpr_metrics(payload: bytes, where: str) -> dict[str, float]:
    text = decode_evidence_text(payload, where)
    logic = float(
        unique_text_match(
            r"Total logic block area .*?:\s*([0-9.eE+-]+)$",
            text,
            f"{where} logic-area",
            re.MULTILINE,
        ).group(1)
    )
    routing = float(
        unique_text_match(
            r"Total routing area:\s*([0-9.eE+-]+),",
            text,
            f"{where} routing-area",
        ).group(1)
    )
    delay = unique_text_match(
        r"Final critical path delay \(least slack\):\s*([0-9.eE+-]+) ns, Fmax:\s*([0-9.eE+-]+) MHz",
        text,
        f"{where} routed timing",
    )
    channel = int(
        unique_text_match(
            r"Circuit successfully routed with a channel width factor of\s+(\d+)\.",
            text,
            f"{where} channel width",
        ).group(1)
    )
    registers = int(
        unique_text_match(
            r"^\s+\.latch\s*:\s*(\d+)\s*$",
            text,
            f"{where} register count",
            re.MULTILINE,
        ).group(1)
    )
    clb_blocks = int(
        unique_text_match(
            r"^\s+clb\s+(\d+)\s+",
            text,
            f"{where} CLB count",
            re.MULTILINE,
        ).group(1)
    )
    memories = int(
        unique_text_match(
            r"^\s+memory\s+(\d+)\s+",
            text,
            f"{where} memory count",
            re.MULTILINE,
        ).group(1)
    )
    return {
        "logic_block_area_mwta": logic,
        "routing_area_mwta": routing,
        "area_total_mwta": logic + routing,
        "critical_path_delay_ns": float(delay.group(1)),
        "fmax_mhz": float(delay.group(2)),
        "clb_blocks": float(clb_blocks),
        "registers": float(registers),
        "memories": float(memories),
        "timing_channel_width": float(channel),
    }


def parse_power_metrics(payload: bytes, where: str) -> tuple[float, float]:
    text = decode_evidence_text(payload, where)
    match = unique_text_match(
        r"^Total\s+([0-9.eE+-]+)\s+1\s+([0-9.eE+-]+)\s*$",
        text,
        f"{where} total-power",
        re.MULTILINE,
    )
    total = float(match.group(1))
    dynamic_fraction = float(match.group(2))
    require(math.isfinite(total) and total > 0.0, f"invalid total power in {where}")
    require(math.isfinite(dynamic_fraction) and 0.0 <= dynamic_fraction <= 1.0, f"invalid dynamic fraction in {where}")
    return total, dynamic_fraction


def derive_raw_metrics(files: dict[str, bytes], where: str) -> dict[str, float]:
    require(set(files) == {"vpr_stdout.log", "active.power", "idle.power", "sha.v"}, f"incomplete raw run tree: {where}")
    values = parse_vpr_metrics(files["vpr_stdout.log"], f"{where}/vpr_stdout.log")
    active_total, active_dynamic_fraction = parse_power_metrics(files["active.power"], f"{where}/active.power")
    idle_total, _ = parse_power_metrics(files["idle.power"], f"{where}/idle.power")
    values.update(
        {
            "active_total_power_w": active_total,
            "active_dynamic_power_w": active_total * active_dynamic_fraction,
            "active_static_power_w": active_total * (1.0 - active_dynamic_fraction),
            "idle_total_power_w": idle_total,
            "energy_per_block_nj": active_total
            * values["critical_path_delay_ns"]
            * 5000.0
            / 60.0,
        }
    )
    return values


def raw_close(actual: float, expected: Any, where: str) -> None:
    target = finite_number(expected, where, positive=False)
    require(
        math.isclose(actual, target, rel_tol=1e-9, abs_tol=1e-8),
        f"{where} is not derived from raw evidence: calculated {actual!r}, published {target!r}",
    )


def rows_by_seed(rows: Any, where: str) -> dict[int, dict[str, Any]]:
    require(type(rows) is list, f"{where} must be a list")
    result: dict[int, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        require(type(row) is dict, f"{where}[{index}] must be an object")
        seed = strict_int(row.get("seed"), f"{where}[{index}].seed")
        require(seed not in result, f"duplicate seed {seed} in {where}")
        result[seed] = row
    require(sorted(result) == CERTIFICATION_SEEDS, f"{where} does not contain the fixed certification seed set")
    return result


def verify_raw_measurement_bindings(
    data: dict[str, Any],
    raw_runs: dict[tuple[str, int], dict[str, bytes]],
    baseline_record: dict[str, Any],
    accepted_record: dict[str, Any],
) -> None:
    compact = rows_by_seed(data["per_seed"], "compact per_seed")
    baseline_rows = rows_by_seed(baseline_record.get("certification_per_seed"), "baseline certification_per_seed")
    accepted_rows = rows_by_seed(accepted_record.get("per_seed"), "accepted per_seed")
    expected_runs = {(side, seed) for side in ("baseline", "accepted") for seed in CERTIFICATION_SEEDS}
    require(set(raw_runs) == expected_runs, "raw archive does not contain exactly 128 certification run trees")

    for side, record_rows, rtl_key in (
        ("baseline", baseline_rows, "corrected_baseline_sha256"),
        ("accepted", accepted_rows, "accepted_rtl_sha256"),
    ):
        for seed in CERTIFICATION_SEEDS:
            where = f"runs/{side}/seed_{seed}"
            files = raw_runs[(side, seed)]
            require(sha256_bytes(files["sha.v"]) == data["source"][rtl_key], f"{where}/sha.v has the wrong RTL identity")
            raw = derive_raw_metrics(files, where)
            compact_metrics = compact[seed][side]
            record_metrics = record_rows[seed]
            for metric in ROW_METRICS:
                raw_close(raw[metric], compact_metrics[metric], f"compact {side} seed {seed} {metric}")
                raw_close(raw[metric], record_metrics[metric], f"archived record {side} seed {seed} {metric}")


def verify_full_evidence(data: dict[str, Any], archive_path: Path) -> None:
    evidence = data["full_evidence"]
    require(type(evidence) is dict, "full_evidence must be an object")
    exact_keys(evidence, {"distribution", "asset_name", "release_url", "download_url", "archive_sha256", "archive_bytes", "bundle_manifest_path", "baseline_record_path", "accepted_record_path", "certification_result_sha256", "formal_driver_log_sha256", "evidence_file_count"}, "full_evidence")
    require(archive_path.is_file(), f"missing evidence archive: {archive_path}")
    require(archive_path.name == evidence["asset_name"], "wrong evidence archive filename")
    require(archive_path.stat().st_size == strict_int(evidence["archive_bytes"], "archive_bytes"), "evidence archive byte count mismatch")
    require(sha256(archive_path) == evidence["archive_sha256"], "evidence archive SHA-256 mismatch")

    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
        require(members, "evidence archive is empty")
        file_members: dict[str, tarfile.TarInfo] = {}
        for member in members:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and ".." not in path.parts, f"unsafe archive member: {member.name}")
            require(member.isfile(), f"non-regular archive member: {member.name}")
            require(member.name not in file_members, f"duplicate archive member: {member.name}")
            file_members[member.name] = member
        manifest_name = f"{BUNDLE_ROOT}/{evidence['bundle_manifest_path']}"
        require(manifest_name in file_members, "missing internal evidence manifest")
        stream = archive.extractfile(file_members[manifest_name])
        require(stream is not None, "cannot read internal evidence manifest")
        manifest = load_json_bytes(stream.read(), "evidence MANIFEST.json")
        exact_keys(manifest, {"schema_version", "bundle", "purpose", "member_count", "members", "transformations", "omissions"}, "evidence manifest")
        require(manifest["schema_version"] == 3 and manifest["bundle"] == BUNDLE_ROOT, "wrong evidence manifest identity")
        require(manifest["purpose"] == "primary_ppa_public_evidence_without_optimization_infrastructure", "wrong evidence purpose")
        entries = manifest["members"]
        require(type(entries) is list and len(entries) == strict_int(manifest["member_count"], "member_count"), "invalid evidence member count")
        expected_names = {manifest_name}
        payloads: dict[str, bytes] = {}
        source_hashes: dict[str, str] = {}
        public_hashes: dict[str, str] = {}
        raw_runs: dict[tuple[str, int], dict[str, bytes]] = {}
        for index, entry in enumerate(entries):
            require(type(entry) is dict, f"manifest member {index} must be an object")
            exact_keys(entry, {"path", "bytes", "sha256", "source_sha256"}, f"manifest member {index}")
            relative = entry["path"]
            require(type(relative) is str, f"manifest path {index} must be a string")
            name = f"{BUNDLE_ROOT}/{relative}"
            require(name not in expected_names, f"duplicate internal manifest path: {relative}")
            expected_names.add(name)
            require(name in file_members, f"manifest references missing member: {relative}")
            stream = archive.extractfile(file_members[name])
            require(stream is not None, f"cannot read evidence member: {relative}")
            payload = stream.read()
            require(len(payload) == strict_int(entry["bytes"], f"manifest[{relative}].bytes"), f"byte count mismatch: {relative}")
            require(sha256_bytes(payload) == entry["sha256"], f"hash mismatch: {relative}")
            require(b"/Users/juanjosefernandezmorales/" not in payload, f"unsanitized host path: {relative}")
            require(PROTECTED_ENGINE_MARKER not in payload.lower(), f"operational engine marker leaked: {relative}")
            public_hashes[relative] = entry["sha256"]
            require(type(entry["source_sha256"]) is str and HEX64.fullmatch(entry["source_sha256"]) is not None, f"invalid source hash: {relative}")
            source_hashes[relative] = entry["source_sha256"]
            if relative in {"records/accepted-certification.json", "records/baseline.json", "rtl/baseline/sha.v", "rtl/accepted/sha.v", "runs/accepted/formal_driver.log", "runs/accepted/sha1_cycle/PASS", "runs/accepted/nist_run.log", "flow/benchmarks/sha_vtr_manifest.json"}:
                payloads[relative] = payload
            raw_match = re.fullmatch(r"runs/(baseline|accepted)/seed_(\d+)/(vpr_stdout\.log|active\.power|idle\.power|sha\.v)", relative)
            if raw_match is not None:
                side, seed_text, filename = raw_match.groups()
                raw_runs.setdefault((side, int(seed_text)), {})[filename] = payload
        require(set(file_members) == expected_names, "archive contains unmanifested members")
        require(sum(name.startswith(f"{BUNDLE_ROOT}/runs/accepted/") for name in file_members) == strict_int(evidence["evidence_file_count"], "evidence_file_count"), "accepted evidence file count mismatch")

        transformations = manifest["transformations"]
        exact_keys(transformations, {"modified_member_count", "modified_members"}, "evidence transformations")
        transformed = transformations["modified_members"]
        require(type(transformed) is list and len(transformed) == strict_int(transformations["modified_member_count"], "transformation count"), "invalid transformation records")
        transformed_paths: set[str] = set()
        for index, item in enumerate(transformed):
            require(type(item) is dict, f"transformation record {index} must be an object")
            exact_keys(item, {"path", "description", "source_sha256", "public_sha256"}, f"transformation record {index}")
            path = item["path"]
            require(type(path) is str and path not in transformed_paths, f"duplicate transformation path: {path}")
            transformed_paths.add(path)
            require(type(item["description"]) is str and bool(item["description"]), f"missing transformation description: {path}")
            require(item["source_sha256"] == source_hashes.get(path), f"transformation source hash mismatch: {path}")
            require(item["public_sha256"] == public_hashes.get(path), f"transformation public hash mismatch: {path}")
        require(transformed_paths == {path for path, source_hash in source_hashes.items() if source_hash != public_hashes[path]}, "source/public hash differences are not completely explained")

        omissions = manifest["omissions"]
        exact_keys(omissions, {"omitted_member_count", "omitted_members"}, "evidence omissions")
        omitted = omissions["omitted_members"]
        require(type(omitted) is list and len(omitted) == strict_int(omissions["omitted_member_count"], "omission count"), "invalid omission records")
        expected_omissions = {"flow/config.py", "flow/runner.py", "flow/evaluator.py", "flow/eval_script.py"}
        omitted_paths: set[str] = set()
        for index, item in enumerate(omitted):
            exact_keys(item, {"path", "reason", "source_sha256"}, f"omission record {index}")
            require(type(item["path"]) is str and item["path"] not in omitted_paths, f"duplicate omission path: {index}")
            omitted_paths.add(item["path"])
            require(type(item["reason"]) is str and bool(item["reason"]), f"missing omission reason: {item['path']}")
            require(type(item["source_sha256"]) is str and HEX64.fullmatch(item["source_sha256"]) is not None, f"invalid omission source hash: {item['path']}")
        require(omitted_paths == expected_omissions, "wrong operational omission set")

    require(sha256_bytes(payloads["records/accepted-certification.json"]) == evidence["certification_result_sha256"], "accepted certification record hash mismatch")
    require(sha256_bytes(payloads["runs/accepted/formal_driver.log"]) == evidence["formal_driver_log_sha256"], "formal driver hash mismatch")
    require(sha256_bytes(payloads["runs/accepted/sha1_cycle/PASS"]) == data["contract"]["eqy_pass_marker_sha256"], "EQY PASS marker hash mismatch")
    require(sha256_bytes(payloads["rtl/baseline/sha.v"]) == data["source"]["corrected_baseline_sha256"], "bundle baseline RTL mismatch")
    require(sha256_bytes(payloads["rtl/accepted/sha.v"]) == data["source"]["accepted_rtl_sha256"], "bundle accepted RTL mismatch")
    accepted_record = load_json_bytes(payloads["records/accepted-certification.json"], "accepted certification record")
    baseline_record = load_json_bytes(payloads["records/baseline.json"], "baseline certification record")
    require(strict_bool(accepted_record.get("valid"), "accepted_record.valid"), "accepted record invalid")
    require(strict_bool(accepted_record.get("certified"), "accepted_record.certified"), "accepted record not certified")
    require(strict_bool(accepted_record.get("accepted_improvement"), "accepted_record.accepted_improvement"), "accepted record not accepted")
    require(accepted_record.get("trace", {}).get("candidate_sha256") == data["source"]["accepted_rtl_sha256"], "accepted record is bound to a different RTL")
    require(b"SHA1_NIST_SHAVS_PASS cases=129" in payloads["runs/accepted/nist_run.log"], "NIST pass log missing expected result")
    archived_contract = load_json_bytes(payloads["flow/benchmarks/sha_vtr_manifest.json"], "archived flow contract")
    require(archived_contract.get("functional_contract", {}).get("interface") == data["contract"]["interface"], "archived flow interface differs from the compact contract")
    verify_raw_measurement_bindings(data, raw_runs, baseline_record, accepted_record)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-archive", type=Path)
    args = parser.parse_args(argv)

    verify_checksums()
    verify_patch()
    data = load_json(RESULT)
    verify_contract(data)
    composite = verify_statistics(data)
    print("SHA-1 compact evidence: PASS")
    print("Compact package consistency: PASS")
    print("paired_seeds=64")
    print(f"composite_estimate={composite['estimate']:.12f}")
    print(f"composite_per_seed_median={data['summary']['accepted']['composite_per_seed_median']:.12f}")
    print(f"improvement={100*(1-composite['estimate']):.2f}% (95% CI {100*(1-composite['high']):.2f}% to {100*(1-composite['low']):.2f}%)")
    if args.evidence_archive is None:
        print("Full raw evidence: NOT CHECKED (pass --evidence-archive)")
    else:
        verify_full_evidence(data, args.evidence_archive.expanduser().resolve())
        print("Full raw evidence: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (VerificationError, KeyError, TypeError, ValueError, OSError, tarfile.TarError) as exc:
        print(f"Verification: FAIL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1) from exc
