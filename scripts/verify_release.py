#!/usr/bin/env python3
"""Run public-release integrity checks for WorkWorlds."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def require(path: str) -> Path:
    p = ROOT / path
    if not p.exists():
        raise AssertionError(f"Missing required artifact: {path}")
    return p


def run(cmd: list[str], *, pythonpath: str | None = None) -> None:
    print("$", " ".join(cmd))
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if pythonpath is not None:
        env["PYTHONPATH"] = str(ROOT / pythonpath)
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def without_software(obj: dict) -> dict:
    out = dict(obj)
    out.pop("software", None)
    return out


def main() -> int:
    manifest = json.loads(require("MANIFEST.json").read_text())
    criterion = pd.read_csv(require("data/criterion_results.csv"))
    runs = pd.read_csv(require("data/run_ledger.csv"))

    expected_criterion = manifest["study"]["criterion_executions"]
    expected_runs = manifest["study"]["runs"]
    assert len(criterion) == expected_criterion, (len(criterion), expected_criterion)
    assert len(runs) == expected_runs, (len(runs), expected_runs)

    for path in [
        "README.md",
        "ARTIFACT_SCOPE.md",
        "LICENSE",
        "CITATION.cff",
        "VALIDATION.txt",
        "Makefile",
        "scripts/sample_audits.py",
        "analysis/analyze_results.py",
        "data/analysis_results.json",
        "data/matched_results.json",
        "data/validation_results.json",
        "data/evidence_map_final.json",
        "data/evidence_map_reviewer_1.csv",
        "data/evidence_map_reviewer_2.csv",
        "data/attempt_ledger.csv",
        "data/configs/semantic_grader.yaml",
        "data/grader_audit_sample_manifest.csv",
        "data/access_audit_sample_manifest.csv",
        "reference/eval_worlds_toy/core.py",
        "reference/tests/test_reference.py",
        "paper/main.tex",
        "paper/references.bib",
    ]:
        require(path)

    run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    run(
        [sys.executable, "-m", "unittest", "discover", "-s", "reference/tests", "-v"],
        pythonpath="reference",
    )
    run([sys.executable, "reference/isolation_adversaries.py"], pythonpath="reference")

    run(
        [sys.executable, "scripts/build_frozen_release.py"],
    )
    run([sys.executable, "scripts/sample_audits.py"])
    run([sys.executable, "scripts/check_records.py"])
    frozen = json.loads(require("data/analysis_results.json").read_text())
    with tempfile.TemporaryDirectory(prefix="workworlds_verify_") as tmpdir:
        recomputed_path = Path(tmpdir) / "analysis_results.json"
        run(
            [
                sys.executable,
                "analysis/analyze_results.py",
                "--output",
                str(recomputed_path),
            ]
        )
        recomputed = json.loads(recomputed_path.read_text())

    # Package versions are environment-specific. All study outputs must match.
    assert without_software(recomputed) == without_software(frozen), (
        "Recomputed analysis differs from frozen analysis_results.json"
    )
    run([sys.executable, "scripts/sync_public_numbers.py"])

    try:
        import jsonschema
    except ImportError:
        jsonschema = None
    if jsonschema is not None:
        schema_dir = ROOT / "data" / "schemas"
        for name in ("matched_results.schema.json", "validation_results.schema.json"):
            schema = json.loads((schema_dir / name).read_text())
            instance_name = name.replace(".schema.json", ".json")
            instance = json.loads(require(f"data/{instance_name}").read_text())
            jsonschema.validate(instance=instance, schema=schema)
        print("jsonschema: matched_results + validation_results OK")
    else:
        print("jsonschema not installed; skipped schema validation")

    print(f"criterion rows: {len(criterion):,}")
    print(f"run rows: {len(runs):,}")
    print("analysis outputs: exact match (excluding environment-specific software versions)")
    print("release verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
