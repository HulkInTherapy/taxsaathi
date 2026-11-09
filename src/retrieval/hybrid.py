"""
Hybrid retrieval: combine BM25 and dense rankings with Reciprocal Rank Fusion (RRF).

BM25 is good at exact terms ("80CCD(1B)", "GSTR-3B"); dense search is good at meaning and
paraphrases. RRF merges the two ranked lists without having to compare their (very different)
scores: each passage gets sum(1 / (k + rank)) over the lists it appears in, with k = 60.
This module also holds the "section boost" that adds old-to-new mapping chunks.
"""
from __future__ import annotations

import re

from src.retrieval.bm25 import tokenize


def rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """rankings: lists of chunk indices, best first. Returns [(index, rrf_score)] best first."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: -kv[1])


def _mentions_section(chunk: dict, section: str) -> bool:
    """Does the chunk's section field or text mention e.g. '80C' as a whole token?"""
    sec_tok = tokenize(section, keep_stopwords=True)
    if not sec_tok:
        return False
    target = sec_tok[0]
    if (chunk.get("section") or "").replace(" ", "").lower() == target:
        return True
    hay = set(tokenize(f"{chunk.get('title', '')} {chunk.get('text', '')} {chunk.get('section', '')}",
                       keep_stopwords=True))
    if target in hay:
        return True
    # "80ccd" in text should also match a query for "80CCD(1B)" and vice versa
    base = re.sub(r"\(.*", "", target)
    return any(re.sub(r"\(.*", "", h) == base and h[:1].isdigit() for h in hay) if base != target else False


def section_boost(chunks: list[dict], sections: list[str], pool: list[int], max_add: int = 4) -> list[int]:
    """Indices of mapping chunks (law == 'mapping') that mention one of the user's section
    numbers and are not already in the candidate pool. The 2025 Act renumbered sections
    (e.g. old 80C), so the mapping chunk tells the reader the new number."""
    if not sections:
        return []
    have = set(pool)
    added = []
    for i, c in enumerate(chunks):
        if i in have or c.get("law") != "mapping":
            continue
        if any(_mentions_section(c, s) for s in sections):
            added.append(i)
            if len(added) >= max_add:
                break
    return added
