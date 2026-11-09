"""
The TaxSaathi pipeline: one question in, one grounded and cited answer out (with a trace).

Steps (same order every time, see SPEC): PII scrub -> Hinglish normalisation -> intent ->
period extraction -> section entities -> BM25 + dense -> RRF fusion -> date filter ->
cross-encoder rerank -> refusal gate -> calculator (for calculations) -> LLM generation ->
citation check. Each step records what it did and how long it took in `trace`, which the
demo UI displays. Configs B0..C5 switch steps on/off for the experiments. Heavy models are
loaded lazily, once, and shared between requests.
"""
from __future__ import annotations

import threading
import time
from contextlib import contextmanager

from src import config
from src.calculator.parse import parse_calc_query
from src.calculator.tax import calculate
from src.generation.generate import generate, generate_plain
from src.guardrails import intent as intent_mod
from src.guardrails.citation_check import extract_ids
from src.guardrails.pii import mask_pii
from src.guardrails.refusal import gate
from src.ingest.ingest import read_chunks
from src.nlp.dates import extract_period
from src.nlp.entities import extract_entities
from src.nlp.hinglish import normalise
from src.retrieval.bm25 import BM25Index
from src.retrieval.date_filter import filter_by_period, period_twins
from src.retrieval.hybrid import rrf, section_boost

# What each experiment configuration switches on (SPEC "Configs").
CONFIGS: dict[str, dict] = {
    "B0": {"description": "LLM alone (no retrieval, no guardrails)", "retrieval": None,
           "rerank": False, "date_filter": False, "hinglish": False},
    "B1": {"description": "BM25 top-5", "retrieval": "bm25", "rerank": False, "date_filter": False, "hinglish": False},
    "C1": {"description": "Dense (multilingual-e5-small) top-5", "retrieval": "dense", "rerank": False, "date_filter": False, "hinglish": False},
    "C2": {"description": "Hybrid BM25 + dense with RRF (k=60) top-5", "retrieval": "hybrid", "rerank": False, "date_filter": False, "hinglish": False},
    "C3": {"description": "Hybrid top-20 -> bge-reranker -> top-5", "retrieval": "hybrid", "rerank": True, "date_filter": False, "hinglish": False},
    "C4": {"description": "C3 + date filter", "retrieval": "hybrid", "rerank": True, "date_filter": True, "hinglish": False},
    "C5": {"description": "C4 + Hinglish normalisation (full system)", "retrieval": "hybrid", "rerank": True, "date_filter": True, "hinglish": True},
    # Extra (not in the original SPEC): on the dev set the reranker re-ordering lowered MRR, so
    # C6 keeps the fused + date-filtered order and uses the reranker score only for the gate.
    "C6": {"description": "C5 but reranker used only for the refusal gate (fusion order kept)", "retrieval": "hybrid",
           "rerank": True, "date_filter": True, "hinglish": True, "rerank_order": False},
}

STEP_LABELS = {
    "pii": "PII scrub", "hinglish": "Hinglish normalisation", "intent": "Intent classification",
    "period": "Period extraction", "entities": "Section & amount entities", "bm25": "BM25 keyword search",
    "dense": "Dense semantic search", "fusion": "Reciprocal Rank Fusion", "date_filter": "Date filter",
    "rerank": "Cross-encoder rerank", "gate": "Guardrail gate", "calculator": "Tax calculator",
    "generate": "Grounded generation", "citation_check": "Citation check",
}


class Trace:
    """Collects trace steps with timings."""

    def __init__(self):
        self.steps: list[dict] = []

    @contextmanager
    def step(self, name: str):
        rec = {"step": name, "label": STEP_LABELS.get(name, name), "summary": "", "ms": 0, "data": {}}
        t0 = time.perf_counter()
        try:
            yield rec
        finally:
            rec["ms"] = int(round((time.perf_counter() - t0) * 1000))
            self.steps.append(rec)


