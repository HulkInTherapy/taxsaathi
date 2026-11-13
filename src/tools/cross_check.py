"""cross_check_documents: runs the deterministic cross-checks over every document parsed so far."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.documents.crosscheck import cross_check


class CrossCheckArgs(BaseModel):
    document_ids: Optional[list[str]] = Field(None, description="Limit to these documents; default: all parsed.")


def cross_check_documents(args: CrossCheckArgs, ctx) -> dict:
    ids = args.document_ids or list(ctx.extracted)
    missing = [i for i in ids if i not in ctx.extracted]
    if not ids:
        return {"error": "no documents parsed yet; call parse_document for each uploaded document first"}
    docs = [{"document_id": i, **ctx.extracted[i]} for i in ids if i in ctx.extracted]
    out = cross_check(docs)
    ctx.outputs["cross_check"] = out
    if missing:
        out["not_parsed"] = missing
    return out
