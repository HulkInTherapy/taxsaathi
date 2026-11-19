"""
Build the Phase 8 agent evaluation set: data/eval/scenarios.jsonl.

One scenario per synthetic persona (40), derived from data/synthetic/ground_truth.jsonl so the
expected answers can never drift from the persona data. Each scenario holds the goal the
simulated user types, the documents uploaded, and what a correct run must produce:

    expected.itr_form, expected.regime (old/new/either), expected.tax_old/tax_new,
    expected.findings (document mismatch codes), expected.escalate (+ reasons),
    expected.injections, expected.gst_registration_required, expected.tax_saving
    tools.required  - tools a correct run must call
    tools.allowed   - every tool a correct run may call (anything else is a wrong tool)
    tools.order     - partial order: each tool listed must come after the ones before it

    python -m scripts.build_scenarios
"""
from __future__ import annotations

import json
import sys

from experiments.sim_user import SimUser, _truth
from src import config

OUT = config.ROOT / "data" / "eval" / "scenarios.jsonl"
GST_THRESHOLD_SERVICES = 20_00_000


def tools_for(gt: dict, freelance: bool) -> dict:
    wf, e = gt["workflow"], gt["expected"]
    has_docs = bool(gt["documents"])
    req: list[str] = ["parse_document", "cross_check_documents"] if has_docs else []
    allowed = {"parse_document", "cross_check_documents", "search_tax_law"}
    if wf == "filing_prep":
        req.append("itr_form_rules")
        allowed |= {"itr_form_rules", "calculate_tax", "write_ca_summary"}
        if e["escalate"]:
            req.append("write_ca_summary")
        else:
            req.append("calculate_tax")
            if freelance:
                req.append("search_tax_law")   # GST agent cites the s.22 threshold
    elif wf == "tax_saving":
        allowed |= {"calculate_tax", "write_ca_summary"}
        req.append("write_ca_summary" if e["escalate"] else "calculate_tax")
    order = [t for t in ("parse_document", "cross_check_documents", "itr_form_rules", "calculate_tax") if t in req]
    return {"required": req, "allowed": sorted(allowed), "order": order}


def scenario(gt: dict) -> dict:
    user = SimUser(gt["persona_id"])
    e, tax = gt["expected"], gt["expected"]["tax"]
    freelance = bool(user.p.get("freelance"))
    exp = {
        "itr_form": e["itr_form"] if gt["workflow"] == "filing_prep" else None,
        "regime": None, "tax_old": None, "tax_new": None,
        "findings": sorted({f["code"] for f in e["findings"]}),
        "escalate": e["escalate"], "escalation_reasons": e["escalation_reasons"],
        "injections": e["injections"],
        "gst_registration_required": None, "tax_saving": e.get("tax_saving"),
    }
    if tax and not e["escalate"] and gt["workflow"] != "document_check":
        exp.update({"regime": "either" if tax["old"] == tax["new"] else tax["best_regime"],
                    "tax_old": tax["old"], "tax_new": tax["new"]})
    if freelance and gt["workflow"] == "filing_prep" and not e["escalate"]:
        exp["gst_registration_required"] = user.p["freelance"]["receipts"] > GST_THRESHOLD_SERVICES
    return {"id": f"S{gt['persona_id'][1:]}", "persona_id": gt["persona_id"], "label": gt["label"],
            "workflow": gt["workflow"], "tax_year": gt["tax_year"], "goal": user.goal,
            "documents": [{"file": d["file"], "type": d["type"]} for d in gt["documents"]],
            "expected": exp, "tools": tools_for(gt, freelance)}


def main() -> int:
    rows = [scenario(g) for g in _truth()]
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    by_wf: dict[str, int] = {}
    for r in rows:
        by_wf[r["workflow"]] = by_wf.get(r["workflow"], 0) + 1
    print(f"wrote {len(rows)} scenarios to {OUT.relative_to(config.ROOT)}: {by_wf}; "
          f"escalate={sum(r['expected']['escalate'] for r in rows)}, "
          f"with findings={sum(bool(r['expected']['findings']) for r in rows)}, "
          f"injections={sum(bool(r['expected']['injections']) for r in rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
