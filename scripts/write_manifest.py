#!/usr/bin/env python3
"""Write stable SHA-256 manifests for the public case-study artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence" / "MANIFEST.json"
SUMS = ROOT / "evidence" / "SHA256SUMS"
EXCLUDED_PARTS = {".git", "__pycache__", "output", "tmp", "reproduction-results"}
EXCLUDED_FILES = {MANIFEST.resolve(), SUMS.resolve()}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.resolve() in EXCLUDED_FILES:
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def main() -> int:
    artifacts = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in public_files()
    ]
    payload = {
        "schema_version": 1,
        "authority": "public_case_study_artifact_manifest",
        "evidence_snapshot": "2026-08-05",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "certified_original_archive": {
            "filename": "rank-2-g15-wt-balanced-xor-743e6c9ffcca-evidence.tar.gz",
            "bytes": 73794287,
            "sha256": "9983b1fef4509b9a9a592af8134be39eaa7545e5269ac7332206e86db7cce3e8",
        },
        "public_release_asset": {
            "filename": "g15-wt-balanced-xor-public-evidence.tar.gz",
            "bytes": 73705071,
            "sha256": "413aefb29bbe9bc1d22e847cd0901c24a0bfaa675af111fbd879598a76b2874f",
            "sanitization": "absolute source-worktree prefix replaced; embedded PUBLIC_SANITIZATION.json maps modified member hashes",
        },
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMS.write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in artifacts)
        + f"413aefb29bbe9bc1d22e847cd0901c24a0bfaa675af111fbd879598a76b2874f  "
        "g15-wt-balanced-xor-public-evidence.tar.gz\n",
        encoding="utf-8",
    )
    print(f"wrote {MANIFEST.relative_to(ROOT)} ({len(artifacts)} artifacts)")
    print(f"wrote {SUMS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
