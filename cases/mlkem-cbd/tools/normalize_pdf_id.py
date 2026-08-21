#!/usr/bin/env python3
"""Replace the checkout-dependent PDF trailer ID with a fixed content identity."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


TRAILER_ID = b"4c9ecf6d88e5c4419b177f252dbb714a"
ID_PATTERN = re.compile(rb"/ID\[<[0-9A-Fa-f]{32}><[0-9A-Fa-f]{32}>\]")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()

    payload = args.pdf.read_bytes()
    replacement = b"/ID[<" + TRAILER_ID + b"><" + TRAILER_ID + b">]"
    normalized, count = ID_PATTERN.subn(replacement, payload)
    if count != 1:
        raise SystemExit(f"expected exactly one PDF trailer ID, found {count}")
    if len(normalized) != len(payload):
        raise SystemExit("normalization changed PDF length")
    args.pdf.write_bytes(normalized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
