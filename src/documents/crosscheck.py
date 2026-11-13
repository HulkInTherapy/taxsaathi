"""
Deterministic cross-checks between a taxpayer's documents.

Input: the typed fields extracted from each document. Output: findings with a stable `code`,
the figures behind them and a plain-language message. No LLM is involved: whether interest is
missing from Form 16 or a PAN differs is a comparison of numbers and strings, so it is done in
Python and can be tested exactly. The document agent explains the findings and adds the law.

Codes (same as the synthetic ground truth):
  interest_not_in_form16, slips_total_mismatch, form16_tds_inconsistent, deduction_over_cap,
  pan_mismatch, multiple_employers, injection_detected
"""
from __future__ import annotations

import re

from src.calculator.tax import format_inr

CAPS = {"80C": 150_000, "80CCD(1B)": 50_000, "80TTA": 10_000}
TOLERANCE = 1  # rupees


def _norm_name(s: str | None) -> str:
    s = re.sub(r"\b(pvt|private|ltd|limited|llp|inc|co)\b\.?", "", (s or "").lower())
    return re.sub(r"[^a-z0-9]", "", s)


def _section(label: str) -> str:
    t = label.upper().replace(" ", "")
    if t.startswith("80CCD(1B)"):
        return "80CCD(1B)"
    if t.startswith("80TTA") and "80TTB" not in t:
        return "80TTA"
    if t.startswith("80C") and not t.startswith("80CC"):
        return "80C"
    return t


