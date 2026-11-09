"""
Entity recognition with regular expressions: section numbers, money amounts and age.

Section numbers ("80C", "u/s 44ADA", "80CCD(1B)") let us pull in the old-to-new section
mapping chunks, because the 2025 Act renumbered everything. Money amounts ("12 lakh",
"₹12,00,000", "1.2 crore", "50k", "12 LPA") are converted to plain rupees for the tax
calculator. Age hints ("I am 65", "senior citizen") choose the right old-regime exemption.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------- section numbers
# Suffixes that make "12L"/"50K" amounts, not sections.
_AMOUNT_SUFFIXES = {"L", "K", "CR", "LPA", "LAC", "LACS", "LAKH", "LAKHS", "CRORE", "CRORES",
                    "PM", "AM", "TH", "ST", "ND", "RD", "GB", "MB", "KG", "X", "M", "LA", "LK"}
_SEC_BODY = r"(\d{1,3})\s?([A-Za-z]{0,5})((?:\s?\(\s?[0-9A-Za-z]{1,4}\s?\))*)"
# With an explicit keyword: "section 80 D", "sec. 194J", "u/s 44ADA", "s.115BAC", "dhara 80C"
SECTION_KW_RE = re.compile(r"\b(?:sections?|secs?\.?|s\.|u/s\.?|us|dhara)\s*" + _SEC_BODY, re.IGNORECASE)
# Bare: "80C", "80ccd(1b)", "87A", "115BAC", "44ADA" (needs ≥2 digits and ≥1 letter)
SECTION_BARE_RE = re.compile(r"(?<![\w₹.,(])(\d{2,3})([A-Za-z]{1,5})((?:\(\s?[0-9A-Za-z]{1,4}\s?\))*)(?![\w])")
# Spaced 80-series: "80 C", "80 CCD 1B"
# "80CCD 1B", "80ccd(2)", "80 CCD (1B)" -> 80CCD(1B) / 80CCD(2)
SECTION_80CCD_RE = re.compile(r"\b80\s?ccd\s*\(?\s*(1b|2|1)\b\s*\)?", re.IGNORECASE)
SECTION_80_RE = re.compile(r"\b(80)\s+([A-Za-z]{1,4})\b(?:\s?\(?\s?(1B|2|1)\s?\)?)?", re.IGNORECASE)


def _norm_section(num: str, letters: str, brackets: str) -> str:
    sub = re.sub(r"\s", "", brackets or "").upper()
    sec = f"{num}{letters.upper()}{sub}"
    sec = re.sub(r"^80CCD1B$", "80CCD(1B)", sec)
    return sec


def extract_sections(text: str) -> list[str]:
    """Return normalised section numbers in order of appearance, without duplicates."""
    found: list[tuple[int, str]] = []
    for m in SECTION_KW_RE.finditer(text):
        found.append((m.start(), _norm_section(m.group(1), m.group(2), m.group(3))))
    for m in SECTION_BARE_RE.finditer(text):
        if m.group(2).upper() in _AMOUNT_SUFFIXES:
            continue
        found.append((m.start(), _norm_section(m.group(1), m.group(2), m.group(3))))
    for m in SECTION_80_RE.finditer(text):
        if m.group(2).upper() in _AMOUNT_SUFFIXES:
            continue
        sub = f"({m.group(3).upper()})" if m.group(3) else ""
        found.append((m.start(), _norm_section("80", m.group(2), sub)))
    for m in SECTION_80CCD_RE.finditer(text):
        found.append((m.start(), f"80CCD({m.group(1).upper()})"))
    specific = {sec for _, sec in found}
    out: list[str] = []
    for _, sec in sorted(found):
        # drop a bare "80CCD" when the more specific "80CCD(1B)" was also found
        if sec == "80CCD" and any(s.startswith("80CCD(") for s in specific):
            continue
        if sec not in out:
            out.append(sec)
    return out


# ---------------------------------------------------------------- money amounts
# Foreign-currency amounts are converted to rupees with these reference rates (₹ per 1 unit).
# Source: FBIL reference rates as published on the RBI website for 28 October 2026
# (https://www.fbil.org.in/ ; cross-checked via https://lawnut.com/usd-inr-reference-rate-today
# and the PTI/ET rupee close of ₹95.22 per US$ on 28 Oct 2026). Update FX_AS_OF with the table.
# For the tax return itself, Rule 115 of the Income-tax Rules prescribes the SBI TT buying rate.
FX_RATES_INR = {"USD": 95.2278, "EUR": 105.8641, "GBP": 126.4657}
FX_AS_OF = "28 Oct 2026"
FX_SOURCE = "RBI/FBIL reference rate"
FX_SOURCE_URL = "https://www.fbil.org.in/"
FX_SYMBOL = {"USD": "US$", "EUR": "€", "GBP": "£"}

_MULT = {
    "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "lacs": 100_000, "l": 100_000,
    "lpa": 100_000, "lakh/year": 100_000,
    "crore": 10_000_000, "crores": 10_000_000, "cr": 10_000_000, "karod": 10_000_000, "karor": 10_000_000,
    "k": 1_000, "thousand": 1_000, "hazaar": 1_000, "hazar": 1_000,
    "million": 1_000_000, "mn": 1_000_000,
}
_NUM = r"\d+(?:,\d+)*(?:\.\d+)?"
_UNIT = r"(lakhs?|lacs?|lpa|l|crores?|cr|karod|karor|k|thousand|hazaa?r|million|mn)\b"
# Currency written before the number: "₹", "Rs.", "$", "US$", "USD", "€", "EUR", "£", "GBP"
_CUR_PRE = r"(?:₹|rs\.?|inr|rupees?|us\s?\$|\$|usd|€|eur|euros?|£|gbp)\s*"
# Currency written after the number/unit: "5k us dollars", "3000 USD", "4000 euros", "2,500 pounds"
_CUR_POST = (r"\s*(?:us\s*dollars?|american\s*dollars?|dollars?|usd|\$|euros?|eur|€|"
             r"(?:british\s*)?pounds?(?:\s*sterling)?|gbp|£|rupees?|rs\.?|inr)(?![a-z])")
_PER_MONTH = (r"per\s+month|per\s+mo\b|/\s*month|/\s*mo\b|/\s*m\b|a\s+month|each\s+month|every\s+month|"
              r"in\s+a\s+month|monthly|p\.?\s?m\.?(?![a-z])|mahina|mahine|mahiney|month\b")
_PER_WEEK = r"per\s+week|/\s*week|/\s*wk\b|a\s+week|each\s+week|every\s+week|weekly|hafta|hafte"
_PER_YEAR = (r"per\s+annum|per\s+year|/\s*year|/\s*yr\b|a\s+year|each\s+year|every\s+year|yearly|annually|"
             r"p\.?\s?a\.?(?![a-z])|saal(?:ana)?\b|year\b")
AMOUNT_RE = re.compile(
    rf"(?P<cur>{_CUR_PRE})?(?P<num>{_NUM})\s*(?P<unit>{_UNIT})?(?P<cur2>{_CUR_POST})?"
    rf"(?P<per>\s*(?:(?P<pm>{_PER_MONTH})|(?P<pw>{_PER_WEEK})|(?P<py>{_PER_YEAR})))?",
    re.IGNORECASE)
# "monthly salary 80k", "mahine ka 40 hazaar": the period word comes before the amount.
_PERIOD_BEFORE_MONTH = re.compile(r"\b(monthly|per\s+month|a\s+month|every\s+month|mahine|mahina|month(?:'s)?)\b[^,;.]{0,25}$", re.I)
_PERIOD_BEFORE_WEEK = re.compile(r"\b(weekly|per\s+week|every\s+week)\b[^,;.]{0,25}$", re.I)


def _currency(pre: str | None, post: str | None) -> str | None:
    """ISO code of the currency written next to the amount (None = not stated)."""
    t = f"{pre or ''} {post or ''}".lower()
    if not t.strip():
        return None
    if re.search(r"\$|dollar|usd", t):
        return "USD"
    if re.search(r"€|euro|eur", t):
        return "EUR"
    if re.search(r"£|pound|gbp", t):
        return "GBP"
    return "INR"


def extract_amounts(text: str) -> list[dict]:
    """Find money amounts. Each item: {"text","value" (rupees per year/as stated, int),
    "per_month","period" (month|week|year|None),"currency","foreign_value","fx_rate","start","end"}.

    A bare number counts as money only if it has a currency sign, a unit (lakh/k/crore) or
    is a large number (≥ 10,000, or written with Indian commas) — so "80C" or "age 65" are ignored.
    `value` is always in rupees (foreign currency converted with FX_RATES_INR) but NOT annualised:
    the parser multiplies by 12 / 52 using `period`.
    """
    out = []
    for m in AMOUNT_RE.finditer(text):
        num_s, unit = m.group("num"), (m.group("unit") or "").lower()
        cur = _currency(m.group("cur"), m.group("cur2"))
        # skip things glued to letters, e.g. the "80" in "80C" or "2" in "GST2"
        if m.start("num") > 0 and text[m.start("num") - 1].isalpha() and not m.group("cur"):
            continue
        after = text[m.end("num"):m.end("num") + 1]
        if not unit and not m.group("cur2") and after.isalpha():
            continue
        try:
            num = float(num_s.replace(",", ""))
        except ValueError:
            continue
        if unit:
            value = num * _MULT[unit]
        elif cur or num >= 10_000 or ("," in num_s and num >= 1_000):
            value = num
        else:
            continue
        # A 4-digit year like 2025 without currency is not money.
        if not cur and not unit and re.fullmatch(r"(19|20)\d{2}", num_s):
            continue
        # Part of a year range like 2024-25
        if not cur and not unit and re.match(r"\s*-\s*\d{2}", text[m.end("num"):]):
            continue
        period = "month" if m.group("pm") else "week" if m.group("pw") else "year" if m.group("py") else None
        if unit == "lpa":
            period = "year"
        if period is None:
            before = text[max(0, m.start() - 40):m.start()]
            if _PERIOD_BEFORE_MONTH.search(before):
                period = "month"
            elif _PERIOD_BEFORE_WEEK.search(before):
                period = "week"
        item = {"text": m.group(0).strip(), "value": int(round(value)), "per_month": period == "month",
                "period": period, "currency": cur or "INR", "foreign_value": None, "fx_rate": None,
                "start": m.start(), "end": m.end()}
        if cur in FX_RATES_INR:
            item.update(foreign_value=value, fx_rate=FX_RATES_INR[cur], value=int(round(value * FX_RATES_INR[cur])))
        out.append(item)
    return out


# ---------------------------------------------------------------- age
AGE_RES = [
    re.compile(r"\b(?:age|aged|umar|umr|umra)\s*(?:is|of|:|hai)?\s*(\d{2,3})\b", re.IGNORECASE),
    re.compile(r"\b(\d{2,3})\s*(?:years?|yrs?|y/o|yo|saal|sal|varsh)\s*(?:old|ka|ki|ke|age|umar)\b", re.IGNORECASE),
    re.compile(r"\bi\s*(?:am|'m)\s*(\d{2,3})\b", re.IGNORECASE),
    # "my dad is 65", "mother aged 72", "papa ki umar 68"
    re.compile(r"\b(?:father|mother|dad|papa|mummy|mom|mum|wife|husband|grandfather|grandmother|grandpa|grandma)\s*(?:is|aged|,)?\s*(?:ki\s+umr?a?\s+)?(\d{2,3})\b(?!\s*(?:k|l|lakh|lac|cr|thousand|%))", re.IGNORECASE),
    # "65 year old dad"
    re.compile(r"\b(\d{2,3})[\s-]*(?:years?|yrs?)[\s-]*old\b", re.IGNORECASE),
    # "my father (65)", "mother, 72,"
    re.compile(r"\b(?:i|me|father|mother|dad|papa|mummy|mom|mum|parent|wife|husband|grandfather|grandmother)\s*[(,]\s*(\d{2,3})\s*[),]", re.IGNORECASE),
]


def age_category(age: int | None) -> str | None:
    if age is None:
        return None
    return "below60" if age < 60 else ("60to80" if age < 80 else "above80")


def extract_age(text: str) -> tuple[int | None, str | None]:
    """Return (age, category) where category is below60 | 60to80 | above80 | None."""
    low = text.lower()
    for rx in AGE_RES:
        m = rx.search(text)
        if m and 10 <= int(m.group(1)) <= 120:
            age = int(m.group(1))
            return age, age_category(age)
    if re.search(r"super\s*senior|very\s*senior|above\s*80|over\s*80|80\s*\+", low):
        return None, "above80"
    if re.search(r"senior\s*citizen|sr\.?\s*citizen|retired|pensioner|buzurg|varishth", low):
        return None, "60to80"
    return None, None


def extract_entities(text: str) -> dict:
    """Run all recognisers. Used by the pipeline (trace step "entities") and the calculator parser."""
    age, cat = extract_age(text)
    return {"sections": extract_sections(text), "amounts": extract_amounts(text),
            "age": age, "age_category": cat}
