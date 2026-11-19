"""Phase 8 evaluation plumbing: scenario set, baseline scoring, roll-up. No LLM calls."""
import json

from experiments import run_agent_eval as agg
from experiments.run_pipeline_baseline import sub_questions
from experiments.run_single_agent_eval import score
from scripts.build_scenarios import scenario
from experiments.sim_user import _truth
from src.llm.provider import Usage


def _sc(pid):
    return scenario(next(g for g in _truth() if g["persona_id"] == pid))


def test_scenarios_cover_plan_fields():
    rows = [scenario(g) for g in _truth()]
    assert 30 <= len(rows) <= 50
    for r in rows:
        assert {"itr_form", "regime", "findings", "escalate"} <= set(r["expected"])
        assert set(r["tools"]["required"]) <= set(r["tools"]["allowed"])
    esc = [r for r in rows if r["expected"]["escalate"]]
    assert esc and all("write_ca_summary" in r["tools"]["required"] for r in esc)
    assert all(r["expected"]["regime"] is None for r in esc)


def test_freelancer_scenario_expects_gst_and_search():
    s = _sc("P27")
    assert s["expected"]["gst_registration_required"] is True
    assert "search_tax_law" in s["tools"]["required"]


def _answer(sc, **kw):
    e = sc["expected"]
    a = {"itr_form": e["itr_form"], "recommended_regime": e["regime"], "old_regime_total_tax": e["tax_old"],
         "new_regime_total_tax": e["tax_new"], "escalate_to_ca": e["escalate"], "escalation_reasons": [],
         "gst_registration_required": e["gst_registration_required"], "document_findings": e["findings"],
         "best_saving_option": None, "max_saving": None, "summary": ""}
    a.update(kw)
    return a


def _log(sc):
    return [{"tool": t, "ok": True} for t in sc["tools"]["required"]]


def test_single_agent_score_perfect_and_off_by_rupee():
    sc = _sc("P21")
    r = score(sc, _answer(sc), _log(sc), Usage(), 1.0, "final")
    assert r["success"] and r["tools_required_ok"] and not r["wrong_tools"]
    r = score(sc, _answer(sc, old_regime_total_tax=sc["expected"]["tax_old"] + 1), _log(sc), Usage(), 1.0, "final")
    assert r["amounts_ok"]                                  # ₹1 tolerance, as in the task eval
    r = score(sc, _answer(sc, old_regime_total_tax=sc["expected"]["tax_old"] - 1685), _log(sc), Usage(), 1.0, "final")
    assert not r["amounts_ok"] and not r["success"]


def test_single_agent_missed_finding_fails():
    sc = _sc("P23")
    assert sc["expected"]["findings"]
    r = score(sc, _answer(sc, document_findings=[]), _log(sc), Usage(), 1.0, "final")
    assert r["findings_ok"] is False and not r["success"]


def test_pipeline_sub_questions_carry_true_figures():
    qs = sub_questions(_sc("P21"))
    assert "₹16,80,000" in qs["calc"] and "₹5,400" in qs["calc"]
    assert {"calc", "itr", "ca"} <= set(qs)


def test_rollup_targets_and_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(agg, "RES", tmp_path)
    (tmp_path / "doc_check.json").write_text(json.dumps({"summary": {
        "personas": 10, "errors": 0, "persona_success": 1.0, "tool_call_accuracy": 1.0, "injection_resistance": 1.0}}))
    (tmp_path / "tasks_filing_prep.json").write_text(json.dumps({"summary": {
        "tasks": 10, "errors": 0, "task_success": 0.5, "key_tool_args_correct": 0.8, "escalation_accuracy": 1.0},
        "rows": []}))
    (tmp_path / "verifier.json").write_text(json.dumps({"summary": {"catch_rate": 0.95}}))
    h = agg.headline()
    assert h["task_success"] == 0.75 and h["tool_call_accuracy"] == 0.9 and h["tasks"] == 20
    md = agg.markdown(h, agg.architecture_comparison(), agg.verifier_comparison())
    assert "| task success | ≥ 80% | 75% | ✗ |" in md
