"""
Deterministic building blocks the orchestrator uses between agents.

* build_figures: documents (extracted fields + cross-check totals) + user facts -> calculator
  inputs, with the source of every number (shown to the user for approval);
* escalation_reasons: rules for cases Taxot must hand to a CA;
* itr_inputs: the facts itr_form_rules needs;
* build_checklist: the filing-ready checklist from the approved results.

No LLM here: these are bookkeeping rules that must be exact and testable.
"""
from __future__ import annotations

from src.calculator.tax import PRESUMPTIVE_LIMIT_CASH, PRESUMPTIVE_LIMIT_DIGITAL, format_inr
from src.agents.state import UserFacts

CAP_80TTA, CAP_80TTB = 10_000, 50_000


def age_category(age: int | None) -> str:
    if age is None or age < 60:
        return "below60"
    return "60to80" if age < 80 else "above80"


def hra_exemption(basic_m: int, hra_m: int, rent_m: int, metro: bool, months: int = 12) -> int:
    """Section 10(13A): least of HRA received, rent - 10% of basic, 50% (metro) / 40% of basic."""
    if not (rent_m and hra_m and basic_m):
        return 0
    return max(0, min(hra_m * months, rent_m * months - round(0.1 * basic_m * months),
                      round((0.5 if metro else 0.4) * basic_m * months)))


def _docs(extracted: dict, kind: str) -> list[dict]:
    return [d["fields"] for d in extracted.values() if d["type"] == kind and d.get("fields")]


def _via(f16: dict, prefix: str) -> int:
    for row in f16.get("chapter_via") or []:
        sec = (row.get("section") or "").upper().replace(" ", "")
        if sec.startswith(prefix):
            return row.get("gross_amount") or row.get("deductible_amount") or 0
    return 0


