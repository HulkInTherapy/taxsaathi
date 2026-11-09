"""
PII (personal data) masking.

Users sometimes paste their PAN, Aadhaar number, phone or e-mail into a question. We never
need these to answer, so they are replaced with placeholders like [PAN] before the text is
logged or sent to the LLM. Regexes: PAN = 5 letters + 4 digits + 1 letter; Aadhaar = 12
digits (optionally in groups of 4); Indian mobile = 10 digits starting 6-9 (optional +91).
"""
from __future__ import annotations

import re

PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("PAN", re.compile(r"\b[A-Za-z]{5}[0-9]{4}[A-Za-z]\b")),
    ("AADHAAR", re.compile(r"(?<!\d)(?<!\d,)[2-9]\d{3}[\s-]?\d{4}[\s-]?\d{4}(?!\d|,\d)")),
    ("PHONE", re.compile(r"(?<!\d)(?<!\d,)(?:\+91[\s-]?|0)?[6-9]\d{4}[\s-]?\d{5}(?!\d|,\d)")),
]


def mask_pii(text: str) -> tuple[str, dict]:
    """Return (masked_text, counts) e.g. ("my PAN is [PAN]", {"PAN": 1})."""
    counts: dict[str, int] = {}
    for name, rx in PATTERNS:
        text, n = rx.subn(f"[{name}]", text)
        if n:
            counts[name] = n
    return text, counts
