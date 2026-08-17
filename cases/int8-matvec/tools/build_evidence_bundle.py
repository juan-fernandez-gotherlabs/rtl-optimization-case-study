#!/usr/bin/env python3
"""Build the deterministic, blinded INT8 full-evidence release archive."""

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
from typing import Any


BUNDLE_ROOT = "int8-matvec-vtr45-full-evidence-v1"
RAW_LEGS = (
    ("baseline-primary", "baseline", "primary"),
    ("baseline-replay", "baseline", "independent_reproduction"),
    ("accepted-primary", "campaign_best", "primary"),
    ("accepted-replay", "campaign_best", "independent_reproduction"),
)


@dataclass(frozen=True)
class Member:
    path: str
    payload: bytes
    source_sha256: str | None
    replacements: int = 0
    transformation: str | None = None


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _stable_pair(index: int) -> str:
    return f"held-out-{index:02d}"


def sanitize_payload(
    payload: bytes,
    *,
    seed: int | None = None,
    pair_id: str | None = None,
    path_replacements: tuple[tuple[bytes, bytes], ...] = (),
) -> tuple[bytes, int]:
    """Remove host paths and contextual held-out identities without touching metrics."""
    result = payload
    replacements = 0
    for before, after in path_replacements:
        count = result.count(before)
        if count:
            result = result.replace(before, after)
            replacements += count
    if seed is None:
        return result, replacements
    if pair_id is None:
        raise ValueError("pair_id is required when sanitizing a seed tree")
    text = result.decode("utf-8", errors="surrogateescape")
    substitutions = [
        (r"seed_\d+\b", pair_id),
        (r"(?i)(--seed\s+)\d+\b", rf"\1<{pair_id.upper()}>") ,
        (r"(?i)(\bseed\b\s*[:=]\s*)\d+\b", rf"\1<{pair_id.upper()}>") ,
        (r"(?i)(\bseed\b\s+)\d+\b", rf"\1<{pair_id.upper()}>") ,
    ]
    for pattern, replacement in substitutions:
        text, count = re.subn(pattern, replacement, text)
        replacements += count
    leak = re.search(r"(?i)(?:seed_\d+|--seed\s+\d+|\bseed\b\s*[:=]\s*\d+|\bseed\b\s+\d+)", text)
    if leak is not None:
        raise ValueError(f"held-out identity remains after sanitization: {pair_id}")
    return text.encode("utf-8", errors="surrogateescape"), replacements


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes, mode: int = 0o644) -> None:
    info = tarfile.TarInfo(f"{BUNDLE_ROOT}/{name}")
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(payload))


def _blinded_record(record: dict[str, Any], seeds: tuple[int, ...]) -> bytes:
    payload = dict(record)
    rows = payload.get("per_seed")
    if not isinstance(rows, list) or len(rows) != len(seeds):
        raise ValueError("raw record has the wrong per-seed rows")
    blinded: list[dict[str, Any]] = []
    for index, (row, seed) in enumerate(zip(rows, seeds, strict=True), 1):
        if not isinstance(row, dict) or row.get("seed") != seed:
            raise ValueError("raw record seed ordering differs from the frozen pool")
        public = {key: value for key, value in row.items() if key != "seed"}
        public["pair_id"] = _stable_pair(index)
        blinded.append(public)
    payload["per_seed"] = blinded
    payload["pair_identity_policy"] = "Held-out seed identities replaced by stable pair labels."
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode()


