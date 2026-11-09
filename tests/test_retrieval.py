"""Tests for ingest (fixture KB), BM25 tokenizer/search, RRF fusion, date filter and boost."""
from datetime import date
from pathlib import Path

from src.ingest.ingest import parse_markdown, validate, load_all, split_long
from src.retrieval.bm25 import BM25Index, tokenize
from src.retrieval.date_filter import filter_by_period, is_eligible
from src.retrieval.hybrid import rrf, section_boost

FIXTURES = Path(__file__).parent / "fixtures" / "kb"


def fixture_chunks():
    return load_all(FIXTURES, None)


def test_ingest_parses_metadata():
    chunks = fixture_chunks()
    by_id = {c["id"]: c for c in chunks}
    assert len(chunks) == 7
    c = by_id["FX-IT25-202-SLABS"]
    assert c["section"] == "202" and c["law"] == "new_act" and c["effective_from"] == "2026-04-01"
    assert c["effective_to"] == "" and c["verified"] == "yes" and c["n_tokens"] > 40
    assert c["source_url"] == "https://example.org/fixture#s202"  # '#' inside URL kept
    assert by_id["FX-MAP-80C"]["law"] == "mapping"                 # per-chunk override
    assert by_id["FX-GST-CEMENT-OLD"]["section"] == ""
    errors, _ = validate(chunks)
    assert errors == []


def test_validate_catches_duplicates_and_bad_dates(tmp_path):
    (tmp_path / "a.md").write_text("---\ndoc_id: a\nlaw: gst\n---\n\n## [X-1] T\neffective_from: 2025-13-01\n\nsome text here\n\n## [X-1] T2\n\nmore text\n")
    errors, _ = validate(parse_markdown(tmp_path / "a.md"))
    assert any("duplicate" in e for e in errors)
    assert any("bad date" in e for e in errors)


def test_split_long_overlap():
    pieces = split_long(" ".join(str(i) for i in range(900)), max_tokens=400, overlap=50)
    assert len(pieces) == 3 and pieces[1].split()[0] == "350"


def test_tokenizer_keeps_sections():
    toks = tokenize("Deduction under 80CCD(1B) and 80C of Rs 1,50,000 u/s 87A")
    assert "80ccd(1b)" in toks and "80c" in toks and "150000" in toks and "87a" in toks
    assert "under" not in toks  # stopword


def test_bm25_finds_section():
    chunks = fixture_chunks()
    idx = BM25Index(chunks)
    top = idx.search("80C deduction limit PPF", k=3)
    assert chunks[top[0][0]]["id"] in ("FX-IT61-80C", "FX-MAP-80C")


def test_rrf():
    fused = rrf([[1, 2, 3], [3, 1, 4]], k=60)
    assert fused[0][0] == 1  # ranks 1 and 2 beat ranks 3 and 1
    assert {i for i, _ in fused} == {1, 2, 3, 4}


def test_date_filter():
    chunks = fixture_chunks()
    ids = [c["id"] for c in chunks]
    old = ids.index("FX-GST-CEMENT-OLD")
    new = ids.index("FX-GST-CEMENT-NEW")
    kept, removed = filter_by_period(chunks, [old, new], date(2025, 8, 1), date(2025, 8, 31))
    assert kept == [old] and removed == [new]
    assert is_eligible({"effective_from": "", "effective_to": ""}, date(2000, 1, 1), date(2000, 1, 1))


def test_section_boost_adds_mapping_chunk():
    chunks = fixture_chunks()
    ids = [c["id"] for c in chunks]
    added = section_boost(chunks, ["80C"], pool=[])
    assert [ids[i] for i in added] == ["FX-MAP-80C"]
    assert section_boost(chunks, [], pool=[]) == []
