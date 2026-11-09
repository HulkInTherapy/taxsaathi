"""
FastAPI web server for TaxSaathi (port 8000).

Endpoints (see SPEC "API contract"): /health, /ask, /compare (plain LLM vs TaxSaathi),
/calculate (calculator only), /experiments (results.json), /kb/stats, /feedback.
It also serves the demo web UI from app/static at "/". Every query is logged as one JSON
line in logs/queries.jsonl with personal data masked.

Run:  uvicorn src.api.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import json
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src import config
from src.calculator.tax import PresumptiveLimitExceeded, calculate
from src.generation.llm import is_available
from src.guardrails.pii import mask_pii
from src.pipeline import CONFIGS, get_pipeline

app = FastAPI(title="TaxSaathi API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_LOG_LOCK = threading.Lock()


def _append_jsonl(name: str, record: dict) -> None:
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK, (config.LOG_DIR / name).open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _log_query(endpoint: str, question: str, result: dict) -> None:
    gate = next((t for t in result.get("trace", []) if t["step"] == "gate"), None)
    _append_jsonl("queries.jsonl", {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "endpoint": endpoint,
        "question": mask_pii(question)[0], "config": result.get("config"),
        "latency_ms": result.get("latency_ms"), "refused": result.get("refused"),
        "refusal_reason": result.get("refusal_reason"), "intent": result.get("intent"),
        "language": result.get("language"),
        "top_score": gate["data"].get("top_score") if gate else None,
        "citations": [c["id"] for c in result.get("citations", [])],
    })


# ---------------------------------------------------------------- request models
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    config: str = "C6"


class CompareRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


class CalcRequest(BaseModel):
    gross_salary: int = Field(..., ge=0)
    deductions_80c: int = Field(0, ge=0)
    deductions_80d: int = Field(0, ge=0)
    deductions_80d_parents: int = Field(0, ge=0)
    parents_senior: bool = False
    hra_exemption: int = Field(0, ge=0)
    home_loan_interest: int = Field(0, ge=0)
    nps_80ccd1b: int = Field(0, ge=0)
    other_deductions: int = Field(0, ge=0)
    employer_nps: int = Field(0, ge=0)
    age: Literal["below60", "60to80", "above80"] = "below60"
    tax_year: Literal["2024-25", "2025-26", "2026-27"] = "2026-27"
    salaried: bool = True
    # "salary" (default) or "professional_presumptive": gross_salary is then the gross receipts and
    # 50% is taxed (section 58 of the 2025 Act / 44ADA of the 1961 Act).
    income_type: Literal["salary", "professional_presumptive"] = "salary"
    cash_receipts_over_5pct: bool = False


class FeedbackRequest(BaseModel):
    question: str
    answer: str = ""
    vote: Literal["up", "down"]
    config: Optional[str] = None
    comment: Optional[str] = None


# ---------------------------------------------------------------- startup
@app.on_event("startup")
def _warm() -> None:
    # Load models in a background thread so the server starts answering /health at once.
    def run():
        try:
            get_pipeline().warmup(("C6",))
        except Exception as e:  # missing KB etc. — endpoints will report it
            print(f"warmup failed: {e}")
    threading.Thread(target=run, daemon=True).start()


# ---------------------------------------------------------------- endpoints
@app.get("/health")
def health():
    return {"status": "ok", "llm": config.LLM_MODEL, "llm_available": is_available(),
            "chunks": len(get_pipeline().chunks), "today": config.TODAY.isoformat(),
            "rerank_threshold": config.rerank_threshold()}


@app.post("/ask")
def ask(req: AskRequest):
    if req.config not in CONFIGS:
        raise HTTPException(400, f"config must be one of {list(CONFIGS)}")
    result = get_pipeline().ask(req.question, req.config)
    _log_query("/ask", req.question, result)
    return result


@app.post("/compare")
def compare(req: CompareRequest):
    p = get_pipeline()
    plain = p.ask(req.question, "B0")
    full = p.ask(req.question, "C6")
    _log_query("/compare", req.question, full)
    return {"plain": plain, "taxsaathi": full}


@app.post("/calculate")
def calc(req: CalcRequest):
    try:
        return calculate(req.model_dump() if hasattr(req, "model_dump") else req.dict())
    except PresumptiveLimitExceeded as e:  # not computed on purpose: needs books / a CA
        return JSONResponse(status_code=422, content={"detail": str(e), "escalate": True, "follow_up": str(e)})
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/experiments")
def experiments():
    if not config.RESULTS_PATH.exists():
        return {"configs": [], "dev_size": 0, "test_size": 0, "generated_at": None,
                "note": "run `python -m experiments.run_experiments` first"}
    return json.loads(config.RESULTS_PATH.read_text())


@app.get("/kb/stats")
def kb_stats():
    chunks = get_pipeline().chunks
    sources: dict[str, dict] = {}
    for c in chunks:
        s = sources.setdefault(c["doc_id"], {"doc_id": c["doc_id"], "source_title": c["source_title"],
                                             "source_url": c["source_url"], "publisher": c["publisher"],
                                             "law": c["law"], "chunks": 0})
        s["chunks"] += 1
    return {"total_chunks": len(chunks),
            "by_law": dict(Counter(c["law"] for c in chunks)),
            "by_topic": dict(Counter(c["topic"] or "(none)" for c in chunks)),
            "by_doc_type": dict(Counter(c["doc_type"] or "(none)" for c in chunks)),
            "verified": dict(Counter(c["verified"] or "(blank)" for c in chunks)),
            "sources": sorted(sources.values(), key=lambda s: -s["chunks"])}


@app.post("/feedback")
def feedback(req: FeedbackRequest):
    _append_jsonl("feedback.jsonl", {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "question": mask_pii(req.question)[0], "answer": mask_pii(req.answer)[0],
        "vote": req.vote, "config": req.config,
        "comment": mask_pii(req.comment)[0] if req.comment else None})
    return {"ok": True}


@app.get("/configs")
def configs():
    return {k: v["description"] for k, v in CONFIGS.items()}


@app.exception_handler(Exception)
async def _unhandled(request, exc):  # keep the demo UI informative instead of a bare 500
    return JSONResponse(status_code=500, content={"error": type(exc).__name__, "detail": str(exc)})


# Static UI last, so the API routes above take precedence.
if config.STATIC_DIR.exists():
    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
else:
    @app.get("/")
    def root():
        return {"message": "TaxSaathi API is running. UI not found in app/static.",
                "time": time.strftime("%Y-%m-%d %H:%M:%S")}
