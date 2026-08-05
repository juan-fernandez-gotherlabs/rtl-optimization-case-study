"""Certify the corrected SHA-1 seed without launching any optimization."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from domains.rtl_sha_vtr.evaluator import (  # noqa: E402
    BENCHMARK_DIR,
    CERTIFICATION_SEEDS,
    MANIFEST_PATH,
    SEARCH_SEEDS,
    RunnerFailure,
    build_default_domain,
    sha256_file,
    summarize,
)
from domains.rtl_sha_vtr.runner import DockerPpa45Runner  # noqa: E402


def _image_identity(image: str) -> dict[str, str]:
    completed = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            "{{.Id}} {{.RepoDigests}} {{.Os}}/{{.Architecture}}",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    fields = completed.stdout.strip().split(maxsplit=2)
    return {"id": fields[0], "repo_digests": fields[1], "platform": fields[2]}


def main() -> int:
    """Run the selected certification phase and emit evidence only after success."""
    parser = argparse.ArgumentParser(
        description="Run the non-optimization SHA/VTR baseline gates."
    )
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument(
        "--phase", choices=("functional", "preflight", "certify"), default="functional"
    )
    args = parser.parse_args()
    if args.results.exists() and any(args.results.iterdir()):
        parser.error("--results must be a new or empty directory")
    args.results.mkdir(parents=True, exist_ok=True)

    spec = build_default_domain()
    runner = DockerPpa45Runner(spec)
    candidate = BENCHMARK_DIR / "sha.v"
    started = datetime.now(timezone.utc)
    inventory = runner.collect_environment(candidate, args.results)
    correctness = runner.run_candidate_correctness(candidate, args.results)
    nist = runner.run_nist_short_long(candidate, args.results)
    payload: dict[str, object] = {
        "schema_version": 2,
        "status": "functional_pass",
        "phase": args.phase,
        "started_at_utc": started.isoformat(),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "golden_seed_sha256": sha256_file(candidate),
        "functional": correctness,
        "environment_inventory": inventory,
        "nist_short_long": nist,
        "measurement_environment": {
            "image": {"tag": runner.image, **_image_identity(runner.image)}
        },
    }
    if args.phase in {"preflight", "certify"}:
        activity = runner.prepare_activity(candidate, args.results)
        payload["activity"] = activity
        preflight = runner.run_seed(candidate, args.results, 1, run_label="preflight")
        payload["preflight_seed_1"] = asdict(preflight)
        payload["preflight_power_warning_fingerprints"] = json.loads(
            (
                args.results / "preflight_seed_1" / "power_warning_fingerprints.json"
            ).read_text(encoding="utf-8")
        )
        payload["status"] = "preflight_pass"
    if args.phase == "certify":
        vectors = runner.run_certification_vectors(candidate, args.results)
        payload["certification_vectors"] = vectors
        mutation = runner.run_mutation(candidate, args.results)
        payload["mutation"] = mutation
        search_per_seed = runner.run_seed_pool(candidate, args.results, SEARCH_SEEDS)
        per_seed = runner.run_seed_pool(candidate, args.results, CERTIFICATION_SEEDS)
        search_aggregate = summarize(search_per_seed, expected_seeds=SEARCH_SEEDS)
        aggregate = summarize(per_seed, expected_seeds=CERTIFICATION_SEEDS)
        payload["search_per_seed"] = [asdict(item) for item in search_per_seed]
        payload["per_seed"] = [asdict(item) for item in per_seed]
        payload["power_warning_fingerprints"] = {
            str(seed): json.loads(
                (
                    args.results / f"seed_{seed}" / "power_warning_fingerprints.json"
                ).read_text(encoding="utf-8")
            )
            for seed in (*SEARCH_SEEDS, *CERTIFICATION_SEEDS)
        }
        payload["aggregate"] = {
            name: asdict(summary) for name, summary in aggregate.items()
        }
        payload["search_aggregate"] = {
            name: asdict(summary) for name, summary in search_aggregate.items()
        }
        payload["seeds"] = list(CERTIFICATION_SEEDS)
        payload["search_seeds"] = list(SEARCH_SEEDS)
        payload["status"] = "success"
    payload["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    evidence_hashes = {
        str(path.relative_to(args.results)): sha256_file(path)
        for path in sorted(args.results.rglob("*"))
        if path.is_file() and not path.name.startswith("baseline_")
    }
    payload["evidence_hashes"] = evidence_hashes
    payload["evidence_root_sha256"] = hashlib.sha256(
        json.dumps(evidence_hashes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output = args.results / f"baseline_{args.phase}.json"
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"RTL_SHA_VTR_BASELINE_{args.phase.upper()}_PASS evidence={output}")
    return 0


def guarded_main() -> int:
    """Persist a fail-closed summary when an external certification stage fails."""
    try:
        return main()
    except (
        RunnerFailure,
        OSError,
        ValueError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        recovery = argparse.ArgumentParser(add_help=False)
        recovery.add_argument("--results", type=Path)
        recovery.add_argument(
            "--phase",
            choices=("functional", "preflight", "certify"),
            default="functional",
        )
        args, _ = recovery.parse_known_args()
        if args.results is None:
            raise
        args.results.mkdir(parents=True, exist_ok=True)
        evidence_hashes = {
            str(path.relative_to(args.results)): sha256_file(path)
            for path in sorted(args.results.rglob("*"))
            if path.is_file() and not path.name.startswith("baseline_")
        }
        payload: dict[str, object] = {
            "schema_version": 2,
            "status": "failure",
            "phase": args.phase,
            "failed_stage": (
                exc.stage
                if isinstance(exc, RunnerFailure)
                else "certification_integrity"
            ),
            "diagnostics": [str(exc)],
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": sha256_file(MANIFEST_PATH),
            "evidence_hashes": evidence_hashes,
            "evidence_root_sha256": hashlib.sha256(
                json.dumps(
                    evidence_hashes, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest(),
        }
        if isinstance(exc, RunnerFailure):
            payload["stdout_tail"] = exc.stdout_tail
            payload["stderr_tail"] = exc.stderr_tail
        output = args.results / f"baseline_{args.phase}_failure.json"
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"RTL_SHA_VTR_BASELINE_{args.phase.upper()}_FAIL stage={payload['failed_stage']} evidence={output}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(guarded_main())
