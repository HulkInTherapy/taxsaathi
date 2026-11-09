"""
Deterministic income-tax calculator (old vs new regime) for individuals.

The LLM never does arithmetic: all numbers come from here. Rates live in the RULES table
below (one entry per tax year), so a new budget only means editing data, not code. Steps per
regime: gross salary - standard deduction - allowed deductions = taxable income -> slab tax
-> section 87A rebate (with marginal relief) -> surcharge (with marginal relief) -> 4% cess.
Covers tax years 2024-25, 2025-26 (Income-tax Act, 1961) and 2026-27 (Income-tax Act, 2025).
Two income types: "salary" (default) and "professional_presumptive" (freelancers/professionals:
50% of gross receipts is deemed profit under section 58 of the 2025 Act / 44ADA of the 1961 Act).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

INF = None  # "no upper limit" in slab tables

# ------------------------------------------------------------------ rate tables (data!)
OLD_SLABS = {  # old regime: basic exemption depends on age, then 5% / 20% / 30%
    "below60": [(0, 250_000, 0), (250_000, 500_000, 5), (500_000, 1_000_000, 20), (1_000_000, INF, 30)],
    "60to80": [(0, 300_000, 0), (300_000, 500_000, 5), (500_000, 1_000_000, 20), (1_000_000, INF, 30)],
    "above80": [(0, 500_000, 0), (500_000, 1_000_000, 20), (1_000_000, INF, 30)],
}
OLD_REGIME = {"slabs_by_age": OLD_SLABS, "std_deduction": 50_000,
              "rebate_limit": 500_000, "rebate_max": 12_500, "rebate_marginal_relief": False,
              "surcharge_cap": 37}
NEW_2024 = {"slabs": [(0, 300_000, 0), (300_000, 700_000, 5), (700_000, 1_000_000, 10),
                      (1_000_000, 1_200_000, 15), (1_200_000, 1_500_000, 20), (1_500_000, INF, 30)],
            "std_deduction": 75_000, "rebate_limit": 700_000, "rebate_max": 25_000,
            "rebate_marginal_relief": True, "surcharge_cap": 25}
NEW_2025 = {"slabs": [(0, 400_000, 0), (400_000, 800_000, 5), (800_000, 1_200_000, 10),
                      (1_200_000, 1_600_000, 15), (1_600_000, 2_000_000, 20),
                      (2_000_000, 2_400_000, 25), (2_400_000, INF, 30)],
            "std_deduction": 75_000, "rebate_limit": 1_200_000, "rebate_max": 60_000,
            "rebate_marginal_relief": True, "surcharge_cap": 25}

RULES = {
    "2024-25": {"label": "FY 2024-25 (AY 2025-26)", "new": NEW_2024, "old": OLD_REGIME,
                "law": "Income-tax Act, 1961 s.115BAC / s.87A"},
    "2025-26": {"label": "FY 2025-26 (AY 2026-27)", "new": NEW_2025, "old": OLD_REGIME,
                "law": "Income-tax Act, 1961 s.115BAC / s.87A"},
    "2026-27": {"label": "Tax Year 2026-27", "new": NEW_2025, "old": OLD_REGIME,
                "law": "Income-tax Act, 2025 s.202 / s.156"},
}
# Surcharge: (income above, rate %). Applied to income tax after rebate.
SURCHARGE = [(5_00_00_000, 37), (2_00_00_000, 25), (1_00_00_000, 15), (50_00_000, 10)]
CESS_RATE = 4  # health & education cess, % of (tax + surcharge)
# Old-regime deduction caps
CAP_80C, CAP_80D, CAP_80D_SENIOR, CAP_80CCD1B, CAP_HOME_LOAN = 150_000, 25_000, 50_000, 50_000, 200_000
AGES = ("below60", "60to80", "above80")

# Presumptive taxation for professionals: section 58 of the Income-tax Act, 2025 (Tax Year
# 2026-27 onwards; KB chunk IT-FL-SEC58-TY2627) = section 44ADA of the 1961 Act (KB chunk
# IT-FL-44ADA). 50% of gross receipts is deemed profit, available if receipts are up to ₹75 lakh
# when cash receipts are within 5% of the total (bank / wire transfers from foreign clients are
# non-cash), otherwise up to ₹50 lakh. No standard deduction (it is not salary).
INCOME_TYPES = ("salary", "professional_presumptive")
PRESUMPTIVE_RATE = 50                      # % of gross receipts deemed to be profit
PRESUMPTIVE_LIMIT_DIGITAL = 75_00_000      # cash receipts <= 5%
PRESUMPTIVE_LIMIT_CASH = 50_00_000         # cash receipts > 5%


def presumptive_limit(cash_over_5pct: bool = False) -> int:
    return PRESUMPTIVE_LIMIT_CASH if cash_over_5pct else PRESUMPTIVE_LIMIT_DIGITAL


def presumptive_section(tax_year: str) -> str:
    return "section 58 of the Income-tax Act, 2025" if tax_year >= "2026-27" else "section 44ADA of the Income-tax Act, 1961"


def rebate_section(tax_year: str) -> str:
    return "section 156 (old section 87A)" if tax_year >= "2026-27" else "section 87A"


class PresumptiveLimitExceeded(ValueError):
    """Receipts above the presumptive limit: we do not compute, the user needs books / a CA."""


def rnd(x: float) -> int:
    """Round to the nearest rupee (half rounds up, unlike Python's round())."""
    return int(math.floor(x + 0.5))


def format_inr(n: int | float) -> str:
    """12,25,000-style Indian grouping with a ₹ sign."""
    n = rnd(n)
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return f"{sign}₹{s}"


@dataclass
class TaxInputs:
    gross_salary: int = 0
    deductions_80c: int = 0
    deductions_80d: int = 0
    deductions_80d_parents: int = 0   # 80D for parents' health insurance: separate ₹25k cap (₹50k if parents are 60+)
    parents_senior: bool = False
    hra_exemption: int = 0
    home_loan_interest: int = 0
    nps_80ccd1b: int = 0
    other_deductions: int = 0
    employer_nps: int = 0
    age: str = "below60"
    tax_year: str = "2025-26"
    salaried: bool = True
    income_type: str = "salary"            # "salary" | "professional_presumptive" (gross_salary = gross receipts)
    cash_receipts_over_5pct: bool = False  # professionals only: decides the ₹75 lakh vs ₹50 lakh limit

    def validate(self) -> None:
        if self.income_type not in INCOME_TYPES:
            raise ValueError(f"income_type must be one of {INCOME_TYPES}")
        if self.income_type == "professional_presumptive":
            self.salaried = False
            limit = presumptive_limit(self.cash_receipts_over_5pct)
            if self.gross_salary > limit:
                raise PresumptiveLimitExceeded(
                    f"Gross receipts of {format_inr(self.gross_salary)} are above the {format_inr(limit)} limit of the "
                    f"presumptive scheme ({presumptive_section(self.tax_year)}). Above this limit you need regular books "
                    f"of account and possibly a tax audit, and tax depends on actual expenses — please consult a CA.")
        if self.tax_year not in RULES:
            raise ValueError(f"tax_year must be one of {list(RULES)}")
        if self.age not in AGES:
            raise ValueError(f"age must be one of {AGES}")
        for k, v in asdict(self).items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v < 0:
                raise ValueError(f"{k} cannot be negative")


def slab_tax(taxable: int, slabs: list) -> tuple[int, list[dict]]:
    """Tax on `taxable` by slabs. Returns (total, breakdown rows touched)."""
    total, rows = 0, []
    for lo, hi, rate in slabs:
        if taxable <= lo:
            break
        portion = (min(taxable, hi) if hi is not None else taxable) - lo
        tax = rnd(portion * rate / 100)
        total += tax
        rows.append({"from": lo, "to": hi, "rate": rate, "tax": tax})
    return total, rows


def _surcharge_rate(income: int, cap: int) -> int:
    for limit, rate in SURCHARGE:
        if income > limit:
            return min(rate, cap)
    return 0


def surcharge_with_relief(taxable: int, tax: int, slabs: list, cap: int) -> tuple[int, bool]:
    """Surcharge on `tax`, with marginal relief: (tax + surcharge) may not exceed the tax +
    surcharge payable at the threshold just crossed + the income above that threshold."""
    rate = _surcharge_rate(taxable, cap)
    if rate == 0:
        return 0, False
    surcharge = tax * rate / 100
    # The threshold that triggered the current rate (skip thresholds where the capped rate is unchanged)
    for limit, _ in SURCHARGE:
        if taxable > limit and _surcharge_rate(limit, cap) < rate:
            tax_at_limit, _ = slab_tax(limit, slabs)
            max_total = tax_at_limit * (1 + _surcharge_rate(limit, cap) / 100) + (taxable - limit)
            if tax + surcharge > max_total:
                return rnd(max(0.0, max_total - tax)), True
            break
    return rnd(surcharge), False


def compute_regime(inp: TaxInputs, regime: str) -> dict:
    """Full computation for one regime ('old' or 'new')."""
    year = RULES[inp.tax_year]
    rules = year[regime]
    notes: list[str] = []
    presumptive = inp.income_type == "professional_presumptive"
    # Professionals on the presumptive scheme: income = 50% of gross receipts, no standard deduction.
    income = rnd(inp.gross_salary * PRESUMPTIVE_RATE / 100) if presumptive else inp.gross_salary
    std = rules["std_deduction"] if inp.salaried and not presumptive else 0
    std = min(std, income)

    if regime == "new":
        # New regime: only standard deduction + employer NPS (80CCD(2)) are allowed.
        deductions = {"employer_nps_80ccd2": inp.employer_nps}
        ignored = inp.deductions_80c + inp.deductions_80d + inp.deductions_80d_parents + inp.hra_exemption + inp.home_loan_interest + inp.nps_80ccd1b + inp.other_deductions
        if ignored:
            notes.append(f"New regime: 80C/80D/HRA/home-loan/80CCD(1B)/other deductions ({format_inr(ignored)}) are not allowed.")
        slabs = rules["slabs"]
    else:
        cap_80d = CAP_80D_SENIOR if inp.age in ("60to80", "above80") else CAP_80D
        cap_80d_parents = CAP_80D_SENIOR if inp.parents_senior else CAP_80D
        deductions = {
            "80c": min(inp.deductions_80c, CAP_80C),
            "80d": min(inp.deductions_80d, cap_80d),
            "80d_parents": min(inp.deductions_80d_parents, cap_80d_parents),
            "80ccd1b": min(inp.nps_80ccd1b, CAP_80CCD1B),
            "home_loan_interest": min(inp.home_loan_interest, CAP_HOME_LOAN),
            "hra_exemption": inp.hra_exemption,
            "other": inp.other_deductions,
            "employer_nps_80ccd2": inp.employer_nps,
        }
        for key, entered, cap, name in [("80c", inp.deductions_80c, CAP_80C, "80C"),
                                        ("80d", inp.deductions_80d, cap_80d, "80D"),
                                        ("80d_parents", inp.deductions_80d_parents, cap_80d_parents, "80D (parents)"),
                                        ("80ccd1b", inp.nps_80ccd1b, CAP_80CCD1B, "80CCD(1B)"),
                                        ("home_loan_interest", inp.home_loan_interest, CAP_HOME_LOAN, "Home-loan interest")]:
            if entered > cap:
                notes.append(f"Old regime: {name} capped at {format_inr(cap)} (you entered {format_inr(entered)}).")
        slabs = rules["slabs_by_age"][inp.age]

    total_ded = sum(deductions.values())
    taxable = max(0, income - std - total_ded)
    tax, rows = slab_tax(taxable, slabs)

    # Section 87A rebate (s.156 in the 2025 Act)
    rebate = 0
    if taxable <= rules["rebate_limit"]:
        rebate = min(tax, rules["rebate_max"])
        if rebate:
            notes.append(f"{regime.title()} regime: rebate u/s 87A of {format_inr(rebate)} (taxable income up to {format_inr(rules['rebate_limit'])}).")
    elif rules["rebate_marginal_relief"]:
        excess = taxable - rules["rebate_limit"]
        if tax > excess:  # tax may not exceed the income above the rebate limit
            rebate = tax - excess
            notes.append(f"New regime: marginal relief of {format_inr(rebate)} — tax limited to the income above {format_inr(rules['rebate_limit'])} ({format_inr(excess)}).")
    tax_after_rebate = tax - rebate

    surcharge, relief = surcharge_with_relief(taxable, tax_after_rebate, slabs, rules["surcharge_cap"])
    if surcharge:
        notes.append(f"{regime.title()} regime: surcharge {format_inr(surcharge)}" + (" (after marginal relief)." if relief else "."))
    cess = rnd((tax_after_rebate + surcharge) * CESS_RATE / 100)
    total = tax_after_rebate + surcharge + cess
    return {"gross": inp.gross_salary, "presumptive_income": income if presumptive else None,
            "std_deduction": std, "deductions": total_ded,
            "deduction_breakdown": deductions, "taxable": taxable, "slab_tax": tax,
            "rebate": rebate, "surcharge": surcharge, "cess": cess, "total": total,
            "slabs": rows, "notes": notes}


def calculate(inputs: TaxInputs | dict) -> dict:
    """Compare both regimes. Output shape = SPEC /calculate response."""
    if isinstance(inputs, dict):
        known = {k: v for k, v in inputs.items() if k in TaxInputs.__dataclass_fields__ and v is not None}
        inputs = TaxInputs(**known)
    inputs.validate()
    old, new = compute_regime(inputs, "old"), compute_regime(inputs, "new")
    if new["total"] < old["total"]:
        better = "new"
    elif old["total"] < new["total"]:
        better = "old"
    else:
        better = "same"
    year = RULES[inputs.tax_year]
    notes = old.pop("notes") + new.pop("notes")
    presumptive = inputs.income_type == "professional_presumptive"
    if presumptive:
        notes.append(f"Presumptive scheme ({presumptive_section(inputs.tax_year)}): {PRESUMPTIVE_RATE}% of gross receipts "
                     f"{format_inr(inputs.gross_salary)} = {format_inr(new['presumptive_income'])} taxed as profit; "
                     f"no standard deduction. Limit {format_inr(presumptive_limit(inputs.cash_receipts_over_5pct))} "
                     f"({'cash receipts above 5%' if inputs.cash_receipts_over_5pct else 'cash receipts within 5%'}).")
        notes.append("Assumes you are resident in India (only residents get the rebate).")
    elif not inputs.salaried:
        notes.append("Not salaried: no standard deduction applied.")
    if inputs.employer_nps:
        notes.append("Employer NPS (80CCD(2)) assumed within the allowed % of salary.")
    notes.append(f"Rates for {year['label']}; health & education cess {CESS_RATE}% included.")
    law = year["law"] + ((" / s.58" if inputs.tax_year >= "2026-27" else " / s.44ADA") if presumptive else "")
    result = {"old": old, "new": new, "better": better, "saving": abs(old["total"] - new["total"]),
              "law": law, "tax_year": inputs.tax_year, "income_type": inputs.income_type,
              "inputs": asdict(inputs), "notes": notes}
    result["headline"] = headline(result)
    return result


def headline(result: dict) -> str:
    """Short verdict the UI shows above the numbers (the details live in notes/explanation)."""
    old, new = result["old"], result["new"]
    if old["total"] == 0 and new["total"] == 0:
        return "No tax in either regime."
    if new["total"] == 0:
        return "No tax under the new regime."
    if old["total"] == 0:
        return "No tax under the old regime."
    if result["better"] == "same":
        return f"Both regimes cost {format_inr(new['total'])}."
    return f"The {result['better']} regime saves you {format_inr(result['saving'])}."


def explanation(result: dict) -> list[str]:
    """Short plain-English explanation of a result (deterministic; used when the LLM adds nothing)."""
    new, old, ty = result["new"], result["old"], result["tax_year"]
    rules = RULES[ty]["new"]
    out = []
    if result.get("income_type") == "professional_presumptive":
        out.append(f"As a freelancer/professional under the presumptive scheme ({presumptive_section(ty)}), only half of "
                   f"your {format_inr(new['gross'])} gross receipts — {format_inr(new['presumptive_income'])} — is treated "
                   f"as income, and there is no standard deduction.")
    elif new["std_deduction"]:
        out.append(f"From your {format_inr(new['gross'])} salary, the new regime deducts the {format_inr(new['std_deduction'])} "
                   f"standard deduction, leaving {format_inr(new['taxable'])} taxable.")
    else:
        out.append(f"Your taxable income under the new regime is {format_inr(new['taxable'])}.")
    if new["total"] == 0 and new["rebate"]:
        out.append(f"That is within {format_inr(rules['rebate_limit'])}, so the rebate under {rebate_section(ty)} cancels the whole "
                   f"{format_inr(new['slab_tax'])} slab tax: no tax under the new regime.")
    elif new["total"] == 0:
        out.append(f"That is below the {format_inr(rules['slabs'][0][1])} basic exemption, so there is no tax under the new regime.")
    else:
        extra = []
        if new["rebate"]:
            extra.append(f"minus {format_inr(new['rebate'])} marginal relief")
        if new["surcharge"]:
            extra.append(f"plus {format_inr(new['surcharge'])} surcharge")
        out.append(f"New-regime slab tax on {format_inr(new['taxable'])} is {format_inr(new['slab_tax'])}"
                   + (" " + ", ".join(extra) if extra else "") + f", plus 4% cess = {format_inr(new['total'])}.")
    if old["total"] == 0:
        out.append("The old regime also gives zero tax." if new["total"] == 0 else "The old regime gives zero tax.")
    else:
        out.append(f"Under the old regime (taxable {format_inr(old['taxable'])}) the total is {format_inr(old['total'])}.")
    if result["better"] != "same":
        out.append(f"So the {result['better']} regime is cheaper by {format_inr(result['saving'])}.")
    elif new["total"]:
        out.append("Both regimes cost the same.")
    return out


def summary_text(result: dict) -> str:
    """Plain-English fact block used in the [CALC] prompt and extractive answers."""
    lines = [f"Tax year {result['tax_year']} ({result['law']})."]
    for regime in ("new", "old"):
        r = result[regime]
        if r.get("presumptive_income") is not None:
            parts = [f"{regime.title()} regime: gross receipts {format_inr(r['gross'])}",
                     f"presumptive income (50%) {format_inr(r['presumptive_income'])}"]
        else:
            parts = [f"{regime.title()} regime: gross {format_inr(r['gross'])}",
                     f"standard deduction {format_inr(r['std_deduction'])}"]
        if r["deductions"]:
            parts.append(f"deductions {format_inr(r['deductions'])}")
        parts.append(f"taxable income {format_inr(r['taxable'])}")
        parts.append(f"slab tax {format_inr(r['slab_tax'])}")
        if r["rebate"]:
            parts.append(f"rebate/relief {format_inr(r['rebate'])}")
        if r["surcharge"]:
            parts.append(f"surcharge {format_inr(r['surcharge'])}")
        parts.append(f"cess {format_inr(r['cess'])}")
        parts.append(f"total tax {format_inr(r['total'])}")
        lines.append(", ".join(parts) + ".")
    if result["better"] == "same":
        lines.append("Both regimes give the same tax.")
    else:
        lines.append(f"The {result['better']} regime is better, saving {format_inr(result['saving'])}.")
    return "\n".join(lines)
