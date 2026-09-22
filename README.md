# WorkWorlds

**WorkWorlds: An Infrastructure for Evaluating AI Agents on Workplace Tasks**

Yining Hua (Harvard University; Agent Evaluation Science Inc.) · Levi Lian (Raycaster; Stanford University) · [arXiv:2609.23806](https://arxiv.org/abs/2609.23806) · [CC BY 4.0](LICENSE)

[Project page](index.html) · [arXiv paper](https://arxiv.org/abs/2609.23806) · [Study data](data/) · [Analysis](analysis/) · [Illustrative reference implementation](reference/) · [Artifact scope](ARTIFACT_SCOPE.md)

## Overview

WorkWorlds is an evaluation infrastructure for workplace agents in which the organization is fixed before the task. A world first fixes a revision, date, and employee seat and materializes the role-visible workplace; the task is then introduced on top of that projection. This release contains the public artifacts used to audit the paper's construction checks and matched information experiment.

The measured study uses PharmaCo, a fictional sterile-injectable pharmaceutical company, with 8 measured tasks across 6 employee seats. The paper also describes three additional organizational worlds: OncologyCo, DiagnosticsCo, and ClinicalSiteCo.

## Main result

Across 192 matched evaluations, the task-curated subset produced higher measured sufficient-evidence access (90.4% vs. 72.8%) and criterion pass (76.7% vs. 68.0%) than the full role-visible projection. Pass conditional on observed evidence access was similar: 82.7% under curation and 84.2% under the full projection. The higher curated values reflect the effect of pre-selecting task-relevant information on the evaluation, not a change in the underlying agent.

| Outcome | Task-curated subset | Full projection | Change to full |
| --- | ---: | ---: | ---: |
| Criterion pass, raw | 664/864 (76.9%) | 589/864 (68.2%) | -8.7 pp |
| Evidence access, raw | 767/848 (90.4%) | 614/842 (72.9%) | -17.5 pp |
| Pass given access | 82.7% | 84.2% | +1.5 pp |
| Mean file/record inspections | 15.2 | 28.6 | +13.4 |
| Mean tool calls before first access | 7.8 | 12.1 | +4.3 |

Read left to right as moving from the task-curated subset to the full role-visible projection. The primary statistical analysis reports the reverse contrast, curated minus full: +8.7 percentage points for criterion pass (95% task-cluster bootstrap interval 1.0 to 15.6) and +17.6 points for sufficient-evidence access (10.3 to 24.3).

## Repository structure

```text
workworlds/
├── README.md
├── ARTIFACT_SCOPE.md
├── CITATION.cff
├── LICENSE
├── MANIFEST.json
├── VALIDATION.txt
├── Makefile
├── analysis/          # statistical reproduction code
├── data/              # de-identified ledgers, outputs, tables, and schemas
├── paper/             # manuscript source, bibliography, and figures
├── reference/         # public-safe illustrative WorkWorld implementation
├── scripts/           # release-integrity checks
└── tests/             # release-structure tests
```

## Quick start

Python 3.10+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r analysis/requirements.txt
make verify
```

`make verify` checks the released ledger counts, runs the illustrative reference tests and seeded isolation checks, and recomputes the released statistical analysis.

To run the components separately:

```bash
make test
make analyze
```

## Released study artifacts

| Path | Contents |
| --- | --- |
| `data/criterion_results.csv` | 1,728 de-identified criterion executions |
| `data/run_ledger.csv` | 192 de-identified completed-run summaries |
| `data/attempt_ledger.csv` | Attempt records for the 192 completed runs, including retries |
| `data/task_mapping.csv` | Mapping from released task IDs to manuscript task labels |
| `data/analysis_results.json` | GEE, GEE-refit bootstrap, and sensitivity estimates |
| `data/validation_results.json` | Construction-validation summary |
| `data/matched_results.json` | Matched-study result object |
| `data/evidence_map_final.json` | Frozen post-adjudication evidence map |
| `data/configs/` | Sanitized grader and agent configuration files |
| `data/tables/` | Task, agent, packet, and leave-one-task-out summaries |
| `data/schemas/` | JSON Schemas for released result objects |
| `analysis/` | Code reproducing the released statistical analyses |
| `reference/` | Illustrative implementation of the published construction contract |
| `paper/` | Manuscript source, references, and figures |

The frozen ledgers retain earlier internal condition names for analysis compatibility:

- `world_first` = **full projection**
- `task_first` = **task-curated subset**

## Illustrative reference implementation

`reference/` is a simplified, public-safe implementation of the high-level WorkWorld construction contract on a fully fictional world. It was produced with generative-AI assistance by abstracting the authors' production WorkWorlds codebase down to the published construction contract. It demonstrates revision/date/seat projection, task overlays, candidate-verifier separation, explicit grading routes, and multiple surfaces backed by one compiled projection.

It is not the production WorkWorlds implementation: it depends only on the Python standard library, omits production materialization, permission, execution, and tool-integration logic, and does not reconstruct PharmaCo.

```bash
PYTHONPATH=reference python -m unittest discover -s reference/tests -v
PYTHONPATH=reference python reference/isolation_adversaries.py
```

The reference suite contains five tests with 12 assertions and a six-case deterministic isolation-adversary check.

## Reproducing the matched analysis

```bash
python analysis/analyze_results.py
```

The analysis reads the frozen criterion- and run-level ledgers and writes `data/analysis_results.json`. It reproduces the reported GEE-standardized marginal probabilities, 2,000-draw task-cluster bootstrap intervals that refit the same GEE on each replicate, equal-task-weighted and leave-one-task-out sensitivity estimates, agent- and curator-level summaries, pass conditional on observed evidence access, and unknown-access sensitivity bounds. The bootstrap seed is `20270908`.

## Release boundary

The public artifact does not include the production WorkWorlds implementation, production world builder, production materialization or permission logic, execution infrastructure, tool integrations, the measured PharmaCo organizational corpus, restricted source materials, held-out verifier evidence, or raw trajectories containing organizational content.

See [ARTIFACT_SCOPE.md](ARTIFACT_SCOPE.md) for the exact public/private boundary.

## Citation

The latest preprint is [arXiv:2609.23806](https://arxiv.org/abs/2609.23806). Citation metadata is also provided in [`CITATION.cff`](CITATION.cff).

```bibtex
@misc{hua2026workworlds,
  title        = {WorkWorlds: An Infrastructure for Evaluating AI Agents on Workplace Tasks},
  author       = {Yining Hua and Levi Lian},
  year         = {2026},
  eprint       = {2609.23806},
  archivePrefix= {arXiv},
  primaryClass = {cs.AI},
  url          = {https://arxiv.org/abs/2609.23806}
}
```

## License

This release is distributed under [CC BY 4.0](LICENSE).
