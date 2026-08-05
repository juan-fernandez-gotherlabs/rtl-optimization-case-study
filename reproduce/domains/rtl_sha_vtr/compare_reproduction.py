"""Fail-closed comparison of two independently certified baseline runs."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from domains.rtl_sha_vtr.evaluator import CERTIFICATION_SEEDS

PRIMARY = ("area_total_mwta", "critical_path_delay_ns", "energy_per_block_nj")
ENVIRONMENT_HASHES = (
    "tool_versions_sha256",
    "dpkg_manifest_sha256",
    "vtr_submodules_sha256",
    "pip_manifest_sha256",
    "python_lock_sha256",
    "cyclonedx_sbom_sha256",
    "license_manifest_sha256",
    "debian_package_copyrights_sha256",
)


def compare(first: dict, second: dict) -> dict:
    """Compare frozen inputs and paired PPA within the release tolerances."""
    failures: list[str] = []
    for label, payload in (("first", first), ("second", second)):
        if payload.get("status") != "success":
            failures.append(f"{label} evidence is not successful")
    for key in ("manifest_sha256", "golden_seed_sha256", "seeds"):
        if first.get(key) != second.get(key):
            failures.append(f"frozen field differs: {key}")
    for key in ("tag", "id", "platform"):
        first_value = first.get("measurement_environment", {}).get("image", {}).get(key)
        second_value = (
            second.get("measurement_environment", {}).get("image", {}).get(key)
        )
        if not first_value or first_value != second_value:
            failures.append(f"measurement image field differs or is missing: {key}")
    for key in ENVIRONMENT_HASHES:
        first_value = first.get("environment_inventory", {}).get(key)
        second_value = second.get("environment_inventory", {}).get(key)
        if not first_value or first_value != second_value:
            failures.append(f"environment inventory differs or is missing: {key}")
    for key in (
        "active_vector_sha256",
        "idle_vector_sha256",
        "synthesized_blif_sha256",
    ):
        if first.get("activity", {}).get(key) != second.get("activity", {}).get(key):
            failures.append(f"activity field differs: {key}")
    for key in ("short_long_cases", "corpus_sha256"):
        first_value = first.get("nist_short_long", {}).get(key)
        second_value = second.get("nist_short_long", {}).get(key)
        if first_value is None or first_value != second_value:
            failures.append(f"NIST Short/Long field differs or is missing: {key}")
    for key in (
        "upstream_abc_expected_failure",
        "monte_carlo_hashes",
        "monte_corpus_sha256",
    ):
        first_value = first.get("certification_vectors", {}).get(key)
        second_value = second.get("certification_vectors", {}).get(key)
        if first_value is None or first_value != second_value:
            failures.append(f"certification vector field differs or is missing: {key}")
    for key in (
        "mutation_count",
        "coverage_percent",
        "contract_rejected_mutations",
        "simulation_detected_mutations",
        "formal_only_rejected_mutations",
        "equivalent_mutations",
        "simulation_only_coverage_percent",
    ):
        first_value = first.get("mutation", {}).get(key)
        second_value = second.get("mutation", {}).get(key)
        if first_value is None or first_value != second_value:
            failures.append(f"mutation field differs or is missing: {key}")
    if first.get("power_warning_fingerprints") != second.get(
        "power_warning_fingerprints"
    ):
        failures.append("power warning fingerprints differ")

    first_rows = {int(row["seed"]): row for row in first.get("per_seed", [])}
    second_rows = {int(row["seed"]): row for row in second.get("per_seed", [])}
    if set(first_rows) != set(CERTIFICATION_SEEDS) or set(second_rows) != set(
        first_rows
    ):
        failures.append("paired seed set is incomplete")
    metric_differences: dict[str, dict[str, float]] = {}
    if not failures:
        for metric in PRIMARY:
            paired = [
                abs(second_rows[seed][metric] / first_rows[seed][metric] - 1.0)
                for seed in sorted(first_rows)
            ]
            median = statistics.median(paired)
            worst = max(paired)
            metric_differences[metric] = {
                "median_relative_difference": median,
                "worst_relative_difference": worst,
            }
            if median > 0.005:
                failures.append(f"{metric} reproduction median difference exceeds 0.5%")
            if worst > 0.01:
                failures.append(f"{metric} reproduction worst difference exceeds 1%")
    return {
        "match": not failures,
        "failures": failures,
        "metric_differences": metric_differences,
    }


def main() -> int:
    """Compare two JSON evidence summaries and optionally persist the report."""
    parser = argparse.ArgumentParser()
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compare(
        json.loads(args.first.read_text(encoding="utf-8")),
        json.loads(args.second.read_text(encoding="utf-8")),
    )
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if result["match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
