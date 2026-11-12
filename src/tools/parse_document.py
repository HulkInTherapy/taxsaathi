"""
parse_document: reads an uploaded PDF from the task's in-memory store.

Phase 2 scope: open the PDF, extract its text, detect the document type. Phase 4 adds LLM
field extraction into typed schemas and validation.

Prompt-injection boundary: the raw document text is never returned to the calling agent. The
agent only sees metadata (and, from Phase 4, schema-validated fields), so instructions hidden in
a document cannot reach the planner.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

DocType = Literal["form16", "salary_slip", "interest_certificate", "unknown"]

TYPE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("form16", re.compile(r"form\s*(no\.?)?\s*16\b(?!\s*a)|certificate under section 203", re.I)),
    ("interest_certificate", re.compile(r"interest\s+certificate|tds\s+certificate\s+on\s+interest|"
                                        r"form\s*(no\.?)?\s*16\s*a\b|statement of interest", re.I)),
    ("salary_slip", re.compile(r"(salary|pay)\s*slip|payslip|pay\s+statement", re.I)),
]


class ParseDocumentArgs(BaseModel):
    document_id: str = Field(..., description="Id of an uploaded document, e.g. 'doc_ab12cd34ef'.")
    expected_type: Optional[DocType] = Field(None, description="What the user said this document is, if known.")


def extract_text(data: bytes) -> list[str]:
    """Text of each page (PyMuPDF). Raises ValueError for unreadable files."""
    import pymupdf
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            return [page.get_text("text") for page in pdf]
    except Exception as e:  # noqa: BLE001 - any parser error means "not a readable PDF"
        raise ValueError(f"could not read PDF: {type(e).__name__}") from e


def detect_type(text: str) -> DocType:
    head = text[:3000]
    for name, rx in TYPE_PATTERNS:
        if rx.search(head):
            return name  # type: ignore[return-value]
    return "unknown"


def parse_document(args: ParseDocumentArgs, ctx) -> dict:
    doc = ctx.documents.get(args.document_id)
    pages = extract_text(doc.data)
    text = "\n".join(pages)
    detected = detect_type(text)
    out = {"document_id": doc.id, "filename": doc.filename, "detected_type": detected,
           "pages": len(pages), "text_chars": len(text), "fields": None,
           "status": "text_extracted" if text.strip() else "no_text_layer"}
    if not text.strip():
        out["warning"] = "No text layer (scanned image?). Ask the user for a digital copy."
    if args.expected_type and detected not in ("unknown", args.expected_type):
        out["warning"] = f"User said {args.expected_type}, but the document looks like {detected}."
    # keep the text for later steps (Phase 4 extraction) without handing it to the LLM agent
    ctx.document_text[doc.id] = text
    return out
