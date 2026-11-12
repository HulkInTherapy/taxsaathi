"""
search_tax_law: the existing Taxot RAG pipeline, exposed as one tool.

It runs the full understanding + retrieval + guardrail-gate part of the pipeline (PII scrub,
Hinglish normalisation, intent, period extraction, hybrid search, date filter, reranker gate)
and returns the top passages with their citations. It does NOT write an answer: the calling
agent does that from the passages, and the verifier later checks the agent's claims against
the same passages. If the gate refuses (out of scope, low confidence, injection), no passages
are returned and the agent is told why, so it can rephrase, ask the user, or escalate.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

DEFAULT_CONFIG = "C6"  # best retrieval config on the dev set (same as the /ask default)


class SearchTaxLawArgs(BaseModel):
    question: str = Field(..., min_length=3, max_length=500,
                          description="A focused question about Indian income tax or GST law.")
    tax_year: Optional[str] = Field(None, pattern=r"^20\d\d-\d\d$",
                                    description="Financial / tax year the question is about, e.g. '2025-26'. "
                                                "Leave empty for the current law.")
    max_passages: int = Field(4, ge=1, le=8, description="How many passages to return.")


def search_tax_law(args: SearchTaxLawArgs, ctx) -> dict:
    pipeline = ctx.pipeline
    question = args.question
    if args.tax_year and args.tax_year not in question:
        question = f"{question} (FY {args.tax_year})"
    r = pipeline.retrieve_only(question, ctx.retrieval_config or DEFAULT_CONFIG)
    out = {
        "refused": r["refused"],
        "refusal_reason": r["refusal_reason"],
        "confidence": None if r["top_score"] is None else round(float(r["top_score"]), 3),
        "period": r["period"].get("label"),
        "passages": [],
    }
    if r["refused"]:
        out["hint"] = ("The knowledge base does not answer this confidently. Rephrase more specifically, "
                       "ask the user for details, or escalate to a CA.")
        return out
    by_id = ctx.chunk_index()
    for cid in r["ids"][:args.max_passages]:
        c = by_id.get(cid)
        if c is None:
            continue
        out["passages"].append({
            "id": c["id"], "title": c["title"], "law": c.get("law", ""), "section": c.get("section", ""),
            "effective_from": c.get("effective_from", ""), "effective_to": c.get("effective_to", ""),
            "source": c.get("source_title", ""), "url": c.get("source_url", ""), "text": c["text"],
        })
    return out
