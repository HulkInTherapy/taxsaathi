"""Build the TaxSaathi class presentation (presentation/TaxSaathi.pptx).

Run from the repo root (needs python-pptx):
    .venv/bin/python presentation/build_deck.py

Reads experiments/results.json, experiments/real_results.json, data/processed/chunks.jsonl,
data/eval/gold.jsonl and data/eval/real_questions.jsonl at build time, so the data and results
slides refresh whenever those files change. Missing metrics are shown as an em dash.

Look: matches the live app (calm near-white, zinc greys, one deep-teal accent #0F766E,
amber only for "ask a CA"). Font: Calibri (metric-safe in PowerPoint and LibreOffice).
Screenshots in presentation/assets/ were taken from the live app on 29 Oct 2026.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
PRES_DIR = ROOT / "presentation"
ASSETS = PRES_DIR / "assets"
OUT = PRES_DIR / "TaxSaathi.pptx"
RESULTS = ROOT / "experiments" / "results.json"
REAL_RESULTS = ROOT / "experiments" / "real_results.json"
CHUNKS = ROOT / "data" / "processed" / "chunks.jsonl"
GOLD = ROOT / "data" / "eval" / "gold.jsonl"
REAL_Q = ROOT / "data" / "eval" / "real_questions.jsonl"
LOGO = ASSETS / "logo.png"

# ---------------------------------------------------------------- palette & type (from app/static/style.css)
BG = RGBColor(0xF7, 0xF8, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SUBTLE = RGBColor(0xF4, 0xF4, 0xF5)
INK = RGBColor(0x0A, 0x0A, 0x0A)
INK2 = RGBColor(0x27, 0x27, 0x2A)
INK3 = RGBColor(0x52, 0x52, 0x5B)
MUTED = RGBColor(0x71, 0x71, 0x7A)
FAINT = RGBColor(0xA1, 0xA1, 0xAA)
LINE = RGBColor(0xE4, 0xE4, 0xE7)
TEAL = RGBColor(0x0F, 0x76, 0x6E)
TEAL_INK = RGBColor(0x11, 0x5E, 0x59)
TEAL_SOFT = RGBColor(0xF0, 0xFD, 0xFA)
TEAL_TINT = RGBColor(0xCC, 0xFB, 0xF1)
MINT = RGBColor(0x99, 0xF6, 0xE4)
AMBER_BG = RGBColor(0xFF, 0xFB, 0xEB)
AMBER_INK = RGBColor(0x92, 0x40, 0x0E)
AMBER = RGBColor(0xB4, 0x53, 0x09)
RED = RGBColor(0xB9, 0x1C, 0x1C)
RED_BG = RGBColor(0xFE, 0xF2, 0xF2)
BAR_GREY = RGBColor(0xD4, 0xD4, 0xD8)
BAR_GREY2 = RGBColor(0x71, 0x71, 0x7A)
FONT = "Calibri"

DASH = "—"
SW, SH = Inches(13.333), Inches(7.5)


# ---------------------------------------------------------------- data loading
def load_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"configs": []}


RES = load_json(RESULTS)
CONFIGS = RES.get("configs", [])
CFG = {c["name"]: c for c in CONFIGS}
REAL = load_json(REAL_RESULTS)
REAL_CFG = {c["name"]: c for c in REAL.get("configs", [])}
CHUNK_ROWS = load_jsonl(CHUNKS)
GOLD_ROWS = load_jsonl(GOLD)
REAL_ROWS = load_jsonl(REAL_Q)

ORDER = ["B0", "B1", "C1", "C2", "C3", "C4", "C5", "C6"]
FINAL = "C6"


def metric(cfg: str, key: str):
    v = CFG.get(cfg, {}).get("metrics", {}).get(key)
    return v if isinstance(v, (int, float)) else None


def fmt(v, digits=2) -> str:
    return DASH if v is None else f"{v:.{digits}f}"


def pct(v, digits=0) -> str:
    return DASH if v is None else f"{v * 100:.{digits}f}%"


def rpct(v) -> str:
    """Percent rounded half-up (0.225 -> 23%)."""
    return f"{int(v * 100 + 0.5)}%"


def secs(ms) -> str:
    return DASH if ms is None else f"{ms / 1000:.1f} s"


# headline numbers (all from results.json)
R5, MRR, NDCG = metric(FINAL, "recall@5"), metric(FINAL, "mrr@10"), metric(FINAL, "ndcg@5")
PER, OOS, FALSE_REF = metric(FINAL, "period_accuracy"), metric(FINAL, "oos_refusal_rate"), metric(FINAL, "false_refusal_rate")
CALC = metric(FINAL, "calc_accuracy")
KF, KF_B0 = metric(FINAL, "key_fact_accuracy"), metric("B0", "key_fact_accuracy")
CIT, FAITH = metric(FINAL, "citation_validity"), metric(FINAL, "faithfulness")
LAT = metric(FINAL, "latency_p50_ms")
DEV_N, TEST_N = RES.get("dev_size", 53), RES.get("test_size", 123)
N_UNIT_TESTS = 99          # tests/ (pytest), see docs/M3_experiment_log.md
N_GOLD_CALCS = 16          # hand-worked gold calculations, all exact
N_INTENT_ROWS, INTENT_CV = 342, 0.90

n_chunks = len(CHUNK_ROWS) or 107
n_docs = len({c.get("doc_id") for c in CHUNK_ROWS}) or 17
n_ver = sum(1 for c in CHUNK_ROWS if c.get("verified") == "yes") if CHUNK_ROWS else 72
n_gold = len(GOLD_ROWS) or 176

real_n = REAL.get("n", len(REAL_ROWS) or 80)
real_cov = REAL.get("coverage", {"full": 51, "partial": 18, "none": 11})
real_src = Counter(r.get("source_type") for r in REAL_ROWS) or Counter(reddit=36, official_faq=25, forum=12, quora=7)
real_c6 = REAL_CFG.get(FINAL, {})
REAL_EXACT = real_c6.get("by_coverage", {}).get("full", {}).get("recall@5", 0.6225)
REAL_RULE = 0.78           # rule-level Recall@5 on fully covered questions (docs/report_draft.md §7.3)
REAL_OOS = real_c6.get("oos_refused_rate", 0.571)


# ---------------------------------------------------------------- helpers
prs = Presentation()
prs.slide_width, prs.slide_height = SW, SH
TITLE_ONLY = prs.slide_layouts[5]
BLANK = prs.slide_layouts[6]
_slide_no = 0


def _font(run, size, color=INK2, bold=False, italic=False, font=FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font
    run.font.color.rgb = color


def text(slide, x, y, w, h, content, size=18, color=INK2, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, italic=False, margin=0.0, spacing=6, name=None, line=None):
    """content: str | list of paragraphs; a paragraph is str or list of (text, opts) runs."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        tb.name = name
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    m = Inches(margin)
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = m
    paras = content if isinstance(content, list) else [content]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(spacing)
        if line:
            p.line_spacing = line
        runs = para if isinstance(para, list) else [(para, {})]
        for t, o in runs:
            r = p.add_run()
            r.text = t
            _font(r, o.get("size", size), o.get("color", color), o.get("bold", bold), o.get("italic", italic))
    return tb


def box(slide, x, y, w, h, fill=WHITE, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, name=None,
        line_w=1.0):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if name:
        s.name = name
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(line_w)
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    for ref in s._element.iter(qn("a:effectRef")):  # no theme shadow
        ref.set("idx", "0")
    s.text_frame.text = ""
    return s


def card(slide, x, y, w, h, fill=WHITE, line=LINE, radius=0.05):
    return box(slide, x, y, w, h, fill=fill, line=line, radius=radius)


def shape_text(s, content, size=18, color=INK2, bold=False, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
               margin=0.08, spacing=0):
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    m = Inches(margin)
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = m
    paras = content if isinstance(content, list) else [content]
    for i, para in enumerate(paras):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(spacing)
        runs = para if isinstance(para, list) else [(para, {})]
        for t, o in runs:
            r = p.add_run()
            r.text = t
            _font(r, o.get("size", size), o.get("color", color), o.get("bold", bold), o.get("italic", False))
    return s


def badge(slide, x, y, d, label, fill=TEAL, color=WHITE, size=18):
    c = box(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    shape_text(c, label, size=size, color=color, bold=True, margin=0)
    return c


def pill(slide, x, y, w, h, label, fill=TEAL_SOFT, color=TEAL_INK, size=14, line=None, bold=True):
    p = box(slide, x, y, w, h, fill=fill, line=line, radius=0.5)
    shape_text(p, label, size=size, color=color, bold=bold, margin=0.02)
    return p


def arrow(slide, x1, y1, x2, y2, color=FAINT, width=1.75):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = etree.SubElement(ln, qn("a:tailEnd"))
    tail.set("type", "triangle")
    tail.set("w", "med")
    tail.set("len", "med")
    return c


def picture(slide, path, x, y, w=None, h=None, crop=None, border=True):
    """crop = (left, top, right, bottom) as fractions of the source image."""
    if not Path(path).exists():
        ph = box(slide, x, y, w or 4, h or 3, fill=SUBTLE, line=LINE)
        shape_text(ph, f"[missing image: {Path(path).name}]", size=14, color=MUTED)
        return ph
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y))
    if crop and w and h:  # keep aspect: trim the bottom crop so the visible area matches w:h
        px_w, px_h = pic.image.size
        vis_w_px = px_w * (1 - crop[0] - crop[2])
        crop = (crop[0], crop[1], crop[2], max(0.0, 1 - crop[1] - (h / w) * vis_w_px / px_h))
    if crop:
        pic.crop_left, pic.crop_top, pic.crop_right, pic.crop_bottom = crop
    nat_w, nat_h = pic.width, pic.height
    vis_w = nat_w * (1 - (crop[0] + crop[2] if crop else 0))
    vis_h = nat_h * (1 - (crop[1] + crop[3] if crop else 0))
    ratio = vis_h / vis_w
    if w and not h:
        pic.width, pic.height = Inches(w), Emu(int(Inches(w) * ratio))
    elif h and not w:
        pic.height, pic.width = Inches(h), Emu(int(Inches(h) / ratio))
    elif w and h:
        pic.width, pic.height = Inches(w), Emu(int(Inches(w) * ratio))
    if border:
        pic.line.color.rgb = LINE
        pic.line.width = Pt(1)
    return pic


