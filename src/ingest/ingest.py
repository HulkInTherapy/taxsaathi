"""
Ingestion: turn the knowledge-base source files into one clean list of "chunks".

A chunk is one small passage (one idea) plus metadata: which law it belongs to, which
section, and the dates during which it is in force. We read the hand-curated Markdown files
in data/raw/curated/ (format in SPEC.md) and, optionally, official PDFs in data/raw/pdfs/.
The result is written to data/processed/chunks.jsonl, which every other module reads.

Run:  python -m src.ingest.ingest            (add --no-pdf to skip PDFs)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from src import config

# Fields every chunk in chunks.jsonl has (SPEC "chunks.jsonl").
CHUNK_FIELDS = ["id", "doc_id", "title", "text", "section", "law", "doc_type", "topic",
                "effective_from", "effective_to", "source_title", "source_url", "publisher",
                "verified", "n_tokens"]
VALID_LAWS = {"new_act", "old_act", "gst", "mapping", "general"}

# "## [IT25-202-SLABS] Section 202 — New tax regime slab rates"
HEADING_RE = re.compile(r"^##\s*\[([A-Za-z0-9][A-Za-z0-9_\-\.]*)\]\s*(.*?)\s*$")
# "effective_from: 2026-04-01" (lowercase key, colon, value) — metadata lines under a heading
META_RE = re.compile(r"^([a-z][a-z_]*)\s*:\s*(.*)$")


def count_tokens(text: str) -> int:
    """Approximate token count = number of words/numbers. Good enough for chunk sizing."""
    return len(re.findall(r"\w+", text))


def chunk_hash(chunk: dict) -> str:
    """Stable fingerprint of a chunk's content; used to cache embeddings."""
    return hashlib.sha1((chunk["id"] + "\n" + chunk["title"] + "\n" + chunk["text"]).encode()).hexdigest()


def _strip_comment(value: str) -> str:
    """Remove trailing '   # comment' (only when '#' follows whitespace, so URLs survive)."""
    return re.sub(r"\s+#.*$", "", value).strip()


# ============================================================ Markdown knowledge base
def parse_front_matter(lines: list[str]) -> tuple[dict, int]:
    """Parse the '---' delimited header. Returns (fields, index of first body line)."""
    meta: dict = {}
    if not lines or lines[0].strip() != "---":
        return meta, 0
    for i in range(1, len(lines)):
        line = lines[i].strip()
        if line == "---":
            return meta, i + 1
        m = re.match(r"^([A-Za-z_][\w]*)\s*:\s*(.*)$", line)
        if m:
            meta[m.group(1).lower()] = _strip_comment(m.group(2))
    return meta, len(lines)  # no closing '---': treat everything as header


