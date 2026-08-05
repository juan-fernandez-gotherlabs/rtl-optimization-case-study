"""Networkless, resource-bounded Linux/amd64 runner for the SHA PPA contract."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
import uuid
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .activity_vectors import canonical_blif_sha256, write_vectors
from .evaluator import (
    BENCHMARK_DIR,
    CERTIFICATION_SEEDS,
    EVALUATION_TIERS,
    SEARCH_SEEDS,
    RtlShaVtrSpec,
    RunnerFailure,
    SeedMetrics,
    _docker_image,
    _tail,
    _validate_interface,
    parse_power_report,
    parse_seed_metrics,
    power_warning_fingerprint,
    sha256_file,
)
from .generate_nist_corpus import (
    monte_carlo_cases,
    parse_response_file,
    write_block_corpus,
)
from .sbom import generate_sbom


def parse_mutation_status(status: str) -> dict[str, int | float]:
    """Parse and validate the complete structure-preserving MCY accounting."""

    def count(label: str) -> int:
        match = re.search(rf"^{re.escape(label)}: (\d+)$", status, re.MULTILINE)
        if match is None:
            raise RunnerFailure("mutation_coverage", f"missing {label!r} in MCY status")
        return int(match.group(1))

    if not re.search(
        r"^Combined verification coverage: 100\.000000%$", status, re.MULTILINE
    ):
        raise RunnerFailure(
            "mutation_coverage", "combined MCY coverage is not exactly 100%"
        )
    simulation_detected = count("Simulation-detected mutations")
    formal_only = count("Formal-only rejected mutations")
    equivalent = count("Equivalent mutations")
    inconclusive = count("Inconclusive mutations")
    if inconclusive:
        raise RunnerFailure(
            "mutation_coverage", f"MCY produced {inconclusive} inconclusive mutations"
        )
    if simulation_detected + formal_only + equivalent != 500:
        raise RunnerFailure(
            "mutation_coverage",
            "MCY classification does not account for all 500 mutations",
        )
    rejected = simulation_detected + formal_only
    if rejected == 0:
        raise RunnerFailure(
            "mutation_coverage", "MCY produced no contract-rejected mutations"
        )
    return {
        "mutation_count": 500,
        "coverage_percent": 100.0,
        "contract_rejected_mutations": rejected,
        "simulation_detected_mutations": simulation_detected,
        "formal_only_rejected_mutations": formal_only,
        "equivalent_mutations": equivalent,
        "simulation_only_coverage_percent": 100.0 * simulation_detected / rejected,
    }


class DockerPpa45Runner:
    """Run functional gates and one of the two frozen paired PPA pools."""

    def __init__(self, spec: RtlShaVtrSpec) -> None:
        """Freeze the image tag and runtime resource limits."""
        self.spec = spec
        self.image = _docker_image(spec)
        self.cpu_limit = 2
        self.memory_limit = "7g"
        self.seed_workers = 2

    def _docker_command(
        self,
        mounts: Sequence[tuple[Path, str, bool]],
        script: str,
        *,
        container_name: str | None = None,
    ) -> list[str]:
        command = [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "--cpus",
            str(self.cpu_limit),
            "--memory",
            self.memory_limit,
            "--memory-swap",
            self.memory_limit,
            "--network",
            "none",
            "--pids-limit",
            "512",
            "--security-opt",
            "no-new-privileges",
        ]
        if container_name:
            command.extend(["--name", container_name])
        for host, container, read_only in mounts:
            command.extend(
                [
                    "--volume",
                    f"{host.resolve()}:{container}{':ro' if read_only else ''}",
                ]
            )
        command.extend([self.image, "bash", "-lc", script])
        return command

    def _run_stage(
        self,
        stage: str,
        results: Path,
        mounts: Sequence[tuple[Path, str, bool]],
        script: str,
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        logs = results / "stage_logs"
        logs.mkdir(parents=True, exist_ok=True)
        safe_stage = re.sub(r"[^a-z0-9_.-]", "-", stage.lower())
        container_name = f"rtl-sha-vtr-{safe_stage}-{uuid.uuid4().hex[:12]}"
        command = self._docker_command(mounts, script, container_name=container_name)
        (logs / f"{stage}.command.json").write_text(
            json.dumps(command, indent=2) + "\n", encoding="utf-8"
        )
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command, capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired as exc:
            self._stop_container(container_name, logs, stage)
            (logs / f"{stage}.elapsed_seconds").write_text(
                f"{time.monotonic() - started:.6f}\n", encoding="ascii"
            )
            raise RunnerFailure(stage, f"{stage} exceeded {timeout} seconds") from exc
        except KeyboardInterrupt as exc:
            self._stop_container(container_name, logs, stage)
            (logs / f"{stage}.elapsed_seconds").write_text(
                f"{time.monotonic() - started:.6f}\n", encoding="ascii"
            )
            raise RunnerFailure(
                stage, f"{stage} was interrupted; its Docker container was stopped"
            ) from exc
        except OSError as exc:
            raise RunnerFailure(
                stage, f"could not start Docker for {stage}: {exc.__class__.__name__}"
            ) from exc
        (logs / f"{stage}.stdout.log").write_text(completed.stdout, encoding="utf-8")
        (logs / f"{stage}.stderr.log").write_text(completed.stderr, encoding="utf-8")
        (logs / f"{stage}.elapsed_seconds").write_text(
            f"{time.monotonic() - started:.6f}\n", encoding="ascii"
        )
        if completed.returncode:
            raise RunnerFailure(
                stage,
                f"{stage} exited with status {completed.returncode}",
                stdout=completed.stdout,
                stderr=completed.stderr,
            )
        return completed

    @staticmethod
    def _stop_container(container_name: str, logs: Path, stage: str) -> None:
        """Best-effort cleanup that also preserves the Docker diagnostic."""
        try:
            stopped = subprocess.run(
                ["docker", "stop", "--timeout", "10", container_name],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            diagnostic = f"returncode={stopped.returncode}\nstdout={stopped.stdout}\nstderr={stopped.stderr}"
        except (OSError, subprocess.TimeoutExpired) as exc:
            diagnostic = f"cleanup_error={exc.__class__.__name__}\n"
        (logs / f"{stage}.container_cleanup.log").write_text(
            diagnostic, encoding="utf-8"
        )

    def _common_mounts(
        self, candidate: Path, results: Path
    ) -> list[tuple[Path, str, bool]]:
        return [
            (candidate, "/candidate/sha.v", True),
            (BENCHMARK_DIR, "/contract", True),
            (results, "/results", False),
        ]

    def collect_environment(self, candidate: Path, results: Path) -> dict[str, Any]:
        """Persist executable versions plus OS and Python package inventories."""
        manifest = self.spec.manifest
        script = f"""
