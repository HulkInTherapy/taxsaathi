"""
Reversible masking of personal data before text is sent to an external LLM.

`guardrails/pii.py` replaces PII with a fixed tag ([PAN]) and forgets it, which is right for
logs. The agents need more: the LLM must be able to say "the PAN on Form 16 differs from the
one on the certificate" without ever seeing either PAN. So each distinct value gets a numbered
placeholder (<PAN_1>, <PAN_2>, ...) and the mapping stays on our server, so we can put the real
values back into the final output if needed.

Detected automatically: e-mail, PAN, Aadhaar, phone (same regexes as guardrails/pii.py) and
bank account numbers that follow an "A/c" / "account no" label (bare long numbers are left
alone, because they are usually amounts). Names cannot be found reliably by regex, so callers
register known names (e.g. the employee name extracted from Form 16) with `add()`.
"""
from __future__ import annotations

import re
from typing import Any

from src.guardrails.pii import PATTERNS

ACCOUNT_RX = re.compile(
    r"(?i)\b(?:a/?c|acct|account)\.?\s*(?:no\.?|number|#)?\s*[:\-]?\s*(\d[\d\s-]{7,20}\d)")
PLACEHOLDER_RX = re.compile(r"<([A-Z]+)_(\d+)>")


class Masker:
    """Per-task mask table. Same value -> same placeholder for the whole task."""

    def __init__(self):
        self._by_value: dict[tuple[str, str], str] = {}
        self._by_token: dict[str, str] = {}
        self._counts: dict[str, int] = {}
        self._names: list[str] = []

    # ------------------------------------------------------------ table
    def _token(self, kind: str, value: str) -> str:
        key = (kind, _norm(value))
        if key not in self._by_value:
            self._counts[kind] = self._counts.get(kind, 0) + 1
            tok = f"<{kind}_{self._counts[kind]}>"
            self._by_value[key] = tok
            self._by_token[tok] = value
        return self._by_value[key]

    def add(self, value: str, kind: str = "NAME") -> str:
        """Register a value (e.g. a person's name) that must always be masked."""
        value = (value or "").strip()
        if len(value) < 3:
            return value
        tok = self._token(kind, value)
        if kind == "NAME" and value not in self._names:
            self._names.append(value)
            self._names.sort(key=len, reverse=True)  # longest first: "Asha Rao" before "Asha"
        return tok

    @property
    def table(self) -> dict[str, str]:
        """placeholder -> real value (never send this anywhere)."""
        return dict(self._by_token)

    # ------------------------------------------------------------ text
    def mask(self, text: str) -> str:
        if not text:
            return text
        for name in self._names:
            text = re.sub(re.escape(name), self._by_value[("NAME", _norm(name))], text, flags=re.I)
        text = ACCOUNT_RX.sub(lambda m: m.group(0).replace(m.group(1), self._token("ACCOUNT", m.group(1))), text)
        for kind, rx in PATTERNS:
            text = rx.sub(lambda m, k=kind: self._token(k, m.group(0)), text)
        return text

    def unmask(self, text: str) -> str:
        if not text:
            return text
        return PLACEHOLDER_RX.sub(lambda m: self._by_token.get(m.group(0), m.group(0)), text)

    # ------------------------------------------------------------ nested objects
    def mask_obj(self, obj: Any) -> Any:
        return _walk(obj, self.mask)

    def unmask_obj(self, obj: Any) -> Any:
        return _walk(obj, self.unmask)


def _norm(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper()


def _walk(obj: Any, fn) -> Any:
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, dict):
        return {k: _walk(v, fn) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_walk(v, fn) for v in obj)
    return obj
