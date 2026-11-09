"""
Cross-encoder reranking with BAAI/bge-reranker-base.

The first-stage retrievers look at the question and passage separately; a cross-encoder reads
the question and a passage *together* and outputs one relevance score, which is slower but
much more accurate. We rerank the top-20 fused candidates and keep the best 5. The raw
score (a logit, roughly -11..+11) is also what the refusal gate compares to its threshold;
sigmoid() turns it into a 0..1 value for display.
"""
from __future__ import annotations

import os

import inspect
import math
import threading

from src import config

_MODEL = None
_LOCK = threading.Lock()


def get_model():
    """Load the cross-encoder once. We ask for raw logits (identity activation)."""
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            import torch
            from sentence_transformers import CrossEncoder
            params = inspect.signature(CrossEncoder.__init__).parameters
            kwargs = {"max_length": int(os.environ.get("TAXSAATHI_RERANK_MAXLEN", "384")), "device": "cpu"}
            # sentence-transformers renamed this argument across versions
            if "activation_fn" in params:
                kwargs["activation_fn"] = torch.nn.Identity()
            elif "default_activation_function" in params:
                kwargs["default_activation_function"] = torch.nn.Identity()
            _MODEL = CrossEncoder(config.RERANK_MODEL, **kwargs)
    return _MODEL


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _passage(chunk: dict, max_words: int = 300) -> str:
    words = chunk["text"].split()
    return f"{chunk['title']}. " + " ".join(words[:max_words])


def rerank(query: str, chunks: list[dict], indices: list[int]) -> list[tuple[int, float]]:
    """Score (query, passage) pairs. Returns [(chunk_index, raw_logit)] best first."""
    if not indices:
        return []
    pairs = [(query, _passage(chunks[i])) for i in indices]
    scores = get_model().predict(pairs, batch_size=16, show_progress_bar=False)
    ranked = sorted(zip(indices, (float(s) for s in scores)), key=lambda kv: -kv[1])
    return ranked