set -euo pipefail
{{
  echo "vtr_commit=$(git rev-parse HEAD)"
  echo "platform=$(uname -srm)"
  yosys -V
  vpr --version
  verilator --version
  eqy --version
  mcy --help | head -1
  sha256sum {manifest["fpga_architecture"]["vtr_path"]} {manifest["fpga_architecture"]["technology_path"]}
}} > /results/tool_versions.log
cp /workspace/dpkg-manifest.tsv /results/dpkg-manifest.tsv
cp /workspace/vtr-submodules.txt /results/vtr-submodules.txt
cp /workspace/requirements-ppa45-linux-amd64.lock /results/requirements-ppa45-linux-amd64.lock
cp -a /workspace/third-party-licenses /results/third-party-licenses
if test -f /workspace/pip-manifest.txt; then
  cp /workspace/pip-manifest.txt /results/pip-manifest.txt
else
  /workspace/.venv/bin/pip freeze --all | LC_ALL=C sort > /results/pip-manifest.txt
fi
"""
        self._run_stage(
            "environment_inventory",
            results,
            self._common_mounts(candidate, results),
            script,
            timeout=60,
        )
        sbom = generate_sbom(
            results / "dpkg-manifest.tsv",
            results / "pip-manifest.txt",
            results / "cyclonedx-sbom.json",
        )
        return {
            "tool_versions_sha256": sha256_file(results / "tool_versions.log"),
            "dpkg_manifest_sha256": sha256_file(results / "dpkg-manifest.tsv"),
            "vtr_submodules_sha256": sha256_file(results / "vtr-submodules.txt"),
            "pip_manifest_sha256": sha256_file(results / "pip-manifest.txt"),
            "python_lock_sha256": sha256_file(
                results / "requirements-ppa45-linux-amd64.lock"
            ),
            "cyclonedx_sbom_sha256": sha256_file(results / "cyclonedx-sbom.json"),
            "license_manifest_sha256": sha256_file(
                results / "third-party-licenses" / "license-manifest.sha256"
            ),
            "debian_package_copyrights_sha256": sha256_file(
                results / "third-party-licenses" / "debian-package-copyrights.tar.gz"
            ),
            "component_count": len(sbom["components"]),
        }

    def run_candidate_correctness(
        self, candidate: Path, results: Path
    ) -> dict[str, Any]:
        """Run structural, representative simulation and unbounded formal candidate gates."""
        manifest = self.spec.manifest
        source = manifest["source"]
        commit = manifest["toolchain"]["vtr_commit"]
        script = f"""
