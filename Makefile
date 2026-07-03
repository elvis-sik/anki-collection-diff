SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON ?= python3
PYTHONPATH := src
export PYTHONPATH

.PHONY: help lint test check build twine-check

help:
	@printf "Available targets:\n"
	@printf "  make lint         Compile Python source and tests\n"
	@printf "  make test         Run unit tests\n"
	@printf "  make check        Run lint and tests\n"
	@printf "  make build        Build sdist and wheel\n"
	@printf "  make twine-check  Validate built distributions\n"

lint:
	@$(PYTHON) -m compileall -q src tests

test:
	@$(PYTHON) -m unittest discover -s tests -v

check: lint test

build:
	@$(PYTHON) -m build --no-isolation

twine-check:
	@$(PYTHON) -m twine check dist/*
