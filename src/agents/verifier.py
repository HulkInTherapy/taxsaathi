"""
Verifier agent: nothing reaches the user unverified.

Given the user-facing texts other agents drafted (finding explanations, ITR reasons, GST advice,
regime explanation, savings recommendations), it:

  1. splits them into atomic factual claims (LLM, verifier role - a different model family from
     the agents that wrote the drafts);
  2. gathers evidence: passages from the knowledge base for each legal claim (the RAG pipeline,
     the same retrieval as search_tax_law) and the task's computed facts (calculator results,
     cross-check findings, ITR rules, extracted figures);
  3. judges each claim supported / unsupported / contradicted against that evidence (LLM), and
     independently checks every rupee amount in a claim against the numbers present in the
     evidence (deterministic: an amount that appears nowhere is unsupported);
  4. sends texts with failing claims back for revision (LLM rewrite using only the evidence),
     and re-verifies, at most MAX_ROUNDS times. Claims still unsupported after that are removed
     from the text by the reviser, and the text is marked for confirmation with a CA.

Retrieval for evidence runs through the pipeline directly, bounded by MAX_CLAIMS per round, so
verification never eats into the 15-call tool budget the agents share.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Literal

from pydantic import BaseModel, Field

from src.llm import provider as prov

ENABLED = os.environ.get("TAXOT_VERIFIER", "1") != "0"
MAX_ROUNDS = 2
MAX_CLAIMS = 12
JUDGE_BATCH = 6        # claims per judge call: keeps each structured reply well inside the output budget
REVISE_MAX_TOKENS = 4000   # the reviser rewrites whole texts; a reasoning model ran out at 1500 and returned nothing
PASSAGES_PER_CLAIM = 3
SECTION_PASSAGES = 2   # extra passages for each section a claim names (80C, 194A, 80CCD(1B)...)
REPLACEMENT = "This point could not be verified against official sources."
UNVERIFIED_NOTE = " (Some points here could not be verified against official sources; please confirm with a CA.)"


class Claim(BaseModel):
    id: int
    key: str = Field(..., description="The key of the text the claim came from")
    text: str = Field(..., description="One atomic factual statement, self-contained")
    kind: Literal["law", "user_figure", "other"] = Field(
        ..., description="law = a rule, limit, rate, threshold, section or deadline; user_figure = a statement about "
                         "this user's own amounts or documents; other = anything else factual")


class ClaimList(BaseModel):
    """Submit the factual claims found in the texts."""
    claims: list[Claim]


class Verdict(BaseModel):
    claim_id: int
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence: list[str] = Field(default_factory=list, description="Passage ids, or 'computed' for computed facts")
    reason: str = Field("", description="Short reason (at most 20 words), especially when not supported")


class Verdicts(BaseModel):
    """Submit a verdict for every claim."""
    verdicts: list[Verdict]


class RevisedText(BaseModel):
    key: str
    text: str


class Revisions(BaseModel):
    """Submit the revised texts."""
    texts: list[RevisedText]


EXTRACT_SYSTEM = """You split drafts written for an Indian taxpayer into atomic factual claims for fact-checking.
Each claim must be one checkable statement (a tax rule, limit, rate, section, deadline, or a statement
about the user's own figures). Skip greetings, pure advice ("keep your receipts") and opinions.
Resolve pronouns so each claim stands alone. Keep the key of the text it came from. Call ClaimList."""

JUDGE_SYSTEM = """You are a strict fact-checker for Indian income tax and GST statements.
For each claim decide, using ONLY the evidence given:
- supported: the evidence states it (or it follows directly, e.g. arithmetic on the computed facts);
- contradicted: the evidence states something different;
- unsupported: the evidence does not establish it.
Claims about the user's own amounts are checked against COMPUTED FACTS. Claims about the law are
checked against the PASSAGES. Do not use your own knowledge of tax law. Call Verdicts once with a
verdict for every claim id."""

REVISE_SYSTEM = """You revise short texts for an Indian taxpayer so that every statement is supported.
For each text: correct claims that the evidence contradicts, and delete claims it does not support,
using ONLY the evidence. Keep everything else, the tone and the length roughly the same. Do not add
new facts. Return every text you were given via Revisions, with the same keys."""


# ------------------------------------------------------------------ deterministic amount check
AMOUNT_RX = re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lakhs|crore|cr)?|"
                       r"\b([\d]+(?:\.\d+)?)\s*(lakh|lakhs|crore)\b", re.IGNORECASE)


def amounts_in(text: str) -> set[int]:
    out = set()
    for m in AMOUNT_RX.finditer(text or ""):
        num, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        try:
            v = float(num.replace(",", ""))
        except ValueError:
            continue
        mult = {"lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "cr": 1e7}.get((unit or "").lower(), 1)
        out.add(int(round(v * mult)))
    return out


PERCENT_RX = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|per\s*cent|percent)", re.IGNORECASE)


def percents_in(text: str) -> set[float]:
    return {float(m.group(1)) for m in PERCENT_RX.finditer(text or "")}


def numbers_in(obj) -> set[int]:
    """Every integer that appears in a structure or text (amounts written with or without commas)."""
    s = obj if isinstance(obj, str) else json.dumps(obj, default=str, ensure_ascii=False)  # keep ₹ (escaped \\u20b9 merges digits)
    nums = {int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", s) if x.replace(",", "").isdigit()}
    return nums | amounts_in(s)


def _close(a: int, pool: set[int]) -> bool:
    return a in pool or any(abs(a - b) <= max(1, 0.005 * b) for b in pool if b > 999)


# ------------------------------------------------------------------ main entry
def verify(texts: dict[str, str], computed: dict, ctx, usage=None, retrieval_config: str | None = None) -> dict:
    """
    texts: {key: user-facing text}. computed: trusted facts (figures, calculator, cross-check, ITR rules).
    Returns {"texts": revised texts, "report": {...}}.
    """
    t0 = time.perf_counter()
    texts = {k: v for k, v in texts.items() if v and v.strip()}
    report = {"enabled": ENABLED, "rounds": 0, "claims": [], "revised_keys": [], "unresolved": [], "ms": 0}
    if not ENABLED or not texts:
        return {"texts": texts, "report": report}
    usage = usage or ctx.usage
    current = dict(texts)
    to_check = dict(texts)          # texts that passed a round are final; only revised ones are re-checked
    computed_nums = numbers_in(computed)
    for rnd in range(1, MAX_ROUNDS + 1):
        report["rounds"] = rnd
        claims = _extract(to_check, ctx, usage)
        if not claims:
            if rnd == 1:
                report["extraction_empty"] = True
            break
        evidence = _evidence(claims, ctx, retrieval_config)
        verdicts = _judge(claims, evidence, computed, ctx, usage)
        report["judge_missing"] = report.get("judge_missing", 0) + sum(c.id not in verdicts for c in claims)
        # deterministic amount check overrides "supported"
        pool = computed_nums | numbers_in([p["text"] for p in evidence.values()])
        pct_pool = percents_in(json.dumps(computed, default=str, ensure_ascii=False) + " " +
                               " ".join(p["text"] for p in evidence.values()))
        for c in claims:
            v = verdicts.setdefault(c.id, {"verdict": "unsupported", "evidence": [], "reason": "no verdict returned"})
            bad = [a for a in amounts_in(c.text) if not _close(a, pool)]
            bad_pct = [x for x in percents_in(c.text) if x not in pct_pool]
            if (bad or bad_pct) and v["verdict"] == "supported":
                v.update(verdict="unsupported",
                         reason=f"amount(s) {bad + [f'{x:g}%' for x in bad_pct]} not found in any evidence")
        failing = [c for c in claims if verdicts[c.id]["verdict"] != "supported"]
        report["claims"].append([{"round": rnd, **c.model_dump(), **verdicts[c.id]} for c in claims])
        if not failing:
            break
        keys = sorted({c.key for c in failing if c.key in current})
        revised = _revise({k: current[k] for k in keys}, failing, evidence, computed, ctx, usage)
        for k, v in revised.items():
            if k in current and v.strip():
                current[k] = v
        report["revised_keys"] = sorted(set(report["revised_keys"]) | set(revised))
        to_check = {k: current[k] for k in keys}
        if rnd == MAX_ROUNDS:   # still failing after the last revision: mark, don't loop forever
            final_claims = _extract({k: current[k] for k in keys}, ctx, usage)
            if final_claims:
                ev2 = _evidence(final_claims, ctx, retrieval_config)
                v2 = _judge(final_claims, ev2, computed, ctx, usage)
                report["judge_missing"] = report.get("judge_missing", 0) + sum(c.id not in v2 for c in final_claims)
                still = [c for c in final_claims if v2.get(c.id, {}).get("verdict") != "supported"]
                for c in still:
                    report["unresolved"].append({"key": c.key, "claim": c.text})
                    if c.key in current:
                        current[c.key], removed = drop_sentence(current[c.key], c.text)
                        if removed:
                            report.setdefault("removed_sentences", []).append({"key": c.key, "sentence": removed})
                for k in {c.key for c in still if c.key in current}:
                    current[k] = current[k].rstrip() + UNVERIFIED_NOTE
    report["ms"] = int((time.perf_counter() - t0) * 1000)
    report["summary"] = _summary(report)
    return {"texts": current, "report": report}


def _summary(report: dict) -> dict:
    first = report["claims"][0] if report["claims"] else []
    return {"claims_checked": len(first),
            "initially_failing": sum(1 for r in first if r["verdict"] != "supported"),
            "final_failing": len(report["unresolved"]), "revised_texts": len(report["revised_keys"]),
            "rounds": report["rounds"], "judge_missing": report.get("judge_missing", 0)}


# ------------------------------------------------------------------ text helpers
_WORD = re.compile(r"[a-z0-9₹]+")


def _words(t: str) -> set[str]:
    return {w for w in _WORD.findall((t or "").lower()) if len(w) > 2 or w.isdigit()}


def match_key(key: str, claim_text: str, texts: dict[str, str]) -> str:
    """The draft a claim belongs to: exact key, key ignoring punctuation, else the text sharing most words."""
    if key in texts:
        return key
    norm = lambda k: re.sub(r"[^a-z0-9]", "", (k or "").lower())  # noqa: E731
    for k in texts:
        if norm(k) == norm(key):
            return k
    cw = _words(claim_text)
    best = max(texts, key=lambda k: len(cw & _words(texts[k])), default=key)
    return best if cw & _words(texts.get(best, "")) else key


def drop_sentence(text: str, claim: str) -> tuple[str, str | None]:
    """Remove the sentence that best matches a claim (deterministic last resort)."""
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    cw = _words(claim)
    scored = [(len(cw & _words(s_)) / max(1, len(cw)), i) for i, s_ in enumerate(sents)]
    score, idx = max(scored, default=(0, -1))
    if score < 0.5:
        return text, None
    removed = sents.pop(idx)
    return (" ".join(sents) or REPLACEMENT), removed


# ------------------------------------------------------------------ steps
def _extract(texts: dict[str, str], ctx, usage) -> list[Claim]:
    body = "\n\n".join(f"[{k}]\n{v}" for k, v in texts.items())
    reply = prov.chat([{"role": "system", "content": EXTRACT_SYSTEM}, {"role": "user", "content": body}],
                      role="verifier", tools=[ClaimList], tool_choice="ClaimList", masker=ctx.masker, usage=usage)
    call = next((c for c in reply.tool_calls if c["name"] == "ClaimList"), None)
    if not call:
        return []
    out = []
    for i, raw in enumerate((call["args"].get("claims") or [])[:MAX_CLAIMS]):
        if isinstance(raw, str):
            raw = {"text": raw}
        kind = str(raw.get("kind", "")).lower()
        raw = {**raw, "kind": "law" if ("law" in kind or "rule" in kind) else
               ("user_figure" if ("user" in kind or "figure" in kind or "amount" in kind) else "other"),
               "key": raw.get("key") or next(iter(texts))}
        try:
            c = Claim.model_validate({**raw, "id": i + 1})
        except Exception:  # noqa: BLE001 - skip malformed claim
            continue
        c.key = match_key(c.key, c.text, texts)
        out.append(c)
    return out


SECTION_RX = re.compile(r"(?<![\w(])(\d{1,3}[A-Z]{0,5}(?:\(\w{1,4}\))?)(?![\w(])", re.IGNORECASE)


def sections_in(text: str) -> set[str]:
    """Section references like 80C, 80CCD(1B), 194A, 10(13A), 87A, 115BAC, 44ADA (not plain amounts or years)."""
    out = set()
    for m in SECTION_RX.finditer(text or ""):
        tok = m.group(1).upper()
        if re.search(r"[A-Z(]", tok) and not re.fullmatch(r"\d{4}", tok):
            out.add(tok.replace(" ", ""))
    return out


def _section_passages(claim_text: str, ctx) -> list[str]:
    """Knowledge-base passages whose `section` field names a section the claim mentions."""
    secs = sections_in(claim_text)
    if not secs:
        return []
    hits = []
    for ch in ctx.pipeline.chunks:
        field = (ch.get("section") or "").upper().replace(" ", "")
        parts = set(re.split(r"[/,;]|->", field))
        if secs & parts:
            hits.append(ch["id"])
    return hits[:SECTION_PASSAGES]


def _evidence(claims: list[Claim], ctx, retrieval_config: str | None) -> dict[str, dict]:
    by_id = ctx.chunk_index()
    passages: dict[str, dict] = {}
    for c in claims:
        if c.kind != "law":
            continue
        r = ctx.pipeline.retrieve_only(c.text, retrieval_config or ctx.retrieval_config or "C6")
        for pid in r["ids"][:PASSAGES_PER_CLAIM] + _section_passages(c.text, ctx):
            if pid in by_id and pid not in passages:
                ch = by_id[pid]
                passages[pid] = {"id": pid, "title": ch["title"], "text": ch["text"][:900],
                                 "effective": f"{ch.get('effective_from', '')}..{ch.get('effective_to', '')}"}
    return passages


def _judge(claims: list[Claim], evidence: dict, computed: dict, ctx, usage) -> dict[int, dict]:
    """Verdicts by claim id, judged JUDGE_BATCH claims per call; a claim whose reply was cut off or malformed is
    judged once more on its own batch before it is left without a verdict."""
    out: dict[int, dict] = {}
    for i in range(0, len(claims), JUDGE_BATCH):
        out.update(_judge_batch(claims[i:i + JUDGE_BATCH], evidence, computed, ctx, usage))
    missing = [c for c in claims if c.id not in out]
    for i in range(0, len(missing), JUDGE_BATCH):
        out.update(_judge_batch(missing[i:i + JUDGE_BATCH], evidence, computed, ctx, usage))
    return out


def _judge_batch(claims: list[Claim], evidence: dict, computed: dict, ctx, usage) -> dict[int, dict]:
    body = ("CLAIMS:\n" + "\n".join(f"{c.id}. ({c.kind}) {c.text}" for c in claims)
            + "\n\nPASSAGES:\n" + ("\n".join(f"[{p['id']}] {p['title']} (effective {p['effective']}): {p['text']}"
                                             for p in evidence.values()) or "(none)")
            + "\n\nCOMPUTED FACTS (exact, from the calculator, the documents and deterministic rules):\n"
            + json.dumps(computed, default=str, ensure_ascii=False)[:6000])
    reply = prov.chat([{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": body}],
                      role="verifier", tools=[Verdicts], tool_choice="Verdicts", masker=ctx.masker, usage=usage)
    call = next((c for c in reply.tool_calls if c["name"] == "Verdicts"), None)
    out: dict[int, dict] = {}
    for raw in (call["args"].get("verdicts") if call else None) or []:
        try:
            v = Verdict.model_validate(raw)
        except Exception:  # noqa: BLE001
            continue
        out[v.claim_id] = {"verdict": v.verdict, "evidence": v.evidence, "reason": v.reason}
    return out


def _revise(texts: dict[str, str], failing: list[Claim], evidence: dict, computed: dict, ctx, usage) -> dict[str, str]:
    body = ("TEXTS:\n" + "\n".join(f"[{k}] {v}" for k, v in texts.items())
            + "\n\nCLAIMS THAT FAILED VERIFICATION:\n" + "\n".join(f"- [{c.key}] {c.text}" for c in failing)
            + "\n\nEVIDENCE PASSAGES:\n" + ("\n".join(f"[{p['id']}] {p['text']}" for p in evidence.values()) or "(none)")
            + "\n\nCOMPUTED FACTS:\n" + json.dumps(computed, default=str, ensure_ascii=False)[:4000])
    reply = prov.chat([{"role": "system", "content": REVISE_SYSTEM}, {"role": "user", "content": body}],
                      role="planner", tools=[Revisions], tool_choice="Revisions", masker=ctx.masker, usage=usage,
                      max_tokens=REVISE_MAX_TOKENS)
    call = next((c for c in reply.tool_calls if c["name"] == "Revisions"), None)
    out = {}
    for raw in (call["args"].get("texts") if call else None) or []:
        try:
            r = RevisedText.model_validate(raw)
        except Exception:  # noqa: BLE001
            continue
        key = match_key(r.key, r.text, texts)
        if key in texts:
            out[key] = r.text
    return out
