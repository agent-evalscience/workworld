#!/usr/bin/env python3
"""Derive manuscript and index-page numbers from the frozen result files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "analysis"))

from release_audit_utils import grader_audit_summary  # noqa: E402


def pct(value: float, digits: int = 1) -> str:
    return f"{100 * value:.{digits}f}"


def pp(value: float, digits: int = 1) -> str:
    return f"{100 * value:.{digits}f}"


def tex_escape_ci(low: float, high: float) -> str:
    return f"{pp(low)} to {pp(high)}"


def signed_pp(value: float, digits: int = 1) -> str:
    return f"{100 * value:+.{digits}f}"


def replace_marked_block(text: str, start: str, end: str, replacement: str) -> str:
    pattern = re.compile(
        rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL
    )
    if not pattern.search(text):
        raise RuntimeError(f"Could not find marked block: {start} ... {end}")
    return pattern.sub(replacement, text, count=1)


def main() -> None:
    analysis = json.loads((DATA / "analysis_results.json").read_text())
    validation = json.loads((DATA / "validation_results.json").read_text())
    matched = json.loads((DATA / "matched_results.json").read_text())
    grader = grader_audit_summary(pd.read_csv(DATA / "grader_audit_ratings.csv"))
    runs = pd.read_csv(DATA / "run_ledger.csv")
    evidence = validation["evidence_map"]
    access = matched["access_label_audit"]
    pass_gee = analysis["primary_outcomes"]["criterion_pass"]["standardized_gee"]
    access_gee = analysis["primary_outcomes"]["evidence_access_observed"]["standardized_gee"]
    pass_ci = analysis["primary_outcomes"]["criterion_pass"]["task_cluster_bootstrap"][
        "percentile_interval"
    ]
    access_ci = analysis["primary_outcomes"]["evidence_access_observed"][
        "task_cluster_bootstrap"
    ]["percentile_interval"]
    cond = analysis["descriptive_decomposition"]["pass_given_access"]["raw"]
    search = runs.groupby("condition")[
        ["files_inspected", "tool_calls", "tool_calls_before_first_access"]
    ].mean()

    packets = matched["packet_construction"]
    sizes = [p["final_packet_size"] for p in packets]
    by_task: dict[str, list[set[tuple[str, str]]]] = {}
    for packet in packets:
        sources = {
            (item["surface"], item["locator"])
            for item in packet["as_submitted_sources"]
        }
        by_task.setdefault(packet["task_id"], []).append(sources)
    jaccards = []
    differ = 0
    for left, right in by_task.values():
        jaccards.append(len(left & right) / len(left | right))
        differ += int(left != right)
    c1 = [p["final_packet_size"] for p in packets if p["curator_id"] == "curator-1"]
    c2 = [p["final_packet_size"] for p in packets if p["curator_id"] == "curator-2"]
    missing = sum(p["missing_criteria"] for p in packets)
    total_pairs = sum(p["total_criteria"] for p in packets)
    revised = sum(int(p["generic_revision_requested"]) for p in packets)
    added = sum(len(p["repair_sources_added"]) for p in packets)

    contingency = grader["contingency"]
    by_cond = grader["by_condition"]
    macros = {
        "WWPassFull": pct(pass_gee["world_first"]),
        "WWPassCur": pct(pass_gee["task_first"]),
        "WWPassRD": pp(pass_gee["risk_difference"]),
        "WWPassCI": tex_escape_ci(pass_ci[0], pass_ci[1]),
        "WWAccessFull": pct(access_gee["world_first"]),
        "WWAccessCur": pct(access_gee["task_first"]),
        "WWAccessRD": pp(access_gee["risk_difference"]),
        "WWAccessCI": tex_escape_ci(access_ci[0], access_ci[1]),
        "WWPassGivenFull": pct(cond["world_first"]),
        "WWPassGivenCur": pct(cond["task_first"]),
        "WWRevOneSolvable": str(evidence["reviewer_1_solvable"]),
        "WWRevTwoSolvable": str(evidence["reviewer_2_solvable"]),
        "WWEvidenceAgreeN": str(
            evidence["solvability_contingency"]["both_solvable"]
            + evidence["solvability_contingency"]["both_not_solvable"]
        ),
        "WWEvidenceAgreePct": pct(evidence["solvability_exact_agreement"]),
        "WWKappa": f"{evidence['solvability_kappa']:.2f}",
        "WWACOne": f"{evidence['solvability_gwet_ac1']:.2f}",
        "WWKappaCILow": f"{evidence['solvability_kappa_bootstrap_ci']['lower']:.2f}",
        "WWKappaCIHigh": f"{evidence['solvability_kappa_bootstrap_ci']['upper']:.2f}",
        "WWJaccardMean": f"{evidence['locator_jaccard_mean']:.2f}",
        "WWJaccardMedian": f"{evidence['locator_jaccard_median']:.2f}",
        "WWAdjudicated": str(evidence["adjudicated_criteria"]),
        "WWGraderN": str(grader["sampled"]),
        "WWGraderAgreePct": pct(grader["raw_agreement"]),
        "WWGraderKappa": f"{grader['cohen_kappa']:.2f}",
        "WWGraderFullAgreePct": pct(by_cond["world_first"]["raw_agreement"]),
        "WWGraderCurAgreePct": pct(by_cond["task_first"]["raw_agreement"]),
        "WWGraderOnlyPass": str(contingency["grader_only_pass"]),
        "WWExpertOnlyPass": str(contingency["expert_only_pass"]),
        "WWAccessN": str(access["sampled"]),
        "WWAccessUnknownN": str(access["unknown_sampled"]),
        "WWAccessAgreePct": pct(access["three_class_raw_agreement"]),
        "WWAccessKappa": f"{access['kappa']:.2f}",
        "WWAccessKappaCILow": f"{access['kappa_bootstrap_ci']['lower']:.2f}",
        "WWAccessKappaCIHigh": f"{access['kappa_bootstrap_ci']['upper']:.2f}",
        "WWAccessAutoAPct": pct(access["automated_vs_coder_a"]),
        "WWAccessAutoBPct": pct(access["automated_vs_coder_b"]),
        "WWSearchFilesFull": f"{search.loc['world_first','files_inspected']:.1f}",
        "WWSearchFilesCur": f"{search.loc['task_first','files_inspected']:.1f}",
        "WWSearchCallsFull": f"{search.loc['world_first','tool_calls']:.1f}",
        "WWSearchCallsCur": f"{search.loc['task_first','tool_calls']:.1f}",
        "WWSearchCBFAFull": f"{search.loc['world_first','tool_calls_before_first_access']:.1f}",
        "WWSearchCBFACur": f"{search.loc['task_first','tool_calls_before_first_access']:.1f}",
        "WWPacketMedian": str(int(np.median(sizes))),
        "WWPacketMin": str(min(sizes)),
        "WWPacketMax": str(max(sizes)),
        "WWPacketMeanCOne": f"{np.mean(c1):.1f}",
        "WWPacketMeanCTwo": f"{np.mean(c2):.1f}",
        "WWPacketJaccardMean": f"{np.mean(jaccards):.2f}",
        "WWPacketJaccardMin": f"{min(jaccards):.3f}".rstrip("0").rstrip("."),
        "WWPacketJaccardMax": f"{max(jaccards):.2f}",
        "WWPacketPairsDiffer": str(differ),
        "WWPacketsRevised": str(revised),
        "WWInitiallySufficient": f"{total_pairs - missing}/{total_pairs}",
        "WWAdjudicatorSources": str(added),
        "WWBootstrapDraws": str(analysis["methods"]["bootstrap_replicates"]),
    }
    lines = [
        "% Auto-generated from frozen result files. Do not edit by hand.",
        r"\makeatletter",
    ]
    for name, value in macros.items():
        lines.append(rf"\newcommand{{\{name}}}{{{value}}}")
    lines.append(r"\makeatother")
    (ROOT / "paper" / "generated_numbers.tex").write_text("\n".join(lines) + "\n")
    print("wrote paper/generated_numbers.tex")

    index_path = ROOT / "index.html"
    index = index_path.read_text()
    pass_full = 100 * pass_gee["world_first"]
    pass_cur = 100 * pass_gee["task_first"]
    access_full = 100 * access_gee["world_first"]
    access_cur = 100 * access_gee["task_first"]
    pass_given_full = 100 * cond["world_first"]
    pass_given_cur = 100 * cond["task_first"]
    inspect_full = float(search.loc["world_first", "files_inspected"])
    inspect_cur = float(search.loc["task_first", "files_inspected"])

    results_summary = f'''<!-- BEGIN AUTO-GENERATED RESULTS SUMMARY -->
            <div class="findings" aria-label="Main findings">
              <div><strong>{access_cur:.1f} → {access_full:.1f}%</strong><span>Sufficient-evidence access, task-curated subset → full projection.</span></div>
              <div><strong>{pass_cur:.1f} → {pass_full:.1f}%</strong><span>Criterion pass, task-curated subset → full projection.</span></div>
              <div><strong>{pass_given_cur:.1f} vs {pass_given_full:.1f}%</strong><span>Pass given observed evidence access was similar across conditions.</span></div>
            </div>
            <p class="result-reading"><strong>How to read this:</strong> arrows run from the task-curated subset to the full role-visible workplace. The higher values under curation do not indicate a better agent; they show that pre-selecting task-relevant information removes part of the information-localization work and raises measured performance. When that curation is removed, evidence access falls by {abs(100 * access_gee['risk_difference']):.1f} percentage points and criterion pass falls by {abs(100 * pass_gee['risk_difference']):.1f} points. Conditional pass is similar once sufficient evidence is reached, so the measured separation is concentrated in whether the agent reaches that evidence. The three tabs below correspond directly to the three interactive rows in the table; selecting either updates the same outcome view.</p>

            <div class="metric-switch" role="tablist" aria-label="Outcome explorer">
              <button type="button" class="active" data-metric="access">Access</button>
              <button type="button" data-metric="pass">Criterion pass</button>
              <button type="button" data-metric="inspect">Search burden</button>
            </div>
            <div class="metric-detail" id="metricDetail" aria-live="polite"></div>

            <div class="results-table-wrap" aria-label="Key experiment table">
              <table>
                <caption>Key matched-information outcomes. Read left to right as task-curated subset → full projection.</caption>
                <thead>
                  <tr>
                    <th>Outcome</th>
                    <th style="text-align:right;">Task-curated</th>
                    <th style="text-align:right;">Full projection</th>
                    <th style="text-align:right;">Change to full</th>
                  </tr>
                </thead>
                <tbody>
                  <tr data-metric-key="access"><td>Sufficient-evidence access</td><td class="num">{access_cur:.1f}%</td><td class="num">{access_full:.1f}%</td><td class="num">{signed_pp(-access_gee['risk_difference'])} pp</td></tr>
                  <tr data-metric-key="pass"><td>Criterion pass</td><td class="num">{pass_cur:.1f}%</td><td class="num">{pass_full:.1f}%</td><td class="num">{signed_pp(-pass_gee['risk_difference'])} pp</td></tr>
                  <tr class="context-row"><td>Pass given observed access</td><td class="num">{pass_given_cur:.1f}%</td><td class="num">{pass_given_full:.1f}%</td><td class="num">{signed_pp(cond['world_first'] - cond['task_first'])} pp</td></tr>
                  <tr data-metric-key="inspect"><td>Mean file / record inspections</td><td class="num">{inspect_cur:.1f}</td><td class="num">{inspect_full:.1f}</td><td class="num">{inspect_full - inspect_cur:+.1f}</td></tr>
                </tbody>
              </table>
            <!-- END AUTO-GENERATED RESULTS SUMMARY -->'''
    index = replace_marked_block(
        index,
        "<!-- BEGIN AUTO-GENERATED RESULTS SUMMARY -->",
        "<!-- END AUTO-GENERATED RESULTS SUMMARY -->",
        results_summary,
    )

    metrics = {
        "access": {
            "label": "Sufficient-evidence access",
            "full": round(access_full, 1),
            "curated": round(access_cur, 1),
            "max": 100,
            "unit": "%",
            "note": (
                f"Removing task-level curation lowers evidence access by {abs(100 * access_gee['risk_difference']):.1f} "
                f"percentage points; 95% task-cluster bootstrap interval for the decrease, "
                f"{abs(100 * access_ci[0]):.1f} to {abs(100 * access_ci[1]):.1f} points."
            ),
        },
        "pass": {
            "label": "Criterion pass",
            "full": round(pass_full, 1),
            "curated": round(pass_cur, 1),
            "max": 100,
            "unit": "%",
            "note": (
                f"Removing task-level curation lowers criterion pass by {abs(100 * pass_gee['risk_difference']):.1f} "
                f"percentage points; 95% task-cluster bootstrap interval for the decrease, "
                f"{abs(100 * pass_ci[0]):.1f} to {abs(100 * pass_ci[1]):.1f} points."
            ),
        },
        "inspect": {
            "label": "Mean file / record inspections",
            "full": round(inspect_full, 1),
            "curated": round(inspect_cur, 1),
            "max": max(30, int(np.ceil(max(inspect_full, inspect_cur) / 5) * 5)),
            "unit": "",
            "note": (
                f"Removing task-level curation increased file or record inspections "
                f"by {inspect_full - inspect_cur:.1f} per run on average."
            ),
        },
    }
    metrics_block = (
        "// BEGIN AUTO-GENERATED METRICS\n"
        "    const metrics = "
        + json.dumps(metrics, indent=2, ensure_ascii=False)
        + ";\n    // END AUTO-GENERATED METRICS"
    )
    index = replace_marked_block(
        index,
        "// BEGIN AUTO-GENERATED METRICS",
        "// END AUTO-GENERATED METRICS",
        metrics_block,
    )
    index_path.write_text(index)
    print("wrote index.html result summaries")


if __name__ == "__main__":
    main()
