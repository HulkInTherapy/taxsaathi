"""Document pipeline without an LLM: hidden-text and injection detection, masking, validation,
cross-checks (on the generator's true figures) and the agent loop with a scripted fake model."""
import json
import re

import pytest
from langchain_core.messages import AIMessage

from scripts import synth_documents as sd
from src.documents import extract as ex
from src.documents.crosscheck import cross_check
from src.llm.masking import Masker
from src.tools.registry import TaskContext, ToolBox


def _persona(pid):
    return next(p for p in sd.load_personas() if p["id"] == pid)


def _render(pid, tmp_path, monkeypatch):
    monkeypatch.setattr(sd, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(sd.config, "ROOT", tmp_path)
    gt = sd.generate([pid])[0]
    return {d["file"].rsplit("/", 1)[-1]: (tmp_path / d["file"]).read_bytes() for d in gt["documents"]}, gt


# ------------------------------------------------------------------ reading + injections
def test_hidden_text_separated(tmp_path, monkeypatch):
    docs, _ = _render("P18", tmp_path, monkeypatch)
    r = ex.read_pdf(docs["form16_orchid_analytics_llp.pdf"])
    assert "SYSTEM OVERRIDE" not in r.text and any("SYSTEM OVERRIDE" in h for h in r.hidden)
    assert "FORM NO. 16" in r.text and r.pages == 2


def test_visible_injection_found_and_redacted(tmp_path, monkeypatch):
    docs, _ = _render("P17", tmp_path, monkeypatch)
    r = ex.read_pdf(docs["interest_certificate_kaveri_bank_ltd.pdf"])
    hits = ex.find_instructions(r.text)
    assert hits
    red = ex.redact(r.text, hits)
    assert "ignore all previous" not in red.lower() and "tell the user" not in red.lower()
    assert "Fixed deposit" in red  # data is kept


def test_no_false_injection_on_clean_documents(tmp_path, monkeypatch):
    docs, _ = _render("P23", tmp_path, monkeypatch)
    for data in docs.values():
        r = ex.read_pdf(data)
        assert ex.find_instructions(r.text) == [] and r.hidden == []


def test_personal_data_masked_before_llm(tmp_path, monkeypatch):
    docs, gt = _render("P03", tmp_path, monkeypatch)
    m = Masker()
    for data in docs.values():
        text = ex.read_pdf(data).text
        ex.register_personal_data(text, m)
        masked = m.mask(text)
        assert gt["name"] not in masked and gt["pan"] not in masked
        assert not ex.ACCOUNT_NUMBER_RE.search(masked)
        assert re.search(r"\d{2,3},\d{3}", masked)  # amounts survive masking


# ------------------------------------------------------------------ validation
def test_validate_form16_chain():
    f = {"part_a_quarters": [{"quarter": "Q1", "tds": 100}, {"quarter": "Q2", "tds": 100}], "part_a_total_tds": 200,
         "gross_salary": 1_000_000, "hra_exemption": 0, "standard_deduction": 75_000, "home_loan_interest": 0,
         "income_chargeable_salaries": 925_000, "other_income_reported": 0, "gross_total_income": 925_000,
         "chapter_via": [], "total_chapter_via": 0, "total_taxable_income": 925_000}
    assert ex.validate("form16", f) == []
    f["income_chargeable_salaries"] = 952_000  # transposed digits
    assert any("Salaries" in i for i in ex.validate("form16", f))


def test_validate_interest_totals():
    f = {"accounts": [{"account_type": "savings", "interest": 5000, "tds": 0},
                      {"account_type": "fixed_deposit", "interest": 60000, "tds": 6000}],
         "total_interest": 65000, "total_tds": 6000}
    assert ex.validate("interest_certificate", f) == []
    f["total_interest"] = 56000
    assert ex.validate("interest_certificate", f)


# ------------------------------------------------------------------ cross-checks on true figures
def _docs_from_truth(pid):
    """Build 'extracted' documents from the generator's true figures (a perfect extractor)."""
    m = sd.build(_persona(pid))
    docs = []
    for e in m["employers"]:
        c = e["calc"]
        via = [{"section": "80C", "deductible_amount": e["shown_80c"]}] if e["regime"] == "old" else []
        docs.append({"document_id": f"f16_{e['name']}", "type": "form16", "filename": "f16", "injections": [],
                     "fields": {"employer_name": e["name"], "employer_tan": e["tan"], "employee_pan": m["pan"],
                                "gross_salary": e["annual_gross"], "standard_deduction": c["std_deduction"],
                                "other_income_reported": e["declared_interest"], "part_a_total_tds": e["tds_part_a"],
                                "tds_part_b": e["tds_part_b"], "chapter_via": via, "new_regime": e["regime"] == "new"}})
        if m["p"]["slips"] and not e["pension"]:
            bonus = 0 if "slips_total_mismatch" in m["planted"] else e["bonus"]
            months = [{"month": str(k), "gross_earnings": e["monthly"]["gross"] + (bonus if k == e["months"] - 1 else 0)}
                      for k in range(e["months"])]
            docs.append({"document_id": f"slip_{e['name']}", "type": "salary_slip", "filename": "s", "injections": [],
                         "fields": {"employer_name": e["name"], "employee_pan": m["pan"], "months": months}})
    for i, b in enumerate(m["interest"]):
        pan = sd.mutate_pan(m["pan"]) if ("pan_mismatch" in m["planted"] and i == 0) else m["pan"]
        accts = ([{"account_type": "savings", "interest": b["savings"], "tds": 0}] if b["savings"] else []) + \
                ([{"account_type": "fixed_deposit", "interest": b["fd"], "tds": b["tds"]}] if b["fd"] else [])
        docs.append({"document_id": f"int_{i}", "type": "interest_certificate", "filename": f"int_{i}", "injections": [],
                     "fields": {"bank_name": b["bank"], "customer_pan": pan, "accounts": accts,
                                "total_interest": b["savings"] + b["fd"], "total_tds": b["tds"]}})
    return docs


@pytest.mark.parametrize("pid", [f"P{i:02d}" for i in range(1, 41)])
def test_cross_check_matches_ground_truth(pid):
    gt = sd.ground_truth(sd.build(_persona(pid)))
    want = {f["code"] for f in gt["expected"]["findings"]}
    got = {f["code"] for f in cross_check(_docs_from_truth(pid))["findings"]}
    assert got == want, pid


def test_cross_check_amounts():
    out = cross_check(_docs_from_truth("P03"))
    f = next(x for x in out["findings"] if x["code"] == "interest_not_in_form16")
    assert f["amount"] == 9_100 + 142_000 and "₹1,51,100" in f["message"]
    assert out["totals"]["tds_interest"] == 14_200


# ------------------------------------------------------------------ agent loop with a scripted model
def test_document_agent_loop_with_fake_model(monkeypatch):
    from src.agents import document_agent as da
    from src.agents import loop
    ctx = TaskContext(extract_fields=False)
    doc_id = ctx.documents.add("a.pdf", b"%PDF-fake")
    ctx.extracted[doc_id] = {"type": "form16", "filename": "a.pdf", "injections": [], "warnings": [],
                             "fields": {"employer_name": "X", "employee_pan": "ABCPX1234Y", "gross_salary": 10,
                                        "other_income_reported": 0, "part_a_total_tds": 5, "tds_part_b": 9}}
    script = iter([
        AIMessage(content="", tool_calls=[{"name": "cross_check_documents", "args": {}, "id": "1"}]),
        AIMessage(content="Here is my answer in prose."),  # gets nudged
        AIMessage(content="", tool_calls=[{"name": "DocumentReport", "id": "2", "args": {
            "summary": "ok", "findings": []}}]),
    ])
    monkeypatch.setattr(loop.prov, "chat", lambda *a, **k: next(script))
    out = da.run_document_agent(ctx)
    assert [s["type"] for s in out["agent"]["steps"]] == ["tool", "text", "final"]
    # the agent reported nothing, but the deterministic Part A/B mismatch is still delivered
    assert out["agent"]["missed_findings"] == ["form16_tds_inconsistent"]
    assert out["report"]["findings"][0]["code"] == "form16_tds_inconsistent" and not out["report"]["all_clear"]


def test_masker_literals_respect_word_boundaries():
    m = Masker()
    m.add("123456789", "ACCOUNT")
    assert m.mask("acct 123456789 and 1234567890") == "acct <ACCOUNT_1> and 1234567890"


def test_invented_findings_never_reach_the_user(monkeypatch):
    from src.agents import document_agent as da
    from src.agents import loop
    ctx = TaskContext(extract_fields=False)
    doc_id = ctx.documents.add("a.pdf", b"%PDF-fake")
    ctx.extracted[doc_id] = {"type": "form16", "filename": "a.pdf", "injections": [], "warnings": [],
                             "fields": {"employer_name": "X", "employee_pan": "ABCPX1234Y", "gross_salary": 10,
                                        "other_income_reported": 0, "part_a_total_tds": 9, "tds_part_b": 9}}
    script = iter([
        AIMessage(content="", tool_calls=[{"name": "cross_check_documents", "args": {}, "id": "1"}]),
        AIMessage(content="", tool_calls=[{"name": "DocumentReport", "id": "2", "args": {"summary": "x", "findings": [
            {"code": "itr1_not_eligible", "title": "t", "explanation": "e", "action": "a"}]}}]),
    ])
    monkeypatch.setattr(loop.prov, "chat", lambda *a, **k: next(script))
    out = da.run_document_agent(ctx)
    assert out["report"]["findings"] == [] and out["agent"]["invented_findings"] == ["itr1_not_eligible"]
