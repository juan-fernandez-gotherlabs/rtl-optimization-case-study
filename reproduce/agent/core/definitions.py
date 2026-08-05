"""Small public types required by the exact evaluator source snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


Number = int | float


@dataclass(slots=True)
class EvaluationResult:
    score: Number
    metrics: Mapping[str, Number]
    valid: bool = True
    candidate_id: str = "candidate"
    trace: dict = field(default_factory=dict)
    baseline_score: Number | None = None
    notes: str | None = None
    signature: object | None = None


@dataclass(frozen=True, slots=True)
class OptimizationObjectiveSpec:
    quality_metric: str = "score"
    metric_directions: Mapping[str, str] = field(default_factory=lambda: {"score": "min"})


class DomainInterface:
    """Compatibility base class; the case study calls the evaluator directly."""