def _results(chunks: list[dict], ranked: list[tuple[int, float]], n: int = 10) -> list[dict]:
    return [{"id": chunks[i]["id"], "title": chunks[i]["title"], "score": round(float(s), 4)} for i, s in ranked[:n]]


def _citation(c: dict) -> dict:
    keys = ["id", "title", "section", "source_title", "source_url", "effective_from", "effective_to", "text"]
    out = {k: c.get(k, "") for k in keys}
    out["law"] = c.get("law", "")
    return out


class TaxSaathi:
    """Main entry point. `ask()` for full answers, `retrieve_only()` for fast experiments."""

    def __init__(self, chunks: list[dict] | None = None, chunks_path=None, use_llm: bool = True):
        self._chunks = chunks
        self._chunks_path = chunks_path
        self.use_llm = use_llm
        self._bm25 = None
        self._dense = None
        self._lock = threading.RLock()  # re-entrant: properties call each other

    # ------------------------------------------------------------ lazy resources
    @property
    def chunks(self) -> list[dict]:
        if self._chunks is None:
            with self._lock:
                if self._chunks is None:
                    path = self._chunks_path or config.CHUNKS_PATH
                    self._chunks = read_chunks(path) if path.exists() else []
        return self._chunks

    @property
    def bm25(self) -> BM25Index:
        if self._bm25 is None:
            with self._lock:
                if self._bm25 is None:
                    self._bm25 = BM25Index(self.chunks)
        return self._bm25

    @property
    def dense(self):
        if self._dense is None:
            chunks = self.chunks
            with self._lock:
                if self._dense is None:
                    from src.retrieval.dense import DenseIndex
                    self._dense = DenseIndex(chunks)
        return self._dense

    def warmup(self, configs=("C5",)) -> None:
        """Load models up-front (used by the API at startup)."""
        _ = self.bm25
        if any(CONFIGS[c]["retrieval"] in ("dense", "hybrid") for c in configs):
            _ = self.dense
        if any(CONFIGS[c]["rerank"] for c in configs):
            from src.retrieval.reranker import get_model
            get_model()
        intent_mod.get_model()

    # ------------------------------------------------------------ core
    def _understand(self, question: str, cfg: dict, trace: Trace) -> dict:
        """Steps 1-5: PII, Hinglish, intent, period, entities."""
        with trace.step("pii") as s:
            masked, found = mask_pii(question)
            s["data"] = {"masked": masked, "found": found}
            s["summary"] = "masked " + ", ".join(f"{v} {k}" for k, v in found.items()) if found else "no personal data found"

        with trace.step("hinglish") as s:
            norm = normalise(masked)
            applied = cfg["hinglish"] and norm["language"] == "hinglish"
            query = norm["normalised"] if applied else masked
            s["data"] = {"original": masked, "normalised": query, "language": norm["language"],
                         "replaced": norm["replaced"] if applied else [], "applied": applied}
            if applied:
                s["summary"] = f"Hinglish detected; {len(norm['replaced'])} replacements"
            elif norm["language"] == "hinglish":
                s["summary"] = "Hinglish detected; normalisation off in this config"
            else:
                s["summary"] = "English; no change"

        with trace.step("intent") as s:
            it = intent_mod.classify(query)
            s["data"] = it
            s["summary"] = f"{it['label']} (p={it['probs'].get(it['label'], 0):.2f})" + (f"; rule: {it['rule']}" if it.get("rule") else "")

        with trace.step("period") as s:
            # dates.py understands Hinglish ("pichle saal") itself, so use both texts
            period = extract_period(masked if not applied else f"{masked} {query}")
            s["data"] = period.to_dict()
            s["summary"] = f"{period.label}" + (" (assumed current law)" if period.assumed_current else f" — {period.reason}")

        with trace.step("entities") as s:
            ents = extract_entities(query)
            s["data"] = {"sections": ents["sections"],
                         "amounts": [{"text": a["text"], "value": a["value"], "per_month": a["per_month"],
                                      "period": a.get("period"), "currency": a.get("currency", "INR"),
                                      "foreign_value": a.get("foreign_value"), "fx_rate": a.get("fx_rate")}
                                     for a in ents["amounts"]],
                         "age": ents["age"], "age_category": ents["age_category"]}
            bits = []
            if ents["sections"]:
                bits.append("sections " + ", ".join(ents["sections"]))
            if ents["amounts"]:
                bits.append("amounts " + ", ".join(f"₹{a['value']:,}" for a in ents["amounts"]))
            if ents["age_category"]:
                bits.append(f"age {ents['age_category']}")
            s["summary"] = "; ".join(bits) or "none found"
        return {"masked": masked, "query": query, "norm": norm, "intent": it, "period": period, "entities": ents}

    def _retrieve(self, query: str, cfg: dict, u: dict, trace: Trace) -> dict:
        """Step 6: retrieval for the chosen config. Returns ranked indices + top score."""
        chunks = self.chunks
        mode = cfg["retrieval"]
        bm, de = [], []
        if mode in ("bm25", "hybrid"):
            with trace.step("bm25") as s:
                bm = self.bm25.search(query, k=config.FIRST_STAGE_K)
                s["data"] = {"results": _results(chunks, bm)}
                s["summary"] = f"{len(bm)} hits; top {chunks[bm[0][0]]['id']}" if bm else "no keyword hits"
        if mode in ("dense", "hybrid"):
            with trace.step("dense") as s:
                de = self.dense.search(query, k=config.FIRST_STAGE_K)
                s["data"] = {"results": _results(chunks, de)}
                s["summary"] = f"top {chunks[de[0][0]]['id']} (cos {de[0][1]:.3f})" if de else "empty index"

        if mode == "bm25":
            ranked = bm
        elif mode == "dense":
            ranked = de
        else:
            with trace.step("fusion") as s:
                ranked = rrf([[i for i, _ in bm], [i for i, _ in de]], k=config.RRF_K)
                s["data"] = {"results": _results(chunks, ranked), "k": config.RRF_K}
                s["summary"] = f"{len(ranked)} unique candidates fused"

        if cfg["date_filter"]:
            with trace.step("date_filter") as s:
                p = u["period"]
                pool_idx = [i for i, _ in ranked]
                kept, removed = filter_by_period(chunks, pool_idx, p.start, p.end)
                # Swap each out-of-period passage for the same rule's in-period version (same rank).
                order, swaps = period_twins(chunks, pool_idx, p.start, p.end)
                scores = dict(ranked)
                by_id = {c["id"]: n for n, c in enumerate(chunks)}
                twin_score = {by_id[t]: scores[by_id[r]] for r, t in swaps.items() if t in by_id}
                ranked = [(i, scores.get(i, twin_score.get(i, 0.0))) for i in order]
                # Spec's "before/after" counts refer to the top-20 window the reranker sees.
                window_before = pool_idx[:config.RERANK_POOL]
                removed_set = set(removed)
                removed_window = [chunks[i]["id"] for i in window_before if i in removed_set]
                s["data"] = {"before": len(window_before), "after": len(window_before) - len(removed_window),
                             "removed": removed_window, "removed_total": len(removed), "swapped_in": swaps,
                             "period": [p.start.isoformat(), p.end.isoformat()]}
                s["summary"] = f"removed {len(removed_window)} out-of-period passages from the top {len(window_before)}"

        top_score = ranked[0][1] if ranked else None
        if cfg["rerank"]:
            from src.retrieval.reranker import rerank, sigmoid
            pool = [i for i, _ in ranked[:config.RERANK_POOL]]
            boost = section_boost(chunks, u["entities"]["sections"], pool)
            if cfg["date_filter"] and boost:
                p = u["period"]
                boost, _ = filter_by_period(chunks, boost, p.start, p.end)
            with trace.step("rerank") as s:
                reranked = rerank(query, chunks, pool + boost)
                top_score = reranked[0][1] if reranked else None
                s["data"] = {"results": [dict(r, prob=round(sigmoid(r["score"]), 3)) for r in _results(chunks, reranked)],
                             "pool": len(pool), "boosted": [chunks[i]["id"] for i in boost]}
                s["summary"] = (f"top {chunks[reranked[0][0]]['id']} (logit {reranked[0][1]:.2f})" if reranked else "no candidates") + \
                               (f"; +{len(boost)} mapping chunks for {', '.join(u['entities']['sections'])}" if boost else "")
            if cfg.get("rerank_order", True):
                ranked = reranked
            else:  # keep fusion order (boosted mapping chunks appended), gate on the best rerank score
                ranked = ranked[:config.RERANK_POOL] + [(i, 0.0) for i in boost]
        return {"ranked": ranked, "top_score": top_score}

    def _gate(self, cfg: dict, u: dict, top_score, trace: Trace):
        use_score = cfg["rerank"]
        threshold = config.rerank_threshold() if use_score else None
        with trace.step("gate") as s:
            g = gate(u["intent"], top_score, threshold, use_score)
            s["data"] = {"passed": g.passed, "top_score": None if top_score is None else round(float(top_score), 4),
                         "threshold": threshold, "reason": g.reason}
            s["summary"] = "passed" if g.passed else f"refused: {g.reason}"
        return g

    # ------------------------------------------------------------ public API
    def retrieve_only(self, question: str, config_name: str = "C5") -> dict:
        """Run steps 1-7 only (no calculator, no LLM). Used by experiments."""
        cfg = CONFIGS[config_name]
        trace = Trace()
        u = self._understand(question, cfg, trace)
        ids, top_score, refused, reason = [], None, False, None
        if cfg["retrieval"]:
            r = self._retrieve(u["query"], cfg, u, trace)
            ids = [self.chunks[i]["id"] for i, _ in r["ranked"][:20]]
            top_score = r["top_score"]
            g = self._gate(cfg, u, top_score, trace)
            refused, reason = not g.passed, g.reason
        return {"ids": ids, "top_score": top_score, "refused": refused, "refusal_reason": reason,
                "intent": u["intent"], "period": u["period"].to_dict(), "query": u["query"],
                "language": u["norm"]["language"], "entities": u["entities"], "trace": trace.steps}

    def ask(self, question: str, config: str = "C5") -> dict:
        """Full pipeline -> dict matching the SPEC /ask response."""
        if config not in CONFIGS:
            raise ValueError(f"unknown config {config}; choose from {list(CONFIGS)}")
        cfg = CONFIGS[config]
        t_start = time.perf_counter()
        trace = Trace()
        resp = {"answer": "", "refused": False, "refusal_reason": None, "follow_up": None, "citations": [],
                "calculation": None, "disclaimer": _disclaimer(), "latency_ms": 0, "config": config, "trace": trace.steps}

        def done():
            resp["latency_ms"] = int((time.perf_counter() - t_start) * 1000)
            return resp

        # ---- B0: the bare LLM
        if cfg["retrieval"] is None:
            with trace.step("pii") as s:
                masked, found = mask_pii(question)
                s["data"] = {"masked": masked, "found": found}
                s["summary"] = "masked " + ", ".join(found) if found else "no personal data found"
            with trace.step("generate") as s:
                g = generate_plain(masked, use_llm=self.use_llm)
                s["data"] = {"model": _llm_name(), "error": g["error"], "prompt": "plain (no passages)"}
                s["summary"] = f"plain LLM answer in {g['llm_ms']} ms" if not g["error"] else f"LLM error: {g['error']}"
            resp["answer"] = g["answer"]
            return done()

        u = self._understand(question, cfg, trace)
        resp.update({"intent": u["intent"]["label"], "language": u["norm"]["language"], "period": u["period"].to_dict()})
        r = self._retrieve(u["query"], cfg, u, trace)
        resp["retrieved"] = [self.chunks[i]["id"] for i, _ in r["ranked"][:10]]
        g = self._gate(cfg, u, r["top_score"], trace)
        if not g.passed:
            resp.update({"answer": g.message, "refused": True, "refusal_reason": g.reason})
            return done()

        top = [self.chunks[i] for i, _ in r["ranked"][:config_final_k()]]

        calc = None
        if u["intent"]["label"] == "calculation":
            with trace.step("calculator") as s:
                parsed = parse_calc_query(u["query"], u["period"], u["entities"])
                s["data"] = {"assigned": parsed["assigned"], "notes": parsed["notes"], "inputs": parsed["inputs"],
                             "income_type": parsed["income_type"], "assumed": parsed["assumed"],
                             "escalate": parsed["escalate"]}
                if parsed["escalate"]:
                    s["summary"] = "receipts above the presumptive limit -> CA escalation (not computed)"
                elif parsed["follow_up"]:
                    s["summary"] = "salary missing -> follow-up question"
                else:
                    calc = calculate(parsed["inputs"])
                    calc["notes"] = parsed["notes"] + calc["notes"]
                    calc["assumed"] = parsed["assumed"]
                    s["data"]["result"] = {"old_total": calc["old"]["total"], "new_total": calc["new"]["total"],
                                           "better": calc["better"], "headline": calc["headline"]}
                    s["summary"] = (f"{calc['income_type']}: old ₹{calc['old']['total']:,} vs new ₹{calc['new']['total']:,} "
                                    f"-> {calc['better']}")
            if parsed["follow_up"]:
                resp.update({"answer": parsed["follow_up"], "follow_up": parsed["follow_up"]})
                if parsed["escalate"]:
                    src = self._calc_sources(parsed["inputs"]["tax_year"], parsed["income_type"], "below60")
                    resp["escalate"] = True
                    resp["calculation_notes"] = parsed["notes"]
                    pres = self._chunk(src.get("presumptive"))
                    if pres:
                        resp["answer"] += f" [{pres['id']}]"
                        resp["citations"] = [_citation(pres)]
                return done()
            # Explain the result with the passages that actually govern it (slabs, rebate,
            # standard deduction / presumptive scheme for that tax year), not the top-ranked hits.
            foreign = any(a.get("foreign_value") is not None for a in u["entities"]["amounts"])
            src = self._calc_sources(calc["tax_year"], calc["income_type"], calc["inputs"]["age"], foreign)
            calc_chunks = [self._chunk(i) for i in dict.fromkeys(src.values()) if self._chunk(i)]
            if calc_chunks:
                top = calc_chunks
            calc["_source_ids"] = src
            if calc["income_type"] == "professional_presumptive" and foreign:
                calc["_gst_note"] = (
                    "On GST: work for foreign clients is an export of services, which is zero-rated — once registered "
                    "(needed above ₹20 lakh turnover) you can bill without IGST under a Letter of Undertaking (LUT); "
                    "take refund and filing details to a CA. [GST-REG-FREELANCER]" if src.get("gst") else
                    "GST on export of services is outside what TaxSaathi covers — please ask a CA.")
            resp["calculation"] = calc

        with trace.step("generate") as s:
            gen = generate(u["masked"], top, u["period"], calc=calc,
                           normalised=u["query"] if u["query"] != u["masked"] else None, use_llm=self.use_llm)
            s["data"] = {"model": _llm_name(), "passages": [c["id"] for c in top], "raw": gen["raw"],
                         "fallback": gen["fallback"], "fallback_reason": gen["fallback_reason"], "error": gen["error"]}
            s["summary"] = (f"LLM answer in {gen['llm_ms']} ms" if not gen["fallback"]
                            else f"extractive fallback ({gen['fallback_reason']})")
        with trace.step("citation_check") as s:
            chk = gen["citation_check"]
            s["data"] = {"kept": chk["kept"], "dropped": chk["dropped"], "invalid_ids": chk["invalid_ids"],
                         "n_tags": chk["n_tags"], "n_valid_tags": chk["n_valid_tags"], "fallback": gen["fallback"]}
            s["summary"] = f"kept {chk['kept']}, dropped {chk['dropped']}" + (f", invalid {chk['invalid_ids']}" if chk["invalid_ids"] else "")

        resp["answer"] = gen["answer"]
        cited = set(extract_ids(gen["answer"]))
        by_id = {c["id"]: c for c in top}
        resp["citations"] = [_citation(by_id[i]) for i in by_id if i in cited]
        if calc:
            calc.pop("_source_ids", None)
            calc.pop("_gst_note", None)
        return done()

    # ------------------------------------------------------------ calculator sources
    def _chunk(self, cid: str | None) -> dict | None:
        if not cid:
            return None
        if getattr(self, "_by_id", None) is None or len(self._by_id) != len(self.chunks):
            self._by_id = {c["id"]: c for c in self.chunks}
        return self._by_id.get(cid)

    def _calc_sources(self, tax_year: str, income_type: str | None, age: str, foreign: bool = False) -> dict:
        """KB chunk IDs that support a calculator result for this tax year (only IDs present in the KB)."""
        table = CALC_SOURCES.get(tax_year, CALC_SOURCES["2026-27"])
        want = {"new_slabs": table["new_slabs"], "rebate": table["rebate"],
                "old_slabs": "IT-OLD-SLABS-BELOW60" if age == "below60" else "IT-OLD-SLABS-SENIOR"}
        if income_type == "professional_presumptive":
            want["presumptive"] = table["presumptive"]
            if foreign:
                want["gst"] = "GST-REG-FREELANCER"
        else:
            want["std"] = table["std"]
        return {k: v for k, v in want.items() if self._chunk(v)}


