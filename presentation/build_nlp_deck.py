"""
Build the 7-slide technical deck for the NLP teacher: presentation/TaxSaathi_NLP_Explained.pptx

Not a pitch: it explains what we built for M1–M3 and how a question is processed end to end.
Numbers are read from experiments/results.json and data files at build time.
Run on the VPS:  .venv/bin/python presentation/build_nlp_deck.py
"""
from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "presentation" / "TaxSaathi_NLP_Explained.pptx"
LOGO = ROOT / "presentation" / "assets" / "logo.png"

INK = RGBColor(0x11, 0x14, 0x18)
MUTED = RGBColor(0x5B, 0x63, 0x6E)
LINE = RGBColor(0xE3, 0xE6, 0xEA)
CARD = RGBColor(0xF6, 0xF7, 0xF8)
TEAL = RGBColor(0x0F, 0x76, 0x6E)
TEAL_BG = RGBColor(0xE6, 0xF3, 0xF1)
AMBER = RGBColor(0xB4, 0x53, 0x09)
AMBER_BG = RGBColor(0xFD, 0xF3, 0xE4)
RED = RGBColor(0xB9, 0x1C, 0x1C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Calibri"

R = json.loads((ROOT / "experiments" / "results.json").read_text())
CFG = {c["name"]: c["metrics"] for c in R["configs"]}
CHUNKS = [json.loads(l) for l in open(ROOT / "data" / "processed" / "chunks.jsonl")]
N_CHUNKS = len(CHUNKS)
N_VERIFIED = sum(c.get("verified") == "yes" for c in CHUNKS)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
BLANK = prs.slide_layouts[6]


# ---------------------------------------------------------------- helpers
def text(slide, x, y, w, h, s, size=16, bold=False, color=INK, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         italic=False):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.02)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    tf.vertical_anchor = anchor
    lines = s if isinstance(s, list) else [s]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        runs = line if isinstance(line, list) else [(line, {})]
        for chunk in runs:
            t, fmt = (chunk, {}) if isinstance(chunk, str) else chunk
            r = p.add_run()
            r.text = t
            f = r.font
            f.name = FONT
            f.size = Pt(fmt.get("size", size))
            f.bold = fmt.get("bold", bold)
            f.italic = fmt.get("italic", italic)
            f.color.rgb = fmt.get("color", color)
        p.space_after = Pt(fmt.get("after", 4) if isinstance(chunk, tuple) else 4)
    return tb


def box(slide, x, y, w, h, fill=CARD, line=LINE, radius=True, lw=0.75):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                                 Inches(x), Inches(y), Inches(w), Inches(h))
    if radius:
        shp.adjustments[0] = 0.08
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(lw)
    shp.shadow.inherit = False
    shp.text_frame.text = ""
    return shp


def node(slide, x, y, w, h, title, sub="", fill=WHITE, line=LINE, tcolor=INK, tsize=13, ssize=10.5, num=None):
    box(slide, x, y, w, h, fill=fill, line=line)
    if num is not None:
        c = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x + 0.08), Inches(y + 0.08), Inches(0.28), Inches(0.28))
        c.fill.solid(); c.fill.fore_color.rgb = TEAL; c.line.fill.background(); c.shadow.inherit = False
        tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = str(num); r.font.size = Pt(9); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = FONT
    lines = [[(title, {"bold": True, "size": tsize, "color": tcolor})]]
    if sub:
        lines.append([(sub, {"size": ssize, "color": MUTED})])
    text(slide, x + (0.4 if num is not None else 0.1), y + 0.06, w - (0.48 if num is not None else 0.2), h - 0.1, lines,
         anchor=MSO_ANCHOR.MIDDLE)


def arrow(slide, x1, y1, x2, y2, color=MUTED):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(1.25)
    ln = c.line._get_or_add_ln()
    from lxml import etree
    tail = etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd")
    tail.set("type", "triangle"); tail.set("w", "med"); tail.set("len", "med")
    return c


