"""
Tool catalogue, per-task context and the per-task tool budget.

`ToolBox.call(name, args)` is the only way agents run tools. It
  * validates the arguments against the tool's pydantic schema; a validation error is returned
    to the agent as a readable message (so it can correct itself) instead of crashing the task;
  * enforces the plan's safety limit of MAX_TOOL_CALLS (15) per task;
  * logs every call (tool, arguments, ok/error, time) for the trace and for the
    "tool-call accuracy" metric;
  * never lets a tool exception kill the task, except LangGraph's interrupt (ask_user), which
    must propagate so the graph can pause.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pydantic import BaseModel, ValidationError

from src import config
from src.documents.store import DocumentStore
from src.tools.ask_user import AskUserArgs, ask_user
from src.tools.calculate_tax import CalculateTaxArgs, calculate_tax
from src.tools.itr_form_rules import ITRFormArgs, itr_form_rules
from src.tools.parse_document import ParseDocumentArgs, parse_document
from src.tools.search_tax_law import SearchTaxLawArgs, search_tax_law
from src.tools.write_ca_summary import CASummaryArgs, write_ca_summary


@dataclass
class TaskContext:
    """Per-task resources the tools share. Lives only in memory, only for the task."""
    documents: DocumentStore = field(default_factory=DocumentStore)
    document_text: dict[str, str] = field(default_factory=dict)  # never sent to the planner LLM
    outputs: dict[str, Any] = field(default_factory=dict)
    answer_provider: Optional[Callable[[dict], Any]] = None   # scripted answers outside a graph
    retrieval_config: Optional[str] = None
    _pipeline: Any = None
    _chunk_index: Optional[dict] = None

    @property
    def pipeline(self):
        if self._pipeline is None:
            from src.pipeline import get_pipeline
            self._pipeline = get_pipeline()
        return self._pipeline

    def chunk_index(self) -> dict:
        if self._chunk_index is None:
            self._chunk_index = {c["id"]: c for c in self.pipeline.chunks}
        return self._chunk_index

    def close(self) -> None:
        """End of session: wipe uploaded documents and their text."""
        self.documents.clear()
        self.document_text.clear()


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    func: Callable[[BaseModel, TaskContext], dict]
    counts_toward_budget: bool = True

    def schema(self) -> dict:
        """OpenAI function-calling schema."""
        params = self.args_model.model_json_schema()
        params.pop("title", None)
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": params}}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("search_tax_law",
         "Search official Indian income-tax and GST law (Income-tax Act 2025 and 1961, rules, CGST Act, CBDT/CBIC "
         "circulars). Returns cited passages, or a refusal if the knowledge base does not cover the question.",
         SearchTaxLawArgs, search_tax_law),
    Tool("calculate_tax",
         "Exact income tax under the old and new regimes for an individual, with optional what-if scenarios. "
         "Always use this for any tax amount; never compute tax yourself.",
         CalculateTaxArgs, calculate_tax),
    Tool("itr_form_rules",
         "Decide which ITR form (ITR-1/2/3/4) an individual must file, with reasons and the due date.",
         ITRFormArgs, itr_form_rules),
    Tool("parse_document",
         "Read an uploaded tax document (Form 16, salary slip, interest certificate) and report its type.",
         ParseDocumentArgs, parse_document),
    Tool("write_ca_summary",
         "Write a structured case summary for a Chartered Accountant when a case is too complex or risky.",
         CASummaryArgs, write_ca_summary),
    Tool("ask_user",
         "Ask the user for missing information, or for approval before a recommendation is final.",
         AskUserArgs, ask_user, counts_toward_budget=False),
]}


class ToolBox:
    """The tools one task may use, with its budget and call log."""

    def __init__(self, ctx: TaskContext | None = None, names: list[str] | None = None,
                 max_calls: int | None = None):
        self.ctx = ctx or TaskContext()
        unknown = set(names or []) - set(TOOLS)
        if unknown:
            raise ValueError(f"unknown tools: {sorted(unknown)}")
        self.tools = {n: TOOLS[n] for n in (names or TOOLS)}
        self.max_calls = config.MAX_TOOL_CALLS if max_calls is None else max_calls
        self.calls_used = 0
        self.log: list[dict] = []

    @property
    def remaining(self) -> int:
        return max(0, self.max_calls - self.calls_used)

    @property
    def exhausted(self) -> bool:
        return self.remaining == 0

    def schemas(self, names: list[str] | None = None) -> list[dict]:
        return [self.tools[n].schema() for n in (names or self.tools)]

    def call(self, name: str, args: dict | None = None) -> dict:
        args = args or {}
        rec = {"tool": name, "args": args, "ok": False, "ms": 0, "error": None}
        t0 = time.perf_counter()
        try:
            tool = self.tools.get(name)
            if tool is None:
                return self._fail(rec, f"unknown tool {name!r}; available: {sorted(self.tools)}")
            if tool.counts_toward_budget:
                if self.exhausted:
                    rec["budget_exhausted"] = True
                    return self._fail(rec, f"tool budget of {self.max_calls} calls for this task is used up; "
                                           "finish with what you have or escalate to a CA")
                self.calls_used += 1
            try:
                parsed = tool.args_model.model_validate(args)
            except ValidationError as e:
                return self._fail(rec, "invalid arguments: " + "; ".join(
                    f"{'.'.join(str(p) for p in err['loc']) or 'args'}: {err['msg']}" for err in e.errors()))
            try:
                result = tool.func(parsed, self.ctx)
            except Exception as e:  # noqa: BLE001
                if _is_graph_interrupt(e):
                    raise
                return self._fail(rec, f"{type(e).__name__}: {e}")
            rec["ok"] = True
            return {"ok": True, "result": result}
        finally:
            rec["ms"] = int((time.perf_counter() - t0) * 1000)
            self.log.append(rec)

    @staticmethod
    def _fail(rec: dict, msg: str) -> dict:
        rec["error"] = msg
        out = {"ok": False, "error": msg}
        if rec.get("budget_exhausted"):
            out["budget_exhausted"] = True
        return out


def _is_graph_interrupt(e: Exception) -> bool:
    try:
        from langgraph.errors import GraphBubbleUp
        return isinstance(e, GraphBubbleUp)
    except ImportError:
        return False