# Passages that govern a calculator result, per tax year (IDs from data/raw/curated).
CALC_SOURCES = {
    "2024-25": {"new_slabs": "IT-NEW-SLABS-FY2425", "rebate": "IT-NEW-REBATE-FY2425",
                "std": "IT-NEW-STDDED-1961", "presumptive": "IT-FL-44ADA"},
    "2025-26": {"new_slabs": "IT-NEW-SLABS-FY2526", "rebate": "IT-NEW-REBATE-FY2526",
                "std": "IT-NEW-STDDED-1961", "presumptive": "IT-FL-44ADA"},
    "2026-27": {"new_slabs": "IT-NEW-SLABS-TY2627", "rebate": "IT-NEW-REBATE-TY2627",
                "std": "IT-NEW-STDDED-TY2627", "presumptive": "IT-FL-SEC58-TY2627"},
}


def config_final_k() -> int:
    return config.GEN_K


def _llm_name() -> str:
    return config.LLM_MODEL


def _disclaimer() -> str:
    return config.DISCLAIMER


_INSTANCE: TaxSaathi | None = None


def get_pipeline() -> TaxSaathi:
    """Process-wide singleton used by the API and scripts."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = TaxSaathi()
    return _INSTANCE


if __name__ == "__main__":
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Ask TaxSaathi one question from the command line")
    ap.add_argument("question")
    ap.add_argument("--config", default="C5", choices=list(CONFIGS))
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--trace", action="store_true", help="print the full trace")
    a = ap.parse_args()
    out = TaxSaathi(use_llm=not a.no_llm).ask(a.question, a.config)
    if not a.trace:
        out["trace"] = [{k: t[k] for k in ("step", "summary", "ms")} for t in out["trace"]]
    print(json.dumps(out, indent=2, ensure_ascii=False))
