# Reproducing the matched analysis

From the release directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r analysis/requirements.txt
python analysis/analyze_results.py
```

The script reads the frozen criterion and run ledgers and writes `data/analysis_results.json`. It reproduces the released GEE-standardized marginal probabilities, 2,000-draw task-cluster bootstrap intervals that refit the same GEE on each replicate, equal-task-weighted and leave-one-task-out sensitivity estimates, agent- and curator-level summaries, pass conditional on observed evidence access, and unknown-access sensitivity bounds.

The bootstrap seed is 20270908. The frozen ledgers retain the internal labels `world_first` and `task_first`; these correspond to **full projection** and **task-curated subset** in the manuscript.

The manuscript reports a completed blinded semantic-grader audit and a separate access-label audit. Derived audit summaries are recomputed directly from the released ratings rather than stored as duplicate files. Their de-identified ratings are released in `data/grader_audit_ratings.csv` and `data/access_label_audit_ratings.csv`. `scripts/build_frozen_release.py` recomputes the audit summaries, and `scripts/sample_audits.py` reproduces the sampled row keys and inclusion probabilities from the declared seeds. Restricted source bodies and reviewer annotations are outside the public release boundary.

After recomputing the analysis, regenerate the numerical manuscript macros with `python scripts/sync_public_numbers.py` and the results figures with `python paper/figures/figure.py`. Figures 1 and 2 describe the study design and remain fixed.
