"""One-command customer preflight: correctness plus one disposable PPA seed."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domains.rtl_sha_vtr.evaluator import (  # noqa: E402
    PRIMARY_METRICS,
    RunnerFailure,
    SeedMetrics,
    baseline_seed_metrics,
    build_default_domain,
    candidate_path,
    preflight,
    sha256_file,
)
from domains.rtl_sha_vtr.runner import DockerPpa45Runner  # noqa: E402


def single_seed_ratios(
    measured: SeedMetrics, baseline: SeedMetrics
) -> dict[str, float]:
    """Return transparent diagnostic ratios without making an acceptance decision."""
    if measured.seed != baseline.seed:
        raise ValueError("demo and baseline seed must match")
    return {
        name: float(getattr(measured, name)) / float(getattr(baseline, name))
        for name in PRIMARY_METRICS
    }


def _write_result(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    """Run fail-closed functional/formal gates followed by disposable seed 1."""
    parser = argparse.ArgumentParser(
        description="Run the customer SHA/VTR correctness and one-seed PPA preflight."
    )
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--results", required=True, type=Path)
    args = parser.parse_args()
    if args.results.exists() and any(args.results.iterdir()):
        parser.error("--results must be a new or empty directory")
    args.results.mkdir(parents=True, exist_ok=True)
    output = args.results / "demo_preflight.json"
    spec = build_default_domain()
    diagnostics = preflight(args.workspace, spec)
    if diagnostics:
        _write_result(
            output,
            {
                "schema_version": 1,
                "status": "blocked_prerequisites",
                "valid_for_preflight": False,
                "acceptance_decision": None,
                "diagnostics": list(diagnostics),
            },
        )
        return 1

    candidate = candidate_path(args.workspace)
    runner = DockerPpa45Runner(spec)
    started = datetime.now(timezone.utc)
    try:
        inventory = runner.collect_environment(candidate, args.results)
        functional = runner.run_candidate_correctness(candidate, args.results)
        nist = runner.run_nist_short_long(candidate, args.results)
        activity = runner.prepare_activity(candidate, args.results)
        measured = runner.run_seed(candidate, args.results, 1, run_label="demo")
        baseline = next(item for item in baseline_seed_metrics(spec) if item.seed == 1)
        ratios = single_seed_ratios(measured, baseline)
    except (RunnerFailure, OSError, ValueError, StopIteration) as exc:
        payload: dict[str, Any] = {
            "schema_version": 1,
            "status": (
                exc.stage if isinstance(exc, RunnerFailure) else "preflight_integrity"
            ),
            "valid_for_preflight": False,
            "acceptance_decision": None,
            "diagnostics": [str(exc)],
        }
        if isinstance(exc, RunnerFailure):
            payload["stdout_tail"] = exc.stdout_tail
            payload["stderr_tail"] = exc.stderr_tail
        _write_result(output, payload)
        return 1

    evidence_hashes = {
        str(path.relative_to(args.results)): sha256_file(path)
        for path in sorted(args.results.rglob("*"))
        if path.is_file() and path != output
    }
    payload = {
        "schema_version": 1,
        "status": "preflight_pass",
        "valid_for_preflight": True,
        "acceptance_decision": None,
        "acceptance_note": "One seed is diagnostic only; the fixed disjoint 64-seed pool determines acceptance.",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_sha256": sha256_file(candidate),
        "environment_inventory": inventory,
        "functional": functional,
        "nist_short_long": nist,
        "activity": activity,
        "seed_1": asdict(measured),
        "seed_1_ratios_to_certified_baseline": ratios,
        "evidence_hashes": evidence_hashes,
        "evidence_root_sha256": hashlib.sha256(
            json.dumps(evidence_hashes, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    _write_result(output, payload)
    print(f"RTL_SHA_VTR_DEMO_PREFLIGHT_PASS evidence={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
