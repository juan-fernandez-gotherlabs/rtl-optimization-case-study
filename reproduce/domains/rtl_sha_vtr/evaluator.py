"""Professional SHA-1/VTR domain contract, PPA parsers and public score."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from agent.core.definitions import EvaluationResult

DOMAIN_DIR = Path(__file__).resolve().parent
BENCHMARK_DIR = DOMAIN_DIR / "benchmarks"
MANIFEST_PATH = BENCHMARK_DIR / "sha_vtr_manifest.json"
BASELINE_EVIDENCE_PATH = DOMAIN_DIR / "evidence" / "ppa45" / "baseline.json"
SEARCH_SEEDS = (1, 7, 19, 43, 97)
# The certification pool is deliberately disjoint from SEARCH_SEEDS.  It is a
# fixed audit set, not a menu from which an evaluator may choose favourable
# placements after seeing a candidate.
CERTIFICATION_SEEDS = tuple(seed for seed in range(2, 69) if seed not in SEARCH_SEEDS)
if len(CERTIFICATION_SEEDS) != 64:  # pragma: no cover - import-time contract guard
    raise RuntimeError("the frozen certification pool must contain exactly 64 seeds")


_EXPECTED_INTERFACE = {
    "clk_i": ("input", 1),
    "rst_i": ("input", 1),
    "text_i": ("input", 32),
    "text_o": ("output", 32),
    "cmd_i": ("input", 3),
    "cmd_w_i": ("input", 1),
    "cmd_o": ("output", 4),
}
_FORBIDDEN_CODE_PATTERNS = {
    "simulation/formal system task": re.compile(
        r"\$(?:display|write|strobe|monitor|finish|stop|fatal|error|warning|info|readmem[bh]|random|"
        r"time|test\$plusargs|value\$plusargs|dump\w*|anyconst|anyseq|allconst|allseq|assert|assume|cover)\b",
        re.IGNORECASE,
    ),
    "include directive": re.compile(r"`include\b", re.IGNORECASE),
    "conditional compilation": re.compile(r"`ifn?def\b", re.IGNORECASE),
    "simulation-only initial block": re.compile(r"\binitial\b", re.IGNORECASE),
    "simulation-only final block": re.compile(r"\bfinal\b", re.IGNORECASE),
    "DPI declaration": re.compile(r"\bDPI(?:-C)?\b", re.IGNORECASE),
    "delay control": re.compile(r"(?<!`)#\s*(?:\d|\()"),
    "force/release": re.compile(r"\b(?:force|release)\b", re.IGNORECASE),
}
_SYNTHESIS_EXCLUSION_PATTERN = re.compile(
    r"translate_(?:off|on)|verilator\s+(?:lint|tracing)_off", re.IGNORECASE
)
PRIMARY_METRICS = ("area_total_mwta", "critical_path_delay_ns", "energy_per_block_nj")
EVALUATION_TIERS = ("search", "certification")


@dataclass(frozen=True, slots=True)
class RtlShaVtrSpec:
    """Frozen evaluator inputs shared by classic Evölther and Evölther Codex."""

    manifest: dict[str, Any]
    baseline: dict[str, Any]
    metric_weights: dict[str, float]


@dataclass(frozen=True, slots=True)
class PowerMetrics:
    """One VPR power report in watts."""

    total_w: float
    dynamic_w: float
    static_w: float
    technology_nm: float
    voltage_v: float
    temperature_c: float
    critical_path_s: float
    channel_width: int
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SeedMetrics:
    """Post-route PPA and informative utilization for one VPR seed."""

    seed: int
    area_total_mwta: float
    logic_block_area_mwta: float
    routing_area_mwta: float
    critical_path_delay_ns: float
    energy_per_block_nj: float
    active_total_power_w: float
    active_dynamic_power_w: float
    active_static_power_w: float
    idle_total_power_w: float
    fmax_mhz: float
    clb_blocks: int
    registers: int
    memories: int
    timing_channel_width: int


# Compatibility name for callers of the initial canary API.
VtrMetrics = SeedMetrics


@dataclass(frozen=True, slots=True)
class MetricSummary:
    """Distribution reported for one frozen seed pool."""

    median: float
    worst: float
    minimum: float
    maximum: float
    population_stdev: float
    relative_range: float


@dataclass(frozen=True, slots=True)
class ScoreAssessment:
    """Public paired score and its fixed-sample evidence decision."""

    valid: bool
    accepted_improvement: bool
    score: float
    median_ratios: dict[str, float]
    worst_ratios: dict[str, float]
    effective_ratios: dict[str, float]
    improved_metrics: tuple[str, ...]
    rejection_reasons: tuple[str, ...]
    decision: str = "inconclusive"
    confidence: dict[str, Any] | None = None

    @property
    def improved(self) -> bool:
        """Return whether the final pool proves a PPA improvement."""
        return self.accepted_improvement

    @property
    def no_regression(self) -> bool:
        """Return whether no primary metric has evidence of regression."""
        return self.decision != "evidence_regression"


class RunnerFailure(RuntimeError):
    """Bounded failure raised by an isolated Docker evaluation stage."""

    def __init__(
        self, stage: str, message: str, *, stdout: str = "", stderr: str = ""
    ) -> None:
        """Capture the failed stage plus bounded diagnostic tails."""
        super().__init__(message)
        self.stage = stage
        self.stdout_tail = _tail(stdout)
        self.stderr_tail = _tail(stderr)


class DomainRunner(Protocol):
    """Runner seam used by the production Docker flow and contract tests."""

    def run(
        self, candidate: Path, results_dir: Path, *, tier: str
    ) -> tuple[Sequence[SeedMetrics], dict[str, Any]]:
        """Return tier-appropriate seed metrics and evidence hashes."""
        ...


def _tail(value: str, limit: int = 4000) -> str:
    return value[-limit:] if len(value) > limit else value


def sha256_file(path: Path) -> str:
    """Return a file's SHA-256 digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_default_domain() -> RtlShaVtrSpec:
    """Load the v3 contract and the separately certified 45 nm baseline."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE_EVIDENCE_PATH.read_text(encoding="utf-8"))
    return RtlShaVtrSpec(
        manifest=manifest,
        baseline=baseline,
        metric_weights={
            "score": 1.0,
            "functional_pass": 1.0,
            "formal_pass": 1.0,
            "area_total_mwta": 1.0 / 3.0,
            "critical_path_delay_ns": 1.0 / 3.0,
            "energy_per_block_nj": 1.0 / 3.0,
        },
    )


def _docker_image(spec: RtlShaVtrSpec) -> str:
    configured = str(spec.baseline["measurement_environment"]["image"]["tag"])
    return os.environ.get("RTL_SHA_VTR_IMAGE", configured).strip() or configured


def _expected_image_id(spec: RtlShaVtrSpec) -> str | None:
    value = spec.baseline["measurement_environment"]["image"].get("id")
    return str(value) if value else None


def _inspect_docker_image(image: str, expected_id: str | None) -> tuple[str, ...]:
    if shutil.which("docker") is None:
        return ("missing executable: docker",)
    try:
        engine = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return (f"Docker Engine is unavailable: {exc.__class__.__name__}",)
    if engine.returncode:
        return (
            "Docker Engine is unavailable; open Docker Desktop and wait for Engine ready",
        )
    inspected = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            image,
            "--format",
            "{{.Id}} {{.Os}}/{{.Architecture}}",
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    if inspected.returncode:
        return (f"missing pinned Docker image: {image}",)
    fields = inspected.stdout.strip().split()
    if len(fields) != 2:
        return (f"could not inspect pinned Docker image: {image}",)
    actual_id, platform = fields
    errors: list[str] = []
    if expected_id and actual_id != expected_id:
        errors.append(
            f"Docker image ID differs from baseline: expected {expected_id}, got {actual_id}"
        )
    if platform != "linux/amd64":
        errors.append(f"Docker image platform must be linux/amd64, got {platform}")
    return tuple(errors)


def candidate_path(workspace: Path) -> Path:
    """Resolve the only editable artifact in a candidate workspace."""
    return Path(workspace) / "domains" / "rtl_sha_vtr" / "benchmarks" / "sha.v"


def candidate_source_diagnostics(path: Path) -> tuple[str, ...]:
    """Block common simulation/synthesis divergence and evaluator escape hatches."""
    source = path.read_text(encoding="utf-8", errors="replace")
    code = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    code = re.sub(r"//[^\n]*", " ", code)
    errors = [
        f"editable sha.v contains forbidden {label}"
        for label, pattern in _FORBIDDEN_CODE_PATTERNS.items()
        if pattern.search(code)
    ]
    if _SYNTHESIS_EXCLUSION_PATTERN.search(source):
        errors.append("editable sha.v contains forbidden synthesis exclusion directive")
    if len(source.encode()) > 2_000_000:
        errors.append("editable sha.v exceeds the 2 MB evaluator limit")
    return tuple(errors)


def _verify_frozen_files(manifest: dict[str, Any]) -> list[str]:
    expected = {
        BENCHMARK_DIR
        / manifest["source"]["conformance_patch"]: manifest["source"][
            "conformance_patch_sha256"
        ],
        BENCHMARK_DIR
        / manifest["functional_contract"]["abc_testbench"]: manifest[
            "functional_contract"
        ]["abc_testbench_sha256"],
        BENCHMARK_DIR
        / manifest["functional_contract"]["cycle_equivalence_testbench"]: manifest[
            "functional_contract"
        ]["cycle_equivalence_testbench_sha256"],
        BENCHMARK_DIR
        / manifest["functional_contract"]["nist_testbench"]: manifest[
            "functional_contract"
        ]["nist_testbench_sha256"],
        BENCHMARK_DIR
        / manifest["functional_contract"]["formal_config"]: manifest[
            "functional_contract"
        ]["formal_config_sha256"],
    }
    expected.update(
        {
            BENCHMARK_DIR / "nist_shavs" / name: digest
            for name, digest in manifest["nist_shavs"]["files"].items()
        }
    )
    expected[DOMAIN_DIR / "generate_nist_corpus.py"] = manifest["nist_shavs"][
        "corpus_generator_sha256"
    ]
    expected[DOMAIN_DIR / "activity_vectors.py"] = manifest["activity"][
        "generator_sha256"
    ]
    expected[BENCHMARK_DIR / manifest["activity"]["ace_patch"]] = manifest["activity"][
        "ace_patch_sha256"
    ]
    expected[DOMAIN_DIR / manifest["toolchain"]["dockerfile"]] = manifest["toolchain"][
        "dockerfile_sha256"
    ]
    expected[DOMAIN_DIR / manifest["toolchain"]["python_lock"]] = manifest["toolchain"][
        "python_lock_sha256"
    ]
    expected[DOMAIN_DIR / "sbom.py"] = manifest["toolchain"]["sbom_generator_sha256"]
    eqy_compatibility = manifest["formal_and_mutation"]["eqy_yosys_compatibility"]
    expected[BENCHMARK_DIR / eqy_compatibility["patch"]] = eqy_compatibility[
        "patch_sha256"
    ]
    project_files = manifest["formal_and_mutation"]["project_files"]
    expected.update(
        {
            DOMAIN_DIR / "mutation" / name: digest
            for name, digest in project_files.items()
        }
    )
    expected.update(
        {
            DOMAIN_DIR / name: digest
            for name, digest in manifest["evaluator_integrity"]["files"].items()
        }
    )
    return [
        f"frozen file hash mismatch: {path.relative_to(DOMAIN_DIR)}"
        for path, digest in expected.items()
        if not path.is_file() or sha256_file(path) != digest
    ]


def preflight(workspace: Path, spec: RtlShaVtrSpec | None = None) -> tuple[str, ...]:
    """Fast gate used before any costly formal or PPA stage."""
    spec = spec or build_default_domain()
    errors = _verify_frozen_files(spec.manifest)
    candidate = candidate_path(workspace)
    if not candidate.is_file():
        errors.append("missing editable RTL at domains/rtl_sha_vtr/benchmarks/sha.v")
    else:
        errors.extend(candidate_source_diagnostics(candidate))
    if spec.baseline.get("status") != "success":
        errors.append("45 nm baseline is not certified; candidate evaluation is locked")
    if spec.baseline.get("manifest_sha256") != sha256_file(MANIFEST_PATH):
        errors.append("45 nm baseline is bound to a different domain manifest")
    if spec.baseline.get("contract_revision") != spec.manifest.get("contract_revision"):
        errors.append("45 nm baseline is bound to a different contract revision")
    if spec.baseline.get("golden_seed_sha256") != spec.manifest.get("source", {}).get(
        "golden_seed_sha256"
    ):
        errors.append("45 nm baseline is bound to a different golden RTL seed")
    manifest_search = tuple(spec.manifest.get("toolchain", {}).get("search_seeds", ()))
    manifest_certification = tuple(
        spec.manifest.get("toolchain", {}).get("certification_seeds", ())
    )
    baseline_search = tuple(
        sorted(row.get("seed") for row in spec.baseline.get("search_per_seed", []))
    )
    baseline_certification = tuple(
        sorted(
            row.get("seed") for row in spec.baseline.get("certification_per_seed", [])
        )
    )
    if manifest_search != SEARCH_SEEDS or baseline_search != tuple(
        sorted(SEARCH_SEEDS)
    ):
        errors.append("five-seed search baseline or manifest pool is incomplete")
    if (
        manifest_certification != CERTIFICATION_SEEDS
        or baseline_certification != tuple(sorted(CERTIFICATION_SEEDS))
    ):
        errors.append("64-seed certification baseline or manifest pool is incomplete")
    if set(SEARCH_SEEDS) & set(CERTIFICATION_SEEDS):
        errors.append("search and certification seed pools must be disjoint")
    if spec.baseline.get("statistical_baseline", {}).get("status") != "complete":
        errors.append("64-seed statistical baseline is not complete")
    errors.extend(_inspect_docker_image(_docker_image(spec), _expected_image_id(spec)))
    return tuple(errors)


def _last(
    pattern: str, text: str, label: str, cast: type[float] | type[int] = float
) -> float | int:
    matches = re.findall(pattern, text, flags=re.MULTILINE | re.IGNORECASE)
    if not matches:
        raise ValueError(f"missing metric: {label}")
    raw = matches[-1]
    if isinstance(raw, tuple):
        raw = raw[0]
    value = cast(str(raw).strip().rstrip("."))
    if not math.isfinite(float(value)) or float(value) < 0:
        raise ValueError(f"invalid metric {label}: {value}")
    return value


def parse_power_report(path: Path) -> PowerMetrics:
    """Parse the VPR `Total` row and derive dynamic/static components."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if re.search(r"^-+ Errors -+$", text, re.MULTILINE):
        raise ValueError(f"VPR reported power errors in {path.name}")
    match = re.search(
        r"^Total\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s*$",
        text,
        re.MULTILINE,
    )
    if match is None:
        raise ValueError(f"missing VPR Total power row in {path.name}")
    total_w = float(match.group(1))
    dynamic_fraction = float(match.group(3))
    if not (math.isfinite(total_w) and total_w > 0 and 0 <= dynamic_fraction <= 1):
        raise ValueError(f"invalid VPR power values in {path.name}")
    dynamic_w = total_w * dynamic_fraction
    technology = float(
        _last(r"^Technology \(nm\):\s*([^\s]+)", text, "power technology")
    )
    voltage = float(_last(r"^Voltage:\s*([^\s]+)", text, "power voltage"))
    temperature = float(_last(r"^Temperature:\s*([^\s]+)", text, "power temperature"))
    critical_path = float(
        _last(r"^Critical Path:\s*([^\s]+)", text, "power critical path")
    )
    channel = int(_last(r"^Channel Width:\s*(\d+)", text, "power channel width", int))
    if critical_path <= 0 or channel <= 0:
        raise ValueError(f"invalid VPR power operating point in {path.name}")
    warning_match = re.search(
        r"^-+ Warnings -+\s*$\n(.*?)(?=^-+ [A-Za-z ]+ -+\s*$|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    warnings = (
        tuple(
            line.strip() for line in warning_match.group(1).splitlines() if line.strip()
        )
        if warning_match
        else ()
    )
    return PowerMetrics(
        total_w,
        dynamic_w,
        total_w - dynamic_w,
        technology,
        voltage,
        temperature,
        critical_path,
        channel,
        warnings,
    )