def parse_markdown(path: Path) -> list[dict]:
    """Parse one curated .md file into chunk dicts (without validation)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    doc, start = parse_front_matter(lines)
    doc.setdefault("doc_id", path.stem)

    # Group body lines by '## [ID] Title' headings.
    blocks: list[tuple[str, str, list[str]]] = []
    for line in lines[start:]:
        m = HEADING_RE.match(line)
        if m:
            blocks.append((m.group(1), m.group(2), []))
        elif blocks:
            blocks[-1][2].append(line)

    chunks = []
    for cid, title, body in blocks:
        meta: dict = {}
        i = 0
        # Skip blank lines right after the heading, then read "key: value" lines.
        while i < len(body) and not body[i].strip():
            i += 1
        while i < len(body):
            m = META_RE.match(body[i].strip())
            if not m or not body[i].strip():
                break
            meta[m.group(1)] = _strip_comment(m.group(2))
            i += 1
        text = "\n".join(body[i:]).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        chunk = {
            "id": cid.strip().upper(),
            "doc_id": doc.get("doc_id", path.stem),
            "title": title.strip(),
            "text": text,
            "section": meta.pop("section", ""),
            "law": meta.pop("law", doc.get("law", "general")),
            "doc_type": meta.pop("doc_type", doc.get("doc_type", "")),
            "topic": meta.pop("topic", ""),
            "effective_from": meta.pop("effective_from", "") or "",
            "effective_to": meta.pop("effective_to", "") or "",
            "source_title": doc.get("source_title", ""),
            "source_url": meta.pop("source_url", doc.get("source_url", "")),
            "publisher": doc.get("publisher", ""),
            "verified": meta.pop("verified", doc.get("verified", "")),
            "n_tokens": count_tokens(text),
            "source_file": path.name,
        }
        if meta:  # any extra metadata keys (e.g. old_section) are kept, not lost
            chunk["extra"] = meta
        chunks.append(chunk)
    return chunks


# ============================================================ optional PDF path
# A legal section heading at the start of a line, e.g. "80C. Deduction in respect of ..."
SECTION_HEADING_RE = re.compile(r"^\s*(\d{1,3}[A-Z]{0,5})\.\s+(\S.*)$", re.MULTILINE)
PAGE_NUMBER_RE = re.compile(r"^\s*(page\s*)?\d{1,4}(\s*(of|/)\s*\d{1,4})?\s*$", re.IGNORECASE)


def _clean_pdf_pages(pages: list[list[str]]) -> str:
    """Drop page numbers and running headers/footers (lines repeated on many pages)."""
    edge_counts: Counter = Counter()
    for lines in pages:
        for line in set(lines[:2] + lines[-2:]):  # headers/footers live at page edges
            edge_counts[line.strip()] += 1
    n = max(len(pages), 1)
    repeated = {l for l, c in edge_counts.items() if l and n >= 3 and c / n >= 0.5}
    kept = []
    for lines in pages:
        for line in lines:
            s = line.strip()
            if not s or PAGE_NUMBER_RE.match(s) or s in repeated:
                continue
            kept.append(s)
    return "\n".join(kept)


def split_long(text: str, max_tokens: int = 400, overlap: int = 50) -> list[str]:
    """Split text into windows of ~max_tokens words that overlap by `overlap` words."""
    words = text.split()
    if len(words) <= max_tokens:
        return [text]
    out, step = [], max_tokens - overlap
    for start in range(0, len(words), step):
        out.append(" ".join(words[start:start + max_tokens]))
        if start + max_tokens >= len(words):
            break
    return out


def parse_pdf(path: Path) -> list[dict]:
    """Extract sections from an official PDF. Metadata may come from a sidecar <name>.meta
    file in the same 'key: value' format as the Markdown front matter."""
    import fitz  # PyMuPDF; imported lazily so the Markdown path works without it

    doc_meta: dict = {}
    sidecar = path.with_suffix(".meta")
    if sidecar.exists():
        doc_meta, _ = parse_front_matter(["---"] + sidecar.read_text().splitlines() + ["---"])
    with fitz.open(path) as pdf:
        pages = [p.get_text("text").splitlines() for p in pdf]
    text = _clean_pdf_pages(pages)

    stem = re.sub(r"[^A-Z0-9]+", "-", path.stem.upper()).strip("-")
    heads = list(SECTION_HEADING_RE.finditer(text))
    sections = []
    if not heads:
        sections.append(("", path.stem, text))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        sections.append((m.group(1), m.group(2)[:120], text[m.start():end]))

    chunks = []
    for sec, title, body in sections:
        body = re.sub(r"\s+", " ", body).strip()
        for j, piece in enumerate(split_long(body)):
            cid = f"PDF-{stem}-{sec or 'X'}-{j + 1}"
            chunks.append({
                "id": cid, "doc_id": doc_meta.get("doc_id", path.stem), "title": title,
                "text": piece, "section": sec, "law": doc_meta.get("law", "general"),
                "doc_type": doc_meta.get("doc_type", "act"), "topic": doc_meta.get("topic", ""),
                "effective_from": doc_meta.get("effective_from", ""),
                "effective_to": doc_meta.get("effective_to", ""),
                "source_title": doc_meta.get("source_title", path.name),
                "source_url": doc_meta.get("source_url", ""),
                "publisher": doc_meta.get("publisher", ""),
                "verified": doc_meta.get("verified", "partial"),
                "n_tokens": count_tokens(piece), "source_file": path.name,
            })
    return chunks


# ============================================================ validation
def _parse_date(value: str) -> date | None:
    return date.fromisoformat(value) if value else None


def validate(chunks: list[dict]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors = must fix (duplicate IDs, bad dates)."""
    errors, warnings = [], []
    seen: dict[str, str] = {}
    for c in chunks:
        where = f"{c['id']} ({c.get('source_file', '?')})"
        if c["id"] in seen:
            errors.append(f"duplicate chunk id {c['id']} in {c.get('source_file')} and {seen[c['id']]}")
        seen[c["id"]] = c.get("source_file", "?")
        try:
            f, t = _parse_date(c["effective_from"]), _parse_date(c["effective_to"])
            if f and t and f > t:
                errors.append(f"{where}: effective_from {f} is after effective_to {t}")
        except ValueError as e:
            errors.append(f"{where}: bad date ({e})")
        if c["law"] not in VALID_LAWS:
            warnings.append(f"{where}: unknown law '{c['law']}'")
        if not c["text"]:
            errors.append(f"{where}: empty passage text")
        elif c["n_tokens"] < 30 or c["n_tokens"] > 300:
            warnings.append(f"{where}: passage has {c['n_tokens']} words (target 60-220)")
    return errors, warnings


