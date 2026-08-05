"""Registration and candidate-boundary contract for VTR SHA-1 RTL optimization."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from agent.core import register_domain
from agent.core.definitions import DomainInterface, OptimizationObjectiveSpec

from .evaluator import RtlShaVtrEvaluator, build_default_domain, preflight

GUIDANCE_DOCUMENTS: Sequence[str] = ("domains/rtl_sha_vtr/CONTEXT.md",)
EVOLVE_BLOCKS: Sequence[str] = ("domains/rtl_sha_vtr/benchmarks/sha.v::sha1",)
FULL_SOURCE_FILES: Sequence[str] = ("domains/rtl_sha_vtr/benchmarks/sha.v",)


@register_domain("rtl_sha_vtr")
class RtlShaVtrDomain(DomainInterface):
    """A generator-neutral evaluator contract with exactly one editable artifact."""

    def __init__(self) -> None:
        """Load the frozen SHA/VTR domain specification."""
        self._spec = build_default_domain()

    def get_evaluator(self) -> RtlShaVtrEvaluator:
        """Return the bounded, local-first evaluator."""
        return RtlShaVtrEvaluator(self._spec)

    def get_metric_weights(self) -> Mapping[str, float]:
        """Return the declared VTR metrics."""
        return dict(self._spec.metric_weights)

    def get_evolve_blocks(self) -> Sequence[str]:
        """Expose only the materialized VTR sha.v module for edits."""
        return EVOLVE_BLOCKS

    def get_prompt_context(
        self,
        parent: object,
        inspirations: Sequence[object],
        database: object,
        generation: int,
        **kwargs: object,
    ) -> Mapping[str, Any]:
        """Describe the immutable benchmark boundary to either Evölther frontend."""
        del parent, inspirations, database, generation
        baseline = self._spec.baseline.get("aggregate", {})
        return {
            "domain": "Pinned VTR SHA-1 RTL optimization",
            "task_description": "Edit only sha.v after it has been materialized from the manifest.",
            "problem_definition_text": (
                "Cycle-exact simulation and unbounded formal equivalence are mandatory for every proposal; "
                "NIST qualification is repeated for certification. The 45 nm VTR architecture, PTM, activity, "
                "two seed pools, flow and tool revisions are frozen."
            ),
            "competition_rules_text": (
                "Use the five exposed search seeds only for provisional ranking. Only the disjoint fixed 64-seed "
                "pool can certify a candidate. The equal-weight paired PPA geometric mean is minimized; an "
                "improvement is accepted only when its one-sided 95% confidence bound is below 1.0 and no primary "
                "metric has evidence of regression. Search retains at most three unique finalists; a new champion "
                "must prove superiority to the incumbent and every other proven finalist. The baseline score is 1.0."
            ),
            "baseline_metrics": {
                "score": 1.0,
                "area_total_mwta": baseline.get("area_total_mwta", {}).get("median"),
                "critical_path_delay_ns": baseline.get(
                    "critical_path_delay_ns", {}
                ).get("median"),
                "energy_per_block_nj": baseline.get("energy_per_block_nj", {}).get(
                    "median"
                ),
            },
            "evolve_blocks": EVOLVE_BLOCKS,
            "full_source_files": FULL_SOURCE_FILES,
            "guidance_documents": GUIDANCE_DOCUMENTS,
            "previous_error": kwargs.get("previous_error"),
        }

    def get_optimization_objective_spec(self) -> OptimizationObjectiveSpec:
        """Minimize equal-weight routed area, delay and active-workload energy."""
        return OptimizationObjectiveSpec(
            quality_metric="score",
            metric_directions={
                "score": "min",
                "functional_pass": "max",
                "formal_pass": "max",
                "area_total_mwta": "min",
                "critical_path_delay_ns": "min",
                "energy_per_block_nj": "min",
                "accepted_improvement": "max",
                "fmax_mhz": "max",
                "busy_cycles_per_block": "min",
                "initiation_interval_cycles": "min",
                "throughput_mblocks_per_s": "max",
                "clb_blocks": "min",
                "registers": "min",
                "memories": "min",
                "timing_channel_width": "min",
                "active_total_power_w": "min",
                "active_dynamic_power_w": "min",
                "active_static_power_w": "min",
                "idle_total_power_w": "min",
            },
        )

    def validate_candidate(self, workspace: Path) -> None:
        """Fail fast with the same local diagnostics used by the baseline probe."""
        diagnostics = preflight(Path(workspace), self._spec)
        if diagnostics:
            raise RuntimeError(
                "RTL SHA VTR preflight failed: " + "; ".join(diagnostics)
            )

    def get_candidate_support_paths(self) -> Sequence[str]:
        """Keep frozen contracts beside the single editable RTL source."""
        return (
            "domains/rtl_sha_vtr/benchmarks",
            "domains/rtl_sha_vtr/CONTEXT.md",
            "domains/rtl_sha_vtr/evaluator.py",
            "domains/rtl_sha_vtr/config.py",
            "domains/rtl_sha_vtr/local_submit.py",
            "domains/rtl_sha_vtr/triage.py",
            "domains/rtl_sha_vtr/runner.py",
            "domains/rtl_sha_vtr/selection.py",
            "domains/rtl_sha_vtr/evidence/ppa45/baseline.json",
        )