def power_warning_fingerprint(metrics: PowerMetrics) -> str:
    """Return a stable fingerprint for the complete ordered power warning set."""
    return hashlib.sha256(
        ("\n".join(metrics.warnings) + ("\n" if metrics.warnings else "")).encode()
    ).hexdigest()


def parse_seed_metrics(
    seed_dir: Path, seed: int, *, cycles: int = 5000, blocks: int = 60
) -> SeedMetrics:
    """Parse routed area/timing and both power profiles from one seed directory."""
    timing_log = (seed_dir / "vpr.crit_path.out").read_text(
        encoding="utf-8", errors="replace"
    )
    if "Circuit successfully routed" not in timing_log:
        raise ValueError("VPR timing route did not report success")
    logic = float(
        _last(r"Total logic block area .*?:\s*([^\s]+)", timing_log, "logic area")
    )
    routing = float(
        _last(r"Total routing area:\s*([^,]+),", timing_log, "routing area")
    )
    delay = float(
        _last(
            r"Final critical path delay \(least slack\):\s*([^\s]+) ns",
            timing_log,
            "delay",
        )
    )
    fmax = float(
        _last(
            r"Final critical path delay \(least slack\):.*Fmax:\s*([^\s]+) MHz",
            timing_log,
            "fmax",
        )
    )
    channel = int(
        _last(
            r"Circuit successfully routed with a channel width factor of (\d+)",
            timing_log,
            "channel",
            int,
        )
    )
    clbs = int(_last(r"Netlist clb blocks:\s*(\d+)\.?", timing_log, "clbs", int))
    registers = int(
        _last(r"^\s+ff\s*:\s*(\d+)\s*$", timing_log, "packed flip-flop count", int)
    )
    memories = int(
        _last(r"Netlist memory blocks:\s*(\d+)\.?", timing_log, "memory blocks", int)
    )
    active = parse_power_report(seed_dir / "active.power")
    idle = parse_power_report(seed_dir / "idle.power")
    for profile, power in (("active", active), ("idle", idle)):
        if (power.technology_nm, power.voltage_v, power.temperature_c) != (
            45.0,
            0.9,
            85.0,
        ):
            raise ValueError(
                f"{profile} power report has the wrong PTM operating point"
            )
        if power.channel_width != channel:
            raise ValueError(
                f"{profile} power report channel width differs from timing route"
            )
        if not math.isclose(
            power.critical_path_s * 1e9, delay, rel_tol=1e-3, abs_tol=1e-4
        ):
            raise ValueError(
                f"{profile} power report critical path differs from timing route"
            )
    energy = active.total_w * float(cycles) * delay / float(blocks)
    values = (logic, routing, delay, fmax, energy, active.total_w, idle.total_w)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError("non-positive or non-finite PPA metric")
    return SeedMetrics(
        seed=seed,
        area_total_mwta=logic + routing,
        logic_block_area_mwta=logic,
        routing_area_mwta=routing,
        critical_path_delay_ns=delay,
        energy_per_block_nj=energy,
        active_total_power_w=active.total_w,
        active_dynamic_power_w=active.dynamic_w,
        active_static_power_w=active.static_w,
        idle_total_power_w=idle.total_w,
        fmax_mhz=fmax,
        clb_blocks=clbs,
        registers=registers,
        memories=memories,
        timing_channel_width=channel,
    )