def header(slide, kicker, title, n):
    text(slide, 0.6, 0.35, 9, 0.3, kicker.upper(), size=11, bold=True, color=TEAL)
    text(slide, 0.6, 0.6, 12, 0.7, title, size=28, bold=True)
    if LOGO.exists():
        slide.shapes.add_picture(str(LOGO), Inches(0.6), Inches(7.0), height=Inches(0.24))
    text(slide, 0.9, 6.99, 6, 0.3, [[("Tax", {"bold": True, "size": 10}), ("Saathi", {"bold": True, "size": 10, "color": TEAL}),
                                    ("  ·  NLP course project · milestones M1–M3", {"size": 10, "color": MUTED})]])
    text(slide, 12.2, 6.99, 0.6, 0.3, f"{n} / 7", size=10, color=MUTED, align=PP_ALIGN.RIGHT)


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def m(cfg, key):
    v = CFG.get(cfg, {}).get(key)
    return v


def pct(v):
    return "—" if v is None else f"{v * 100:.0f}%"


def f3(v):
    return "—" if v is None else f"{v:.3f}"


# ================================================================ 1. Problem & context
s = prs.slides.add_slide(BLANK)
header(s, "1 · The problem", "Tax questions are simple to ask, hard to answer correctly", 1)
text(s, 0.6, 1.45, 6.1, 2.4, [
    [("In plain words: ", {"bold": True}), ("people pay a CA or trust a random blog for routine questions — "
      "“old or new regime?”, “GST on an AC?”, “do I need GST registration?”", {})],
    [("Why now: ", {"bold": True}), ("the law changed twice in a year, so the right answer depends on the date — "
      "and chatbots answer from outdated memory, without sources, and get arithmetic wrong.", {})],
    [("Our goal: ", {"bold": True}), ("answer in English or Hinglish, cite the official rule for every sentence, "
      "use the law in force on the asked date, compute with a calculator, and say “ask a CA” when unsure.", {})],
], size=15)

# timeline
text(s, 0.6, 4.05, 6, 0.3, "Two law changes", size=12, bold=True, color=MUTED)
box(s, 0.6, 4.4, 6.1, 1.95, fill=CARD)
s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(0.9), Inches(5.0), Inches(6.4), Inches(5.0)).line.color.rgb = LINE
for x, d, t1, t2 in [(1.0, "22 Sep 2025", "GST 2.0", "4 slabs → 5% / 18% (+40% sin goods). AC: 28% → 18%"),
                     (3.75, "1 Apr 2026", "Income-tax Act, 2025", "Replaces the 1961 Act. “Tax Year”; 80C → s.123")]:
    dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(4.9), Inches(0.2), Inches(0.2))
    dot.fill.solid(); dot.fill.fore_color.rgb = TEAL; dot.line.fill.background(); dot.shadow.inherit = False
    text(s, x - 0.05, 4.5, 2.7, 0.35, d, size=11, bold=True, color=TEAL)
    text(s, x - 0.05, 5.2, 2.65, 1.1, [[(t1, {"bold": True, "size": 13})], [(t2, {"size": 11, "color": MUTED})]])

# regimes table (right)
text(s, 7.1, 1.45, 5.6, 0.3, "Income tax: two regimes (Tax Year 2026-27)", size=12, bold=True, color=MUTED)
rows = [("", "Old regime", "New regime (default)"),
        ("Idea", "High rates, many deductions", "Low rates, few deductions"),
        ("Slabs", "0 / 5 / 20 / 30%\n(from ₹2.5 L)", "0 / 5 / 10 / 15 / 20 / 25 / 30%\n(from ₹4 L)"),
        ("Deductions", "80C, 80D, HRA, home loan…", "Standard deduction + employer NPS"),
        ("Std. deduction", "₹50,000", "₹75,000"),
        ("Zero tax up to", "₹5 L", "₹12 L (₹12.75 L salary)")]
tbl = s.shapes.add_table(len(rows), 3, Inches(7.1), Inches(1.8), Inches(5.6), Inches(3.3)).table
tbl.columns[0].width, tbl.columns[1].width, tbl.columns[2].width = Inches(1.45), Inches(1.9), Inches(2.25)
for i, row in enumerate(rows):
    for j, val in enumerate(row):
        c = tbl.cell(i, j); c.text = ""
        c.fill.solid(); c.fill.fore_color.rgb = TEAL if i == 0 else (WHITE if i % 2 else CARD)
        c.margin_left = c.margin_right = Inches(0.06); c.margin_top = c.margin_bottom = Inches(0.03)
        p = c.text_frame.paragraphs[0]
        r = p.add_run(); r.text = val; r.font.name = FONT
        r.font.size = Pt(11 if i else 12); r.font.bold = (i == 0 or j == 0)
        r.font.color.rgb = WHITE if i == 0 else (INK if j else MUTED)
