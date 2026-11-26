import json
from datetime import datetime, timezone

from src.api.monitoring import summarize


def _write(path, rows):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_summarize_aggregates_logs(tmp_path):
    now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
    _write(tmp_path / "queries.jsonl", [
        {"ts": "2026-11-26T10:00:00+00:00", "endpoint": "/ask", "question": "q1", "latency_ms": 1000,
         "refused": False, "intent": "question", "language": "en", "top_score": -5.5, "citations": ["A", "B"]},
        {"ts": "2026-11-26T11:00:00+00:00", "endpoint": "/ask", "question": "q2", "latency_ms": 3000,
         "refused": True, "refusal_reason": "out_of_scope", "intent": "out_of_scope", "language": "hinglish",
         "top_score": -9.0, "citations": []},
        {"ts": "2026-11-20T11:00:00+00:00", "endpoint": "/compare", "question": "q3", "latency_ms": 2000,
         "refused": False, "intent": "calculation", "language": "en", "top_score": 2.0, "citations": ["A"]},
        "not json",
    ])
    (tmp_path / "queries.jsonl").write_text((tmp_path / "queries.jsonl").read_text().replace('"not json"', "{broken"))
    _write(tmp_path / "feedback.jsonl", [{"ts": "2026-11-26T10:01:00+00:00", "vote": "up", "question": "q1"},
                                         {"ts": "2026-11-26T10:02:00+00:00", "vote": "down", "question": "q3"}])
    _write(tmp_path / "llm_usage.jsonl", [
        {"provider": "groq", "role": "writer", "ok": True, "ms": 2000, "input_tokens": 700, "output_tokens": 400},
        {"provider": "groq", "role": "writer", "ok": False},
        {"provider": "gemini", "role": "writer", "ok": True, "ms": 4000, "input_tokens": 10, "output_tokens": 5}])

    d = summarize(tmp_path, threshold=-5.83, now=now, days=7)
    q = d["queries"]
    assert q["total"] == 3                      # the malformed line is skipped
    assert q["last_24h"] == 2
    assert abs(q["refusal_rate"] - 1 / 3) < 1e-9
    assert q["refusal_reasons"] == {"out_of_scope": 1}
    assert q["latency_p50_ms"] == 2000 and q["latency_p95_ms"] == 3000
    assert len(q["per_day"]) == 7 and q["per_day"][-1] == {"day": "2026-11-26", "queries": 2, "refused": 1}
    assert [r["question"] for r in q["near_gate"]] == ["q1"]   # answered, score within 1.0 of the gate
    assert q["top_citations"][0] == ["A", 2] or q["top_citations"][0] == ("A", 2)
    assert d["feedback"]["up"] == 1 and d["feedback"]["down"] == 1
    groq = next(p for p in d["llm"]["providers"] if p["provider"] == "groq")
    assert groq["calls"] == 2 and groq["ok_rate"] == 0.5 and groq["input_tokens"] == 700


def test_summarize_empty(tmp_path):
    d = summarize(tmp_path, threshold=None)
    assert d["queries"]["total"] == 0 and d["queries"]["refusal_rate"] is None
    assert d["llm"]["providers"] == []
