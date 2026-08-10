from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
        for name in (".gitattributes", ".github", ".gitignore", "LICENSE", "Makefile", "README.md", "SHA256SUMS", "report", "results", "rtl", "scripts", "technical-report.pdf", "tests", "verify.py"):
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

    def test_clean_compact_package_passes(self) -> None:
        result = self.run_verify(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Compact package consistency: PASS", result.stdout)
        self.assertIn("Full raw evidence: NOT CHECKED", result.stdout)

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

    def test_duplicate_json_key_fails(self) -> None:
        root = self.copy()
        path = root / "results/certification.json"
        text = path.read_text(encoding="utf-8").replace('"schema_version": 2,', '"schema_version": 2,\n  "schema_version": 2,', 1)
        path.write_text(text, encoding="utf-8")
        write_manifest(root)
        self.assertNotEqual(self.run_verify(root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
