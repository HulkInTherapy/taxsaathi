"""
Answer generation with a safety net.

1. Build the grounded prompt (passages + optional [CALC] block) and ask the local LLM.
2. Run the citation check: sentences without a valid [CHUNK-ID] are removed.
3. If the LLM is down, times out, or every sentence gets removed, fall back to an
   "extractive" answer: the best-matching sentences copied from the top passages, each with
   its ID. That answer is less fluent but always grounded.
"""
from __future__ import annotations

import re
import time

from src.calculator.tax import explanation, summary_text
from src.generation import llm, prompts
from src.guardrails.citation_check import check_citations, split_sentences
from src.nlp.dates import Period
from src.retrieval.bm25 import tokenize


TAG_STRIP = re.compile(r"\[[^\[\]]{1,80}\]")


def _numbers(text: str) -> set[str]:
    """Amounts/numbers in a text, normalised ("1,17,000" -> "117000"); ignores 1-2 digit numbers."""
    return {n.replace(",", "") for n in re.findall(r"\d[\d,]*\d|\d", text) if len(n.replace(",", "")) >= 3}


_GST_YEAR = re.compile(r"\b(For|In|During)\s+(the\s+)?(Tax\s+Year|FY|financial\s+year)\s+\d{4}-\d{2,4},?\s*", re.I)


