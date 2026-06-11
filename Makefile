PYTHON ?= python3

.PHONY: test lint format typecheck check

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check src/patchsmith tests
	$(PYTHON) -m ruff format --check src/patchsmith tests

format:
	$(PYTHON) -m ruff check --fix src/patchsmith tests
	$(PYTHON) -m ruff format src/patchsmith tests

typecheck:
	$(PYTHON) -m mypy

check: lint typecheck test