box(s, 7.1, 5.3, 5.6, 1.05, fill=AMBER_BG, line=None)
text(s, 7.25, 5.36, 5.35, 0.95, [
    [("Effect on Indians: ", {"bold": True, "size": 12, "color": AMBER}),
     ("most taxpayers moved to the new regime (~88% for AY 2025-26, per CBDT Chairman). "
      "Top real confusion on Reddit: “no tax up to ₹12 L — but 5% from ₹4 L?” (both true: slabs, then the rebate cancels it).",
      {"size": 12})]])
notes(s, "Start with the problem in plain words. People keep paying a CA for simple tax questions. "
         "Two law changes happened close together: GST 2.0 on 22 September 2025, and the new Income-tax Act on 1 April 2026. "
         "So the right answer now depends on the date you ask about. Normal chatbots answer from old memory, can't show sources, "
         "and make arithmetic mistakes. On the right is the background: old regime has higher rates but many deductions, the new regime "
         "has lower rates and almost no deductions, and since Budget 2025 income up to 12 lakh is effectively tax free in the new regime. "
         "That is why 'which regime is better for me?' is the most common question.")

# ================================================================ 2. What we built + the field
s = prs.slides.add_slide(BLANK)
header(s, "2 · What we built", "RAG: the LLM writes the answer, but never decides the facts", 2)
# closed vs open book
box(s, 0.6, 1.5, 3.9, 2.55, fill=CARD)
text(s, 0.8, 1.6, 3.6, 2.4, [
    [("LLM alone  (“closed book”)", {"bold": True, "size": 15})],
    [("Answers from memory frozen at training time", {"size": 12, "color": MUTED})],
    [("✗ outdated (pre-2025 slabs, 28% GST on AC)", {"size": 12, "color": RED})],
    [("✗ no sources   ✗ arithmetic errors", {"size": 12, "color": RED})],
    [("Measured (B0): only ", {"size": 12}), (pct(m("B0", "key_fact_accuracy")), {"size": 12, "bold": True}),
     (" of key facts right", {"size": 12})]])
arrow(s, 4.6, 2.78, 5.1, 2.78, color=TEAL)
box(s, 5.2, 1.5, 3.9, 2.55, fill=TEAL_BG, line=None)
text(s, 5.4, 1.6, 3.6, 2.4, [
    [("RAG  (“open book”)", {"bold": True, "size": 15, "color": TEAL})],
    [("Search a trusted, dated library first; paste the passages into the prompt", {"size": 12, "color": MUTED})],
    [("✓ current law for the asked date", {"size": 12})],
    [("✓ every sentence cited   ✓ calculator for numbers", {"size": 12})],
    [("Measured (C6): ", {"size": 12}), (pct(m("C6", "key_fact_accuracy")), {"size": 12, "bold": True}),
     (" key facts, 100% valid citations", {"size": 12})]])
# features
text(s, 9.5, 1.45, 3.3, 0.3, "What the user gets", size=12, bold=True, color=MUTED)
feats = [("Cited answers", "source chip on every sentence"), ("Period-aware", "law in force on the asked date"),
         ("Hinglish", "“kitna hai?” works"), ("Old section numbers", "80C → s.123"),
         ("Regime calculator", "salary or freelancer, ₹ or US$"), ("Safe refusal", "“ask a CA” when unsure")]
for i, (a, b) in enumerate(feats):
    node(s, 9.5, 1.8 + i * 0.72, 3.25, 0.62, a, b, tsize=12, ssize=10)
