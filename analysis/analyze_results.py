#!/usr/bin/env python3
"""Reproduce the matched-construction estimates reported in the paper."""

from __future__ import annotations

import argparse
import json
import warnings
import os
import multiprocessing as mp
from importlib.metadata import version
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

RELEASE = Path(__file__).resolve().parents[1]
DATA = RELEASE / "data"
DEFAULT_OUTPUT = DATA / "analysis_results.json"
CONDITIONS = ["world_first", "task_first"]
AGENTS = ["opus5", "grok", "sol"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-replicates", type=int, default=2_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20_270_908)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def standardized_gee(
    data: pd.DataFrame,
    outcome: str,
    start_params: dict[str, float] | None = None,
    maxiter: int = 100,
) -> dict[str, float | dict[str, float]]:
    model = smf.gee(
        f"{outcome} ~ C(condition) + C(agent_id)",
        groups="task_id",
        data=data,
        family=sm.families.Binomial(),
        cov_struct=sm.cov_struct.Exchangeable(),
    )
    fit_kwargs: dict[str, object] = {"maxiter": maxiter}
    if start_params is not None:
        fit_kwargs["start_params"] = list(start_params.values())
    fitted = model.fit(**fit_kwargs)
    grid = pd.DataFrame(
        [
            {"condition": condition, "agent_id": agent}
            for condition, agent in product(CONDITIONS, AGENTS)
        ]
    )
    grid["prediction"] = fitted.predict(grid)
    rates = grid.groupby("condition")["prediction"].mean()
    return {
        "world_first": float(rates["world_first"]),
        "task_first": float(rates["task_first"]),
        "risk_difference": float(
            rates["task_first"] - rates["world_first"]
        ),
        "working_correlation": float(fitted.cov_struct.dep_params),
        "coefficients": {
            name: float(value)
            for name, value in fitted.params.items()
        },
    }


def task_count_matrix(criterion: pd.DataFrame) -> tuple[list[str], np.ndarray]:
    tasks = sorted(criterion["task_id"].unique())
    rows: list[list[float]] = []
    for task in tasks:
        row: list[float] = []
        for condition in CONDITIONS:
            subset = criterion[
                (criterion["task_id"] == task)
                & (criterion["condition"] == condition)
            ]
            observable = subset[subset["access_label"] != "unknown"]
            accessed = subset[subset["access_label"] == "accessed"]
            row.extend(
                [
                    float(subset["pass_int"].sum()),
                    float(len(subset)),
                    float(observable["access_int"].sum()),
                    float(len(observable)),
                    float(accessed["pass_int"].sum()),
                    float(len(accessed)),
                ]
            )
        rows.append(row)
    return tasks, np.asarray(rows)


def task_cluster_raw_bootstrap(
    criterion: pd.DataFrame,
    replicates: int,
    seed: int,
) -> dict[str, dict[str, float | int | list[float]]]:
    tasks, counts = task_count_matrix(criterion)
    rng = np.random.default_rng(seed)
    draws = rng.integers(low=0, high=len(tasks), size=(replicates, len(tasks)))
    sampled = counts[draws].sum(axis=1)
    world = sampled[:, :6]
    task = sampled[:, 6:]
    distributions = {
        "criterion_pass": task[:, 0] / task[:, 1] - world[:, 0] / world[:, 1],
        "evidence_access_observed": (
            task[:, 2] / task[:, 3] - world[:, 2] / world[:, 3]
        ),
        "pass_given_access": (
            task[:, 4] / task[:, 5] - world[:, 4] / world[:, 5]
        ),
    }
    output: dict[str, dict[str, float | int | list[float]]] = {}
    for name, values in distributions.items():
        lower, upper = np.quantile(values, [0.025, 0.975])
        output[name] = {
            "replicates": replicates,
            "seed": seed,
            "percentile_interval": [float(lower), float(upper)],
            "estimator": (
                "Task-cluster bootstrap of the raw marginal risk difference "
                "from resampled task-level pass and access counts."
            ),
        }
    return output


def _bootstrap_task_frame(
    by_task: dict[str, pd.DataFrame],
    sampled_tasks: np.ndarray,
) -> pd.DataFrame:
    pieces: list[pd.DataFrame] = []
    for draw_index, task in enumerate(sampled_tasks):
        chunk = by_task[str(task)].copy()
        chunk["task_id"] = f"{task}#{draw_index}"
        pieces.append(chunk)
    return pd.concat(pieces, ignore_index=True)


_BOOT_BY_TASK = None
_BOOT_OUTCOME = None
_BOOT_START_PARAMS = None


def _init_gee_bootstrap(by_task, outcome, start_params):
    global _BOOT_BY_TASK, _BOOT_OUTCOME, _BOOT_START_PARAMS
    _BOOT_BY_TASK = by_task
    _BOOT_OUTCOME = outcome
    _BOOT_START_PARAMS = start_params


