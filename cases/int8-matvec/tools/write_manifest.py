#!/usr/bin/env python3
"""Write the exact INT8 compact-package checksum manifest."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    spec = importlib.util.spec_from_file_location("int8_public_verify", ROOT / "verify.py")
    if spec is None or spec.loader is None:
        raise SystemExit("cannot import INT8 verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lines = []
    for relative in sorted(module.REQUIRED_MANIFEST):
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"missing public INT8 file: {relative}")
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}\n")
    (ROOT / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
    print(f"manifested={len(lines)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