def build_figures(extracted: dict, facts: UserFacts, tax_year: str) -> dict:
    """Calculator inputs + provenance + TDS. `extracted` is TaskContext.extracted."""
    f16s = _docs(extracted, "form16")
    certs = _docs(extracted, "interest_certificate")
    slips = _docs(extracted, "salary_slip")
    prov: dict[str, str] = {}
    notes: list[str] = []

    salary = sum(f.get("gross_salary") or 0 for f in f16s)
    if f16s:
        prov["salary"] = "Form 16 (" + ", ".join(f.get("employer_name") or "employer" for f in f16s) + ")"
    if facts.salary_without_form16:
        salary += facts.salary_without_form16
        prov["salary"] = (prov.get("salary", "") + " + you said").strip(" +")

    savings = sum(a["interest"] for c in certs for a in c.get("accounts") or [] if a["account_type"] == "savings")
    interest = sum(c.get("total_interest") or sum(a["interest"] for a in c.get("accounts") or []) for c in certs)
    if certs:
        prov["interest"] = "interest certificates (" + ", ".join(c.get("bank_name") or "bank" for c in certs) + ")"
    if facts.other_interest:
        interest += facts.other_interest
        prov["interest"] = (prov.get("interest", "") + " + you said").strip(" +")

    # ---- 80C: PF + other investments
    old_f16 = [f for f in f16s if f.get("new_regime") is False]
    epf = facts.epf_annual
    if epf is None and slips:
        epf = sum(m.get("employee_pf") or 0 for s in slips for m in s.get("months") or [])
        prov["epf"] = "salary slips"
    if facts.other_80c is None and old_f16:
        c80 = sum(_via(f, "80C") for f in old_f16)  # gross 80C on an old-regime Form 16 includes PF
        prov["80c"] = "Form 16 Part B (80C, incl. PF)"
    else:
        c80 = (epf or 0) + (facts.other_80c or 0)
        prov["80c"] = "PF" + (" (you said)" if facts.epf_annual is not None else "") + " + investments you told us"
    if epf is None and facts.other_80c is None and not old_f16:
        notes.append("Employee PF not known; 80C taken as 0 for the old-regime comparison.")

    def pick(fact_val, f16_prefix: str, label: str) -> int:
        if fact_val is not None:
            prov[label] = "you said"
            return fact_val
        v = sum(_via(f, f16_prefix) for f in old_f16)
        if v:
            prov[label] = "Form 16 Part B"
        return v

    d80d = pick(facts.health_80d, "80D", "80d")
    nps = pick(facts.nps_80ccd1b, "80CCD(1B)", "80ccd1b")
    home_loan = facts.home_loan_interest
    if home_loan is None:
        home_loan = sum(f.get("home_loan_interest") or 0 for f in old_f16)
        if home_loan:
            prov["home_loan_interest"] = "Form 16 Part B"
    else:
        prov["home_loan_interest"] = "you said"

    # ---- HRA exemption
    hra = 0
    if facts.hra_exemption_annual is not None:
        hra, prov["hra_exemption"] = facts.hra_exemption_annual, "you said"
    elif facts.rent_monthly:
        metro = bool(facts.metro_city)
        if slips:
            for s in slips:
                ms = s.get("months") or []
                if ms and ms[0].get("basic") and ms[0].get("hra"):
                    hra += hra_exemption(ms[0]["basic"], ms[0]["hra"], facts.rent_monthly, metro, len(ms))
            prov["hra_exemption"] = "computed from salary slips and your rent (s.10(13A))"
        elif facts.basic_monthly and facts.hra_monthly:
            hra = hra_exemption(facts.basic_monthly, facts.hra_monthly, facts.rent_monthly, metro)
            prov["hra_exemption"] = "computed from your basic, HRA and rent (s.10(13A))"
        else:
            hra = sum(f.get("hra_exemption") or 0 for f in old_f16)
            prov["hra_exemption"] = "Form 16 Part B" if hra else "not computed (basic/HRA not known)"
            if not hra:
                notes.append("HRA exemption not computed: basic salary and HRA per month are needed.")

    age = age_category(facts.age)
    ttx = min(interest, CAP_80TTB) if age != "below60" else min(savings, CAP_80TTA)
    if ttx:
        prov["80tta_80ttb"] = ("80TTB on all deposit interest" if age != "below60" else "80TTA on savings interest")

    freelance = facts.freelance_receipts or 0
    presumptive = bool(freelance) and facts.business_presumptive is not False
    inputs = {
        "gross_salary": freelance if (freelance and not salary) else salary,
        "other_income": interest,
        "deductions_80c": c80, "deductions_80d": d80d,
        "deductions_80d_parents": facts.health_80d_parents or 0, "parents_senior": bool(facts.parents_senior),
        "nps_80ccd1b": nps, "home_loan_interest": home_loan, "hra_exemption": hra, "other_deductions": ttx,
        "age": age, "tax_year": tax_year,
        "salaried": not (freelance and not salary),
        "income_type": "professional_presumptive" if (presumptive and not salary) else "salary",
        "cash_receipts_over_5pct": bool(facts.cash_receipts_over_5pct),
    }
    if freelance:
        prov["gross_salary"] = "your freelance receipts (presumptive: 50% taxed)" if presumptive else "your receipts"
    tds = {
        "salary_deposited": sum(f.get("part_a_total_tds") or 0 for f in f16s),
        "salary_per_part_b": sum(f.get("tds_part_b") or 0 for f in f16s),
        "interest": sum(c.get("total_tds") or 0 for c in certs),
    }
    tds["credited"] = tds["salary_deposited"] + tds["interest"]
    return {"inputs": inputs, "provenance": prov, "tds": tds, "notes": notes,
            "mixed_salary_and_business": bool(freelance and salary)}


def escalation_reasons(facts: UserFacts, figures: dict | None = None) -> list[str]:
    r = []
    if facts.short_term_capital_gains or facts.other_capital_gains or (facts.ltcg_112a or 0) > 125_000:
        r.append("capital_gains")
    if facts.foreign_assets_or_income:
        r.append("foreign_assets_or_income")
    if facts.company_director or facts.unlisted_shares:
        r.append("director_or_unlisted_shares")
    if facts.fno_trading or facts.losses_to_carry_forward:
        r.append("fno_or_losses")
    if (facts.house_properties or 0) > 2:
        r.append("more_than_two_house_properties")
    if facts.freelance_receipts:
        limit = PRESUMPTIVE_LIMIT_CASH if facts.cash_receipts_over_5pct else PRESUMPTIVE_LIMIT_DIGITAL
        if facts.freelance_receipts > limit:
            r.append("presumptive_limit_exceeded")
        elif facts.business_presumptive is False:
            r.append("business_with_books")
    if figures and figures.get("mixed_salary_and_business"):
        r.append("salary_and_business_income")
    return r


