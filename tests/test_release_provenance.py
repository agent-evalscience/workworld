import json
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class ReleaseProvenanceTests(unittest.TestCase):
    def test_reviewer_sheets_are_complete(self):
        left = pd.read_csv(DATA / "evidence_map_reviewer_1.csv")
        right = pd.read_csv(DATA / "evidence_map_reviewer_2.csv")
        self.assertEqual(len(left), 72)
        self.assertEqual(len(right), 72)
        for column in ["solvable", "locators", "submitted_at", "sheet_version"]:
            self.assertIn(column, left.columns)
            self.assertIn(column, right.columns)

    def test_final_evidence_map_is_frozen(self):
        frame = pd.read_csv(DATA / "evidence_map_final.csv")
        payload = json.loads((DATA / "evidence_map_final.json").read_text())
        self.assertEqual(len(frame), 72)
        self.assertEqual(frame["map_freeze_hash"].nunique(), 1)
        self.assertEqual(payload["map_freeze_hash"], frame["map_freeze_hash"].iloc[0])
        self.assertEqual(len(payload["criteria"]), 72)
        self.assertTrue(bool(frame["final_solvable"].all()))

    def test_grader_audit_sample(self):
        ratings = pd.read_csv(DATA / "grader_audit_ratings.csv")
        manifest = pd.read_csv(DATA / "grader_audit_sample_manifest.csv")
        self.assertEqual(len(ratings), 240)
        self.assertEqual(len(manifest), 240)
        self.assertEqual(
            set(zip(ratings["run_id"], ratings["criterion_id"])),
            set(zip(manifest["run_id"], manifest["criterion_id"])),
        )

    def test_access_audit_sample(self):
        ratings = pd.read_csv(DATA / "access_label_audit_ratings.csv")
        coder_a = pd.read_csv(DATA / "access_label_coder_a.csv")
        coder_b = pd.read_csv(DATA / "access_label_coder_b.csv")
        manifest = pd.read_csv(DATA / "access_audit_sample_manifest.csv")
        self.assertEqual(len(ratings), 346)
        self.assertEqual(len(coder_a), 346)
        self.assertEqual(len(coder_b), 346)
        self.assertEqual(len(manifest), 346)

    def test_packet_revision_history(self):
        matched = json.loads((DATA / "matched_results.json").read_text())
        self.assertEqual(len(matched["packet_construction"]), 16)
        for packet in matched["packet_construction"]:
            self.assertGreaterEqual(len(packet["revision_history"]), 4)

    def test_run_and_attempt_ledgers(self):
        runs = pd.read_csv(DATA / "run_ledger.csv")
        attempts = pd.read_csv(DATA / "attempt_ledger.csv")
        criterion = pd.read_csv(DATA / "criterion_results.csv")
        completed = attempts[attempts["status"] == "completed"]
        self.assertEqual(len(runs), 192)
        self.assertEqual(len(completed), 192)
        self.assertEqual(set(completed["scheduled_run_id"]), set(runs["run_id"]))
        self.assertEqual(runs["run_record_sha256"].nunique(), 192)
        self.assertEqual(criterion["criterion_record_sha256"].nunique(), 1728)

    def test_config_hashes_match_released_bodies(self):
        import hashlib

        matched = json.loads((DATA / "matched_results.json").read_text())
        grader_path = ROOT / matched["grading"]["grader_config_path"]
        digest = hashlib.sha256(grader_path.read_bytes()).hexdigest()
        self.assertEqual(digest, matched["grading"]["grader_config_sha256"])
        for agent_id, name in [
            ("opus5", "agent_opus5.yaml"),
            ("grok", "agent_grok.yaml"),
            ("sol", "agent_sol.yaml"),
        ]:
            path = DATA / "configs" / name
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            runs = [run for run in matched["runs"] if run["agent_id"] == agent_id]
            self.assertTrue(runs)
            self.assertEqual(runs[0]["agent_config_sha256"], digest)


if __name__ == "__main__":
    unittest.main()
