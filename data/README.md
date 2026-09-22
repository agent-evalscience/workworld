# Study data

| File | Contents |
| --- | --- |
| `criterion_results.csv` | 1,728 de-identified criterion executions, with `criterion_record_sha256` |
| `run_ledger.csv` | 192 de-identified completed-run summaries, with `run_record_sha256` |
| `attempt_ledger.csv` | Attempt records for the 192 completed runs, including retries |
| `task_mapping.csv` | Mapping from released task IDs to manuscript task labels |
| `analysis_results.json` | GEE estimates, GEE-refit task-cluster bootstrap intervals, and sensitivity analyses |
| `validation_results.json` | Experiment 1 infrastructure-validation summary |
| `matched_results.json` | Experiment 2 matched-study object |
| `tables/` | Task, agent, packet, and leave-one-task-out summaries |
| `schemas/` | JSON Schemas for released result objects |
| `configs/` | Sanitized grader and agent configuration files; hashes must match the study object |
| `evidence_map_reviewer_1.csv` | Reviewer 1's independent 72-row submission |
| `evidence_map_reviewer_2.csv` | Reviewer 2's independent 72-row submission |
| `evidence_map_final.csv` / `evidence_map_final.json` | Frozen post-adjudication sufficient sets, access rules, and freeze hash |
| `grader_audit_ratings.csv` | 240-row stratified semantic-grader audit (120 per condition) |
| `grader_audit_summary.json` | Agreement, Cohen's kappa, and disagreement counts recomputed from `grader_audit_ratings.csv` |
| `grader_audit_sample_manifest.csv` | Sample-selection seed, stratum, and inclusion probability |
| `access_label_coder_a.csv` / `access_label_coder_b.csv` | Independent coder submissions |
| `access_label_audit_ratings.csv` | Combined 346-row access-label audit with frozen automated labels |
| `access_audit_sample_manifest.csv` | Access-audit sampling seed, stratum, and inclusion probability |
| `packet_revisions.csv` | Packet history: submitted → completeness review → curator revision → adjudicator → final |

Agent identifiers in the ledgers are `opus5`, `grok`, and `sol`.


## Task IDs

| task_id | Manuscript task label |
| --- | --- |
| `T01` | stability update |
| `T02` | overwrap position |
| `T03` | validation defense |
| `T04` | authority response |
| `T05` | records integrity |
| `T06` | supplier-change audit |
| `T07` | qualification sweep |
| `T08` | shelf-life assessment |

Criterion identifiers follow the pattern `<task_id>-R<nn>`. Task and criterion identifiers were renamed to this uniform scheme for the public release; the renaming preserves the sort order of the frozen identifiers, so the recorded audit-sampling seeds reproduce the same selections. The `criterion_freeze_hash` and `map_freeze_hash` values are reported exactly as recorded when the evidence map was frozen and were computed over the pre-release identifiers; the `*_record_sha256` digests were recomputed over the released records.

`EMP-QC-001` has no task-agnostic tool bundle, so `tool_bundle_sha256` is `null` for all three of its repeated materializations. Its workspace digest is still compared across all three materializations.

The frozen condition labels are retained for compatibility with the analysis scripts:

- `world_first` = full projection
- `task_first` = task-curated subset

`matched_results.json` records the semantic-grader model version, blinding indicators, the grader-configuration path, and the SHA-256 digest of that file. The release does not include the measured PharmaCo organizational corpus, held-out verifier evidence, raw trajectories containing restricted organizational content, or proprietary production infrastructure.

## Record integrity

The `run_record_sha256` and `criterion_record_sha256` fields hash the corresponding released CSV records. Canonicalization uses UTF-8 JSON with sorted keys, compact separators, string-valued CSV fields, and every `*_sha256` field excluded. These hashes verify release-record integrity; no raw trajectory, candidate-output, or grader-output body is supplied or implied. Construction-validation fingerprints describe the shared reference world and cannot be independently recomputed without its withheld corpus.
