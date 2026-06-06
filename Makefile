# `make verify` is the single verification command and the only definition of
# "done". It delegates to verify.py so the exact same pipeline runs whether or
# not `make` is installed. On Windows / PowerShell where `make` is absent, run
# the canonical command directly:  python verify.py
#
# Stages (see verify.py): pytest -> build -> validate --strict -> catalog --reconcile

PYTHON ?= python

.PHONY: verify build validate catalog test fmt clean

verify:
	$(PYTHON) verify.py

# Iteration helpers so a loop need not regenerate the whole library each time.
build:
	$(PYTHON) -m wtfoundry.cli build --config presets.yaml

# Build a single family:  make only GEN=wavefold
only:
	$(PYTHON) -m wtfoundry.cli build --config presets.yaml --only $(GEN)

validate:
	$(PYTHON) -m wtfoundry.cli validate out --strict

catalog:
	$(PYTHON) -m wtfoundry.cli catalog out --reconcile

test:
	$(PYTHON) -m pytest -q

fmt:
	$(PYTHON) -m ruff format src tests
	$(PYTHON) -m ruff check --fix src tests

clean:
	$(PYTHON) -c "import shutil, glob, os; [shutil.rmtree(p, ignore_errors=True) for p in glob.glob('**/__pycache__', recursive=True)]"
