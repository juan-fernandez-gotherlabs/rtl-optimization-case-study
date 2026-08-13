#!/usr/bin/env python3
"""Write the exact compact-package checksum manifest expected by verify.py."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def required_paths() -> set[str]:
    spec = importlib.util.spec_from_file_location("public_verify", ROOT / "verify.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load verify.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return set(module.REQUIRED_MANIFEST)


def main() -> int:
    lines = []
    for relative in sorted(required_paths()):
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"missing required public file: {relative}")
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n")
    (ROOT / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
    print(f"manifested={len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