def _strip_tax_year(text: str) -> str:
    """GST has no 'tax year'; drop a 'For Tax Year 2026-27,' opener the small LLM sometimes copies."""
    out = _GST_YEAR.sub("", text)
    return re.sub(r"(^|[.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), out)


def _best_sentences(question: str, chunk: dict, n: int = 1) -> list[str]:
    """Sentences of a passage ranked by word overlap with the question."""
    q = set(tokenize(question))
    sents = [s for s in split_sentences(chunk["text"]) if len(s.split()) >= 4]
    if not sents:
        return []
    scored = sorted(enumerate(sents), key=lambda kv: (-len(q & set(tokenize(kv[1]))), kv[0]))
    picked = sorted(scored[:n], key=lambda kv: kv[0])  # keep original order
    return [s for _, s in picked]


def _with_tag(sentence: str, cid: str) -> str:
    s = sentence.rstrip()
    if not s.endswith((".", "!", "?")):
        s += "."
    return f"{s} [{cid}]"


def extractive_answer(question: str, chunks: list[dict], calc: dict | None = None) -> str:
    """Grounded answer made only of copied sentences (no LLM)."""
    out = []
    if calc:
        return calc_answer(calc, chunks)
    for i, c in enumerate(chunks[:2]):
        out += [_with_tag(s, c["id"]) for s in _best_sentences(question, c, 2 if i == 0 else 1)]
    return " ".join(out) if out else "My sources do not cover this."


# ---------------------------------------------------------------- calculation answers
# LLM sentences that must never sit next to a calculator result.
# Sentences that talk ABOUT the passages instead of answering ("mentions cess…", "the passage
# does not clarify…") are useless to a taxpayer, so they are dropped like uncited sentences.
META_RE = re.compile(r"^\s*(it\s+|this\s+|the\s+passage\s+|passage\s+\S+\s+)?(mentions|explains|discusses|describes|"
                     r"states|covers|talks\s+about)\b|does\s+not\s+(specify|clarify|mention|say|state|explain)|"
                     r"\bthe\s+(passages?|sources?)\s+(say|says|mention|mentions|state|states)\b", re.I)

NOT_COVERED_RE = re.compile(
    r"do(es)?\s*n[o']t\s+cover|not\s+covered|sources?\s+(do|does)\s+not|no\s+information|not\s+mentioned|"
    r"cannot\s+(answer|calculate|determine|provide)|can'?t\s+(answer|calculate|determine)|unable\s+to|"
    r"not\s+(provided|available|specified)\s+in|outside\s+(the|my)\s+(scope|sources)|i\s+don'?t\s+know", re.I)
_REGIME_CLAIM = re.compile(r"\b(old|new)\s+(tax\s+)?regime\s+(is|would\s+be|will\s+be)\s+(better|cheaper|more\s+beneficial|beneficial)", re.I)
# Which KB topics are relevant to explaining a calculator result.
CALC_TOPICS = {"slabs", "rebate", "presumptive", "standard_deduction", "deductions", "new_regime_deductions",
               "old_regime_deductions", "regime_choice", "surcharge", "cess", "hra", "registration_freelancer", "mapping"}


def _tag_for(sentence: str, ids: dict) -> str:
    """Pick the KB chunk that supports a deterministic explanation sentence (falls back to CALC)."""
    low = sentence.lower()
    for key, words in (("presumptive", ("presumptive",)), ("std", ("standard deduction",)),
                       ("rebate", ("rebate", "marginal relief")), ("old_slabs", ("old regime",)),
                       ("new_slabs", ("slab tax", "basic exemption"))):
        if ids.get(key) and any(w in low for w in words):
            return ids[key]
    return "CALC"


def calc_answer(calc: dict, chunks: list[dict], llm_sentences: list[str] | None = None) -> str:
    """Deterministic plain-English explanation of a calculator result, each sentence cited,
    optionally followed by up to two vetted LLM sentences, and a GST note for foreign-client freelancers."""
    ids = calc.get("_source_ids") or {}
    out = [_with_tag(sent, _tag_for(sent, ids)) for sent in explanation(calc)]
    out += (llm_sentences or [])[:2]
    if calc.get("_gst_note"):
        out.append(calc["_gst_note"])
    return " ".join(out)


# Verdicts ("no tax", "you save", "new regime is better", "you have to pay") come only from the
# calculator. A small LLM sometimes writes "you would not have to pay any tax" next to ₹4.5 lakh.
VERDICT_RE = re.compile(r"\b(no|zero|nil|any)\s+tax|tax[- ]free|not\s+(have\s+to\s+)?pay|don'?t\s+(have\s+to\s+)?pay|"
                        r"\bsav(e|es|ing)\b|\bbetter\b|\bcheaper\b|\bhave\s+to\s+pay\b|\bwould\s+pay\b|\bowe\b", re.I)


def vet_calc_sentences(answer: str, calc: dict, chunks: list[dict], known: set[str]) -> list[str]:
    """Keep only LLM sentences that explain the calculator result: cited to a relevant passage,
    no amounts the calculator/passages don't contain, no "not covered", no contradicting verdict."""
    relevant = {c["id"] for c in chunks if c.get("topic") in CALC_TOPICS} | set((calc.get("_source_ids") or {}).values())
    keep = []
    for x in split_sentences(answer):
        cited = set(re.findall(r"\[([A-Z0-9][A-Z0-9\-_]+)\]", x))
        plain = TAG_STRIP.sub("", x)
        if "[CALC]" in x or not cited & relevant:
            continue
        # The deterministic explanation already states every number, so an LLM sentence with an
        # amount can only repeat it or mislabel it (e.g. pre-cess tax called "including cess").
        if NOT_COVERED_RE.search(plain) or _numbers(plain) or VERDICT_RE.search(plain):
            continue
        claim = _REGIME_CLAIM.search(plain)
        if claim and (calc["better"] == "same" or claim.group(1).lower() != calc["better"]):
            continue
        keep.append(x.strip())
    return keep


def generate(question: str, chunks: list[dict], period: Period | None, calc: dict | None = None,
             normalised: str | None = None, use_llm: bool = True) -> dict:
    """Return {"answer","raw","citation_check","fallback","fallback_reason","error","llm_ms"}."""
    ids = [c["id"] for c in chunks] + (["CALC"] if calc else [])
    calc_block = summary_text(calc) if calc else None
    raw, error, fallback_reason = None, None, None
    t0 = time.perf_counter()
    # Reviewed FAQ answers: a few passages that address a known, common confusion carry a
    # `short_answer` written and checked by the team. If such a passage is the top hit we use it
    # word for word (cited) instead of letting a small LLM paraphrase — and possibly drop — the key step.
    curated = (chunks[0].get("extra") or {}).get("short_answer") if chunks and not calc else None
    if curated:
        answer = f"{curated.strip()} [{chunks[0]['id']}]"
        check = check_citations(answer, ids)
        return {"answer": answer, "raw": None, "citation_check": check, "fallback": False,
                "fallback_reason": "curated_answer", "error": None, "llm_ms": 0}
    if use_llm:
        try:
            raw = llm.chat(prompts.grounded_messages(question, chunks, period, calc_block, normalised))
        except llm.LLMError as e:
            error = str(e)
            fallback_reason = "llm_error"
    else:
        fallback_reason = "llm_disabled"
    llm_ms = int((time.perf_counter() - t0) * 1000)

    if raw is not None:
        check = check_citations(raw, ids)
        no_info = "do not cover" in raw.lower() and check["kept"] == 0
        if calc:
            # Numbers always come from the calculator, never the LLM: lead with the deterministic
            # explanation, then add only LLM sentences that explain (cited to a relevant passage,
            # every amount also in the calculator result or passages, no "not covered", no verdict
            # that contradicts the calculator).
            known = _numbers(calc_block + " " + " ".join(explanation(calc)) + " " + " ".join(c["text"] for c in chunks))
            explain = vet_calc_sentences(check["answer"], calc, chunks, known) if check["kept"] else []
            return {"answer": calc_answer(calc, chunks, explain), "raw": raw, "citation_check": check,
                    "fallback": not explain, "fallback_reason": None if explain else "llm_added_nothing_useful",
                    "error": None, "llm_ms": llm_ms, "llm_kept": len(explain)}
        # Keep what the LLM wrote, minus "my sources do not cover this" filler: the safety gate already
        # found a relevant passage, so if nothing else is left we answer from that passage instead.
        useful = [x for x in split_sentences(check["answer"])
                  if not NOT_COVERED_RE.search(TAG_STRIP.sub("", x)) and not META_RE.search(TAG_STRIP.sub("", x))]
        if check["kept"] > 0 and useful:
            text = " ".join(useful)
            if chunks and sum(c.get("law") == "gst" for c in chunks) > len(chunks) / 2:
                text = _strip_tax_year(text)
            return {"answer": text, "raw": raw, "citation_check": check, "fallback": False,
                    "fallback_reason": None, "error": None, "llm_ms": llm_ms}
        no_info = no_info or (check["kept"] > 0 and not useful)
        fallback_reason = "llm_said_not_covered" if no_info else "all_sentences_dropped"
    else:
        check = {"kept": 0, "dropped": 0, "invalid_ids": [], "n_tags": 0, "n_valid_tags": 0, "n_sentences": 0}

    answer = extractive_answer(question, chunks, calc)
    return {"answer": answer, "raw": raw, "citation_check": check, "fallback": True,
            "fallback_reason": fallback_reason, "error": error, "llm_ms": llm_ms}


def generate_plain(question: str, use_llm: bool = True) -> dict:
    """B0 baseline: plain LLM answer (no passages, no citation check)."""
    t0 = time.perf_counter()
    if not use_llm:
        return {"answer": "(LLM disabled)", "raw": None, "error": "llm_disabled", "llm_ms": 0}
    try:
        raw = llm.chat(prompts.plain_messages(question))
        return {"answer": raw, "raw": raw, "error": None, "llm_ms": int((time.perf_counter() - t0) * 1000)}
    except llm.LLMError as e:
        return {"answer": "The language model is not available right now.", "raw": None,
                "error": str(e), "llm_ms": int((time.perf_counter() - t0) * 1000)}