def summarize(
    metrics: Sequence[SeedMetrics], *, expected_seeds: Sequence[int] = SEARCH_SEEDS
) -> dict[str, MetricSummary]:
    """Aggregate one complete frozen seed pool."""
    expected = tuple(sorted(expected_seeds))
    if tuple(sorted(item.seed for item in metrics)) != expected:
        raise ValueError(f"expected exactly seeds {expected}")
    result: dict[str, MetricSummary] = {}
    for name in PRIMARY_METRICS:
        values = [float(getattr(item, name)) for item in metrics]
        median = statistics.median(values)
        result[name] = MetricSummary(
            median=median,
            worst=max(values),
            minimum=min(values),
            maximum=max(values),
            population_stdev=statistics.pstdev(values),
            relative_range=(max(values) - min(values)) / median,
        )
    return result


def _paired_rows(
    candidate: Sequence[SeedMetrics],
    baseline: Sequence[SeedMetrics],
    expected_seeds: Sequence[int],
) -> tuple[dict[int, SeedMetrics], dict[int, SeedMetrics]]:
    """Validate and index two complete, positive, paired measurement pools."""
    candidate_by_seed = {item.seed: item for item in candidate}
    baseline_by_seed = {item.seed: item for item in baseline}
    expected = tuple(sorted(expected_seeds))
    if (
        tuple(sorted(candidate_by_seed)) != expected
        or tuple(sorted(baseline_by_seed)) != expected
    ):
        raise ValueError(
            f"score requires one candidate and reference result for every frozen seed {expected}"
        )
    for name in PRIMARY_METRICS:
        for seed in expected:
            values = (
                float(getattr(candidate_by_seed[seed], name)),
                float(getattr(baseline_by_seed[seed], name)),
            )
            if any(not math.isfinite(value) or value <= 0 for value in values):
                raise ValueError(
                    f"{name} contains a non-positive or non-finite value at seed {seed}"
                )
    return candidate_by_seed, baseline_by_seed


