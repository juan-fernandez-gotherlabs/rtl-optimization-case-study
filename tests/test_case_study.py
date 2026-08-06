from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_evidence  # noqa: E402


def load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class EvidenceTests(unittest.TestCase):
    def test_published_evidence_recomputes(self) -> None:
        self.assertEqual(verify_evidence.main(), 0)

    def test_exact_rtl_identities_and_four_assignments(self) -> None:
        baseline = (ROOT / "rtl/baseline/sha.v").read_text(encoding="utf-8")
        accepted = (ROOT / "rtl/accepted/sha.v").read_text(encoding="utf-8")
        self.assertEqual(
            hashlib.sha256(baseline.encode()).hexdigest(),
            "191a4f2148a4efda7aadd24480eb13d78a1d2c0c7e8a3fcc37c44f6a8e8011e5",
        )
        self.assertEqual(
            hashlib.sha256(accepted.encode()).hexdigest(),
            "743e6c9ffcca6f00d35d5e73ba6f6478a9133a0c55a471c16d6e59d831aeeabc",
        )
        baseline_assigns = {line.strip() for line in baseline.splitlines() if line.strip().startswith("assign ")}
        accepted_assigns = {line.strip() for line in accepted.splitlines() if line.strip().startswith("assign ")}
        self.assertEqual(len(baseline_assigns - accepted_assigns), 4)
        self.assertEqual(len(accepted_assigns - baseline_assigns), 4)

    def test_certification_pool_is_paired_and_disjoint(self) -> None:
        baseline = load("results/baseline-certification.json")
        accepted = load("results/accepted-certification.json")
        baseline_seeds = {int(row["seed"]) for row in baseline["per_seed"]}
        accepted_seeds = {int(row["seed"]) for row in accepted["per_seed"]}
        self.assertEqual(baseline_seeds, accepted_seeds)
        self.assertEqual(len(accepted_seeds), 64)

    def test_public_result_contains_only_baseline_and_accepted_measurements(self) -> None:
        self.assertEqual(
            {path.name for path in (ROOT / "results").glob("*.json")},
            {
                "accepted-certification.json",
                "baseline-certification.json",
                "netlist-seed20-summary.json",
            },
        )

    def test_figures_are_generated_data_artifacts(self) -> None:
        for path in sorted((ROOT / "figures").glob("*.svg")):
            text = path.read_text(encoding="utf-8")
            self.assertIn("<svg", text)
            self.assertNotRegex(text.lower(), r"\b(?:nan|infinity)\b")
            self.assertIn("<title>", text)
            self.assertIn("<desc>", text)


class DocumentationTests(unittest.TestCase):
    LINK = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")

    def test_local_markdown_links_exist(self) -> None:
        missing: list[str] = []
        for document in ROOT.rglob("*.md"):
            if any(part in {".git", "tmp", "output"} for part in document.parts):
                continue
            for target in self.LINK.findall(document.read_text(encoding="utf-8")):
                target = target.strip().strip("<>").split("#", 1)[0]
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.exists():
                    missing.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual(missing, [])

    def test_public_files_do_not_expose_local_workspace_paths(self) -> None:
        forbidden = (
            b"/" + b"Users/",
            b".codex/" + b"worktrees",
            b"Temporary" + b"Items",
        )
        offenders: list[str] = []
        for path in ROOT.rglob("*"):
            if not path.is_file() or any(
                part in {".git", "tmp", "output", "__pycache__"} for part in path.parts
            ):
                continue
            data = path.read_bytes()
            if any(token in data for token in forbidden):
                offenders.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_canonical_report_is_portable_xelatex(self) -> None:
        canonical = ROOT / "report/technical-report.pdf"
        source = ROOT / "report/latex/technical-report.tex"
        self.assertTrue(canonical.is_file())
        self.assertTrue(source.is_file())
        self.assertFalse((ROOT / "report/technical-report-latex.pdf").exists())
        text = source.read_text(encoding="utf-8")
        self.assertIn("texgyreheros-regular.otf", text)
        self.assertIn("texgyrecursor-regular.otf", text)
        self.assertNotIn("Helvetica Neue", text)
        self.assertNotIn("Menlo", text)


if __name__ == "__main__":
    unittest.main()
