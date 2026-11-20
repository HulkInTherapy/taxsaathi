"""
Verifier evaluation: drafts with one planted unsupported claim, and clean drafts.

    python -m experiments.run_verifier_eval [--workers 3]

Metrics:
  catch_rate            planted claim judged unsupported/contradicted in round 1   (plan target >= 90%)
  removed_rate          planted claim no longer in the final text (revised or dropped)
  clean_false_alarm     share of clean drafts where any claim was flagged
  clean_text_changed    share of clean drafts whose text the verifier changed
Writes experiments/agent_results/verifier.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from src import config

OUT = config.ROOT / "experiments" / "agent_results" / "verifier.json"

# (draft with one false sentence, regex that is present only while the false claim survives)
PLANTED = [
    ("Your PPF and ELSS investments count under section 80C. Section 80C allows a deduction of up to ₹2,50,000 "
     "in the old regime. These deductions are not available in the new regime.", r"2,50,000"),
    ("Interest from savings accounts and fixed deposits is income from other sources. FD interest becomes "
     "tax-free once the bank has deducted TDS. You should report it in your return.", r"becomes tax-free"),
    ("You have salary and an FD. ITR-1 can also be used by people who have short-term capital gains from shares. "
     "The due date for ITR-1 for FY 2025-26 is 31 July 2026.", r"can also be used by people who have short-term"),
    ("Salaried taxpayers get a standard deduction. In the new regime for FY 2025-26 the standard deduction is "
     "₹50,000. The old regime also has a standard deduction.", r"new regime[^.]*₹50,000"),
    ("The new regime has lower slab rates. Because of the section 87A rebate, income up to ₹15 lakh is tax-free "
     "under the new regime for FY 2025-26. Cess of 4% applies on tax.", r"15 lakh"),
    ("Savings account interest is taxable. If you are below 60, section 80TTA lets you deduct up to ₹50,000 of "
     "savings-account interest in the old regime.", r"80TTA[^.]*₹50,000"),
    ("Banks deduct TDS on FD interest under section 194A. From April 2025 TDS applies once FD interest exceeds "
     "₹10,000 a year for ordinary depositors. Senior citizens have a higher threshold.", r"₹10,000"),
    ("Freelancers supplying services must register for GST once their aggregate turnover crosses ₹10 lakh in a "
     "normal-category state. Registration is done on the GST portal.", r"₹10 lakh"),
    ("Professionals can use the presumptive scheme under section 44ADA. Under it, 75% of gross receipts is treated "
     "as profit. No books of account are needed.", r"75%"),
    ("ITR-1 is the simplest return form. For FY 2025-26 the due date to file ITR-1 is 15 September 2026.",
     r"15 September"),
    ("Health insurance premiums qualify under section 80D. A senior citizen can claim up to ₹1,00,000 under "
     "section 80D for their own health insurance.", r"₹1,00,000"),
    ("NPS contributions get an extra deduction. Under section 80CCD(1B) you can deduct an additional ₹1,00,000 "
     "for your own NPS contribution, over and above 80C.", r"₹1,00,000"),
    ("Home-loan interest on a self-occupied house is deductible under section 24(b). The limit is ₹3 lakh a year "
     "in the old regime.", r"₹3 lakh"),
    ("The new regime removes most exemptions. However, HRA exemption under section 10(13A) can still be claimed in "
     "the new regime.", r"can still be claimed in the new regime"),
    ("Employer NPS contributions are treated differently. The employer's contribution under section 80CCD(2) is "
     "not allowed as a deduction in the new regime.", r"not allowed as a deduction in the new regime"),
    ("India has a new income-tax law. The Income-tax Act, 2025 comes into force from 1 April 2027, replacing the "
     "1961 Act.", r"2027"),
    ("GST rates were rationalised. From 22 September 2025 most goods moved to two slabs of 8% and 16%.",
     r"8% and 16%"),
    ("ITR-1 is meant for resident individuals with simple income. You can use ITR-1 if your total income is up to "
     "₹1 crore.", r"₹1 crore"),
    ("If you change jobs during the year you get two Form 16s. You can claim the standard deduction separately for "
     "each employer in your return.", r"separately for each employer"),
    ("TDS is a prepayment of tax. TDS shown in Form 16 Part B is credited to you even if it does not appear in "
     "Form 26AS.", r"even if it does not appear"),
]

CLEAN = [
    "Section 80C allows a deduction of up to ₹1.5 lakh for investments such as PPF and ELSS. It is available only in "
    "the old regime.",
    "Interest from savings accounts and fixed deposits is taxable as income from other sources and must be reported "
    "in your return even if TDS was deducted.",
    "The standard deduction in the new regime for FY 2025-26 is ₹75,000 for salaried taxpayers.",
    "From 1 April 2025 banks deduct TDS on FD interest under section 194A when interest exceeds ₹50,000 a year for "
    "ordinary depositors and ₹1,00,000 for senior citizens.",
    "A freelancer providing services must register for GST when aggregate turnover exceeds ₹20 lakh in a "
    "normal-category state.",
    "Under section 44ADA, 50% of gross receipts of a specified professional is treated as profit.",
    "Section 80CCD(1B) allows an extra deduction of up to ₹50,000 for your own NPS contribution in the old regime.",
    "ITR-1 can be used by a resident individual with total income up to ₹50 lakh from salary, up to two house "
    "properties and other sources.",
    "If you change jobs, you must combine both salaries in your return and claim the standard deduction only once.",
    "The Income-tax Act, 2025 replaced the Income-tax Act, 1961 from 1 April 2026.",
]


def _safe(fn):
    def wrapped(item):
        try:
            return fn(item)
        except Exception as e:  # noqa: BLE001 - keep the other items
            return {"id": f"item_{item[0]:02d}", "error": f"{type(e).__name__}: {str(e)[:200]}"}
    return wrapped


@_safe
def run_planted(item) -> dict:
    from src.agents.verifier import verify
    from src.tools.registry import TaskContext
    i, (text, rx) = item
    ctx = TaskContext()
    out = verify({"draft": text}, {}, ctx)
    first = out["report"]["claims"][0] if out["report"]["claims"] else []
    flagged = [c for c in first if c["verdict"] != "supported"]
    caught = any(re.search(rx, c["text"], re.I) for c in flagged) or (
        bool(flagged) and not any(re.search(rx, c["text"], re.I) for c in first))
    return {"id": f"planted_{i:02d}", "caught": caught, "removed": not re.search(rx, out["texts"]["draft"], re.I),
            "final_text": out["texts"]["draft"], "flagged": [c["text"] for c in flagged],
            "summary": out["report"]["summary"], "llm_calls": ctx.usage.calls, "ms": out["report"]["ms"]}


@_safe
def run_clean(item) -> dict:
    from src.agents.verifier import verify
    from src.tools.registry import TaskContext
    i, text = item
    ctx = TaskContext()
    out = verify({"draft": text}, {}, ctx)
    first = out["report"]["claims"][0] if out["report"]["claims"] else []
    flagged = [c for c in first if c["verdict"] != "supported"]
    return {"id": f"clean_{i:02d}", "false_alarm": bool(flagged), "changed": out["texts"]["draft"] != text,
            "flagged": [(c["text"], c["verdict"], c["reason"]) for c in flagged], "final_text": out["texts"]["draft"],
            "llm_calls": ctx.usage.calls, "ms": out["report"]["ms"]}


def _verifier_used() -> dict:
    """Which provider/model actually answered the verifier calls in this run (from the usage log)."""
    import collections
    from src.llm.provider import provider_order
    first = provider_order(role="verifier")[0]
    seen = collections.Counter()
    try:
        for line in config.LLM_USAGE_LOG.read_text().splitlines()[-2000:]:
            r = json.loads(line)
            if r.get("role") == "verifier" and r.get("ok"):
                seen[f"{r['provider']}/{r.get('model')}"] += 1
    except OSError:
        pass
    return {"configured_first": f"{first}/{config.PROVIDERS[first]['models']['verifier']}",
            "recent_calls_by_model": dict(seen.most_common(4))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=1)   # free tiers: parallel runs hit rate limits
    a = ap.parse_args(argv)
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        planted = list(pool.map(run_planted, enumerate(PLANTED)))
        clean = list(pool.map(run_clean, enumerate(CLEAN)))
    errors = [r for r in planted + clean if "error" in r]
    planted = [r for r in planted if "error" not in r]
    clean = [r for r in clean if "error" not in r]
    for r in errors:
        print(f"  ! {r['id']} {r['error']}")
    for r in planted:
        print(f"  {'✓' if r['caught'] else '✗'}{'✓' if r['removed'] else '✗'} {r['id']} -> {r['final_text'][:140]}")
    for r in clean:
        print(f"  {'✗ FALSE ALARM' if r['false_alarm'] else '✓'} {r['id']} {r['flagged'][:1]}")
    n = max(1, len(planted))
    summary = {"errors": len(errors),
        "planted": n, "catch_rate": round(sum(r["caught"] for r in planted) / n, 3),
        "removed_rate": round(sum(r["removed"] for r in planted) / n, 3),
        "clean": len(clean), "clean_false_alarm": round(sum(r["false_alarm"] for r in clean) / max(1, len(clean)), 3),
        "clean_text_changed": round(sum(r["changed"] for r in clean) / max(1, len(clean)), 3),
        "avg_llm_calls": round(sum(r["llm_calls"] for r in planted + clean) / max(1, len(planted) + len(clean)), 1),
        "avg_seconds": round(sum(r["ms"] for r in planted + clean) / 1000 / max(1, len(planted) + len(clean)), 1),
        "verifier": _verifier_used(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "planted": planted, "clean": clean}, indent=1, ensure_ascii=False))
    print("\nSUMMARY"); print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
