"""
Hand-worked calculator tests. Each test shows the arithmetic in comments so anyone can check
the expected number with a pen and paper. Amounts in rupees; L = lakh (1,00,000).
"""
import pytest

from src.calculator.tax import calculate, format_inr, slab_tax, NEW_2025
from src.calculator.parse import parse_calc_query
from src.nlp.dates import extract_period


def calc(**kw):
    base = {"tax_year": "2025-26", "age": "below60", "salaried": True}
    base.update(kw)
    return calculate(base)


# ---------------------------------------------------------------- new regime FY 2025-26
def test_new_2025_12L_is_zero():
    # gross 12,00,000 - std 75,000 = taxable 11,25,000
    # slabs: 4-8L @5% = 20,000; 8-11.25L @10% = 32,500 -> 52,500
    # taxable <= 12L -> rebate 87A = 52,500 (<= 60,000) -> tax 0, cess 0
    r = calc(gross_salary=1_200_000)["new"]
    assert r["taxable"] == 1_125_000
    assert r["slab_tax"] == 52_500
    assert r["rebate"] == 52_500
    assert r["total"] == 0


def test_new_2025_13L_marginal_relief():
    # gross 13,00,000 - 75,000 = taxable 12,25,000
    # slabs: 20,000 + 40,000 (8-12L @10%) + 3,750 (12-12.25L @15%) = 63,750
    # taxable > 12L, marginal relief: tax <= 12,25,000 - 12,00,000 = 25,000 -> relief 38,750
    # cess 4% of 25,000 = 1,000 -> total 26,000
    r = calc(gross_salary=1_300_000)["new"]
    assert r["slab_tax"] == 63_750
    assert r["rebate"] == 38_750
    assert r["cess"] == 1_000
    assert r["total"] == 26_000


def test_new_2026_27_20L_and_law_reference():
    # Tax Year 2026-27 uses the same slabs (Income-tax Act, 2025 s.202 / s.156)
    # taxable 20,00,000 - 75,000 = 19,25,000
    # 20,000 + 40,000 + 60,000 (12-16L @15%) + 65,000 (16-19.25L @20%) = 1,85,000
    # cess 7,400 -> 1,92,400
    res = calc(gross_salary=2_000_000, tax_year="2026-27")
    assert res["new"]["slab_tax"] == 185_000
    assert res["new"]["total"] == 192_400
    assert res["law"] == "Income-tax Act, 2025 s.202 / s.156"


def test_new_regime_employer_nps_allowed():
    # gross 13,00,000 - 75,000 - employer NPS 1,00,000 = 11,25,000 -> rebate -> 0
    r = calc(gross_salary=1_300_000, employer_nps=100_000)["new"]
    assert r["taxable"] == 1_125_000
    assert r["total"] == 0


def test_new_regime_ignores_80c():
    # 80C is not allowed in the new regime: taxable stays 11,25,000
    r = calc(gross_salary=1_200_000, deductions_80c=150_000)
    assert r["new"]["taxable"] == 1_125_000
    assert any("not allowed" in n for n in r["notes"])


# ---------------------------------------------------------------- old regime
def test_old_12L_with_80c():
    # gross 12,00,000 - std 50,000 - 80C 1,50,000 = taxable 10,00,000
    # 2.5-5L @5% = 12,500; 5-10L @20% = 1,00,000 -> 1,12,500; cess 4,500 -> 1,17,000
    r = calc(gross_salary=1_200_000, deductions_80c=150_000)["old"]
    assert r["taxable"] == 1_000_000
    assert r["slab_tax"] == 112_500
    assert r["cess"] == 4_500
    assert r["total"] == 117_000


def test_compare_12L_new_better():
    # new = 0 (see above), old = 1,17,000 -> new better, saving 1,17,000
    res = calc(gross_salary=1_200_000, deductions_80c=150_000)
    assert res["better"] == "new"
    assert res["saving"] == 117_000


def test_old_80d_cap_below60():
    # 80D entered 40,000 but capped at 25,000 (below 60)
    # taxable = 10,00,000 - 50,000 - 25,000 = 9,25,000
    # 12,500 + (9.25L-5L) 4,25,000 @20% = 85,000 -> 97,500; cess 3,900 -> 1,01,400
    r = calc(gross_salary=1_000_000, deductions_80d=40_000)["old"]
    assert r["taxable"] == 925_000
    assert r["total"] == 101_400


