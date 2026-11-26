"""
Monitoring summary for the dashboard (M5): reads the JSON-lines logs the API already writes.

    logs/queries.jsonl    one row per /ask or /compare (question PII-masked, latency, intent, refusal, gate score, citations)
    logs/feedback.jsonl   thumbs up / down from the UI
    logs/llm_usage.jsonl  every LLM call (role, provider, model, ok, ms, tokens)

Nothing here stores new data; it only aggregates. Questions are already masked when logged.
"""
from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _read(path: Path, limit: int = 50_000) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


def _ts(r: dict) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(r.get("ts")))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return xs[max(0, min(len(xs) - 1, round(q * (len(xs) - 1))))]


def summarize(log_dir: Path, threshold: float | None = None, now: datetime | None = None, days: int = 14) -> dict:
    now = now or datetime.now(timezone.utc)
    queries = _read(log_dir / "queries.jsonl")
    feedback = _read(log_dir / "feedback.jsonl")
    usage = _read(log_dir / "llm_usage.jsonl")

    # ---------------------------------------------------------------- queries
    lat = [q["latency_ms"] for q in queries if isinstance(q.get("latency_ms"), (int, float))]
    refused = [q for q in queries if q.get("refused")]
    day0 = (now - timedelta(days=days - 1)).date()
    per_day = Counter()
    refused_day = Counter()
    for q in queries:
        t = _ts(q)
        if t and t.date() >= day0:
            per_day[t.date().isoformat()] += 1
            if q.get("refused"):
                refused_day[t.date().isoformat()] += 1
    series = [{"day": (day0 + timedelta(days=i)).isoformat(),
               "queries": per_day.get((day0 + timedelta(days=i)).isoformat(), 0),
               "refused": refused_day.get((day0 + timedelta(days=i)).isoformat(), 0)} for i in range(days)]

    # Answered but close to the refusal gate: likely gaps in the knowledge base.
    margin = 1.0
    near_gate = []
    if threshold is not None:
        near_gate = [q for q in queries if not q.get("refused") and isinstance(q.get("top_score"), (int, float))
                     and q["top_score"] < threshold + margin]
    low = sorted(near_gate, key=lambda q: q["top_score"])[:10]

    cites = Counter(c for q in queries for c in (q.get("citations") or []))

    # ---------------------------------------------------------------- feedback
    votes = Counter(f.get("vote") for f in feedback)
    downs = [f for f in feedback if f.get("vote") == "down"][-8:][::-1]

    # ---------------------------------------------------------------- LLM usage
    prov = defaultdict(lambda: {"calls": 0, "ok": 0, "ms": [], "in": 0, "out": 0})
    for u in usage:
        p = prov[u.get("provider") or "?"]
        p["calls"] += 1
        if u.get("ok"):
            p["ok"] += 1
            if isinstance(u.get("ms"), (int, float)):
                p["ms"].append(u["ms"])
            p["in"] += u.get("input_tokens") or 0
            p["out"] += u.get("output_tokens") or 0
    providers = sorted(({"provider": k, "calls": v["calls"], "ok_rate": v["ok"] / v["calls"] if v["calls"] else None,
                         "p50_ms": statistics.median(v["ms"]) if v["ms"] else None,
                         "input_tokens": v["in"], "output_tokens": v["out"]} for k, v in prov.items()),
                       key=lambda x: -x["calls"])
    roles = Counter(u.get("role") or "?" for u in usage)

    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "threshold": threshold,
        "queries": {
            "total": len(queries),
            "last_24h": sum(1 for q in queries if (_ts(q) or now - timedelta(days=99)) >= now - timedelta(hours=24)),
            "refusal_rate": len(refused) / len(queries) if queries else None,
            "refusal_reasons": dict(Counter(q.get("refusal_reason") or "unknown" for q in refused).most_common(6)),
            "latency_p50_ms": _pct(lat, 0.5), "latency_p95_ms": _pct(lat, 0.95),
            "intents": dict(Counter(q.get("intent") or "?" for q in queries)),
            "languages": dict(Counter(q.get("language") or "?" for q in queries)),
            "endpoints": dict(Counter(q.get("endpoint") or "?" for q in queries)),
            "per_day": series,
            "near_gate": [{"ts": q.get("ts"), "question": q.get("question"), "top_score": round(q["top_score"], 2)}
                          for q in low],
            "near_gate_count": len(near_gate),
            "recent_refused": [{"ts": q.get("ts"), "question": q.get("question"), "reason": q.get("refusal_reason")}
                               for q in refused[-8:][::-1]],
            "top_citations": cites.most_common(8),
        },
        "feedback": {"up": votes.get("up", 0), "down": votes.get("down", 0),
                     "recent_down": [{"ts": f.get("ts"), "question": f.get("question")} for f in downs]},
        "llm": {"calls": len(usage), "ok_rate": sum(1 for u in usage if u.get("ok")) / len(usage) if usage else None,
                "by_role": dict(roles), "providers": providers},
    }
