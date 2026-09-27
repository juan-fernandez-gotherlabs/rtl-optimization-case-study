#!/usr/bin/env python3
"""Write the exact public-package checksum manifest for the Quartus experiment."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def excluded_part(part: str) -> bool:
    return part == "__pycache__" or part == "output" or part.startswith("output-")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return (
        path.is_file()
        and relative.as_posix() != "SHA256SUMS"
        and not any(excluded_part(part) for part in relative.parts)
        and path.name != ".DS_Store"
    )


def main() -> int:
    paths = sorted(path for path in ROOT.rglob("*") if included(path))
    (ROOT / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(ROOT).as_posix()}\n" for path in paths
        ),
        encoding="utf-8",
    )
    print(f"manifested={len(paths)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
