# TaxSaathi brand mark

**Concept: an answer that is also a document.**

The mark is a speech bubble (the conversation with your *saathi*, your companion) that is
also a page of law: its top-right corner is folded like a document. Inside sits a check mark.

- **Bubble** = TaxSaathi talks with you, in English or Hinglish.
- **Folded corner** = every answer is backed by an official source document.
- **Check** = the answer was verified: right law, right date, citations checked.

It reads as one simple shape, so it works at 16 px (favicon) and in the 30 px header.

## Construction

- 32 × 32 grid, tile radius 9. Bubble from (8, 7) to (24, 23) with a 2.5 radius, a 5 px fold and a
  short tail at the bottom left.
- Check stroke 2.3, round caps. The fold is filled mint (#99F6E4) to show depth.
- Colours: accent tile **#0F766E** (deep teal), white bubble. Monochrome version: ink tile **#0A0A0A**.
- Wordmark: Inter 650, tight tracking: "Tax" in ink, "Saathi" in teal.

## Motion (the mark is alive, quietly)

- **Thinking:** while an answer is being prepared the bubble gently breathes (scale 1 → 0.92)
  and the check keeps drawing itself, in the header and in the progress line.
- **Answer lands:** a single satisfied pulse (scale 1.14 with a spring) and the check draws in.
- **First load:** the large hero mark pops in and draws its check.
- All motion is disabled when the system asks for reduced motion.

Files: `app/static/favicon.svg`, inline SVG in `app/static/index.html` and `TS.markSvg()` in `app.js`.
