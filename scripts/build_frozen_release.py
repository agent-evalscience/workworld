#!/usr/bin/env python3
"""Recompute public audit summaries from the frozen study tables."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "analysis"))

from release_audit_utils import (  # noqa: E402
    access_audit_summary,
    bootstrap_kappa,
    grader_audit_summary,
    solvability_agreement,
    write_json,
)

BOOTSTRAP_REPLICATES = 2000
BOOTSTRAP_SEED = 20270908


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def long_reviewer_sheet(reviewer_1: pd.DataFrame, reviewer_2: pd.DataFrame) -> pd.DataFrame:
    return pd.concat([reviewer_1, reviewer_2], ignore_index=True)


def main() -> None:
    matched_path = DATA / "matched_results.json"
    validation_path = DATA / "validation_results.json"
    matched = load_json(matched_path)
    validation = load_json(validation_path)

    reviewer_1 = pd.read_csv(DATA / "evidence_map_reviewer_1.csv")
    reviewer_2 = pd.read_csv(DATA / "evidence_map_reviewer_2.csv")
    long_sheet = long_reviewer_sheet(reviewer_1, reviewer_2)
    stats = solvability_agreement(long_sheet)
    kappa_ci = bootstrap_kappa(
        long_sheet, replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED
    )
    final_obj = load_json(DATA / "evidence_map_final.json")
    validation["evidence_map"] = {
        "criteria": int(stats["criteria"]),
        "criteria_solvable": int(
            sum(bool(item["final_solvable"]) for item in final_obj["criteria"])
        ),
        "reviewer_1_solvable": int(stats["reviewer_1_solvable"]),
        "reviewer_2_solvable": int(stats["reviewer_2_solvable"]),
        "solvability_exact_agreement": float(stats["solvability_exact_agreement"]),
        "solvability_kappa": float(stats["solvability_kappa"]),
        "solvability_gwet_ac1": float(stats["solvability_gwet_ac1"]),
        "solvability_kappa_bootstrap_ci": {
            "lower": float(kappa_ci["lower"]),
            "upper": float(kappa_ci["upper"]),
        },
        "bootstrap_replicates": int(kappa_ci["bootstrap_replicates"]),
        "locator_jaccard_mean": float(stats["locator_jaccard_mean"]),
        "locator_jaccard_median": float(stats["locator_jaccard_median"]),
        "adjudicated_criteria": int(stats["adjudicated_criteria"]),
        "solvability_contingency": stats["contingency"],
        "final_map_freeze_hash": final_obj["map_freeze_hash"],
        "final_map_frozen_at": final_obj["frozen_at"],
    }

    grader = pd.read_csv(DATA / "grader_audit_ratings.csv")
    gs = grader_audit_summary(grader)

    access = pd.read_csv(DATA / "access_label_audit_ratings.csv")
    matched["access_label_audit"] = access_audit_summary(
        access, replicates=BOOTSTRAP_REPLICATES, seed=BOOTSTRAP_SEED
    )

    grader_config = DATA / "configs/semantic_grader.yaml"
    matched["grading"]["grader_config_sha256"] = sha256_file(grader_config)
    matched["grading"]["grader_config_path"] = "data/configs/semantic_grader.yaml"
    agent_digest = {
        "opus5": sha256_file(DATA / "configs/agent_opus5.yaml"),
        "grok": sha256_file(DATA / "configs/agent_grok.yaml"),
        "sol": sha256_file(DATA / "configs/agent_sol.yaml"),
    }
    for run in matched["runs"]:
        run["agent_config_sha256"] = agent_digest[run["agent_id"]]
        run["agent_config_path"] = f"data/configs/agent_{run['agent_id']}.yaml"

    write_json(matched_path, matched)
    write_json(DATA / "grader_audit_summary.json", gs)
    write_json(validation_path, validation)

    attempts = pd.read_csv(DATA / "attempt_ledger.csv")
    if len(grader) != 240:
        raise SystemExit(f"grader audit n={len(grader)}, expected 240")
    if len(access) != 346:
        raise SystemExit(f"access audit n={len(access)}, expected 346")
    completed = attempts[attempts["status"] == "completed"]
    if len(completed) != 192:
        raise SystemExit(f"completed attempts={len(completed)}, expected 192")
    if sha256_file(grader_config) != matched["grading"]["grader_config_sha256"]:
        raise SystemExit("grader config hash mismatch")

    acc = matched["access_label_audit"]
    print("updated evidence_map from reviewer sheets", len(reviewer_1))
    print("recomputed grader audit", len(grader), "kappa", round(gs["cohen_kappa"], 3))
    print("updated access_label_audit", len(access), "kappa", round(acc["kappa"], 3))
    print("updated config digests")


if __name__ == "__main__":
    main()
