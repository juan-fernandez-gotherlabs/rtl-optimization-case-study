#!/usr/bin/env python3
"""Build the deterministic public evidence bundle for the primary-PPA result.

The bundle is deliberately separate from normal Git history: it contains the
complete baseline and accepted 64-seed EDA output trees.  Every archived file
is content-addressed in an internal manifest.  Host source-worktree paths are
replaced with a stable token and recorded in the manifest.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = "rtl-sha-vtr-primary-ppa-evidence-v1"
REPLACEMENT = b"<SOURCE_WORKTREE>"


@dataclass(frozen=True)
class Source:
    source: Path
    archive_path: str


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def add_bytes(archive: tarfile.TarFile, name: str, payload: bytes, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(f"{BUNDLE_ROOT}/{name}")
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(payload))


def sources(domain: Path) -> list[Source]:
    accepted_run = domain / (
        "evidence/ppa45/runs/codex_campaign_sol_high_dev32_20gen_20260809/"
        "g05-f1-mux-direct-read-cert64-evidence-attempt2"
    )
    accepted_record = accepted_run.parent / "g05-f1-mux-direct-read-cert64-attempt2.json"
    baseline_run = domain / "evidence/ppa45/runs/certification_baseline_v2_20260802"

    required_files = {
        accepted_record: "records/accepted-certification.json",
        domain / "evidence/ppa45/baseline.json": "records/baseline.json",
        ROOT / "rtl/baseline/sha.v": "rtl/baseline/sha.v",
        ROOT / "rtl/accepted/sha.v": "rtl/accepted/sha.v",
        ROOT / "rtl/baseline-to-accepted.patch": "rtl/baseline-to-accepted.patch",
    }
    result = [Source(path, name) for path, name in required_files.items()]

    trees = {
        baseline_run: "runs/baseline",
        accepted_run: "runs/accepted",
        domain / "benchmarks/nist_shavs": "contract/nist_shavs",
    }
    for base, prefix in trees.items():
        if not base.is_dir():
            raise FileNotFoundError(base)
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            result.append(Source(path, f"{prefix}/{path.relative_to(base).as_posix()}"))

    flow_files = [
        "Dockerfile.vtr-ppa45-linux-amd64",
        "requirements-ppa45-linux-amd64.lock",
        "config.py",
        "runner.py",
        "evaluator.py",
        "eval_script.py",
        "certify_baseline.py",
        "activity_vectors.py",
        "generate_nist_corpus.py",
        "compare_reproduction.py",
        "sbom.py",
        "benchmarks/sha1_cycle.eqy",
        "benchmarks/sha1_nist_tb.sv",
        "benchmarks/sha1_equivalence_tb.v",
        "benchmarks/sha1_abc_tb.v",
        "benchmarks/sha_vtr_manifest.json",
        "benchmarks/eqy_yosys_compat.patch",
        "benchmarks/ace_frozen_vectors.patch",
        "benchmarks/sha1_conformance.patch",
    ]
    for relative in flow_files:
        path = domain / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        result.append(Source(path, f"flow/{relative}"))

    archive_names = [item.archive_path for item in result]
    if len(archive_names) != len(set(archive_names)):
        raise ValueError("duplicate archive path")
    return sorted(result, key=lambda item: item.archive_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    domain = args.domain_root.expanduser().resolve()
    if not (domain / "evaluator.py").is_file():
        raise SystemExit(f"not an RTL SHA VTR domain root: {domain}")
    args.output.parent.mkdir(parents=True, exist_ok=True)

    needles = [str(domain).encode(), str(domain.parent.parent).encode()]
    manifest: list[dict[str, object]] = []
    modified_members: list[dict[str, object]] = []

    with args.output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as zipped:
            with tarfile.open(fileobj=zipped, mode="w|") as archive:
                readme = (
                    "Primary-PPA certification evidence for corrected baseline versus accepted RTL.\n"
                    "Contains complete 64-seed baseline and accepted VTR/ACE output trees,\n"
                    "formal/NIST records, exact RTL, flow inputs and content manifest.\n"
                    "Certification seeds are the frozen set disjoint from search seeds 1,7,19,43,97.\n"
                    "Host source-worktree paths are replaced by <SOURCE_WORKTREE>.\n"
                ).encode()
                add_bytes(archive, "README.txt", readme)
                manifest.append(
                    {"path": "README.txt", "bytes": len(readme), "sha256": digest(readme)}
                )

                for item in sources(domain):
                    before = item.source.read_bytes()
                    after = before
                    replacements = 0
                    for needle in needles:
                        count = after.count(needle)
                        if count:
                            after = after.replace(needle, REPLACEMENT)
                            replacements += count
                    add_bytes(archive, item.archive_path, after, item.source.stat().st_mode & 0o777)
                    entry = {
                        "path": item.archive_path,
                        "bytes": len(after),
                        "sha256": digest(after),
                        "source_sha256": digest(before),
                    }
                    manifest.append(entry)
                    if replacements:
                        modified_members.append(
                            {
                                "path": item.archive_path,
                                "replacements": replacements,
                                "source_sha256": digest(before),
                                "public_sha256": digest(after),
                            }
                        )
                record = {
                    "schema_version": 2,
                    "bundle": BUNDLE_ROOT,
                    "purpose": "primary_ppa_full_public_audit_evidence",
                    "member_count": len(manifest),
                    "members": manifest,
                    "sanitization": {
                        "replacement": REPLACEMENT.decode(),
                        "modified_member_count": len(modified_members),
                        "modified_members": modified_members,
                    },
                    "corrections": {
                        "modified_member_count": 0,
                        "modified_members": [],
                    },
                }
                payload = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()
                add_bytes(archive, "MANIFEST.json", payload)

    print(f"bundle={args.output}")
    print(f"bytes={args.output.stat().st_size}")
    print(f"sha256={hashlib.sha256(args.output.read_bytes()).hexdigest()}")
    print(f"manifest_members={len(manifest)}")
    print(f"sanitized_members={len(modified_members)}")
    print("corrected_members=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
