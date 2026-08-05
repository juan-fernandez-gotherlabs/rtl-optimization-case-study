#!/usr/bin/env python3
"""Create a deterministic, public evidence archive with host paths redacted."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path, PurePosixPath


REPLACEMENT = b"<SOURCE_WORKTREE>"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(info: tarfile.TarInfo) -> tarfile.TarInfo:
    clone = tarfile.TarInfo(info.name)
    clone.mode = info.mode
    clone.type = info.type
    clone.linkname = info.linkname
    clone.mtime = 0
    clone.uid = 0
    clone.gid = 0
    clone.uname = ""
    clone.gname = ""
    clone.pax_headers = {}
    return clone


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--redact-prefix", required=True)
    args = parser.parse_args()
    needle = args.redact_prefix.encode("utf-8")
    if not needle.startswith(b"/") or len(needle) < 20:
        raise ValueError("redaction prefix must be a specific absolute path")

    original_sha = hashlib.sha256(args.input.read_bytes()).hexdigest()
    modified: list[dict[str, object]] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(args.input, "r:gz") as source:
        members = source.getmembers()
        if not members:
            raise ValueError("source archive is empty")
        root = PurePosixPath(members[0].name).parts[0]
        if not root:
            raise ValueError("source archive has no stable root")
        with args.output.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=6) as zipped:
                with tarfile.open(fileobj=zipped, mode="w|") as target:
                    for member in members:
                        parts = PurePosixPath(member.name)
                        if parts.is_absolute() or ".." in parts.parts:
                            raise ValueError(f"unsafe archive member: {member.name}")
                        info = normalized(member)
                        if member.isfile():
                            stream = source.extractfile(member)
                            if stream is None:
                                raise ValueError(f"cannot read archive member: {member.name}")
                            before = stream.read()
                            after = before.replace(needle, REPLACEMENT)
                            info.size = len(after)
                            if after != before:
                                modified.append(
                                    {
                                        "path": member.name,
                                        "replacements": before.count(needle),
                                        "original_sha256": digest(before),
                                        "public_sha256": digest(after),
                                    }
                                )
                            target.addfile(info, io.BytesIO(after))
                        else:
                            info.size = 0
                            target.addfile(info)

                    record = {
                        "schema_version": 1,
                        "purpose": "public_release_path_sanitization",
                        "certified_original_archive_sha256": original_sha,
                        "replacement": "<SOURCE_WORKTREE>",
                        "modified_member_count": len(modified),
                        "modified_members": modified,
                        "note": (
                            "Only the absolute host source-worktree prefix was replaced. "
                            "Original and public member hashes preserve an auditable mapping."
                        ),
                    }
                    payload = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode("utf-8")
                    record_info = tarfile.TarInfo(f"{root}/PUBLIC_SANITIZATION.json")
                    record_info.size = len(payload)
                    record_info.mode = 0o644
                    record_info.mtime = 0
                    target.addfile(record_info, io.BytesIO(payload))

    public_sha = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"modified_members={len(modified)}")
    print(f"certified_original_sha256={original_sha}")
    print(f"public_archive_sha256={public_sha}")
    print(f"public_archive_bytes={args.output.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