def _geometric_score(
    candidate: Sequence[SeedMetrics],
    baseline: Sequence[SeedMetrics],
    expected_seeds: Sequence[int],
) -> tuple[float, dict[str, float]]:
    """Return equal-weight PPA geometric means over paired log ratios."""
    candidate_by_seed, baseline_by_seed = _paired_rows(
        candidate, baseline, expected_seeds
    )
    metric_estimates: dict[str, float] = {}
    for name in PRIMARY_METRICS:
        logs = [
            math.log(
                float(getattr(candidate_by_seed[seed], name))
                / float(getattr(baseline_by_seed[seed], name))
            )
            for seed in expected_seeds
        ]
        metric_estimates[name] = math.exp(statistics.mean(logs))
    return math.prod(metric_estimates.values()) ** (1.0 / 3.0), metric_estimates


def search_score(
    candidate: Sequence[SeedMetrics], baseline: Sequence[SeedMetrics]
) -> ScoreAssessment:
    """Rank a proposal on five exposed seeds without making an acceptance claim."""
    score, estimates = _geometric_score(candidate, baseline, SEARCH_SEEDS)
    candidate_by_seed, baseline_by_seed = _paired_rows(
        candidate, baseline, SEARCH_SEEDS
    )
    worst = {
        name: max(
            float(getattr(candidate_by_seed[seed], name))
            / float(getattr(baseline_by_seed[seed], name))
            for seed in SEARCH_SEEDS
        )
        for name in PRIMARY_METRICS
    }
    confidence: dict[str, Any] = {
        "authority": "descriptive_search_only",
        "metrics": {},
    }
    composite_logs: list[float] = []
    for name in PRIMARY_METRICS:
        logs = [
            math.log(
                float(getattr(candidate_by_seed[seed], name))
                / float(getattr(baseline_by_seed[seed], name))
            )
            for seed in SEARCH_SEEDS
        ]
        confidence["metrics"][name] = _search_log_summary(logs)
    for seed in SEARCH_SEEDS:
        composite_logs.append(
            statistics.mean(
                math.log(
                    float(getattr(candidate_by_seed[seed], name))
                    / float(getattr(baseline_by_seed[seed], name))
                )
                for name in PRIMARY_METRICS
            )
        )
    confidence["composite"] = _search_log_summary(composite_logs)
    lower, upper = confidence["composite"]["ci95_two_sided"]
    confidence["fragile_vs_reference"] = lower <= 1.0 <= upper
    confidence["per_seed_composite_ratios"] = [
        math.exp(value) for value in composite_logs
    ]
    return ScoreAssessment(
        True,
        False,
        score,
        estimates,
        worst,
        dict(estimates),
        tuple(name for name, value in estimates.items() if value < 1.0),
        (),
        "search_only",
        confidence,
    )