set -euo pipefail
test "$(git rev-parse HEAD)" = "{commit}"
test "$(sha256sum vtr_flow/benchmarks/verilog/sha.v | cut -d' ' -f1)" = "{source["upstream_sha256"]}"
cp vtr_flow/benchmarks/verilog/sha.v /results/sha1_gold.v
patch --silent /results/sha1_gold.v /contract/{source["conformance_patch"]}
test "$(sha256sum /results/sha1_gold.v | cut -d' ' -f1)" = "{source["golden_seed_sha256"]}"
sed '0,/module sha1 (/s//module sha1_reference (/' /results/sha1_gold.v > /results/sha1_reference.v

/usr/bin/time -v -o /results/interface_lint.time \
  yosys -q -p 'read_verilog /candidate/sha.v; hierarchy -check -top sha1; proc; \
    check -assert; write_json /results/interface.json' \
  > /results/interface_lint.log 2>&1
/usr/bin/time -v -o /results/verilator_lint.time \
  verilator --lint-only -Wall -Wno-DECLFILENAME /candidate/sha.v \
  > /results/verilator_lint.log 2>&1

/usr/bin/time -v -o /results/abc_compile.time \
  verilator --binary --timing -Wall -Wno-fatal --top-module sha1_abc_tb \
  --Mdir /tmp/abc_obj /candidate/sha.v /contract/sha1_abc_tb.v \
  > /results/abc_compile.log 2>&1
/usr/bin/time -v -o /results/abc_run.time /tmp/abc_obj/Vsha1_abc_tb \
  > /results/abc_run.log 2>&1
grep -q '^SHA1_ABC_KAT_PASS digest=a9993e364706816aba3e25717850c26c9cd0d89d busy_cycles=' /results/abc_run.log

/usr/bin/time -v -o /results/cycle_compile.time \
  verilator --binary --timing -Wall -Wno-fatal --top-module sha1_equivalence_tb \
  --Mdir /tmp/cycle_obj /candidate/sha.v /results/sha1_reference.v /contract/sha1_equivalence_tb.v \
  > /results/cycle_compile.log 2>&1
/usr/bin/time -v -o /results/cycle_run.time /tmp/cycle_obj/Vsha1_equivalence_tb \
  > /results/cycle_run.log 2>&1
grep -q '^SHA_VTR_EQUIVALENCE_CONTRACT_PASS cases=16 checks=' /results/cycle_run.log

