#!/usr/bin/env python3
"""Create the public, path-sanitized evidence package from certified sources."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import tarfile
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_patch(baseline: Path, champion: Path, output: Path) -> None:
    before = baseline.read_text(encoding="utf-8").splitlines(keepends=True)
    after = champion.read_text(encoding="utf-8").splitlines(keepends=True)
    output.write_text(
        "".join(
            difflib.unified_diff(
                before,
                after,
                fromfile="rtl/baseline/sha.v",
                tofile="rtl/champion/sha.v",
            )
        ),
        encoding="utf-8",
    )


def compact_baseline(path: Path) -> dict[str, Any]:
    source = read_json(path)
    return {
        "schema_version": 1,
        "authority": "certified_public_baseline",
        "source_sha256": sha256(path),
        "status": source["status"],
        "valid": source["valid"],
        "score": source["score"],
        "contract_revision": source["contract_revision"],
        "golden_seed_sha256": source["golden_seed_sha256"],
        "manifest_sha256": source["manifest_sha256"],
        "measurement_environment": source["measurement_environment"],
        "seed_sets": source["seed_sets"],
        "aggregate": source["certification_aggregate"],
        "per_seed": source["certification_per_seed"],
        "functional": source["functional"],
        "nist_short_long": source["nist_short_long"],
        "mutation": source["mutation"],
        "activity": source["activity"],
        "reproduction": source["statistical_baseline"]["reproduction"],
        "limitations": source["limitations"],
    }


def compact_champion(path: Path, archive_manifest: Path) -> dict[str, Any]:
    source = read_json(path)
    archive = read_json(archive_manifest)
    evidence = source["evidence"]
    hashes = source["evidence_hashes"]
    return {
        "schema_version": 1,
        "authority": "fixed_64_seed_certification",
        "source_sha256": sha256(path),
        "candidate_id": source["candidate_id"],
        "candidate_sha256": source["trace"]["candidate_sha256"],
        "valid": source["valid"],
        "certified": source["certified"],
        "score": source["score"],
        "accepted_improvement": source["accepted_improvement"],
        "acceptance_decision": source["acceptance_decision"],
        "ratios": source["ratios"],
        "statistical_confidence": source["statistical_confidence"],
        "metrics": source["metrics"],
        "per_seed": source["per_seed"],
        "correctness": {
            "functional_pass": source["metrics"]["functional_pass"],
            "formal_pass": source["metrics"]["formal_pass"],
            "busy_cycles_per_block": source["metrics"]["busy_cycles_per_block"],
            "nist_short_long_cases": evidence["nist_short_long"][
                "short_long_cases"
            ],
            "nist_corpus_sha256": evidence["nist_short_long"]["corpus_sha256"],
            "eqy_pass_marker_sha256": hashes["sha1_cycle/PASS"],
            "formal_driver_log_sha256": hashes["formal_driver.log"],
            "cycle_run_log_sha256": hashes["cycle_run.log"],
            "nist_run_log_sha256": hashes["nist_run.log"],
        },
        "activity": evidence["activity"],
        "certification_seeds": evidence["seeds"],
        "raw_evidence_archive": {
            "filename": Path(archive["archive"]).name,
            "sha256": archive["sha256"],
            "elapsed_seconds": archive["elapsed_seconds"],
            "formal_status": archive["formal_status"],
        },
        "notes": source["notes"],
    }


def compact_campaign(campaign_dir: Path, decision_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state = read_json(campaign_dir / "campaign-state.json")
    decision = read_json(decision_path)
    selected_by_generation = {
        int(row["generation"]): row.get("selected", {}).get("candidate_sha256")
        for row in state["generations"]
    }
    submissions: list[dict[str, Any]] = []
    for path in sorted(campaign_dir.glob("generation-*/submissions/*.json")):
        payload = read_json(path)
        report = payload.get("report", {})
        triage = payload.get("triage_result", {})
        generation_match = re.search(r"generation-(\d+)", str(path))
        if generation_match is None:
            raise ValueError(f"cannot parse generation from {path}")
        generation = int(generation_match.group(1))
        candidate_sha = report.get("candidate_sha256") or triage.get("candidate_sha256")
        submissions.append(
            {
                "generation": generation,
                "candidate_id": report.get("candidate_id") or triage.get("candidate_id"),
                "candidate_sha256": candidate_sha,
                "status": report.get("status", triage.get("status")),
                "formal_status": report.get("formal_status", triage.get("formal_status", "not_run")),
                "triage_pass": bool(report.get("triage_pass", triage.get("triage_pass", False))),
                "provisional_score": report.get("provisional_score", triage.get("provisional_score")),
                "selected": candidate_sha == selected_by_generation.get(generation),
            }
        )
    formal_counts: dict[str, int] = {}
    for row in submissions:
        status = str(row["formal_status"])
        formal_counts[status] = formal_counts.get(status, 0) + 1
    unique_formal_pass = len(
        {
            row["candidate_sha256"]
            for row in submissions
            if row["formal_status"] == "pass" and row["candidate_sha256"]
        }
    )
    history = {
        "schema_version": 1,
        "authority": "five_seed_search_history_non_certifying",
        "generations": state["completed_generations"],
        "submissions_total": len(submissions),
        "formal_status_counts": formal_counts,
        "unique_formal_pass_candidates": unique_formal_pass,
        "submissions": submissions,
    }
    comparisons = {}
    for candidate_sha, comparison in decision["comparisons_to_incumbent"].items():
        comparisons[candidate_sha] = {
            "candidate_id": comparison["candidate_id"],
            "decision": comparison["decision"],
            "score": comparison["score"],
            "ratio_estimates": comparison["ratio_estimates"],
            "confidence": comparison["confidence"],
        }
    campaign = {
        "schema_version": 1,
        "authority": decision["authority"],
        "source_sha256": sha256(decision_path),
        "contract_revision": decision["contract_revision"],
        "decision": decision["decision"],
        "baseline_sha256": decision["baseline_sha256"],
        "certification_seeds": decision["certification_seeds"],
        "champion": decision["champion"],
        "comparisons_to_previous_incumbent": comparisons,
        "notes": decision["notes"],
    }
    return history, campaign


def extract_member(tf: tarfile.TarFile, suffix: str) -> bytes:
    members = [item for item in tf.getmembers() if item.name.endswith(suffix)]
    if len(members) != 1:
        raise ValueError(f"expected one archive member ending {suffix!r}, got {len(members)}")
    stream = tf.extractfile(members[0])
    if stream is None:
        raise ValueError(f"archive member is not a file: {members[0].name}")
    return stream.read()


def parse_vpr_summary(vpr_text: str, crit_text: str, blif_text: str) -> dict[str, Any]:
    def one(pattern: str, text: str, cast: type[int] | type[float]) -> int | float:
        matches = re.findall(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if not matches:
            raise ValueError(f"missing VPR field: {pattern}")
        return cast(matches[0])

    clb_rows = re.findall(r"^\s*(\d+)\s+blocks of type: clb\s*$", vpr_text, re.MULTILINE)
    if not clb_rows:
        raise ValueError("missing CLB count")
    return {
        "abc_names_nodes": len(re.findall(r"^\.names ", blif_text, re.MULTILINE)),
        "clb_blocks": int(clb_rows[0]),
        "timing_graph_levels": one(r"Timing Graph Levels:\s*(\d+)", crit_text, int),
        "critical_path_delay_ns": one(
            r"Final critical path delay \(least slack\):\s*([0-9.]+) ns", vpr_text, float
        ),
        "channel_width": one(
            r"Circuit successfully routed with a channel width factor of\s*(\d+)",
            vpr_text,
            int,
        ),
    }


def netlist_summary(baseline_seed_dir: Path, champion_archive: Path) -> dict[str, Any]:
    baseline_files = {
        "vpr": (baseline_seed_dir / "vpr_stdout.log").read_bytes(),
        "crit": (baseline_seed_dir / "vpr.crit_path.out").read_bytes(),
        "blif": (baseline_seed_dir / "sha.abc.blif").read_bytes(),
    }
    with tarfile.open(champion_archive, "r:gz") as tf:
        champion_files = {
            "vpr": extract_member(tf, "/seed_20/vpr_stdout.log"),
            "crit": extract_member(tf, "/seed_20/vpr.crit_path.out"),
            "blif": extract_member(tf, "/seed_20/sha.abc.blif"),
        }

    def record(files: dict[str, bytes]) -> dict[str, Any]:
        summary = parse_vpr_summary(
            files["vpr"].decode(errors="replace"),
            files["crit"].decode(errors="replace"),
            files["blif"].decode(errors="replace"),
        )
        summary["source_hashes"] = {
            name: hashlib.sha256(data).hexdigest() for name, data in files.items()
        }
        return summary

    return {
        "schema_version": 1,
        "authority": "derived_from_seed_20_post_synthesis_and_post_route_artifacts",
        "seed": 20,
        "baseline": record(baseline_files),
        "champion": record(champion_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--champion-result", type=Path, required=True)
    parser.add_argument("--champion-rtl", type=Path, required=True)
    parser.add_argument("--campaign-dir", type=Path, required=True)
    parser.add_argument("--campaign-decision", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-manifest", type=Path, required=True)
    parser.add_argument("--baseline-seed20", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()

    baseline = compact_baseline(args.baseline)
    champion = compact_champion(args.champion_result, args.archive_manifest)
    history, campaign = compact_campaign(args.campaign_dir, args.campaign_decision)
    netlist = netlist_summary(args.baseline_seed20, args.archive)

    write_json(root / "results/baseline-certification.json", baseline)
    write_json(root / "results/champion-certification.json", champion)
    write_json(root / "results/search-history.json", history)
    write_json(root / "results/campaign-decision.json", campaign)
    write_json(root / "results/netlist-seed20-summary.json", netlist)
    write_json(
        root / "evidence/formal-proof.json",
        {
            "schema_version": 1,
            "candidate_id": champion["candidate_id"],
            "candidate_sha256": champion["candidate_sha256"],
            "formal_status": "pass",
            "eqy_pass_marker_sha256": champion["correctness"]["eqy_pass_marker_sha256"],
            "formal_driver_log_sha256": champion["correctness"]["formal_driver_log_sha256"],
            "raw_evidence_archive": champion["raw_evidence_archive"],
        },
    )
    write_patch(root / "rtl/baseline/sha.v", root / "rtl/champion/sha.v", root / "rtl/baseline-to-champion.patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
