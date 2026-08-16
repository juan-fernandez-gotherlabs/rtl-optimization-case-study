#!/usr/bin/env python3
"""Verify the compact public evidence for every portfolio case."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parent
CASES = {
    "sha1": ROOT / "cases/sha1",
    "int8-matvec": ROOT / "cases/int8-matvec",
}
ROOT_MANIFEST = {
    ".gitattributes",
    ".github/workflows/verify.yml",
    ".gitignore",
    "INT8-MatVec-Optimization.pdf",
    "LICENSE",
    "METHODOLOGY.md",
    "Makefile",
    "README.md",
    "SHA1-RTL-Optimization.pdf",
    "THIRD_PARTY_NOTICES.md",
    "cases/int8-matvec/SHA256SUMS",
    "cases/sha1/SHA256SUMS",
    "verify.py",
}


class PortfolioVerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PortfolioVerificationError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest() -> None:
    lines = []
    for relative in sorted(ROOT_MANIFEST):
        path = ROOT / relative
        require(path.is_file(), f"missing public portfolio file: {relative}")
        lines.append(f"{sha256(path)}  {relative}\n")
    (ROOT / "SHA256SUMS").write_text("".join(lines), encoding="utf-8")
    print(f"manifested={len(lines)}")


def verify_manifest() -> None:
    path = ROOT / "SHA256SUMS"
    require(path.is_file(), "missing portfolio SHA256SUMS")
    seen: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64})  ([^\n]+)", line)
        require(match is not None, f"malformed portfolio checksum line {line_number}")
        expected, relative = match.groups()
        pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts, f"unsafe portfolio path: {relative}")
        require(relative not in seen, f"duplicate portfolio checksum: {relative}")
        seen[relative] = expected
    require(set(seen) == ROOT_MANIFEST, "portfolio checksum coverage differs")
    for relative, expected in seen.items():
        require(sha256(ROOT / relative) == expected, f"portfolio checksum mismatch: {relative}")


def verify_report_copies() -> None:
    require(
        sha256(ROOT / "SHA1-RTL-Optimization.pdf") == sha256(ROOT / "cases/sha1/technical-report.pdf"),
        "root SHA-1 report differs from the case report",
    )
    require(
        sha256(ROOT / "INT8-MatVec-Optimization.pdf") == sha256(ROOT / "cases/int8-matvec/technical-report.pdf"),
        "root INT8 report differs from the case report",
    )


def run_case(name: str) -> None:
    case = CASES[name]
    result = subprocess.run(
        [sys.executable, "verify.py"],
        cwd=case,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    require(result.returncode == 0, f"{name} verification failed: {result.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("all", *CASES), default="all")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args(argv)
    if args.write_manifest:
        write_manifest()
        return 0
    verify_manifest()
    verify_report_copies()
    names = CASES if args.case == "all" else (args.case,)
    for name in names:
        run_case(name)
    print("Portfolio verification: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PortfolioVerificationError, OSError) as exc:
        print(f"Portfolio verification: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
