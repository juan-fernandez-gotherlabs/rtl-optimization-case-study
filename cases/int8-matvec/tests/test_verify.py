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
    paths = [line.split("  ", 1)[1] for line in (root / "SHA256SUMS").read_text().splitlines() if line]
    payload = "".join(
        f"{hashlib.sha256((root / relative).read_bytes()).hexdigest()}  {relative}\n"
        for relative in sorted(paths)
    )
    (root / "SHA256SUMS").write_text(payload, encoding="utf-8")


class Int8PublicVerifierTests(unittest.TestCase):
    def copy(self) -> Path:
        temporary = Path(tempfile.mkdtemp(prefix="int8-public-test-"))
        self.addCleanup(shutil.rmtree, temporary)
        for name in ("LICENSE", "Makefile", "README.md", "SHA256SUMS", "certificate.json", "report", "rtl", "technical-report.pdf", "tests", "tools", "verify.py"):
            source = ROOT / name
            target = temporary / name
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        return temporary

    def run_verify(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", "verify.py"],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def mutate(self, root: Path, callback) -> None:
        path = root / "certificate.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_manifest(root)

    def test_clean_package_passes(self) -> None:
        result = self.run_verify(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("INT8 MatVec compact evidence: PASS", result.stdout)

    def test_false_formal_status_fails_after_rehash(self) -> None:
        root = self.copy()
        self.mutate(root, lambda data: data["correctness"].__setitem__("formal_passed", False))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_metric_substitution_fails(self) -> None:
        root = self.copy()
        self.mutate(root, lambda data: data["pairs"][0]["optimized"].__setitem__("critical_path_delay_ns", 99.0))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_score_substitution_fails(self) -> None:
        root = self.copy()
        self.mutate(root, lambda data: data["summary"].__setitem__("score", 0.1))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_held_out_seed_identity_is_rejected(self) -> None:
        root = self.copy()
        self.mutate(root, lambda data: data["pairs"][0].__setitem__("seed", 2))
        result = self.run_verify(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("held-out seed identity leaked", result.stderr)

    def test_rtl_drift_fails(self) -> None:
        root = self.copy()
        path = root / "rtl/optimized/int8_matvec_4x4.sv"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        write_manifest(root)
        self.assertNotEqual(self.run_verify(root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
