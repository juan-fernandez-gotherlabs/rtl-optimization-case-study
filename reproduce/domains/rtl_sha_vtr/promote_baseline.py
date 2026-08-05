"""Promote two matching certifications into the evaluator's locked baseline."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domains.rtl_sha_vtr.compare_reproduction import compare  # noqa: E402
from domains.rtl_sha_vtr.evaluator import (  # noqa: E402
    BASELINE_EVIDENCE_PATH,
    BENCHMARK_DIR,
    MANIFEST_PATH,
    sha256_file,
)


def build_baseline(
    primary: dict[str, Any], reproduction: dict[str, Any]
) -> dict[str, Any]:
    """Build a public baseline only from two matching successful runs."""
    comparison = compare(primary, reproduction)
    if not comparison["match"]:
        raise ValueError(
            "clean reproduction does not match: " + "; ".join(comparison["failures"])
        )
    manifest_sha256 = sha256_file(MANIFEST_PATH)
    golden_sha256 = sha256_file(BENCHMARK_DIR / "sha.v")
    if primary.get("manifest_sha256") != manifest_sha256:
        raise ValueError(
            "certification manifest hash differs from the current checkout"
        )
    if primary.get("golden_seed_sha256") != golden_sha256:
        raise ValueError(
            "certification golden seed hash differs from the current checkout"
        )
    return {
        "schema_version": 4,
        "contract_revision": json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))[
            "contract_revision"
        ],
        "status": "success",
        "valid": True,
        "accepted_improvement": False,
        "score": 1.0,
        "baseline_score": 1.0,
        "manifest_sha256": manifest_sha256,
        "golden_seed_sha256": golden_sha256,
        "measurement_environment": primary["measurement_environment"],
        "environment_inventory": primary["environment_inventory"],
        "functional": primary["functional"],
        "nist_short_long": primary["nist_short_long"],
        "certification_vectors": primary["certification_vectors"],
        "mutation": primary["mutation"],
        "activity": primary["activity"],
        "seeds": primary["seeds"],
        "search_per_seed": primary["search_per_seed"],
        "certification_per_seed": primary["per_seed"],
        "per_seed": primary["per_seed"],
        "certification_aggregate": primary["aggregate"],
        "search_aggregate": primary["search_aggregate"],
        "seed_sets": {
            "search": {
                "seeds": primary["search_seeds"],
                "count": len(primary["search_seeds"]),
                "authority": "provisional_ranking_only",
                "exposed_to_optimizer": True,
            },
            "certification": {
                "seeds": primary["seeds"],
                "count": len(primary["seeds"]),
                "authority": "fixed_sample_statistical_acceptance",
                "exposed_to_optimizer": False,
                "disjoint_from_search": True,
                "stopping_rule": "fixed_n_64_no_extension",
                "confidence_level": 0.95,
            },
        },
        "statistical_baseline": {
            "status": "complete",
            "seed_count": len(primary["seeds"]),
            "qualification_relationship": "Measured as part of two clean baseline certifications.",
        },
        "aggregate": primary["aggregate"],
        "power_warning_fingerprints": primary["power_warning_fingerprints"],
        "reproduction": {
            "match": True,
            "metric_differences": comparison["metric_differences"],
            "calibrates_acceptance_margins": True,
            "median_relative_limit": 0.005,
            "worst_relative_limit": 0.01,
            "primary_evidence_root_sha256": primary["evidence_root_sha256"],
            "reproduction_evidence_root_sha256": reproduction["evidence_root_sha256"],
            "primary_completed_at_utc": primary["completed_at_utc"],
            "reproduction_completed_at_utc": reproduction["completed_at_utc"],
        },
        "limitations": (
            "Academic open-FPGA VTR 45 nm estimate; not a commercial FPGA, ASIC, "
            "manufactured silicon result, or signoff. SHA-1 is a legacy benchmark only."
        ),
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> int:
    """Validate both evidence records and atomically write the public baseline."""
    parser = argparse.ArgumentParser(
        description="Promote two matching SHA/VTR certifications."
    )
    parser.add_argument("primary", type=Path)
    parser.add_argument("reproduction", type=Path)
    parser.add_argument("--output", type=Path, default=BASELINE_EVIDENCE_PATH)
    args = parser.parse_args()
    try:
        payload = build_baseline(
            json.loads(args.primary.read_text(encoding="utf-8")),
            json.loads(args.reproduction.read_text(encoding="utf-8")),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"RTL_SHA_VTR_BASELINE_PROMOTION_BLOCKED: {exc}", file=sys.stderr)
        return 1
    _atomic_write(args.output, payload)
    print(f"RTL_SHA_VTR_BASELINE_PROMOTED evidence={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