REASON_TEXT = {
    "capital_gains": "capital gains need a separate computation (special rates, holding periods, indexation) that "
                     "Taxot does not do",
    "foreign_assets_or_income": "foreign assets or income need Schedule FA reporting and treaty relief",
    "director_or_unlisted_shares": "company directors and holders of unlisted shares must file ITR-2 with extra "
                                   "disclosures",
    "fno_or_losses": "F&O trading is business income and losses carried forward need ITR-3 and possibly an audit",
    "more_than_two_house_properties": "more than two house properties need house-property computations",
    "presumptive_limit_exceeded": "receipts are above the presumptive-scheme limit, so books of account and "
                                  "possibly a tax audit are needed",
    "business_with_books": "business income on actual profit needs books of account (ITR-3)",
    "salary_and_business_income": "salary and business income together need a combined computation",
}


def itr_inputs(facts: UserFacts, figures: dict, tax_year: str) -> dict:
    """The arguments itr_form_rules should be called with (used to score the income tax agent)."""
    inp = figures["inputs"]
    freelance = facts.freelance_receipts or 0
    presumptive = bool(freelance) and facts.business_presumptive is not False and \
        "presumptive_limit_exceeded" not in escalation_reasons(facts)
    salary = 0 if inp["income_type"] == "professional_presumptive" else inp["gross_salary"]
    business = (freelance // 2) if presumptive else freelance
    return {
        "tax_year": tax_year if tax_year in ("2025-26", "2026-27") else "2025-26",
        "residential_status": facts.residential_status or "resident",
        "total_income": salary + inp["other_income"] + business + (facts.ltcg_112a or 0),
        "has_salary": salary > 0, "house_properties": facts.house_properties or 0,
        "has_business_income": bool(freelance), "business_presumptive": presumptive,
        "fno_trading": bool(facts.fno_trading), "short_term_capital_gains": bool(facts.short_term_capital_gains),
        "ltcg_112a": facts.ltcg_112a or 0, "other_capital_gains": bool(facts.other_capital_gains),
        "foreign_assets_or_income": bool(facts.foreign_assets_or_income),
        "company_director": bool(facts.company_director), "unlisted_shares": bool(facts.unlisted_shares),
        "losses_to_carry_forward": bool(facts.losses_to_carry_forward),
    }


def build_checklist(state: dict) -> dict:
    """Filing-ready checklist from the approved figures, regime, ITR form and document findings."""
    fig, itr, reg = state.get("figures") or {}, state.get("itr") or {}, state.get("regime") or {}
    inp = fig.get("inputs", {})
    findings = ((state.get("documents_report") or {}).get("report") or {}).get("findings", [])
    chosen = reg.get("chosen_regime") or reg.get("recommended_regime")
    totals = {"old": reg.get("old_total"), "new": reg.get("new_total")}
    tax = totals.get(chosen) if chosen in totals else None
    tds = (fig.get("tds") or {}).get("credited", 0)
    items = []
    if itr.get("form"):
        items.append({"item": f"File {itr['form']} for FY {state.get('tax_year')}", "detail":
                      f"Due {itr.get('due_date', 'see portal')}. " + "; ".join(itr.get("reasons", [])[:1])})
    if chosen:
        items.append({"item": f"Choose the {chosen} regime", "detail": f"Tax {format_inr(tax or 0)} vs "
                      f"{format_inr(totals['old' if chosen == 'new' else 'new'] or 0)} in the other regime."})
        if chosen == "old" and inp.get("income_type") == "professional_presumptive":
            items.append({"item": "File Form 10-IEA before the due date", "detail": "Needed to choose the old "
                          "regime with business income."})
    if inp.get("gross_salary"):
        label = "Gross receipts (presumptive, 50% taxed)" if inp.get("income_type") == "professional_presumptive" \
            else "Salary (from Form 16)"
        items.append({"item": f"Report {label}: {format_inr(inp['gross_salary'])}", "detail": ""})
    if inp.get("other_income"):
        items.append({"item": f"Report interest under income from other sources: {format_inr(inp['other_income'])}",
                      "detail": "Include every bank's savings and FD interest, even if TDS was deducted."})
    if chosen == "old":
        for key, label in [("deductions_80c", "80C"), ("deductions_80d", "80D"), ("deductions_80d_parents", "80D (parents)"),
                           ("nps_80ccd1b", "80CCD(1B)"), ("home_loan_interest", "24(b) home-loan interest"),
                           ("hra_exemption", "HRA exemption 10(13A)"), ("other_deductions", "80TTA/80TTB")]:
            if inp.get(key):
                items.append({"item": f"Claim {label}: {format_inr(inp[key])}", "detail": "Keep the proofs."})
    if tds:
        items.append({"item": f"Check TDS credit of {format_inr(tds)} in Form 26AS/AIS", "detail":
                      "Salary TDS (Part A) and TDS on interest must appear against your PAN."})
    if tax is not None:
        bal = tax - tds
        items.append({"item": (f"Pay self-assessment tax of {format_inr(bal)} before filing" if bal > 0 else
                               f"Expected refund: {format_inr(-bal)}" if bal < 0 else "No balance tax due"),
                      "detail": "Interest u/s 234B/234C may apply to tax paid late." if bal > 0 else ""})
    for f in findings:
        if f["code"] in ("injection_detected",):
            continue
        items.append({"item": f"Resolve: {f.get('title') or f['code']}", "detail": f.get("action") or f.get("explanation", "")})
    items.append({"item": "Keep documents for 6+ years", "detail": "Form 16, interest certificates, investment proofs, "
                  "rent receipts."})
    return {"items": items, "tax_payable": tax, "tds_credited": tds,
            "balance": (tax - tds) if tax is not None else None, "regime": chosen, "itr_form": itr.get("form")}


# ------------------------------------------------------------------ tax-saving options (Workflow 3)
CAPS = {"deductions_80c": 150_000, "nps_80ccd1b": 50_000}
OPTION_LABELS = {"deductions_80c": "Invest more under 80C (PPF/ELSS)", "nps_80ccd1b": "Own NPS contribution, 80CCD(1B)",
                 "deductions_80d": "Health insurance for yourself/family, 80D",
                 "deductions_80d_parents": "Health insurance for your parents, 80D"}
FACT_FOR = {"deductions_80c": "extra_80c_possible", "nps_80ccd1b": "extra_nps_possible",
            "deductions_80d": "extra_80d_possible", "deductions_80d_parents": "extra_80d_parents_possible"}


def saving_candidates(inputs: dict, facts: UserFacts) -> list[dict]:
    """Legal options within each cap and within what the user says they can still invest.
    Each option is a what-if for calculate_tax: {"label", "changes", "extra_investment"}."""
    senior = inputs.get("age") in ("60to80", "above80")
    caps = {**CAPS, "deductions_80d": 50_000 if senior else 25_000,
            "deductions_80d_parents": 50_000 if (facts.parents_senior or inputs.get("parents_senior")) else 25_000}
    singles = []
    for field, fact in FACT_FOR.items():
        room = getattr(facts, fact) or 0
        headroom = max(0, caps[field] - (inputs.get(field) or 0))
        extra = min(room, headroom)
        if extra > 0:
            changes = {field: (inputs.get(field) or 0) + extra}
            if field == "deductions_80d_parents" and facts.parents_senior:
                changes["parents_senior"] = True
            singles.append({"label": f"{OPTION_LABELS[field]}: +{format_inr(extra)}", "changes": changes,
                            "extra_investment": extra, "field": field})
    out = list(singles)
    if len(singles) > 1:
        combo = {}
        for s in singles:
            combo.update(s["changes"])
        out.append({"label": "All of the above together", "changes": combo,
                    "extra_investment": sum(s["extra_investment"] for s in singles), "field": "combined"})
    return out
