"""
Experiment runner for milestone M3: compares configurations B0..C5 on the gold set.

It (1) merges the gold files into data/eval/gold.jsonl, (2) makes a fixed, stratified
30% dev / 70% test split, (3) runs each config and measures retrieval quality (Recall@5,
MRR@10, nDCG@5), refusal accuracy, period accuracy on time-trap questions, calculator
accuracy and, with --generate, answer quality (key facts, citation validity, faithfulness,
latency). Results go to MLflow (experiments/mlruns) and experiments/results.json for the UI.

Examples:
  python -m experiments.run_experiments                      # retrieval metrics on dev
  python -m experiments.run_experiments --generate           # + LLM answers (slow)
  python -m experiments.run_experiments --tune-threshold     # pick the refusal threshold
  python -m experiments.run_experiments --split test --generate   # final numbers, run once
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from src import config
from src.calculator.parse import parse_calc_query
from src.calculator.tax import calculate, summary_text
from src.nlp.dates import extract_period
from src.pipeline import CONFIGS, TaxSaathi
from src.retrieval.date_filter import chunk_range

GOLD_PATH = config.EVAL_DIR / "gold.jsonl"
SPLITS_PATH = config.EVAL_DIR / "splits.json"
SEED = 42
DEV_FRACTION = 0.30


# ============================================================ data
def merge_gold() -> list[dict]:
    """Merge data/eval/gold_*.jsonl (income tax + GST, plus any other gold_ files) into gold.jsonl.
    If two files use the same id, the later one is renamed <file-tag>-<id> with a warning."""
    files = sorted(p for p in config.EVAL_DIR.glob("gold_*.jsonl"))
    if not files:
        if GOLD_PATH.exists():
            return [json.loads(l) for l in GOLD_PATH.read_text().splitlines() if l.strip()]
        sys.exit("No gold files found in data/eval (expected gold_income_tax.jsonl, gold_gst.jsonl)")
    rows, seen = [], set()
    for f in files:
        tag = f.stem.replace("gold_", "").upper()[:6]
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"WARNING: {f.name}:{n} is not valid JSON ({e}); skipped")
                continue
            if row["id"] in seen:
                new_id = f"{tag}-{row['id']}"
                print(f"WARNING: duplicate id {row['id']} in {f.name}; renamed to {new_id}")
                row["id"] = new_id
            seen.add(row["id"])
            row.setdefault("gold_chunk_ids", [])
            row.setdefault("key_facts", [])
            row.setdefault("answerable", row.get("category") != "out_of_scope")
            row["source_file"] = f.name
            rows.append(row)
    with GOLD_PATH.open("w", encoding="utf-8") as out:
        for r in rows:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    return rows


def make_splits(rows: list[dict], force: bool = False) -> dict:
    """Stratified 30% dev / 70% test split by category, seed 42.

    Why: the gold set is small (a few hundred questions), so we keep most of it (70%) as a
    held-out TEST set that we only evaluate once at the end — that gives the final numbers
    some statistical weight. The 30% DEV set is what we look at while tuning (refusal
    threshold, prompts, which config is best); tuning on test would make the reported scores
    optimistic. Stratifying by category keeps the mix of income_tax / gst / time_trap /
    calculation / out_of_scope / hinglish questions identical in both halves, so a small
    category is never missing from dev. The split is saved and reused so it never changes
    silently between runs (use --resplit to force a new one, e.g. after adding questions).
    """
    ids = {r["id"] for r in rows}
    if SPLITS_PATH.exists() and not force:
        s = json.loads(SPLITS_PATH.read_text())
        if set(s["dev"]) | set(s["test"]) == ids:
            return s
        print("gold set changed since splits.json was written -> re-splitting")
    rng = random.Random(SEED)
    by_cat: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        by_cat[r.get("category", "unknown")].append(r["id"])
    dev, test = [], []
    for cat in sorted(by_cat):
        cat_ids = sorted(by_cat[cat])
        rng.shuffle(cat_ids)
        n_dev = round(DEV_FRACTION * len(cat_ids))
        if len(cat_ids) >= 2:
            n_dev = max(1, n_dev)
        dev += cat_ids[:n_dev]
        test += cat_ids[n_dev:]
    s = {"seed": SEED, "dev_fraction": DEV_FRACTION, "stratified_by": "category",
         "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "dev": sorted(dev), "test": sorted(test)}
    SPLITS_PATH.write_text(json.dumps(s, indent=2))
    return s


# ============================================================ metrics
def recall_at(ranked: list[str], gold: list[str], k: int) -> float:
    return len(set(ranked[:k]) & set(gold)) / len(gold) if gold else 0.0


def mrr_at(ranked: list[str], gold: list[str], k: int) -> float:
    for i, cid in enumerate(ranked[:k], 1):
        if cid in gold:
            return 1.0 / i
    return 0.0


def ndcg_at(ranked: list[str], gold: list[str], k: int) -> float:
    dcg = sum(1.0 / math.log2(i + 1) for i, cid in enumerate(ranked[:k], 1) if cid in gold)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, min(len(gold), k) + 1))
    return dcg / ideal if ideal else 0.0


def _norm(s: str) -> str:
    """SPEC: key facts are matched case-insensitively after removing ₹, commas and spaces."""
    return re.sub(r"[₹,\s]", "", str(s)).lower()


def key_facts_ok(text: str, facts: list[str]) -> bool:
    t = _norm(text)
    return all(_norm(f) in t for f in facts)


def period_correct(top1: str | None, gold_ids: list[str], by_id: dict) -> bool:
    """Top-1 chunk is period-correct if it is a gold chunk, or if it carries explicit dates
    that overlap the validity period of at least one dated gold chunk (i.e. it describes the
    same time period even if it is a different passage). Undated top-1 chunks only count
    if they are gold, because they say nothing about which period applies."""
    if top1 is None:
        return False
    if top1 in gold_ids:
        return True
    c = by_id.get(top1)
    if not c or not (c.get("effective_from") or c.get("effective_to")):
        return False
    cf, ct = chunk_range(c)
    for g in gold_ids:
        gc = by_id.get(g)
        if gc and (gc.get("effective_from") or gc.get("effective_to")):
            gf, gt = chunk_range(gc)
            if cf <= gt and ct >= gf:
                return True
    return False


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None


def _pct(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    idx = min(len(xs) - 1, max(0, int(math.ceil(q * len(xs))) - 1))
    return xs[idx]


def calc_text_for(row: dict) -> str | None:
    """Run the calculator directly on a calculation question (independent of retrieval)."""
    q = row["question"]
    from src.nlp.hinglish import normalise
    norm = normalise(q)["normalised"]
    parsed = parse_calc_query(norm, extract_period(f"{q} {norm}"))
    if parsed["inputs"] is None:
        return None
    res = calculate(parsed["inputs"])
    numbers = " ".join(str(res[r][k]) for r in ("old", "new") for k in ("taxable", "slab_tax", "rebate", "surcharge", "cess", "total"))
    return summary_text(res) + " " + numbers + f" better {res['better']} saving {res['saving']}"


# ============================================================ evaluation
def evaluate_config(ts: TaxSaathi, name: str, rows: list[dict], generate: bool) -> dict:
    by_id = {c["id"]: c for c in ts.chunks}
    per_row = []
    for n, row in enumerate(rows, 1):
        rec = {"id": row["id"], "category": row.get("category"), "answerable": bool(row.get("answerable", True))}
        gold = row.get("gold_chunk_ids") or []
        t0 = time.perf_counter()
        if generate:
            out = ts.ask(row["question"], name)
            rec["latency_ms"] = out["latency_ms"]
            rec["refused"] = out["refused"]
            trace = {t["step"]: t for t in out["trace"]}
            ranked = out.get("retrieved") or _ranked_from_trace(trace)
            if rec["answerable"] and row.get("key_facts") and not out["refused"]:
                text = out["answer"]
                if out.get("calculation"):
                    text += " " + summary_text(out["calculation"])
                rec["key_facts_ok"] = key_facts_ok(text, row["key_facts"])
            elif rec["answerable"] and row.get("key_facts"):
                rec["key_facts_ok"] = False
            cc = trace.get("citation_check")
            if cc and not cc["data"].get("fallback"):
                d = cc["data"]
                rec["citation_validity"] = d["n_valid_tags"] / d["n_tags"] if d["n_tags"] else 0.0
                total = d["kept"] + d["dropped"]
                rec["faithfulness"] = d["kept"] / total if total else 0.0
            if cc:
                rec["fallback"] = bool(cc["data"].get("fallback"))
        else:
            out = ts.retrieve_only(row["question"], name)
            rec["refused"] = out["refused"]
            rec["latency_ms"] = int((time.perf_counter() - t0) * 1000)
            ranked = out["ids"]
        rec["ranked"] = ranked[:10]
        if rec["answerable"] and gold and CONFIGS[name]["retrieval"]:
            rec["recall5"] = recall_at(ranked, gold, 5)
            rec["mrr10"] = mrr_at(ranked, gold, 10)
            rec["ndcg5"] = ndcg_at(ranked, gold, 5)
            if row.get("category") == "time_trap":
                rec["period_ok"] = period_correct(ranked[0] if ranked else None, gold, by_id)
        rec["refusal_ok"] = (rec["refused"] == (not rec["answerable"]))
        if row.get("category") == "calculation" and row.get("key_facts") and name != "B0":
            txt = calc_text_for(row)
            rec["calc_ok"] = bool(txt) and key_facts_ok(txt, row["key_facts"])
        per_row.append(rec)
        if n % 25 == 0:
            print(f"  {name}: {n}/{len(rows)}", flush=True)
    return summarise(name, per_row, generate)


def _ranked_from_trace(trace: dict) -> list[str]:
    for step in ("rerank", "fusion", "dense", "bm25"):
        if step in trace:
            res = trace[step]["data"].get("results", [])
            if step == "fusion" and "date_filter" in trace:
                removed = set(trace["date_filter"]["data"].get("removed", []))
                res = [r for r in res if r["id"] not in removed]
            return [r["id"] for r in res]
    return []


def _agg(recs: list[dict]) -> dict:
    m = {
        "n": len(recs),
        "recall@5": _mean([r.get("recall5") for r in recs]),
        "mrr@10": _mean([r.get("mrr10") for r in recs]),
        "ndcg@5": _mean([r.get("ndcg5") for r in recs]),
        "refusal_accuracy": _mean([1.0 if r["refusal_ok"] else 0.0 for r in recs]),
        "period_accuracy": _mean([1.0 if r["period_ok"] else 0.0 for r in recs if "period_ok" in r]),
        "calc_accuracy": _mean([1.0 if r["calc_ok"] else 0.0 for r in recs if "calc_ok" in r]),
    }
    oos = [r for r in recs if not r["answerable"]]
    ans = [r for r in recs if r["answerable"]]
    m["oos_refusal_rate"] = _mean([1.0 if r["refused"] else 0.0 for r in oos])
    m["false_refusal_rate"] = _mean([1.0 if r["refused"] else 0.0 for r in ans])
    if any("key_facts_ok" in r for r in recs):
        m["key_fact_accuracy"] = _mean([1.0 if r["key_facts_ok"] else 0.0 for r in recs if "key_facts_ok" in r])
    if any("citation_validity" in r for r in recs):
        m["citation_validity"] = _mean([r.get("citation_validity") for r in recs])
        m["faithfulness"] = _mean([r.get("faithfulness") for r in recs])
    if any("fallback" in r for r in recs):
        m["fallback_rate"] = _mean([1.0 if r["fallback"] else 0.0 for r in recs if "fallback" in r])
    lat = [r["latency_ms"] for r in recs if r.get("latency_ms") is not None]
    m["latency_p50_ms"] = _pct(lat, 0.5)
    m["latency_p95_ms"] = _pct(lat, 0.95)
    return m


def summarise(name: str, per_row: list[dict], generate: bool) -> dict:
    cats = sorted({r["category"] for r in per_row})
    return {"name": name, "description": CONFIGS[name]["description"], "generated": generate,
            "metrics": _agg(per_row),
            "per_category": {c: _agg([r for r in per_row if r["category"] == c]) for c in cats},
            "rows": [{k: v for k, v in r.items()} for r in per_row]}


# ============================================================ MLflow
def log_mlflow(result: dict, split: str, threshold: float, generate: bool) -> None:
    import os
    # MLflow 3.x refuses the plain file store unless explicitly allowed; the SPEC asks for it.
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    try:
        import mlflow
    except ImportError:
        print("mlflow not installed; skipping MLflow logging")
        return
    try:
        mlflow.set_tracking_uri(f"file:{config.MLRUNS_DIR}")
        mlflow.set_experiment("taxsaathi-m3")
        with mlflow.start_run(run_name=f"{result['name']}-{split}{'-gen' if generate else ''}"):
            cfg = CONFIGS[result["name"]]
            mlflow.log_params({"config": result["name"], "split": split, "generate": generate,
                               "retrieval": cfg["retrieval"], "rerank": cfg["rerank"],
                               "date_filter": cfg["date_filter"], "hinglish": cfg["hinglish"],
                               "rerank_threshold": threshold, "llm": config.LLM_MODEL,
                               "embed_model": config.EMBED_MODEL, "reranker": config.RERANK_MODEL})
            metrics = {re.sub(r"[^\w\-./ ]", "_", k): v for k, v in result["metrics"].items() if isinstance(v, (int, float))}
            for cat, m in result["per_category"].items():
                for k, v in m.items():
                    if isinstance(v, (int, float)):
                        metrics[f"{cat}.{re.sub(r'[^0-9A-Za-z_]', '_', k)}"] = v
            mlflow.log_metrics(metrics)
    except Exception as e:  # never lose the results because of a logging problem
        print(f"MLflow logging failed: {e}")


# ============================================================ threshold tuning
def tune_threshold(ts: TaxSaathi, rows: list[dict], name: str) -> dict:
    """Sweep the rerank threshold on dev; choose the one with the best refusal accuracy."""
    scored = []
    for row in rows:
        out = ts.retrieve_only(row["question"], name)
        intent_refused = out["refusal_reason"] in ("out_of_scope", "prompt_injection")
        is_calc = out["intent"]["label"] == "calculation"
        scored.append((out["top_score"], bool(row.get("answerable", True)), intent_refused, is_calc))
    values = sorted({s for s, *_ in scored if s is not None})
    candidates = [values[0] - 0.01] + [(a + b) / 2 for a, b in zip(values, values[1:])] + [values[-1] + 0.01] if values else [config.DEFAULT_RERANK_THRESHOLD]
    table = []
    for th in candidates:
        correct = tp = fp = 0
        for score, answerable, intent_refused, is_calc in scored:
            refused = intent_refused or (not is_calc and (score is None or score < th))
            correct += refused == (not answerable)
            tp += refused and not answerable
            fp += refused and answerable
        n_oos = sum(1 for _, a, *_ in scored if not a)
        n_ans = len(scored) - n_oos
        table.append({"threshold": round(th, 3), "accuracy": correct / len(scored),
                      "oos_refusal_rate": tp / n_oos if n_oos else None,
                      "false_refusal_rate": fp / n_ans if n_ans else None})
    # Best accuracy; among equally good thresholds (a "plateau") take the median one, so the
    # threshold is not glued to a single dev question's score (more robust on unseen data).
    top_acc = max(r["accuracy"] for r in table)
    plateau = [r for r in table if r["accuracy"] == top_acc]
    best = plateau[len(plateau) // 2]
    print(f"\nthreshold sweep for {name} on {len(rows)} dev rows (showing every ~10th):")
    for r in table[::max(1, len(table) // 10)]:
        print(f"  th={r['threshold']:7.3f}  acc={r['accuracy']:.3f}  oos_refused={r['oos_refusal_rate']}  false_refusals={r['false_refusal_rate']}")
    print(f"BEST threshold = {best['threshold']} (refusal accuracy {best['accuracy']:.3f})")
    config.THRESHOLD_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.THRESHOLD_PATH.write_text(json.dumps({"rerank_threshold": best["threshold"], "config": name,
                                                 "dev_refusal_accuracy": best["accuracy"],
                                                 "tuned_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=2))
    print(f"saved to {config.THRESHOLD_PATH} (used automatically by the pipeline)")
    return best


# ============================================================ main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run TaxSaathi experiments B0..C5 on the gold set")
    ap.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    ap.add_argument("--configs", default=None, help="comma list, e.g. B1,C2,C5 (default: B1..C5; B0 too with --generate)")
    ap.add_argument("--generate", action="store_true", help="also run the LLM and score answers (slow)")
    ap.add_argument("--tune-threshold", action="store_true", help="sweep the rerank refusal threshold on dev and save the best")
    ap.add_argument("--limit", type=int, default=None, help="only the first N rows (quick checks)")
    ap.add_argument("--resplit", action="store_true", help="regenerate splits.json")
    ap.add_argument("--no-mlflow", action="store_true")
    ap.add_argument("--out", type=Path, default=config.RESULTS_PATH)
    args = ap.parse_args(argv)

    rows = merge_gold()
    splits = make_splits(rows, force=args.resplit)
    print(f"gold rows: {len(rows)}  dev: {len(splits['dev'])}  test: {len(splits['test'])}")
    wanted = set(splits["dev"]) | set(splits["test"]) if args.split == "all" else set(splits[args.split])
    eval_rows = [r for r in rows if r["id"] in wanted]
    if args.limit:
        eval_rows = eval_rows[:args.limit]

    ts = TaxSaathi()
    if not ts.chunks:
        sys.exit("No chunks: run `python -m src.ingest.ingest` first")

    if args.tune_threshold:
        if args.split == "test":
            print("WARNING: tuning on the test set leaks information; use --split dev")
        name = (args.configs or "C5").split(",")[0]
        tune_threshold(ts, eval_rows, name)
        return 0

    names = args.configs.split(",") if args.configs else (list(CONFIGS) if args.generate else [c for c in CONFIGS if c != "B0"])
    threshold = config.rerank_threshold()
    results = []
    for name in names:
        print(f"== {name}: {CONFIGS[name]['description']} ({len(eval_rows)} rows)", flush=True)
        t0 = time.time()
        res = evaluate_config(ts, name, eval_rows, args.generate)
        print(f"   done in {time.time() - t0:.0f}s  " + "  ".join(f"{k}={v}" for k, v in res["metrics"].items() if v is not None))
        if not args.no_mlflow:
            log_mlflow(res, args.split, threshold, args.generate)
        results.append(res)

    # Merge with an existing results file for the same split so partial runs don't erase others.
    existing = {}
    if args.out.exists():
        try:
            old = json.loads(args.out.read_text())
            if old.get("split") == args.split:
                existing = {c["name"]: c for c in old.get("configs", [])}
        except json.JSONDecodeError:
            pass
    for r in results:
        existing[r["name"]] = r
    ordered = [existing[n] for n in CONFIGS if n in existing]
    detail_path = args.out.with_name(f"results_{args.split}_rows.json")
    detail_path.write_text(json.dumps({c["name"]: c["rows"] for c in ordered}, indent=1, ensure_ascii=False))
    payload = {"configs": [{k: v for k, v in c.items() if k != "rows"} for c in ordered],
               "split": args.split, "dev_size": len(splits["dev"]), "test_size": len(splits["test"]),
               "rerank_threshold": threshold, "llm": config.LLM_MODEL,
               "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"wrote {args.out} and {detail_path}")
    _print_table(payload["configs"])
    return 0


def _print_table(configs: list[dict]) -> None:
    cols = ["recall@5", "mrr@10", "ndcg@5", "refusal_accuracy", "period_accuracy", "calc_accuracy",
            "key_fact_accuracy", "citation_validity", "faithfulness", "latency_p50_ms"]
    cols = [c for c in cols if any(cfg["metrics"].get(c) is not None for cfg in configs)]
    print("\n" + "config".ljust(7) + "".join(c[:12].rjust(13) for c in cols))
    for cfg in configs:
        vals = [cfg["metrics"].get(c) for c in cols]
        print(cfg["name"].ljust(7) + "".join(("-" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)).rjust(13) for v in vals))


if __name__ == "__main__":
    sys.exit(main())
