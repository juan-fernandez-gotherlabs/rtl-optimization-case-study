#!/usr/bin/env python3
"""Copy the minimal auditable Quartus evidence and write its manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS = (
    ("baseline", "dsp_auto"),
    ("optimized", "dsp_auto"),
    ("baseline", "lut_only"),
    ("optimized", "lut_only"),
)
ROOT_FILES = ("run_contract.json", "summary.csv", "summary.json")
RUN_FILES = ("quartus_compile.log", "quartus_power.log", "summary.json")
PROJECT_SUFFIXES = (".qpf", ".qsf", ".sdc")
REPORT_SUFFIXES = (
    ".flow.rpt",
    ".map.rpt",
    ".map.summary",
    ".fit.rpt",
    ".fit.summary",
    ".sta.rpt",
    ".sta.summary",
    ".pow.rpt",
    ".pow.summary",
)


class EvidenceError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise EvidenceError(f"missing required evidence input: {path}")
    return path


def copy_file(source: Path, destination: Path) -> None:
    require_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root", type=Path)
    parser.add_argument("evidence_root", type=Path)
    parser.add_argument(
        "--result-snapshot",
        type=Path,
        default=ROOT / "results" / "quartus-lite-25.1std-max10-summary.json",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = args.output_root.expanduser().resolve()
    evidence = args.evidence_root.expanduser().resolve()
    snapshot = args.result_snapshot.expanduser().resolve()
    if evidence.exists():
        raise EvidenceError(
            f"refusing to overwrite existing evidence directory: {evidence}"
        )
    evidence.mkdir(parents=True)

    for name in ROOT_FILES:
        copy_file(output / name, evidence / name)

    for variant, mapping in RUNS:
        source_run = output / variant / mapping
        destination_run = evidence / variant / mapping
        for name in RUN_FILES:
            copy_file(source_run / name, destination_run / name)
        project = f"int8_{variant}_{mapping}"
        for suffix in PROJECT_SUFFIXES:
            copy_file(
                source_run / f"{project}{suffix}",
                destination_run / f"{project}{suffix}",
            )
        for suffix in REPORT_SUFFIXES:
            copy_file(
                source_run / "output_files" / f"{project}{suffix}",
                destination_run / "output_files" / f"{project}{suffix}",
            )

    payload_files = sorted(
        path for path in evidence.rglob("*") if path.is_file()
    )
    for path in payload_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        if "/Users/" in text or "juanjosefernandezmorales" in text:
            raise EvidenceError(
                f"personal absolute path found in evidence; rerun from a neutral path: {path}"
            )

    combined = json.loads((evidence / "summary.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": 1,
        "experiment": "quartus-int8-matvec-max10-transfer-v1",
        "quartus_version": combined["contract"]["quartus_version"],
        "device": combined["contract"]["device"],
        "files": [
            {
                "path": path.relative_to(evidence).as_posix(),
                "sha256": sha256(path),
                "size_bytes": path.stat().st_size,
            }
            for path in payload_files
        ],
    }
    manifest_path = evidence / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    checksum_paths = [*payload_files, manifest_path]
    (evidence / "SHA256SUMS").write_text(
        "".join(
            f"{sha256(path)}  {path.relative_to(evidence).as_posix()}\n"
            for path in sorted(checksum_paths)
        ),
        encoding="utf-8",
    )
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(evidence / "summary.json", snapshot)
    print(f"evidence_files={len(payload_files)}")
    print(f"evidence_root={evidence}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EvidenceError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