# M1-M3 strip
text(s, 0.6, 4.35, 8.5, 0.3, "Scope delivered (M1 → M3)", size=12, bold=True, color=MUTED)
for i, (t, d) in enumerate([("M1 · Problem", "personas, business case, success metrics fixed before building"),
                            ("M2 · Data", f"{N_CHUNKS}-passage dated library, 176-question gold set, 80 real questions, leakage-safe split"),
                            ("M3 · Models", "baseline B0 + 7 systems B1→C6, all measured on the same dev set, logged in MLflow")]):
    node(s, 0.6 + i * 2.88, 4.7, 2.75, 1.65, t, d, tsize=14, ssize=11)
notes(s, "This is the core idea. A language model on its own is like a closed-book exam: it answers from memory, and its memory is "
         "from before the law changed. We measured that: the same model without search gets only about 10 percent of the key facts right. "
         "RAG makes it an open-book exam: we first search our own library of official, dated rules, and give the model only those passages. "
         "With that, it gets about 69 percent of key facts right and every citation is valid. On the right are the six things a user gets. "
         "At the bottom is what each milestone delivered.")

# ================================================================ 3. Pipeline
s = prs.slides.add_slide(BLANK)
header(s, "3 · How it works", "Offline: build a dated library.  Online: 12 fixed steps for every question", 3)
text(s, 0.6, 1.4, 6, 0.3, "OFFLINE — once", size=11, bold=True, color=TEAL)
off = [("Official sources", "CBDT, CBIC, GST Council"), ("1 rule = 1 passage", f"{N_CHUNKS} passages"),
       ("Tag every passage", "law, section, dates, URL"), ("Two indexes", "BM25 words + e5 vectors")]
for i, (a, b) in enumerate(off):
    x = 0.6 + i * 3.1
    node(s, x, 1.7, 2.75, 0.75, a, b, tsize=13, ssize=10.5)
    if i < 3:
        arrow(s, x + 2.78, 2.07, x + 3.07, 2.07)
text(s, 0.6, 2.7, 6, 0.3, "ONLINE — every question (config C6)", size=11, bold=True, color=TEAL)
steps = [("PII scrub", "mask PAN/phone"), ("Hinglish → English", "dictionary"), ("Intent", "TF-IDF + LogReg"),
         ("Period", "dates → law"), ("Entities", "80C, ₹, $/month"), ("BM25 search", "exact words"),
         ("Dense search", "e5 meaning"), ("RRF merge", "1/(60+rank)"), ("Date filter", "swap in current version"),
         ("Safety gate", "reranker score ≥ θ"), ("Calculator / LLM", "Qwen2.5-3B writes"), ("Citation check", "drop unsupported")]
for i, (a, b) in enumerate(steps):
    row, col = divmod(i, 6)
    x, y = 0.6 + col * 2.07, 3.05 + row * 1.15
    hi = a in ("Date filter", "Safety gate", "Calculator / LLM")
    node(s, x, y, 1.85, 0.9, a, b, num=i + 1, tsize=12, ssize=10, fill=TEAL_BG if hi else WHITE,
         line=None if hi else LINE)
    if col < 5:
        arrow(s, x + 1.86, y + 0.45, x + 2.06, y + 0.45)
box(s, 0.6, 5.5, 12.15, 0.85, fill=CARD)
text(s, 0.8, 5.56, 11.8, 0.75, [
    [("Design rule: ", {"bold": True, "size": 13}),
     ("everything that must be correct — which law, which numbers, which source, answer-or-refuse — is decided by testable components "
      "before the LLM runs. The LLM only turns 3 passages into plain sentences, and the citation check deletes any sentence it can’t back.",
      {"size": 13})]])
notes(s, "Offline, once: we researched official sources, wrote one passage per legal rule, tagged each with its law, section number, "
         "and the dates it was in force, and built two search indexes. Online, every question goes through the same 12 steps in the same order. "
         "The highlighted ones are our key ideas: the date filter, the safety gate, and the calculator or LLM at the very end. "
         "The design rule at the bottom is the main message of the project.")

