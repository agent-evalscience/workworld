# Artifact scope

This release is designed to make the reported WorkWorlds study auditable without publishing proprietary production infrastructure or restricted organizational material.

## Included

The release includes:

- manuscript source, bibliography, and figures;
- de-identified criterion-level outcomes for 1,728 criterion executions, including a deterministic `criterion_record_sha256` digest of each released criterion record;
- a de-identified run-level ledger for 192 completed runs, including `run_record_sha256` record integrity digests;
- an attempt ledger for the 192 completed runs, including retries after transient execution failures;
- independent evidence-map reviewer sheets, a frozen final evidence map, grader and access-label audit sheets with sampling manifests, and sanitized agent/grader config files;
- aggregate construction-validation, GEE, bootstrap, task-, agent-, and curator-sensitivity outputs;
- code reproducing the released statistical analyses from the released ledgers;
- schemas for released result objects;
- a simplified illustrative implementation of the high-level WorkWorld construction contract on a fully fictional world, abstracted from the production codebase with generative-AI assistance;
- deterministic conformance and isolation tests; and
- release-integrity checks for required files and frozen study counts.

The illustrative implementation demonstrates the concepts described in the paper: revision, date, employee-seat projection, task overlays, candidate/verifier separation, explicit grading routes, and multiple surfaces backed by one compiled projection.

## Not included

The release does not include:

- the production WorkWorlds implementation;
- the production organizational-world builder;
- production materialization, permission, execution, or tool-integration code;
- the measured PharmaCo organizational corpus or restricted source materials;
- held-out verifier evidence or verifier truth for the measured tasks;
- raw agent trajectories that can expose restricted organizational content; or
- production credentials, provider configuration, or internal deployment metadata.

## Relationship between the demonstration and production system

The code under `reference/` was produced with generative-AI assistance by abstracting the authors' production WorkWorlds codebase down to the published construction contract. It is a simplified derivative rather than the production implementation: it depends only on the Python standard library, does not import production modules, and omits production materialization, permission, execution, and tool-integration logic. Passing the reference tests shows that the toy implementation satisfies the published high-level invariants. It is not evidence that the proprietary production implementation is identical to the demonstration.

Production-world validation is reported separately in the manuscript. The reference-world tests are included so that the construction contract can be executed and inspected without access to the measured organization.

## Reproducibility claim

The artifact supports independent recomputation of the released outcome summaries and statistical analyses, inspection of the experimental protocol and validation results, and execution of a high-level demonstration of the construction contract. It does not provide implementation-level reproduction of the proprietary production infrastructure.

## Record integrity

The `run_record_sha256` and `criterion_record_sha256` fields hash the corresponding released CSV records. Canonicalization uses UTF-8 JSON with sorted keys, compact separators, string-valued CSV fields, and every `*_sha256` field excluded. These hashes verify release-record integrity; no raw trajectory, candidate-output, or grader-output body is supplied or implied. Construction-validation fingerprints describe the shared reference world and cannot be independently recomputed without its withheld corpus.
