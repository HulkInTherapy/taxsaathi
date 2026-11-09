"""
Evaluate TaxSaathi on REAL questions asked by real taxpayers (Reddit, Quora, CA forums, official FAQs).

The gold set was written by the team; this checks whether the system also works on how people
actually phrase things. Retrieval-only (fast): Recall@5 / MRR on questions our knowledge base
fully covers, refusal behaviour on out-of-scope ones, and how often low-coverage questions are
refused (a good thing: better "ask a CA" than a guess).
Usage: python -m scripts.eval_real [--configs B1,C2,C6] [--generate]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.run_experiments import _agg, evaluate_config
from src.pipeline import TaxSaathi

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", default="B1,C2,C6")
    ap.add_argument("--generate", action="store_true")
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(ROOT / "data/eval/real_questions.jsonl") if l.strip()]
    ts = TaxSaathi()
    out = {"n": len(rows), "coverage": {k: sum(r["covered"] == k for r in rows) for k in ("full", "partial", "none")},
           "configs": []}
    for name in a.configs.split(","):
        res = evaluate_config(ts, name, rows, a.generate)
        recs = {r["id"]: r for r in res["rows"]}
        by_cov = {}
        for cov in ("full", "partial", "none"):
            sub = [recs[r["id"]] for r in rows if r["covered"] == cov and r["answerable"]]
            by_cov[cov] = {"n": len(sub), "refused_rate": round(sum(x["refused"] for x in sub) / len(sub), 3) if sub else None,
                           **{k: v for k, v in _agg(sub).items() if k in ("recall@5", "mrr@10", "key_fact_accuracy")}}
        oos = [recs[r["id"]] for r in rows if not r["answerable"]]
        res["by_coverage"] = by_cov
        res["oos_refused_rate"] = round(sum(x["refused"] for x in oos) / len(oos), 3) if oos else None
        res.pop("rows")
        out["configs"].append(res)
        m = res["metrics"]
        print(f"{name}: recall@5(full)={by_cov['full'].get('recall@5')} mrr={by_cov['full'].get('mrr@10')} "
              f"oos_refused={res['oos_refused_rate']} refused(full/partial/none)="
              f"{by_cov['full']['refused_rate']}/{by_cov['partial']['refused_rate']}/{by_cov['none']['refused_rate']} "
              f"kfa={m.get('key_fact_accuracy')}", flush=True)
    (ROOT / "experiments/real_results.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
