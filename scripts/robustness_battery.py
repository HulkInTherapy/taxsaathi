"""
Robustness battery: the 80 real questions (data/eval/real_questions.jsonl) plus hand-written
tricky ones (foreign currency, per-month pay, Hinglish, typos, freelancers, seniors).

For each question we run the full pipeline with the LLM switched off (fast; generation falls
back to the deterministic answer) and check intent, parsed calculator inputs and refusal.

    python -m scripts.robustness_battery --out /tmp/battery.json [--llm-ids T01,T05]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from src import config
from src.pipeline import TaxSaathi

# expect: intent, gross (annual ₹, ±2%), income_type, age, follow_up, escalate, refused
TRICKY = [
    ("T01", "how much tax do i have to pay if i am earning 5k us dollars per month remote",
     {"intent": "calculation", "gross": 5000 * 12 * 95.2278, "income_type": "professional_presumptive"}),
    ("T02", "I make 80k a month, how much tax?", {"intent": "calculation", "gross": 960_000, "income_type": "salary"}),
    ("T03", "CTC 18 LPA, which regime is better?", {"intent": "calculation", "gross": 1_800_000, "income_type": "salary"}),
    ("T04", "my dad is 65 and gets 6 lakh pension, how much tax will he pay?",
     {"intent": "calculation", "gross": 600_000, "income_type": "salary", "age": "60to80"}),
    ("T05", "freelance designer earning 2 lakh per month, how much tax",
     {"intent": "calculation", "gross": 2_400_000, "income_type": "professional_presumptive"}),
    ("T06", "YouTube income 30 lakh, how much tax do I pay?",
     {"intent": "calculation", "gross": 3_000_000, "income_type": "professional_presumptive"}),
    ("T07", "meri salary 1 lakh mahina hai kitna tax lagega", {"intent": "calculation", "gross": 1_200_000, "income_type": "salary"}),
    ("T08", "I earn $3000 per month from a US client as a software consultant, tax?",
     {"intent": "calculation", "gross": 3000 * 12 * 95.2278, "income_type": "professional_presumptive"}),
    ("T09", "salary 50k per month how much tax", {"intent": "calculation", "gross": 600_000, "income_type": "salary"}),
    ("T10", "I get 1.2L monthly salary, tax in new regime?", {"intent": "calculation", "gross": 1_440_000, "income_type": "salary"}),
    ("T11", "earning 12 lakh per annum, tax?", {"intent": "calculation", "gross": 1_200_000, "income_type": "salary"}),
    ("T12", "how much tax on 1.5 cr salary", {"intent": "calculation", "gross": 15_000_000, "income_type": "salary"}),
    ("T13", "I earn €4000 a month working remotely for a German company as a contractor, how much tax",
     {"intent": "calculation", "gross": 4000 * 12 * 105.8641, "income_type": "professional_presumptive"}),
    ("T14", "£2,500 per month freelance income, how much tax in india",
     {"intent": "calculation", "gross": 2500 * 12 * 126.4657, "income_type": "professional_presumptive"}),
    ("T15", "i earn 2000 dollars per week freelancing, tax?",
     {"intent": "calculation", "income_type": "professional_presumptive", "escalate": True}),
    ("T16", "salry 15 lakh kitna tax", {"intent": "calculation", "gross": 1_500_000, "income_type": "salary"}),
    ("T17", "how much tax do i pay", {"intent": "calculation", "follow_up": True}),
    ("T18", "I am a doctor with private practice earning 40 lakh a year, tax under presumptive scheme?",
     {"intent": "calculation", "gross": 4_000_000, "income_type": "professional_presumptive"}),
    ("T19", "income 5 thousand per month, do i pay tax?", {"intent": "calculation", "gross": 60_000}),
    ("T20", "my wife earns 25k pm, does she have to pay tax?", {"intent": "calculation", "gross": 300_000}),
    ("T21", "tax on 7.5 lakh salary for FY 2024-25", {"intent": "calculation", "gross": 750_000, "tax_year": "2024-25"}),
    ("T22", "kitna tax lagega agar meri kamai 20 lakh saal hai", {"intent": "calculation", "gross": 2_000_000}),
    ("T23", "self employed consultant, 60 lakh receipts, how much tax",
     {"intent": "calculation", "gross": 6_000_000, "income_type": "professional_presumptive"}),
    ("T24", "freelancer with 90 lakh receipts how much tax", {"intent": "calculation", "escalate": True}),
    ("T25", "I earn 50k, how much tax?", {"intent": "calculation", "gross": 50_000, "assumed": True}),
    ("T26", "What is GST on export of services for freelancers?", {"intent": "question", "refused": False}),
    ("T27", "remote job for a US company paying 6000 USD monthly as an employee on payroll, tax?",
     {"intent": "calculation", "gross": 6000 * 12 * 95.2278, "income_type": "salary"}),
    ("T28", "mera mahine ka 40 hazaar hai, tax lagega kya?", {"intent": "calculation", "gross": 480_000}),
]


def _calc_inputs(resp: dict) -> dict:
    for t in resp.get("trace", []):
        if t["step"] == "calculator":
            return t["data"]
    return {}


def run_one(ts: TaxSaathi, qid: str, q: str, expect: dict, cfg: str) -> dict:
    r = ts.ask(q, cfg)
    cd = _calc_inputs(r)
    inputs = cd.get("inputs") or {}
    calc = r.get("calculation") or {}
    got = {"intent": r.get("intent"), "refused": r["refused"], "follow_up": bool(r.get("follow_up")),
           "gross": (inputs or {}).get("gross_salary"), "income_type": (inputs or {}).get("income_type",
                    "salary" if inputs.get("salaried", True) else "business/professional (no std ded)") if inputs else None,
           "age": inputs.get("age"), "tax_year": inputs.get("tax_year"),
           "old": (calc.get("old") or {}).get("total"), "new": (calc.get("new") or {}).get("total"),
           "headline": calc.get("headline"), "escalate": bool(cd.get("escalate")),
           "notes": (calc.get("notes") or cd.get("notes") or [])[:4], "answer": r["answer"][:400],
           "citations": [c["id"] for c in r.get("citations", [])]}
    fails = []
    for k, v in expect.items():
        if k == "gross":
            if not got["gross"] or abs(got["gross"] - v) > 0.02 * v:
                fails.append(f"gross {got['gross']} != {int(v)}")
        elif k == "assumed":
            if not any("assumed" in n.lower() for n in got["notes"]):
                fails.append("no assumption note")
        elif k == "income_type" and got["income_type"] is None and expect.get("escalate"):
            continue
        elif got.get(k) != v:
            fails.append(f"{k} {got.get(k)} != {v}")
    if r.get("calculation") and "do not cover" in r["answer"].lower():
        fails.append("'not covered' sentence next to a calculator result")
    return {"id": qid, "question": q, "expect": expect, "got": got, "pass": not fails, "fails": fails}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/battery.json")
    ap.add_argument("--config", default="C6")
    a = ap.parse_args()
    ts = TaxSaathi(use_llm=False)
    rows = []
    for line in (config.ROOT / "data/eval/real_questions.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        exp = {"intent": q["intent"]}
        if q["intent"] == "out_of_scope":
            exp["refused"] = True
        elif q["covered"] == "full":
            exp["refused"] = False
        rows.append(run_one(ts, q["id"], q["question"], exp, a.config))
    for qid, q, exp in TRICKY:
        rows.append(run_one(ts, qid, q, exp, a.config))
    Path(a.out).write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    real = [r for r in rows if r["id"].startswith("R")]
    tricky = [r for r in rows if r["id"].startswith("T")]
    print(f"real {sum(r['pass'] for r in real)}/{len(real)}  tricky {sum(r['pass'] for r in tricky)}/{len(tricky)}")
    for r in rows:
        if not r["pass"]:
            print(r["id"], "|", r["question"][:80], "|", "; ".join(r["fails"]))


if __name__ == "__main__":
    main()