def _log_summary(
    log_values: Sequence[float], *, t_two_sided_95: float, t_one_sided_95: float
) -> dict[str, float | list[float] | int]:
    """Summarize paired log ratios with caller-declared Student-t quantiles."""
    mean = statistics.mean(log_values)
    stdev = statistics.stdev(log_values)
    standard_error = stdev / math.sqrt(len(log_values))
    return {
        "estimate": math.exp(mean),
        "ci95_two_sided": [
            math.exp(mean - t_two_sided_95 * standard_error),
            math.exp(mean + t_two_sided_95 * standard_error),
        ],
        "lower_one_sided_95": math.exp(mean - t_one_sided_95 * standard_error),
        "upper_one_sided_95": math.exp(mean + t_one_sided_95 * standard_error),
        "log_stdev": stdev,
        "wins": sum(value < 0 for value in log_values),
        "ties": sum(value == 0 for value in log_values),
        "losses": sum(value > 0 for value in log_values),
    }


def _search_log_summary(
    log_values: Sequence[float],
) -> dict[str, float | list[float] | int]:
    """Return descriptive n=5 bounds; these never establish acceptance."""
    if len(log_values) != 5:
        raise ValueError("search uncertainty requires exactly five paired observations")
    return _log_summary(
        log_values,
        t_two_sided_95=2.7764451051977987,
        t_one_sided_95=2.131846786326649,
    )