cd /results
/usr/bin/time -v -o formal.time timeout --signal=TERM --kill-after=15s 600s \
  eqy -f /contract/sha1_cycle.eqy > formal_driver.log 2>&1
grep -q 'Successfully proved designs equivalent' formal_driver.log
"""
        completed = self._run_stage(
            "candidate_correctness",
            results,
            self._common_mounts(candidate, results),
            script,
            timeout=660,
        )
        try:
            _validate_interface(results / "interface.json")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RunnerFailure("interface_contract", str(exc)) from exc
        abc_log = (results / "abc_run.log").read_text(
            encoding="utf-8", errors="replace"
        )
        busy_match = re.search(r"busy_cycles=(\d+)", abc_log)
        if busy_match is None or int(busy_match.group(1)) != 80:
            raise RunnerFailure(
                "latency_contract",
                "corrected seed does not report exactly 80 busy cycles",
            )
        return {
            "busy_cycles_per_block": 80,
            "golden_seed_sha256": sha256_file(results / "sha1_gold.v"),
            "stdout_tail": _tail(completed.stdout),
            "stderr_tail": _tail(completed.stderr),
        }

    def run_nist_short_long(self, candidate: Path, results: Path) -> dict[str, Any]:
        """Run the 129 official NIST Short/Long vectors for qualification or certification."""
        short = parse_response_file(BENCHMARK_DIR / "nist_shavs" / "SHA1ShortMsg.rsp")
        long = parse_response_file(BENCHMARK_DIR / "nist_shavs" / "SHA1LongMsg.rsp")
        cases = short + long
        corpus = results / "nist_short_long.corpus"
        write_block_corpus(cases, corpus)
        script = """
set -euo pipefail
/usr/bin/time -v -o /results/nist_compile.time \
  verilator --binary --timing -Wall -Wno-fatal --top-module sha1_nist_tb \
  --Mdir /tmp/nist_obj /candidate/sha.v /contract/sha1_nist_tb.sv \
  > /results/nist_compile.log 2>&1
/usr/bin/time -v -o /results/nist_run.time /tmp/nist_obj/Vsha1_nist_tb +CORPUS=/results/nist_short_long.corpus \
  > /results/nist_run.log 2>&1
grep -q '^SHA1_NIST_SHAVS_PASS cases=129$' /results/nist_run.log
"""
        self._run_stage(
            "nist_short_long",
            results,
            self._common_mounts(candidate, results),
            script,
            timeout=180,
        )
        return {"short_long_cases": len(cases), "corpus_sha256": sha256_file(corpus)}

    def run_certification_vectors(
        self, candidate: Path, results: Path
    ) -> dict[str, Any]:
        """Prove the upstream defect and run all 100,000 NIST Monte Carlo hashes."""
        monte = results / "nist_monte.corpus"
        cases = monte_carlo_cases(BENCHMARK_DIR / "nist_shavs" / "SHA1Monte.rsp")
        write_block_corpus(cases, monte)
        source = self.spec.manifest["source"]
        script = f"""
set -euo pipefail
cp vtr_flow/benchmarks/verilog/sha.v /tmp/upstream.v
set +e
verilator --binary --timing -Wall -Wno-fatal --top-module sha1_abc_tb \
  --Mdir /tmp/upstream_obj /tmp/upstream.v /contract/sha1_abc_tb.v > /results/upstream_compile.log 2>&1
compile_status=$?
if [[ $compile_status -eq 0 ]]; then
  /tmp/upstream_obj/Vsha1_abc_tb > /results/upstream_abc.log 2>&1
  upstream_status=$?
else
  upstream_status=$compile_status
fi
set -e
test $upstream_status -ne 0
test $compile_status -eq 0
! grep -q '^SHA1_ABC_KAT_PASS' /results/upstream_abc.log

/usr/bin/time -v -o /results/monte_compile.time \
  verilator --binary --timing -Wall -Wno-fatal --top-module sha1_nist_tb \
  --Mdir /tmp/monte_obj /candidate/sha.v /contract/sha1_nist_tb.sv \
  > /results/monte_compile.log 2>&1
