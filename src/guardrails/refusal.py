"""
Refusal gate: decide whether TaxSaathi should answer or politely refuse and escalate to a CA.

Two reasons to refuse: (1) the intent classifier says the question is out of scope (crypto,
foreign income, evasion, prompt injection, chit-chat, complex CA-only cases), or (2) the best
reranker score is below a threshold, meaning our knowledge base has no passage that really
answers it — answering anyway would invite hallucination. Calculations skip check (2)
because the calculator itself is deterministic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from src import config


@dataclass
class GateResult:
    passed: bool
    reason: str | None
    message: str | None
    top_score: float | None
    threshold: float | None

    def to_dict(self) -> dict:
        return asdict(self)


def gate(intent: dict, top_score: float | None, threshold: float | None, use_score: bool) -> GateResult:
    """intent: output of guardrails.intent.classify. use_score: True for configs C3+."""
    label = intent["label"]
    if label == "out_of_scope":
        if intent.get("rule") == "prompt-injection pattern":
            reason = "prompt_injection"
            msg = ("I can only answer Indian income-tax and GST questions from official sources, "
                   "and I can't change how I work. ")
        else:
            reason = "out_of_scope"
            msg = ("This question is outside what TaxSaathi can answer reliably (it covers "
                   "individual income tax and GST basics only). ")
        return GateResult(False, reason, msg + config.CA_ESCALATION, top_score, threshold)
    if use_score and label != "calculation" and threshold is not None:
        if top_score is None or top_score < threshold:
            msg = ("I could not find this in my verified sources, so I would rather not guess. "
                   + config.CA_ESCALATION)
            return GateResult(False, "low_retrieval_score", msg, top_score, threshold)
    return GateResult(True, None, None, top_score, threshold)
