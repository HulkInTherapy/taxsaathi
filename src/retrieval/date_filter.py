"""
Date filter: keep only passages that were in force during the question's period.

Every chunk may carry effective_from / effective_to dates (empty = open-ended). A chunk is
eligible when its validity range overlaps the query period [start, end]. Chunks without any
dates (general explanations, FAQs) are always eligible. This is what stops the system from
quoting GST 2.0 rates for an "August 2025" question, or the 2025 Act for FY 2024-25.
"""
from __future__ import annotations

import re

from datetime import date

_MIN, _MAX = date(1900, 1, 1), date(9999, 12, 31)


def chunk_range(chunk: dict) -> tuple[date, date]:
    f = chunk.get("effective_from") or ""
    t = chunk.get("effective_to") or ""
    return (date.fromisoformat(f) if f else _MIN, date.fromisoformat(t) if t else _MAX)


def is_eligible(chunk: dict, start: date, end: date) -> bool:
    """True if the chunk's [from, to] range overlaps [start, end] (inclusive)."""
    cf, ct = chunk_range(chunk)
    return cf <= end and ct >= start


def filter_by_period(chunks: list[dict], indices: list[int], start: date, end: date) -> tuple[list[int], list[int]]:
    """Split candidate indices into (kept, removed), preserving order."""
    kept, removed = [], []
    for i in indices:
        (kept if is_eligible(chunks[i], start, end) else removed).append(i)
    return kept, removed


# Chunk IDs of the same rule for different periods share a stem: IT-NEW-REBATE-FY2526 /
# IT-NEW-REBATE-TY2627, GST-RATE-AC-PRE / GST-RATE-AC-POST, IT-NEW-STDDED-1961 / -TY2627.
_PERIOD_SUFFIX = re.compile(r"-(FY\d{4}|TY\d{4}|PRE20|PRE|POST|1961|2025ACT)$")


def rule_stem(chunk_id: str) -> str:
    return _PERIOD_SUFFIX.sub("", chunk_id)


def _successors(chunks: list[dict], i: int, start: date, end: date) -> list[int]:
    """Versions of chunk i's rule that are valid for [start, end]: same ID stem first, then the
    same topic — but only true successors/predecessors (their dates don't overlap chunk i's)."""
    ci = chunks[i]
    fi, ti = chunk_range(ci)
    stem = rule_stem(ci["id"])
    same_stem, same_topic = [], []
    for j, c in enumerate(chunks):
        if j == i or not is_eligible(c, start, end):
            continue
        fj, tj = chunk_range(c)
        if not (fj > ti or tj < fi):        # overlapping in time = a different rule, not a version
            continue
        if _PERIOD_SUFFIX.search(ci["id"]) and rule_stem(c["id"]) == stem:
            same_stem.append(j)
        elif ci.get("topic") and c.get("topic") == ci["topic"]:
            same_topic.append(j)
    return same_stem + same_topic


def _has_earlier_version(chunks: list[dict], i: int) -> bool:
    """True if an older version of chunk i's rule exists (same stem or topic, ends before i starts)."""
    ci, (fi, _) = chunks[i], chunk_range(chunks[i])
    for k, c in enumerate(chunks):
        if k == i or chunk_range(c)[1] >= fi:
            continue
        if rule_stem(c["id"]) == rule_stem(ci["id"]) or (ci.get("topic") and c.get("topic") == ci["topic"]):
            return True
    return False


def period_twins(chunks: list[dict], ranked: list[int], start: date, end: date) -> tuple[list[int], dict]:
    """Date filter with substitution. When a passage is from the wrong period, put the version of
    the SAME rule that is valid for the asked period in its place (moving it up if it was ranked
    lower). Search often finds the right rule but the wrong year's version; without this the
    correct version could be missing from the candidates entirely or ranked far below.
    If the user asks about a period BEFORE our sources begin (e.g. FY 2023-24) and no version
    covers it, the earliest version we have is kept and flagged, rather than returning nothing.
    Returns (new order, {removed_id: replacement_id or "kept-closest"})."""
    out, seen, swaps = [], set(), {}
    for i in ranked:
        if i in seen:
            continue
        if is_eligible(chunks[i], start, end):
            out.append(i); seen.add(i)
            continue
        twin = next((j for j in _successors(chunks, i, start, end) if j not in seen), None)
        if twin is not None:
            out.append(twin); seen.add(twin); swaps[chunks[i]["id"]] = chunks[twin]["id"]
        elif end < chunk_range(chunks[i])[0] and not _has_earlier_version(chunks, i):
            out.append(i); seen.add(i); swaps[chunks[i]["id"]] = "kept-closest"
    return out, swaps
