"""
A simulated user for scripted runs: answers the orchestrator from a synthetic persona's true facts.

Answers to fact questions are written as natural-language text (so the orchestrator's LLM fact
parsing is exercised, not bypassed); approvals are given unless told otherwise. Facts are only
volunteered when asked, mimicking a real user who answers the questions put to them.
"""
from __future__ import annotations

from scripts import synth_documents as sd
from src.calculator.tax import format_inr

GOALS = {
    "document_check": "Please check my tax documents for FY 2025-26 before I file.",
    "filing_prep": "Help me prepare my income tax return for FY 2025-26: which ITR form, which regime, and what I "
                   "need to do.",
    "tax_saving": "How can I legally reduce my income tax for FY 2025-26? Show me the options and the saving.",
}


class SimUser:
    def __init__(self, persona_id: str, approve: bool = True):
        self.p = next(x for x in sd.load_personas() if x["id"] == persona_id)
        self.m = sd.build(self.p)
        self.approve = approve
        self.questions: list[dict] = []

    @property
    def goal(self) -> str:
        g = GOALS[self.p["workflow"] if self.p["workflow"] in GOALS else "filing_prep"]
        return g + (" " + self.p["user_says"] if self.p.get("user_says") else "")

    def documents(self) -> list[tuple[str, bytes]]:
        gt = next(g for g in _truth() if g["persona_id"] == self.p["id"])
        return [((sd.config.ROOT / d["file"]).name, (sd.config.ROOT / d["file"]).read_bytes()) for d in gt["documents"]]

    def answer(self, interrupt: dict):
        self.questions.append(interrupt)
        if interrupt.get("type") == "approval":
            return {"approved": self.approve}
        asked = {f["name"] for f in interrupt.get("fields", [])}
        return {"text": self.facts_text(asked)}

    # ------------------------------------------------------------ facts as prose
    def facts_text(self, asked: set[str]) -> str:
        p, m = self.p, self.m
        f = p.get("itr_facts") or {}
        emps = [e for e in m["employers"] if not e["pension"]]
        lines = []
        if "age" in asked:
            lines.append(f"I am {p['age']} years old.")
        if "residential_status" in asked:
            lines.append("I live in India and am a resident.")
        if p.get("freelance") and asked & {"freelance_receipts", "business_presumptive", "cash_receipts_over_5pct"}:
            fl = p["freelance"]
            lines.append(f"My freelance receipts were {format_inr(fl['receipts'])}. I use the presumptive scheme, no "
                         f"detailed books. {'About 10% came in cash.' if fl.get('cash_over_5pct') else 'All payments came by bank transfer.'}")
        elif "freelance_receipts" in asked:
            lines.append("I have no freelance or business income.")
        cg = []
        if f.get("short_term_capital_gains"):
            cg.append("I had short-term capital gains from selling shares")
        if f.get("ltcg_112a"):
            cg.append(f"long-term gains of {format_inr(f['ltcg_112a'])} on equity mutual funds")
        if f.get("other_capital_gains"):
            cg.append("I sold a flat (property) this year")
        if asked & {"short_term_capital_gains", "other_capital_gains"}:
            lines.append(("; ".join(cg) + ".") if cg else "No capital gains of any kind.")
        flags = [("foreign_assets_or_income", "I have foreign assets (RSUs in a US brokerage)"),
                 ("company_director", "I am a director of a private company"),
                 ("unlisted_shares", "I hold unlisted shares"),
                 ("fno_trading", "I trade futures and options"),
                 ("losses_to_carry_forward", "I have losses to carry forward")]
        said = [t for k, t in flags if f.get(k)]
        if asked & {k for k, _ in flags}:
            lines.append(("; ".join(said) + ".") if said else
                         "No foreign assets or income, I'm not a company director, no unlisted shares, no F&O trading.")
        if "house_properties" in asked:
            lines.append(f"I own {f.get('house_properties', 0)} house properties." if f.get("house_properties")
                         else "I don't own any house property.")
        if "epf_annual" in asked and emps:
            lines.append(f"My PF deduction for the year was {format_inr(sum(e['epf_annual'] for e in emps))}.")
        if "other_80c" in asked:
            v = p.get("other_80c", 0)
            lines.append(f"Other 80C investments (PPF/ELSS/LIC) besides PF: {format_inr(v)}." if v else
                         "No 80C investments besides PF.")
        if "health_80d" in asked:
            v = p.get("health_80d", 0)
            lines.append(f"Health insurance for myself: {format_inr(v)}." if v else "No health insurance premium.")
        if "health_80d_parents" in asked or p.get("health_80d_parents"):
            v = p.get("health_80d_parents", 0)
            lines.append(f"Parents' health insurance: {format_inr(v)}; my parents are "
                         f"{'senior citizens' if p.get('parents_senior') else 'below 60'}." if v else
                         "I don't pay for my parents' health insurance.")
        if "nps_80ccd1b" in asked:
            v = p.get("nps_80ccd1b", 0)
            lines.append(f"Own NPS contribution under 80CCD(1B): {format_inr(v)}." if v else "No NPS contribution.")
        if "home_loan_interest" in asked:
            v = p.get("home_loan_interest", 0)
            lines.append(f"Home-loan interest paid: {format_inr(v)}." if v else "No home loan.")
        if "rent_monthly" in asked:
            rent = p.get("rent_monthly", 0)
            lines.append(f"I pay rent of {format_inr(rent)} a month in {'a metro city (Mumbai)' if p['metro'] else 'Pune'}."
                         if rent else "I don't pay rent.")
        if asked & {"basic_monthly", "hra_monthly", "metro_city"} and p.get("rent_monthly") and emps:
            if len(emps) == 1:
                e = emps[0]
                lines.append(f"My basic salary is {format_inr(e['monthly']['basic'])} a month and HRA "
                             f"{format_inr(e['monthly']['hra'])} a month. {'I live in Mumbai, a metro.' if p['metro'] else ''}")
            else:
                lines.append(f"My HRA exemption for the year, worked out with my employers, is "
                             f"{format_inr(sum(e['hra_exempt'] for e in emps))}.")
        return " ".join(lines) or "Nothing else to add."


_TRUTH = None


def _truth() -> list[dict]:
    global _TRUTH
    if _TRUTH is None:
        import json
        _TRUTH = [json.loads(line) for line in sd.GROUND_TRUTH_PATH.read_text().splitlines()]
    return _TRUTH
