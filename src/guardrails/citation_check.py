"""
Citation check: every sentence of an answer must cite a passage we actually retrieved.

The LLM is told to end each sentence with a tag such as [IT25-202-SLABS]. Here we split the
answer into sentences, read the tags, and drop any sentence that has no tag or only tags
that are not among the retrieved passages (a made-up ID is a sign of hallucination).
Small LLMs often put the tag only at the end of a short run of sentences, so an untagged
sentence is covered by the next valid tag in the same paragraph ("group citation"); untagged
sentences with no valid tag after them are still dropped.
Invalid tags are removed from kept sentences and reported, so we can measure citation validity.
"""
from __future__ import annotations

import re

# [IT25-202-SLABS] or [GST-RATES-2025, IT-80C] (several IDs separated by commas)
TAG_RE = re.compile(r"\[\s*([A-Za-z0-9][A-Za-z0-9_\-\.]*(?:\s*[,;]\s*[A-Za-z0-9][A-Za-z0-9_\-\.]*)*)\s*\]")
_TAG = r"\[[^\[\]]{1,80}\]"
_ABBREV = {"rs", "no", "e.g", "i.e", "vs", "sec", "u/s", "s", "approx", "etc", "viz", "nos", "dr", "mr", "mrs", "st"}


def split_sentences(text: str) -> list[str]:
    """Split into sentences, keeping citation tags that follow a full stop with that sentence."""
    out: list[str] = []
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        start = 0
        for m in re.finditer(rf"[.!?](?:\s*{_TAG})*(?=\s|$)", line):
            words = line[start:m.start() + 1].split()
            last = words[-1].lower().rstrip(".") if words else ""
            if last in _ABBREV and "[" not in m.group(0):
                continue  # "Rs. 75,000" is not the end of a sentence
            piece = line[start:m.end()].strip()
            if piece:
                out.append(piece)
            start = m.end()
        rest = line[start:].strip()
        if rest:
            out.append(rest)
    return out


def extract_ids(sentence: str) -> list[str]:
    ids = []
    for m in TAG_RE.finditer(sentence):
        ids.extend(x.strip().upper() for x in re.split(r"[,;]", m.group(1)) if x.strip())
    return ids


def check_citations(answer: str, retrieved_ids: list[str], extra_valid: tuple[str, ...] = ("CALC",)) -> dict:
    """Return {"answer", "kept", "dropped", "invalid_ids", "n_tags", "n_valid_tags",
    "kept_sentences", "dropped_sentences", "n_sentences"}."""
    valid = {i.upper() for i in retrieved_ids} | set(extra_valid)
    kept, dropped, invalid = [], [], []
    pending: list[str] = []   # untagged sentences waiting for a tag later in the paragraph
    n_tags = n_valid = n_inherited = 0
    for para in [p for p in answer.split("\n") if p.strip()]:
        for sent in split_sentences(para):
            ids = extract_ids(sent)
            good = [i for i in ids if i in valid]
            bad = [i for i in ids if i not in valid]
            n_tags += len(ids)
            n_valid += len(good)
            invalid.extend(b for b in bad if b not in invalid)
            if not ids:
                pending.append(sent)
                continue
            if good:
                cleaned = sent
                for m in list(TAG_RE.finditer(sent)):
                    tag_ids = [x.strip().upper() for x in re.split(r"[,;]", m.group(1))]
                    keep_ids = [x for x in tag_ids if x in valid]
                    new = "[" + ", ".join(keep_ids) + "]" if keep_ids else ""
                    cleaned = cleaned.replace(m.group(0), new)
                kept.extend(pending)
                n_inherited += len(pending)
                kept.append(re.sub(r"\s{2,}", " ", cleaned).replace(" .", ".").strip())
            else:
                dropped.extend(pending)
                dropped.append(sent)
            pending = []
        dropped.extend(pending)   # end of paragraph: nothing left to cover them
        pending = []
    return {"answer": " ".join(kept), "kept": len(kept), "dropped": len(dropped),
            "invalid_ids": invalid, "n_tags": n_tags, "n_valid_tags": n_valid,
            "n_sentences": len(kept) + len(dropped), "n_inherited": n_inherited,
            "kept_sentences": kept, "dropped_sentences": dropped}
