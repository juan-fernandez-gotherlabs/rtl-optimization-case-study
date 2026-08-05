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
        champion = (ROOT / "rtl/champion/sha.v").read_text(encoding="utf-8")
        self.assertEqual(
            hashlib.sha256(baseline.encode()).hexdigest(),
            "191a4f2148a4efda7aadd24480eb13d78a1d2c0c7e8a3fcc37c44f6a8e8011e5",
        )
        self.assertEqual(
            hashlib.sha256(champion.encode()).hexdigest(),
            "743e6c9ffcca6f00d35d5e73ba6f6478a9133a0c55a471c16d6e59d831aeeabc",
        )
        baseline_assigns = {line.strip() for line in baseline.splitlines() if line.strip().startswith("assign ")}
        champion_assigns = {line.strip() for line in champion.splitlines() if line.strip().startswith("assign ")}
        self.assertEqual(len(baseline_assigns - champion_assigns), 4)
        self.assertEqual(len(champion_assigns - baseline_assigns), 4)

    def test_search_history_is_formal_first(self) -> None:
        history = load("results/search-history.json")
        self.assertEqual(history["generations"], 20)
        self.assertEqual(history["submissions_total"], 46)
        self.assertEqual(history["formal_status_counts"], {"fail": 1, "not_run": 4, "pass": 41})
        self.assertEqual(history["unique_formal_pass_candidates"], 29)
        non_pass = [row for row in history["submissions"] if row["formal_status"] != "pass"]
        self.assertEqual(len(non_pass), 5)
        self.assertTrue(all(row["status"] == "candidate_correctness" for row in non_pass))

    def test_certification_pool_is_paired_and_disjoint(self) -> None:
        baseline = load("results/baseline-certification.json")
        champion = load("results/champion-certification.json")
        baseline_seeds = {int(row["seed"]) for row in baseline["per_seed"]}
        champion_seeds = {int(row["seed"]) for row in champion["per_seed"]}
        search_seeds = set(baseline["seed_sets"]["search"])
        self.assertEqual(baseline_seeds, champion_seeds)
        self.assertEqual(len(champion_seeds), 64)
        self.assertFalse(search_seeds & champion_seeds)

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


if __name__ == "__main__":
    unittest.main()
