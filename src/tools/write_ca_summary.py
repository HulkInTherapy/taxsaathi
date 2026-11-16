"""
write_ca_summary: turns an escalated case into a structured summary a CA can act on quickly.

Phase 2 scope: render a summary from what the agent passes in. Phase 6 fills it from the shared
task state (extracted figures, findings, open questions, citations). Output is Markdown (for
the UI and download) plus the same content as structured JSON.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.calculator.tax import format_inr


class CheckedItem(BaseModel):
    point: str = Field(..., description="What was checked or concluded.")
    citation: Optional[str] = Field(None, description="Knowledge-base passage id or section supporting it.")


class CASummaryArgs(BaseModel):
    reason_for_escalation: str = Field(..., min_length=5, description="Why this case needs a CA.")
    taxpayer_profile: str = Field(..., description="Short profile, e.g. 'Salaried, below 60, resident, "
                                                   "two employers in FY 2025-26'. No names, PAN or Aadhaar.")
    tax_year: str = Field("2025-26")
    figures: dict[str, int] = Field(default_factory=dict, description="Key amounts in rupees, e.g. "
                                                                      "{'gross_salary': 1450000}.")
    findings: list[str] = Field(default_factory=list, description="Mismatches or issues found.")
    already_checked: list[CheckedItem] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list, description="What the CA needs to decide or ask.")
    documents_reviewed: list[str] = Field(default_factory=list)


ACRONYMS = {"tds": "TDS", "hra": "HRA", "nps": "NPS", "gst": "GST", "pf": "PF", "epf": "EPF", "fd": "FD", "ltcg": "LTCG",
            "stcg": "STCG", "80c": "80C", "80d": "80D", "itr": "ITR", "ais": "AIS"}


def _label(key: str) -> str:
    words = key.replace("_", " ").split()
    text = " ".join(ACRONYMS.get(w.lower(), w) for w in words)
    return (text[:1].upper() + text[1:]) if text else key


def write_ca_summary(args: CASummaryArgs, ctx=None) -> dict:
    a = args
    lines = [f"# Case summary for your Chartered Accountant — FY {a.tax_year}", "",
             f"**Why a CA is needed:** {a.reason_for_escalation}", "",
             f"**Taxpayer profile:** {a.taxpayer_profile}", ""]
    if a.documents_reviewed:
        lines += ["## Documents reviewed", *[f"- {d}" for d in a.documents_reviewed], ""]
    if a.figures:
        lines += ["## Key figures", "| Item | Amount |", "|---|---|",
                  *[f"| {_label(k)} | {format_inr(v)} |" for k, v in a.figures.items()], ""]
    if a.findings:
        lines += ["## Findings", *[f"- {f}" for f in a.findings], ""]
    if a.already_checked:
        lines += ["## Already checked by Taxot",
                  *[f"- {c.point}" + (f" _(source: {c.citation})_" if c.citation else "") for c in a.already_checked], ""]
    if a.open_questions:
        lines += ["## Open questions for the CA", *[f"{i}. {q}" for i, q in enumerate(a.open_questions, 1)], ""]
    lines += ["---", "_Prepared by Taxot from the documents and answers provided. Taxot does not file returns "
                     "or give professional advice; figures should be verified by the CA._"]
    markdown = "\n".join(lines)
    if ctx is not None:
        ctx.outputs["ca_summary"] = markdown
        ctx.outputs["ca_summary_args"] = a.model_dump()
    return {"markdown": markdown, "summary": a.model_dump(), "sections": sum(1 for x in lines if x.startswith("## "))}
