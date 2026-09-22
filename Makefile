PYTHON ?= python3

.PHONY: verify test analyze

verify:
	$(PYTHON) scripts/verify_release.py

test:
	$(PYTHON) -m unittest discover -s tests -v
	PYTHONPATH=reference $(PYTHON) -m unittest discover -s reference/tests -v
	PYTHONPATH=reference $(PYTHON) reference/isolation_adversaries.py

analyze:
	$(PYTHON) analysis/analyze_results.py
