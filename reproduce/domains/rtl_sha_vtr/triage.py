"""Formal-gated, non-certifying search triage for the SHA/VTR domain.

Every submission is frozen by SHA-256 before evaluation.  The promoted
evaluator remains the only acceptance authority, but the local search tier now
requires EQY to pass before spending any work on activity or five-seed PPA.
"""

from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import math
import os
import shutil
import statistics
import tempfile
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .evaluator import (
    MANIFEST_PATH,
    PRIMARY_METRICS,
    SEARCH_SEEDS,
    RtlShaVtrSpec,
    RunnerFailure,
    baseline_seed_metrics,
    build_default_domain,
    candidate_path,
    preflight,
    search_score,
    sha256_file,
)
from .runner import DockerPpa45Runner

TRIAGE_SCHEMA_VERSION = 4


@contextmanager
def _cache_key_lock(cache_dir: Path, key: str):
    """Serialize expensive identical submissions without leaving stale locks."""
    lock_dir = cache_dir / ".locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    with (lock_dir / f"{key}.lock").open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _evidence_hashes(root: Path) -> dict[str, str]:
    """Hash bounded evidence files while excluding the self-referential result."""
    return {
        str(path.relative_to(root)): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "triage_result.json" and path.stat().st_size <= 50_000_000
    }