def _log_confidence(
    log_values: Sequence[float],
) -> dict[str, float | list[float] | int]:
    """Return the predeclared fixed-n=64 Student-t confidence summary."""
    if len(log_values) != 64:
        raise ValueError(
            "certification confidence requires exactly 64 paired observations"
        )
    # Student-t quantiles for df=63.  Keeping these constants in the contract
    # avoids a runtime dependency solely for a frozen sample size.
    return _log_summary(
        log_values,
        t_two_sided_95=1.998340542520741,
        t_one_sided_95=1.6694022217068127,
    )


def score_metrics(
    candidate: Sequence[SeedMetrics], baseline: Sequence[SeedMetrics]
) -> ScoreAssessment:
    """Certify paired PPA evidence on the frozen, disjoint 64-seed pool."""
    candidate_by_seed, baseline_by_seed = _paired_rows(
        candidate, baseline, CERTIFICATION_SEEDS
    )
    confidence: dict[str, Any] = {"metrics": {}}
    composite_logs: list[float] = []
    worst: dict[str, float] = {}
    for name in PRIMARY_METRICS:
        logs = [
            math.log(
                float(getattr(candidate_by_seed[seed], name))
                / float(getattr(baseline_by_seed[seed], name))
            )
            for seed in CERTIFICATION_SEEDS
        ]
        confidence["metrics"][name] = _log_confidence(logs)
        worst[name] = math.exp(max(logs))
    for seed in CERTIFICATION_SEEDS:
        composite_logs.append(
            statistics.mean(
                math.log(
                    float(getattr(candidate_by_seed[seed], name))
                    / float(getattr(baseline_by_seed[seed], name))
                )
                for name in PRIMARY_METRICS
            )
        )
    confidence["composite"] = _log_confidence(composite_logs)
    composite = confidence["composite"]
    metric_summaries = confidence["metrics"]
    if composite["upper_one_sided_95"] < 1.0 and all(
        summary["lower_one_sided_95"] <= 1.0 for summary in metric_summaries.values()
    ):
        decision = "evidence_improvement"
    elif composite["lower_one_sided_95"] > 1.0 or any(
        summary["lower_one_sided_95"] > 1.0 for summary in metric_summaries.values()
    ):
        decision = "evidence_regression"
    else:
        decision = "inconclusive"
    estimates = {
        name: float(summary["estimate"]) for name, summary in metric_summaries.items()
    }
    reasons = (
        tuple(
            f"{name} has one-sided 95% evidence of regression"
            for name, summary in metric_summaries.items()
            if summary["lower_one_sided_95"] > 1.0
        )
        if decision == "evidence_regression"
        else ()
    )
    return ScoreAssessment(
        True,
        decision == "evidence_improvement",
        float(composite["estimate"]),
        estimates,
        worst,
        dict(estimates),
        tuple(name for name, value in estimates.items() if value < 1.0),
        reasons,
        decision,
        confidence,
    )


def baseline_seed_metrics(
    spec: RtlShaVtrSpec, *, tier: str = "search"
) -> tuple[SeedMetrics, ...]:
    """Load the typed baseline rows for one of the two public modes."""
    if tier not in EVALUATION_TIERS:
        raise ValueError(
            f"evaluation tier must be one of {EVALUATION_TIERS}, got {tier!r}"
        )
    key = "search_per_seed" if tier == "search" else "certification_per_seed"
    rows = spec.baseline.get(
        key, spec.baseline.get("per_seed", []) if tier == "search" else []
    )
    return tuple(SeedMetrics(**row) for row in rows)


