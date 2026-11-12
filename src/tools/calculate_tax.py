"""
calculate_tax: deterministic old-vs-new regime comparison, plus what-if scenarios.

Wraps src/calculator/tax.py. The LLM never does arithmetic; it only fills in the inputs.
`what_if` runs extra scenarios that change some inputs (e.g. "+₹50,000 in NPS 80CCD(1B)") and
reports each one's best tax and the saving against the base case. The tax-saving optimiser
(Phase 6) builds on this.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.calculator.tax import PresumptiveLimitExceeded, calculate

TaxYear = Literal["2024-25", "2025-26", "2026-27"]


class TaxInputsArgs(BaseModel):
    gross_salary: int = Field(..., ge=0, description="Annual gross salary in rupees (gross receipts for "
                                                      "presumptive professionals).")
    other_income: int = Field(0, ge=0, description="Other taxable income in rupees, e.g. bank/FD interest. "
                                                   "Added to income in both regimes.")
    deductions_80c: int = Field(0, ge=0, description="80C investments (PPF, ELSS, EPF, LIC, tuition...).")
    deductions_80d: int = Field(0, ge=0, description="80D health insurance premium for self/family.")
    deductions_80d_parents: int = Field(0, ge=0, description="80D health insurance premium for parents.")
    parents_senior: bool = Field(False, description="Parents are 60 or older.")
    hra_exemption: int = Field(0, ge=0, description="HRA exemption already computed, in rupees.")
    home_loan_interest: int = Field(0, ge=0, description="Interest on home loan for a self-occupied house.")
    nps_80ccd1b: int = Field(0, ge=0, description="Own extra NPS contribution under 80CCD(1B).")
    employer_nps: int = Field(0, ge=0, description="Employer NPS contribution, 80CCD(2).")
    other_deductions: int = Field(0, ge=0, description="Other old-regime deductions, e.g. 80TTA/80TTB, 80G.")
    age: Literal["below60", "60to80", "above80"] = "below60"
    tax_year: TaxYear = "2025-26"
    salaried: bool = True
    income_type: Literal["salary", "professional_presumptive"] = "salary"
    cash_receipts_over_5pct: bool = False


class WhatIf(BaseModel):
    label: str = Field(..., description="Short name, e.g. 'Max out 80C'.")
    changes: dict[str, int | bool | str] = Field(..., description="Input fields to override, e.g. "
                                                                  "{'nps_80ccd1b': 50000}.")


class CalculateTaxArgs(TaxInputsArgs):
    what_if: Optional[list[WhatIf]] = Field(None, max_length=12,
                                            description="Optional scenarios to compare against the base case.")


def _to_calc_inputs(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "what_if"}


def _summary(res: dict) -> dict:
    def regime(r):
        return {"taxable_income": r["taxable"], "deductions": r["deductions"],
                "standard_deduction": r["std_deduction"], "rebate": r["rebate"],
                "surcharge": r["surcharge"], "cess": r["cess"], "total_tax": r["total"]}
    return {"old_regime": regime(res["old"]), "new_regime": regime(res["new"]),
            "better_regime": res["better"], "saving_with_better_regime": res["saving"],
            "headline": res["headline"], "law": res["law"], "notes": res["notes"]}


def calculate_tax(args: CalculateTaxArgs, ctx=None) -> dict:
    base_in = _to_calc_inputs(args.model_dump())
    try:
        base = calculate(base_in)
    except PresumptiveLimitExceeded as e:
        return {"escalate": True, "reason": str(e)}
    out = _summary(base)
    if args.what_if:
        base_best = min(base["old"]["total"], base["new"]["total"])
        rows = []
        for w in args.what_if:
            unknown = set(w.changes) - set(TaxInputsArgs.model_fields)
            if unknown:
                rows.append({"label": w.label, "error": f"unknown fields: {sorted(unknown)}"})
                continue
            merged = TaxInputsArgs(**{**args.model_dump(exclude={"what_if"}), **w.changes})
            try:
                r = calculate(_to_calc_inputs(merged.model_dump()))
            except (PresumptiveLimitExceeded, ValueError) as e:
                rows.append({"label": w.label, "error": str(e)})
                continue
            best = min(r["old"]["total"], r["new"]["total"])
            rows.append({"label": w.label, "changes": w.changes, "best_regime": r["better"],
                         "old_total": r["old"]["total"], "new_total": r["new"]["total"],
                         "best_total": best, "saving_vs_base": base_best - best})
        rows.sort(key=lambda x: -x.get("saving_vs_base", -10**12))
        out["what_if"] = rows
    return out
