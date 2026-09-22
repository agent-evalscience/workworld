# Illustrative reference implementation

This directory contains a simplified, public-safe demonstration of the high-level WorkWorld construction contract described in the paper. It was produced with generative-AI assistance by abstracting the authors' production WorkWorlds codebase down to that contract.

It uses a fully fictional world (`northstar-r1`) and demonstrates:

- revision/date/employee-seat materialization;
- role-dependent visibility;
- task overlays applied after the world projection is fixed;
- candidate/verifier separation;
- explicit deterministic and semantic grading routes; and
- filesystem-like and record-like surfaces backed by one compiled projection.

It is not the production WorkWorlds implementation, depends only on the Python standard library, and is not a reconstruction of PharmaCo.

From the release directory:

```bash
PYTHONPATH=reference python -m unittest discover -s reference/tests -v
PYTHONPATH=reference python reference/isolation_adversaries.py
```

Expected results are five passing unit tests (12 assertions) and `6/6` detected seeded isolation adversaries.
