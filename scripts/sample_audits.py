#!/usr/bin/env python3
"""Reproduce stratified audit selection from criterion_results.csv and the recorded seeds."""
from __future__ import annotations

import argparse
import csv
import math
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def sample_rows(criteria, seed, kind):
    groups = defaultdict(list)
    for row in criteria:
        if kind == "grader":
            if row["grading_route"] != "semantic":
                continue
            key = (row["task_id"], row["agent_id"], row["condition"])
        else:
            key = (row["condition"], row["access_label"])
        groups[key].append(row)
    keys = sorted(groups)
    if kind == "grader":
        counts = {key: 5 for key in keys}
    else:
        fractions = {key: 346 * len(groups[key]) / len(criteria) for key in keys}
        counts = {key: math.floor(fractions[key]) for key in keys}
        remaining = 346 - sum(counts.values())
        priority = sorted(keys, key=lambda key: (-(fractions[key] - counts[key]), key))
        for key in priority[:remaining]:
            counts[key] += 1
    rng = random.Random(seed)
    result = []
    for key in keys:
        population = sorted(groups[key], key=lambda row: (row["run_id"], row["criterion_id"]))
        for row in rng.sample(population, counts[key]):
            result.append((row["run_id"], row["criterion_id"], "|".join(key), counts[key] / len(population)))
    rng.shuffle(result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check selected identities, ordering, strata and inclusion probabilities")
    parser.parse_args()
    criteria = read_csv(DATA / "criterion_results.csv")
    for kind, manifest_name, rating_name in [
        ("grader", "grader_audit_sample_manifest.csv", "grader_audit_ratings.csv"),
        ("access", "access_audit_sample_manifest.csv", "access_label_audit_ratings.csv"),
    ]:
        manifest = read_csv(DATA / manifest_name)
        ratings = read_csv(DATA / rating_name)
        seeds = {int(row["seed"]) for row in manifest}
        if len(seeds) != 1:
            raise SystemExit(f"{kind}: expected one reproducible sampling seed")
        selected = sample_rows(criteria, seeds.pop(), kind)
        if len(selected) != len(manifest):
            raise SystemExit(f"{kind}: sample size mismatch")
        prefix = "GA" if kind == "grader" else "AA"
        for index, (expected, row) in enumerate(zip(selected, manifest), 1):
            run_id, criterion_id, stratum, probability = expected
            if (run_id, criterion_id, stratum) != (row["run_id"], row["criterion_id"], row["stratum"]):
                raise SystemExit(f"{kind}: selected row {index} does not match recorded seed")
            if abs(probability - float(row["selection_probability"])) > 1e-15:
                raise SystemExit(f"{kind}: inclusion probability mismatch at row {index}")
            if row["audit_id"] != f"{prefix}-{index:04d}":
                raise SystemExit(f"{kind}: audit identity mismatch at row {index}")
        rating_keys = {(row["run_id"], row["criterion_id"], row["audit_id"]) for row in ratings}
        manifest_keys = {(row["run_id"], row["criterion_id"], row["audit_id"]) for row in manifest}
        if rating_keys != manifest_keys:
            raise SystemExit(f"{kind}: rating identities differ from the reproduced selection")
        print(f"{kind}: {len(selected)} selected rows reproduced exactly; inclusion probabilities verified")


if __name__ == "__main__":
    main()
