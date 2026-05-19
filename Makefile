# Spurs vs Thunder — WCF 2026 analysis pipeline.
#
# Common workflows:
#   make            # full pipeline (= make update)
#   make update     # fetch + enrich + analyze, in order
#   make fetch      # just 01_fetch_data.py
#   make enrich     # just 02_clean.py
#   make analyze    # just 03_analyze.py
#   make setup      # one-time: create .venv and install deps
#   make help       # list available targets

PYTHON := .venv/bin/python

.PHONY: all update fetch enrich analyze setup help

all: update  ## Default: run the full pipeline

update: fetch enrich analyze  ## Run all three stages in order

fetch:  ## Pull latest team + player game logs from nba_api
	$(PYTHON) scripts/01_fetch_data.py

enrich:  ## Add context flags + derive four factors / pace / ratings
	$(PYTHON) scripts/02_clean.py

analyze:  ## Compute deltas + series prediction (prints copy-paste row)
	$(PYTHON) scripts/03_analyze.py

setup:  ## One-time: create .venv and install dependencies
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-10s  %s\n", $$1, $$2}'
