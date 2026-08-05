"""Standalone Docker-backed evaluator for the VTR SHA RTL domain."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _result_payload(result: Any) -> dict[str, Any]:
    """Expose the stable evaluator contract without hiding evidence in trace."""
    ratios = {
        "estimate": result.trace.get("ratio_estimates", {}),
        "worst_observed": result.trace.get("worst_observed_ratios", {}),
    }
    evidence = result.trace.get("evidence", {})
    return {
        "score": result.score,
        "metrics": result.metrics,
        "valid": result.valid,
        "accepted_improvement": bool(result.trace.get("accepted_improvement", False)),
        "evaluation_tier": result.trace.get("evaluation_tier"),
        "certified": bool(result.trace.get("certified", False)),
        "acceptance_decision": result.trace.get("acceptance_decision"),
        "statistical_confidence": result.trace.get("statistical_confidence"),
        "descriptive_uncertainty": result.trace.get("descriptive_uncertainty"),
        "ratios": ratios,
        "proxy_ratios": result.trace.get("proxy_ratios", {}),
        "per_seed": result.trace.get("per_seed", []),
        "evidence": evidence,
        "evidence_hashes": (
            evidence.get("hashes", {}) if isinstance(evidence, dict) else {}
        ),
        "candidate_id": result.candidate_id,
        "trace": result.trace,
        "baseline_score": result.baseline_score,
        "notes": result.notes,
    }


def main() -> int:
    """Evaluate one materialized workspace and always write a result payload."""
    from domains.rtl_sha_vtr.evaluator import RtlShaVtrEvaluator

    parser = argparse.ArgumentParser(
        description="Evaluate one SHA RTL candidate with the pinned Docker/VTR flow."
    )
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--candidate-id", default="candidate")
    parser.add_argument(
        "--tier",
        choices=("search", "certification"),
        default="search",
        help="Use five exposed search seeds or the disjoint fixed 64-seed certification pool.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        help="New or empty directory for persistent logs; mandatory for certification.",
    )
    args, _ = parser.parse_known_args()
    result = RtlShaVtrEvaluator(tier=args.tier).evaluate_workspace(
        Path(args.workspace),
        candidate_id=args.candidate_id,
        evidence_dir=args.evidence_dir,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(_result_payload(result), indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