def test_old_senior_80d_50k_and_3L_exemption():
    # age 60-80: basic exemption 3L, 80D cap 50,000
    # taxable = 8,00,000 - 50,000 - 80C 1,50,000 - 80D 50,000 = 5,50,000
    # 3-5L @5% = 10,000; 5-5.5L @20% = 10,000 -> 20,000; no rebate (> 5L); cess 800 -> 20,800
    r = calc(gross_salary=800_000, deductions_80c=150_000, deductions_80d=60_000, age="60to80")["old"]
    assert r["taxable"] == 550_000
    assert r["slab_tax"] == 20_000
    assert r["total"] == 20_800


def test_old_senior_rebate_at_5L():
    # taxable = 7,00,000 - 50,000 - 1,50,000 = 5,00,000; senior slab tax 3-5L @5% = 10,000
    # taxable <= 5L -> rebate 87A 10,000 (<= 12,500) -> 0
    r = calc(gross_salary=700_000, deductions_80c=150_000, age="60to80")["old"]
    assert r["slab_tax"] == 10_000
    assert r["rebate"] == 10_000
    assert r["total"] == 0


def test_old_super_senior_5L_exemption():
    # above 80: nil up to 5L. taxable = 9,00,000 - 50,000 = 8,50,000
    # 5-8.5L @20% = 70,000; cess 2,800 -> 72,800
    r = calc(gross_salary=900_000, age="above80")["old"]
    assert r["taxable"] == 850_000
    assert r["total"] == 72_800


def test_old_hra_home_loan_cap():
    # taxable = 15L - 50k - HRA 2L - home loan 2L (2.5L capped) - 80C 1.5L = 9,00,000
    # 12,500 + 4L @20% = 80,000 -> 92,500; cess 3,700 -> 96,200
    r = calc(gross_salary=1_500_000, hra_exemption=200_000, home_loan_interest=250_000, deductions_80c=150_000)
    assert r["old"]["taxable"] == 900_000
    assert r["old"]["total"] == 96_200
    assert any("capped" in n for n in r["notes"])


# ---------------------------------------------------------------- FY 2024-25
def test_new_2024_rebate_at_7L():
    # gross 7,75,000 - 75,000 = 7,00,000; 3-7L @5% = 20,000; rebate 20,000 -> 0
    r = calc(gross_salary=775_000, tax_year="2024-25")["new"]
    assert r["taxable"] == 700_000
    assert r["total"] == 0


def test_new_2024_marginal_relief_just_above_7L():
    # taxable 7,10,000: 20,000 + 10,000 @10% = 21,000; excess over 7L = 10,000
    # tax limited to 10,000; cess 400 -> 10,400
    r = calc(gross_salary=785_000, tax_year="2024-25")["new"]
    assert r["slab_tax"] == 21_000
    assert r["rebate"] == 11_000
    assert r["total"] == 10_400


def test_new_2024_no_relief_when_tax_below_excess():
    # taxable 7,25,000: 20,000 + 2,500 = 22,500 < excess 25,000 -> no relief
    # cess 900 -> 23,400
    r = calc(gross_salary=800_000, tax_year="2024-25")["new"]
    assert r["rebate"] == 0
    assert r["total"] == 23_400


def test_new_2024_15L():
    # taxable 14,25,000: 20,000 + 30,000 + 30,000 + 2.25L @20% = 45,000 -> 1,25,000
    # cess 5,000 -> 1,30,000; law = 1961 Act
    res = calc(gross_salary=1_500_000, tax_year="2024-25")
    assert res["new"]["slab_tax"] == 125_000
    assert res["new"]["total"] == 130_000
    assert res["law"] == "Income-tax Act, 1961 s.115BAC / s.87A"


# ---------------------------------------------------------------- surcharge
def test_surcharge_10pct_60L():
    # taxable 60,00,000 (gross 60,75,000). Tax up to 24L = 3,00,000; 36L @30% = 10,80,000
    # slab tax 13,80,000; surcharge 10% = 1,38,000 (relief check: tax at 50L 10,80,000 + 10L
    # = 20,80,000 > 15,18,000, so no relief); cess 4% of 15,18,000 = 60,720 -> 15,78,720
    r = calc(gross_salary=6_075_000)["new"]
    assert r["slab_tax"] == 1_380_000
    assert r["surcharge"] == 138_000
    assert r["total"] == 1_578_720