def cross_check(docs: list[dict], senior: bool | None = None) -> dict:
    """
    docs: [{"document_id", "type", "fields", "injections": [...], "filename"}] (fields may be None)
    Returns {"findings": [...], "totals": {...}, "documents": [...]}.
    """
    form16 = [d for d in docs if d["type"] == "form16" and d.get("fields")]
    certs = [d for d in docs if d["type"] == "interest_certificate" and d.get("fields")]
    slips = [d for d in docs if d["type"] == "salary_slip" and d.get("fields")]
    findings: list[dict] = []

    # ---- interest that Form 16 does not include
    total_interest = sum(c["fields"].get("total_interest") or sum(a["interest"] for a in c["fields"]["accounts"])
                         for c in certs)
    reported = sum(f["fields"].get("other_income_reported") or 0 for f in form16)
    if form16 and total_interest > reported + TOLERANCE:
        missing = total_interest - reported
        findings.append({
            "code": "interest_not_in_form16", "severity": "high", "amount": missing,
            "banks": [c["fields"].get("bank_name") for c in certs],
            "message": f"Your interest certificates show {format_inr(total_interest)} of interest, but your Form 16 "
                       f"includes {format_inr(reported)} of other income. {format_inr(missing)} is not in Form 16 "
                       f"and must be declared in your return as income from other sources."})

    # ---- salary slips vs Form 16, per employer
    for s in slips:
        months = s["fields"].get("months") or []
        slips_total = sum(m.get("gross_earnings") or 0 for m in months)
        match = next((f for f in form16 if _norm_name(f["fields"].get("employer_name"))
                      == _norm_name(s["fields"].get("employer_name"))), None)
        if match is None and len(form16) == 1:
            match = form16[0]
        if match is None or not months:
            continue
        f16_gross = match["fields"].get("gross_salary") or 0
        if abs(f16_gross - slips_total) > TOLERANCE:
            findings.append({
                "code": "slips_total_mismatch", "severity": "medium", "employer": match["fields"].get("employer_name"),
                "form16_gross": f16_gross, "slips_total": slips_total, "months_in_slips": len(months),
                "delta": f16_gross - slips_total,
                "message": f"Form 16 from {match['fields'].get('employer_name')} shows gross salary "
                           f"{format_inr(f16_gross)}, but the {len(months)} salary slips add up to "
                           f"{format_inr(slips_total)} (difference {format_inr(abs(f16_gross - slips_total))}). "
                           "Check for a bonus, arrears or a missing slip before you file."})

    # ---- Form 16 Part A (deposited) vs Part B (computed)
    for f in form16:
        a, b = f["fields"].get("part_a_total_tds"), f["fields"].get("tds_part_b")
        if a is not None and b is not None and abs(a - b) > TOLERANCE:
            findings.append({
                "code": "form16_tds_inconsistent", "severity": "high", "employer": f["fields"].get("employer_name"),
                "part_a_total": a, "part_b_tds": b, "delta": b - a,
                "message": f"Form 16 from {f['fields'].get('employer_name')}: Part B says {format_inr(b)} of tax was "
                           f"deducted, but Part A shows only {format_inr(a)} deposited. Only deposited TDS appears in "
                           "Form 26AS and is credited to you; ask the employer to deposit or correct the difference."})

    # ---- deductions above their legal caps
    for f in form16:
        for row in f["fields"].get("chapter_via") or []:
            sec = _section(row.get("section", ""))
            cap = CAPS.get(sec)
            got = row.get("deductible_amount") or 0
            if cap and got > cap + TOLERANCE:
                findings.append({
                    "code": "deduction_over_cap", "severity": "high", "employer": f["fields"].get("employer_name"),
                    "section": sec, "claimed": got, "cap": cap,
                    "message": f"Form 16 from {f['fields'].get('employer_name')} allows {format_inr(got)} under "
                               f"section {sec}, above the {format_inr(cap)} limit. Your return can only claim "
                               f"{format_inr(cap)}, so tax will be higher than the TDS deducted."})

    # ---- PAN consistency
    pans = {}
    for d in form16:
        pans.setdefault(d["fields"].get("employee_pan"), []).append(d)
    for d in certs:
        pans.setdefault(d["fields"].get("customer_pan"), []).append(d)
    for d in slips:
        pans.setdefault(d["fields"].get("employee_pan"), []).append(d)
    pans.pop(None, None)
    if len(pans) > 1:
        main = max(pans, key=lambda p: (any(x["type"] == "form16" for x in pans[p]), len(pans[p])))
        for pan, ds in pans.items():
            if pan == main:
                continue
            for d in ds:
                findings.append({
                    "code": "pan_mismatch", "severity": "high", "document": d.get("filename") or d["document_id"],
                    "expected_pan": main, "document_pan": pan,
                    "message": f"The PAN on {d.get('filename') or d['document_id']} ({pan}) differs from the PAN on "
                               f"your other documents ({main}). TDS reported under the wrong PAN will not be "
                               "credited to you; ask the issuer to correct it."})

    # ---- more than one employer
    employers = {(f["fields"].get("employer_tan") or _norm_name(f["fields"].get("employer_name"))): f for f in form16}
    if len(employers) > 1:
        std = [f["fields"].get("standard_deduction") or 0 for f in employers.values()]
        tds = sum(f["fields"].get("tds_part_b") or 0 for f in employers.values())
        findings.append({
            "code": "multiple_employers", "severity": "medium",
            "employers": [f["fields"].get("employer_name") for f in employers.values()],
            "standard_deduction_claimed": sum(std), "standard_deduction_allowed": max(std) if std else 0,
            "salary_tds_total": tds,
            "message": f"You have Form 16s from {len(employers)} employers. Each one gave you a standard deduction "
                       f"(total {format_inr(sum(std))}), but only one is allowed ({format_inr(max(std) if std else 0)}). "
                       "Combine both salaries in your return; the total tax may be more than the TDS deducted."})

    # ---- instructions hidden in documents
    for d in docs:
        if d.get("injections"):
            where = sorted({i["where"] for i in d["injections"]})
            findings.append({
                "code": "injection_detected", "severity": "high", "document": d.get("filename") or d["document_id"],
                "where": where,
                "message": f"{d.get('filename') or d['document_id']} contains text that tries to instruct an AI "
                           f"({', '.join(where)}). It was ignored. Make sure this document really comes from its issuer."})

    totals = {
        "salary": sum(f["fields"].get("gross_salary") or 0 for f in form16),
        "interest": total_interest,
        "interest_reported_in_form16": reported,
        "tds_salary_part_a": sum(f["fields"].get("part_a_total_tds") or 0 for f in form16),
        "tds_salary_part_b": sum(f["fields"].get("tds_part_b") or 0 for f in form16),
        "tds_interest": sum(c["fields"].get("total_tds") or 0 for c in certs),
        "savings_interest": sum(a["interest"] for c in certs for a in c["fields"]["accounts"]
                                if a["account_type"] == "savings"),
        "employers": len(employers),
        "regimes_in_form16": sorted({"new" if f["fields"].get("new_regime") else "old" for f in form16
                                     if f["fields"].get("new_regime") is not None}),
    }
    unreadable = [d.get("filename") or d["document_id"] for d in docs if not d.get("fields")]
    return {"findings": findings, "totals": totals, "unreadable_documents": unreadable}
