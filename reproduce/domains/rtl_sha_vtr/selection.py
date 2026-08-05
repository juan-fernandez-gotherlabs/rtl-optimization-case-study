"""Deterministic finalist selection and champion decisions for SHA/VTR."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domains.rtl_sha_vtr.evaluator import (  # noqa: E402
    BASELINE_EVIDENCE_PATH,
    CERTIFICATION_SEEDS,
    MANIFEST_PATH,
    SEARCH_SEEDS,
    RtlShaVtrSpec,
    ScoreAssessment,
    SeedMetrics,
    baseline_seed_metrics,
    build_default_domain,
    score_metrics,
    search_score,
)

SHORTLIST_SIZE = 3
SELECTION_SCHEMA_VERSION = 2


def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    """Accept either an evaluator result or the agent-local wrapper payload."""
    nested = payload.get("triage_result")
    return nested if isinstance(nested, dict) else payload


def _candidate_hash(payload: dict[str, Any]) -> str:
    value = payload.get("candidate_sha256")
    if value is None and isinstance(payload.get("trace"), dict):
        value = payload["trace"].get("candidate_sha256")
    digest = str(value or "")
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest.lower()):
        raise ValueError("candidate result is missing a valid SHA-256 identity")
    return digest.lower()


def _candidate_id(payload: dict[str, Any]) -> str:
    value = str(payload.get("candidate_id") or "").strip()
    if not value:
        raise ValueError("candidate result is missing candidate_id")
    return value


def _rows(payload: dict[str, Any], expected_seeds: Sequence[int]) -> tuple[SeedMetrics, ...]:
    raw = payload.get("per_seed")
    if not isinstance(raw, list):
        raise ValueError("candidate result is missing per_seed measurements")
    try:
        rows = tuple(SeedMetrics(**item) for item in raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"candidate per_seed measurements are malformed: {exc}") from exc
    if tuple(item.seed for item in rows) != tuple(expected_seeds):
        raise ValueError(f"candidate result must contain ordered seeds {tuple(expected_seeds)}")
    return rows


def _descriptive_decision(assessment: ScoreAssessment) -> str:
    composite = (assessment.confidence or {}).get("composite", {})
    lower, upper = composite.get("ci95_two_sided", (None, None))
    if lower is None or upper is None:
        raise ValueError("search result lacks descriptive paired uncertainty")
    if upper < 1.0:
        return "provisional_better"
    if lower > 1.0:
        return "provisional_worse"
    return "provisional_tie"


def _assessment_payload(assessment: ScoreAssessment, *, decision: str | None = None) -> dict[str, Any]:
    return {
        "decision": decision or assessment.decision,
        "score": assessment.score,
        "ratio_estimates": assessment.median_ratios,
        "worst_observed_ratios": assessment.worst_ratios,
        "confidence": assessment.confidence,
    }


def _valid_search_payload(payload: dict[str, Any]) -> bool:
    return (
        payload.get("evaluation_tier") == "search"
        and payload.get("valid") is True
        and payload.get("certified") is False
        and payload.get("acceptance_decision") is None
        and payload.get("formal_status") == "pass"
    )


def select_finalists(results: Sequence[dict[str, Any]], spec: RtlShaVtrSpec | None = None) -> dict[str, Any]:
    """Select at most three unique candidates from valid five-seed results."""
    spec = spec or build_default_domain()
    baseline = baseline_seed_metrics(spec, tier="search")
    accepted: dict[str, tuple[dict[str, Any], tuple[SeedMetrics, ...], ScoreAssessment]] = {}
    rejected: list[dict[str, str]] = []
    for original in results:
        payload = _unwrap(original)
        try:
            _candidate_id(payload)
            candidate_hash = _candidate_hash(payload)
            if not _valid_search_payload(payload):
                raise ValueError("result is not a valid formal-pass non-certifying search result")
            rows = _rows(payload, SEARCH_SEEDS)
            assessment = search_score(rows, baseline)
            recorded = float(payload.get("score", payload.get("provisional_score")))
            if not math.isclose(recorded, assessment.score, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("recorded search score does not match the paired measurements")
            if candidate_hash not in accepted:
                accepted[candidate_hash] = (payload, rows, assessment)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            rejected.append(
                {
                    "candidate_id": str(payload.get("candidate_id") or "unknown"),
                    "reason": str(exc),
                }
            )
    ranked = sorted(
        accepted.items(),
        key=lambda item: (item[1][2].score, _candidate_id(item[1][0]), item[0]),
    )
    if not ranked:
        raise ValueError("no valid five-seed search results were supplied")
    leader_rows = ranked[0][1][1]
    ranking: list[dict[str, Any]] = []
    for index, (candidate_hash, (payload, rows, assessment)) in enumerate(ranked, start=1):
        relative = search_score(rows, leader_rows)
        relative_decision = "leader" if index == 1 else _descriptive_decision(relative)
        ranking.append(
            {
                "rank": index,
                "candidate_id": _candidate_id(payload),
                "candidate_sha256": candidate_hash,
                "formal_status": "pass",
                "selected_for_certification": index <= SHORTLIST_SIZE,
                "search_vs_baseline": _assessment_payload(assessment, decision="search_only"),
                "comparison_to_point_leader": _assessment_payload(relative, decision=relative_decision),
                "fragile_relative_to_leader": relative_decision == "provisional_tie",
            }
        )
    selected = [item for item in ranking if item["selected_for_certification"]]
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "contract_revision": spec.manifest["contract_revision"],
        "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "baseline_sha256": hashlib.sha256(BASELINE_EVIDENCE_PATH.read_bytes()).hexdigest(),
        "authority": "formal_pass_five_seed_shortlist",
        "certification_required": True,
        "search_seeds": list(SEARCH_SEEDS),
        "shortlist_size": SHORTLIST_SIZE,
        "unique_valid_candidates": len(ranked),
        "selected": selected,
        "ranking": ranking,
        "rejected_inputs": rejected,
        "notes": (
            "Only immutable submissions with formal_status=pass are eligible. "
            "Intervals are descriptive because the optimizer sees these seeds; "
            "selection never establishes improvement or a champion."
        ),
    }


def _valid_certification_payload(payload: dict[str, Any]) -> bool:
    return (
        payload.get("evaluation_tier") == "certification"
        and payload.get("valid") is True
        and payload.get("certified") is True
    )


def _load_incumbent(incumbent: dict[str, Any] | None, spec: RtlShaVtrSpec) -> tuple[str, str, tuple[SeedMetrics, ...]]:
    if incumbent is None:
        return (
            "baseline",
            str(spec.baseline["golden_seed_sha256"]),
            baseline_seed_metrics(spec, tier="certification"),
        )
    payload = _unwrap(incumbent)
    if not _valid_certification_payload(payload):
        raise ValueError("incumbent is not a valid 64-seed certification result")
    rows = _rows(payload, CERTIFICATION_SEEDS)
    recorded_assessment = score_metrics(rows, baseline_seed_metrics(spec, tier="certification"))
    recorded = float(payload.get("score"))
    if not math.isclose(recorded, recorded_assessment.score, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("incumbent certification score does not match the paired measurements")
    trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
    if trace.get("status", payload.get("status")) != recorded_assessment.decision:
        raise ValueError("incumbent certification decision does not match the paired measurements")
    return _candidate_id(payload), _candidate_hash(payload), rows


def select_champion(
    results: Sequence[dict[str, Any]],
    *,
    incumbent: dict[str, Any] | None = None,
    spec: RtlShaVtrSpec | None = None,
) -> dict[str, Any]:
    """Name a champion only when one candidate proves superiority on all 64 seeds."""
    spec = spec or build_default_domain()
    incumbent_id, incumbent_hash, incumbent_rows = _load_incumbent(incumbent, spec)
    public_baseline_rows = baseline_seed_metrics(spec, tier="certification")
    candidates: dict[str, tuple[dict[str, Any], tuple[SeedMetrics, ...], ScoreAssessment]] = {}
    rejected: list[dict[str, str]] = []
    for original in results:
        payload = _unwrap(original)
        try:
            _candidate_id(payload)
            candidate_hash = _candidate_hash(payload)
            if candidate_hash == incumbent_hash:
                raise ValueError("candidate duplicates the incumbent RTL")
            if candidate_hash in candidates:
                raise ValueError("duplicate candidate RTL identity")
            if not _valid_certification_payload(payload):
                raise ValueError("result is not a valid 64-seed certification")
            rows = _rows(payload, CERTIFICATION_SEEDS)
            assessment = score_metrics(rows, incumbent_rows)
            recorded_assessment = score_metrics(rows, public_baseline_rows)
            recorded = float(payload.get("score"))
            if not math.isclose(recorded, recorded_assessment.score, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError("recorded certification score does not match the paired measurements")
            trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
            recorded_decision = trace.get("status", payload.get("status"))
            if recorded_decision != recorded_assessment.decision:
                raise ValueError("recorded certification decision does not match the paired measurements")
            candidates[candidate_hash] = (payload, rows, assessment)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            rejected.append(
                {
                    "candidate_id": str(payload.get("candidate_id") or "unknown"),
                    "reason": str(exc),
                }
            )
    if not candidates:
        if incumbent is None:
            raise ValueError("no valid 64-seed certification results were supplied")
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "contract_revision": spec.manifest["contract_revision"],
            "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
            "baseline_sha256": hashlib.sha256(BASELINE_EVIDENCE_PATH.read_bytes()).hexdigest(),
            "authority": "fixed_64_seed_champion_decision",
            "decision": "incumbent_retained_all_challengers_rejected",
            "champion": {
                "candidate_id": incumbent_id,
                "candidate_sha256": incumbent_hash,
            },
            "certification_seeds": list(CERTIFICATION_SEEDS),
            "comparisons_to_incumbent": {},
            "pairwise_finalist_comparisons": {},
            "rejected_inputs": rejected,
            "notes": (
                "Every challenger failed the frozen certification contract; the valid "
                "incumbent is retained without reinterpreting invalid results."
            ),
        }
    proven = {digest: item for digest, item in candidates.items() if item[2].decision == "evidence_improvement"}
    comparisons_to_incumbent = {
        digest: {
            "candidate_id": _candidate_id(payload),
            **_assessment_payload(assessment),
        }
        for digest, (payload, _rows_value, assessment) in candidates.items()
    }
    if not proven:
        return {
            "schema_version": SELECTION_SCHEMA_VERSION,
            "contract_revision": spec.manifest["contract_revision"],
            "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
            "baseline_sha256": hashlib.sha256(BASELINE_EVIDENCE_PATH.read_bytes()).hexdigest(),
            "authority": "fixed_64_seed_champion_decision",
            "decision": "incumbent_retained_no_proven_improvement",
            "champion": {
                "candidate_id": incumbent_id,
                "candidate_sha256": incumbent_hash,
            },
            "certification_seeds": list(CERTIFICATION_SEEDS),
            "comparisons_to_incumbent": comparisons_to_incumbent,
            "pairwise_finalist_comparisons": {},
            "rejected_inputs": rejected,
        }
    dominance: dict[str, dict[str, Any]] = {}
    winners: list[str] = []
    for digest, (payload, rows, _assessment) in proven.items():
        against: dict[str, Any] = {}
        dominates_all = True
        for other_digest, (
            other_payload,
            other_rows,
            _other_assessment,
        ) in proven.items():
            if digest == other_digest:
                continue
            direct = score_metrics(rows, other_rows)
            against[other_digest] = {
                "candidate_id": _candidate_id(other_payload),
                **_assessment_payload(direct),
            }
            if direct.decision != "evidence_improvement":
                dominates_all = False
        dominance[digest] = {
            "candidate_id": _candidate_id(payload),
            "dominates_every_other_proven_finalist": dominates_all,
            "against": against,
        }
        if dominates_all:
            winners.append(digest)
    if len(winners) == 1:
        winner_hash = winners[0]
        winner_payload = proven[winner_hash][0]
        decision = "new_champion"
        champion = {
            "candidate_id": _candidate_id(winner_payload),
            "candidate_sha256": winner_hash,
        }
    else:
        decision = "no_unique_champion"
        champion = {"candidate_id": incumbent_id, "candidate_sha256": incumbent_hash}
    return {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "contract_revision": spec.manifest["contract_revision"],
        "manifest_sha256": hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest(),
        "baseline_sha256": hashlib.sha256(BASELINE_EVIDENCE_PATH.read_bytes()).hexdigest(),
        "authority": "fixed_64_seed_champion_decision",
        "decision": decision,
        "champion": champion,
        "certification_seeds": list(CERTIFICATION_SEEDS),
        "comparisons_to_incumbent": comparisons_to_incumbent,
        "pairwise_finalist_comparisons": dominance,
        "rejected_inputs": rejected,
        "notes": (
            "The incumbent changes only when exactly one finalist has evidence of improvement "
            "against the incumbent and every other proven finalist."
        ),
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    return payload


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> int:
    """Build a three-candidate shortlist or decide a certified champion."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    shortlist = subparsers.add_parser("shortlist", help="Select up to three five-seed finalists.")
    shortlist.add_argument("results", nargs="+", type=Path)
    shortlist.add_argument("--output", required=True, type=Path)
    champion = subparsers.add_parser("champion", help="Compare completed 64-seed certifications.")
    champion.add_argument("results", nargs="+", type=Path)
    champion.add_argument("--incumbent", type=Path)
    champion.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        records = [_read_json(path) for path in args.results]
        if args.command == "shortlist":
            payload = select_finalists(records)
        else:
            incumbent = _read_json(args.incumbent) if args.incumbent else None
            payload = select_champion(records, incumbent=incumbent)
        input_paths = list(args.results)
        if args.command == "champion" and args.incumbent:
            input_paths.append(args.incumbent)
        payload["input_sha256"] = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in input_paths}
        _atomic_write(args.output, payload)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"RTL_SHA_VTR_SELECTION_BLOCKED: {exc}")
        return 2
    print(f"RTL_SHA_VTR_{args.command.upper()}_PASS evidence={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
