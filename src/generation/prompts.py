"""
Prompt templates.

The grounded prompt gives the LLM the retrieved passages (each labelled with its chunk ID)
and strict rules: use only these passages, end every sentence with the [CHUNK-ID] it came
from, keep it to 2-5 short sentences in simple English, and say which period/law applies.
For calculations the calculator result is supplied as a fact block [CALC]; the LLM only
explains it. The B0 baseline prompt is a plain assistant with no passages (for comparison).
"""
from __future__ import annotations

from src import config
from src.nlp.dates import Period

GROUNDED_SYSTEM = """You are TaxSaathi, an assistant for Indian income tax and GST.
Rules:
1. Answer ONLY using the passages given below. Do not use outside knowledge.
2. End EVERY sentence with the ID of the passage it comes from in square brackets, e.g. [IT25-202-SLABS]. Use only IDs that appear below.
3. Write 2 to 5 short sentences in simple English, speaking directly to the user ("you"). Answer the question itself; never describe the passages (do not write "the passage mentions..."). No lists, no headings.
4. Say which period and which law applies, using the exact period name from "Period asked about" (for example "For FY 2024-25, under the Income-tax Act, 1961 ..." or "For Tax Year 2026-27, under the Income-tax Act, 2025 ..."). GST has no tax year: for GST say the date instead (for example "Since 22 September 2025, ..." or "In August 2025, ...").
5. If the passages do not answer the question, say "My sources do not cover this." and nothing else.
6. Never calculate numbers yourself. If a [CALC] block is given, the user already sees its numbers: do NOT repeat any amounts. Write only 1-2 sentences explaining in words why that regime wins (for example the rebate, the presumptive 50% rule, or which deductions each regime allows), citing passage IDs. With a [CALC] block, never say the sources do not cover it."""

PLAIN_SYSTEM = """You are a helpful assistant for Indian income tax and GST questions. Answer in 2 to 5 short sentences in simple English."""


def _law_name(law: str) -> str:
    return config.LAW_NAMES.get(law, law or "general")


def format_passages(chunks: list[dict]) -> str:
    blocks = []
    for c in chunks:
        valid = f"in force {c.get('effective_from') or 'earlier'} to {c.get('effective_to') or 'now'}"
        sec = f"section {c['section']}; " if c.get("section") else ""
        blocks.append(f"[{c['id']}] {c['title']} ({sec}{_law_name(c.get('law', ''))}; {valid})\n{c['text']}")
    return "\n\n".join(blocks)


def _gst_label(period: Period) -> str:
    """GST has no 'tax year': name the date or month instead (e.g. 'August 2025', 'today (29 Oct 2026)')."""
    import calendar
    s, e = period.start, period.end
    if period.assumed_current:
        return f"today ({s.strftime('%d %b %Y')})"
    if s.day == 1 and s.year == e.year and s.month == e.month and e.day == calendar.monthrange(e.year, e.month)[1]:
        return s.strftime("%B %Y")
    return s.strftime("%d %b %Y") if s == e else f"{s.strftime('%d %b %Y')} to {e.strftime('%d %b %Y')}"


def period_line(period: Period | None, gst: bool = False) -> str:
    if period is None:
        return ""
    label = _gst_label(period) if gst else period.label
    line = f"Period asked about: {label}." if gst else f"Period asked about: {label} ({period.reason})."
    if gst:
        line += " This is a GST question: refer to the date or month, never to a 'Tax Year'."
    if period.assumed_current:
        line += " The user did not give a period, so say the answer assumes the current law."
    return line


def grounded_messages(question: str, chunks: list[dict], period: Period | None,
                      calc_block: str | None = None, normalised: str | None = None) -> list[dict]:
    parts = ["PASSAGES:", format_passages(chunks) if chunks else "(none)"]
    if calc_block:
        parts += ["", "[CALC] Calculator result (exact, deterministic):", calc_block]
    gst = bool(chunks) and sum(c.get("law") == "gst" for c in chunks) > len(chunks) / 2 and not calc_block
    parts += ["", period_line(period, gst), f"QUESTION: {question}"]
    if normalised and normalised != question:
        parts.append(f"(Same question in plain English: {normalised})")
    parts.append("ANSWER (2-5 sentences, each ending with a [ID] citation):")
    return [{"role": "system", "content": GROUNDED_SYSTEM},
            {"role": "user", "content": "\n".join(p for p in parts if p is not None)}]


def plain_messages(question: str) -> list[dict]:
    """B0 baseline: the LLM alone, no retrieval, no rules about citations."""
    return [{"role": "system", "content": PLAIN_SYSTEM}, {"role": "user", "content": question}]
