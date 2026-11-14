"""Orchestrator graph without a real LLM: plan validation, routing, interrupts/resume, approvals,
escalation, budget and figure building. The LLM gateway is replaced by a scripted fake."""
from langchain_core.messages import AIMessage

import pytest

from src.agents import figures as F
from src.agents import graph as G
from src.agents.service import TaskService
from src.agents.state import UserFacts


# ------------------------------------------------------------------ deterministic pieces
def test_validate_steps_adds_required_and_orders():
    steps, fixes = G.validate_steps("filing_prep", ["regime", "itr_form", "bogus"], has_docs=True, facts=UserFacts())
    assert steps == ["documents", "facts", "figures", "itr_form", "escalation", "regime", "checklist"]
    assert any("added" in f for f in fixes) and any("unknown" in f for f in fixes)
    steps, _ = G.validate_steps("document_check", ["documents", "regime"], has_docs=True, facts=UserFacts())
    assert steps == ["documents"]
    steps, _ = G.validate_steps("filing_prep", ["documents", "facts"], has_docs=False, facts=UserFacts())
    assert "documents" not in steps


def test_hra_exemption_rule():
    # least of HRA 30k*12, rent-10% basic (40k-6k)*12, 50% basic 30k*12
    assert F.hra_exemption(60_000, 30_000, 40_000, metro=True) == 360_000
    assert F.hra_exemption(60_000, 30_000, 20_000, metro=True) == (20_000 - 6_000) * 12
    assert F.hra_exemption(60_000, 30_000, 0, metro=True) == 0


def test_build_figures_from_documents_and_facts():
    extracted = {
        "a": {"type": "form16", "fields": {"employer_name": "X", "gross_salary": 1_500_000, "part_a_total_tds": 90_000,
                                          "tds_part_b": 97_500, "new_regime": True, "chapter_via": []}},
        "b": {"type": "interest_certificate", "fields": {"bank_name": "B", "total_interest": 60_000, "total_tds": 5_000,
              "accounts": [{"account_type": "savings", "interest": 12_000, "tds": 0},
                           {"account_type": "fixed_deposit", "interest": 48_000, "tds": 5_000}]}},
    }
    facts = UserFacts(age=35, epf_annual=72_000, other_80c=50_000, health_80d=20_000, rent_monthly=30_000,
                      basic_monthly=62_500, hra_monthly=31_250, metro_city=True, nps_80ccd1b=0, home_loan_interest=0)
    fig = F.build_figures(extracted, facts, "2025-26")
    i = fig["inputs"]
    assert i["gross_salary"] == 1_500_000 and i["other_income"] == 60_000
    assert i["deductions_80c"] == 122_000 and i["deductions_80d"] == 20_000
    assert i["other_deductions"] == 10_000            # 80TTA capped
    assert i["hra_exemption"] == F.hra_exemption(62_500, 31_250, 30_000, True)
    assert fig["tds"]["credited"] == 95_000           # Part A deposited + interest TDS, not Part B
    assert "Form 16" in fig["provenance"]["salary"]


def test_escalation_rules():
    assert F.escalation_reasons(UserFacts(short_term_capital_gains=True)) == ["capital_gains"]
    assert F.escalation_reasons(UserFacts(ltcg_112a=90_000)) == []
    assert F.escalation_reasons(UserFacts(freelance_receipts=6_200_000, cash_receipts_over_5pct=True)) == \
        ["presumptive_limit_exceeded"]
    assert F.escalation_reasons(UserFacts(company_director=True, fno_trading=True)) == \
        ["director_or_unlisted_shares", "fno_or_losses"]


# ------------------------------------------------------------------ graph with a scripted LLM
ALL_NO = {k: v for k, v in dict(age=30, residential_status="resident", short_term_capital_gains=False,
                                other_capital_gains=False, foreign_assets_or_income=False, company_director=False,
                                unlisted_shares=False, fno_trading=False, house_properties=0, other_80c=0, health_80d=0,
                                nps_80ccd1b=0, home_loan_interest=0, rent_monthly=0, salary_without_form16=1_500_000,
                                epf_annual=0).items()}


