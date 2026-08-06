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


def write_patch(baseline: Path, accepted: Path, output: Path) -> None:
    before = baseline.read_text(encoding="utf-8").splitlines(keepends=True)
    after = accepted.read_text(encoding="utf-8").splitlines(keepends=True)
    output.write_text(
        "".join(
            difflib.unified_diff(
                before,
                after,
                fromfile="rtl/baseline/sha.v",
                tofile="rtl/accepted/sha.v",
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


def compact_accepted(path: Path, archive_manifest: Path) -> dict[str, Any]:
    source = read_json(path)
    archive = read_json(archive_manifest)
    evidence = source["evidence"]
    hashes = source["evidence_hashes"]
    return {
        "schema_version": 1,
        "authority": "fixed_64_seed_certification",
        "source_sha256": sha256(path),
        "candidate_id": "accepted-rtl",
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
            "filename": "accepted-rtl-certification-evidence.tar.gz",
            "sha256": archive["sha256"],
            "elapsed_seconds": archive["elapsed_seconds"],
            "formal_status": archive["formal_status"],
        },
        "notes": source["notes"],
    }


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


def netlist_summary(baseline_seed_dir: Path, accepted_archive: Path) -> dict[str, Any]:
    baseline_files = {
        "vpr": (baseline_seed_dir / "vpr_stdout.log").read_bytes(),
        "crit": (baseline_seed_dir / "vpr.crit_path.out").read_bytes(),
        "blif": (baseline_seed_dir / "sha.abc.blif").read_bytes(),
    }
    with tarfile.open(accepted_archive, "r:gz") as tf:
        accepted_files = {
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
        "accepted": record(accepted_files),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--accepted-result", type=Path, required=True)
    parser.add_argument("--accepted-rtl", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--archive-manifest", type=Path, required=True)
    parser.add_argument("--baseline-seed20", type=Path, required=True)
    args = parser.parse_args()
    root = args.repo.resolve()

    baseline = compact_baseline(args.baseline)
    accepted = compact_accepted(args.accepted_result, args.archive_manifest)
    accepted_rtl_sha256 = sha256(args.accepted_rtl)
    if accepted_rtl_sha256 != accepted["candidate_sha256"]:
        raise ValueError(
            "accepted RTL SHA-256 does not match the accepted certification: "
            f"{accepted_rtl_sha256} != {accepted['candidate_sha256']}"
        )
    netlist = netlist_summary(args.baseline_seed20, args.archive)

    write_json(root / "results/baseline-certification.json", baseline)
    write_json(root / "results/accepted-certification.json", accepted)
    write_json(root / "results/netlist-seed20-summary.json", netlist)
    write_json(
        root / "evidence/formal-proof.json",
        {
            "schema_version": 1,
            "candidate_id": accepted["candidate_id"],
            "candidate_sha256": accepted["candidate_sha256"],
            "formal_status": "pass",
            "eqy_pass_marker_sha256": accepted["correctness"]["eqy_pass_marker_sha256"],
            "formal_driver_log_sha256": accepted["correctness"]["formal_driver_log_sha256"],
            "raw_evidence_archive": accepted["raw_evidence_archive"],
        },
    )
    write_patch(root / "rtl/baseline/sha.v", root / "rtl/accepted/sha.v", root / "rtl/baseline-to-accepted.patch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
