#!/usr/bin/env python3
"""Deterministically produce the public-only SHA-1 evidence archive.

The source is the exact v1.3.1 evidence asset. Measurement outputs, RTL,
correctness logs and metric records are preserved. Four operational
optimization modules are omitted, and the accepted-run source pathname is
replaced by a stable public token. Every included source/public identity and
declared transformation is recorded in a new manifest.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any


SOURCE_ROOT = "rtl-sha-vtr-primary-ppa-evidence-v1"
PUBLIC_ROOT = "rtl-sha-vtr-primary-ppa-evidence-v2"
SOURCE_ARCHIVE_SHA256 = "24d37a964bce19ccba13b7e7e6410965394437c8d4d960f34e3ba80d1b565cff"
SOURCE_MEMBER_COUNT = 11_362
ACCEPTED_RECORD = "records/accepted-certification.json"
PUBLIC_RUN_TOKEN = b"<ACCEPTED_EVIDENCE_ROOT>"
OMITTED = {
    "flow/config.py",
    "flow/runner.py",
    "flow/evaluator.py",
    "flow/eval_script.py",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def digest_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def add_bytes(archive: tarfile.TarFile, relative: str, payload: bytes, mode: int) -> None:
    info = tarfile.TarInfo(f"{PUBLIC_ROOT}/{relative}")
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(payload))


def accepted_source_root(payload: bytes) -> bytes:
    record = json.loads(payload)
    roots = {
        record.get("evidence", {}).get("root"),
        record.get("trace", {}).get("evidence", {}).get("root"),
    }
    require(len(roots) == 1, "accepted record does not contain one stable evidence root")
    value = roots.pop()
    require(type(value) is str and value.startswith("<SOURCE_WORKTREE>/"), "accepted evidence root is not sanitized")
    return value.encode()


def reissue(source: Path, output: Path) -> tuple[int, int, str]:
    require(source.resolve() != output.resolve(), "source and output paths must differ")
    require(digest_file(source) == SOURCE_ARCHIVE_SHA256, "input is not the exact v1.3.1 evidence archive")
    with tarfile.open(source, "r:gz") as archive:
        members = {member.name: member for member in archive.getmembers()}
        require(len(members) == SOURCE_MEMBER_COUNT + 1, "unexpected source archive member count")
        manifest_member = members.get(f"{SOURCE_ROOT}/MANIFEST.json")
        require(manifest_member is not None, "missing source manifest")
        stream = archive.extractfile(manifest_member)
        require(stream is not None, "cannot read source manifest")
        source_manifest = json.load(stream)
        require(source_manifest.get("schema_version") == 2, "unexpected source manifest schema")
        entries = source_manifest.get("members")
        require(type(entries) is list and len(entries) == SOURCE_MEMBER_COUNT, "unexpected source member list")

        accepted_entry = next(entry for entry in entries if entry.get("path") == ACCEPTED_RECORD)
        accepted_member = members[f"{SOURCE_ROOT}/{ACCEPTED_RECORD}"]
        stream = archive.extractfile(accepted_member)
        require(stream is not None, "cannot read accepted record")
        accepted_payload = stream.read()
        require(digest(accepted_payload) == accepted_entry.get("sha256"), "accepted record hash mismatch")
        private_root = accepted_source_root(accepted_payload)

        old_descriptions: dict[str, str] = {}
        for item in source_manifest["sanitization"]["modified_members"]:
            old_descriptions[item["path"]] = "Host source-worktree paths replaced by the public source token."
        for item in source_manifest["corrections"]["modified_members"]:
            old_descriptions[item["path"]] = item["description"]

        rewritten: list[tuple[str, bytes, int]] = []
        new_entries: list[dict[str, Any]] = []
        transformations: list[dict[str, str]] = []
        omissions: list[dict[str, str]] = []
        expected = {f"{SOURCE_ROOT}/MANIFEST.json"}
        for entry in entries:
            relative = entry["path"]
            name = f"{SOURCE_ROOT}/{relative}"
            require(name in members and name not in expected, f"missing or duplicate source member: {relative}")
            expected.add(name)
            stream = archive.extractfile(members[name])
            require(stream is not None, f"cannot read source member: {relative}")
            before = stream.read()
            require(len(before) == entry["bytes"] and digest(before) == entry["sha256"], f"source member mismatch: {relative}")
            source_hash = entry.get("source_sha256", entry["sha256"])
            if relative in OMITTED:
                omissions.append({
                    "path": relative,
                    "source_sha256": source_hash,
                    "reason": "Operational optimization module; not required to verify the delivered before/after evidence.",
                })
                continue
            after = before.replace(private_root, PUBLIC_RUN_TOKEN)
            new_entry = {
                "path": relative,
                "bytes": len(after),
                "sha256": digest(after),
                "source_sha256": source_hash,
            }
            rewritten.append((relative, after, members[name].mode & 0o777))
            new_entries.append(new_entry)
            descriptions = []
            if relative in old_descriptions:
                descriptions.append(old_descriptions[relative])
            if after != before:
                descriptions.append("Accepted-run pathname replaced by a stable public evidence token.")
            if source_hash != new_entry["sha256"]:
                require(descriptions, f"undeclared source/public transformation: {relative}")
                transformations.append({
                    "path": relative,
                    "source_sha256": source_hash,
                    "public_sha256": new_entry["sha256"],
                    "description": " ".join(descriptions),
                })
        require(set(members) == expected, "source archive contains unmanifested members")
        require({item["path"] for item in omissions} == OMITTED, "not all operational modules were omitted")

    manifest = {
        "schema_version": 3,
        "bundle": PUBLIC_ROOT,
        "purpose": "primary_ppa_public_evidence_without_optimization_infrastructure",
        "member_count": len(new_entries),
        "members": new_entries,
        "transformations": {
            "modified_member_count": len(transformations),
            "modified_members": transformations,
        },
        "omissions": {
            "omitted_member_count": len(omissions),
            "omitted_members": sorted(omissions, key=lambda item: item["path"]),
        },
    }
    payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as zipped:
            with tarfile.open(fileobj=zipped, mode="w|") as target:
                for relative, member_payload, mode in rewritten:
                    add_bytes(target, relative, member_payload, mode)
                add_bytes(target, "MANIFEST.json", payload, 0o644)
    public_record = next(payload for relative, payload, _ in rewritten if relative == ACCEPTED_RECORD)
    return len(new_entries), len(transformations), digest(public_record)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="exact v1.3.1 evidence archive")
    parser.add_argument("--output", required=True, type=Path, help="public-only evidence archive")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    require(source.is_file(), f"missing source archive: {source}")
    members, transformations, record_hash = reissue(source, output)
    print(f"bundle={output}")
    print(f"bytes={output.stat().st_size}")
    print(f"sha256={digest_file(output)}")
    print(f"manifest_members={members}")
    print(f"transformed_members={transformations}")
    print(f"accepted_record_sha256={record_hash}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, tarfile.TarError, json.JSONDecodeError, StopIteration) as exc:
        print(f"Reissue: FAIL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1) from exc