/usr/bin/time -v -o /results/monte_run.time /tmp/monte_obj/Vsha1_nist_tb +CORPUS=/results/nist_monte.corpus \
  > /results/monte_run.log 2>&1
grep -q '^SHA1_NIST_SHAVS_PASS cases=100000$' /results/monte_run.log
test "$(sha256sum /candidate/sha.v | cut -d' ' -f1)" = "{source["golden_seed_sha256"]}"
"""
        self._run_stage(
            "certification_vectors",
            results,
            self._common_mounts(candidate, results),
            script,
            timeout=300,
        )
        return {
            "upstream_abc_expected_failure": True,
            "monte_carlo_hashes": len(cases),
            "monte_corpus_sha256": sha256_file(monte),
        }

    def run_mutation(self, candidate: Path, results: Path) -> dict[str, Any]:
        """Require 100% combined rejection coverage of 500 deterministic mutations.

        Simulation and the structure-aware EQY gate are both part of the pilot
        verification stack.  The report preserves their separate contribution;
        a timeout or tool error remains inconclusive and fails qualification.
        """
        project = results / "mutation"
        project.mkdir(parents=True, exist_ok=True)
        frozen = Path(__file__).resolve().parent / "mutation"
        for name in ("config.mcy", "test_formal.sh", "test_functional.sh"):
            shutil.copy2(frozen / name, project / name)
        shutil.copy2(candidate, project / "sha.v")
        shutil.copy2(results / "sha1_gold.v", project / "sha1_gold.v")
        shutil.copy2(results / "sha1_reference.v", project / "sha1_reference.v")
        shutil.copy2(BENCHMARK_DIR / "sha1_nist_tb.sv", project / "sha1_nist_tb.sv")
        shutil.copy2(
            BENCHMARK_DIR / "sha1_equivalence_tb.v", project / "sha1_equivalence_tb.v"
        )
        shutil.copy2(
            results / "nist_short_long.corpus", project / "nist_short_long.corpus"
        )
        script = """
set -euo pipefail
cd /results/mutation
chmod 0555 test_formal.sh test_functional.sh
/usr/bin/time -v -o init.time mcy init > init.log 2>&1
/usr/bin/time -v -o run.time timeout --signal=TERM --kill-after=30s 10800s mcy run -j2 > run.log 2>&1
mcy status > status.log 2>&1
grep -q '^Combined verification coverage: 100.000000%$' status.log
grep -q '^Inconclusive mutations: 0$' status.log
mcy list > mutations.list
test "$(wc -l < mutations.list)" -eq 500
! grep -q ' INCONCLUSIVE' mutations.list
"""
        self._run_stage(
            "mutation_coverage",
            results,
            self._common_mounts(candidate, results),
            script,
            timeout=10860,
        )
        status = (project / "status.log").read_text(encoding="utf-8", errors="replace")
        return {**parse_mutation_status(status), "status_report": status}

    def prepare_activity(self, candidate: Path, results: Path) -> dict[str, Any]:
        """Synthesize through ABC once, then freeze exact-order 5,000-cycle vectors."""
        setup = results / "activity_setup"
        setup.mkdir(parents=True, exist_ok=True)
        manifest = self.spec.manifest
        arch = manifest["fpga_architecture"]
        script = rf"""
set -euo pipefail
test "$(sha256sum {arch["vtr_path"]} | cut -d' ' -f1)" = "{arch["sha256"]}"
.venv/bin/python vtr_flow/scripts/run_vtr_flow.py \
  /candidate/sha.v {arch["vtr_path"]} \
  -temp_dir /results/activity_setup -ending_stage abc \
  -track_memory_usage true -limit_memory_usage 6500 \
  -timeout 240 -show_failures > /results/activity_setup_driver.log 2>&1