class FakeLLM:
    """Answers each agent the way a well-behaved model would, keyed by which tools it was offered."""

    def __init__(self):
        self.calls = 0

    def __call__(self, messages, role="planner", tools=None, tool_choice=None, **kw):
        self.calls += 1
        names = [t["function"]["name"] if isinstance(t, dict) else t.__name__ for t in (tools or [])]
        last = messages[-1]
        tool_msgs = [m for m in messages if getattr(m, "type", "") == "tool"]
        if "TaskPlan" in names:
            return _call("TaskPlan", {"workflow": "filing_prep", "steps": ["facts", "figures", "regime"]})
        if "FactsAnswer" in names:
            return _call("FactsAnswer", ALL_NO)
        if "ITRDecision" in names:
            if not tool_msgs:
                import json
                args = json.loads(messages[1].content.split("arguments:\n", 1)[1])
                return _call("itr_form_rules", args)
            return _call("ITRDecision", {"form": "ITR-2", "reasons": ["wrong on purpose"]})  # gets corrected
        if "RegimeRecommendation" in names:
            if not tool_msgs:
                import json
                return _call("calculate_tax", json.loads(messages[1].content.split("inputs:\n", 1)[1]))
            return _call("RegimeRecommendation", {"recommended_regime": "new", "explanation": "cheaper"})
        raise AssertionError(f"unexpected call: {names} {last}")


def _call(name, args):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"c{name}"}])


@pytest.fixture
def fake(monkeypatch):
    f = FakeLLM()
    monkeypatch.setattr("src.llm.provider.chat", f)
    monkeypatch.setattr(G.prov, "chat", f)
    return f


def test_filing_prep_end_to_end_with_interrupts(fake):
    svc = TaskService(db_path=":memory:")
    tid = svc.create("Help me prepare my return", "2025-26")
    st = svc.run(tid)
    assert st["status"] == "waiting" and st["interrupt"]["kind"] == "missing_info"
    st = svc.resume(tid, {"text": "I'm 30, resident, salary 15 lakh, nothing else."})
    assert st["interrupt"]["step"] == "figures" and st["interrupt"]["figures"]["gross_salary"] == 1_500_000
    st = svc.resume(tid, {"approved": True})
    assert st["interrupt"]["step"] == "regime" and st["interrupt"]["recommended_regime"] == "new"
    st = svc.resume(tid, "yes")
    assert st["interrupt"]["step"] == "checklist"
    st = svc.resume(tid, {"approved": True})
    assert st["status"] == "done"
    s = svc.state(tid)
    assert s["itr"]["form"] == "ITR-1" and s["itr"]["agent"]["corrected"] is True   # agent said ITR-2
    assert s["regime"]["new_total"] == 97_500 and s["regime"]["agent"]["key_args_ok"] is True
    assert s["final"]["usage"]["tool_calls"] == 2
    assert [p["status"] for p in s["plan"]].count("pending") == 0
    svc.close(tid)
    assert svc.state(tid) == {}


def test_user_edits_figures_then_approves(fake):
    svc = TaskService(db_path=":memory:")
    tid = svc.create("Prepare my return", "2025-26")
    svc.run(tid)
    svc.resume(tid, {"text": "..."})
    st = svc.resume(tid, {"approved": False, "edits": {"salary_without_form16": 1_200_000}})
    assert st["interrupt"]["step"] == "figures" and st["interrupt"]["figures"]["gross_salary"] == 1_200_000


def test_escalation_skips_regime_and_checklist(fake, monkeypatch):
    monkeypatch.setitem(ALL_NO, "foreign_assets_or_income", True)
    svc = TaskService(db_path=":memory:")
    tid = svc.create("Prepare my return", "2025-26")
    svc.run(tid)
    svc.resume(tid, {"text": "..."})
    st = svc.resume(tid, {"approved": True})
    assert st["status"] == "done"
    s = svc.state(tid)
    assert s["escalation"]["escalate"] and "Schedule FA" in s["escalation"]["ca_summary"]
    assert {p["step"]: p["status"] for p in s["plan"]}["regime"] == "skipped"


def test_parse_facts_structured_answer_skips_llm(fake):
    out = G.parse_facts_answer({"facts": {"age": 41, "rent_monthly": 0}}, ["age"], G.register_task("x")[0])
    assert out == {"age": 41, "rent_monthly": 0} and fake.calls == 0


def test_lenient_validate_drops_bad_fields_only():
    from src.agents.state import lenient_validate
    out = lenient_validate(UserFacts, {"age": 40, "fno_trading": "None", "company_director": "maybe", "other_80c": "null"})
    assert out.model_dump(exclude_none=True) == {"age": 40}
