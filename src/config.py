"""
Central configuration for TaxSaathi.

Every path, model name, "today" date and tunable threshold lives here so that the rest of
the code never hard-codes them. Values can be overridden with environment variables
(handy on the VPS) and the refusal threshold can be overridden by the file written by
`python -m experiments.run_experiments --tune-threshold`.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parent.parent
KB_DIR = Path(os.environ.get("TAXSAATHI_KB_DIR", ROOT / "data" / "raw" / "curated"))
PDF_DIR = ROOT / "data" / "raw" / "pdfs"
PROCESSED_DIR = ROOT / "data" / "processed"
CHUNKS_PATH = Path(os.environ.get("TAXSAATHI_CHUNKS", PROCESSED_DIR / "chunks.jsonl"))
EVAL_DIR = ROOT / "data" / "eval"
INTENT_TRAIN_PATH = EVAL_DIR / "intent_train.jsonl"
INTENT_MODEL_PATH = PROCESSED_DIR / "intent.joblib"
THRESHOLD_PATH = PROCESSED_DIR / "threshold.json"
LOG_DIR = ROOT / "logs"
STATIC_DIR = ROOT / "app" / "static"
RESULTS_PATH = ROOT / "experiments" / "results.json"
MLRUNS_DIR = ROOT / "experiments" / "mlruns"

# ---------------------------------------------------------------- "today"
# The system pretends today is 2026-10-29 (see SPEC). Used for "last year", "now", defaults.
TODAY = date.fromisoformat(os.environ.get("TAXSAATHI_TODAY", "2026-10-29"))

# ---------------------------------------------------------------- models
EMBED_MODEL = os.environ.get("TAXSAATHI_EMBED", "intfloat/multilingual-e5-small")
RERANK_MODEL = os.environ.get("TAXSAATHI_RERANKER", "BAAI/bge-reranker-base")
LLM_MODEL = os.environ.get("TAXSAATHI_LLM", "qwen2.5:3b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
LLM_TIMEOUT_S = float(os.environ.get("TAXSAATHI_LLM_TIMEOUT", "90"))
LLM_NUM_PREDICT = int(os.environ.get("TAXSAATHI_NUM_PREDICT", "220"))

# ---------------------------------------------------------------- retrieval knobs
FIRST_STAGE_K = 50   # how many hits BM25 / dense each return before fusion
RRF_K = 60           # the "k" constant in Reciprocal Rank Fusion
RERANK_POOL = 20     # fused candidates sent to the cross-encoder
FINAL_K = 5          # passages counted by the retrieval metrics (Recall@5)
# Passages actually shown to the LLM. Fewer passages = shorter prompt = much faster on CPU.
GEN_K = int(os.environ.get("TAXSAATHI_GEN_K", "3"))

# ---------------------------------------------------------------- refusal threshold
# bge-reranker-base returns raw logits (roughly -11 .. +11). Below this value we say the
# knowledge base does not really answer the question. Tuned on the dev set with
# `--tune-threshold`; the tuned value (if any) is read from data/processed/threshold.json.
DEFAULT_RERANK_THRESHOLD = -2.0


def rerank_threshold() -> float:
    """Return the refusal threshold: env var > tuned file > default."""
    if "TAXSAATHI_RERANK_THRESHOLD" in os.environ:
        return float(os.environ["TAXSAATHI_RERANK_THRESHOLD"])
    if THRESHOLD_PATH.exists():
        try:
            return float(json.loads(THRESHOLD_PATH.read_text())["rerank_threshold"])
        except (KeyError, ValueError, json.JSONDecodeError):
            pass
    return DEFAULT_RERANK_THRESHOLD


# ---------------------------------------------------------------- user-facing text
DISCLAIMER = (
    "TaxSaathi gives general information from official sources, not professional advice. "
    "Please verify with the Income Tax Department / GST portal or a Chartered Accountant "
    "before filing."
)
CA_ESCALATION = (
    "For this, please consult a Chartered Accountant (CA) or a GST practitioner. You can "
    "find a CA through the ICAI directory (icai.org) or use the Income Tax Department "
    "helpline 1800 103 0025."
)

# Human-readable names for the `law` field of chunks (used in prompts and the UI).
LAW_NAMES = {
    "new_act": "Income-tax Act, 2025",
    "old_act": "Income-tax Act, 1961",
    "gst": "GST law (CGST Act, 2017 and rate notifications)",
    "mapping": "Old-to-new section mapping (1961 Act to 2025 Act)",
    "general": "General guidance",
}
