# TaxSaathi — common commands. Run from the project root (on the VPS: /opt/taxsaathi).
PY ?= .venv/bin/python

.PHONY: setup ingest train-intent test eda experiments experiments-gen tune test-split serve all

setup:            ## create venv and install dependencies (CPU torch)
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
	.venv/bin/pip install -r requirements.txt

ingest:           ## data/raw/curated/*.md (+ pdfs) -> data/processed/chunks.jsonl
	$(PY) -m src.ingest.ingest

train-intent:     ## train TF-IDF + LogReg intent classifier
	$(PY) -m src.guardrails.intent --train

test:             ## unit tests
	$(PY) -m pytest -q

eda:              ## figures + docs/eda.md
	$(PY) -m scripts.eda

tune:             ## tune refusal threshold on dev
	$(PY) -m experiments.run_experiments --tune-threshold

experiments:      ## retrieval/refusal metrics B1..C5 on dev
	$(PY) -m experiments.run_experiments

experiments-gen:  ## + LLM answers, B0..C5 on dev (slow)
	$(PY) -m experiments.run_experiments --generate

test-split:       ## final numbers on the held-out test split (run once)
	$(PY) -m experiments.run_experiments --split test --generate

serve:            ## API + UI on port 8000
	$(PY) -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

all: ingest train-intent test eda tune experiments
