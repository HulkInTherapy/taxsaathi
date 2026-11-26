"""Build the short Taxot deck (presentation/Taxot_Short.pptx, 15 slides) from the full deck builder.

Run from the repo root:
    .venv/bin/python presentation/build_short_deck.py

It executes build_deck.py in memory (same look, same live numbers from experiments/*.json) without
saving the full deck, then keeps the core slides, adds a held-out test-set slide built from
experiments/results_test.json, puts the team on the title and closing slides, renumbers, and saves.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT_SHORT = HERE / "Taxot_Short.pptx"
TEST_RESULTS = ROOT / "experiments" / "results_test.json"

TEAM = [("Ritesh Patil", "230056"), ("Meghavi Rao", "230044"), ("Harshal Nerpagar", "230076")]

# Titles of the full-deck slides to keep, in order (matched by prefix). The test slide goes after "Targets".
KEEP = [
    "__title__",
    "Simple tax questions still need a paid CA",
    "Two big law changes in seven months",
    "What Taxot does: five promises",
    "__screens__",
    "How it works: build a library once",
    "Our data: a dated library and an answer key",
    "Experiment design: a ladder",
    "Results: the final system finds the right rule",
    "Same AI model:",
    "Targets we set at the start",
    "__test__",
    "From answers to tasks: a team of AI agents",
    "One AI with all tools",
    "Cost per answer and how Taxot could earn",
    "Limits, ethics, and what comes next",
    "__thanks__",
]

# ---------------------------------------------------------------- run the full builder in memory
src = (HERE / "build_deck.py").read_text(encoding="utf-8")
marker = "\n# 23. Thanks "
assert marker in src and "prs.save(OUT)" in src
src = src.split(marker)[0]          # everything except the closing slide and the save
ns: dict = {"__file__": str(HERE / "build_deck.py"), "__name__": "build_deck_inline"}
exec(compile(src, str(HERE / "build_deck.py"), "exec"), ns)

prs = ns["prs"]
text, card, badge, pill, picture, pic_bottom, notes, new_slide, set_bg = (
    ns[k] for k in ("text", "card", "badge", "pill", "picture", "pic_bottom", "notes", "new_slide", "set_bg"))
INK, INK2, INK3, MUTED, TEAL, TEAL_INK, TEAL_SOFT, LINE, WHITE, AMBER_BG, AMBER_INK = (
    ns[k] for k in ("INK", "INK2", "INK3", "MUTED", "TEAL", "TEAL_INK", "TEAL_SOFT", "LINE", "WHITE",
                    "AMBER_BG", "AMBER_INK"))
ASSETS, LOGO, fmt, pct = ns["ASSETS"], ns["LOGO"], ns["fmt"], ns["pct"]
DEV_N, R5, MRR, NDCG = ns["DEV_N"], ns["R5"], ns["MRR"], ns["NDCG"]
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN  # noqa: E402
from pptx.util import Inches  # noqa: E402

# ---------------------------------------------------------------- new slide: held-out test set
test = json.loads(TEST_RESULTS.read_text()) if TEST_RESULTS.exists() else {"configs": []}
TCFG = {c["name"]: c["metrics"] for c in test.get("configs", [])}
TEST_N = test.get("test_size", 123)


def tm(cfg, key):
    v = TCFG.get(cfg, {}).get(key)
    return v if isinstance(v, (int, float)) else None


s_test = new_slide("Sealed test set: the final system holds up", f"Held-out test · {TEST_N} questions, run once")
cols = [("Config", 1.3), ("Recall@5", 1.55), ("MRR", 1.4), ("nDCG@5", 1.5), ("Right period", 1.75),
        ("Refusal acc.", 1.75), ("Calculator", 1.6)]
keys = ["recall@5", "mrr@10", "ndcg@5", "period_accuracy", "refusal_accuracy", "calc_accuracy"]
x0, y0, rh = 0.6, 1.65, 0.46
x = x0
for name, w in cols:
    text(s_test, x, y0, w, 0.4, name, size=14, bold=True, color=MUTED, align=PP_ALIGN.CENTER if name != "Config" else PP_ALIGN.LEFT)
    x += w
names = [n for n in ["B1", "C1", "C2", "C3", "C4", "C5", "C6"] if n in TCFG]
for i, n in enumerate(names):
    y = y0 + 0.45 + i * rh
    final = n == "C6"
    card(s_test, x0 - 0.1, y, sum(w for _, w in cols) + 0.2, rh - 0.06, fill=TEAL_SOFT if final else WHITE, line=LINE)
    x = x0
    for j, (name, w) in enumerate(cols):
        if j == 0:
            val = n + ("  (final)" if final else "")
            al = PP_ALIGN.LEFT
        else:
            v = tm(n, keys[j - 1])
            val = fmt(v) if keys[j - 1] in ("recall@5", "mrr@10", "ndcg@5") else pct(v)
            al = PP_ALIGN.CENTER
        text(s_test, x, y, w, rh - 0.06, val, size=15, bold=final, color=TEAL_INK if final else INK2, align=al,
             anchor=MSO_ANCHOR.MIDDLE)
        x += w
tr5, tmrr = tm("C6", "recall@5"), tm("C6", "mrr@10")
yb = y0 + 0.5 + len(names) * rh + 0.1
card(s_test, 0.6, yb, 12.1, 0.8, fill=WHITE, line=LINE)
text(s_test, 0.85, yb, 11.7, 0.8,
     [[("Dev → test for C6:  ", {"bold": True, "color": INK}),
       (f"Recall@5 {fmt(R5)} → {fmt(tr5)}   ·   MRR {fmt(MRR)} → {fmt(tmrr)}   ·   "
        f"right period {pct(tm('C6', 'period_accuracy'))}   ·   off-topic refused {pct(tm('C6', 'oos_refusal_rate'))} (target 90%)",
        {"color": INK2})]], size=16, anchor=MSO_ANCHOR.MIDDLE)
text(s_test, 0.6, 6.45, 12.1, 0.35, "Tuning used only the dev split; the test split was run once with the frozen code. "
     "Answer-writing metrics need the LLM for every question and are reported on dev.", size=12, color=MUTED, italic=True)
notes(s_test, f"""
Everything so far was measured on the 53 development questions, the only ones we tuned on.
We kept {TEST_N} questions sealed. After we froze the system, we ran them once.
Our final system, C6, scores Recall at 5 of {fmt(tr5)} and MRR of {fmt(tmrr)} on the sealed set, against {fmt(R5)} and {fmt(MRR)} on dev.
It still picks the right year's law {pct(tm('C6', 'period_accuracy'))} of the time, and the calculator is {pct(tm('C6', 'calc_accuracy'))} exact.
One honest miss: it refused {pct(tm('C6', 'oos_refusal_rate'))} of off-topic questions, below our 90% target. The two it answered were GST raid and GST-evasion questions that look like ordinary GST questions.
The ladder keeps the same shape: hybrid search beats either search alone, and letting the reranker reorder hurts.
""")

# ---------------------------------------------------------------- new slide: the app, four screens
s_screens = new_slide("The app: four tabs people use", "Live app · screenshots, 26 Nov 2026")
shots = [("shot_compare_nov.jpg", (0.13, 0.417, 0.13, 0), "Compare: a plain chatbot says 18% for an AC in Aug 2025; Taxot says 28%, with its source"),
         ("shot_ask_nov.jpg", (0.24, 0.10, 0.24, 0), "Ask, in Hinglish: GST registration for a freelancer, cited to s. 22 and s. 25(3)"),
         ("shot_tasks_nov.jpg", (0.19, 0.12, 0.19, 0), "Tasks: agents check documents, prepare the return or find savings"),
         ("shot_mon_nov.jpg", (0.12, 0.31, 0.12, 0), "Monitor: questions, refusals, speed, feedback and AI providers, from the logs")]
for i, (f, crop, cap) in enumerate(shots):
    x = 0.6 + (i % 2) * 6.2
    y = 1.6 + (i // 2) * 2.65
    pic = picture(s_screens, ASSETS / f, x, y, w=5.9, h=2.2, crop=crop)
    text(s_screens, x, pic_bottom(pic) + 0.04, 5.9, 0.32, cap, size=12, color=MUTED, italic=True)
notes(s_screens, """
This is the real app, captured today.
Top left, the Compare tab: the same question to a plain chatbot and to Taxot. The plain chatbot says 18 percent for an AC in August 2025, which is today's rate, not August's. Taxot says 28 percent, the rate in force then, and shows its source.
Top right, the Ask tab with a Hinglish question about GST registration for a freelancer. The answer cites sections 22 and 25(3) of the CGST Act.
Bottom left, the Tasks tab, where the agents check documents, prepare a return or plan tax savings.
Bottom right, the new Monitor tab: questions per day, refusal rate, answer time, feedback and which AI providers answered, all built from the server's logs.
""")

# ---------------------------------------------------------------- new closing slide with the team
s_thanks = prs.slides.add_slide(ns["TITLE_ONLY"])
set_bg(s_thanks)
t = s_thanks.shapes.title
t.left, t.top, t.width, t.height = Inches(1.9), Inches(0.75), Inches(10.5), Inches(0.9)
t.text_frame.margin_left = t.text_frame.margin_top = 0
t.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
p = t.text_frame.paragraphs[0]
p.alignment = PP_ALIGN.LEFT
r = p.add_run()
r.text = "Thank you. Questions?"
ns["_font"](r, 40, INK, bold=True)
if LOGO.exists():
    s_thanks.shapes.add_picture(str(LOGO), Inches(0.6), Inches(0.7), Inches(1.0), Inches(1.0))
text(s_thanks, 0.6, 2.0, 6, 0.4, "Team", size=16, bold=True, color=TEAL)
for i, (nm, roll) in enumerate(TEAM):
    y = 2.5 + i * 1.15
    card(s_thanks, 0.6, y, 6.4, 0.95)
    badge(s_thanks, 0.85, y + 0.18, 0.6, nm.split()[0][0] + nm.split()[-1][0], fill=TEAL_SOFT, color=TEAL_INK, size=14)
    text(s_thanks, 1.65, y, 3.6, 0.95, nm, size=20, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    text(s_thanks, 5.2, y, 1.6, 0.95, roll, size=16, color=MUTED, anchor=MSO_ANCHOR.MIDDLE, align=PP_ALIGN.RIGHT)
pt_ = picture(s_thanks, ASSETS / "shot_how_nov.jpg", 7.55, 2.5, w=5.15, h=2.9, crop=(0.125, 0.08, 0.125, 0))
text(s_thanks, 7.55, pic_bottom(pt_) + 0.08, 5.15, 0.4, "Live demo: http://167.86.114.152:8000", size=18, bold=True,
     color=TEAL)
text(s_thanks, 0.6, 6.55, 12, 0.4, "Code, data card, experiment logs, IEEE report and viva notes are in our repository.",
     size=14, color=MUTED)
notes(s_thanks, "Thank you for listening. We are happy to take questions; each of us will take questions on our own part.")

# ---------------------------------------------------------------- choose, order and renumber
slides = list(prs.slides)
by_id = {id(s): s for s in slides}


def title_of(s):
    try:
        return s.shapes.title.text_frame.text if s.shapes.title is not None else ""
    except Exception:
        return ""


chosen = []
for k in KEEP:
    if k == "__title__":
        chosen.append(slides[0])
    elif k == "__test__":
        chosen.append(s_test)
    elif k == "__screens__":
        chosen.append(s_screens)
    elif k == "__thanks__":
        chosen.append(s_thanks)
    else:
        m = [s for s in slides if title_of(s).startswith(k)]
        assert m, f"slide not found: {k}"
        chosen.append(m[0])

sld_lst = prs.slides._sldIdLst
id_of = {}
for sld_id, s in zip(list(sld_lst), slides):
    id_of[id(s)] = sld_id
keep_ids = [id_of[id(s)] for s in chosen]
for sld_id in list(sld_lst):
    if sld_id not in keep_ids:
        prs.part.drop_rel(sld_id.rId)
    sld_lst.remove(sld_id)
for sld_id in keep_ids:
    sld_lst.append(sld_id)

# title slide: team instead of "Team of 4"
for sh in chosen[0].shapes:
    if sh.has_text_frame and "NLP course project" in sh.text_frame.text:
        runs = sh.text_frame.paragraphs[0].runs
        runs[-1].text = "   ·   " + ", ".join(n for n, _ in TEAM) + "   ·   November 2026"

# limits slide: bring the M5 / test items up to date
LAT_H = 8.1  # s, C6 median with the hosted writer (experiments/results_api_writer.json)
lim = next(s for s in chosen if title_of(s).startswith("Limits"))
FIX = {
    f"Slow: {ns['secs'](ns['LAT'])} per answer on a CPU": f"Above the 5 s target: {LAT_H} s median (hosted writer)",
    "Re-score answers with the hosted writer; multilingual reranker; CA review of the answer key":
        "Faster writer for the 5 s target; multilingual reranker; CA review of the answer key",
    "Run the sealed test set once; better off-topic sorter from real questions":
        "Done: sealed test set run once. Next: test-set answer scores, better off-topic sorter",
}
for sh in lim.shapes:
    if sh.has_text_frame:
        for para in sh.text_frame.paragraphs:
            for run in para.runs:
                if run.text in FIX:
                    run.text = FIX[run.text]
nt = lim.notes_slide.notes_text_frame
nt.text = "\n".join(
    (f"It is slower than our target: about {LAT_H} seconds per answer with the hosted writer, against 5 seconds." if l.startswith("It is slow") else l)
    for l in nt.text.splitlines() if "sealed test set" not in l and "re-score the answers" not in l)

# title slide: today's app instead of the 29 Oct screenshot
t0 = chosen[0]
for sh in list(t0.shapes):
    if sh.shape_type == 13 and sh.width > Inches(4):
        x, y, w = sh.left, sh.top, sh.width
        sh._element.getparent().remove(sh._element)
        picture(t0, ASSETS / "shot_compare_nov.jpg", x / 914400, y / 914400, w=w / 914400, h=5.0, crop=(0.14, 0.13, 0.14, 0))
    elif sh.has_text_frame and sh.text_frame.text.startswith("The live app"):
        sh.text_frame.paragraphs[0].runs[0].text = "The live app, 26 Nov 2026"

# targets slide: latency with the hosted writer
tg = next(s for s in chosen if title_of(s).startswith("Targets"))
for sh in tg.shapes:
    if sh.has_text_frame:
        for para in sh.text_frame.paragraphs:
            for run in para.runs:
                if run.text.endswith(" on CPU"):
                    run.text = f"{LAT_H} s (hosted)"
                elif run.text.startswith("Dev set,") and "Latency" in run.text:
                    run.text = f"Dev set, {DEV_N} questions. Latency: 16.8 s with the local 3B model on CPU, {LAT_H} s with the hosted writer; still above 5 s."

# renumber the footer slide numbers
for n, s in enumerate(chosen, 1):
    for sh in s.shapes:
        if sh.name == "SlideNumber" and sh.has_text_frame:
            sh.text_frame.paragraphs[0].runs[0].text = str(n)

prs.save(OUT_SHORT)
print(f"wrote {OUT_SHORT}  ({len(chosen)} slides)")
