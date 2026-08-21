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
    paths = [
        line.split("  ", 1)[1]
        for line in (root / "SHA256SUMS").read_text().splitlines()
        if line
    ]
    payload = "".join(
        f"{hashlib.sha256((root / relative).read_bytes()).hexdigest()}  {relative}\n"
        for relative in sorted(paths)
    )
    (root / "SHA256SUMS").write_text(payload, encoding="utf-8")


class MlkemCbdPublicVerifierTests(unittest.TestCase):
    def copy(self) -> Path:
        temporary = Path(tempfile.mkdtemp(prefix="mlkem-cbd-public-test-"))
        self.addCleanup(shutil.rmtree, temporary)
        for name in (
            "LICENSE",
            "Makefile",
            "README.md",
            "SHA256SUMS",
            "certificate.json",
            "full-evidence.json",
            "report",
            "rtl",
            "technical-report.pdf",
            "tests",
            "tools",
            "verify.py",
        ):
            source = ROOT / name
            target = temporary / name
            if source.is_dir():
                shutil.copytree(
                    source,
                    target,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
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
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_manifest(root)

    def test_clean_package_passes(self) -> None:
        result = self.run_verify(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ML-KEM CBD compact evidence: PASS", result.stdout)
        self.assertIn("held_out_pairs=64", result.stdout)
        self.assertIn("Full raw evidence: NOT CHECKED", result.stdout)

    def test_public_claim_boundary_is_explicit(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        report = (ROOT / "report/latex/technical-report.tex").read_text(
            encoding="utf-8"
        )
        self.assertIn("64 prospectively frozen publication pairs", readme)
        self.assertIn("ACE probabilistic activity", readme)
        self.assertIn("not side-channel", readme.lower())
        self.assertNotRegex(readme, r"__[A-Z0-9_]+__")
        self.assertIn("Raw-provenance verification", report)
        self.assertIn("five-step temporal induction", report)

    def test_false_formal_status_fails_after_rehash(self) -> None:
        root = self.copy()
        self.mutate(
            root, lambda data: data["correctness"].__setitem__("formal_passed", False)
        )
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_metric_substitution_fails(self) -> None:
        root = self.copy()
        self.mutate(
            root,
            lambda data: data["pairs"][0]["optimized"].__setitem__(
                "critical_path_delay_ns", 99.0
            ),
        )
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_score_substitution_fails(self) -> None:
        root = self.copy()
        self.mutate(
            root,
            lambda data: data["summary"]["paired_ratio"].__setitem__("composite", 0.1),
        )
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_improvement_substitution_fails(self) -> None:
        root = self.copy()
        self.mutate(
            root,
            lambda data: data["summary"]["improvement_percent"].__setitem__(
                "composite", 99.0
            ),
        )
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_authority_drift_fails(self) -> None:
        root = self.copy()
        self.mutate(root, lambda data: data.__setitem__("authority", "post_hoc_pool"))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_seed_substitution_fails(self) -> None:
        root = self.copy()
        self.mutate(root, lambda data: data["pairs"][0].__setitem__("seed", 999))
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rtl_drift_fails(self) -> None:
        root = self.copy()
        path = root / "rtl/optimized/cbd.v"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        write_manifest(root)
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_patch_drift_fails(self) -> None:
        root = self.copy()
        path = root / "rtl/changes.patch"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        write_manifest(root)
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_full_evidence_placeholder_fails(self) -> None:
        root = self.copy()
        path = root / "full-evidence.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["archive_sha256"] = "0" * 64
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_manifest(root)
        self.assertNotEqual(self.run_verify(root).returncode, 0)

    def test_rehashed_full_evidence_url_substitution_fails(self) -> None:
        root = self.copy()
        path = root / "full-evidence.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["download_url"] = "https://example.invalid/substitute.tar.gz"
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_manifest(root)
        self.assertNotEqual(self.run_verify(root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