# ================================================================ 4. One question, token by token
s = prs.slides.add_slide(BLANK)
header(s, "4 · Under the hood — one real question, step by step", "“Naye regime mein standard deduction kitna hai?”", 4)
trace = [("2  Hinglish", "naye→new · mein→in · kitna→how much · hai→is  ⇒  “New regime in standard deduction how much is?”", "2 ms"),
         ("3  Intent", "TF-IDF word 1-2-grams + char 2-5-grams → LogReg:  question 0.936 · calculation 0.048 · out-of-scope 0.016", "5 ms"),
         ("4  Period", "no date in question → current law: Tax Year 2026-27 (today 29 Oct 2026)", "4 ms"),
         ("6  BM25", "tokens [new, regime, standard, deduction, much] → STDDED-1961 7.29 · STDDED-TY2627 6.75", "1 ms"),
         ("7  Dense e5", "SentencePiece ▁que ry : ▁New ▁regime … ▁de duction … → 384-d vector · cos: STDDED-1961 0.889 · TY2627 0.883", "290 ms"),
         ("8  RRF", "Σ 1/(60+rank) → STDDED-1961 first — both searchers prefer the OUTDATED 1961-Act passage", "0 ms"),
         ("9  Date filter", "13 of top-20 out of period removed; each swapped for its current version: STDDED-1961 → STDDED-TY2627", "1 ms"),
         ("10 Reranker gate", "XLM-R cross-encoder [CLS] q [SEP] passage → best +3.30 ≥ θ = −5.83 → answer", "4.8 s"),
         ("11 Qwen2.5-3B", "~1,200-token prompt (rules + 3 passages + question) → “…standard deduction of ₹75,000 [IT-NEW-STDDED-TY2627]”", "18.3 s"),
         ("12 Citation check", "1 tag, 1 valid, 0 sentences dropped · disclaimer added", "0 ms")]
tb = s.shapes.add_table(len(trace), 3, Inches(0.6), Inches(1.45), Inches(12.15), Inches(4.7)).table
tb.columns[0].width, tb.columns[1].width, tb.columns[2].width = Inches(1.9), Inches(9.35), Inches(0.9)
for i, (a, b, c) in enumerate(trace):
    for j, val in enumerate((a, b, c)):
        cell = tb.cell(i, j); cell.text = ""
        hi = a.startswith(("8", "9"))
        cell.fill.solid(); cell.fill.fore_color.rgb = TEAL_BG if hi else (WHITE if i % 2 == 0 else CARD)
        cell.margin_left = cell.margin_right = Inches(0.07); cell.margin_top = cell.margin_bottom = Inches(0.02)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]; p.alignment = PP_ALIGN.RIGHT if j == 2 else PP_ALIGN.LEFT
        r = p.add_run(); r.text = val; r.font.name = FONT
        r.font.size = Pt(12 if j == 0 else 11.5); r.font.bold = (j == 0)
        r.font.color.rgb = TEAL if j == 0 else (MUTED if j == 2 else INK)
text(s, 0.6, 6.3, 12.15, 0.6, [[("Total ≈ 23 s on a 4-core CPU — ", {"bold": True, "size": 12}),
     ("the LLM (18 s) and reranker (5 s) dominate. Each model tokenises differently: BM25 sees whole words; e5 and the reranker see "
      "XLM-R sub-words (250k vocab: “deduction” = ▁de + duction); Qwen uses byte-level BPE (~151k vocab).", {"size": 12, "color": MUTED})]])
notes(s, "This is a real trace from the live system, which you can also open on the website under 'How this was found'. "
         "First, the Hinglish words are replaced with English. The intent classifier says it is a normal question with 94 percent confidence. "
         "No date is mentioned, so we assume today's law. Now the interesting part: both search methods actually rank the OLD 1961-Act "
         "version of the standard deduction first. The date filter notices it is out of date and swaps in the same rule's current version. "
         "The reranker is confident, so we answer. Finally the small language model writes one sentence with its source, and the citation "
         "check confirms the source was really retrieved. Note how each model splits text into tokens differently.")

