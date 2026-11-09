"""
Period extraction: which time period is the user asking about?

Tax rules change over time (Income-tax Act 1961 -> 2025 on 1 Apr 2026; GST 2.0 rates from
22 Sep 2025), so before retrieving we work out the date range of the question, e.g.
"FY 2024-25" -> 2024-04-01..2025-03-31, "AY 2025-26" -> the same FY, "August 2025" -> that
month, "before GST 2.0" -> 21 Sep 2025. If nothing is mentioned we assume "today" and flag
it (assumed_current=True) so the answer can say "assuming current law".
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date, timedelta

from src import config

TODAY = config.TODAY                     # configurable "today" (2026-10-29)
GST2_START = date(2025, 9, 22)           # GST 2.0 rates in force from this date
GST_START = date(2017, 7, 1)
NEW_ACT_START = date(2026, 4, 1)         # Income-tax Act, 2025 in force

MONTHS = {
    "jan": 1, "january": 1, "janvari": 1, "feb": 2, "february": 2, "farvari": 2,
    "mar": 3, "march": 3, "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6,
    "jul": 7, "july": 7, "julai": 7, "aug": 8, "august": 8, "agast": 8, "agust": 8,
    "sep": 9, "sept": 9, "september": 9, "sitambar": 9, "oct": 10, "october": 10,
    "aktubar": 10, "nov": 11, "november": 11, "navambar": 11, "dec": 12, "december": 12,
    "disambar": 12,
}
_MON = "|".join(sorted(MONTHS, key=len, reverse=True))


@dataclass
class Period:
    start: date
    end: date
    reason: str
    assumed_current: bool = False

    def to_dict(self) -> dict:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(),
                "reason": self.reason, "assumed_current": self.assumed_current}

    @property
    def label(self) -> str:
        """Short human label, e.g. 'FY 2024-25' or '2025-09-21'."""
        if self.start.month == 4 and self.start.day == 1 and self.end == date(self.start.year + 1, 3, 31):
            y = self.start.year
            prefix = "Tax Year" if self.start >= NEW_ACT_START else "FY"
            return f"{prefix} {y}-{str(y + 1)[2:]}"
        span = self.start.isoformat() if self.start == self.end else f"{self.start.isoformat()} to {self.end.isoformat()}"
        y = fy_start_year(self.start)
        if fy_start_year(self.end) == y:  # whole range inside one financial / tax year
            prefix = "Tax Year" if self.start >= NEW_ACT_START else "FY"
            span += f" ({prefix} {y}-{str(y + 1)[2:]})"
        return span


def fy_bounds(start_year: int) -> tuple[date, date]:
    """Indian financial / tax year starting 1 April of start_year."""
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def fy_start_year(d: date) -> int:
    """The financial year that contains date d (e.g. 2026-10-29 -> 2026, i.e. 2026-27)."""
    return d.year if d.month >= 4 else d.year - 1


def _year(y: str, base: int | None = None) -> int:
    """'24' -> 2024; '2025' -> 2025; for the 2nd half of a range use the first half's century."""
    v = int(y)
    if v < 100:
        v += (base // 100 * 100) if base else 2000
    return v


def _range_start(a: str, b: str) -> int | None:
    """Validate a 'YYYY-YY' style range; return the start year or None if inconsistent."""
    y1 = _year(a)
    y2 = _year(b, base=y1)
    return y1 if y2 == y1 + 1 else None


def _fy_label(y: int) -> str:
    return f"{y}-{str(y + 1)[2:]}"


def _parse_dmy(day: str, mon: str, year: str) -> date | None:
    try:
        return date(_year(year), MONTHS[mon.lower()], int(day))
    except (KeyError, ValueError):
        return None


def extract_period(text: str, today: date | None = None) -> Period:
    """Return the Period a question refers to (see module docstring)."""
    today = today or TODAY
    t = " " + text.lower().replace("–", "-").replace("—", "-") + " "
    cur_fy = fy_start_year(today)

    # ---- GST 2.0 / explicit "before/after <date>" -----------------------------------
    if re.search(r"\b(before|pre|prior to|earlier than|old)\s*-?\s*gst\s*2(\.0)?\b|gst\s*2(\.0)?\s*(se\s*)?(pehle|pahle|before)", t):
        d = GST2_START - timedelta(days=1)
        return Period(d, d, "before GST 2.0 (rates in force on 21 Sep 2025)")
    m = re.search(rf"\b(before|until|till|up to|upto|prior to)\s+(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})\b,?\s+(\d{{4}})", t)
    if m and (d := _parse_dmy(m.group(2), m.group(3), m.group(4))):
        d = d - timedelta(days=1)
        return Period(d, d, f"rules in force just before {m.group(2)} {m.group(3).title()} {m.group(4)}")
    m = re.search(rf"\b(after|from|since|w\.?e\.?f\.?)\s+(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})\b,?\s+(\d{{4}})", t)
    if m and (d := _parse_dmy(m.group(2), m.group(3), m.group(4))):
        start = d + timedelta(days=1) if m.group(1) == "after" else d
        return Period(start, max(start, today), f"from {start.isoformat()} onwards")
    if re.search(r"\b(after|post|since|under|new)\s*-?\s*gst\s*2(\.0)?\b|\bgst\s*2(\.0)?\b", t):
        return Period(GST2_START, today, "GST 2.0 rates (in force from 22 Sep 2025)")

    # ---- Assessment year: AY 2025-26 = income of FY 2024-25 ---------------------------
    m = re.search(r"\b(?:a\.?y\.?|assessment\s+year)\s*'?(\d{2,4})\s*[-/]\s*(\d{2,4})\b", t)
    if m and (y := _range_start(m.group(1), m.group(2))):
        s, e = fy_bounds(y - 1)
        return Period(s, e, f"AY {_fy_label(y)} = income of FY {_fy_label(y - 1)}")

    # ---- Tax year (2025 Act term) ----------------------------------------------------
    m = re.search(r"\btax\s*year\s*'?(\d{2,4})\s*[-/]\s*(\d{2,4})\b", t)
    if m and (y := _range_start(m.group(1), m.group(2))):
        s, e = fy_bounds(y)
        return Period(s, e, f"Tax Year {_fy_label(y)}")

    # ---- Financial year / previous year ---------------------------------------------
    m = re.search(r"\b(?:f\.?y\.?|financial\s+year|previous\s+year|fiscal(?:\s+year)?)\s*'?(\d{2,4})\s*[-/]\s*(\d{2,4})\b", t)
    if m and (y := _range_start(m.group(1), m.group(2))):
        s, e = fy_bounds(y)
        return Period(s, e, f"FY {_fy_label(y)}")
    m = re.search(r"\bf\.?y\.?\s*'?(\d{2}|\d{4})\b(?!\s*[-/]\s*\d)", t)
    if m:  # "FY25" / "FY 2025" = the year ENDING March 2025, i.e. FY 2024-25
        y = _year(m.group(1)) - 1
        s, e = fy_bounds(y)
        return Period(s, e, f"FY{m.group(1)} read as FY {_fy_label(y)} (year ending March {y + 1})")

    # ---- Budget / Finance Act YYYY -> changes apply from FY starting April YYYY ---------
    m = re.search(r"\b(?:budget|finance\s+act)\s*,?\s*(20\d{2})\b", t)
    if m:
        y = int(m.group(1))
        s, e = fy_bounds(y)
        return Period(s, e, f"Budget/Finance Act {y} applies to FY {_fy_label(y)}")

    # ---- specific day "15 August 2025" -----------------------------------------------
    m = re.search(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MON})\b,?\s+(20\d{{2}})\b", t)
    if m and (d := _parse_dmy(m.group(1), m.group(2), m.group(3))):
        return Period(d, d, f"on {d.isoformat()}")

    # ---- month + year "August 2025" / "Aug 2025" / "agast 2025" ----------------------
    m = re.search(rf"\b({_MON})\b\.?,?\s*'?(20\d{{2}}|\d{{2}})\b", t)
    if m and m.group(1) in MONTHS:
        y, mo = _year(m.group(2)), MONTHS[m.group(1)]
        last = calendar.monthrange(y, mo)[1]
        return Period(date(y, mo, 1), date(y, mo, last), f"{calendar.month_name[mo]} {y}")

    # ---- bare range "2024-25" (FY and Tax Year both run April-March) -------------------
    m = re.search(r"(?<![\d,.])(20\d{2})\s*[-/]\s*(\d{2}|20\d{2})(?![\d,])", t)
    if m and (y := _range_start(m.group(1), m.group(2))):
        s, e = fy_bounds(y)
        return Period(s, e, f"year {_fy_label(y)} (April {y} - March {y + 1})")

    # ---- relative expressions --------------------------------------------------------
    if re.search(r"\b(last|previous|pichle|pichhle|pichla|pichhla)\s+(financial\s+|tax\s+|fiscal\s+)?(year|saal|sal|fy)\b", t):
        s, e = fy_bounds(cur_fy - 1)
        return Period(s, e, f"last year = FY {_fy_label(cur_fy - 1)} (today is {today.isoformat()})")
    if re.search(r"\b(next|agle|agla)\s+(financial\s+|tax\s+)?(year|saal|sal)\b", t):
        s, e = fy_bounds(cur_fy + 1)
        return Period(s, e, f"next year = Tax Year {_fy_label(cur_fy + 1)}")
    if re.search(r"\b(this|current|is|iss|chalu)\s+(financial\s+|tax\s+|fiscal\s+)?(year|saal|sal|fy)\b", t):
        s, e = fy_bounds(cur_fy)
        return Period(s, e, f"this year = Tax Year {_fy_label(cur_fy)}")

    # ---- bare calendar year "in 2023" (not an amount) ---------------------------------
    m = re.search(r"(?<![\d,.₹$€£])\b(20[0-3]\d)\b(?![\d,]|\s*(?:rs|rupees|₹|lakh|lac|k\b|\$|€|£|usd|us\s*\$|dollars?|"
                  r"euros?|eur\b|pounds?|gbp|inr|per\s+(month|week|annum|year)|a\s+(month|week|year)|monthly|weekly|"
                  r"pm\b|p\.m\.|/\s*(month|week|mo\b)))", t)
    if m:
        y = int(m.group(1))
        return Period(date(y, 1, 1), date(y, 12, 31), f"calendar year {y}")

    if re.search(r"\b(now|currently|current|today|abhi|aaj|aajkal|latest|presently|at present)\b", t):
        return Period(today, today, f"current law (today {today.isoformat()})")

    return Period(today, today, f"no period mentioned - assuming current law (today {today.isoformat()})",
                  assumed_current=True)