test -s /results/activity_setup/sha.abc.blif
"""
        self._run_stage(
            "activity_synthesis",
            results,
            self._common_mounts(candidate, results),
            script,
            timeout=300,
        )
        active = results / "active.vec"
        idle = results / "idle.vec"
        blocks = write_vectors(setup / "sha.abc.blif", "active", active)
        write_vectors(setup / "sha.abc.blif", "idle", idle)
        if blocks != 60:
            raise RunnerFailure(
                "activity_integrity", f"expected 60 complete blocks, got {blocks}"
            )
        return {
            "synthesized_blif_sha256": canonical_blif_sha256(setup / "sha.abc.blif"),
            "synthesized_blif_raw_sha256": sha256_file(setup / "sha.abc.blif"),
            "synthesized_blif_hash_basis": "all bytes except the first ABC timestamp comment",
            "active_vector_sha256": sha256_file(active),
            "idle_vector_sha256": sha256_file(idle),
            "cycles": 5000,
            "active_completed_blocks": blocks,
        }

    def run_seed(
        self, candidate: Path, results: Path, seed: int, *, run_label: str | None = None
    ) -> SeedMetrics:
        """Route once with active power, then reuse that route for idle analysis.

        ``run_label`` isolates disposable/preflight measurements from certified
        seed directories.  A certified rerun therefore cannot consume or
        overwrite any artifact produced by the preflight.
        """
        directory_name = f"{run_label}_seed_{seed}" if run_label else f"seed_{seed}"
        seed_dir = results / directory_name
        seed_dir.mkdir(parents=True, exist_ok=True)
        manifest = self.spec.manifest
        arch = manifest["fpga_architecture"]
        mounts = self._common_mounts(candidate, results) + [
            (results / "active.vec", "/inputs/active.vec", True),
            (results / "idle.vec", "/inputs/idle.vec", True),
        ]
        script = rf"""
set -euo pipefail
test "$(sha256sum {arch["vtr_path"]} | cut -d' ' -f1)" = "{arch["sha256"]}"
test "$(sha256sum {arch["technology_path"]} | cut -d' ' -f1)" = "{arch["technology_sha256"]}"
/usr/bin/time -v -o /results/{directory_name}/flow.time \
  .venv/bin/python vtr_flow/scripts/run_vtr_flow.py \
  /candidate/sha.v {arch["vtr_path"]} \
  -temp_dir /results/{directory_name} -cmos_tech {arch["technology_path"]} \
  -track_memory_usage true -limit_memory_usage 6500 \
  -timeout 720 -show_failures --seed {seed} \
  > /results/{directory_name}/flow_driver.log 2>&1
cd /results/{directory_name}
test -s sha.abc.blif
cmp <(sed '1{{/^# Benchmark .* written by ABC on /d;}}' sha.abc.blif) \
  <(sed '1{{/^# Benchmark .* written by ABC on /d;}}' /results/activity_setup/sha.abc.blif)
test -s sha.power
cp sha.power active.power
channel=$(sed -n \
  's/.*Circuit successfully routed with a channel width factor of \([0-9][0-9]*\).*/\1/p' \
  vpr.crit_path.out | tail -1)
test -n "$channel"
/workspace/build/ace2/ace -b sha.abc.blif -c clk_i -n idle.raw.ace.blif -o idle.act -v /inputs/idle.vec \
  > idle_ace.log 2>&1
awk 'NF {{print $1}}' sha.act | LC_ALL=C sort > active_activity_names.txt
awk 'NF {{print $1}}' idle.act | LC_ALL=C sort > idle_activity_names.txt
cmp active_activity_names.txt idle_activity_names.txt
sha256sum sha.net sha.place sha.route > routed_before.sha256
cp sha.net active_sha.net
cp sha.place active_sha.place
cp sha.route active_sha.route
/usr/bin/time -v -o idle_power.time \
  /workspace/build/vpr/vpr /workspace/{arch["vtr_path"]} sha \
  --circuit_file sha.pre-vpr.blif --analysis \
  --route_chan_width "$channel" --seed {seed} --power \
  --tech_properties /workspace/{arch["technology_path"]} --activity_file idle.act \
  > idle_vpr.log 2>&1
