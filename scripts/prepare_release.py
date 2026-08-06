#!/usr/bin/env python3
"""Assemble the client-facing release assets after validating their identity."""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "output" / "release-v1.1.0"
PUBLIC_EVIDENCE_NAME = "accepted-rtl-certification-evidence.tar.gz"
PUBLIC_EVIDENCE_BYTES = 73_705_071
PUBLIC_EVIDENCE_SHA256 = "413aefb29bbe9bc1d22e847cd0901c24a0bfaa675af111fbd879598a76b2874f"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_evidence(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"missing evidence archive: {path}")
    if path.stat().st_size != PUBLIC_EVIDENCE_BYTES:
        raise SystemExit(
            f"evidence size mismatch: expected {PUBLIC_EVIDENCE_BYTES}, got {path.stat().st_size}"
        )
    actual = sha256(path)
    if actual != PUBLIC_EVIDENCE_SHA256:
        raise SystemExit(
            f"evidence SHA-256 mismatch: expected {PUBLIC_EVIDENCE_SHA256}, got {actual}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-archive", required=True, type=Path)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT, type=Path)
    args = parser.parse_args()

    evidence = args.evidence_archive.expanduser().resolve()
    validate_evidence(evidence)

    sources = {
        "executive-summary.pdf": ROOT / "report" / "executive-summary.pdf",
        "technical-report.pdf": ROOT / "report" / "technical-report.pdf",
        PUBLIC_EVIDENCE_NAME: evidence,
    }
    missing = [str(path) for path in sources.values() if not path.is_file()]
    if missing:
        raise SystemExit("missing release source(s): " + ", ".join(missing))

    output = args.output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name, source in sources.items():
        shutil.copyfile(source, output / name)

    sums = "".join(f"{sha256(output / name)}  {name}\n" for name in sorted(sources))
    (output / "SHA256SUMS").write_text(sums, encoding="utf-8")

    print(f"prepared {output}")
    for name in sorted(sources):
        print(f"{sha256(output / name)}  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
