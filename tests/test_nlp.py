"""Tests for period extraction (dates.py), entities (entities.py) and Hinglish normalisation."""
from datetime import date

import pytest

from src.nlp.dates import extract_period
from src.nlp.entities import extract_age, extract_amounts, extract_sections
from src.nlp.hinglish import PHRASES, WORDS, detect_language, normalise

TODAY = date(2026, 10, 29)


@pytest.mark.parametrize("text,start,end", [
    ("slab rates for FY 2024-25", "2024-04-01", "2025-03-31"),
    ("FY24-25 new regime", "2024-04-01", "2025-03-31"),
    ("return for AY 2025-26", "2024-04-01", "2025-03-31"),        # AY = FY + 1
    ("assessment year 2026-27", "2025-04-01", "2026-03-31"),
    ("tax year 2026-27 slabs", "2026-04-01", "2027-03-31"),
    ("GST on cement in August 2025", "2025-08-01", "2025-08-31"),
    ("Aug 2025 rate", "2025-08-01", "2025-08-31"),
    ("agast 2025 mein GST", "2025-08-01", "2025-08-31"),
    ("rates in 2024-25", "2024-04-01", "2025-03-31"),
    ("rate before GST 2.0", "2025-09-21", "2025-09-21"),
    ("rate before 22 September 2025", "2025-09-21", "2025-09-21"),
    ("rate after GST 2.0", "2025-09-22", "2026-10-29"),
    ("tax last year", "2025-04-01", "2026-03-31"),
    ("pichle saal ka tax", "2025-04-01", "2026-03-31"),
    ("is saal ka slab", "2026-04-01", "2027-03-31"),
    ("this year slab", "2026-04-01", "2027-03-31"),
])
def test_periods(text, start, end):
    p = extract_period(text, today=TODAY)
    assert (p.start.isoformat(), p.end.isoformat()) == (start, end)
    assert p.assumed_current is False


def test_default_is_today_and_flagged():
    p = extract_period("what is the 80C limit?", today=TODAY)
    assert p.start == p.end == TODAY
    assert p.assumed_current is True


def test_now_is_explicit_current():
    p = extract_period("GST on cars abhi kitna hai", today=TODAY)
    assert p.start == TODAY and p.assumed_current is False


def test_amount_not_mistaken_for_year():
    p = extract_period("salary 2025000", today=TODAY)
    assert p.assumed_current is True


@pytest.mark.parametrize("text,expected", [
    ("limit of 80C", ["80C"]),
    ("section 80 D for parents", ["80D"]),
    ("NPS under 80CCD(1B)", ["80CCD(1B)"]),
    ("80ccd 1b", ["80CCD(1B)"]),
    ("u/s 44ADA presumptive", ["44ADA"]),
    ("sec 115BAC and 87A", ["115BAC", "87A"]),
    ("salary 12L and 12 lpa", []),
])
def test_sections(text, expected):
    assert extract_sections(text) == expected


@pytest.mark.parametrize("text,value", [
    ("12 lakh", 1_200_000), ("₹12,00,000", 1_200_000), ("12L", 1_200_000),
    ("1.5 lac", 150_000), ("1.2 crore", 12_000_000), ("50k", 50_000),
    ("12 lpa", 1_200_000), ("Rs. 75,000", 75_000), ("1500000", 1_500_000),
])
def test_amounts(text, value):
    a = extract_amounts(text)
    assert a and a[0]["value"] == value


def test_amounts_ignore_sections_and_years():
    assert extract_amounts("80C deduction in FY 2024-25") == []


def test_monthly_flag():
    assert extract_amounts("50k per month")[0]["per_month"] is True


def test_age():
    assert extract_age("I am 65 years old") == (65, "60to80")
    assert extract_age("my father is a senior citizen")[1] == "60to80"
    assert extract_age("super senior citizen")[1] == "above80"
    assert extract_age("salary 12 lakh") == (None, None)


def test_hinglish_detection():
    assert detect_language("mujhe kitna tax lagega?") == "hinglish"
    assert detect_language("What is the standard deduction?") == "en"


def test_hinglish_dictionary_size():
    assert len(WORDS) + len(PHRASES) >= 120


def test_hinglish_normalise():
    r = normalise("mujhe kitna tax lagega agar salary 12 lakh hai")
    assert r["language"] == "hinglish"
    n = r["normalised"].lower()
    assert "how much" in n and "if" in n and "12 lakh" in n
    assert ["kitna", "how much"] in r["replaced"]


def test_hinglish_phrase_before_words():
    r = normalise("ITR kab tak bharna hai")
    assert "deadline" in r["normalised"] and "file" in r["normalised"]


def test_english_unchanged():
    q = "Is HRA allowed for me in the new regime?"
    assert normalise(q)["normalised"] == q


def test_period_twin_swaps_in_current_version():
    from datetime import date
    from src.retrieval.date_filter import period_twins, rule_stem
    chunks = [{"id": "IT-NEW-REBATE-FY2526", "effective_from": "2025-04-01", "effective_to": "2026-03-31"},
              {"id": "IT-CESS", "effective_from": "2024-04-01", "effective_to": ""},
              {"id": "IT-NEW-REBATE-TY2627", "effective_from": "2026-04-01", "effective_to": ""}]
    assert rule_stem("GST-RATE-AC-PRE") == rule_stem("GST-RATE-AC-POST") == "GST-RATE-AC"
    order, swaps = period_twins(chunks, [0, 1], date(2026, 10, 29), date(2026, 10, 29))
    assert order == [2, 1] and swaps == {"IT-NEW-REBATE-FY2526": "IT-NEW-REBATE-TY2627"}


def test_period_twin_moves_up_lower_ranked_version():
    from datetime import date
    from src.retrieval.date_filter import period_twins
    chunks = [{"id": "GST-RATE-AC-PRE", "effective_from": "2017-07-01", "effective_to": "2025-09-21"},
              {"id": "IT-CESS", "effective_from": "2024-04-01", "effective_to": ""},
              {"id": "GST-RATE-AC-POST", "effective_from": "2025-09-22", "effective_to": ""}]
    order, _ = period_twins(chunks, [0, 1, 2], date(2026, 10, 29), date(2026, 10, 29))
    assert order == [2, 1]


def test_period_twin_by_topic_and_closest_fallback():
    from datetime import date
    from src.retrieval.date_filter import period_twins
    chunks = [{"id": "IT-NEW-DEFAULT-OPTOUT-1961", "topic": "regime_choice", "effective_from": "2024-04-01", "effective_to": "2026-03-31"},
              {"id": "IT-NEW-OPTOUT-TY2627", "topic": "regime_choice", "effective_from": "2026-04-01", "effective_to": ""},
              {"id": "IT-CESS", "topic": "cess", "effective_from": "2024-04-01", "effective_to": ""}]
    order, swaps = period_twins(chunks, [0, 2], date(2026, 10, 29), date(2026, 10, 29))
    assert order == [1, 2] and swaps["IT-NEW-DEFAULT-OPTOUT-1961"] == "IT-NEW-OPTOUT-TY2627"
    # FY 2023-24 is before our sources: keep the earliest version instead of returning nothing
    order, swaps = period_twins(chunks, [0, 1, 2], date(2023, 4, 1), date(2024, 3, 31))
    assert 0 in order and swaps["IT-NEW-DEFAULT-OPTOUT-1961"] == "kept-closest" and 1 not in order
