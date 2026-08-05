"""Agent-facing local submission for the non-certifying SHA/VTR triage tier."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domains.rtl_sha_vtr.evaluator import (  # noqa: E402
    PRIMARY_METRICS,
    baseline_seed_metrics,
    build_default_domain,
)
from domains.rtl_sha_vtr.triage import default_cache_dir, evaluate_triage  # noqa: E402

LOCAL_SUBMISSION_SCHEMA_VERSION = 4


def _finite_float(value: object) -> float | None:
    """Return a finite float or ``None`` for missing/invalid values."""
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def build_local_submission_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Project a verbose triage payload into concise feedback for a coding agent."""
    spec = build_default_domain()
    baseline = baseline_seed_metrics(spec, tier="search")
    scoring = spec.manifest["scoring"]
    triage_pass = bool(payload.get("triage_pass"))
    score = _finite_float(payload.get("provisional_score"))
    ratios_raw = payload.get("proxy_ratios")
    metrics_raw = payload.get("metrics")
    uncertainty_raw = payload.get("descriptive_uncertainty")
    ratios = ratios_raw if isinstance(ratios_raw, dict) else {}
    metrics = metrics_raw if isinstance(metrics_raw, dict) else {}
    uncertainty = uncertainty_raw if isinstance(uncertainty_raw, dict) else {}
    composite = uncertainty.get("composite", {})

    comparisons: dict[str, dict[str, float | None]] = {}
    for name in PRIMARY_METRICS:
        ratio = _finite_float(ratios.get(name))
        candidate_value = _finite_float(metrics.get(name))
        baseline_value = statistics.median(float(getattr(item, name)) for item in baseline)
        comparisons[name] = {
            "candidate": candidate_value,
            "baseline_search_median": baseline_value,
            "ratio": ratio,
            "delta_percent": None if ratio is None else (ratio - 1.0) * 100.0,
        }

    return {
        "schema_version": LOCAL_SUBMISSION_SCHEMA_VERSION,
        "authority": "non_certifying_local_submission",
        "candidate_id": payload.get("candidate_id"),
        "candidate_sha256": payload.get("candidate_sha256"),
        "triage_pass": triage_pass,
        "status": payload.get("status"),
        "provisional_score": score,
        "baseline_score": float(scoring["baseline_score"]),
        "formal_status": payload.get("formal_status", "not_run"),
        "certified": False,
        "acceptance_decision": None,
        "cache_hit": (bool(payload.get("cache", {}).get("hit")) if isinstance(payload.get("cache"), dict) else False),
        "comparisons": comparisons,
        "search_uncertainty": {
            "authority": uncertainty.get("authority", "descriptive_search_only"),
            "ci95_two_sided": composite.get("ci95_two_sided"),
            "paired_log_stdev": composite.get("log_stdev"),
            "wins": composite.get("wins"),
            "ties": composite.get("ties"),
            "losses": composite.get("losses"),
            "fragile_vs_baseline": uncertainty.get("fragile_vs_reference"),
        },
        "diagnostics": payload.get("diagnostics", []),
        "evidence_root": (
            payload.get("evidence", {}).get("root") if isinstance(payload.get("evidence"), dict) else None
        ),
        "warning": (
            "This five-seed search is a ranking aid produced only after EQY passes. "
            "It does not run the disjoint 64-seed certification and cannot establish an accepted improvement."
        ),
    }


def _render_text(report: dict[str, Any]) -> str:
    """Render compact feedback intended to be read directly by a coding agent."""
    lines = [
        "EVOLTHER RTL SHA LOCAL SUBMISSION (NON-CERTIFYING)",
        f"status={report['status']}",
        f"provisional_score={report['provisional_score']}",
        f"baseline_score={report['baseline_score']}",
        f"cache_hit={str(report['cache_hit']).lower()}",
        f"search_uncertainty={report['search_uncertainty']}",
    ]
    for name, comparison in report["comparisons"].items():
        lines.append(
            f"{name}: candidate={comparison['candidate']} baseline_search_median="
            f"{comparison['baseline_search_median']} "
            f"ratio={comparison['ratio']} delta_percent={comparison['delta_percent']}"
        )
    lines.extend(
        [
            f"formal_status={report['formal_status']}",
            f"warning={report['warning']}",
        ]
    )
    diagnostics = report.get("diagnostics")
    if diagnostics:
        lines.append("diagnostics=" + " | ".join(str(item) for item in diagnostics))
    return "\n".join(lines)


def main() -> int:
    """Run one cached local submission and print actionable, non-certifying feedback."""
    parser = argparse.ArgumentParser(description="Submit one SHA RTL candidate to formal-gated five-seed search.")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--candidate-id", default="codex-local")
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path for the complete triage payload and report.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the concise report as JSON instead of text.",
    )
    args = parser.parse_args()

    payload = evaluate_triage(
        args.workspace.resolve(),
        candidate_id=args.candidate_id,
        cache_dir=args.cache_dir,
    )
    report = build_local_submission_report(payload)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps({"report": report, "triage_result": payload}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else _render_text(report))
    return 0 if report["triage_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
