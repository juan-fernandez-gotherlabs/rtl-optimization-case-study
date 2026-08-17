from __future__ import annotations

import difflib
import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY_SPEC = importlib.util.spec_from_file_location("sha1_public_verify", ROOT / "verify.py")
assert VERIFY_SPEC is not None and VERIFY_SPEC.loader is not None
public_verify = importlib.util.module_from_spec(VERIFY_SPEC)
VERIFY_SPEC.loader.exec_module(public_verify)


def write_manifest(root: Path) -> None:
    paths = []
    for line in (root / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        if line:
            paths.append(line.split("  ", 1)[1])
    payload = "".join(
        f"{hashlib.sha256((root / relative).read_bytes()).hexdigest()}  {relative}\n"
        for relative in sorted(paths)
    )
    (root / "SHA256SUMS").write_text(payload, encoding="utf-8")


class VerifyAdversarialTests(unittest.TestCase):
    def copy(self) -> Path:
        temporary = Path(tempfile.mkdtemp(prefix="rtl-verify-test-"))
        self.addCleanup(shutil.rmtree, temporary)
        for name in ("Makefile", "README.md", "SHA256SUMS", "report", "results", "rtl", "scripts", "technical-report.pdf", "tests", "verify.py"):
            source = ROOT / name
            target = temporary / name
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        return temporary

    def run_verify(self, root: Path, *, optimized: bool = False) -> subprocess.CompletedProcess[str]:
        command = ["python3"]
        if optimized:
            command.append("-O")
        command.append("verify.py")
        return subprocess.run(command, cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def mutate_json(self, root: Path, callback) -> None:
        path = root / "results/certification.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_manifest(root)

    def synthetic_raw_evidence(self):
        data = json.loads((ROOT / "results/certification.json").read_text(encoding="utf-8"))
        raw_runs = {}
        baseline_rows = []
        accepted_rows = []
        rtl = {
            "baseline": (ROOT / "rtl/baseline/sha.v").read_bytes(),
            "accepted": (ROOT / "rtl/accepted/sha.v").read_bytes(),
        }
        for row in data["per_seed"]:
            seed = row["seed"]
            for side, record_rows in (("baseline", baseline_rows), ("accepted", accepted_rows)):
                metrics = row[side]
                dynamic_fraction = metrics["active_dynamic_power_w"] / metrics["active_total_power_w"]
                vpr = f"""
Total logic block area (Warning: this is an estimate only): {metrics['logic_block_area_mwta']}
Total routing area: {metrics['routing_area_mwta']}, per logic tile
Final critical path delay (least slack): {metrics['critical_path_delay_ns']} ns, Fmax: {metrics['fmax_mhz']} MHz
Circuit successfully routed with a channel width factor of {metrics['timing_channel_width']}.
    .latch : {metrics['registers']}
    clb {metrics['clb_blocks']} 0
    memory {metrics['memories']} 0
""".encode()
                raw_runs[(side, seed)] = {
                    "vpr_stdout.log": vpr,
                    "active.power": f"Total {metrics['active_total_power_w']!r} 1 {dynamic_fraction!r}\n".encode(),
                    "idle.power": f"Total {metrics['idle_total_power_w']!r} 1 0.5\n".encode(),
                    "sha.v": rtl[side],
                }
                record_rows.append({"seed": seed, **metrics})
        return data, raw_runs, {"certification_per_seed": baseline_rows}, {"per_seed": accepted_rows}

    def test_clean_compact_package_passes(self) -> None:
        result = self.run_verify(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Compact package consistency: PASS", result.stdout)
        self.assertIn("Full raw evidence: NOT CHECKED", result.stdout)

    def test_public_bundle_builder_has_no_operational_optimization_inputs(self) -> None:
        source = (ROOT / "scripts/build_evidence_bundle.py").read_text(encoding="utf-8").lower()
        public_flow_files = source.split("flow_files = [", 1)[1].split("]", 1)[0]
        for marker in ('"config.py"', '"runner.py"', '"evaluator.py"', '"eval_script.py"'):
            self.assertNotIn(marker, public_flow_files)
        self.assertNotIn("evidence/ppa45/runs/", source)
        for option in ("--accepted-run", "--accepted-record", "--baseline-run"):
            self.assertIn(option, source)

    def test_missing_manifest_entry_fails(self) -> None:
        root = self.copy()
        lines = (root / "SHA256SUMS").read_text().splitlines()
        (root / "SHA256SUMS").write_text("\n".join(lines[1:]) + "\n")
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_false_correctness_fails_after_rehash(self) -> None:
        root = self.copy()
        self.mutate_json(root, lambda data: data["correctness"].__setitem__("formal_pass", False))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_empty_correctness_fails_after_rehash(self) -> None:
        root = self.copy()
        self.mutate_json(root, lambda data: data.__setitem__("correctness", {}))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_wrong_interface_contract_fails_after_rehash(self) -> None:
        root = self.copy()
        self.mutate_json(
            root,
            lambda data: data["contract"].__setitem__(
                "interface",
                "sha1(clk_i, rst_i, text_i[31:0], text_o[31:0], cmd_i[3:0], cmd_w_i, cmd_o[3:0])",
            ),
        )
        result = self.run_verify(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("published interface does not match the RTL declarations", result.stderr)

    def test_rtl_interface_drift_fails_even_after_rehash(self) -> None:
        root = self.copy()
        baseline_path = root / "rtl/baseline/sha.v"
        accepted_path = root / "rtl/accepted/sha.v"
        baseline = baseline_path.read_text(encoding="utf-8")
        self.assertEqual(baseline.count("input\t[2:0]\tcmd_i;"), 1)
        baseline_path.write_text(baseline.replace("input\t[2:0]\tcmd_i;", "input\t[3:0]\tcmd_i;"), encoding="utf-8")
        patch = "".join(
            difflib.unified_diff(
                baseline_path.read_text(encoding="utf-8").splitlines(keepends=True),
                accepted_path.read_text(encoding="utf-8").splitlines(keepends=True),
                fromfile="rtl/baseline/sha.v",
                tofile="rtl/accepted/sha.v",
            )
        )
        (root / "rtl/baseline-to-accepted.patch").write_text(patch, encoding="utf-8")
        result_path = root / "results/certification.json"
        data = json.loads(result_path.read_text(encoding="utf-8"))
        data["source"]["corrected_baseline_sha256"] = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
        result_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_manifest(root)
        result = self.run_verify(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline and accepted RTL interfaces differ", result.stderr)

    def test_fractional_seed_fails_after_rehash(self) -> None:
        root = self.copy()
        self.mutate_json(root, lambda data: data["per_seed"][0].__setitem__("seed", 2.9))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_scaled_power_units_fail_after_rehash(self) -> None:
        root = self.copy()
        def mutate(data):
            for row in data["per_seed"]:
                for side in ("baseline", "accepted"):
                    row[side]["active_total_power_w"] *= 1000
                    row[side]["active_dynamic_power_w"] *= 1000
                    row[side]["active_static_power_w"] *= 1000
                    row[side]["idle_total_power_w"] *= 1000
                    row[side]["energy_per_block_nj"] *= 1000
        self.mutate_json(root, mutate)
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_wrong_metric_definition_fails_under_python_optimized(self) -> None:
        root = self.copy()
        self.mutate_json(root, lambda data: data["score_definition"].__setitem__("primary_metrics", ["area_total_mwta", "critical_path_delay_ns", "energy_per_block_nj"]))
        self.assertNotEqual(self.run_verify(root, optimized=True).returncode, 0)

    def test_corrupt_auxiliary_summary_fails_after_rehash(self) -> None:
        root = self.copy()
        self.mutate_json(root, lambda data: data["summary"]["accepted"].__setitem__("clb_blocks", 1))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_authority_drift_fails(self) -> None:
        mutations = {
            "VTR commit": lambda data: data["contract"].__setitem__("vtr_commit", "0" * 40),
            "architecture": lambda data: data["contract"].__setitem__("architecture_sha256", "0" * 64),
            "technology": lambda data: data["contract"].__setitem__("technology_sha256", "0" * 64),
            "NIST corpus": lambda data: data["contract"].__setitem__("nist_corpus_sha256", "0" * 64),
            "EQY commit": lambda data: data["contract"].__setitem__("eqy_commit", "0" * 40),
            "container image": lambda data: data["contract"].__setitem__("image_id", "sha256:" + "0" * 64),
            "validity policy": lambda data: data["acceptance_policy"].__setitem__("validity", "route only"),
            "sample policy": lambda data: data["acceptance_policy"].__setitem__("sample", "adaptive sample"),
        }
        for label, mutation in mutations.items():
            with self.subTest(label=label):
                root = self.copy()
                self.mutate_json(root, mutation)
                self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_duplicate_json_key_fails(self) -> None:
        root = self.copy()
        path = root / "results/certification.json"
        text = path.read_text(encoding="utf-8").replace('"schema_version": 2,', '"schema_version": 2,\n  "schema_version": 2,', 1)
        path.write_text(text, encoding="utf-8")
        write_manifest(root)
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_raw_metric_substitution_fails_semantically(self) -> None:
        data, raw_runs, baseline_record, accepted_record = self.synthetic_raw_evidence()
        public_verify.verify_raw_measurement_bindings(data, raw_runs, baseline_record, accepted_record)
        files = raw_runs[("accepted", 2)]
        original = str(data["per_seed"][0]["accepted"]["critical_path_delay_ns"]).encode()
        self.assertEqual(files["vpr_stdout.log"].count(original), 1)
        files["vpr_stdout.log"] = files["vpr_stdout.log"].replace(original, b"99.2839")
        with self.assertRaises(public_verify.VerificationError):
            public_verify.verify_raw_measurement_bindings(data, raw_runs, baseline_record, accepted_record)


if __name__ == "__main__":
    unittest.main()