def test_surcharge_marginal_relief_just_above_50L():
    # taxable 50,10,000: slab tax 10,80,000 + 10,000 @30% = 10,83,000
    # 10% surcharge would be 1,08,300 -> 11,91,300, but cap = tax at 50L (10,80,000) + 10,000
    # = 10,90,000 -> surcharge 7,000; cess 4% of 10,90,000 = 43,600 -> 11,33,600
    r = calc(gross_salary=5_085_000)["new"]
    assert r["slab_tax"] == 1_083_000
    assert r["surcharge"] == 7_000
    assert r["total"] == 1_133_600


def test_surcharge_cap_25_new_vs_37_old():
    # taxable 6 crore. New: slab 3,00,000 + 5.76Cr @30% = 1,75,80,000; surcharge capped 25% = 43,95,000
    # Old: 12,500 + 1,00,000 + 5.9Cr @30% = 1,78,12,500; surcharge 37% = 65,90,625
    res = calc(gross_salary=60_075_000)
    assert res["new"]["taxable"] == 60_000_000
    assert res["new"]["surcharge"] == 4_395_000
    res_old = calc(gross_salary=60_050_000)
    assert res_old["old"]["taxable"] == 60_000_000
    assert res_old["old"]["surcharge"] == 6_590_625


# ---------------------------------------------------------------- misc
def test_not_salaried_no_std_deduction():
    r = calc(gross_salary=1_200_000, salaried=False)["new"]
    assert r["std_deduction"] == 0
    assert r["taxable"] == 1_200_000


def test_slab_breakdown_rows():
    tax, rows = slab_tax(1_225_000, NEW_2025["slabs"])
    assert tax == 63_750
    assert [r["rate"] for r in rows] == [0, 5, 10, 15]


def test_format_inr():
    assert format_inr(1225000) == "₹12,25,000"
    assert format_inr(26000) == "₹26,000"
    assert format_inr(999) == "₹999"
    assert format_inr(60075000) == "₹6,00,75,000"


def test_bad_inputs():
    with pytest.raises(ValueError):
        calculate({"gross_salary": 100, "tax_year": "2019-20"})
    with pytest.raises(ValueError):
        calculate({"gross_salary": -5})


# ---------------------------------------------------------------- query parsing
def test_parse_salary_and_deductions():
    q = "My salary is 18 lakh, 80C 1.5L and health insurance 30k for FY 2025-26, which regime is better?"
    p = parse_calc_query(q, extract_period(q))
    assert p["inputs"]["gross_salary"] == 1_800_000
    assert p["inputs"]["deductions_80c"] == 150_000
    assert p["inputs"]["deductions_80d"] == 30_000
    assert p["inputs"]["tax_year"] == "2025-26"


def test_parse_monthly_and_senior():
    q = "I am 65 years old and get 1 lakh per month salary"
    p = parse_calc_query(q, extract_period(q))
    assert p["inputs"]["gross_salary"] == 1_200_000
    assert p["inputs"]["age"] == "60to80"
    assert p["inputs"]["tax_year"] == "2026-27"  # no period -> current tax year


def test_parse_missing_salary_follow_up():
    p = parse_calc_query("Which regime is better for me?", None)
    assert p["inputs"] is None
    assert "salary" in p["follow_up"].lower()


def test_parse_hinglish_last_year():
    q = "pichle saal meri salary 13 lakh thi, tax kitna tha"
    p = parse_calc_query(q, extract_period(q))
    assert p["inputs"]["gross_salary"] == 1_300_000
    assert p["inputs"]["tax_year"] == "2025-26"


def test_parse_keyword_in_same_clause():
    # "₹25,000" belongs to "health insurance" (after it), not to "PPF" (before the "and")
    q = "FY 2024-25 salary ₹10 lakh; I invested ₹1.5 lakh in PPF and paid ₹25,000 health insurance"
    p = parse_calc_query(q, extract_period(q))
    assert p["inputs"]["deductions_80c"] == 150_000
    assert p["inputs"]["deductions_80d"] == 25_000


def test_parse_parent_age_in_brackets():
    q = "My father (65) gets a pension of ₹9 lakh"
    p = parse_calc_query(q, extract_period(q))
    assert p["inputs"]["age"] == "60to80" and p["inputs"]["gross_salary"] == 900_000