def _gee_bootstrap_worker(sampled_tasks):
    try:
        boot = _bootstrap_task_frame(_BOOT_BY_TASK, sampled_tasks)
        estimate = standardized_gee(
            boot,
            _BOOT_OUTCOME,
            start_params=_BOOT_START_PARAMS,
            maxiter=60,
        )
        value = float(estimate["risk_difference"])
        return value if np.isfinite(value) else None
    except Exception:
        return None


def task_cluster_gee_bootstrap(
    criterion: pd.DataFrame,
    outcome: str,
    replicates: int,
    seed: int,
    start_params: dict[str, float] | None = None,
) -> dict[str, float | int | list[float] | str]:
    tasks = sorted(criterion["task_id"].unique())
    by_task = {
        task: criterion[criterion["task_id"] == task].copy() for task in tasks
    }
    rng = np.random.default_rng(seed)
    sampled = [rng.choice(tasks, len(tasks), replace=True) for _ in range(replicates)]
    workers = max(1, min(4, (os.cpu_count() or 1) - 1))
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        if workers == 1 or replicates < 100:
            _init_gee_bootstrap(by_task, outcome, start_params)
            raw_values = [_gee_bootstrap_worker(draw) for draw in sampled]
        else:
            ctx = mp.get_context("fork") if "fork" in mp.get_all_start_methods() else mp.get_context()
            with ctx.Pool(
                processes=workers,
                initializer=_init_gee_bootstrap,
                initargs=(by_task, outcome, start_params),
            ) as pool:
                raw_values = pool.map(_gee_bootstrap_worker, sampled, chunksize=25)
    values = [float(value) for value in raw_values if value is not None and np.isfinite(value)]
    if len(values) < max(50, replicates // 4):
        raise RuntimeError(
            f"GEE bootstrap for {outcome} produced only {len(values)} finite replicates"
        )
    lower, upper = np.quantile(values, [0.025, 0.975])
    return {
        "replicates": replicates,
        "valid_replicates": len(values),
        "seed": seed,
        "percentile_interval": [float(lower), float(upper)],
        "estimator": (
            "Task-cluster bootstrap of the GEE-standardized risk difference. "
            "Each replicate resamples the eight tasks with replacement, refits "
            "the same logistic GEE, and re-standardizes over the three-agent panel."
        ),
    }


def raw_outcome_rates(criterion: pd.DataFrame) -> dict[str, dict[str, float]]:
    pass_rates = criterion.groupby("condition")["pass_int"].mean()
    observable = criterion[criterion["access_label"] != "unknown"]
    access_rates = observable.groupby("condition")["access_int"].mean()
    accessed = criterion[criterion["access_label"] == "accessed"]
    conditional_rates = accessed.groupby("condition")["pass_int"].mean()
    return {
        "criterion_pass": {
            condition: float(pass_rates[condition])
            for condition in CONDITIONS
        },
        "evidence_access_observed": {
            condition: float(access_rates[condition])
            for condition in CONDITIONS
        },
        "pass_given_access": {
            condition: float(conditional_rates[condition])
            for condition in CONDITIONS
        },
    }


def equal_task_sensitivity(
    criterion: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    pass_by_task = (
        criterion.groupby(["task_id", "condition"])["pass_int"]
        .mean()
        .unstack()
    )
    observable = criterion[criterion["access_label"] != "unknown"]
    access_by_task = (
        observable.groupby(["task_id", "condition"])["access_int"]
        .mean()
        .unstack()
    )

    def summarize(table: pd.DataFrame) -> dict[str, float]:
        world = float(table["world_first"].mean())
        task = float(table["task_first"].mean())
        return {
            "world_first": world,
            "task_first": task,
            "risk_difference": task - world,
        }

    return {
        "criterion_pass": summarize(pass_by_task),
        "evidence_access_observed": summarize(access_by_task),
    }


def unknown_access_sensitivity(
    criterion: pd.DataFrame,
) -> dict[str, dict[str, float]]:
    counts: dict[str, dict[str, int]] = {}
    for condition in CONDITIONS:
        subset = criterion[criterion["condition"] == condition]
        counts[condition] = {
            "total": len(subset),
            "accessed": int((subset["access_label"] == "accessed").sum()),
            "unknown": int((subset["access_label"] == "unknown").sum()),
        }

    def rate(condition: str, unknown_accessed: bool) -> float:
        values = counts[condition]
        numerator = values["accessed"]
        if unknown_accessed:
            numerator += values["unknown"]
        return numerator / values["total"]

    scenarios = {
        "all_unknown_accessed": {
            condition: rate(condition, True)
            for condition in CONDITIONS
        },
        "all_unknown_not_accessed": {
            condition: rate(condition, False)
            for condition in CONDITIONS
        },
        "condition_adversarial_lower": {
            "world_first": rate("world_first", True),
            "task_first": rate("task_first", False),
        },
        "condition_adversarial_upper": {
            "world_first": rate("world_first", False),
            "task_first": rate("task_first", True),
        },
    }
    for values in scenarios.values():
        values["risk_difference"] = (
            values["task_first"] - values["world_first"]
        )
    return scenarios


def curator_submitted_jaccard(matched: dict) -> dict[str, float | list[float]]:
    by_task: dict[str, list[set[tuple[str, str]]]] = {}
    for packet in matched["packet_construction"]:
        sources = {
            (source["surface"], source["locator"])
            for source in packet["as_submitted_sources"]
        }
        by_task.setdefault(packet["task_id"], []).append(sources)
    values: list[float] = []
    for task in sorted(by_task):
        left, right = by_task[task]
        values.append(len(left & right) / len(left | right))
    return {
        "by_task": values,
        "mean": float(np.mean(values)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
    }


def main() -> None:
    args = parse_args()
    criterion = pd.read_csv(DATA / "criterion_results.csv")
    runs = pd.read_csv(DATA / "run_ledger.csv")
    matched = json.loads((DATA / "matched_results.json").read_text())

    if len(criterion) != 1_728 or len(runs) != 192:
        raise ValueError("unexpected frozen-ledger dimensions")
    criterion["pass_int"] = criterion["pass"].astype(int)
    criterion["access_int"] = (
        criterion["access_label"] == "accessed"
    ).astype(int)

    pass_gee = standardized_gee(criterion, "pass_int")
    access_data = criterion[criterion["access_label"] != "unknown"].copy()
    access_gee = standardized_gee(access_data, "access_int")
    raw = raw_outcome_rates(criterion)
    pass_boot = task_cluster_gee_bootstrap(
        criterion,
        "pass_int",
        replicates=args.bootstrap_replicates,
        seed=args.bootstrap_seed,
        start_params=pass_gee["coefficients"],
    )
    access_boot = task_cluster_gee_bootstrap(
        access_data,
        "access_int",
        replicates=args.bootstrap_replicates,
        seed=args.bootstrap_seed,
        start_params=access_gee["coefficients"],
    )
    raw_bootstrap = task_cluster_raw_bootstrap(
        criterion,
        replicates=args.bootstrap_replicates,
        seed=args.bootstrap_seed,
    )
    conditional_rd = (
        raw["pass_given_access"]["task_first"]
        - raw["pass_given_access"]["world_first"]
    )

    result = {
        "schema": "eval-worlds-analysis-results/v1",
        "source": {
            "criterion_results": "data/criterion_results.csv",
            "run_ledger": "data/run_ledger.csv",
            "matched_results": "data/matched_results.json",
        },
        "methods": {
            "point_estimates": (
                "Logistic GEE with exchangeable task correlation and "
                "condition and agent fixed effects; probabilities are "
                "standardized equally over the three-agent panel."
            ),
            "intervals": (
                "Percentile task-cluster bootstrap of the GEE-standardized "
                "risk difference. Each draw resamples the eight tasks with "
                "replacement, refits the same logistic GEE, and re-standardizes "
                "over the three-agent panel."
            ),
            "bootstrap_replicates": args.bootstrap_replicates,
            "bootstrap_seed": args.bootstrap_seed,
        },
        "primary_outcomes": {
            "criterion_pass": {
                "raw": raw["criterion_pass"],
                "standardized_gee": pass_gee,
                "task_cluster_bootstrap": pass_boot,
            },
            "evidence_access_observed": {
                "raw": raw["evidence_access_observed"],
                "standardized_gee": access_gee,
                "task_cluster_bootstrap": access_boot,
            },
        },
        "descriptive_decomposition": {
            "pass_given_access": {
                "raw": raw["pass_given_access"],
                "risk_difference": float(conditional_rd),
                "task_cluster_bootstrap": raw_bootstrap["pass_given_access"],
                "post_treatment": True,
            }
        },
        "equal_task_sensitivity": equal_task_sensitivity(criterion),
        "access_unknown_sensitivity": unknown_access_sensitivity(criterion),
        "curator_submitted_source_jaccard": curator_submitted_jaccard(
            matched
        ),
        "software": {
            package: version(package)
            for package in [
                "numpy",
                "pandas",
                "scipy",
                "statsmodels",
            ]
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"wrote {args.output}")
    for name, outcome in result["primary_outcomes"].items():
        gee = outcome["standardized_gee"]
        interval = outcome["task_cluster_bootstrap"][
            "percentile_interval"
        ]
        print(
            name,
            f"{100 * gee['world_first']:.1f}% -> "
            f"{100 * gee['task_first']:.1f}%; "
            f"RD {100 * gee['risk_difference']:.1f} pp "
            f"[{100 * interval[0]:.1f}, {100 * interval[1]:.1f}]",
        )


if __name__ == "__main__":
    main()
