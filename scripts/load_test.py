"""
M5 performance check: latency (p50/p95) and throughput of the C6 pipeline under concurrent users.

Runs the pipeline in-process with the answer writer switched off (deterministic extractive answer),
so it measures everything Taxot itself does per question: PII scrub, Hinglish normalisation, intent,
period extraction, hybrid retrieval, date filter, cross-encoder gate, calculator and citation check.
Writer latency depends on the hosted provider and is reported separately from
experiments/results_api_writer.json.

    python -m scripts.load_test --users 1,10 --rounds 2 --out experiments/load_test.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from src import config
from src.pipeline import Taxot


def pctl(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(q * (len(xs) - 1))))
    return xs[k]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--users", default="1,10")
    ap.add_argument("--rounds", type=int, default=2, help="passes over the dev questions per level")
    ap.add_argument("--out", type=Path, default=Path("experiments/load_test.json"))
    a = ap.parse_args(argv)

    gold = {json.loads(l)["id"]: json.loads(l) for l in (config.ROOT / "data/eval/gold.jsonl").open()}
    dev = json.loads((config.ROOT / "data/eval/splits.json").read_text())["dev"]
    qs = [gold[i]["question"] for i in dev if i in gold]

    ts = Taxot(use_llm=False)
    for q in qs[:3]:  # warm-up: load models, caches
        ts.ask(q, "C6")

    levels = []
    for users in [int(u) for u in a.users.split(",")]:
        work = qs * a.rounds
        lat: list[float] = []

        def one(q):
            t0 = time.perf_counter()
            ts.ask(q, "C6")
            lat.append((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=users) as ex:
            list(ex.map(one, work))
        wall = time.perf_counter() - t0
        lv = {"users": users, "requests": len(work), "wall_s": round(wall, 2),
              "throughput_qps": round(len(work) / wall, 2),
              "p50_ms": round(statistics.median(lat)), "p95_ms": round(pctl(lat, 0.95)),
              "max_ms": round(max(lat))}
        print(lv, flush=True)
        levels.append(lv)

    a.out.write_text(json.dumps({"config": "C6", "writer": "off (extractive)", "questions": len(qs),
                                 "levels": levels,
                                 "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")},
                                indent=2))
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