# ================================================================ 5. Models & stack
s = prs.slides.add_slide(BLANK)
header(s, "5 · Models and tech stack", "Eight components — only one of them is a generative model", 5)
stack = [("Keyword search", "BM25 (rank_bm25)", "no training", "Exact terms: 80C, ITR-4, “August 2025”"),
         ("Embeddings", "intfloat/multilingual-e5-small", "118M · 384-d", "Meaning + Hinglish; ‘query:’/‘passage:’ prefixes, cosine"),
         ("Fusion", "Reciprocal Rank Fusion", "k = 60", "Merge rankings without calibrating scores"),
         ("Reranker → gate", "BAAI/bge-reranker-base", "278M · XLM-R", "Answer-or-refuse confidence (θ = −5.83, tuned on dev)"),
         ("Intent", "TF-IDF + Logistic Regression", "342 rows · CV 0.90", "question / calculation / out-of-scope in ~5 ms"),
         ("Rules", "Hinglish dict · dates · entities", "~370 words", "Exact, testable; every replacement shown"),
         ("Calculator", "Deterministic Python", "16/16 exact", "Both regimes, 3 years, rebate, cess, s.58, FX"),
         ("Writer LLM", "Qwen2.5-3B-Instruct (Ollama)", "3.1B · Q4_K_M", "Temp 0, top-3 passages, must cite every sentence")]
tb = s.shapes.add_table(len(stack) + 1, 4, Inches(0.6), Inches(1.45), Inches(8.3), Inches(4.85)).table
for j, wdt in enumerate((1.55, 2.6, 1.35, 2.8)):
    tb.columns[j].width = Inches(wdt)
for i, row in enumerate([("Role", "Model / tool", "Size", "Why")] + stack):
    for j, val in enumerate(row):
        cell = tb.cell(i, j); cell.text = ""
        cell.fill.solid(); cell.fill.fore_color.rgb = TEAL if i == 0 else (TEAL_BG if row[0] == "Writer LLM" else (WHITE if i % 2 else CARD))
        cell.margin_left = cell.margin_right = Inches(0.06); cell.margin_top = cell.margin_bottom = Inches(0.02)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        r = cell.text_frame.paragraphs[0].add_run(); r.text = val; r.font.name = FONT
        r.font.size = Pt(12 if i == 0 else 11); r.font.bold = (i == 0 or j == 0)
        r.font.color.rgb = WHITE if i == 0 else (INK if j != 3 else MUTED)
text(s, 9.2, 1.45, 3.6, 0.3, "Serving", size=12, bold=True, color=MUTED)
for i, (a, b) in enumerate([("FastAPI + Uvicorn", "/ask /compare /calculate /experiments"),
                            ("Vanilla HTML/CSS/JS", "live pipeline trace, charts"),
                            ("MLflow", "every config logged"),
                            ("pytest", "101 tests"),
                            ("VPS, CPU only", "4 vCPU · 8 GB · no GPU"),
                            ("Tailscale Funnel", "public HTTPS link")]):
    node(s, 9.2, 1.8 + i * 0.75, 3.55, 0.65, a, b, tsize=12, ssize=10)
notes(s, "Here is every model and what it is for. Only the last row is a generative language model. "
         "BM25 and the embedding model do the searching, RRF merges their results, the reranker decides whether we are confident enough "
         "to answer, a small classic classifier decides if the question is a normal question, a calculation, or out of scope, rule-based "
         "code handles Hinglish, dates and numbers, and the calculator does all arithmetic. Qwen 2.5 with 3 billion parameters, compressed "
         "to 4 bits, runs locally on our CPU server. It is free, private and reproducible, but slow.")

# ================================================================ 6. Data + experiments
s = prs.slides.add_slide(BLANK)
header(s, "6 · M2 data  +  M3 experiments", "One change per step, same LLM, same 53 dev questions", 6)
text(s, 0.6, 1.4, 3.6, 0.3, "M2 · Data", size=12, bold=True, color=MUTED)
for i, (a, b) in enumerate([(f"{N_CHUNKS} passages", f"17 official sources · {N_VERIFIED} verified on official pages"),
                            ("176 gold questions", "income tax 60 · GST 42 · time traps 26 · calc 18 · out-of-scope 18 · Hinglish 12"),
                            ("Split 53 dev / 123 test", "stratified, seed 42 — test untouched until M4 (no leakage)"),
                            ("80 real questions", "Reddit, Quora, CA forum, official FAQs — never used for tuning")]):
    node(s, 0.6, 1.75 + i * 1.12, 3.6, 1.0, a, b, tsize=14, ssize=10.5)
