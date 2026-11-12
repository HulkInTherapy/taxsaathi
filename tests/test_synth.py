"""Synthetic data generator: every planted problem has a finding, ground truth is consistent and
deterministic, documents render with the right type and the injections are extractable."""
import json

import pytest

from scripts import synth_documents as sd
from src.tools.parse_document import detect_type, extract_text


@pytest.fixture(scope="module")
def truths():
    return {p["id"]: sd.ground_truth(sd.build(p)) for p in sd.load_personas()}


def test_forty_personas_with_unique_ids(truths):
    assert len(truths) == 40


def test_deterministic():
    p = next(x for x in sd.load_personas() if x["id"] == "P23")
    a, b = sd.ground_truth(sd.build(p)), sd.ground_truth(sd.build(p))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_planted_problems_have_findings(truths):
    plants = {p["id"]: set(p["planted"]) for p in sd.load_personas()}
    for pid, gt in truths.items():
        codes = {f["code"] for f in gt["expected"]["findings"]}
        inj = {f"injection_{i['mode']}" for i in gt["expected"]["injections"]}
        assert plants[pid] <= codes | inj, pid


def test_clean_personas_have_no_findings(truths):
    for pid in ("P06", "P07", "P08"):
        assert truths[pid]["expected"]["findings"] == [], pid


def test_balance_and_escalation_consistency(truths):
    for pid, gt in truths.items():
        e = gt["expected"]
        if e["tax"] is None:
            assert e["escalate"] and "presumptive_limit_exceeded" in e["escalation_reasons"]
        else:
            assert e["balance_after_tds"] == e["tax"]["best_total"] - e["tds_credited"]
    assert truths["P35"]["expected"]["escalate"] and truths["P35"]["expected"]["itr_form"] == "ITR-2"
    assert not truths["P28"]["expected"]["escalate"] and truths["P28"]["expected"]["itr_form"] == "ITR-1"
    assert truths["P27"]["expected"]["gst_registration_required"] is True
    assert truths["P26"]["expected"]["gst_registration_required"] is False


def test_regime_mix_and_optimiser_flips(truths):
    regimes = {pid: gt["expected"]["tax"]["best_regime"] for pid, gt in truths.items() if gt["expected"]["tax"]}
    assert {"P12", "P22", "P34"} <= {k for k, v in regimes.items() if v == "old"}
    ts = truths["P29"]["expected"]["tax_saving"]
    assert ts["best_option"] == "all of the above" and ts["max_saving"] > 0
    assert truths["P30"]["expected"]["tax_saving"]["best_option"] is None


def test_interest_tds_thresholds():
    p05 = sd.build(next(x for x in sd.load_personas() if x["id"] == "P05"))  # senior, FD 1.85L > 1L
    assert p05["interest"][0]["tds"] == 18_500
    p04 = sd.build(next(x for x in sd.load_personas() if x["id"] == "P04"))  # 46k and 44k, both under 50k
    assert all(b["tds"] == 0 for b in p04["interest"])


def test_render_types_and_injection(tmp_path, monkeypatch):
    monkeypatch.setattr(sd, "DOCS_DIR", tmp_path / "docs")
    monkeypatch.setattr(sd.config, "ROOT", tmp_path)
    rows = sd.generate(["P18", "P20", "P23"])
    seen_injection = set()
    for gt in rows:
        for d in gt["documents"]:
            text = "\n".join(extract_text((tmp_path / d["file"]).read_bytes()))
            assert detect_type(text) == d["type"], d
            if "SYSTEM OVERRIDE" in text:
                seen_injection.add(gt["persona_id"])
    assert seen_injection == {"P18", "P20"}
    assert len(rows[2]["documents"]) == 3  # two Form 16s + one interest certificate
