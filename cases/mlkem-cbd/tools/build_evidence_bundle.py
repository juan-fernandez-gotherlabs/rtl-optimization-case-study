#!/usr/bin/env python3
"""Build a deterministic public raw-evidence archive for ML-KEM CBD."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import tarfile
from dataclasses import dataclass
from pathlib import Path


BUNDLE_ROOT = "mlkem-cbd-vtr45-full-evidence-v1"
SEEDS = tuple(range(101, 165))
RUN_FILES = ("vpr.crit_path.out", "active.power", "flow.time", "flow_driver.log")
CORRECTNESS_FILES = (
    "verilator_lint.log",
    "interface.log",
    "interface.json",
    "cycle_compile.log",
    "cycle_run.log",
    "formal.log",
)


@dataclass(frozen=True)
class Member:
    path: str
    payload: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


def public_payload(payload: bytes, path: str) -> bytes:
    forbidden = (
        rb"/Users/[^/\s]+/",
        rb"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth\.json|credential)",
    )
    for pattern in forbidden:
        if re.search(pattern, payload):
            raise ValueError(f"private execution marker in {path}")
    return payload


def add_file(members: list[Member], path: str, source: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    payload = source.read_bytes()
    members.append(Member(path, public_payload(payload, path)))


def add_sanitized_record(members: list[Member], path: str, source: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    if "evidence_root" in data:
        data["evidence_root"] = "<SANITIZED_SOURCE_EVIDENCE_ROOT>"
    payload = json.dumps(data, indent=2, sort_keys=True).encode() + b"\n"
    members.append(Member(path, public_payload(payload, path)))


def write_member(archive: tarfile.TarFile, member: Member) -> None:
    info = tarfile.TarInfo(f"{BUNDLE_ROOT}/{member.path}")
    info.size = len(member.payload)
    info.mode = 0o644
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(member.payload))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-domain", required=True, type=Path)
    parser.add_argument("--case-root", required=True, type=Path)
    parser.add_argument("--baseline-raw", required=True, type=Path)
    parser.add_argument("--optimized-raw", required=True, type=Path)
    parser.add_argument("--architecture-file", required=True, type=Path)
    parser.add_argument("--technology-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--metadata-output", required=True, type=Path)
    parser.add_argument("--release-tag", default="v2.2.0")
    args = parser.parse_args()

    domain = args.source_domain.resolve()
    case = args.case_root.resolve()
    baseline_raw = args.baseline_raw.resolve()
    optimized_raw = args.optimized_raw.resolve()
    members: list[Member] = []
    members.append(
        Member(
            "README.txt",
            (
                "ML-KEM CBD VTR/PTM45 public raw evidence\n"
                "Contains the exact public contract, correctness logs, compact records, and\n"
                "64 baseline/optimized VTR timing and ACE power pairs. Use the case verify.py\n"
                "with --evidence-archive to audit hashes and re-extract every primary metric.\n"
            ).encode(),
        )
    )
    contract = {
        "LICENSE": case / "LICENSE",
        "cbd_baseline.v": case / "rtl/baseline/cbd.v",
        "cbd_optimized.v": case / "rtl/optimized/cbd.v",
        "changes.patch": case / "rtl/changes.patch",
        "cbd_equivalence_tb.sv": domain / "benchmarks/cbd_equivalence_tb.sv",
        "cbd_cycle.eqy": domain / "benchmarks/cbd_cycle.eqy",
        "prepare_ace_probabilistic.py": domain
        / "benchmarks/prepare_ace_probabilistic.py",
        "publication_protocol.json": domain / "benchmarks/publication_protocol.json",
        "evaluator.py": domain / "evaluator.py",
    }
    for name, source in contract.items():
        add_file(members, f"contract/{name}", source)
    add_file(
        members,
        "toolchain/k6_N10_I40_Fi6_L4_frac0_ff1_45nm.xml",
        args.architecture_file.resolve(),
    )
    add_file(members, "toolchain/45nm.xml", args.technology_file.resolve())
    add_file(members, "certificate.json", case / "certificate.json")
    add_file(
        members,
        "records/baseline-publication.json",
        domain / "benchmarks/baseline_publication.json",
    )
    add_sanitized_record(
        members,
        "records/optimized-publication.json",
        domain / "evidence/publication_result.json",
    )
    add_file(
        members, "records/initial-12-pair-result.json", domain / "evidence/result.json"
    )

    for design, raw in (("baseline", baseline_raw), ("optimized", optimized_raw)):
        for name in CORRECTNESS_FILES:
            add_file(members, f"correctness/{design}/{name}", raw / name)
        for seed in SEEDS:
            seed_dir = raw / f"seed_{seed}"
            for name in RUN_FILES:
                add_file(members, f"runs/{design}/seed_{seed}/{name}", seed_dir / name)

    paths = [member.path for member in members]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate public archive path")
    manifest = {
        "schema_version": 1,
        "bundle": BUNDLE_ROOT,
        "purpose": "public raw-provenance verification for the prospectively frozen 64-pair ML-KEM CBD result",
        "pair_count": len(SEEDS),
        "seeds": list(SEEDS),
        "transformations": [
            "records/optimized-publication.json replaces the local evidence_root value with <SANITIZED_SOURCE_EVIDENCE_ROOT>; metrics and all other JSON values are preserved from the source record"
        ],
        "member_count_excluding_manifest": len(members),
        "members": [
            {"path": member.path, "bytes": len(member.payload), "sha256": member.sha256}
            for member in sorted(members, key=lambda item: item.path)
        ],
    }
    manifest_member = Member(
        "MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n"
    )
    ordered = [manifest_member, *sorted(members, key=lambda item: item.path)]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as raw_output:
        with gzip.GzipFile(
            fileobj=raw_output, mode="wb", filename="", mtime=0, compresslevel=9
        ) as zipped:
            with tarfile.open(fileobj=zipped, mode="w|") as archive:
                for member in ordered:
                    write_member(archive, member)

    archive_hash = hashlib.sha256(args.output.read_bytes()).hexdigest()
    metadata = {
        "schema_version": 1,
        "asset_name": args.output.name,
        "archive_sha256": archive_hash,
        "archive_bytes": args.output.stat().st_size,
        "bundle_root": BUNDLE_ROOT,
        "member_count": len(ordered),
        "release_tag": args.release_tag,
        "download_url": (
            "https://github.com/juan-fernandez-gotherlabs/rtl-optimization-case-study/releases/download/"
            f"{args.release_tag}/{args.output.name}"
        ),
    }
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"archive={args.output}")
    print(f"sha256={archive_hash}")
    print(f"bytes={args.output.stat().st_size}")
    print(f"members={len(ordered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