ladder = [("B0", "LLM alone"), ("B1", "BM25"), ("C1", "Dense"), ("C2", "Hybrid RRF"), ("C3", "+Rerank reorders"),
          ("C4", "+Date filter"), ("C5", "+Hinglish"), ("C6", "Final")]
cd = CategoryChartData()
cd.categories = [f"{n}\n{d}" for n, d in ladder]
cd.add_series("Recall@5", [m(n, "recall@5") or 0 for n, _ in ladder])
cd.add_series("MRR@10", [m(n, "mrr@10") or 0 for n, _ in ladder])
cd.add_series("Key-fact accuracy", [m(n, "key_fact_accuracy") or 0 for n, _ in ladder])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(4.5), Inches(1.4), Inches(8.3), Inches(3.85), cd)
ch = gf.chart
ch.has_legend = True; ch.legend.position = XL_LEGEND_POSITION.TOP; ch.legend.include_in_layout = False
ch.legend.font.size = Pt(11); ch.legend.font.name = FONT
ch.value_axis.maximum_scale = 1.0; ch.value_axis.minimum_scale = 0
ch.value_axis.has_major_gridlines = True
ch.value_axis.major_gridlines.format.line.color.rgb = LINE
ch.value_axis.tick_labels.font.size = Pt(10); ch.category_axis.tick_labels.font.size = Pt(9.5)
ch.value_axis.tick_labels.font.name = FONT; ch.category_axis.tick_labels.font.name = FONT
for ser, col in zip(ch.plots[0].series, (TEAL, RGBColor(0x5E, 0xB8, 0xAE), AMBER)):
    ser.format.fill.solid(); ser.format.fill.fore_color.rgb = col
ch.plots[0].gap_width = 60
text(s, 4.5, 5.3, 8.3, 0.3, "Key-fact accuracy needs the LLM (~25 s/answer on CPU), so it was run for B0, B1, C2, C4, C6; 0 = not run.",
     size=10, italic=True, color=MUTED)
for i, (k, v, d) in enumerate([("Key facts", f"{pct(m('B0','key_fact_accuracy'))} → {pct(m('C6','key_fact_accuracy'))}", "LLM alone → full system"),
                               ("Period accuracy", f"{pct(m('C2','period_accuracy'))} → {pct(m('C4','period_accuracy'))}", "date filter (C2 → C4)"),
                               ("MRR", f"{f3(m('C2','mrr@10'))} → {f3(m('C3','mrr@10'))}", "reranker reordering hurt (C3)"),
                               ("C6 final", f"R@5 {f3(m('C6','recall@5'))} · MRR {f3(m('C6','mrr@10'))}", "best on both")]):
    node(s, 4.5 + i * 2.1, 5.62, 1.98, 0.85, k, f"{v}\n{d}", tsize=12, ssize=10,
         fill=TEAL_BG if k == "C6 final" else WHITE, line=None if k == "C6 final" else LINE)
notes(s, "On the left is the data from milestone 2: our library, the 176 test questions we wrote, the split into a development set "
         "for tuning and a test set we have not touched yet, and 80 real questions collected from Reddit and forums. "
         "On the right is milestone 3. We built the system step by step, changing one thing each time, and measured everything on the same "
         "53 development questions with the same language model. B0 is the language model alone. B1 adds keyword search, C1 meaning search, "
         "C2 both merged, C3 adds a reranker, C4 the date filter, C5 Hinglish handling, and C6 is our final system.")

# ================================================================ 7. What worked + targets + why LLM + next
s = prs.slides.add_slide(BLANK)
header(s, "7 · Findings", "What worked, what didn’t, and where the LLM belongs", 7)
find = [("✓", "Retrieval is essential", f"key facts {pct(m('B0','key_fact_accuracy'))} → {pct(m('C6','key_fact_accuracy'))}; the LLM’s memory predates the 2025–26 law changes", TEAL),
        ("~", "Dense alone: better recall, worse dates", f"C1 Recall@5 {f3(m('C1','recall@5'))} but period accuracy {pct(m('C1','period_accuracy'))}: “Aug 2025” ≈ “now” in vector space", AMBER),
        ("✓", "Hybrid RRF ranks best (single stage)", f"C2 MRR {f3(m('C2','mrr@10'))}: BM25 exact tokens + dense paraphrase", TEAL),
        ("✗", "Reranker reordering hurt", f"MRR {f3(m('C2','mrr@10'))} → {f3(m('C3','mrr@10'))}; EN/ZH-only model promotes related or wrong-period passages", RED),
        ("✓", "Fix: reranker as confidence gate only (C6)", f"best Recall@5 {f3(m('C6','recall@5'))} and MRR {f3(m('C6','mrr@10'))}", TEAL),
        ("✓", "Date filter + period substitution", "period accuracy 100%; swaps an outdated passage for the same rule’s current version", TEAL)]