def pic_bottom(pic) -> float:
    return (pic.top + pic.height) / 914400


def notes(slide, s: str):
    slide.notes_slide.notes_text_frame.text = s.strip()


def set_bg(slide, color=BG):
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = color


def footer(s):
    if LOGO.exists():
        s.shapes.add_picture(str(LOGO), Inches(0.6), Inches(6.98), Inches(0.26), Inches(0.26))
    text(s, 0.95, 6.97, 6, 0.3, [[("Tax", {"bold": True, "color": INK}), ("Saathi", {"bold": True, "color": TEAL}),
                                  ("   ·   NLP course project", {"color": MUTED})]], size=12, name="Footer",
         anchor=MSO_ANCHOR.MIDDLE)
    text(s, 11.73, 6.97, 1.0, 0.3, str(_slide_no), size=12, color=MUTED, align=PP_ALIGN.RIGHT, name="SlideNumber",
         anchor=MSO_ANCHOR.MIDDLE)


def new_slide(title: str, kicker: str | None = None):
    """Content slide: a real title placeholder (outline / accessibility), styled consistently."""
    global _slide_no
    _slide_no += 1
    s = prs.slides.add_slide(TITLE_ONLY)
    set_bg(s)
    t = s.shapes.title
    t.left, t.top, t.width, t.height = Inches(0.6), Inches(0.72), Inches(12.1), Inches(0.75)
    tf = t.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    r = p.add_run()
    r.text = title
    _font(r, 32, INK, bold=True)
    if kicker:
        text(s, 0.6, 0.38, 9, 0.32, kicker.upper(), size=13, bold=True, color=TEAL, name="Kicker")
    footer(s)
    return s


def style_chart(ch, size=13):
    ch.font.size = Pt(size)
    ch.font.name = FONT
    ch.font.color.rgb = INK3


# ================================================================ SLIDES
# 1. Title ---------------------------------------------------------------------------------
_slide_no += 1
s = prs.slides.add_slide(BLANK)
set_bg(s)
if LOGO.exists():
    s.shapes.add_picture(str(LOGO), Inches(0.75), Inches(0.95), Inches(1.15), Inches(1.15))
text(s, 0.72, 2.3, 6.6, 1.1, [[("Tax", {"color": INK}), ("Saathi", {"color": TEAL})]], size=64, bold=True)
text(s, 0.75, 3.45, 6.2, 1.4, "Ask an Indian tax question. Get a short answer that cites the official rule, "
     "for the right date.", size=24, color=INK3, line=1.05)
# logo decode
for i, (k, v) in enumerate([("Speech bubble", "your companion"), ("Folded corner", "an official source"),
                            ("Check", "verified")]):
    x = 0.75 + i * 2.1
    text(s, x, 5.05, 2.0, 0.3, k, size=14, bold=True, color=TEAL_INK)
    text(s, x, 5.35, 2.0, 0.3, v, size=14, color=MUTED)
text(s, 0.75, 6.15, 6.4, 0.7, [[("4th-year NLP course project", {"bold": True, "color": INK2}),
                                ("   ·   Team of 4   ·   29 October 2026", {"color": MUTED})]], size=16)
picture(s, ASSETS / "shot_ask.jpg", 7.45, 0.95, w=5.25, crop=(0.22, 0.0, 0.22, 0.14))
text(s, 7.45, 6.2, 5.25, 0.4, "The live app, 29 Oct 2026", size=12, color=MUTED, italic=True)
notes(s, """
Good morning. We are presenting TaxSaathi.
"Saathi" means companion. It is a helper for Indian tax questions: income tax and GST, in English or in Hinglish.
Look at our logo. It is a speech bubble, because you chat with it. The top corner is folded like a page, because every answer comes from an official document. And there is a check mark, because the answer is checked: right law, right date, and every sentence has a source.
Three more promises. It knows the law changed, so it checks which date you mean. If it is not sure, it says so and sends you to a Chartered Accountant. And it never lets the AI do maths; a normal calculator program does that.
On the right is the real app, running live on our server.
""")

# 2. The problem ---------------------------------------------------------------------------
s = new_slide("Simple tax questions still need a paid CA", "The problem")
cards = [
    ("Pay a CA", "Typical fee ₹1,500–2,000, even for a one-line answer"),
    ("Search the web", "Old blog posts and pre-reform rates, all mixed together"),
    ("Ask a chatbot", "Sounds confident, shows no source, may not know the new law"),
]
for i, (head, body) in enumerate(cards):
    x = 0.6 + i * 4.1
    card(s, x, 1.8, 3.8, 2.65)
    badge(s, x + 0.35, 2.1, 0.62, str(i + 1), fill=SUBTLE, color=INK3, size=18)
    text(s, x + 0.35, 2.9, 3.2, 0.5, head, size=22, bold=True, color=INK)
    text(s, x + 0.35, 3.42, 3.15, 0.95, body, size=17, color=MUTED)
text(s, 0.6, 4.75, 3.8, 0.9, "7.8 crore+", size=48, bold=True, color=TEAL)
text(s, 0.6, 5.65, 3.8, 0.6, "income-tax returns filed for AY 2026-27", size=16, color=MUTED)
text(s, 4.7, 4.75, 3.8, 0.9, "1.67 crore", size=48, bold=True, color=TEAL)
text(s, 4.7, 5.65, 3.8, 0.6, "active GST taxpayers (June 2026)", size=16, color=MUTED)
box(s, 8.8, 4.8, 3.9, 1.5, fill=TEAL_SOFT, line=MINT)
text(s, 9.05, 4.8, 3.45, 1.5, "Most of these questions need one paragraph of the law, not a consultation.",
     size=18, bold=True, color=TEAL_INK, anchor=MSO_ANCHOR.MIDDLE)
notes(s, """
Here is the problem.
Most tax questions in India are simple. Which regime is better for me? What is the GST on cement now?
Today people have three options.
One: pay a CA. That costs money and time, even for a one-line answer.
Two: search the web. You get old blog posts mixed with new rules.
Three: ask a chatbot. It sounds sure of itself, but it shows no source, and it may not know the new law.
The scale is large. More than 7.8 crore income-tax returns were filed this year, and there are 1.67 crore GST taxpayers.
Our point: most of these questions only need one paragraph of the law, with a clear source.
""")

# 3. Why now -------------------------------------------------------------------------------
s = new_slide("Two big law changes in seven months", "Why now")
box(s, 0.9, 2.98, 11.5, 0.05, fill=LINE, shape=MSO_SHAPE.RECTANGLE)
for x, date, head, body in [
    (1.3, "22 Sep 2025", "GST 2.0", "Most goods now 5% or 18%; a 40% rate for a few luxury and 'sin' goods"),
    (7.0, "1 Apr 2026", "Income-tax Act, 2025", "Replaces the 1961 Act: new section numbers and a new idea, the 'Tax Year'"),
]:
    badge(s, x, 2.75, 0.5, "", fill=TEAL)
    text(s, x - 0.05, 1.85, 5.2, 0.6, date, size=26, bold=True, color=TEAL)
    card(s, x - 0.1, 3.5, 5.2, 1.9)
    text(s, x + 0.2, 3.7, 4.7, 0.5, head, size=22, bold=True, color=INK)
    text(s, x + 0.2, 4.25, 4.7, 1.1, body, size=18, color=MUTED)
box(s, 0.9, 5.75, 11.5, 0.95, fill=AMBER_BG, line=RGBColor(0xFD, 0xE6, 0x8A))
text(s, 1.15, 5.75, 11.0, 0.95, [[("Same question, different answer.  ", {"bold": True, "color": AMBER_INK}),
                                   ("\"GST on an AC?\" was 28% in August 2025. It is 18% today.", {"color": INK2})]],
     size=20, anchor=MSO_ANCHOR.MIDDLE)
notes(s, """
Why build this now? Because the law changed twice, very quickly.
First, on 22 September 2025, GST 2.0 started. Most things now have 5% or 18% GST. A few luxury items have 40%.
Second, on 1 April 2026, a brand-new Income-tax Act came into force. It replaces the Act from 1961.
Section numbers changed. For example, the famous section 80C is now section 123. And it uses a new term, the "Tax Year".
So the same question has different answers depending on the date.
GST on an air conditioner was 28% in August 2025. Today it is 18%.
A chatbot trained on older internet text cannot know which one you mean. So in our system, the date is part of the question.
""")

# 4. Personas ------------------------------------------------------------------------------
s = new_slide("Who it is for", "Three people we designed for")
people = [
    ("P", "Priya, 23", "First salaried job, never filed", "\"Old regime ya new regime, kaunsa better hai? Salary 9.5 lakh hai.\"",
     "A regime comparison she can trust"),
    ("A", "Arjun, 27", "Freelancer, works for foreign clients", "\"I earn $5k a month remote. How much tax do I pay?\"",
     "Right income type, and a clear 'see a CA' when it gets complex"),
    ("R", "Ramesh-ji, 52", "Hardware-shop owner, tier-3 town", "\"22 September ke baad cement pe GST kitna hai?\"",
     "Short, date-correct GST answers in Hinglish"),
]
for i, (ini, name, who, q, need) in enumerate(people):
    x = 0.6 + i * 4.1
    card(s, x, 1.75, 3.8, 4.85)
    badge(s, x + 0.3, 2.02, 0.8, ini, fill=TEAL_SOFT, color=TEAL_INK, size=22)
    text(s, x + 1.3, 2.0, 2.4, 0.42, name, size=21, bold=True, color=INK)
    text(s, x + 1.3, 2.42, 2.4, 0.5, who, size=14, color=MUTED)
    text(s, x + 0.3, 3.2, 3.25, 1.6, q, size=18, italic=True, color=INK2)
    text(s, x + 0.3, 4.95, 3.25, 0.32, "NEEDS", size=12, bold=True, color=TEAL)
    text(s, x + 0.3, 5.27, 3.25, 1.2, need, size=17, color=INK2)
