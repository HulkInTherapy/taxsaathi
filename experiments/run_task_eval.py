"""
Run full agentic tasks end to end with a simulated user and score them against ground truth.

    python -m experiments.run_task_eval P21 P22 P23          # specific personas
    python -m experiments.run_task_eval --workflow filing_prep
    python -m experiments.run_task_eval --workers 3

Per task: correct ITR form, correct regime (the cheaper one per the true facts), tax amounts
within ₹1 of ground truth, escalation decided correctly, GST answer, the three approval pauses
reached (filing prep), tool budget respected, key tool arguments right, and cost.
Writes experiments/agent_results/tasks_<workflow or custom>.json.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from experiments.sim_user import SimUser, _truth
from src import config

OUT_DIR = config.ROOT / "experiments" / "agent_results"
MAX_TURNS = 12


def run_one(pid: str) -> dict:
    from src.agents.service import TaskService
    gt = next(g for g in _truth() if g["persona_id"] == pid)
    user = SimUser(pid)
    svc = TaskService(db_path=":memory:")
    tid = svc.create(goal=user.goal, tax_year=gt["tax_year"], workflow=gt["workflow"])
    for name, data in user.documents():
        svc.add_document(tid, name, data)
    t0 = time.perf_counter()
    st = svc.run(tid)
    turns = 0
    while st["status"] == "waiting" and turns < MAX_TURNS:
        st = svc.resume(tid, user.answer(st["interrupt"]))
        turns += 1
    secs = time.perf_counter() - t0
    state = svc.state(tid)
    svc.close(tid)
    if st["status"] != "done":
        return {"persona_id": pid, "error": st.get("error") or f"ended in status {st['status']}",
                "trace": [t["summary"] for t in st.get("trace", [])]}
    return score(gt, state, user, secs, turns)


def score(gt: dict, state: dict, user: SimUser, secs: float, turns: int) -> dict:
    e, fin = gt["expected"], state["final"]
    itr, reg, esc = state.get("itr") or {}, state.get("regime") or {}, state.get("escalation") or {}
    tax = e["tax"]
    approvals = [q["step"] for q in user.questions if q.get("type") == "approval"]
    r = {
        "persona_id": gt["persona_id"], "label": gt["label"], "workflow": gt["workflow"],
        "itr_ok": itr.get("form") == e["itr_form"] if gt["workflow"] == "filing_prep" else None,
        "itr": itr.get("form"), "itr_expected": e["itr_form"],
        "escalate_ok": bool(esc.get("escalate")) == e["escalate"],
        "escalation_reasons": esc.get("reasons", []), "escalation_expected": e["escalation_reasons"],
        "regime_ok": None, "amounts_ok": None,
        "approvals": approvals, "questions": sum(1 for q in user.questions if q.get("type") != "approval"),
        "tool_calls": fin["usage"]["tool_calls"], "budget_ok": fin["usage"]["tool_calls"] <= fin["usage"]["tool_budget"],
        "agents": {k: (state.get(k) or {}).get("agent") for k in ("itr", "regime", "gst") if state.get(k)},
        "cost": {"llm_calls": fin["usage"]["calls"], "input_tokens": fin["usage"]["input_tokens"],
                 "output_tokens": fin["usage"]["output_tokens"], "seconds": round(secs, 1), "turns": turns},
        "assumptions": fin.get("assumptions"),
        "trace": [f"{t['node']}: {t['summary']}" for t in state.get("trace", [])],
    }
    if not e["escalate"] and tax:
        r["regime_ok"] = reg.get("recommended_regime") == tax["best_regime"] or (tax["old"] == tax["new"])
        r["amounts_ok"] = reg.get("old_total") == tax["old"] and reg.get("new_total") == tax["new"]
        r["regime"] = {"got": [reg.get("recommended_regime"), reg.get("old_total"), reg.get("new_total")],
                       "want": [tax["best_regime"], tax["old"], tax["new"]]}
        if not r["amounts_ok"]:
            r["figures_diff"] = {k: [state["figures"]["inputs"].get(k), v] for k, v in gt["true_inputs"].items()
                                 if state["figures"]["inputs"].get(k) != v}
    if gt["workflow"] == "tax_saving" and e.get("tax_saving"):
        sav = state.get("savings") or {}
        r["savings"] = {"got": [sav.get("best_option"), sav.get("max_saving")],
                        "want": [e["tax_saving"]["best_option"], e["tax_saving"]["max_saving"]]}
        r["savings_ok"] = sav.get("max_saving") == e["tax_saving"]["max_saving"] and \
            bool(sav.get("best_option")) == bool(e["tax_saving"]["best_option"])
    r["verification"] = state.get("verification", {}).get("summary")
    if "gst_registration_required" in e and not e["escalate"]:
        r["gst_ok"] = (state.get("gst") or {}).get("registration_required") == e["gst_registration_required"]
    checks = [r[k] for k in ("itr_ok", "escalate_ok", "regime_ok", "amounts_ok", "gst_ok", "savings_ok")
              if r.get(k) is not None]
    if gt["workflow"] == "filing_prep" and not e["escalate"]:
        checks.append(approvals == ["figures", "regime", "checklist"])
    if gt["workflow"] == "tax_saving" and not e["escalate"]:
        checks.append(approvals == ["figures", "savings_plan"])
    r["success"] = all(checks)
    return r


def summarise(rows: list[dict]) -> dict:
    ok = [r for r in rows if "error" not in r]

    def rate(k):
        v = [r[k] for r in ok if r.get(k) is not None]
        return round(sum(v) / len(v), 3) if v else None
    key_args = [a.get("key_args_ok") for r in ok for a in r["agents"].values() if a and a.get("key_args_ok") is not None]
    corrected = [a.get("corrected") for r in ok for a in r["agents"].values() if a]
    return {
        "tasks": len(rows), "errors": len(rows) - len(ok),
        "task_success": round(sum(r["success"] for r in ok) / max(1, len(rows)), 3),  # errors count as failures
        "itr_form_accuracy": rate("itr_ok"), "regime_accuracy": rate("regime_ok"), "amounts_exact": rate("amounts_ok"),
        "escalation_accuracy": rate("escalate_ok"), "gst_accuracy": rate("gst_ok"),
        "savings_accuracy": rate("savings_ok"),
        "verifier_claims_checked": sum((r.get("verification") or {}).get("claims_checked", 0) for r in ok),
        "verifier_initially_failing": sum((r.get("verification") or {}).get("initially_failing", 0) for r in ok),
        "verifier_unresolved": sum((r.get("verification") or {}).get("final_failing", 0) for r in ok),
        "key_tool_args_correct": round(sum(key_args) / len(key_args), 3) if key_args else None,
        "agent_answers_corrected": round(sum(corrected) / len(corrected), 3) if corrected else None,
        "budget_respected": rate("budget_ok"),
        "avg_tool_calls": round(statistics.mean(r["tool_calls"] for r in ok), 1) if ok else None,
        "avg_llm_calls": round(statistics.mean(r["cost"]["llm_calls"] for r in ok), 1) if ok else None,
        "avg_tokens": round(statistics.mean(r["cost"]["input_tokens"] + r["cost"]["output_tokens"] for r in ok)) if ok else None,
        "median_seconds": round(statistics.median(r["cost"]["seconds"] for r in ok), 1) if ok else None,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("personas", nargs="*")
    ap.add_argument("--workflow", default=None)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args(argv)
    ids = a.personas or [g["persona_id"] for g in _truth() if not a.workflow or g["workflow"] == a.workflow]
    rows = []
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for r in pool.map(run_one, ids):
            rows.append(r)
            if "error" in r:
                print(f"  ! {r['persona_id']} ERROR {r['error'][:300]}\n     " + " | ".join(r.get("trace", [])[-4:]), flush=True)
                continue
            print(f"  {'✓' if r['success'] else '✗'} {r['persona_id']} itr={r['itr']}/{r['itr_expected']} "
                  f"regime={r.get('regime')} esc={r['escalation_reasons']}/{r['escalation_expected']} "
                  f"gst={r.get('gst_ok')} savings={r.get('savings')} verify={r.get('verification')} "
                  f"approvals={r['approvals']} tools={r['tool_calls']} "
                  f"llm={r['cost']['llm_calls']} {r['cost']['seconds']}s"
                  + (f"\n     figures_diff={r['figures_diff']}" if r.get("figures_diff") else ""), flush=True)
    summary = summarise(rows)
    out = a.out or OUT_DIR / f"tasks_{a.workflow or 'custom'}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=1, ensure_ascii=False, default=str))
    print("\nSUMMARY"); print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
