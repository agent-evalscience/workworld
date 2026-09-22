#!/usr/bin/env python3
"""Shared helpers for recomputing frozen audit statistics in the public release."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

VALID_VERDICTS = {"pass", "fail", "unrateable"}


def source_key(surface: str, locator: str) -> tuple[str, str]:
    return (surface, locator)


def parse_locator_list(value: str) -> set[tuple[str, str]]:
    if not value or not str(value).strip():
        return set()
    out: set[tuple[str, str]] = set()
    for item in str(value).split("|"):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(f"locator must be surface:path, got {item!r}")
        surface, locator = item.split(":", 1)
        out.add((surface.strip(), locator.strip()))
    return out


def format_locator_list(sources: Iterable[tuple[str, str]]) -> str:
    return "|".join(f"{surface}:{locator}" for surface, locator in sorted(sources))


def jaccard(left: set[tuple[str, str]], right: set[tuple[str, str]]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def solvability_agreement(
    reviewer_sheet: pd.DataFrame,
) -> dict[str, float | int | dict[str, float]]:
    pivot = reviewer_sheet.pivot_table(
        index="criterion_id",
        columns="reviewer",
        values="solvable",
        aggfunc="first",
    )
    r1 = pivot["reviewer_1"].astype(bool).to_numpy()
    r2 = pivot["reviewer_2"].astype(bool).to_numpy()
    agree = r1 == r2
    n = len(r1)
    observed = float(np.mean(agree))
    p1 = float(np.mean(r1))
    p2 = float(np.mean(r2))
    expected = p1 * p2 + (1 - p1) * (1 - p2)
    kappa = (
        float((observed - expected) / (1 - expected))
        if expected < 1
        else float("nan")
    )
    mean_positive = (p1 + p2) / 2
    ac1_expected = 2 * mean_positive * (1 - mean_positive)
    gwet_ac1 = (
        float((observed - ac1_expected) / (1 - ac1_expected))
        if ac1_expected < 1
        else float("nan")
    )
    both_pass = int(np.sum(r1 & r2))
    both_fail = int(np.sum(~r1 & ~r2))
    r1_only = int(np.sum(r1 & ~r2))
    r2_only = int(np.sum(~r1 & r2))
    jaccards: list[float] = []
    for criterion_id in pivot.index:
        rows = reviewer_sheet[reviewer_sheet["criterion_id"] == criterion_id]
        left = parse_locator_list(
            rows.loc[rows["reviewer"] == "reviewer_1", "locators"].iloc[0]
        )
        right = parse_locator_list(
            rows.loc[rows["reviewer"] == "reviewer_2", "locators"].iloc[0]
        )
        jaccards.append(jaccard(left, right))
    flags = []
    for criterion_id in pivot.index:
        vals = pivot.loc[criterion_id]
        disagree = bool(vals["reviewer_1"]) != bool(vals["reviewer_2"])
        both_no = not bool(vals["reviewer_1"]) and not bool(vals["reviewer_2"])
        if disagree or both_no:
            flags.append(criterion_id)
    return {
        "criteria": n,
        "criteria_solvable": int(np.sum(r1 | r2)),
        "reviewer_1_solvable": int(np.sum(r1)),
        "reviewer_2_solvable": int(np.sum(r2)),
        "solvability_exact_agreement": observed,
        "solvability_kappa": kappa,
        "solvability_gwet_ac1": gwet_ac1,
        "locator_jaccard_mean": float(np.mean(jaccards)),
        "locator_jaccard_median": float(np.median(jaccards)),
        "adjudicated_criteria": len(flags),
        "contingency": {
            "both_solvable": both_pass,
            "both_not_solvable": both_fail,
            "reviewer_1_only": r1_only,
            "reviewer_2_only": r2_only,
        },
    }


def bootstrap_kappa(
    reviewer_sheet: pd.DataFrame,
    replicates: int,
    seed: int,
) -> dict[str, float | int]:
    # Compute task-level 2x2 reviewer contingency tables once, then resample and
    # sum those sufficient statistics. This is exactly equivalent to rebuilding
    # a duplicated criterion frame on every bootstrap draw.
    pivot = reviewer_sheet.pivot_table(
        index=["task_id", "criterion_id"], columns="reviewer", values="solvable", aggfunc="first"
    ).reset_index()
    tasks = sorted(pivot["task_id"].unique())
    counts = []
    for task in tasks:
        g = pivot[pivot["task_id"] == task]
        a = g["reviewer_1"].astype(bool).to_numpy()
        b = g["reviewer_2"].astype(bool).to_numpy()
        counts.append([
            np.sum(a & b), np.sum(~a & ~b), np.sum(a & ~b), np.sum(~a & b)
        ])
    counts = np.asarray(counts, dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(tasks), size=(replicates, len(tasks)))
    sampled = counts[draws].sum(axis=1)
    n = sampled.sum(axis=1)
    observed = (sampled[:, 0] + sampled[:, 1]) / n
    p1 = (sampled[:, 0] + sampled[:, 2]) / n
    p2 = (sampled[:, 0] + sampled[:, 3]) / n
    expected = p1 * p2 + (1 - p1) * (1 - p2)
    denom = 1 - expected
    values = np.full_like(denom, np.nan, dtype=float)
    np.divide(observed - expected, denom, out=values, where=denom > 0)
    values = values[np.isfinite(values)]
    lower, upper = np.quantile(values, [0.025, 0.975])
    return {
        "lower": float(lower),
        "upper": float(upper),
        "bootstrap_replicates": replicates,
        "valid_replicates": int(len(values)),
    }

def three_class_kappa(left: Iterable[str], right: Iterable[str]) -> float:
    left_list = list(left)
    right_list = list(right)
    labels = sorted(set(left_list) | set(right_list))
    n = len(left_list)
    if n == 0:
        return float("nan")
    agree = sum(a == b for a, b in zip(left_list, right_list)) / n
    idx = {c: i for i, c in enumerate(labels)}
    mat = np.zeros((len(labels), len(labels)))
    for a, b in zip(left_list, right_list):
        mat[idx[a], idx[b]] += 1
    mat /= n
    pe = float((mat.sum(axis=0) * mat.sum(axis=1)).sum())
    return float((agree - pe) / (1 - pe)) if pe < 1 else float("nan")


def bootstrap_three_class_kappa(
    frame: pd.DataFrame,
    left_col: str,
    right_col: str,
    task_col: str,
    replicates: int,
    seed: int,
) -> dict[str, float | int]:
    labels = sorted(set(frame[left_col].astype(str)) | set(frame[right_col].astype(str)))
    idx = {label: i for i, label in enumerate(labels)}
    tasks = sorted(frame[task_col].unique())
    mats = []
    for task in tasks:
        mat = np.zeros((len(labels), len(labels)), dtype=float)
        g = frame[frame[task_col] == task]
        for left, right in zip(g[left_col].astype(str), g[right_col].astype(str)):
            mat[idx[left], idx[right]] += 1
        mats.append(mat)
    mats = np.asarray(mats)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(tasks), size=(replicates, len(tasks)))
    sampled = mats[draws].sum(axis=1)
    n = sampled.sum(axis=(1, 2))
    observed = np.trace(sampled, axis1=1, axis2=2) / n
    row = sampled.sum(axis=2) / n[:, None]
    col = sampled.sum(axis=1) / n[:, None]
    expected = (row * col).sum(axis=1)
    denom = 1 - expected
    values = np.full_like(denom, np.nan, dtype=float)
    np.divide(observed - expected, denom, out=values, where=denom > 0)
    values = values[np.isfinite(values)]
    lower, upper = np.quantile(values, [0.025, 0.975])
    return {
        "lower": float(lower),
        "upper": float(upper),
        "bootstrap_replicates": replicates,
        "valid_replicates": int(len(values)),
    }

def access_audit_summary(
    ratings: pd.DataFrame,
    replicates: int = 2000,
    seed: int = 20270908,
) -> dict:
    agree = ratings["coder_a"] == ratings["coder_b"]
    observed = float(agree.mean())
    kappa = three_class_kappa(ratings["coder_a"], ratings["coder_b"])
    kappa_ci = bootstrap_three_class_kappa(
        ratings,
        "coder_a",
        "coder_b",
        "task_id",
        replicates=replicates,
        seed=seed,
    )
    binary = ratings["coder_a"].isin(["accessed", "not_accessed"]) & ratings[
        "coder_b"
    ].isin(["accessed", "not_accessed"])
    binary_agree = float(
        (ratings.loc[binary, "coder_a"] == ratings.loc[binary, "coder_b"]).mean()
    )
    auto_a = float((ratings["automated_label"] == ratings["coder_a"]).mean())
    auto_b = float((ratings["automated_label"] == ratings["coder_b"]).mean())
    consensus = ratings["coder_a"] == ratings["coder_b"]
    consensus_match = float(
        (
            ratings.loc[consensus, "coder_a"]
            == ratings.loc[consensus, "automated_label"]
        ).mean()
    )
    return {
        "sampled": int(len(ratings)),
        "unknown_sampled": int((ratings["automated_label"] == "unknown").sum()),
        "three_class_raw_agreement": observed,
        "binary_raw_agreement": binary_agree,
        "kappa": float(kappa),
        "kappa_bootstrap_ci": {
            "lower": float(kappa_ci["lower"]),
            "upper": float(kappa_ci["upper"]),
        },
        "bootstrap_replicates": replicates,
        "automated_vs_coder_a": auto_a,
        "automated_vs_coder_b": auto_b,
        "consensus_vs_automated": consensus_match,
    }


def grader_audit_summary(ratings: pd.DataFrame) -> dict:
    required = {
        "audit_id",
        "condition",
        "expert_verdict",
        "grader_pass",
    }
    if not required.issubset(ratings.columns):
        raise ValueError(f"ratings must contain {sorted(required)}")
    verdicts = ratings["expert_verdict"].astype(str).str.strip().str.lower()
    invalid = sorted(set(verdicts) - VALID_VERDICTS)
    if invalid:
        raise ValueError(f"invalid expert_verdict values: {invalid}")
    eligible = verdicts != "unrateable"
    expert = (verdicts[eligible] == "pass").astype(int)
    grader = ratings.loc[eligible, "grader_pass"].astype(bool).astype(int)
    observed = float(np.mean(expert.to_numpy() == grader.to_numpy()))
    p1 = float(np.mean(expert))
    p2 = float(np.mean(grader))
    expected = p1 * p2 + (1 - p1) * (1 - p2)
    kappa = (
        float((observed - expected) / (1 - expected))
        if expected < 1
        else float("nan")
    )
    both_pass = int(np.sum((expert == 1) & (grader == 1)))
    both_fail = int(np.sum((expert == 0) & (grader == 0)))
    expert_only = int(np.sum((expert == 1) & (grader == 0)))
    grader_only = int(np.sum((expert == 0) & (grader == 1)))
    by_condition: dict[str, dict[str, float | int]] = {}
    for condition, group in ratings[eligible].groupby("condition"):
        left = (group["expert_verdict"].str.lower() == "pass").astype(int)
        right = group["grader_pass"].astype(bool).astype(int)
        by_condition[str(condition)] = {
            "n": int(len(group)),
            "raw_agreement": float(np.mean(left.to_numpy() == right.to_numpy())),
        }
    return {
        "schema": "eval-worlds-grader-audit-summary/v1",
        "sampled": int(len(ratings)),
        "rateable": int(len(expert)),
        "raw_agreement": observed,
        "cohen_kappa": kappa,
        "contingency": {
            "both_pass": both_pass,
            "both_fail": both_fail,
            "expert_only_pass": expert_only,
            "grader_only_pass": grader_only,
        },
        "by_condition": by_condition,
    }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n")
