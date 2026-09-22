import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseStructureTests(unittest.TestCase):
    def test_required_release_paths_exist(self):
        for rel in [
            "README.md",
            "ARTIFACT_SCOPE.md",
            "CITATION.cff",
            "VALIDATION.txt",
            "Makefile",
            "MANIFEST.json",
            "scripts/sample_audits.py",
            "analysis/analyze_results.py",
            "data/criterion_results.csv",
            "data/run_ledger.csv",
            "data/attempt_ledger.csv",
            "data/evidence_map_final.json",
            "data/configs/semantic_grader.yaml",
            "reference/tests/test_reference.py",
            "paper/main.tex",
            "paper/generated_numbers.tex",
        ]:
            with self.subTest(path=rel):
                self.assertTrue((ROOT / rel).exists(), rel)

    def test_manifest_counts_match_ledgers(self):
        manifest = json.loads((ROOT / "MANIFEST.json").read_text())
        with open(ROOT / "data/criterion_results.csv", encoding="utf-8") as f:
            criterion_rows = sum(1 for _ in f) - 1
        with open(ROOT / "data/run_ledger.csv", encoding="utf-8") as f:
            run_rows = sum(1 for _ in f) - 1
        self.assertEqual(criterion_rows, manifest["study"]["criterion_executions"])
        self.assertEqual(run_rows, manifest["study"]["runs"])

    def test_paper_figures_exist(self):
        for name in ["figure1.png", "figure2.png", "figure3.png", "figure4.png"]:
            with self.subTest(figure=name):
                self.assertTrue((ROOT / "paper" / "figures" / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
