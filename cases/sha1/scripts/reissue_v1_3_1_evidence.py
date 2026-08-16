#!/usr/bin/env python3
"""Deterministically reissue the v1.3.0 evidence bundle for v1.3.1.

The v1.3.0 public bundle changed the flow manifest's correct ``cmd_i[2:0]``
interface to ``cmd_i[3:0]``.  The measurement RTL and all raw outputs were
already correct.  This tool accepts only the exact v1.3.0 archive, restores
that one manifest payload to its recorded source hash, removes the obsolete
correction record, and preserves every other member byte-for-byte.
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


BUNDLE_ROOT = "rtl-sha-vtr-primary-ppa-evidence-v1"
MANIFEST_PATH = f"{BUNDLE_ROOT}/MANIFEST.json"
INTERFACE_PATH = "flow/benchmarks/sha_vtr_manifest.json"
SOURCE_ARCHIVE_SHA256 = "fd345d155d5f2225d3a3a6e9f0431b9db4b0f0dcc1d1951083c53a7997821704"
SOURCE_MEMBER_COUNT = 11_362
SOURCE_INTERFACE_SHA256 = "6094a47c9923d5eb23290f24fbf7ecff0cc1977009ca070a3f5f1a435229f27e"
PUBLIC_INTERFACE_SHA256 = "e16acd70e5cd7ff0b64996598d3f404adaf71b4f3ba2676953d0d0d295cbca51"
OBSOLETE_CORRECTION = {
    "description": (
        "Correct stale cmd_i[2:0] prose to the frozen RTL interface cmd_i[3:0]; "
        "measurement RTL and raw outputs are unchanged"
    ),
    "path": INTERFACE_PATH,
    "public_sha256": PUBLIC_INTERFACE_SHA256,
    "source_sha256": SOURCE_INTERFACE_SHA256,
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def exact_keys(value: dict[str, Any], expected: set[str], where: str) -> None:
    require(set(value) == expected, f"unexpected {where} keys")


def add_bytes(
    archive: tarfile.TarFile,
    relative: str,
    payload: bytes,
    mode: int,
) -> None:
    info = tarfile.TarInfo(f"{BUNDLE_ROOT}/{relative}")
    info.size = len(payload)
    info.mode = mode
    info.mtime = 0
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    archive.addfile(info, io.BytesIO(payload))


def repaired_interface(payload: bytes) -> bytes:
    require(sha256_bytes(payload) == PUBLIC_INTERFACE_SHA256, "unexpected public flow-manifest hash")
    require(payload.count(b"cmd_i[3:0]") == 1, "public flow manifest lacks one cmd_i[3:0] record")
    require(b"cmd_i[2:0]" not in payload, "public flow manifest already contains cmd_i[2:0]")
    repaired = payload.replace(b"cmd_i[3:0]", b"cmd_i[2:0]")
    require(sha256_bytes(repaired) == SOURCE_INTERFACE_SHA256, "repaired flow manifest does not match its source hash")
    return repaired


def load_source(source: Path) -> tuple[tarfile.TarFile, dict[str, tarfile.TarInfo], dict[str, Any]]:
    require(sha256_file(source) == SOURCE_ARCHIVE_SHA256, "input is not the exact v1.3.0 evidence archive")
    archive = tarfile.open(source, "r:gz")
    members: dict[str, tarfile.TarInfo] = {}
    for member in archive.getmembers():
        path = PurePosixPath(member.name)
        require(not path.is_absolute() and ".." not in path.parts, f"unsafe member: {member.name}")
        require(member.isfile(), f"non-regular member: {member.name}")
        require(member.name not in members, f"duplicate member: {member.name}")
        members[member.name] = member
    require(MANIFEST_PATH in members, "missing source MANIFEST.json")
    stream = archive.extractfile(members[MANIFEST_PATH])
    require(stream is not None, "cannot read source MANIFEST.json")
    manifest = json.loads(stream.read())
    require(type(manifest) is dict, "source manifest must be an object")
    exact_keys(
        manifest,
        {"schema_version", "bundle", "purpose", "member_count", "members", "sanitization", "corrections"},
        "manifest",
    )
    require(manifest["schema_version"] == 2 and manifest["bundle"] == BUNDLE_ROOT, "unexpected source manifest identity")
    require(manifest["member_count"] == SOURCE_MEMBER_COUNT, "unexpected source member count")
    require(manifest["corrections"] == {"modified_member_count": 1, "modified_members": [OBSOLETE_CORRECTION]}, "unexpected source correction provenance")
    return archive, members, manifest


def reissue(source: Path, output: Path) -> None:
    require(source.resolve() != output.resolve(), "source and output paths must differ")
    source_archive, source_members, manifest = load_source(source)
    try:
        entries = manifest["members"]
        require(type(entries) is list and len(entries) == SOURCE_MEMBER_COUNT, "invalid source member list")
        expected_names = {MANIFEST_PATH}
        rewritten: list[tuple[str, bytes, int]] = []
        new_entries: list[dict[str, Any]] = []
        for index, entry in enumerate(entries):
            require(type(entry) is dict, f"member entry {index} must be an object")
            path = entry.get("path")
            require(type(path) is str, f"member entry {index} has no path")
            full_name = f"{BUNDLE_ROOT}/{path}"
            require(full_name not in expected_names, f"duplicate manifest path: {path}")
            expected_names.add(full_name)
            require(full_name in source_members, f"missing source member: {path}")
            stream = source_archive.extractfile(source_members[full_name])
            require(stream is not None, f"cannot read source member: {path}")
            payload = stream.read()
            require(len(payload) == entry.get("bytes"), f"source byte-count mismatch: {path}")
            require(sha256_bytes(payload) == entry.get("sha256"), f"source hash mismatch: {path}")
            new_entry = dict(entry)
            if path == INTERFACE_PATH:
                require(entry.get("sha256") == PUBLIC_INTERFACE_SHA256, "unexpected interface member identity")
                require(entry.get("source_sha256") == SOURCE_INTERFACE_SHA256, "unexpected interface source identity")
                payload = repaired_interface(payload)
                new_entry["bytes"] = len(payload)
                new_entry["sha256"] = SOURCE_INTERFACE_SHA256
            rewritten.append((path, payload, source_members[full_name].mode & 0o777))
            new_entries.append(new_entry)
        require(set(source_members) == expected_names, "source archive contains unmanifested members")

        new_manifest = dict(manifest)
        new_manifest["members"] = new_entries
        new_manifest["corrections"] = {"modified_member_count": 0, "modified_members": []}
        manifest_payload = (json.dumps(new_manifest, indent=2, sort_keys=True) + "\n").encode()

        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as zipped:
                with tarfile.open(fileobj=zipped, mode="w|") as target:
                    for path, payload, mode in rewritten:
                        add_bytes(target, path, payload, mode)
                    add_bytes(target, "MANIFEST.json", manifest_payload, 0o644)
    finally:
        source_archive.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path, help="exact v1.3.0 evidence archive")
    parser.add_argument("--output", required=True, type=Path, help="corrected v1.3.1 evidence archive")
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve()
    require(source.is_file(), f"missing source archive: {source}")
    reissue(source, output)
    print(f"bundle={output}")
    print(f"bytes={output.stat().st_size}")
    print(f"sha256={sha256_file(output)}")
    print(f"manifest_members={SOURCE_MEMBER_COUNT}")
    print("corrected_members=0")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, tarfile.TarError, json.JSONDecodeError) as exc:
        print(f"Reissue: FAIL: {exc}", file=__import__("sys").stderr)
        raise SystemExit(1) from exc