notes(s, """
We designed for three people.
Priya is 23. She just got her first job. She wants to know: old regime or new regime? She often types in Hinglish.
Arjun is 27. He works remotely for foreign clients and is paid in dollars. He asks: I earn 5 thousand dollars a month, how much tax do I pay?
His case can get complicated, so he also needs the system to say "please see a CA" at the right time.
Ramesh-ji is 52. He runs a small hardware shop. He asks about GST on cement, in Hinglish, and the date matters a lot to him.
These personas are written by our team, but Arjun's question is almost word for word one that a real user typed into our app.
""")

# 5. What TaxSaathi does -------------------------------------------------------------------
s = new_slide("What TaxSaathi does: five promises", "The product")
feats = [
    ("Cites every sentence", "\"Standard deduction is ₹75,000\" [1]  →  the card opens the official source"),
    ("Uses the law for your date", "\"GST on AC in August 2025?\"  →  28% (the old rate), not today's 18%"),
    ("Understands how people talk", "\"naye regime mein kitna\", \"1 lakh mahina\", \"$5k per month\""),
    ("Says \"ask a CA\" when it should", "\"How do I avoid tax on foreign crypto?\"  →  polite refusal + CA link"),
    ("Exact maths, by a calculator", "₹12 lakh salary  →  old regime ₹1,63,800, new regime ₹0"),
]
for i, (head, ex) in enumerate(feats):
    y = 1.72 + i * 1.0
    badge(s, 0.6, y + 0.13, 0.6, str(i + 1), fill=TEAL, size=18)
    text(s, 1.45, y, 4.3, 0.86, head, size=21, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    card(s, 5.85, y, 6.85, 0.86)
    text(s, 6.1, y, 6.45, 0.86, ex, size=17, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
notes(s, """
TaxSaathi makes five promises.
One: every sentence has a citation, like a footnote. You can click it and see the official source.
Two: it uses the law for your date. Ask about August 2025, and you get the old GST rate.
Three: it understands how people really talk: Hinglish, "1 lakh mahina", or "5k dollars per month".
Four: it knows its limits. If you ask how to avoid tax on foreign crypto, it refuses politely and points you to a CA.
Five: the tax maths is done by a normal calculator program, not by the AI. On a 12 lakh salary, the new regime tax is zero and the old regime is 1 lakh 63 thousand 8 hundred.
""")

# 6. Landscape -----------------------------------------------------------------------------
s = new_slide("Isn't this already solved?", "Landscape")
cols = [
    ("Kar Saathi", "Income Tax Dept, April 2026",
     ["AI assistant in the new e-filing portal", "Filing, notices, refunds", "Accuracy and languages not published"]),
    ("ClearTax and similar", "Paid assisted filing",
     ["Experts file for you", "Plans from about ₹999", "Sells filing, not explanations"]),
    ("General chatbots", "ChatGPT-style assistants",
     ["Fluent answers", "No sources, no dates", "Even legal RAG tools hallucinate 17–33% (Magesh et al.)"]),
]
for i, (head, sub, pts) in enumerate(cols):
    x = 0.6 + i * 3.1
    card(s, x, 1.75, 2.85, 4.3)
    text(s, x + 0.25, 1.95, 2.4, 0.45, head, size=20, bold=True, color=INK)
    text(s, x + 0.25, 2.42, 2.4, 0.4, sub, size=14, color=MUTED, italic=True)
    text(s, x + 0.25, 3.0, 2.4, 3.0, [[("•  " + p, {})] for p in pts], size=16, spacing=9, color=INK2)
box(s, 9.9, 1.75, 2.8, 4.3, fill=TEAL)
text(s, 10.15, 1.95, 2.4, 0.45, "TaxSaathi", size=20, bold=True, color=WHITE)
text(s, 10.15, 2.42, 2.4, 0.4, "Open research prototype", size=14, color=MINT, italic=True)
text(s, 10.15, 3.0, 2.4, 3.0, [[("•  " + p, {})] for p in
                                ["Every sentence cited, with dates", "Full step-by-step trace", "Published evaluation",
                                 "Free; hands hard cases to a CA"]], size=16, color=WHITE, spacing=9)
text(s, 0.6, 6.3, 12.1, 0.45, "TaxSaathi is a student project and is not linked to the Income Tax Department.",
     size=14, color=MUTED, italic=True)
notes(s, """
Is this already solved? Partly.
In April 2026 the Income Tax Department launched its own assistant, called Kar Saathi, inside the new filing portal.
We could not find published accuracy numbers or language support for it.
Companies like ClearTax sell assisted filing: an expert files for you, for a fee.
General chatbots are fluent, but they show no sources and no dates.
One study found that even legal research tools built on retrieval still make things up 17 to 33 percent of the time.
Our project is different in one way: everything is open. You see the source, the dates, every step, and our test results.
To be clear, we are a student project with no link to the government.
""")

# 7. System design (C6) --------------------------------------------------------------------
s = new_slide("How it works: build a library once, then answer each question", "System design · final version C6")
card(s, 0.6, 1.62, 12.1, 1.5, fill=SUBTLE, line=None)
text(s, 0.85, 1.7, 6, 0.32, "ONCE, BEFORE ANY QUESTION", size=12, bold=True, color=MUTED)
off = [("Official sources", "Acts 1961 & 2025, GST notices"), ("Short cards", "one rule each"),
       ("Date stickers", "valid from … to …"), ("Two indexes", "keywords + meaning")]
for i, (h, b) in enumerate(off):
    x = 0.85 + i * 3.0
    c = card(s, x, 2.08, 2.55, 0.86)
    shape_text(c, [[(h, {"bold": True, "size": 16, "color": INK})], [(b, {"size": 13, "color": MUTED})]], margin=0.04)
    if i < 3:
        arrow(s, x + 2.57, 2.51, x + 2.98, 2.51)
text(s, 0.6, 3.38, 6, 0.32, "EVERY QUESTION", size=12, bold=True, color=TEAL)
on = [("Tidy up", "hide PAN · fix Hinglish"), ("Sort", "question / maths / off-topic"), ("Find the date", "which year's law?"),
      ("Search twice", "keywords + meaning, merged"), ("Date filter", "swap in the right year's version"),
      ("Safety gate", "reranker scores confidence")]
w, gap = 1.82, 0.236
for i, (h, b) in enumerate(on):
    x = 0.6 + i * (w + gap)
    key = i in (3, 4, 5)
    c = card(s, x, 3.78, w, 1.12, fill=TEAL_SOFT if key else WHITE, line=MINT if key else LINE)
    shape_text(c, [[(h, {"bold": True, "size": 16, "color": TEAL_INK if key else INK})],
                   [(b, {"size": 12, "color": MUTED})]], margin=0.05)
    if i < len(on) - 1:
        arrow(s, x + w + 0.01, 4.34, x + w + gap - 0.01, 4.34)
outs = [("Calculator", "all the numbers", WHITE, LINE, INK, 0.6),
        ("AI writer", "Qwen2.5-3B, on our server", WHITE, LINE, INK, 3.15),
        ("Fact-check", "cited sentences only", WHITE, LINE, INK, 5.7),
        ("Answer", "with sources + dates", TEAL, None, WHITE, 8.25),
        ("Ask a CA", "off-topic or unsure", AMBER_BG, RGBColor(0xFD, 0xE6, 0x8A), AMBER_INK, 10.65)]
for h, b, f, ln, col, x in outs:
    ww = 2.05 if h == "Ask a CA" else 2.2
    c = card(s, x, 5.45, ww, 1.05, fill=f, line=ln)
    shape_text(c, [[(h, {"bold": True, "size": 16, "color": col})],
                   [(b, {"size": 12, "color": MINT if f == TEAL else MUTED})]], margin=0.05)
arrow(s, 2.82, 5.98, 3.13, 5.98)
arrow(s, 5.37, 5.98, 5.68, 5.98)
arrow(s, 7.92, 5.98, 8.23, 5.98)
arrow(s, 11.65, 4.92, 11.65, 5.43, color=AMBER)
arrow(s, 10.5, 4.92, 4.3, 5.43, color=TEAL)
notes(s, """
This is the whole system on one slide. There are two parts.
The grey part at the top is done once. Think of it as stocking a library.
We take official documents, cut them into small cards with one rule each, and put a date sticker on each card saying when that rule was valid. Then we build two indexes, like two catalogues for the same library.
The middle row runs for every question.
We hide personal numbers like PAN, and we fix Hinglish words. A small classifier sorts the question: a normal question, a maths question, or off-topic. We find the date the person is asking about.
Then we search twice and merge the results. The date filter removes cards from the wrong year, and if a card is out of date, it swaps in the same rule's version for that year.
The safety gate uses a second model, called a reranker, only to judge how confident we are. It does not change the order. That was an important lesson, which we show later.
At the bottom: numbers come from the calculator, the small AI model on our own server writes the explanation, and a fact-checker removes any sentence without a valid source.
If the question is off-topic or we are unsure, we refuse and suggest a CA.
This exact version is called C6, our final system. The teal boxes are explained on the next slides.
""")

# 8. Search twice & merge ------------------------------------------------------------------
s = new_slide("Search twice, then merge the two lists", "Step 1 · retrieval")
card(s, 0.6, 1.75, 3.9, 2.45)
text(s, 0.85, 1.92, 3.5, 0.45, "Keyword search (BM25)", size=20, bold=True, color=INK)
text(s, 0.85, 2.45, 3.45, 0.9, "Like the index at the back of a book: finds the exact words.", size=17, color=MUTED)
text(s, 0.85, 3.4, 3.45, 0.7, "Great for \"80C\", \"Form 16\", \"44ADA\"", size=17, italic=True, color=INK2)
card(s, 0.6, 4.45, 3.9, 2.3)
text(s, 0.85, 4.62, 3.5, 0.45, "Meaning search (embeddings)", size=20, bold=True, color=INK)
text(s, 0.85, 5.15, 3.45, 1.5, "Finds cards that mean the same thing in other words: \"tax kam kaise karein\" → deductions",
     size=17, color=MUTED)
arrow(s, 4.55, 3.0, 5.4, 3.95, color=TEAL, width=2.5)
arrow(s, 4.55, 5.6, 5.4, 4.65, color=TEAL, width=2.5)
c = box(s, 5.45, 3.35, 2.65, 1.9, fill=TEAL)
shape_text(c, [[("Merge (RRF)", {"bold": True, "size": 20, "color": WHITE})],
               [("score = 1 / (60 + rank)", {"size": 14, "color": MINT})],
               [("added up over both lists", {"size": 14, "color": MINT})]])
arrow(s, 8.15, 4.3, 8.7, 4.3, color=TEAL, width=2.5)
text(s, 8.85, 1.75, 3.9, 0.45, "Merged top 5 (illustration)", size=18, bold=True, color=INK)
ranks = [("IT-DED-80C", "high in both lists", TEAL), ("IT-MAP-80C", "high in one", TEAL_INK),
         ("IT-DED-80CCD1B", "high in one", TEAL_INK), ("IT-DED-80D", "lower", FAINT),
         ("IT-NEW-STDDED-TY2627", "lower", FAINT)]
for i, (cid, why, col) in enumerate(ranks):
    y = 2.3 + i * 0.86
    badge(s, 8.85, y + 0.08, 0.52, str(i + 1), fill=col, size=15)
    text(s, 9.55, y, 3.2, 0.4, cid, size=16, bold=True, color=INK)
    text(s, 9.55, y + 0.38, 3.2, 0.4, why, size=14, color=MUTED)
text(s, 5.2, 5.6, 3.3, 1.1, "Uses rank, not raw score, so the two searches never need to agree on a scale.",
     size=14, color=MUTED, italic=True)
notes(s, """
Our first step is search. We search in two different ways.
The first is keyword search, called BM25. It is like the index at the back of a textbook. It is very good at exact things like "80C" or "Form 16".
The second is meaning search, using embeddings. An embedding turns a sentence into a list of numbers, so sentences with similar meaning get similar numbers.
It can match "tax kam kaise karein" to the deductions card, even though the words are different.
Each search gives a ranked list. We merge them with Reciprocal Rank Fusion, or RRF.
Think of two judges in a competition. A card ranked high by both judges goes to the top. A card only one judge liked still gets a chance.
The formula: each card gets 1 divided by 60 plus its rank, added up over both lists.
The IDs on the right are an illustration of how this works.
""")

# 9. Date filter + period substitution + Hinglish ------------------------------------------
s = new_slide("Every card has a date sticker", "Step 2 · the right year's law")
text(s, 0.6, 1.65, 7.4, 0.45, "\"What was GST on AC in August 2025?\"", size=20, bold=True, color=INK)
cards9 = [("GST-RATE-AC-PRE", "AC at 28%", "1 Jul 2017 → 21 Sep 2025", True),
          ("GST-RATE-AC-POST", "AC at 18%", "22 Sep 2025 → today", False)]
for i, (cid, body, dates, keep) in enumerate(cards9):
    x = 0.6 + i * 3.7
    card(s, x, 2.3, 3.45, 1.85, fill=TEAL_SOFT if keep else RED_BG, line=MINT if keep else RGBColor(0xFE, 0xCA, 0xCA))
    pill(s, x + 0.2, 2.45, 2.9, 0.38, dates, fill=WHITE, color=INK3, size=13, line=LINE)
    text(s, x + 0.2, 2.98, 3.0, 0.4, cid, size=15, bold=True, color=INK)
    text(s, x + 0.2, 3.35, 3.0, 0.4, body, size=18, color=INK2)
    text(s, x + 0.2, 3.72, 3.1, 0.38, "KEPT: in force in Aug 2025" if keep else "REMOVED: not yet in force",
         size=13, bold=True, color=TEAL if keep else RED)
card(s, 0.6, 4.4, 7.15, 1.08)
text(s, 0.85, 4.45, 6.75, 1.0, [
    [("New: period swap.  ", {"bold": True, "color": TEAL_INK}),
     ("If a card is from the wrong year, the same rule's version for your year takes its place. "
      "Years before our sources keep the closest version.", {})]], size=16, anchor=MSO_ANCHOR.MIDDLE)
card(s, 0.6, 5.65, 7.15, 1.08)
text(s, 0.85, 5.68, 6.75, 1.0, [
    [("Hinglish phrasebook (rules, not AI):  ", {"bold": True, "color": TEAL_INK}),
     ("\"salary pe tax kitna lagega\"  →  \"salary on tax how much will apply\". Tax words like 80C are never changed.",
      {})]], size=16, anchor=MSO_ANCHOR.MIDDLE)
p9 = picture(s, ASSETS / "shot_live_ac_trace.jpg", 8.0, 1.65, w=4.7, crop=(0.615, 0.505, 0.0, 0.0))
text(s, 8.0, pic_bottom(p9) + 0.08, 4.7, 0.5, "Live trace: the date filter removed 8 of the top 20 passages",
     size=12, color=MUTED, italic=True)
notes(s, """
Our second step is about time.
Every card in our library has a date sticker: valid from this date, to that date.
The question is: what was the GST on an AC in August 2025?
We have two cards. One says 28 percent, valid until 21 September 2025. The other says 18 percent, valid from 22 September.
Because the question says August 2025, the date filter keeps the first card and removes the second.
New since our last update: period swap. If search finds the right rule but the wrong year's version, we do not just throw it away. We replace it with the same rule's version for the year you asked about. And if you ask about a year before our sources start, we keep the closest version instead of answering nothing.
On the right is the real trace from the live app. For this question the date filter removed 8 of the top 20 passages.
At the bottom: Hinglish. We use a simple phrasebook. "kitna" becomes "how much", "pe" becomes "on". Tax words like 80C are never changed. It is just a list of rules, so it is fast and easy to check.
""")

# 10. Safety: gate + fact-checker ----------------------------------------------------------
s = new_slide("Two safety checks: a bouncer and a fact-checker", "Step 3 · guardrails")
card(s, 0.6, 1.75, 5.85, 4.95)
badge(s, 0.88, 2.0, 0.7, "1", fill=AMBER, size=20)
text(s, 1.78, 2.0, 4.5, 0.7, "The bouncer (safety gate)", size=22, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
text(s, 0.88, 2.95, 5.35, 3.7, [
    [("Stops the question if:", {"bold": True, "color": INK})],
    "•  the sorter says it is off-topic, or",
    "•  even the best card gets a low score from a careful second reader (the reranker)",
    [(f"Sorter: TF-IDF + logistic regression, {N_INTENT_ROWS} training examples, {INTENT_CV:.0%} in 5-fold "
      "cross-validation", {"size": 15, "color": MUTED})],
    [("Result: \"This needs a Chartered Accountant.\"", {"bold": True, "color": AMBER_INK})],
], size=18, spacing=10)
card(s, 6.85, 1.75, 5.85, 4.95)
badge(s, 7.13, 2.0, 0.7, "2", fill=TEAL, size=20)
text(s, 8.03, 2.0, 4.5, 0.7, "The fact-checker (citation check)", size=22, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
text(s, 7.13, 2.95, 5.35, 3.7, [
    [("Reads every sentence the AI wrote:", {"bold": True, "color": INK})],
    "•  no card ID, or a made-up ID  →  deleted",
    "•  a number the calculator did not produce  →  removed",
    "•  \"which regime is cheaper\" always comes from the calculator",
    [("If too little is left, we show the best card's own text.", {"size": 15, "color": MUTED})],
    [("Result: no claim without a source.", {"bold": True, "color": TEAL})],
], size=18, spacing=10)
notes(s, f"""
Our third step is safety. There are two checks.
The first is the bouncer at the door. It stops a question in two cases.
Case one: our sorter says the question is off-topic. The sorter is a simple classic model: TF-IDF plus logistic regression. It learned from {N_INTENT_ROWS} example questions, written separately from our test questions, and gets about {INTENT_CV:.0%} right in cross-validation.
Case two: a careful second reader, the reranker, reads the question and each card together. If even the best card gets a low score, we probably do not have the answer.
Then the system says: this needs a Chartered Accountant. Saying "I don't know" is a feature.
The second check is the fact-checker. The AI must put a card ID after every sentence. Any sentence with no ID, or a made-up ID, is deleted.
For calculation answers, any number the AI writes must come from the calculator, and the verdict, which regime is cheaper, always comes from the calculator. The AI only explains.
So every claim the user sees has a source.
""")

# 11. Calculator ---------------------------------------------------------------------------
s = new_slide("Maths is done by a calculator, never by the AI", "Step 4 · calculator")
text(s, 0.6, 1.7, 5.3, 1.3,
     "An AI doing tax maths is like a confident friend doing mental maths: usually close, sometimes badly wrong.",
     size=19, color=INK2)
stats = [(str(N_UNIT_TESTS), "unit tests pass, incl. hand-worked examples"),
         (f"{N_GOLD_CALCS}/{N_GOLD_CALCS}", "test calculations exactly right"),
         ("0", "numbers computed by the AI; it only explains")]
for i, (big, small) in enumerate(stats):
    y = 3.2 + i * 1.12
    text(s, 0.6, y, 1.75, 0.9, big, size=40 if len(big) < 4 else 32, bold=True, color=TEAL, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 2.4, y, 3.5, 0.9, small, size=17, color=INK3, anchor=MSO_ANCHOR.MIDDLE)
p11 = picture(s, ASSETS / "shot_calculator.jpg", 6.25, 1.75, w=6.45, crop=(0.455, 0.235, 0.14, 0.385))
text(s, 6.25, pic_bottom(p11) + 0.1, 6.45, 0.6, "Live Calculator tab: ₹12 lakh salary, Tax Year 2026-27. "
     "Old regime ₹1,63,800, new regime ₹0 (rebate under s.156 of the 2025 Act).", size=13, color=MUTED, italic=True)
notes(s, f"""
Our fourth step is the calculator.
Language models are bad at exact arithmetic. It is like asking a confident friend to do mental maths: usually close, sometimes badly wrong, and they never say "I'm not sure".
In tax, a small mistake costs real money. So the AI never computes anything.
We wrote a normal Python program instead. Same input, same output, every time. We call that deterministic.
It has {N_UNIT_TESTS} unit tests that pass, including examples we worked out by hand. On our answer key, all {N_GOLD_CALCS} calculation questions are exactly right.
It compares the old and new regime and says which one is cheaper. If you forget your salary, it asks you. It never guesses.
The screenshot is the live calculator. For a 12 lakh salary, the new regime tax is zero because of the rebate, and the old regime is 1 lakh 63 thousand 8 hundred.
""")

# 12. Data ---------------------------------------------------------------------------------
s = new_slide("Our data: a dated library and an answer key", "Data")
text(s, 0.6, 1.65, 6, 0.45, "Knowledge base (the library)", size=20, bold=True, color=INK)
kb = [(str(n_chunks), "short passages (cards)"), (str(n_docs), "official sources"),
      (str(n_ver), "checked word-for-word against official pages"), ("100%", "carry dates + a source link")]
for i, (big, small) in enumerate(kb):
    x = 0.6 + (i % 2) * 3.05
    y = 2.2 + (i // 2) * 1.55
    card(s, x, y, 2.85, 1.35)
    text(s, x + 0.25, y + 0.1, 2.5, 0.65, big, size=34, bold=True, color=TEAL)
    text(s, x + 0.25, y + 0.75, 2.5, 0.55, small, size=14, color=MUTED)
laws = Counter(c.get("law") for c in CHUNK_ROWS)
law_lbl = [("gst", "GST"), ("general", "General"), ("old_act", "1961 Act"), ("new_act", "2025 Act"), ("mapping", "Map")]
text(s, 0.6, 5.4, 6.1, 0.4, "  ·  ".join(f"{lbl} {laws.get(k, 0)}" for k, lbl in law_lbl
                                                                if laws.get(k)), size=14, color=INK3)
text(s, 0.6, 5.85, 5.9, 0.8, "Cards per law. Old and new versions of the same rule sit side by side, each with its own dates.",
     size=14, color=MUTED, italic=True)
cat_order = ["income_tax", "gst", "time_trap", "calculation", "out_of_scope", "hinglish"]
labels = {"income_tax": "Income tax", "gst": "GST", "time_trap": "Time traps", "calculation": "Calculations",
          "out_of_scope": "Off-topic", "hinglish": "Hinglish"}
cnt = Counter(r.get("category") for r in GOLD_ROWS)
text(s, 7.0, 1.65, 5.7, 0.45, f"Answer key: {n_gold} questions", size=20, bold=True, color=INK)
cd = CategoryChartData()
cats = [c for c in cat_order if cnt.get(c)] or cat_order
cd.categories = [labels[c] for c in reversed(cats)]
cd.add_series("Questions", [cnt.get(c, 0) for c in reversed(cats)])
gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(6.9), Inches(2.1), Inches(5.8), Inches(3.25), cd)
ch = gf.chart
style_chart(ch, 14)
ch.has_legend = False
ch.has_title = False
pl = ch.plots[0]
pl.gap_width = 55
pl.has_data_labels = True
pl.data_labels.font.size = Pt(14)
pl.data_labels.font.bold = True
pl.data_labels.font.color.rgb = INK2
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ser = pl.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = TEAL
ch.value_axis.visible = False
ch.value_axis.has_major_gridlines = False
ch.category_axis.format.line.color.rgb = LINE
ch.category_axis.tick_labels.font.size = Pt(14)
card(s, 7.0, 5.55, 5.7, 1.15, fill=SUBTLE, line=None)
text(s, 7.25, 5.55, 5.3, 1.15, [
    [(f"Split 30 / 70:  {DEV_N} dev  ·  {TEST_N} test", {"bold": True, "color": INK})],
    [("We tune only on dev. The test set stays sealed until the final run.", {"color": MUTED, "size": 15})],
], size=18, anchor=MSO_ANCHOR.MIDDLE, spacing=3)
notes(s, f"""
Now our data. There are two parts.
First, the knowledge base: our library. It has {n_chunks} short passages from {n_docs} official sources, like the Income-tax Acts of 1961 and 2025 and the GST Council notifications.
Every passage has dates and a source link. {n_ver} of them we checked word for word against the official pages; the rest against reputable secondary sources.
Old and new versions of the same rule sit side by side, each with its own dates. That is what makes the date filter and the period swap possible.
Second, the answer key, which we call the gold set. It has {n_gold} questions written by our team, with the correct passages and the key facts an answer must contain.
It includes {cnt.get('time_trap', 26)} time-trap questions where the answer depends on the date, {cnt.get('out_of_scope', 18)} off-topic questions that should be refused, and {cnt.get('hinglish', 12)} in Hinglish.
We split it 30 to 70. We tune on the {DEV_N} dev questions only. The {TEST_N} test questions stay sealed, like a final exam paper we have not looked at.
""")

# 13. Experiment design --------------------------------------------------------------------
s = new_slide("Experiment design: a ladder, one change per step", "Method")
steps = [("B0", "AI alone", "no search"), ("B1", "Keywords", "BM25"), ("C1", "Meaning", "embeddings"),
         ("C2", "Both, merged", "RRF"), ("C3", "+ reranker", "reorders"), ("C4", "+ date filter", ""),
         ("C5", "+ Hinglish", ""), ("C6", "Final", "reranker = gate only")]
for i, (code, h, b) in enumerate(steps):
    x = 0.6 + i * 1.53
    y = 1.75
    final = code == FINAL
    c = card(s, x, y, 1.38, 1.4, fill=TEAL if final else WHITE, line=None if final else LINE)
    col = WHITE if final else INK
    shape_text(c, [[(code, {"bold": True, "size": 22, "color": col})], [(h, {"size": 14, "color": col, "bold": True})]]
               + ([[(b, {"size": 12, "color": MINT if final else MUTED})]] if b else []), margin=0.04)
    if i < len(steps) - 1:
        arrow(s, x + 1.39, y + 0.7, x + 1.52, y + 0.7)
text(s, 0.6, 3.5, 5.6, 1.2, [
    [("Each step changes exactly one thing,", {"color": INK})],
    [("so any change in score comes from that one thing.", {"color": MUTED})],
], size=19, spacing=2)
meas = [("Recall@5", "is the right card in the top 5?"), ("MRR", "how near the top is it?"),
        ("Key facts", "does the written answer contain them?")]
for i, (k, v) in enumerate(meas):
    y = 4.65 + i * 0.68
    card(s, 0.6, y, 5.6, 0.56)
    text(s, 0.82, y, 1.4, 0.56, k, size=17, bold=True, color=TEAL, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 2.25, y, 3.9, 0.56, v, size=16, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
p13 = picture(s, ASSETS / "shot_experiments.jpg", 6.6, 3.55, w=6.1, crop=(0.13, 0.545, 0.127, 0.0))
text(s, 6.6, pic_bottom(p13) + 0.08, 6.1, 0.35, "The same ladder, live in the app's Results tab", size=12, color=MUTED,
     italic=True)
notes(s, """
How did we test this? With a ladder of experiments.
We start with the AI alone, B0. Then keyword search only, B1. Then meaning search only, C1. Then both merged, C2.
Then we add the reranker, then the date filter, then Hinglish. Finally C6, our final system.
The rule: each step changes exactly one thing. This is called an ablation study.
It is like cooking: add one spice at a time and taste after each, and you know which spice made the difference.
We measure three main things.
Recall at 5: is the right card somewhere in the top 5 results?
MRR, mean reciprocal rank: how close to the top is the first right card? First place scores 1, second place one half, third place one third.
Key facts: does the final written answer contain the facts from our answer key, like the right amount?
The app has a Results tab that shows this same ladder, shown on the right.
""")

# 14. Results: retrieval ladder ------------------------------------------------------------
s = new_slide("Results: the final system finds the right rule most often", f"Results · {DEV_N} dev questions")
names = [n for n in ORDER if n in CFG]
cd = CategoryChartData()
cd.categories = names
series = [("Recall@5 (right card in top 5)", "recall@5", BAR_GREY, MINT),
          ("MRR (how near the top)", "mrr@10", BAR_GREY2, TEAL)]
for label, key, _, _ in series:
    cd.add_series(label, [metric(n, key) for n in names])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.5), Inches(1.6), Inches(8.3), Inches(4.55), cd)
ch = gf.chart
style_chart(ch, 13)
ch.has_legend = True
ch.legend.position = XL_LEGEND_POSITION.TOP
ch.legend.include_in_layout = False
ch.legend.font.size = Pt(14)
pl = ch.plots[0]
pl.gap_width = 55
pl.overlap = -8
pl.has_data_labels = True
dl = pl.data_labels
dl.number_format = "0.00"
dl.number_format_is_linked = False
dl.font.size = Pt(11)
dl.font.color.rgb = INK3
dl.position = XL_LABEL_POSITION.OUTSIDE_END
fin_idx = names.index(FINAL) if FINAL in names else None
for (label, key, col, fcol), ser in zip(series, pl.series):
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = col
    if fin_idx is not None:
        pt = ser.points[fin_idx]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = fcol
va = ch.value_axis
va.minimum_scale, va.maximum_scale = 0.5, 1.0
va.major_unit = 0.1
va.has_major_gridlines = True
va.major_gridlines.format.line.color.rgb = LINE
va.format.line.fill.background()
va.tick_labels.font.size = Pt(12)
va.tick_labels.font.color.rgb = MUTED
va.tick_labels.number_format = "0.0"
va.tick_labels.number_format_is_linked = False
ch.category_axis.tick_labels.font.size = Pt(15)
ch.category_axis.tick_labels.font.bold = True
ch.category_axis.format.line.color.rgb = LINE
text(s, 0.6, 6.2, 8.2, 0.6, "B0 AI alone (no search, so no bar) · B1 keywords · C1 meaning · C2 both merged · "
     "C3 + reranker reorders · C4 + date filter · C5 + Hinglish · C6 final. Axis starts at 0.5.",
     size=12, color=MUTED, italic=True)
right = [(fmt(R5), "Recall@5", f"keywords alone: {fmt(metric('B1', 'recall@5'))}  ·  target 0.85"),
         (fmt(MRR), "MRR", f"keywords alone: {fmt(metric('B1', 'mrr@10'))}"),
         (fmt(PER), "period accuracy", f"meaning search alone: {fmt(metric('C1', 'period_accuracy'))}")]
for i, (big, lbl, sub) in enumerate(right):
    y = 1.7 + i * 1.5
    card(s, 9.2, y, 3.5, 1.32, fill=TEAL_SOFT if i == 0 else WHITE, line=MINT if i == 0 else LINE)
    text(s, 9.45, y + 0.08, 1.6, 0.7, big, size=34, bold=True, color=TEAL)
    text(s, 10.95, y + 0.2, 1.7, 0.5, lbl, size=15, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 9.45, y + 0.8, 3.15, 0.45, sub, size=13, color=MUTED)
c3m, c2m = metric("C3", "mrr@10"), metric("C2", "mrr@10")
card(s, 9.2, 6.12, 3.5, 0.68, fill=RED_BG, line=RGBColor(0xFE, 0xCA, 0xCA))
text(s, 9.35, 6.12, 3.3, 0.68, f"C3 dip: reranker reorders, MRR {fmt(c2m, 3)} → {fmt(c3m, 3)}", size=13, bold=True,
     color=RED, anchor=MSO_ANCHOR.MIDDLE)
notes(s, f"""
Here are the search results on the {DEV_N} dev questions. Higher is better. Light bars are Recall at 5, dark bars are MRR, and the teal pair is our final system.
B0, the AI alone, does not search at all, so it has no bars here. We judge it on the next slide.
Keyword search alone, B1, gets a Recall at 5 of {fmt(metric('B1', 'recall@5'))} and an MRR of {fmt(metric('B1', 'mrr@10'))}.
Meaning search alone, C1, finds the right card more often, but ranks it lower, and it gets the year wrong a quarter of the time.
Merging both, C2, gives the best balance of the simple systems.
Look at C3: when we let the reranker reorder the list, MRR dropped from {fmt(c2m, 3)} to {fmt(c3m, 3)}. That surprised us.
The date filter, C4, makes period accuracy perfect: the system always picks the law for the right date.
Our final system, C6, is the best on every search score: Recall at 5 of {fmt(R5)}, MRR of {fmt(MRR)}, and nDCG of {fmt(NDCG)}.
That means for about {round((R5 or 0) * 100)} out of 100 questions, the right card is in the top 5. Our target, set before building, was 0.85.
""")

# 15. Answers: same AI, with vs without retrieval -------------------------------------------
s = new_slide("Same AI model: 10% right alone, 69% with TaxSaathi", f"Results · answer quality, {DEV_N} dev questions")
card(s, 0.6, 1.7, 2.75, 2.4, fill=RED_BG, line=RGBColor(0xFE, 0xCA, 0xCA))
text(s, 0.85, 1.85, 2.3, 0.9, pct(KF_B0), size=54, bold=True, color=RED)
text(s, 0.85, 2.85, 2.3, 1.2, "key facts right: the AI alone (B0), answering from memory", size=15, color=INK3)
card(s, 3.6, 1.7, 2.75, 2.4, fill=TEAL_SOFT, line=MINT)
text(s, 3.85, 1.85, 2.3, 0.9, pct(KF), size=54, bold=True, color=TEAL)
text(s, 3.85, 2.85, 2.3, 1.2, f"key facts right: the same AI inside TaxSaathi ({FINAL})", size=15, color=INK3)
safety = [(fmt(CIT), "citations valid"), (fmt(FAITH), "sentences backed by a source"),
          (pct(OOS), "off-topic questions refused"), (pct(FALSE_REF, 1), "good questions wrongly refused")]
for i, (big, small) in enumerate(safety):
    x = 0.6 + (i % 2) * 2.95
    y = 4.35 + (i // 2) * 1.2
    card(s, x, y, 2.8, 1.05)
    text(s, x + 0.2, y, 1.15, 1.05, big, size=24, bold=True, color=TEAL if i != 3 else AMBER_INK, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 1.35, y, 1.4, 1.05, small, size=13, color=INK3, anchor=MSO_ANCHOR.MIDDLE)
gen_names = [n for n in ORDER if metric(n, "key_fact_accuracy") is not None]
cd = CategoryChartData()
cd.categories = gen_names
cd.add_series("Key facts right", [metric(n, "key_fact_accuracy") for n in gen_names])
gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(6.75), Inches(2.05), Inches(5.95), Inches(4.0), cd)
ch = gf.chart
style_chart(ch, 13)
ch.has_legend = False
ch.has_title = False
pl = ch.plots[0]
pl.gap_width = 70
pl.has_data_labels = True
pl.data_labels.number_format = "0%"
pl.data_labels.number_format_is_linked = False
pl.data_labels.font.size = Pt(15)
pl.data_labels.font.bold = True
pl.data_labels.font.color.rgb = INK2
pl.data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
ser = pl.series[0]
ser.format.fill.solid()
ser.format.fill.fore_color.rgb = BAR_GREY
for i, n in enumerate(gen_names):
    if n in ("B0", FINAL):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = RED if n == "B0" else TEAL
va = ch.value_axis
va.minimum_scale, va.maximum_scale = 0.0, 1.0
va.visible = False
va.has_major_gridlines = False
ch.category_axis.tick_labels.font.size = Pt(15)
ch.category_axis.tick_labels.font.bold = True
ch.category_axis.format.line.color.rgb = LINE
text(s, 6.85, 1.65, 5.8, 0.4, "Key facts right, by step (configs run with the AI writer)", size=16, bold=True, color=INK)
text(s, 6.85, 6.1, 5.85, 0.6, f"Median answer time {secs(LAT)} on our 4-core CPU server (no GPU).", size=13,
     color=MUTED, italic=True)
notes(s, f"""
This is the slide that matters most.
We took the same small AI model, Qwen 2.5 with 3 billion parameters, running on our own server.
Alone, answering from memory, it got the key facts right only {pct(KF_B0)} of the time. It states the old rules, like the old slabs and 28 percent GST on ACs, and it never cites anything.
Put the same model inside TaxSaathi, and it gets {pct(KF)} right. That is about six to seven times better, with no change to the model. Only the search, the dates and the checks changed.
And the answers are safe. Citation validity is {fmt(CIT)}: every citation points to a card we actually gave it. {fmt(FAITH)} of sentences are backed by a source. Every off-topic question was refused, and only {pct(FALSE_REF, 1)} of good questions were wrongly refused; that is one question out of 48.
The honest part: one answer takes about {secs(LAT)}, because the AI runs on a normal CPU without a graphics card.
""")

# 16. Targets scorecard --------------------------------------------------------------------
s = new_slide("Targets we set at the start: 4 of 5 met", "Scorecard")
rows = [("Finds the right card (Recall@5)", "≥ 0.85", fmt(R5), True),
        ("Answers backed by sources (faithfulness)", "≥ 0.90", fmt(FAITH), True),
        ("Refuses off-topic questions", "≥ 90%", f"{pct(OOS)}  ({pct(FALSE_REF, 1)} false)", True),
        ("Calculator exactly right", "100%", f"{pct(CALC)}  ({N_GOLD_CALCS}/{N_GOLD_CALCS})", True),
        ("Median answer time", "≤ 5 s", f"{secs(LAT)} on CPU", False)]
text(s, 0.6, 1.6, 5.6, 0.4, "Target (fixed in milestone 1)", size=14, bold=True, color=MUTED)
text(s, 6.4, 1.6, 1.6, 0.4, "Goal", size=14, bold=True, color=MUTED)
text(s, 8.1, 1.6, 2.9, 0.4, f"{FINAL} result", size=14, bold=True, color=MUTED)
for i, (name, goal, res, ok) in enumerate(rows):
    y = 2.05 + i * 0.9
    card(s, 0.6, y, 12.1, 0.76, fill=WHITE if ok else AMBER_BG, line=LINE if ok else RGBColor(0xFD, 0xE6, 0x8A))
    text(s, 0.85, y, 5.5, 0.76, name, size=19, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 6.4, y, 1.6, 0.76, goal, size=19, color=INK3, anchor=MSO_ANCHOR.MIDDLE)
    text(s, 8.1, y, 3.0, 0.76, res, size=19, bold=True, color=TEAL if ok else AMBER_INK, anchor=MSO_ANCHOR.MIDDLE)
    pill(s, 11.15, y + 0.17, 1.35, 0.42, "MET" if ok else "NOT YET", fill=TEAL if ok else AMBER,
         color=WHITE, size=13)
text(s, 0.6, 6.6, 12.1, 0.35, f"Dev set, {DEV_N} questions. Latency needs a GPU or a hosted model: planned for milestone 5.",
     size=13, color=MUTED, italic=True)
notes(s, f"""
At the very start of the project, in milestone 1, we wrote down five targets. Here is how the final system did.
Finding the right card: target 0.85, we got {fmt(R5)}. Met.
Answers backed by sources: target 0.90, we got {fmt(FAITH)}. Met. This is a simple automatic check; a stricter AI-judge version is planned.
Refusing off-topic questions: target 90 percent, we got {pct(OOS)}, with only {pct(FALSE_REF, 1)} false refusals. Met.
Calculator: target 100 percent exact, we got 100 percent, all {N_GOLD_CALCS} calculations. Met.
Speed: target 5 seconds. We got {secs(LAT)}. Not met. The time is almost all the AI model writing on a CPU. With a graphics card, or a hosted model, this should drop a lot. That is planned for milestone 5.
So: 4 of 5 targets met, and we know exactly why the fifth is not.
""")

# 17. What we learned ----------------------------------------------------------------------
s = new_slide("What we learned", "Three takeaways")
c1p, c4p = metric("C1", "period_accuracy"), metric("C4", "period_accuracy")
take = [
    ("1", "Two searches beat one", f"Keywords catch \"80C\"; meaning catches paraphrases. Merged, MRR went "
                                  f"{fmt(metric('B1', 'mrr@10'))} → {fmt(c2m)}.", TEAL),
    ("2", "Dates need rules, not hope", f"Meaning search alone picked the right year {pct(c1p)} of the time. "
                                         f"With the date filter: {pct(c4p)}.", TEAL),
    ("3", "Surprise: the \"smarter\" model hurt", f"Letting the reranker reorder dropped MRR {fmt(c2m, 3)} → {fmt(c3m, 3)}. "
                                                 f"Used only as a safety gate (C6): {fmt(MRR, 3)}.", RED),
]
for i, (n, head, body, col) in enumerate(take):
    x = 0.6 + i * 4.1
    card(s, x, 1.75, 3.8, 4.35, fill=RED_BG if col == RED else WHITE,
         line=RGBColor(0xFE, 0xCA, 0xCA) if col == RED else LINE)
    badge(s, x + 0.3, 2.0, 0.75, n, fill=col, size=22)
    text(s, x + 0.3, 2.95, 3.25, 1.0, head, size=22, bold=True, color=INK)
    text(s, x + 0.3, 3.95, 3.25, 2.1, body, size=18, color=INK2)
text(s, 0.6, 6.3, 12.1, 0.45, "The reranker's model card lists English and Chinese only. The multilingual version took "
     "about 25 s per question on our CPU: future work with a GPU.", size=14, color=MUTED, italic=True)
notes(s, f"""
We learned three things.
One: two searches are better than one. Keyword search is great at exact codes like 80C. Meaning search is great when people use different words. Together they cover each other's blind spots.
Two: dates need clear rules. Meaning search alone picked the right year only {pct(c1p)} of the time. With our date filter it became {pct(c4p)}. We did not hope the AI would figure out dates. We wrote the rule.
Three was a surprise. The reranker is a slower, more careful model. We expected it to improve the order. It made it worse: MRR dropped from {fmt(c2m, 3)} to {fmt(c3m, 3)}.
When we read its model card, we saw it was trained for English and Chinese only, and it often confused cards from different years.
So in our final system we kept the merged order and used the reranker only as the bouncer's confidence score. That gave our best result, an MRR of {fmt(MRR)}.
The lesson: measure every change. A fancier model is not always better.
""")

# 18. Real people, real questions ----------------------------------------------------------
s = new_slide("Real people, real questions", f"Real-world check · {real_n} questions, not used for tuning")
text(s, 0.6, 1.62, 3.0, 1.0, str(real_n), size=60, bold=True, color=TEAL)
text(s, 2.3, 1.75, 4.2, 0.9, "real questions people asked online, plus official FAQs", size=17, color=INK3,
     anchor=MSO_ANCHOR.MIDDLE)
src_lbl = [("reddit", "Reddit"), ("official_faq", "Official FAQs"), ("forum", "CAclubindia"), ("quora", "Quora")]
xx = 0.6
for k, lbl in src_lbl:
    t = f"{lbl}  {real_src.get(k, 0)}"
    w = 0.32 + 0.08 * len(t)
    pill(s, xx, 2.75, w, 0.42, t, fill=WHITE, color=INK2, size=13, line=LINE, bold=False)
    xx += w + 0.12
text(s, 0.6, 3.45, 6, 0.4, "Does our library cover them?", size=17, bold=True, color=INK)
tot = sum(real_cov.values()) or 1
segs = [("full", "Fully", TEAL, WHITE), ("partial", "Partly", MINT, TEAL_INK), ("none", "Not", BAR_GREY, INK3)]
xx, W = 0.6, 6.0
for k, lbl, f, tc in segs:
    w = W * real_cov.get(k, 0) / tot
    b = box(s, xx, 3.95, w, 0.75, fill=f, shape=MSO_SHAPE.RECTANGLE)
    shape_text(b, f"{lbl} {rpct(real_cov.get(k, 0) / tot)}", size=15 if w > 1.0 else 12, color=tc, bold=True, margin=0.02)
    xx += w
card(s, 0.6, 5.0, 6.0, 1.7)
text(s, 0.85, 5.08, 5.5, 1.55, [
    [("Most common real confusion (10 posts):", {"bold": True, "color": INK})],
    [("\"No tax up to ₹12 lakh, but 5% from ₹4 lakh?\"", {"italic": True})],
    [("Both are true (slabs + rebate). We added an explainer card.", {"color": TEAL_INK, "bold": True})],
], size=16, spacing=4)
card(s, 7.0, 1.7, 5.7, 2.45, fill=TEAL_SOFT, line=MINT)
text(s, 7.25, 1.8, 2.2, 1.0, f"{REAL_RULE:.0%}", size=48, bold=True, color=TEAL)
text(s, 9.2, 1.9, 3.35, 0.9, "right rule found, on fully covered questions", size=16, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
text(s, 7.25, 2.85, 5.25, 1.25, f"Exact passage: {REAL_EXACT:.2f}. Most of the gap is time: 2025 posts ask about last "
     "year's law, while TaxSaathi answers with today's.", size=14, color=INK3)
card(s, 7.0, 4.4, 5.7, 2.3, fill=AMBER_BG, line=RGBColor(0xFD, 0xE6, 0x8A))
text(s, 7.25, 4.5, 2.2, 1.0, f"{REAL_OOS:.0%}", size=48, bold=True, color=AMBER_INK)
text(s, 9.2, 4.6, 3.35, 0.9, "of real off-topic questions refused", size=16, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
text(s, 7.25, 5.55, 5.25, 1.05, "Real off-topic questions (NRI, crypto, US stocks) are harder than ours. "
     "Our clearest next step.", size=14, color=INK3)
notes(s, f"""
Our answer key was written by us. So we also checked TaxSaathi on real questions that real people asked.
We collected {real_n}: {real_src.get('reddit', 36)} from Reddit, {real_src.get('official_faq', 25)} from official government FAQ pages, {real_src.get('forum', 12)} from the CAclubindia forum, and {real_src.get('quora', 7)} from Quora. We did not tune anything on them.
First question: does our library even cover them? {rpct(real_cov.get('full', 51) / tot)} fully, {rpct(real_cov.get('partial', 18) / tot)} partly, and {rpct(real_cov.get('none', 11) / tot)} not at all. Real forum posts often mix several problems in one.
On the fully covered ones, TaxSaathi finds the right rule {REAL_RULE:.0%} of the time. By exact passage it is {REAL_EXACT:.2f}. Most of that gap is about time: many posts are from 2025 and ask about last year's law, while TaxSaathi deliberately answers with the law in force today.
The most common confusion, in 10 posts: "no tax up to 12 lakh, but 5 percent from 4 lakh?" Both are true, because of the rebate. Our library did not explain this clearly, so we added an explainer card.
The weak spot: only {REAL_OOS:.0%} of real off-topic questions were refused. Real people ask about NRI rules, crypto and US stocks in ways our sorter had not seen. That is our clearest next step.
""")

# 19. Real users taught it new tricks ------------------------------------------------------
s = new_slide("Real users taught it new tricks", "Built from real-user testing")
tricks = [("\"$5k per month\"", "US$5,000 × 12 at the RBI reference rate  →  ₹57,13,668 a year"),
          ("\"1 lakh mahina\"", "₹1 lakh a month  →  ₹12 lakh a year"),
          ("\"remote, foreign clients\"", "Freelance income under section 58 (old 44ADA): 50% counted as profit")]
for i, (q, a) in enumerate(tricks):
    y = 1.75 + i * 1.22
    card(s, 0.6, y, 6.1, 1.05)
    text(s, 0.85, y + 0.08, 5.7, 0.45, q, size=19, bold=True, color=TEAL_INK)
    text(s, 0.85, y + 0.5, 5.7, 0.5, a, size=15, color=INK3)
text(s, 0.6, 5.42, 6.1, 0.4, "Tax for US$5,000 a month (Tax Year 2026-27):", size=15, bold=True, color=INK3)
for i, (lbl, val, f, c) in enumerate([("New regime", "₹4,54,532", TEAL_SOFT, TEAL), ("Old regime", "₹6,96,332", WHITE, INK2)]):
    x = 0.6 + i * 3.1
    card(s, x, 5.95, 2.95, 0.85, fill=f, line=MINT if i == 0 else LINE)
    text(s, x + 0.2, 5.95, 1.3, 0.85, lbl, size=14, color=INK3, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 1.3, 5.95, 1.6, 0.85, val, size=21, bold=True, color=c, anchor=MSO_ANCHOR.MIDDLE)
p19 = picture(s, ASSETS / "shot_live_usd.jpg", 7.1, 1.6, h=4.85, crop=(0.26, 0.11, 0.28, 0.19))
text(s, 7.1, pic_bottom(p19) + 0.08, 5.6, 0.4, "Live answer, 29 Oct 2026 (about 34 s on our CPU server)",
     size=12, color=MUTED, italic=True)
notes(s, """
When we watched real people use the app, they typed things our system did not understand at first.
"I earn 5k dollars per month." "1 lakh mahina." "I work remotely for foreign clients."
So we taught it. It now reads currency and per-month amounts. 5 thousand US dollars a month becomes 60 thousand dollars a year, converted at the Reserve Bank reference rate, which is about 57 lakh rupees. "1 lakh mahina" becomes 12 lakh a year.
And remote work paid by foreign clients is treated as freelance income under section 58 of the new Act, which used to be 44ADA. Under that scheme, half of what you receive is counted as profit.
On the right is a live answer from our app. For 5 thousand dollars a month, the new regime tax is 4 lakh 54 thousand 532 rupees, and the old regime is 6 lakh 96 thousand 332. The calculator produced every number. The answer also says its assumptions: that you are resident in India, and that if you are actually on a foreign company's payroll, you should tell it so it can recalculate as salary.
Every change was re-tested on our dev set with no drop in scores.
""")

# 20. Live demo ----------------------------------------------------------------------------
s = new_slide("Live demo: five questions", "Demo")
demo = [("Plain AI vs TaxSaathi", "\"What was GST on AC in August 2025?\""),
        ("Hinglish", "\"Naye regime mein standard deduction kitna hai?\""),
        ("Old section number", "\"Is 80C still available in the new Income-tax Act?\""),
        ("Real-user calculation", "\"how much tax do i have to pay if i am earning 5k us dollars per month remote\""),
        ("Off-topic, so it refuses", "\"How do I avoid tax on foreign crypto income?\"")]
for i, (h, q) in enumerate(demo):
    y = 1.7 + i * 0.98
    badge(s, 0.6, y + 0.08, 0.56, str(i + 1), fill=TEAL, size=16)
    text(s, 1.35, y, 4.75, 0.4, h, size=18, bold=True, color=INK)
    text(s, 1.35, y + 0.38, 4.75, 0.58, q, size=13, italic=True, color=MUTED)
p20 = picture(s, ASSETS / "shot_live_compare.jpg", 6.35, 1.65, w=6.35, crop=(0.135, 0.355, 0.135, 0.15))
text(s, 6.35, pic_bottom(p20) + 0.08, 6.35, 0.6, "Live Compare tab, question 1: the plain AI says the rate was \"not set\" "
     "(wrong). TaxSaathi says 28% for August 2025, with its source.", size=12, color=MUTED, italic=True)
card(s, 6.35, 5.75, 6.35, 0.95, fill=SUBTLE, line=None)
text(s, 6.6, 5.75, 6.0, 0.95, [[("https://taxsaathi.taild58d86.ts.net", {"bold": True, "color": TEAL})],
                               [("New questions take 15–40 s on our CPU. Backup screenshots on the next slide.",
                                 {"color": MUTED, "size": 14})]], size=18, anchor=MSO_ANCHOR.MIDDLE, spacing=2)
notes(s, """
Now we show the live app. We have five questions.
One, in the Compare tab: the plain AI and TaxSaathi get the same question, GST on an AC in August 2025. The plain AI says the rate was "not set", which is wrong. TaxSaathi says 28 percent and shows the source and the date. Point out "8 outdated passages dropped".
Two, in the Ask tab: the Hinglish question about standard deduction. Open "How this was found" to show the Hinglish fix and the date step. The answer is 75 thousand rupees, citing section 19 of the 2025 Act.
Three: "Is 80C still available?" 80C is from the old 1961 Act. The answer explains it is now section 123, still up to 1 lakh 50 thousand, and shows the mapping card.
Four: the real user's question about 5 thousand US dollars a month. The calculator gives both regimes; the new regime is cheaper.
Five: "How do I avoid tax on foreign crypto income?" The bouncer stops it and suggests a Chartered Accountant.
A new question takes 15 to 40 seconds because the AI runs on a normal CPU. While we wait, we explain the step-by-step trace.
If the internet fails, the next slide has screenshots of all five answers, taken from the live app.
""")

# 21. Demo backup --------------------------------------------------------------------------
s = new_slide("Demo backup: real answers from the live app", "If the Wi-Fi fails")
shots = [("shot_live_hinglish.jpg", "2 · Hinglish: ₹75,000, from s.19 of the 2025 Act", (0.245, 0.11, 0.255, 0.48)),
         ("shot_live_80c.jpg", "3 · 80C is now section 123, still up to ₹1,50,000", (0.245, 0.11, 0.255, 0.45)),
         ("shot_live_usd.jpg", "4 · US$5k a month: new ₹4,54,532 vs old ₹6,96,332", (0.245, 0.255, 0.255, 0.30)),
         ("shot_live_crypto.jpg", "5 · Crypto tax avoidance: refused, ask a CA", (0.245, 0.11, 0.255, 0.45))]
for i, (f, cap, crop) in enumerate(shots):
    x = 0.6 + (i % 2) * 6.15
    y = 1.6 + (i // 2) * 2.68
    p = picture(s, ASSETS / f, x, y, w=5.95, h=2.1, crop=crop)
    text(s, x, y + 2.14, 5.95, 0.35, cap, size=13, bold=True, color=INK3)
notes(s, """
This slide is our backup if the live demo fails. All four are real answers from the live app, captured on 29 October.
Top left: the Hinglish question. Standard deduction is 75 thousand rupees under the new regime, with section 19 of the 2025 Act as the source.
Top right: 80C. It is now section 123 of the new Act, still up to 1 lakh 50 thousand rupees, and the answer cites the mapping card.
Bottom left: 5 thousand US dollars a month. New regime 4 lakh 54 thousand 532 rupees, old regime 6 lakh 96 thousand 332. The calculator did the maths.
Bottom right: the crypto question is refused with a link to find a Chartered Accountant.
Question one, the AC comparison, is on the previous slide.
""")

# 22. Limits, ethics, future ---------------------------------------------------------------
s = new_slide("Limits, ethics, and what comes next", "Honest about the gaps")
text(s, 0.6, 1.62, 5.9, 0.45, "Limits today", size=20, bold=True, color=INK)
lims = [f"Slow: {secs(LAT)} per answer on a CPU", f"Only {REAL_OOS:.0%} of real off-topic questions refused",
        "Curated summaries, not the full Acts", "Answer key written by us, not yet checked by a CA",
        "Not advice: every answer has a disclaimer + CA link", "PAN, Aadhaar, phone numbers hidden before logging"]
for i, l in enumerate(lims):
    y = 2.15 + i * 0.75
    warn = i < 4
    card(s, 0.6, y, 5.9, 0.62, fill=AMBER_BG if warn else WHITE, line=RGBColor(0xFD, 0xE6, 0x8A) if warn else LINE)
    text(s, 0.85, y, 5.55, 0.62, l, size=17, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
text(s, 6.9, 1.62, 5.8, 0.45, "Next milestones", size=20, bold=True, color=INK)
fut = [("M4", "Run the sealed test set once; study the errors; better off-topic sorter from real questions"),
       ("M5", "GPU or hosted model to reach 5 s; multilingual reranker; CA review of the answer key"),
       ("M6", "Small user study with our three personas"),
       ("Agent", "AI picks tools (search, calculator, follow-up); calculator + fact-check stay hard rules")]
for i, (k, v) in enumerate(fut):
    y = 2.15 + i * 1.12
    c = box(s, 6.9, y, 1.1, 0.95, fill=TEAL)
    shape_text(c, k, size=16 if len(k) > 2 else 20, color=WHITE, bold=True, margin=0.02)
    text(s, 8.2, y, 4.5, 0.95, v, size=16, color=INK2, anchor=MSO_ANCHOR.MIDDLE)
notes(s, f"""
We want to be honest about what is missing.
It is slow: about {secs(LAT)} per answer, because the AI runs on a CPU.
Real off-topic questions are harder than ours: only {REAL_OOS:.0%} were refused.
Our library is made of careful summaries, not the full text of the Acts.
Our answer key was written by us. A real CA has not checked it yet.
On ethics: this is general information, not professional advice. Every answer says so and links to a CA. We hide PAN, Aadhaar and phone numbers before anything is logged.
Next steps. In milestone 4 we run the sealed test set once, study the errors, and retrain the off-topic sorter using what we learned from real questions.
In milestone 5, a GPU or a hosted model to meet the 5-second target, a multilingual reranker, and a CA review of our answer key.
In milestone 6, a small user study.
Later, an agent layer: the AI could choose its own tools, but the calculator and the fact-check stay as hard rules it cannot skip.
""")

# 23. Thanks -------------------------------------------------------------------------------
_slide_no += 1
s = prs.slides.add_slide(TITLE_ONLY)
set_bg(s)
t = s.shapes.title
t.left, t.top, t.width, t.height = Inches(1.9), Inches(0.75), Inches(10.5), Inches(0.9)
t.text_frame.margin_left = t.text_frame.margin_top = 0
t.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
p = t.text_frame.paragraphs[0]
p.alignment = PP_ALIGN.LEFT
r = p.add_run()
r.text = "Thank you. Questions?"
_font(r, 40, INK, bold=True)
if LOGO.exists():
    s.shapes.add_picture(str(LOGO), Inches(0.6), Inches(0.7), Inches(1.0), Inches(1.0))
text(s, 0.6, 2.0, 6, 0.4, "Who presents what", size=16, bold=True, color=TEAL)
team = [("P1", "Problem & data", "Law changes, personas, library, answer key, real questions"),
        ("P2", "Search & results", "Keyword + meaning search, merging, date filter, results"),
        ("P3", "Language & safety", "Hinglish, sorter, safety gate, fact-check, privacy"),
        ("P4", "Calculator & demo", "AI writer, calculator, real-user fixes, live demo")]
for i, (k, h, b) in enumerate(team):
    x = 0.6 + (i % 2) * 3.35
    y = 2.5 + (i // 2) * 1.95
    card(s, x, y, 3.15, 1.75)
    badge(s, x + 0.25, y + 0.25, 0.6, k, fill=TEAL_SOFT, color=TEAL_INK, size=14)
    text(s, x + 1.0, y + 0.25, 2.05, 0.6, h, size=17, bold=True, color=INK, anchor=MSO_ANCHOR.MIDDLE)
    text(s, x + 0.25, y + 0.95, 2.75, 0.8, b, size=13, color=INK3)
pt_ = picture(s, ASSETS / "shot_how.jpg", 7.55, 2.5, w=5.15, crop=(0.125, 0.22, 0.125, 0.12))
text(s, 7.55, pic_bottom(pt_) + 0.08, 5.15, 0.4, "Try it: https://taxsaathi.taild58d86.ts.net", size=18, bold=True, color=TEAL)
text(s, 0.6, 6.55, 12, 0.4, "Code, data card, experiment log, report and viva notes are in our repository.",
     size=14, color=MUTED)
text(s, 11.73, 6.97, 1.0, 0.3, str(_slide_no), size=12, color=MUTED, align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE)
notes(s, """
Thank you for listening.
Here is how we split the work. Person 1 covered the problem, the data and the real questions. Person 2 covered search and the results.
Person 3 covered Hinglish and the safety checks. Person 4 covered the calculator, the AI writer, and the demo.
Each of us will take questions on our own part.
On the right is the app's "How it works" tab. It plays every step for a sample question. The app is live at the address on the slide if you would like to try it.
We are happy to take your questions.
""")

prs.save(OUT)
print(f"wrote {OUT}  ({_slide_no} slides)")