def _cache_key(spec: RtlShaVtrSpec, candidate_sha256: str) -> str:
    """Bind a cache entry to RTL, the certified contract and this triage implementation."""
    payload = {
        "schema_version": TRIAGE_SCHEMA_VERSION,
        "candidate_sha256": candidate_sha256,
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "baseline_manifest_sha256": spec.baseline["manifest_sha256"],
        "image_id": spec.baseline["measurement_environment"]["image"]["id"],
        "triage_sha256": sha256_file(Path(__file__)),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _load_cache(entry: Path, key: str) -> dict[str, Any] | None:
    """Return a verified complete cache entry or fail closed on corruption."""
    result_path = entry / "triage_result.json"
    if not entry.exists():
        return None
    if not result_path.is_file():
        raise RunnerFailure("triage_cache_integrity", f"incomplete cache entry: {key}")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    if payload.get("cache", {}).get("key") != key:
        raise RunnerFailure("triage_cache_integrity", f"invalid cache metadata: {key}")
    expected = payload.get("evidence", {}).get("hashes")
    if not isinstance(expected, dict) or _evidence_hashes(entry) != expected:
        raise RunnerFailure("triage_cache_integrity", f"cached evidence hash mismatch: {key}")
    return payload


class DockerTriageRunner(DockerPpa45Runner):
    """Run the hard functional/formal gate before five exposed search seeds."""

    def run_triage(self, candidate: Path, results: Path) -> tuple[Any, dict[str, Any]]:
        """Return five search seeds only after the complete EQY gate passes."""
        correctness = self.run_candidate_correctness(candidate, results)
        activity = self.prepare_activity(candidate, results)
        measured = self.run_seed_pool(candidate, results, SEARCH_SEEDS)
        return measured, {
            "evaluation_tier": "search",
            "correctness": correctness,
            "activity": activity,
            "formal_status": "pass",
        }


def _failure(
    candidate_id: str,
    candidate_sha256: str | None,
    stage: str,
    diagnostic: str,
    *,
    formal_status: str = "not_run",
) -> dict[str, Any]:
    """Create a fail-closed triage payload without implying formal validity."""
    return {
        "schema_version": TRIAGE_SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "candidate_sha256": candidate_sha256,
        "evaluation_tier": "search",
        "triage_pass": False,
        "eligible_for_certification": False,
        "valid": False,
        "certified": False,
        "accepted_improvement": False,
        "acceptance_decision": None,
        "formal_status": formal_status,
        "score": math.inf,
        "provisional_score": math.inf,
        "status": stage,
        "diagnostics": [diagnostic],
    }


def evaluate_triage(
    workspace: Path,
    *,
    candidate_id: str,
    cache_dir: Path,
    spec: RtlShaVtrSpec | None = None,
) -> dict[str, Any]:
    """Evaluate or retrieve one content-addressed, non-certifying triage result."""
    spec = spec or build_default_domain()
    candidate = candidate_path(workspace)
    try:
        candidate_bytes = candidate.read_bytes()
    except OSError:
        candidate_bytes = None
    candidate_hash = hashlib.sha256(candidate_bytes).hexdigest() if candidate_bytes is not None else None
    diagnostics = preflight(workspace, spec)
    if diagnostics:
        return _failure(
            candidate_id,
            candidate_hash,
            "blocked_prerequisites",
            "; ".join(diagnostics),
        )
    if candidate_bytes is None or candidate_hash is None:
        return _failure(candidate_id, candidate_hash, "submission_snapshot", "editable RTL cannot be read")
    if sha256_file(candidate) != candidate_hash:
        return _failure(
            candidate_id,
            candidate_hash,
            "submission_source_changed",
            "editable RTL changed while the submission was being frozen; resubmit",
        )
    key = _cache_key(spec, candidate_hash)
    cache_dir.mkdir(parents=True, exist_ok=True)
    entry = cache_dir / key
    try:
        cached = _load_cache(entry, key)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, RunnerFailure) as exc:
        return _failure(candidate_id, candidate_hash, "triage_cache_integrity", str(exc))
    if cached is not None:
        cached = {**cached, "candidate_id": candidate_id}
        cached["cache"] = {**cached["cache"], "hit": True}
        cached["evidence"] = {**cached["evidence"], "root": str(entry.resolve())}
        return cached

    with _cache_key_lock(cache_dir, key):
        # A concurrent identical submission may have populated the cache while
        # this process waited.  Re-check under the per-key lock before running
        # any Docker stages.
        try:
            cached = _load_cache(entry, key)
        except (
            OSError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            RunnerFailure,
        ) as exc:
            return _failure(candidate_id, candidate_hash, "triage_cache_integrity", str(exc))
        if cached is not None:
            cached = {**cached, "candidate_id": candidate_id}
            cached["cache"] = {**cached["cache"], "hit": True}
            cached["evidence"] = {**cached["evidence"], "root": str(entry.resolve())}
            return cached

        attempt = Path(tempfile.mkdtemp(prefix=f".{key}.", dir=cache_dir))
        runner = DockerTriageRunner(spec)
        try:
            snapshot = attempt / "submission" / candidate_hash / "sha.v"
            snapshot.parent.mkdir(parents=True, exist_ok=False)
            snapshot.write_bytes(candidate_bytes)
            snapshot.chmod(0o444)
            if sha256_file(snapshot) != candidate_hash:
                raise RunnerFailure("submission_snapshot", "immutable submission SHA-256 mismatch")
            measured, evidence = runner.run_triage(snapshot, attempt)
            baseline = baseline_seed_metrics(spec, tier="search")
            assessment = search_score(measured, baseline)
            hashes = _evidence_hashes(attempt)
            payload: dict[str, Any] = {
                "schema_version": TRIAGE_SCHEMA_VERSION,
                "candidate_id": candidate_id,
                "candidate_sha256": candidate_hash,
                "evaluation_tier": "search",
                "triage_pass": True,
                "eligible_for_certification": True,
                "valid": True,
                "valid_scope": "non_certifying_search_triage",
                "certified": False,
                "accepted_improvement": False,
                "acceptance_decision": None,
                "formal_status": "pass",
                "score": assessment.score,
                "provisional_score": assessment.score,
                "proxy_ratios": assessment.median_ratios,
                "descriptive_uncertainty": assessment.confidence,
                "metrics": {
                    name: statistics.median(float(getattr(item, name)) for item in measured)
                    for name in (*PRIMARY_METRICS, "fmax_mhz")
                },
                "per_seed": [asdict(item) for item in measured],
                "submission": {
                    "sha256": candidate_hash,
                    "snapshot": str(snapshot.relative_to(attempt)),
                    "immutable": True,
                },
                "evidence": {**evidence, "hashes": hashes},
                "cache": {"key": key, "hit": False},
                "status": "valid_search_score",
                "notes": (
                    "Ranking-only result produced after EQY passed on the frozen RTL. "
                    "The candidate must still pass the disjoint 64-seed certification flow before acceptance."
                ),
            }
            (attempt / "triage_result.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            try:
                os.rename(attempt, entry)
            except OSError as exc:
                # Retain a defensive cross-platform collision path even though
                # cooperating local submissions are serialized above.
                if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                    raise
                existing = _load_cache(entry, key)
                if existing is None:
                    raise RunnerFailure(
                        "triage_cache_integrity",
                        f"concurrent cache publication failed: {key}",
                    ) from None
                shutil.rmtree(attempt)
                payload = existing
                payload["cache"] = {**payload["cache"], "hit": True}
            payload["candidate_id"] = candidate_id
            payload["evidence"] = {**payload["evidence"], "root": str(entry.resolve())}
            return payload
        except (
            OSError,
            StopIteration,
            TypeError,
            ValueError,
            ZeroDivisionError,
            RunnerFailure,
        ) as exc:
            if isinstance(exc, RunnerFailure):
                stage = exc.stage
                diagnostic = str(exc)
            else:
                stage = "triage_integrity"
                diagnostic = str(exc)
            formal_status = (
                "fail"
                if (attempt / "formal_driver.log").is_file()
                and "Successfully proved designs equivalent"
                not in (attempt / "formal_driver.log").read_text(encoding="utf-8", errors="replace")
                else "not_run"
            )
            payload = _failure(
                candidate_id,
                candidate_hash,
                stage,
                diagnostic,
                formal_status=formal_status,
            )
            hashes = _evidence_hashes(attempt)
            payload["submission"] = {
                "sha256": candidate_hash,
                "snapshot": str(snapshot.relative_to(attempt))
                if "snapshot" in locals() and snapshot.is_file()
                else None,
                "immutable": "snapshot" in locals() and snapshot.is_file(),
            }
            payload["evidence"] = {"hashes": hashes}
            payload["cache"] = {"key": key, "hit": False}
            (attempt / "triage_result.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.rename(attempt, entry)
            payload["evidence"]["root"] = str(entry.resolve())
            return payload
        finally:
            if attempt.exists():
                shutil.rmtree(attempt)


def default_cache_dir() -> Path:
    """Return an isolated host-local cache suitable for repeated search proposals."""
    return Path(tempfile.gettempdir()) / "evolther-rtl-sha-vtr-triage-cache"
