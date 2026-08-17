from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
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
        for name in ("LICENSE", "Makefile", "README.md", "SHA256SUMS", "certificate.json", "full-evidence.json", "report", "rtl", "technical-report.pdf", "tests", "tools", "verify.py"):
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

    def mutate_full_evidence(self, root: Path, callback) -> None:
        path = root / "full-evidence.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        callback(data)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_manifest(root)

    def test_clean_package_passes(self) -> None:
        result = self.run_verify(ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("INT8 MatVec compact evidence: PASS", result.stdout)
        self.assertIn("Full raw evidence: NOT CHECKED", result.stdout)

    def test_seed_sanitizer_is_contextual(self) -> None:
        path = ROOT / "tools/build_evidence_bundle.py"
        spec = importlib.util.spec_from_file_location("int8_bundle", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        self.addCleanup(sys.modules.pop, spec.name, None)
        spec.loader.exec_module(module)
        payload = b"--seed 37\nplacer_opts.seed: 37\nseed_37/out\nmetric=37.125\n"
        sanitized, replacements = module.sanitize_payload(payload, seed=37, pair_id="held-out-01")
        self.assertEqual(replacements, 3)
        self.assertIn(b"metric=37.125", sanitized)
        self.assertNotIn(b"seed_37", sanitized)
        self.assertNotRegex(sanitized, rb"--seed\s+37")

    def test_public_payload_rejects_internal_execution_markers(self) -> None:
        path = ROOT / "verify.py"
        spec = importlib.util.spec_from_file_location("int8_verify_payload", path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(module.VerificationError):
            module.verify_public_payload(b"refresh_token: private", "raw.log")

    def test_public_claim_boundary_is_explicit(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        report = (ROOT / "report/latex/technical-report.tex").read_text(encoding="utf-8")
        self.assertIn("72 registers belong", readme)
        self.assertIn("no commercial DSP-slice, BRAM or ASIC MAC-cell model", readme)
        self.assertIn("re-extracts all 256 post-route", readme)
        self.assertIn("It does not rerun the EDA tools", readme)
        self.assertIn("Fixed wrapper registers", report)
        self.assertIn("three overlapping structural views", report)
        self.assertIn("Raw provenance replay", report)
        self.assertNotIn("\\newpageheading{6. Rewrite", report)

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

    def test_rehashed_full_evidence_identity_substitution_fails(self) -> None:
        root = self.copy()
        self.mutate_full_evidence(root, lambda data: data.__setitem__("archive_sha256", "0" * 64))
        self.assertNotEqual(self.run_verify(root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
