"""
Dense (semantic) retrieval with the multilingual-e5-small embedding model.

Each passage and each question is turned into a 384-number vector ("embedding") so that texts
with similar meaning end up close together even if they share no words (also works across
Hindi/English). Vectors are L2-normalised, so cosine similarity = a simple dot product.
Passage embeddings are cached in data/processed/ keyed by a hash of each chunk, so only new
or edited chunks are re-embedded. The model is loaded once (singleton).
"""
from __future__ import annotations

import threading

import numpy as np

from src import config
from src.ingest.ingest import chunk_hash

_MODEL = None
_LOCK = threading.Lock()


def get_model():
    """Load the sentence-transformers model once per process (CPU)."""
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            from sentence_transformers import SentenceTransformer
            _MODEL = SentenceTransformer(config.EMBED_MODEL, device="cpu")
    return _MODEL


def embed_queries(texts: list[str]) -> np.ndarray:
    # e5 models are trained with these prefixes; leaving them out hurts quality.
    return get_model().encode([f"query: {t}" for t in texts], normalize_embeddings=True,
                              batch_size=32, convert_to_numpy=True).astype(np.float32)


def embed_passages(texts: list[str]) -> np.ndarray:
    return get_model().encode([f"passage: {t}" for t in texts], normalize_embeddings=True,
                              batch_size=32, convert_to_numpy=True,
                              show_progress_bar=len(texts) > 64).astype(np.float32)


class DenseIndex:
    """Embedding matrix for all chunks + cosine-similarity search."""

    def __init__(self, chunks: list[dict], cache_dir=None):
        self.chunks = chunks
        slug = config.EMBED_MODEL.replace("/", "__")
        self.cache_path = (cache_dir or config.PROCESSED_DIR) / f"emb_{slug}.npz"
        self.matrix = self._load_or_build()

    def _load_or_build(self) -> np.ndarray:
        hashes = [chunk_hash(c) for c in self.chunks]
        cached: dict[str, np.ndarray] = {}
        if self.cache_path.exists():
            data = np.load(self.cache_path, allow_pickle=False)
            cached = {h: v for h, v in zip(data["hashes"], data["vectors"])}
        missing = [i for i, h in enumerate(hashes) if h not in cached]
        if missing:
            texts = [f"{self.chunks[i]['title']}. {self.chunks[i]['text']}" for i in missing]
            vecs = embed_passages(texts)
            for i, v in zip(missing, vecs):
                cached[hashes[i]] = v
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            keep = list(dict.fromkeys(hashes))  # only store vectors for current chunks
            np.savez(self.cache_path, hashes=np.array(keep), vectors=np.stack([cached[h] for h in keep]))
        if not hashes:
            return np.zeros((0, 384), dtype=np.float32)
        return np.stack([cached[h] for h in hashes]).astype(np.float32)

    def search(self, query: str, k: int = 50) -> list[tuple[int, float]]:
        if len(self.chunks) == 0:
            return []
        q = embed_queries([query])[0]
        scores = self.matrix @ q
        order = np.argsort(-scores)[:k]
        return [(int(i), float(scores[i])) for i in order]