sha256sum -c routed_before.sha256
cmp sha.net active_sha.net
cmp sha.place active_sha.place
cmp sha.route active_sha.route
cp sha.power idle.power
test -s idle.power
grep -q '^Total' active.power
grep -q '^Total' idle.power
"""
        self._run_stage(f"ppa_seed_{seed}", results, mounts, script, timeout=900)
        try:
            metrics = parse_seed_metrics(seed_dir, seed)
        except (OSError, ValueError) as exc:
            raise RunnerFailure("metric_integrity", f"seed {seed}: {exc}") from exc
        warning_fingerprints = {
            "active": power_warning_fingerprint(
                parse_power_report(seed_dir / "active.power")
            ),
            "idle": power_warning_fingerprint(
                parse_power_report(seed_dir / "idle.power")
            ),
        }
        (seed_dir / "power_warning_fingerprints.json").write_text(
            json.dumps(warning_fingerprints, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        expected = self.spec.baseline.get("power_warning_fingerprints", {}).get(
            str(seed)
        )
        if (
            self.spec.baseline.get("status") == "success"
            and warning_fingerprints != expected
        ):
            raise RunnerFailure(
                "power_warning_policy",
                f"seed {seed} power warnings differ from the baseline allowlist",
            )
        return metrics

    def run_seed_pool(
        self, candidate: Path, results_dir: Path, seeds: Sequence[int]
    ) -> tuple[SeedMetrics, ...]:
        """Measure a frozen seed pool with two globally bounded workers."""
        original_cpu, original_memory = self.cpu_limit, self.memory_limit
        self.cpu_limit, self.memory_limit = 1, "3g"
        try:
            measured_by_seed: dict[int, SeedMetrics] = {}
            with ThreadPoolExecutor(max_workers=self.seed_workers) as pool:
                futures = {
                    pool.submit(self.run_seed, candidate, results_dir, seed): seed
                    for seed in seeds
                }
                for future in as_completed(futures):
                    seed = futures[future]
                    measured_by_seed[seed] = future.result()
            return tuple(measured_by_seed[seed] for seed in seeds)
        finally:
            self.cpu_limit, self.memory_limit = original_cpu, original_memory

    def run(
        self, candidate: Path, results_dir: Path, *, tier: str = "search"
    ) -> tuple[Sequence[SeedMetrics], dict[str, Any]]:
        """Run five search seeds or the disjoint 64-seed certification pool."""
        if tier not in EVALUATION_TIERS:
            raise ValueError(
                f"evaluation tier must be one of {EVALUATION_TIERS}, got {tier!r}"
            )
        results_dir.mkdir(parents=True, exist_ok=True)
        correctness = self.run_candidate_correctness(candidate, results_dir)
        nist = (
            self.run_nist_short_long(candidate, results_dir)
            if tier == "certification"
            else None
        )
        activity = self.prepare_activity(candidate, results_dir)
        seeds = CERTIFICATION_SEEDS if tier == "certification" else SEARCH_SEEDS
        # Two one-CPU/3-GB workers remain below the domain-wide 2-CPU/7-GB
        # envelope while making the fixed seed pools practical on a 16-GB Mac.
        measured = self.run_seed_pool(candidate, results_dir, seeds)
        evidence_files = [
            path
            for path in results_dir.rglob("*")
            if path.is_file() and path.stat().st_size <= 50_000_000
        ]
        hashes = {
            str(path.relative_to(results_dir)): sha256_file(path)
            for path in evidence_files
        }
        return measured, {
            "evaluation_tier": tier,
            "correctness": correctness,
            "nist_short_long": nist,
            "activity": activity,
            "seeds": list(seeds),
            "seed_workers": self.seed_workers,
            "hashes": hashes,
        }
