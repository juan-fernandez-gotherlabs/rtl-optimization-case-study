"""Command-line entry point for non-certifying SHA/VTR search triage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domains.rtl_sha_vtr.triage import default_cache_dir, evaluate_triage  # noqa: E402


def main() -> int:
    """Evaluate one candidate and emit a ranking-only result."""
    parser = argparse.ArgumentParser(
        description="Run fast, non-certifying SHA/VTR candidate triage."
    )
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--candidate-id", default="candidate")
    parser.add_argument("--cache-dir", type=Path, default=default_cache_dir())
    args = parser.parse_args()
    payload = evaluate_triage(
        args.workspace,
        candidate_id=args.candidate_id,
        cache_dir=args.cache_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
