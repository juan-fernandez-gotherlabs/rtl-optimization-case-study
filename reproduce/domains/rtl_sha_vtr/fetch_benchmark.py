"""Rebuild the corrected golden seed from the exact pinned VTR source."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import urllib.request
from pathlib import Path


def manifest() -> dict[str, object]:
    """Load the immutable VTR SHA benchmark manifest."""
    path = Path(__file__).with_name("benchmarks") / "sha_vtr_manifest.json"
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    """Download upstream, verify it, apply the frozen patch, and verify gold."""
    parser = argparse.ArgumentParser(
        description="Materialize the corrected pinned VTR SHA-1 seed."
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--from-vtr-checkout",
        type=Path,
        help=(
            "Use the already pinned local VTR checkout instead of downloading; useful on hosts with restricted CA "
            "stores."
        ),
    )
    args = parser.parse_args()
    source = manifest()["source"]
    assert isinstance(source, dict)
    if args.from_vtr_checkout:
        checkout_source = args.from_vtr_checkout / str(source["path"])
        if not checkout_source.exists():
            raise FileNotFoundError(
                f"Pinned VTR source is absent from checkout: {checkout_source}"
            )
        content = checkout_source.read_bytes()
    else:
        with urllib.request.urlopen(
            str(source["url"]), timeout=30
        ) as response:  # noqa: S310 - URL is pinned in manifest
            content = response.read()
    actual = hashlib.sha256(content).hexdigest()
    if actual != source["upstream_sha256"]:
        raise RuntimeError(
            f"upstream sha.v digest mismatch: expected {source['upstream_sha256']}, got {actual}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    patch_path = Path(__file__).with_name("benchmarks") / str(
        source["conformance_patch"]
    )
    with tempfile.TemporaryDirectory(prefix="sha1_gold_") as temporary:
        materialized = Path(temporary) / "sha.v"
        materialized.write_bytes(content)
        subprocess.run(
            ["patch", "--silent", str(materialized), str(patch_path)], check=True
        )
        corrected = materialized.read_bytes()
    corrected_hash = hashlib.sha256(corrected).hexdigest()
    if corrected_hash != source["golden_seed_sha256"]:
        raise RuntimeError(
            f"corrected sha.v digest mismatch: expected {source['golden_seed_sha256']}, got {corrected_hash}"
        )
    args.output.write_bytes(corrected)
    print(
        f"materialized corrected golden seed {args.output} ({corrected_hash}); upstream={actual}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
