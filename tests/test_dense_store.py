"""ChromaDB and numpy dense search must return the same ranking. Uses a fake embedder (no model download)."""
import hashlib

import numpy as np

from src.retrieval import dense


def _fake_embed(texts, prefix):
    out = []
    for t in texts:
        seed = int(hashlib.md5(t.split(" ", 1)[-1].encode()).hexdigest()[:8], 16)
        v = np.random.default_rng(seed).normal(size=384).astype(np.float32)
        out.append(v / np.linalg.norm(v))
    return np.stack(out)


def _chunks(n):
    return [{"id": f"C-{i}", "title": f"title {i}", "text": f"text number {i}", "law": "new_act"} for i in range(n)]


def test_chroma_matches_numpy(monkeypatch, tmp_path):
    monkeypatch.setattr(dense, "embed_passages", lambda t: _fake_embed(t, "passage"))
    # a query equal to a passage text must find that passage first
    monkeypatch.setattr(dense, "embed_queries", lambda t: _fake_embed(t, "query"))
    chunks = _chunks(40)
    np_idx = dense.DenseIndex(chunks, cache_dir=tmp_path, store="numpy")
    ch_idx = dense.DenseIndex(chunks, cache_dir=tmp_path, store="chroma", chroma_dir=tmp_path / "chroma")
    for q in ["title 3. text number 3", "something else", "title 17. text number 17"]:
        a, b = np_idx.search(q, k=10), ch_idx.search(q, k=10)
        assert [i for i, _ in a] == [i for i, _ in b]
        assert np.allclose([s for _, s in a], [s for _, s in b], atol=1e-4)
    assert ch_idx.search("title 3. text number 3", k=1)[0][0] == 3


def test_chroma_sync_removes_and_updates(monkeypatch, tmp_path):
    monkeypatch.setattr(dense, "embed_passages", lambda t: _fake_embed(t, "passage"))
    monkeypatch.setattr(dense, "embed_queries", lambda t: _fake_embed(t, "query"))
    dense.DenseIndex(_chunks(10), cache_dir=tmp_path, chroma_dir=tmp_path / "c", store="chroma")
    smaller = _chunks(6)
    smaller[2]["text"] = "edited text"
    idx = dense.DenseIndex(smaller, cache_dir=tmp_path, chroma_dir=tmp_path / "c", store="chroma")
    assert idx._collection.count() == 6
    assert idx.search("title 2. edited text", k=1)[0][0] == 2
