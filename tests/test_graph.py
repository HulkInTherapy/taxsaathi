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
    assert steps == ["documents", "facts", "figures", "itr_form", "escalation", "regime", "verify", "checklist"]
    assert any("added" in f for f in fixes) and any("unknown" in f for f in fixes)
    steps, _ = G.validate_steps("document_check", ["documents", "regime"], has_docs=True, facts=UserFacts())
    assert steps == ["documents", "verify"]
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
        if "CASummaryDone" in names:
            if not tool_msgs:
                return _call("write_ca_summary", {"reason_for_escalation": "Foreign assets need Schedule FA reporting",
                                                  "taxpayer_profile": "resident, 30", "open_questions": ["Schedule FA"]})
            return _call("CASummaryDone", {"note": "A CA must handle foreign assets."})
        if "ClaimList" in names:      # verifier: nothing to check in these tests
            return _call("ClaimList", {"claims": []})
        if "TaskPlan" in names:
            return _call("TaskPlan", {"workflow": "filing_prep", "steps": ["facts", "figures", "regime"]})
        if "FactsAnswer" in names:
            schema = next(t for t in tools if not isinstance(t, dict))
            return _call("FactsAnswer", {k: v for k, v in ALL_NO.items() if k in schema.model_fields})
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


def test_saving_candidates_respect_caps_and_capacity():
    inputs = {"deductions_80c": 130_000, "nps_80ccd1b": 0, "deductions_80d": 12_000, "deductions_80d_parents": 0,
              "age": "below60", "parents_senior": False}
    facts = UserFacts(extra_80c_possible=110_000, extra_nps_possible=50_000, extra_80d_possible=13_000,
                      extra_80d_parents_possible=60_000, parents_senior=True)
    c = {x["field"]: x for x in F.saving_candidates(inputs, facts)}
    assert c["deductions_80c"]["extra_investment"] == 20_000          # only up to the ₹1.5 lakh cap
    assert c["nps_80ccd1b"]["extra_investment"] == 50_000
    assert c["deductions_80d"]["extra_investment"] == 13_000          # 25k cap for below 60
    assert c["deductions_80d_parents"]["extra_investment"] == 50_000  # senior parents: 50k cap, not 60k
    assert c["combined"]["extra_investment"] == 133_000
    assert F.saving_candidates(inputs, UserFacts()) == []              # no capacity, no options


def test_verified_texts_written_back():
    state = {"documents_report": {"report": {"summary": "s", "findings": [{"code": "x", "explanation": "e", "action": "a"}]}},
             "regime": {"explanation": "old"}, "savings": {"summary": "S", "recommendations": [{"explanation": "r"}]},
             "itr": {"reasons": ["a", "b"]}}
    texts = G.collect_texts(state)
    assert set(texts) == {"documents.summary", "documents.findings.0.explanation", "documents.findings.0.action",
                          "regime.text", "savings.summary", "savings.recommendations.0.explanation", "itr.reasons"}
    upd = G.apply_texts(state, {"regime.text": "new", "documents.findings.0.explanation": "E2", "itr.reasons": "fixed"})
    assert upd["regime"]["explanation"] == "new" and upd["documents_report"]["report"]["findings"][0]["explanation"] == "E2"
    assert upd["itr"]["reasons"] == ["fixed"] and state["regime"]["explanation"] == "old"   # original untouched


def test_verifier_revises_then_drops_unsupported(monkeypatch):
    from src.agents import verifier as V
    from src.tools.registry import TaskContext
    ctx = TaskContext(retrieval_config="B1")
    from pathlib import Path
    from src.ingest.ingest import load_all
    from src.pipeline import Taxot
    ctx._pipeline = Taxot(chunks=load_all(Path(__file__).parent / "fixtures" / "kb", None), use_llm=False)
    text = "Your tax is ₹97,500. Section 80C allows up to ₹2,50,000."
    script = iter([
        _call("ClaimList", {"claims": [{"key": "d", "text": "Your tax is ₹97,500.", "kind": "user_figure"},
                                       {"key": "d", "text": "Section 80C allows up to ₹2,50,000.", "kind": "law"}]}),
        _call("Verdicts", {"verdicts": [{"claim_id": 1, "verdict": "supported"}, {"claim_id": 2, "verdict": "contradicted"}]}),
        _call("Revisions", {"texts": [{"key": "d", "text": "Your tax is ₹97,500. Section 80C allows up to ₹1,50,000."}]}),
        _call("ClaimList", {"claims": [{"key": "d", "text": "Section 80C allows up to ₹1,50,000.", "kind": "law"}]}),
        # judge wrongly says supported, but ₹1,50,000 is not in the (fixture) evidence -> deterministic check fails it
        _call("Verdicts", {"verdicts": [{"claim_id": 1, "verdict": "supported"}]}),
        _call("Revisions", {"texts": [{"key": "d", "text": "Your tax is ₹97,500. Section 80C allows up to ₹1,50,000."}]}),
        _call("ClaimList", {"claims": [{"key": "d", "text": "Section 80C allows up to ₹1,50,000.", "kind": "law"}]}),
        _call("Verdicts", {"verdicts": [{"claim_id": 1, "verdict": "unsupported"}]}),
    ])
    monkeypatch.setattr(V.prov, "chat", lambda *a, **k: next(script))
    monkeypatch.setattr(V, "_evidence", lambda claims, ctx, rc: {"P1": {"id": "P1", "title": "t", "text": "80C limit", "effective": ""}})
    out = V.verify({"d": text}, {"tax": 97_500}, ctx)
    assert out["report"]["summary"]["initially_failing"] == 1 and out["report"]["rounds"] == 2
    assert "2,50,000" not in out["texts"]["d"] and "1,50,000" not in out["texts"]["d"]   # unresolved sentence dropped
    assert out["texts"]["d"].startswith("Your tax is ₹97,500.") and V.UNVERIFIED_NOTE.strip() in out["texts"]["d"]


