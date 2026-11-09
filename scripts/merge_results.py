"""
Merge two experiment runs into experiments/results.json and print Markdown tables.

Retrieval metrics are cheap, so they were run for every config (B1..C6). LLM answer metrics
are slow on our CPU server (~25 s per answer), so generation was run for the configs that
mark each big step of the ladder (B0, B1, C2, C4, C6). This script combines both files so
the UI, the slides and the report all read one results.json.

Usage: python -m scripts.merge_results RETRIEVAL.json GENERATION.json [--out experiments/results.json]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ORDER = ["B0", "B1", "C1", "C2", "C3", "C4", "C5", "C6"]
MAIN_COLS = [("recall@5", "Recall@5"), ("mrr@10", "MRR@10"), ("ndcg@5", "nDCG@5"),
             ("period_accuracy", "Period acc."), ("refusal_accuracy", "Refusal acc."),
             ("false_refusal_rate", "False refusal"), ("key_fact_accuracy", "Key-fact acc."),
             ("citation_validity", "Citation valid."), ("faithfulness", "Faithfulness"),
             ("latency_p50_ms", "p50 latency (s)")]


def fmt(key: str, v) -> str:
    if v is None:
        return "—"
    if key.startswith("latency"):
        return f"{v / 1000:.1f}"
    return f"{v:.3f}" if isinstance(v, float) else str(v)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("retrieval")
    ap.add_argument("generation")
    ap.add_argument("--out", default="experiments/results.json")
    a = ap.parse_args()
    ret, gen = json.loads(Path(a.retrieval).read_text()), json.loads(Path(a.generation).read_text())
    by = {c["name"]: c for c in ret["configs"]}
    for g in gen["configs"]:
        if g["name"] in by:
            base = by[g["name"]]
            # retrieval latency in the retrieval run excludes the LLM; keep the end-to-end one
            base["metrics"].update({k: v for k, v in g["metrics"].items()
                                    if k not in base["metrics"] or k.startswith("latency")
                                    or k in ("key_fact_accuracy", "citation_validity", "faithfulness")})
            for cat, m in g.get("per_category", {}).items():
                base.setdefault("per_category", {}).setdefault(cat, {}).update(
                    {k: v for k, v in m.items() if k not in base["per_category"][cat]})
            base["generated"] = True
        else:
            g["generated"] = True
            by[g["name"]] = g
    merged = dict(ret)
    merged["configs"] = [by[n] for n in ORDER if n in by]
    merged["generation_configs"] = [g["name"] for g in gen["configs"]]
    merged["note"] = ("Retrieval/refusal metrics for all configs; LLM answer metrics (key facts, citations, "
                      "faithfulness, end-to-end latency) for " + ", ".join(merged["generation_configs"]) + ".")
    Path(a.out).write_text(json.dumps(merged, indent=2, ensure_ascii=False))

    print("| Config | " + " | ".join(h for _, h in MAIN_COLS) + " |")
    print("|---" * (len(MAIN_COLS) + 1) + "|")
    for c in merged["configs"]:
        print(f"| {c['name']} | " + " | ".join(fmt(k, c["metrics"].get(k)) for k, _ in MAIN_COLS) + " |")
    cats = sorted({cat for c in merged["configs"] for cat in c.get("per_category", {})})
    print("\nPer-category Recall@5 / key-fact accuracy:\n")
    print("| Config | " + " | ".join(cats) + " |")
    print("|---" * (len(cats) + 1) + "|")
    for c in merged["configs"]:
        pc = c.get("per_category", {})
        cells = []
        for cat in cats:
            m = pc.get(cat, {})
            cells.append(f"{fmt('x', m.get('recall@5'))} / {fmt('x', m.get('key_fact_accuracy'))}")
        print(f"| {c['name']} | " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