def _leg_members(
    raw_root: Path,
    leg_name: str,
    artifact: str,
    role: str,
    path_replacements: tuple[tuple[bytes, bytes], ...],
) -> list[Member]:
    leg = raw_root / leg_name
    record_path = leg / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    if record.get("status") != "qualified" or record.get("artifact") != artifact or record.get("evidence_role") != role:
        raise ValueError(f"unqualified raw evidence leg: {leg_name}")
    rows = record.get("per_seed")
    if not isinstance(rows, list) or len(rows) != 64:
        raise ValueError(f"raw evidence leg is not a fixed 64-pair run: {leg_name}")
    seeds = tuple(int(row["seed"]) for row in rows)
    result = [
        Member(
            f"records/{leg_name}.json",
            _blinded_record(record, seeds),
            None,
            transformation="Removed held-out seed identities and added stable pair labels.",
        )
    ]
    for path in sorted(item for item in leg.rglob("*") if item.is_file() and item != record_path):
        relative = path.relative_to(leg)
        if relative.parts[:1] == ("results",) and path.name.startswith("seed_") and path.suffixes[-2:] == [".tar", ".gz"]:
            continue
        before = path.read_bytes()
        after, replacements = sanitize_payload(before, path_replacements=path_replacements)
        result.append(
            Member(
                f"runs/{leg_name}/{relative.as_posix()}",
                after,
                None if replacements else digest(before),
                replacements,
            )
        )
    for index, seed in enumerate(seeds, 1):
        seed_archive = leg / "results" / f"seed_{seed}.tar.gz"
        if not seed_archive.is_file():
            raise FileNotFoundError(seed_archive)
        pair_id = _stable_pair(index)
        with tarfile.open(seed_archive, mode="r:gz") as source:
            files = sorted(
                (member for member in source.getmembers() if member.isfile()),
                key=lambda member: member.name,
            )
            if not files:
                raise ValueError(f"empty seed tree: {leg_name}/{pair_id}")
            for member in files:
                extracted = source.extractfile(member)
                if extracted is None:
                    raise ValueError(f"unreadable seed member: {member.name}")
                before = extracted.read()
                after, replacements = sanitize_payload(
                    before,
                    seed=seed,
                    pair_id=pair_id,
                    path_replacements=path_replacements,
                )
                relative = Path(member.name).relative_to(f"seed_{seed}").as_posix()
                result.append(
                    Member(
                        f"runs/{leg_name}/{pair_id}/{relative}",
                        after,
                        None if replacements else digest(before),
                        replacements,
                    )
                )
    return result


def _contract_members(
    domain: Path,
    path_replacements: tuple[tuple[bytes, bytes], ...],
) -> list[Member]:
    files = {
        "baseline/int8_matvec_4x4_baseline.sv": "contract/baseline.sv",
        "evidence/campaign_best_20260815.sv": "contract/accepted.sv",
        "ppa_wrapper.sv": "contract/ppa_wrapper.sv",
        "Dockerfile.vtr-ppa45-linux-amd64": "flow/Dockerfile.vtr-ppa45-linux-amd64",
        "activity_vectors.py": "flow/activity_vectors.py",
        "benchmark.py": "flow/benchmark.py",
        "vtr_ppa.py": "flow/vtr_ppa.py",
        "ppa_manifest.json": "flow/ppa_manifest.json",
    }
    result: list[Member] = []
    for source_name, archive_name in files.items():
        path = domain / source_name
        before = path.read_bytes()
        after, replacements = sanitize_payload(before, path_replacements=path_replacements)
        result.append(
            Member(
                archive_name,
                after,
                None if replacements else digest(before),
                replacements,
            )
        )
    private_manifest = json.loads((domain / "certification_manifest.json").read_text(encoding="utf-8"))
    certification_contract = {
        "schema_version": 1,
        "contract_revision": private_manifest["contract_revision"],
        "scope_statement": private_manifest["scope_statement"],
        "search_contract_manifest_sha256": private_manifest["search_contract_manifest_sha256"],
        "target": private_manifest["target"],
        "search_seeds": private_manifest["search_seeds"],
        "certification_seed_count": 64,
        "public_seed_policy": "Reserved identities replaced by stable held-out pair labels.",
        "runner_resources": private_manifest["runner"],
        "statistics": private_manifest["statistics"],
        "artifacts": {
            "baseline_sha256": private_manifest["artifacts"]["baseline"]["sha256"],
            "accepted_sha256": private_manifest["artifacts"]["campaign_best"]["sha256"],
        },
    }
    payload = (json.dumps(certification_contract, indent=2, sort_keys=True) + "\n").encode()
    result.append(
        Member(
            "flow/certification_contract.public.json",
            payload,
            None,
            transformation="Published only the case measurement contract, fixed count, public search sample and blinding policy; omitted private execution fields and held-out identities.",
        )
    )
    return result