def test_sections_in_claims():
    from src.agents.verifier import sections_in
    assert sections_in("80C ₹1.5 lakh; 80CCD(1B); u/s 194A; 10(13A); 44ADA; FY 2025-26; 12 lakh") == \
        {"80C", "80CCD(1B)", "194A", "10(13A)", "44ADA"}


def test_numbers_in_structures_keep_rupee_amounts():
    from src.agents.verifier import numbers_in
    got = numbers_in(["Section 80C allows ₹1.5 lakh; standard deduction ₹75,000"])
    assert {150000, 75000} <= got and 975000 not in got


def test_verifier_rechecks_only_revised_texts_and_replaces_single_sentence(monkeypatch):
    from src.agents import verifier as V
    from src.tools.registry import TaskContext
    ctx = TaskContext()
    seen_bodies = []

    def chat(messages, **k):
        tool = k["tool_choice"]
        body = messages[-1]["content"] if isinstance(messages[-1], dict) else messages[-1].content
        if tool == "ClaimList":
            seen_bodies.append(body)
            if "[good]" in body:
                return _call("ClaimList", {"claims": [{"key": "good", "text": "Tax is ₹97,500.", "kind": "user figure"},
                                                      {"key": "bad", "text": "FD interest is tax-free.", "kind": "LAW"}]})
            return _call("ClaimList", {"claims": [{"key": "bad", "text": "FD interest is tax-free.", "kind": "law"}]})
        if tool == "Verdicts":
            ids = [int(line.split(".")[0]) for line in body.split("PASSAGES")[0].splitlines()[1:] if line[:1].isdigit()]
            return _call("Verdicts", {"verdicts": [{"claim_id": i, "verdict": "supported" if i == 1 and len(ids) == 2
                                                    else "contradicted"} for i in ids]})
        return _call("Revisions", {"texts": [{"key": "bad", "text": "FD interest is tax-free."}]})  # reviser fails
    monkeypatch.setattr(V.prov, "chat", chat)
    monkeypatch.setattr(V, "_evidence", lambda c, ctx, rc: {})
    out = V.verify({"good": "Tax is ₹97,500.", "bad": "FD interest is tax-free."}, {"tax": 97_500}, ctx)
    assert "[good]" in seen_bodies[0] and all("[good]" not in b for b in seen_bodies[1:])   # good text not re-checked
    assert out["texts"]["good"] == "Tax is ₹97,500."                                          # and left untouched
    assert "tax-free" not in out["texts"]["bad"] and V.REPLACEMENT in out["texts"]["bad"]


def test_facts_parser_uses_schema_of_asked_fields_only(monkeypatch):
    seen = {}

    def chat(messages, tools=None, **k):
        seen["fields"] = set(tools[0].model_fields)
        return _call("FactsAnswer", {"rent_monthly": 35000, "extra_nps_possible": "50000", "age": "None"})
    monkeypatch.setattr(G.prov, "chat", chat)
    out = G.parse_facts_answer({"text": "rent 35k, can add 50k NPS"}, ["rent_monthly", "extra_nps_possible", "age"],
                               G.register_task("y")[0])
    assert seen["fields"] == {"rent_monthly", "extra_nps_possible", "age"}
    assert out == {"rent_monthly": 35000, "extra_nps_possible": 50000}


def test_percentages_checked_against_evidence():
    from src.agents.verifier import percents_in
    assert percents_in("50% of gross receipts; 4 per cent cess; 12.5 percent") == {50.0, 4.0, 12.5}


def test_dependent_questions_asked_up_front():
    ctx = G.register_task("deps")[0]
    need = G.missing_facts({"facts": {}, "workflow": "tax_saving"}, ctx)
    assert {"rent_monthly", "basic_monthly", "hra_monthly", "metro_city", "parents_senior",
            "extra_80d_parents_possible"} <= set(need)
    need = G.missing_facts({"facts": {"rent_monthly": 0, "extra_80d_parents_possible": 0, "health_80d": 0},
                            "workflow": "tax_saving"}, ctx)
    assert not {"basic_monthly", "hra_monthly", "metro_city", "parents_senior"} & set(need)
