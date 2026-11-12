"""
itr_form_rules: decides which ITR form an individual files, with reasons. Deterministic.

Rules follow the AY 2026-27 (FY 2025-26) eligibility in the knowledge base
(data/raw/curated/it_itr_forms.md, chunks IT-ITR1..IT-ITR4):

  ITR-1  resident (ordinarily resident), total income <= ₹50 lakh, salary/pension, <= 2 house
         properties, other sources (interest), agricultural income <= ₹5,000, LTCG u/s 112A
         <= ₹1.25 lakh; no business income, no STCG, no other capital gains, not a director,
         no unlisted shares, no foreign assets/income, no losses carried forward.
  ITR-4  same limits, resident, plus business/professional income on a presumptive basis
         (44AD / 44ADA / 44AE); not a partner in a firm, no F&O trading.
  ITR-3  business/professional income that cannot go in ITR-4.
  ITR-2  everything else without business income.

For Tax Year 2026-27 (Income-tax Act, 2025) the new forms are not notified yet (chunk
IT-ITR-FORMS-TY2627); the AY 2026-27 rules are applied and a note says so.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

INCOME_CAP = 50_00_000
LTCG_112A_CAP = 1_25_000
AGRI_CAP = 5_000
MAX_HOUSES = 2

DUE_DATES = {  # AY 2026-27, from the knowledge base
    "ITR-1": "31 July 2026",
    "ITR-2": "31 July 2026",
    "ITR-3": "31 August 2026",
    "ITR-4": "31 August 2026",
}
AUDIT_DUE_DATE = "31 October 2026 (extended by CBDT to 21 November 2026)"
KB_REFS = {"ITR-1": "IT-ITR1", "ITR-2": "IT-ITR2", "ITR-3": "IT-ITR3", "ITR-4": "IT-ITR4"}


class ITRFormArgs(BaseModel):
    tax_year: Literal["2025-26", "2026-27"] = Field("2025-26", description="Financial / tax year of the income.")
    residential_status: Literal["resident", "rnor", "non_resident"] = Field(
        "resident", description="resident = resident and ordinarily resident; rnor = resident but not "
                                "ordinarily resident.")
    total_income: int = Field(..., ge=0, description="Total income in rupees (before deductions).")
    has_salary: bool = Field(True, description="Has salary or pension income.")
    house_properties: int = Field(0, ge=0, le=50, description="Number of house properties owned.")
    has_business_income: bool = Field(False, description="Has income from business or profession "
                                                         "(freelancing, consulting, shop...).")
    business_presumptive: bool = Field(False, description="Business/professional income is declared on a "
                                                          "presumptive basis (44AD/44ADA/44AE).")
    partner_in_firm: bool = False
    fno_trading: bool = Field(False, description="Traded futures & options.")
    tax_audit_required: bool = Field(False, description="Accounts must be audited u/s 44AB.")
    short_term_capital_gains: bool = Field(False, description="Any short-term capital gain (shares, funds, "
                                                              "property...).")
    ltcg_112a: int = Field(0, ge=0, description="Long-term gains on listed equity / equity funds (s.112A), rupees.")
    other_capital_gains: bool = Field(False, description="Other long-term gains, e.g. sale of property, gold, "
                                                         "debt funds.")
    agricultural_income: int = Field(0, ge=0)
    foreign_assets_or_income: bool = False
    company_director: bool = False
    unlisted_shares: bool = Field(False, description="Held unlisted equity shares at any time in the year.")
    losses_to_carry_forward: bool = False


def _common_blockers(a: ITRFormArgs) -> list[str]:
    """Reasons that rule out both ITR-1 and ITR-4."""
    r = []
    if a.residential_status != "resident":
        r.append("not a resident and ordinarily resident")
    if a.total_income > INCOME_CAP:
        r.append(f"total income above ₹50 lakh (₹{a.total_income:,})")
    if a.short_term_capital_gains:
        r.append("has short-term capital gains")
    if a.ltcg_112a > LTCG_112A_CAP:
        r.append(f"LTCG u/s 112A above ₹1.25 lakh (₹{a.ltcg_112a:,})")
    if a.other_capital_gains:
        r.append("has capital gains other than LTCG u/s 112A")
    if a.house_properties > MAX_HOUSES:
        r.append(f"more than two house properties ({a.house_properties})")
    if a.agricultural_income > AGRI_CAP:
        r.append(f"agricultural income above ₹5,000 (₹{a.agricultural_income:,})")
    if a.foreign_assets_or_income:
        r.append("has foreign assets or foreign income")
    if a.company_director:
        r.append("is a company director")
    if a.unlisted_shares:
        r.append("held unlisted equity shares")
    if a.losses_to_carry_forward:
        r.append("has losses to carry forward")
    return r


def itr_form_rules(args: ITRFormArgs, ctx=None) -> dict:
    a = args
    business = a.has_business_income or a.partner_in_firm or a.fno_trading
    common = _common_blockers(a)
    why_not: dict[str, list[str]] = {}

    itr1_block = list(common) + (["has business or professional income"] if business else [])
    why_not["ITR-1"] = itr1_block

    itr4_block = list(common)
    if not business:
        itr4_block.append("no business or professional income")
    else:
        if not a.business_presumptive:
            itr4_block.append("business income is not on a presumptive basis (44AD/44ADA/44AE)")
        if a.partner_in_firm:
            itr4_block.append("is a partner in a firm")
        if a.fno_trading:
            itr4_block.append("trades in futures & options")
    why_not["ITR-4"] = itr4_block

    if not itr1_block:
        form = "ITR-1"
        reasons = ["resident with income up to ₹50 lakh from salary/pension, house property (≤2) and other "
                   "sources, with no business income or disqualifying capital gains"]
    elif business:
        if not itr4_block:
            form = "ITR-4"
            reasons = ["business/professional income declared on a presumptive basis, within ITR-4 limits"]
        else:
            form = "ITR-3"
            reasons = ["has business/professional income but cannot use ITR-4: " + "; ".join(itr4_block)]
    else:
        form = "ITR-2"
        reasons = ["no business income but cannot use ITR-1: " + "; ".join(itr1_block)]

    due =AUDIT_DUE_DATE if (form == "ITR-3" and a.tax_audit_required) else DUE_DATES[form]
    out = {"form": form, "reasons": reasons, "why_not": {k: v for k, v in why_not.items() if v and k != form},
           "due_date": due, "kb_refs": [KB_REFS[form]] + [KB_REFS[k] for k in why_not if k != form and why_not[k]],
           "tax_year": a.tax_year}
    if a.tax_year == "2026-27":
        out["note"] = ("Tax Year 2026-27 return forms under the Income-tax Act, 2025 are not notified yet; "
                       "this uses the AY 2026-27 rules, the best guide until then (KB IT-ITR-FORMS-TY2627).")
        out["kb_refs"].append("IT-ITR-FORMS-TY2627")
        out["due_date"] = "to be notified (returns for Tax Year 2026-27 are filed in 2027)"
    if form == "ITR-4":
        out["reminder"] = "To choose the old regime with business income, Form 10-IEA must be filed by the due date."
    return out
