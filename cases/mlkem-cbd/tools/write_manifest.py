#!/usr/bin/env python3
"""Write the exact compact-package SHA-256 manifest."""

from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATHS = {
    "LICENSE",
    "Makefile",
    "README.md",
    "certificate.json",
    "full-evidence.json",
    "report/latex/generated/executive-ci.csv",
    "report/latex/generated/metrics.tex",
    "report/latex/generated/pair-clouds.csv",
    "report/latex/technical-report.tex",
    "rtl/baseline/cbd.v",
    "rtl/changes.patch",
    "rtl/optimized/cbd.v",
    "technical-report.pdf",
    "tests/test_verify.py",
    "tools/build_certificate.py",
    "tools/build_evidence_bundle.py",
    "tools/generate_report_data.py",
    "tools/normalize_pdf_id.py",
    "tools/write_manifest.py",
    "verify.py",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    missing = sorted(relative for relative in PATHS if not (ROOT / relative).is_file())
    if missing:
        raise SystemExit(f"missing manifest files: {missing}")
    payload = "".join(
        f"{sha256(ROOT / relative)}  {relative}\n" for relative in sorted(PATHS)
    )
    (ROOT / "SHA256SUMS").write_text(payload, encoding="utf-8")
    print(f"manifested={len(PATHS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
