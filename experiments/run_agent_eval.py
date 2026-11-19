"""
Phase 8 roll-up: read every agent evaluation result, check it against the plan's targets, build
the comparison tables, and log it all to MLflow (experiment "taxot-m4-agents").

It makes no LLM calls; run the evaluations first (sequentially on free tiers):

    python -m scripts.build_scenarios                                   # data/eval/scenarios.jsonl
    python -m experiments.run_doc_eval --workers 1                      # Workflow 1
    python -m experiments.run_task_eval --workflow filing_prep --workers 1
    python -m experiments.run_task_eval --workflow tax_saving --workers 1
    python -m experiments.run_verifier_eval                             # planted claims
    python -m experiments.run_single_agent_eval                         # baseline: one LLM, all tools
    python -m experiments.run_pipeline_baseline --mode single           # baseline: M3 pipeline
    python -m experiments.run_pipeline_baseline --mode decomposed
    python -m experiments.run_agent_eval [--no-mlflow]

Writes experiments/agent_results/summary.json and prints the tables in Markdown.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from src import config

RES = config.ROOT / "experiments" / "agent_results"

TARGETS = [  # (name, target, higher is better)
    ("task_success", 0.80), ("tool_call_accuracy", 0.85), ("verifier_catch_rate", 0.90),
    ("escalation_accuracy", 0.90), ("injection_resistance", 1.00)]


def _load(name: str) -> dict | None:
    p = RES / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _weighted(parts: list[tuple[float | None, int]]) -> float | None:
    parts = [(v, n) for v, n in parts if v is not None and n]
    n = sum(n for _, n in parts)
    return round(sum(v * n for v, n in parts) / n, 3) if n else None


def headline() -> dict:
    doc, fp, ts, ver = _load("doc_check"), _load("tasks_filing_prep"), _load("tasks_tax_saving"), _load("verifier")
    d = (doc or {}).get("summary", {})
    f = (fp or {}).get("summary", {})
    t = (ts or {}).get("summary", {})
    v = (ver or {}).get("summary", {})
    m = {
        "task_success": _weighted([(d.get("persona_success"), d.get("personas", 0)),
                                   (f.get("task_success"), f.get("tasks", 0)), (t.get("task_success"), t.get("tasks", 0))]),
        "tool_call_accuracy": _weighted([(d.get("tool_call_accuracy"), d.get("personas", 0)),
                                         (f.get("key_tool_args_correct"), f.get("tasks", 0)),
                                         (t.get("key_tool_args_correct"), t.get("tasks", 0))]),
        "verifier_catch_rate": v.get("catch_rate"),
        "escalation_accuracy": _weighted([(f.get("escalation_accuracy"), f.get("tasks", 0)),
                                          (t.get("escalation_accuracy"), t.get("tasks", 0))]),
        "injection_resistance": d.get("injection_resistance"),
        "tasks": sum(x for x in (d.get("personas"), f.get("tasks"), t.get("tasks")) if x),
        "errors": sum(x for x in (d.get("errors"), f.get("errors"), t.get("errors")) if x),
    }
    for wf, s in (("document_check", d), ("filing_prep", f), ("tax_saving", t)):
        m[f"{wf}_avg_llm_calls"] = s.get("avg_llm_calls")
        m[f"{wf}_avg_tokens"] = s.get("avg_tokens")
        m[f"{wf}_median_seconds"] = s.get("median_seconds")
        m[f"{wf}_avg_tool_calls"] = s.get("avg_tool_calls")
    return m


def architecture_comparison() -> list[dict]:
    """Same 22 filing/tax-saving scenarios: M3 pipeline vs single agent vs multi-agent (raw and final)."""
    rows = []
    for name, label in (("pipeline_baseline_single", "NLP pipeline, whole request"),
                        ("pipeline_baseline_decomposed", "NLP pipeline, one question per sub-task"),
                        ("single_agent", "Single agent (one LLM, all tools)")):
        s = (_load(name) or {}).get("summary")
        if s:
            rows.append({"system": label, **{k: s.get(k) for k in (
                "tasks", "task_success", "itr_form_accuracy", "regime_accuracy", "amounts_exact",
                "escalation_accuracy", "gst_accuracy", "savings_accuracy", "findings_recall",
                "avg_llm_calls", "avg_tokens", "median_seconds")}})
    multi = [r for n in ("tasks_filing_prep", "tasks_tax_saving") for r in (_load(n) or {}).get("rows", [])]
    if multi:
        ok = [r for r in multi if "error" not in r]

        def rate(k):
            v = [r[k] for r in ok if r.get(k) is not None]
            return round(sum(v) / len(v), 3) if v else None
        agents = [a for r in ok for a in r["agents"].values() if a]
        raw = round(1 - sum(a["corrected"] for a in agents) / len(agents), 3) if agents else None
        rows.append({"system": "Multi-agent orchestrator (Taxot)", "tasks": len(multi),
                     "task_success": round(sum(r["success"] for r in ok) / len(multi), 3),
                     "itr_form_accuracy": rate("itr_ok"), "regime_accuracy": rate("regime_ok"),
                     "amounts_exact": rate("amounts_ok"), "escalation_accuracy": rate("escalate_ok"),
                     "gst_accuracy": rate("gst_ok"), "savings_accuracy": rate("savings_ok"),
                     "findings_recall": (_load("doc_check") or {}).get("summary", {}).get("finding_recall"),
                     "specialist_answers_right_before_reconciliation": raw,
                     "avg_llm_calls": round(sum(r["cost"]["llm_calls"] for r in ok) / len(ok), 1),
                     "avg_tokens": round(sum(r["cost"]["input_tokens"] + r["cost"]["output_tokens"] for r in ok) / len(ok)),
                     "median_seconds": sorted(r["cost"]["seconds"] for r in ok)[len(ok) // 2]})
    return rows


def verifier_comparison() -> dict:
    """With vs without the verifier: unsupported claims that would reach the user."""
    rows = [r for n in ("tasks_filing_prep", "tasks_tax_saving") for r in (_load(n) or {}).get("rows", [])
            if r.get("verification")]
    checked = sum(r["verification"].get("claims_checked", 0) for r in rows)
    before = sum(r["verification"].get("initially_failing", 0) for r in rows)
    after = sum(r["verification"].get("final_failing", 0) for r in rows)
    v = (_load("verifier") or {}).get("summary", {})
    return {"tasks_with_verification": len(rows), "claims_checked": checked,
            "unsupported_without_verifier": before, "unsupported_with_verifier": after,
            "planted_caught": v.get("catch_rate"), "planted_removed": v.get("removed_rate"),
            "clean_false_alarm": v.get("clean_false_alarm")}


def markdown(head: dict, arch: list[dict], ver: dict) -> str:
    def f(x):
        return "—" if x is None else (f"{x:.0%}" if isinstance(x, float) and x <= 1 else str(x))
    out = ["### Targets (plan, Phase 8)", "", "| Metric | Target | Result | Met |", "|---|---|---|---|"]
    for k, tgt in TARGETS:
        got = head.get(k)
        out.append(f"| {k.replace('_', ' ')} | ≥ {tgt:.0%} | {f(got)} | {'✓' if got is not None and got >= tgt else '✗'} |")
    out += ["", f"{head['tasks']} tasks, {head['errors']} errors.", "",
            "### Architecture comparison (same filing / tax-saving scenarios)", "",
            "| System | Success | ITR | Regime | Exact tax | Escalation | GST | Savings | Findings | LLM calls | Tokens | Median s |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in arch:
        out.append("| " + " | ".join([r["system"]] + [f(r.get(k)) for k in (
            "task_success", "itr_form_accuracy", "regime_accuracy", "amounts_exact", "escalation_accuracy",
            "gst_accuracy", "savings_accuracy", "findings_recall", "avg_llm_calls", "avg_tokens",
            "median_seconds")]) + " |")
    out += ["", "### With vs without the verifier", "",
            f"- Claims checked on real task outputs: {ver['claims_checked']} over {ver['tasks_with_verification']} tasks",
            f"- Without the verifier, **{ver['unsupported_without_verifier']}** unsupported claims would have reached "
            f"the user unmarked; with it, revision fixed all but **{ver['unsupported_with_verifier']}**, which were "
            f"removed from the text or flagged \"confirm with a CA\" (none shipped unmarked)",
            f"- Planted unsupported claims caught: {f(ver['planted_caught'])} (removed {f(ver['planted_removed'])}); "
            f"false alarms on clean drafts: {f(ver['clean_false_alarm'])}"]
    return "\n".join(out)


def log_mlflow(head: dict, arch: list[dict], ver: dict) -> None:
    try:
        import mlflow
    except ImportError:
        print("mlflow not installed; skipping MLflow logging")
        return
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")   # newer MLflow refuses file stores unless opted in
    mlflow.set_tracking_uri(f"file:{config.MLRUNS_DIR}")
    mlflow.set_experiment("taxot-m4-agents")
    with mlflow.start_run(run_name="headline"):
        mlflow.log_metrics({k: v for k, v in head.items() if isinstance(v, (int, float))})
        mlflow.log_metrics({f"verifier_{k}": v for k, v in ver.items() if isinstance(v, (int, float))})
        for p in sorted(RES.glob("*.json")):
            mlflow.log_artifact(str(p), "results")
    for r in arch:
        with mlflow.start_run(run_name=r["system"]):
            mlflow.log_param("system", r["system"])
            mlflow.log_metrics({k: v for k, v in r.items() if isinstance(v, (int, float))})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-mlflow", action="store_true")
    a = ap.parse_args(argv)
    head, arch, ver = headline(), architecture_comparison(), verifier_comparison()
    (RES / "summary.json").write_text(json.dumps({"headline": head, "architectures": arch, "verifier": ver},
                                                 indent=1, ensure_ascii=False))
    print(markdown(head, arch, ver))
    if not a.no_mlflow:
        log_mlflow(head, arch, ver)
    return 0


if __name__ == "__main__":
    sys.exit(main())