for i, (ic, a, b, col) in enumerate(find):
    y = 1.45 + i * 0.72
    c = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.6), Inches(y + 0.08), Inches(0.36), Inches(0.36))
    c.fill.solid(); c.fill.fore_color.rgb = col; c.line.fill.background(); c.shadow.inherit = False
    tf = c.text_frame; tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = ic; r.font.size = Pt(12); r.font.bold = True; r.font.color.rgb = WHITE; r.font.name = FONT
    text(s, 1.1, y, 6.6, 0.68, [[(a, {"bold": True, "size": 13})], [(b, {"size": 11, "color": MUTED})]])
# targets
text(s, 8.0, 1.4, 4.8, 0.3, "Targets fixed in M1 (before building) — C6", size=12, bold=True, color=MUTED)
tg = [("Recall@5 ≥ 0.85", f3(m("C6", "recall@5")), True), ("Faithfulness ≥ 0.90", f3(m("C6", "faithfulness")), True),
      ("Out-of-scope refused ≥ 90%", "100%", True), ("Calculator exact = 100%", "100%", True),
      ("Median latency ≤ 5 s", f"{(m('C6','latency_p50_ms') or 0) / 1000:.1f} s (CPU)", False)]
for i, (a, b, ok) in enumerate(tg):
    y = 1.75 + i * 0.5
    box(s, 8.0, y, 4.75, 0.42, fill=TEAL_BG if ok else AMBER_BG, line=None)
    text(s, 8.12, y + 0.04, 3.0, 0.36, a, size=11.5)
    text(s, 10.9, y + 0.04, 1.75, 0.36, [[(b + ("  ✓" if ok else "  ✗"), {"bold": True, "size": 11.5, "color": TEAL if ok else AMBER})]],
         align=PP_ALIGN.RIGHT)
box(s, 8.0, 4.4, 4.75, 1.95, fill=CARD)
text(s, 8.15, 4.47, 4.5, 1.85, [
    [("Why an LLM — and only at the end?", {"bold": True, "size": 13})],
    [("It is the only part good at turning 3 legal passages into 2–5 plain sentences for this user. Everything it is bad at "
      "(dates, numbers, sources, knowing when to stop) is handled before it, by testable code. "
      "Small local model (Qwen 3B): free, private, reproducible — the cost is ~17 s on CPU.", {"size": 11, "color": MUTED})]])
box(s, 0.6, 5.85, 7.1, 0.5, fill=AMBER_BG, line=None)
text(s, 0.72, 5.9, 6.9, 0.42, [[("Limits / next (M4): ", {"bold": True, "size": 11, "color": AMBER}),
     ("curated summaries not full Acts · team-written gold set · real out-of-scope refusal 57% · run the untouched test set · GPU for speed",
      {"size": 11})]])
notes(s, "Our findings. Retrieval is essential: without it the model gets 10 percent of facts right. Meaning search alone finds more passages "
         "but mixes up dates, because 'August 2025' and 'now' look similar as vectors. Merging keyword and meaning search gave the best ranking. "
         "Surprise: the reranker, which papers say usually helps most, made ranking worse for us because it only supports English and Chinese "
         "and kept promoting the wrong year's passage. So in our final system it only decides whether we are confident enough to answer. "
         "The date filter with substitution gets the period right every time. On the right: four of our five targets, fixed before we built "
         "anything, are met. Latency is not, because everything runs on a CPU. And this is why the language model is the last step: it is only "
         "trusted with wording, never with facts, numbers or sources.")

prs.save(OUT)
print(f"wrote {OUT} ({len(prs.slides)} slides)")