# ============================================================ main
def load_all(kb_dir: Path, pdf_dir: Path | None) -> list[dict]:
    chunks: list[dict] = []
    for path in sorted(kb_dir.glob("*.md")):
        chunks.extend(parse_markdown(path))
    if pdf_dir is not None and pdf_dir.exists():
        for path in sorted(pdf_dir.glob("*.pdf")):
            try:
                chunks.extend(parse_pdf(path))
            except Exception as e:  # a broken PDF should not stop the whole ingest
                print(f"WARNING: could not parse {path.name}: {e}", file=sys.stderr)
    return chunks


def write_chunks(chunks: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")


def read_chunks(path: Path | None = None) -> list[dict]:
    """Load chunks.jsonl (used by retrieval, pipeline, EDA, experiments)."""
    path = Path(path or config.CHUNKS_PATH)
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def print_stats(chunks: list[dict]) -> None:
    lens = [c["n_tokens"] for c in chunks] or [0]
    print(f"chunks: {len(chunks)}   documents: {len({c['doc_id'] for c in chunks})}")
    print(f"words per chunk: min {min(lens)}  mean {sum(lens) / len(lens):.0f}  max {max(lens)}")
    for field in ("law", "doc_type", "topic", "verified"):
        counts = Counter(c[field] or "(blank)" for c in chunks)
        print(f"by {field}: " + ", ".join(f"{k}={v}" for k, v in counts.most_common()))
    dated = sum(1 for c in chunks if c["effective_from"] or c["effective_to"])
    print(f"chunks with effective dates: {dated}/{len(chunks)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build data/processed/chunks.jsonl from the KB")
    ap.add_argument("--kb-dir", type=Path, default=config.KB_DIR)
    ap.add_argument("--pdf-dir", type=Path, default=config.PDF_DIR)
    ap.add_argument("--no-pdf", action="store_true", help="skip data/raw/pdfs")
    ap.add_argument("--out", type=Path, default=config.CHUNKS_PATH)
    ap.add_argument("--strict", action="store_true", help="exit non-zero on validation errors")
    args = ap.parse_args(argv)

    chunks = load_all(args.kb_dir, None if args.no_pdf else args.pdf_dir)
    if not chunks:
        print(f"No chunks found in {args.kb_dir}", file=sys.stderr)
        return 1
    errors, warnings = validate(chunks)
    for w in warnings:
        print("WARNING:", w)
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    if errors:
        # Keep the first occurrence of duplicate ids so the system still runs.
        seen, unique = set(), []
        for c in chunks:
            if c["id"] not in seen:
                seen.add(c["id"])
                unique.append(c)
        chunks = unique
        if args.strict:
            return 2
    write_chunks(chunks, args.out)
    print_stats(chunks)
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
