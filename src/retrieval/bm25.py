"""
BM25 keyword retrieval (the classic "search engine" scoring).

BM25 scores a passage higher when it contains the query's words, especially rare words.
Our tokenizer keeps legal section numbers such as "80ccd(1b)", "87a" or "115bac" as single
tokens (a normal tokenizer would split them and lose the meaning), turns "75,000" into
"75000", and removes a small list of very common English/Hinglish stopwords.
"""
from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am", "of", "in", "on", "at",
    "to", "for", "and", "or", "by", "with", "as", "it", "its", "this", "that", "these",
    "those", "i", "me", "my", "we", "our", "you", "your", "he", "she", "they", "them", "do",
    "does", "did", "can", "could", "should", "would", "will", "shall", "may", "might", "what",
    "which", "who", "whom", "how", "when", "where", "why", "there", "here", "from", "so",
    "if", "then", "than", "but", "not", "no", "yes", "any", "some", "all", "about", "into",
    "under", "also", "please", "tell", "know", "want", "need", "get", "have", "has", "had",
    # Hinglish grammar words
    "hai", "hain", "kya", "ka", "ki", "ke", "ko", "se", "mein", "me", "toh", "to", "bhi",
    "aur", "ya", "hota", "hoti", "hoga", "tha", "wala", "wali", "wale", "mujhe", "mera", "meri",
}

# section-like tokens first (80ccd(1b), 10(13a), 87a), then plain words / numbers
TOKEN_RE = re.compile(r"\d+[a-z]*(?:\([0-9a-z]+\))+|\d+[a-z]+|[^\W\d_]+|\d+(?:\.\d+)?")


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    """Lowercase, glue Indian-format numbers (12,00,000 -> 1200000), keep section numbers intact."""
    t = text.lower()
    t = re.sub(r"(?<=\d),(?=\d)", "", t)           # 75,000 -> 75000
    t = re.sub(r"(\d+[a-z]*)\s+\((\w{1,4})\)", r"\1(\2)", t)  # "80ccd (1b)" -> "80ccd(1b)"
    toks = TOKEN_RE.findall(t)
    if keep_stopwords:
        return toks
    return [w for w in toks if w not in STOPWORDS]


def chunk_to_text(chunk: dict) -> str:
    """The text we index for a chunk: title + section + passage."""
    sec = f"section {chunk['section']}" if chunk.get("section") else ""
    return f"{chunk.get('title', '')} {sec} {chunk.get('text', '')}"


class BM25Index:
    """Keyword index over all chunks. search() returns [(chunk_index, score), ...] best first."""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.docs = [tokenize(chunk_to_text(c)) for c in chunks]
        self.bm25 = BM25Okapi(self.docs) if chunks else None

    def search(self, query: str, k: int = 50) -> list[tuple[int, float]]:
        q = tokenize(query)
        if not q or self.bm25 is None:
            return []
        scores = self.bm25.get_scores(q)
        order = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in order if scores[i] > 0]
