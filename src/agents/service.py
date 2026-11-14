"""
TaskService: the API the web app (Phase 7) and scripts use to run agentic tasks.

    svc = TaskService()
    tid = svc.create(goal="Help me prepare my return", tax_year="2025-26")
    svc.add_document(tid, "form16.pdf", data)
    status = svc.run(tid)                 # -> {"status": "waiting", "interrupt": {...}} or "done"
    status = svc.resume(tid, {"approved": True})
    svc.close(tid)                        # wipe documents, mask table and saved checkpoints

Checkpoints go to SQLite (TAXOT_TASK_DB, default logs/tasks.sqlite) so a task survives page
reloads; `close()` deletes the task's checkpoints, because they contain extracted figures.
"""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from typing import Any

from langgraph.types import Command

from src import config
from src.agents import graph as G

TASK_DB = os.environ.get("TAXOT_TASK_DB", str(config.LOG_DIR / "tasks.sqlite"))


class TaskService:
    def __init__(self, db_path: str | None = TASK_DB):
        if db_path in (None, ":memory:"):
            from langgraph.checkpoint.memory import InMemorySaver
            self.checkpointer = InMemorySaver()
        else:
            from langgraph.checkpoint.sqlite import SqliteSaver
            os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
            self.checkpointer = SqliteSaver(sqlite3.connect(db_path, check_same_thread=False))
        self.graph = G.build_graph(self.checkpointer)
        self._init: dict[str, dict] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------ lifecycle
    def create(self, goal: str, tax_year: str = "2025-26", workflow: str | None = None,
               facts: dict | None = None, task_id: str | None = None, answer_provider=None) -> str:
        tid = task_id or "task_" + uuid.uuid4().hex[:12]
        ctx, _ = G.register_task(tid)
        ctx.answer_provider = answer_provider
        self._init[tid] = {"task_id": tid, "goal": goal, "tax_year": tax_year, "facts": facts or {},
                           "trace": [], **({"workflow": workflow} if workflow else {})}
        return tid

    def add_document(self, task_id: str, filename: str, data: bytes) -> str:
        ctx, _ = G._TASKS[task_id]
        return ctx.documents.add(filename, data)

    def run(self, task_id: str) -> dict:
        return self._invoke(task_id, self._init.pop(task_id))

    def resume(self, task_id: str, answer: Any) -> dict:
        return self._invoke(task_id, Command(resume=answer))

    def close(self, task_id: str) -> None:
        G.drop_task(task_id)
        try:
            self.checkpointer.delete_thread(task_id)
        except Exception:  # noqa: BLE001 - nothing saved yet
            pass

    # ------------------------------------------------------------ state
    def status(self, task_id: str) -> dict:
        snap = self.graph.get_state(self._cfg(task_id))
        v = snap.values or {}
        if snap.interrupts:
            return {"status": "waiting", "task_id": task_id, "interrupt": snap.interrupts[0].value,
                    "plan": v.get("plan"), "trace": v.get("trace", [])}
        if v.get("final"):
            return {"status": "done", "task_id": task_id, "final": v["final"], "plan": v.get("plan"),
                    "trace": v.get("trace", [])}
        return {"status": "running" if snap.next else "unknown", "task_id": task_id, "plan": v.get("plan"),
                "trace": v.get("trace", [])}

    def state(self, task_id: str) -> dict:
        return self.graph.get_state(self._cfg(task_id)).values or {}

    def _cfg(self, task_id: str) -> dict:
        return {"configurable": {"thread_id": task_id}, "recursion_limit": 60}

    def _invoke(self, task_id: str, payload) -> dict:
        try:
            self.graph.invoke(payload, self._cfg(task_id))
        except Exception as e:  # noqa: BLE001 - report, keep the task inspectable
            return {"status": "error", "task_id": task_id, "error": f"{type(e).__name__}: {e}",
                    **{k: v for k, v in self.status(task_id).items() if k in ("plan", "trace")}}
        return self.status(task_id)