def _validate_interface(interface_path: Path) -> None:
    payload = json.loads(interface_path.read_text(encoding="utf-8"))
    ports = payload.get("modules", {}).get("sha1", {}).get("ports", {})
    if set(ports) != set(_EXPECTED_INTERFACE):
        raise ValueError(
            f"sha1 interface ports differ: expected {sorted(_EXPECTED_INTERFACE)}, got {sorted(ports)}"
        )
    for name, (direction, width) in _EXPECTED_INTERFACE.items():
        actual = (str(ports[name].get("direction")), len(ports[name].get("bits", [])))
        if actual != (direction, width):
            raise ValueError(
                f"sha1 port {name} must be {direction}[{width}], got {actual[0]}[{actual[1]}]"
            )


class RtlShaVtrEvaluator:
    """Generator-neutral candidate evaluator; only `sha.v` is supplied by the generator."""

    def __init__(
        self,
        spec: RtlShaVtrSpec | None = None,
        runner: DomainRunner | None = None,
        *,
        tier: str = "search",
    ) -> None:
        """Use the frozen specification and production runner unless injected."""
        if tier not in EVALUATION_TIERS:
            raise ValueError(
                f"evaluation tier must be one of {EVALUATION_TIERS}, got {tier!r}"
            )
        self.spec = spec or build_default_domain()
        if runner is None:
            from .runner import DockerPpa45Runner

            runner = DockerPpa45Runner(self.spec)
        self.runner = runner
        self.tier = tier

    def _invalid(
        self, candidate_id: str, status: str, diagnostics: Sequence[str], **trace: Any
    ) -> EvaluationResult:
        return EvaluationResult(
            score=math.inf,
            metrics={
                "score": math.inf,
                "functional_pass": 0.0,
                "formal_pass": 0.0,
                "area_total_mwta": math.inf,
                "critical_path_delay_ns": math.inf,
                "energy_per_block_nj": math.inf,
                "accepted_improvement": 0.0,
            },
            valid=False,
            candidate_id=candidate_id,
            trace={
                "status": status,
                "evaluation_tier": self.tier,
                "certified": False,
                "accepted_improvement": False,
                "acceptance_decision": False if self.tier == "certification" else None,
                "diagnostics": list(diagnostics),
                **trace,
            },
            baseline_score=1.0,
            notes="Candidate failed a mandatory SHA-1/VTR contract gate.",
        )

    def evaluate_workspace(
        self,
        workspace: Path,
        *,
        candidate_id: str,
        evidence_dir: Path | None = None,
    ) -> EvaluationResult:
        """Apply hard gates and either proxy or certification-grade PPA scoring."""
        diagnostics = preflight(workspace, self.spec)
        if self.tier == "certification" and evidence_dir is None:
            diagnostics = (
                *diagnostics,
                "64-seed certification requires a persistent evidence directory",
            )
        if diagnostics:
            return self._invalid(candidate_id, "blocked_prerequisites", diagnostics)
        candidate = candidate_path(workspace)
        candidate_hash = sha256_file(candidate)
        temporary: tempfile.TemporaryDirectory[str] | None = None
        if evidence_dir is None:
            temporary = tempfile.TemporaryDirectory(prefix="rtl_sha_vtr_")
            results_dir = Path(temporary.name)
        else:
            results_dir = Path(evidence_dir)
            if results_dir.exists() and any(results_dir.iterdir()):
                return self._invalid(
                    candidate_id,
                    "evidence_integrity",
                    ["evidence directory must be new or empty"],
                    candidate_sha256=candidate_hash,
                )
            results_dir.mkdir(parents=True, exist_ok=True)
        try:
            try:
                measured, evidence = self.runner.run(
                    candidate, results_dir, tier=self.tier
                )
            except RunnerFailure as exc:
                failure_hashes = {
                    str(path.relative_to(results_dir)): sha256_file(path)
                    for path in results_dir.rglob("*")
                    if path.is_file() and path.stat().st_size <= 50_000_000
                }
                return self._invalid(
                    candidate_id,
                    exc.stage,
                    [str(exc)],
                    candidate_sha256=candidate_hash,
                    stdout_tail=exc.stdout_tail,
                    stderr_tail=exc.stderr_tail,
                    evidence={
                        "persisted": evidence_dir is not None,
                        "root": (
                            str(results_dir.resolve())
                            if evidence_dir is not None
                            else None
                        ),
                        "hashes": failure_hashes,
                    },
                )
        finally:
            if temporary is not None:
                temporary.cleanup()
        evidence = {
            **evidence,
            "persisted": evidence_dir is not None,
            "root": str(results_dir.resolve()) if evidence_dir is not None else None,
        }
        baseline = baseline_seed_metrics(self.spec, tier=self.tier)
        if self.tier == "search":
            try:
                assessment = search_score(tuple(measured), baseline)
                aggregate = summarize(tuple(measured), expected_seeds=SEARCH_SEEDS)
            except (TypeError, ValueError, ZeroDivisionError) as exc:
                return self._invalid(
                    candidate_id,
                    "score_integrity",
                    [str(exc)],
                    candidate_sha256=candidate_hash,
                )
            delay = aggregate["critical_path_delay_ns"].median

            def median(name: str) -> float:
                return statistics.median(
                    float(getattr(item, name)) for item in measured
                )

            metrics = {
                "score": assessment.score,
                "functional_pass": 1.0,
                "formal_pass": 1.0,
                "area_total_mwta": aggregate["area_total_mwta"].median,
                "critical_path_delay_ns": delay,
                "energy_per_block_nj": aggregate["energy_per_block_nj"].median,
                "accepted_improvement": 0.0,
                "fmax_mhz": median("fmax_mhz"),
                "busy_cycles_per_block": 80.0,
                "initiation_interval_cycles": 83.0,
                "throughput_mblocks_per_s": 1000.0 / (83.0 * delay),
                "clb_blocks": median("clb_blocks"),
                "registers": median("registers"),
                "memories": median("memories"),
                "timing_channel_width": median("timing_channel_width"),
                "active_total_power_w": median("active_total_power_w"),
                "active_dynamic_power_w": median("active_dynamic_power_w"),
                "active_static_power_w": median("active_static_power_w"),
                "idle_total_power_w": median("idle_total_power_w"),
            }
            return EvaluationResult(
                score=assessment.score,
                metrics=metrics,
                valid=True,
                candidate_id=candidate_id,
                baseline_score=1.0,
                trace={
                    "status": "valid_search_score",
                    "evaluation_tier": "search",
                    "evidence_level": "five_seed_search",
                    "certified": False,
                    "accepted_improvement": False,
                    "acceptance_decision": None,
                    "acceptance_note": "Five exposed seeds guide search only; certification requires 64 disjoint seeds.",
                    "candidate_sha256": candidate_hash,
                    "golden_seed_sha256": self.spec.manifest["source"][
                        "golden_seed_sha256"
                    ],
                    "proxy_ratios": assessment.median_ratios,
                    "descriptive_uncertainty": assessment.confidence,
                    "per_seed": [asdict(item) for item in measured],
                    "aggregate": {
                        name: asdict(value) for name, value in aggregate.items()
                    },
                    "evidence": evidence,
                },
                notes="Provisional five-seed open-FPGA search score; not certification or signoff.",
            )

        try:
            assessment = score_metrics(tuple(measured), baseline)
            aggregate = summarize(tuple(measured), expected_seeds=CERTIFICATION_SEEDS)
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            return self._invalid(
                candidate_id,
                "score_integrity",
                [str(exc)],
                candidate_sha256=candidate_hash,
            )

        def median(name: str) -> float:
            return statistics.median(float(getattr(item, name)) for item in measured)

        delay_median = aggregate["critical_path_delay_ns"].median
        metrics = {
            "score": assessment.score,
            "functional_pass": 1.0,
            "formal_pass": 1.0,
            "area_total_mwta": aggregate["area_total_mwta"].median,
            "critical_path_delay_ns": aggregate["critical_path_delay_ns"].median,
            "energy_per_block_nj": aggregate["energy_per_block_nj"].median,
            "accepted_improvement": float(assessment.accepted_improvement),
            "fmax_mhz": median("fmax_mhz"),
            "busy_cycles_per_block": 80.0,
            "initiation_interval_cycles": 83.0,
            "throughput_mblocks_per_s": 1000.0 / (83.0 * delay_median),
            "clb_blocks": median("clb_blocks"),
            "registers": median("registers"),
            "memories": median("memories"),
            "timing_channel_width": median("timing_channel_width"),
            "active_total_power_w": median("active_total_power_w"),
            "active_dynamic_power_w": median("active_dynamic_power_w"),
            "active_static_power_w": median("active_static_power_w"),
            "idle_total_power_w": median("idle_total_power_w"),
        }
        status = assessment.decision
        return EvaluationResult(
            score=assessment.score,
            metrics=metrics,
            valid=assessment.valid,
            candidate_id=candidate_id,
            baseline_score=1.0,
            trace={
                "status": status,
                "evaluation_tier": "certification",
                "evidence_level": "fixed_64_seed_certification",
                "certified": True,
                "accepted_improvement": assessment.accepted_improvement,
                "acceptance_decision": assessment.accepted_improvement,
                "candidate_sha256": candidate_hash,
                "golden_seed_sha256": self.spec.manifest["source"][
                    "golden_seed_sha256"
                ],
                "ratio_estimates": assessment.median_ratios,
                "worst_observed_ratios": assessment.worst_ratios,
                "pareto_coordinates": {
                    name: aggregate[name].median for name in PRIMARY_METRICS
                },
                "improved_metrics": assessment.improved_metrics,
                "rejection_reasons": assessment.rejection_reasons,
                "statistical_confidence": assessment.confidence,
                "per_seed": [asdict(item) for item in measured],
                "aggregate": {name: asdict(value) for name, value in aggregate.items()},
                "evidence": evidence,
            },
            notes="Open 45 nm FPGA estimate; not commercial FPGA, silicon, ASIC, or signoff.",
        )
