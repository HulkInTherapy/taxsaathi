"""
HTTP API for agentic tasks (Workflows 1-3), used by the "Tasks" tab of the web UI.

    POST   /tasks                     {goal, workflow?, tax_year?, sample?}  -> {task_id}
    POST   /tasks/{id}/documents      multipart PDF upload (kept in memory only)
    POST   /tasks/{id}/start          run until the first question/approval (background)
    POST   /tasks/{id}/answer         {answer}  resume with the user's answer (background)
    GET    /tasks/{id}                status: running | waiting | done | error, plan, trace, interrupt, final
    GET    /tasks/{id}/ca_summary.md  the CA hand-off summary, if the case was escalated
    DELETE /tasks/{id}                end the session: wipe documents, mask table and checkpoints
    GET    /samples                   synthetic demo taxpayers (fictitious documents)
    POST   /samples/{pid}/answer      {fields}  a sample user's answer to a question (for demos)

Agent runs take tens of seconds, so start/answer return at once and the graph runs in a
background thread; the UI polls GET /tasks/{id}. Every node is checkpointed, so the plan and
trace update while agents work. One run per task at a time.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from src import config
from src.agents import graph as G
from src.agents.service import TaskService

router = APIRouter()

SAMPLE_TITLES = {   # curated demo personas (fictitious) and the title shown in the UI
    "P17": "Salaried with FD interest (one document hides an instruction aimed at AI)",
    "P23": "Changed jobs mid-year: two Form 16s",
    "P22": "Pays rent in Mumbai, invests in 80C, 80D and NPS",
    "P26": "Freelance UI designer earning ₹18 lakh",
    "P29": "Could investing a little more save tax?",
    "P35": "Sold shares at a short-term gain",
}
SAMPLE_IDS = list(SAMPLE_TITLES)
MAX_TASKS = 50                                              # in-memory tasks kept at once
TASK_TTL_S = 2 * 3600                                       # idle tasks are closed after this

_svc: TaskService | None = None
_svc_lock = threading.Lock()
_runs: dict[str, dict] = {}       # task_id -> {"thread", "error", "started", "touched"}
_runs_lock = threading.Lock()


def svc() -> TaskService:
    global _svc
    with _svc_lock:
        if _svc is None:
            _svc = TaskService()
    return _svc


# ------------------------------------------------------------------ models
class CreateTask(BaseModel):
    goal: str = Field("", max_length=2000)
    workflow: Optional[Literal["document_check", "filing_prep", "tax_saving"]] = None
    tax_year: Literal["2025-26", "2026-27"] = "2025-26"
    sample: Optional[str] = Field(None, description="Attach a demo persona's synthetic documents, e.g. 'P17'")


class Answer(BaseModel):
    answer: Any


class SampleAnswer(BaseModel):
    fields: list[str] = Field(default_factory=list)


# ------------------------------------------------------------------ helpers
def _need(task_id: str) -> None:
    with _runs_lock:
        if task_id not in _runs:
            raise HTTPException(404, "task not found (it may have expired; start a new one)")
        _runs[task_id]["touched"] = time.time()


def _busy(task_id: str) -> bool:
    t = _runs.get(task_id, {}).get("thread")
    return bool(t and t.is_alive())


def _launch(task_id: str, fn) -> None:
    def run():
        try:
            out = fn()
            _runs[task_id]["error"] = out.get("error") if out.get("status") == "error" else None
        except Exception as e:  # noqa: BLE001 - surfaced via status
            _runs[task_id]["error"] = f"{type(e).__name__}: {e}"
    with _runs_lock:
        if _busy(task_id):
            raise HTTPException(409, "the task is still working; wait for it to finish this step")
        _runs[task_id]["error"] = None
        th = threading.Thread(target=run, daemon=True, name=f"task-{task_id}")
        _runs[task_id]["thread"] = th
        th.start()


def _gc() -> None:
    """Close idle tasks (documents and checkpoints are deleted with them)."""
    now = time.time()
    with _runs_lock:
        stale = [t for t, r in _runs.items() if now - r["touched"] > TASK_TTL_S and not _busy(t)]
        if len(_runs) - len(stale) >= MAX_TASKS:
            stale += sorted((t for t in _runs if t not in stale and not _busy(t)),
                            key=lambda t: _runs[t]["touched"])[: len(_runs) - MAX_TASKS + 1]
    for t in stale:
        _close(t)


def _close(task_id: str) -> None:
    svc().close(task_id)
    with _runs_lock:
        _runs.pop(task_id, None)


def _status(task_id: str) -> dict:
    st = svc().status(task_id)
    values = svc().state(task_id)
    ctx, tb = G._TASKS.get(task_id, (None, None))
    if _busy(task_id):
        st["status"] = "running"
        st.pop("interrupt", None)
    elif _runs.get(task_id, {}).get("error"):
        st["status"], st["error"] = "error", _runs[task_id]["error"]
    elif st["status"] == "unknown" and not values:
        st["status"] = "new"
    st.update({
        "workflow": values.get("workflow"), "goal": values.get("goal") or (svc()._init.get(task_id) or {}).get("goal"),
        "facts": values.get("facts") or {},
        "documents": ctx.documents.list() if ctx else [],
        "usage": ({**vars(ctx.usage), "tool_calls": tb.calls_used, "tool_budget": tb.max_calls} if ctx else None),
        "started": _runs.get(task_id, {}).get("started"),
    })
    return st


# ------------------------------------------------------------------ routes
@router.post("/tasks")
def create_task(req: CreateTask):
    _gc()
    goal = req.goal.strip()
    sample = None
    if req.sample:
        from experiments.sim_user import SimUser
        if req.sample not in SAMPLE_IDS:
            raise HTTPException(400, f"unknown sample; choose from {SAMPLE_IDS}")
        sample = SimUser(req.sample)
        goal = goal or sample.goal
    if not goal:
        goal = {"document_check": "Please check my tax documents before I file.",
                "tax_saving": "How can I legally reduce my income tax this year?"}.get(req.workflow or "",
                                                                                  "Help me prepare my income tax return.")
    tid = svc().create(goal=goal, tax_year=req.tax_year, workflow=req.workflow)
    with _runs_lock:
        _runs[tid] = {"thread": None, "error": None, "started": None, "touched": time.time(), "sample": req.sample}
    if sample:
        for name, data in sample.documents():
            svc().add_document(tid, name, data)
    return {"task_id": tid, "goal": goal, "documents": G._TASKS[tid][0].documents.list()}


@router.post("/tasks/{task_id}/documents")
async def upload_document(task_id: str, file: UploadFile = File(...)):
    _need(task_id)
    if _runs[task_id]["started"]:
        raise HTTPException(409, "documents must be added before the task starts")
    data = await file.read()
    try:
        doc_id = svc().add_document(task_id, file.filename or "document.pdf", data)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"document_id": doc_id, "documents": G._TASKS[task_id][0].documents.list()}


@router.post("/tasks/{task_id}/start")
def start_task(task_id: str):
    _need(task_id)
    if _runs[task_id]["started"]:
        raise HTTPException(409, "task already started")
    _runs[task_id]["started"] = time.time()
    _launch(task_id, lambda: svc().run(task_id))
    return _status(task_id)


@router.post("/tasks/{task_id}/answer")
def answer_task(task_id: str, req: Answer):
    _need(task_id)
    st = svc().status(task_id)
    if _busy(task_id) or st["status"] != "waiting":
        raise HTTPException(409, "the task is not waiting for an answer")
    _launch(task_id, lambda: svc().resume(task_id, req.answer))
    return _status(task_id)


@router.get("/tasks/{task_id}")
def get_task(task_id: str):
    _need(task_id)
    return _status(task_id)


@router.get("/tasks/{task_id}/ca_summary.md", response_class=PlainTextResponse)
def ca_summary(task_id: str):
    _need(task_id)
    md = ((svc().state(task_id).get("escalation") or {}).get("ca_summary"))
    if not md:
        raise HTTPException(404, "no CA summary for this task")
    return PlainTextResponse(md, headers={"Content-Disposition": 'attachment; filename="taxot_ca_summary.md"'})


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    if task_id in _runs and _busy(task_id):
        raise HTTPException(409, "the task is still working; try again in a moment")
    _close(task_id)
    return {"deleted": task_id}


@router.get("/samples")
def samples():
    truth = {json.loads(line)["persona_id"]: json.loads(line)
             for line in (config.ROOT / "data" / "synthetic" / "ground_truth.jsonl").read_text().splitlines() if line}
    out = []
    for pid in SAMPLE_IDS:
        g = truth[pid]
        out.append({"id": pid, "label": SAMPLE_TITLES[pid], "workflow": g["workflow"], "age": g["age"],
                    "user_says": g.get("user_says", ""),
                    "documents": [d["file"].rsplit("/", 1)[-1] for d in g["documents"]]})
    return {"samples": out, "note": "All people, employers, banks, PANs and figures are fictitious."}


@router.post("/samples/{pid}/answer")
def sample_answer(pid: str, req: SampleAnswer):
    from experiments.sim_user import SimUser
    if pid not in SAMPLE_IDS:
        raise HTTPException(404, "unknown sample")
    return {"text": SimUser(pid).facts_text(set(req.fields))}
