"""
Baseline for the Phase 8 comparison "NLP pipeline (M1-M3) vs agentic".

The single-shot /ask pipeline cannot read documents or ask questions, so it gets more help
than the agents: the request is the scenario goal plus the TRUE document figures (gross salary,
interest) and every user fact written out. Its answer is scored on the same scenario fields:

  * ITR form    - the expected form named in the answer text (and no other form)
  * regime/tax  - from the pipeline's structured `calculation`, when its calculator fires
  * escalation  - the answer recommends a CA exactly when the scenario expects escalation
  * findings    - it cannot cross-check documents, so any expected finding is missed
  * GST         - the answer states registration is (not) required, matching the scenario

    python -m experiments.run_pipeline_baseline --mode single       # the whole request, as typed
    python -m experiments.run_pipeline_baseline --mode decomposed   # best case: one question per sub-task

No agent LLM calls (if Ollama is not running the pipeline answers extractively). Writes
experiments/agent_results/pipeline_baseline_<mode>.json.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from experiments.run_single_agent_eval import ALL_FACTS, load
from experiments.sim_user import SimUser, _truth
from src import config
from src.calculator.tax import format_inr

OUT = config.ROOT / "experiments" / "agent_results" / "pipeline_baseline.json"  # suffixed with the mode
CA_RE = re.compile(r"chartered accountant|\bCA\b|tax professional|consult (a|an) (expert|professional)", re.I)
GST_YES = re.compile(r"(must|need to|required to|have to) register|registration is (mandatory|required)", re.I)
GST_NO = re.compile(r"(not|no) (need|required) to register|registration is not (mandatory|required)", re.I)


def request(sc: dict) -> str:
    gt = next(g for g in _truth() if g["persona_id"] == sc["persona_id"])
    ti, user = gt["true_inputs"], SimUser(sc["persona_id"])
    docs = []
    if ti.get("income_type") == "salary" and ti.get("gross_salary"):
        docs.append(f"My Form 16 shows gross salary of {format_inr(ti['gross_salary'])}.")
    if ti.get("other_income"):
        docs.append(f"I earned {format_inr(ti['other_income'])} bank/FD interest.")
    return " ".join([sc["goal"], *docs, user.facts_text(ALL_FACTS)])


def sub_questions(sc: dict) -> dict[str, str]:
    """What a user would type as separate questions (best case for a single-shot pipeline)."""
    gt = next(g for g in _truth() if g["persona_id"] == sc["persona_id"])
    ti, user = gt["true_inputs"], SimUser(sc["persona_id"])
    about = user.facts_text(ALL_FACTS)
    inc = (f"freelance professional receipts {format_inr(ti['gross_salary'])} under section 44ADA"
           if ti.get("income_type") != "salary" else f"salary {format_inr(ti['gross_salary'])}")
    parts = [inc]
    for k, label in (("other_income", "interest income"), ("deductions_80c", "80C"), ("deductions_80d", "80D"),
                     ("deductions_80d_parents", "80D for parents"), ("nps_80ccd1b", "NPS 80CCD(1B)"),
                     ("home_loan_interest", "home loan interest"), ("hra_exemption", "HRA exemption"),
                     ("other_deductions", "80TTA/80TTB")):
        if ti.get(k):
            parts.append(f"{label} {format_inr(ti[k])}")
    age = {"below60": "below 60", "60to80": "a senior citizen", "above80": "above 80"}.get(ti.get("age"), "below 60")
    qs = {"calc": f"Calculate my income tax for FY {sc['tax_year']} under the old and new regime: "
                  + ", ".join(parts) + f". I am {age}.",
          "itr": f"Which ITR form should I file for FY {sc['tax_year']}? {about}",
          "ca": f"Can I file my return myself or do I need a chartered accountant? {about}"}
    if sc["expected"]["gst_registration_required"] is not None:
        qs["gst"] = f"Do I need GST registration? {sc['goal']}"
    return qs


def run_one(pipe, sc: dict, cfg: str, mode: str) -> dict:
    qs = {k: request(sc) for k in ("calc", "itr", "ca", "gst")} if mode == "single" else sub_questions(sc)
    t0 = time.perf_counter()
    cache: dict[str, dict] = {}
    res = {}
    for k, q in qs.items():   # single mode asks the same question once
        if q not in cache:
            cache[q] = pipe.ask(q, cfg)
        res[k] = cache[q]
    secs = time.perf_counter() - t0
    e = sc["expected"]
    txt = {k: v.get("answer") or "" for k, v in res.items()}
    calc = res["calc"].get("calculation") or {}
    forms = set(re.findall(r"ITR-?\s?([1-4])\b", txt["itr"]))
    r: dict = {"id": sc["id"], "label": sc["label"], "workflow": sc["workflow"], "mode": mode,
               "questions": qs, "answers": {k: v[:1200] for k, v in txt.items()},
               "refused": any(v.get("refused") for v in res.values()), "calculator_used": bool(calc),
               "itr_ok": None, "regime_ok": None, "amounts_ok": None, "gst_ok": None, "savings_ok": None,
               "escalate_ok": bool(CA_RE.search(txt["ca"])) == e["escalate"],
               "findings_ok": False if e["findings"] else None, "seconds": round(secs, 2)}
    if e["itr_form"] and not e["escalate"]:
        r["itr_ok"] = forms == {e["itr_form"][-1]}
    if e["regime"]:
        better = calc.get("better")
        r["regime_ok"] = bool(calc) and (e["regime"] == "either" or better == e["regime"])
        r["amounts_ok"] = bool(calc) and calc.get("old", {}).get("total") == e["tax_old"] and \
            calc.get("new", {}).get("total") == e["tax_new"]
    if e["gst_registration_required"] is not None:
        t = txt.get("gst", "")
        r["gst_ok"] = bool(GST_YES.search(t)) if e["gst_registration_required"] else bool(GST_NO.search(t))
    if e.get("tax_saving") and not e["escalate"]:
        r["savings_ok"] = False   # no what-if optimiser in the pipeline
    checks = [r[k] for k in ("itr_ok", "escalate_ok", "regime_ok", "amounts_ok", "gst_ok", "savings_ok", "findings_ok")
              if r[k] is not None]
    r["success"] = all(checks)
    return r


def summarise(rows: list[dict]) -> dict:
    def rate(k):
        v = [r[k] for r in rows if r.get(k) is not None]
        return round(sum(v) / len(v), 3) if v else None
    return {"tasks": len(rows), "task_success": rate("success"), "itr_form_accuracy": rate("itr_ok"),
            "regime_accuracy": rate("regime_ok"), "amounts_exact": rate("amounts_ok"),
            "escalation_accuracy": rate("escalate_ok"), "gst_accuracy": rate("gst_ok"),
            "savings_accuracy": rate("savings_ok"), "findings_recall": rate("findings_ok"),
            "calculator_fired": rate("calculator_used"), "refused": rate("refused"),
            "median_seconds": sorted(r["seconds"] for r in rows)[len(rows) // 2] if rows else None}


def main(argv=None) -> int:
    from src.generation.llm import is_available
    from src.pipeline import get_pipeline
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--config", default="C5")
    ap.add_argument("--mode", choices=["single", "decomposed"], default="single",
                    help="single: the whole request as one question; decomposed: separate sub-questions")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    pipe = get_pipeline()
    rows = []
    for sc in load(a.ids):
        r = run_one(pipe, sc, a.config, a.mode)
        rows.append(r)
        print(f"  {'✓' if r['success'] else '✗'} {r['id']} itr={r['itr_ok']} regime={r['regime_ok']} "
              f"amounts={r['amounts_ok']} esc={r['escalate_ok']} gst={r['gst_ok']} find={r['findings_ok']} "
              f"calc={r['calculator_used']} refused={r['refused']}", flush=True)
    summary = {**summarise(rows), "mode": a.mode, "config": a.config, "llm_generation": is_available()}
    out = a.out or OUT.with_name(f"pipeline_baseline_{a.mode}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False, default=str))
    print("\nSUMMARY"); print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