def build_bundle(domain: Path, raw_root: Path, output: Path) -> dict[str, Any]:
    source_worktree = domain.parents[1]
    path_replacements = (
        (str(source_worktree).encode(), b"<SOURCE_WORKTREE>"),
        (str(raw_root).encode(), b"<RAW_EVIDENCE_ROOT>"),
    )
    members = _contract_members(domain, path_replacements)
    expected_seeds: tuple[int, ...] | None = None
    for leg_name, artifact, role in RAW_LEGS:
        record = json.loads((raw_root / leg_name / "record.json").read_text(encoding="utf-8"))
        leg_seeds = tuple(int(row["seed"]) for row in record.get("per_seed", ()))
        if expected_seeds is None:
            expected_seeds = leg_seeds
        elif leg_seeds != expected_seeds:
            raise ValueError(f"raw evidence leg uses a different held-out pool or ordering: {leg_name}")
        members.extend(_leg_members(raw_root, leg_name, artifact, role, path_replacements))
    public_case = Path(__file__).resolve().parents[1]
    for source_name, archive_name in (("LICENSE", "LICENSE"), ("certificate.json", "certificate.json")):
        payload = (public_case / source_name).read_bytes()
        members.append(Member(archive_name, payload, digest(payload)))
    names = [member.path for member in members]
    if len(names) != len(set(names)):
        raise ValueError("duplicate public archive member")
    readme = (
        "Full public raw evidence for the INT8 MatVec VTR45 certification.\n"
        "Contains baseline and accepted primary/replay trees, functional and formal logs,\n"
        "routed implementation outputs, power reports, frozen RTL, and fixed flow inputs.\n"
        "Held-out placement identities are replaced by stable pair labels.\n"
        "Metrics are academic VTR/PTM45 estimates, not physical measurements or signoff.\n"
        "Use the case verify.py with --evidence-archive to audit this asset.\n"
    ).encode()
    members.append(Member("README.txt", readme, digest(readme)))
    manifest_members: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    transformed: list[dict[str, Any]] = []
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as zipped:
            with tarfile.open(fileobj=zipped, mode="w|") as archive:
                for member in sorted(members, key=lambda item: item.path):
                    _add_bytes(archive, member.path, member.payload)
                    entry = {
                        "path": member.path,
                        "bytes": len(member.payload),
                        "sha256": digest(member.payload),
                        "provenance": "byte_exact_source" if member.source_sha256 is not None else "public_sanitized_or_blinded",
                    }
                    if member.source_sha256 is not None:
                        entry["source_sha256"] = member.source_sha256
                    manifest_members.append(entry)
                    if member.replacements:
                        modified.append(
                            {
                                "path": member.path,
                                "replacements": member.replacements,
                                "public_sha256": digest(member.payload),
                            }
                        )
                    if member.transformation is not None:
                        transformed.append(
                            {
                                "path": member.path,
                                "description": member.transformation,
                                "public_sha256": digest(member.payload),
                            }
                        )
                manifest = {
                    "schema_version": 1,
                    "bundle": BUNDLE_ROOT,
                    "purpose": "int8_matvec_full_public_raw_audit_evidence",
                    "member_count": len(manifest_members),
                    "members": manifest_members,
                    "legs": [leg[0] for leg in RAW_LEGS],
                    "pairs_per_leg": 64,
                    "seed_identity_policy": "blinded_stable_pair_labels",
                    "sanitization": {
                        "modified_member_count": len(modified),
                        "modified_members": modified,
                    },
                    "transformations": {
                        "modified_member_count": len(transformed),
                        "modified_members": transformed,
                    },
                }
                payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
                _add_bytes(archive, "MANIFEST.json", payload)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain-root", required=True, type=Path)
    parser.add_argument("--raw-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = build_bundle(
        args.domain_root.expanduser().resolve(),
        args.raw_root.expanduser().resolve(),
        args.output.expanduser().resolve(),
    )
    output = args.output.expanduser().resolve()
    print(f"bundle={output}")
    print(f"bytes={output.stat().st_size}")
    print(f"sha256={digest(output.read_bytes())}")
    print(f"manifest_members={manifest['member_count']}")
    print(f"sanitized_members={manifest['sanitization']['modified_member_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
