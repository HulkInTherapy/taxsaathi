"""
ask_user: pauses the task and asks the user a question (missing information or an approval).

Implemented with LangGraph's `interrupt()`: the graph stops, the API shows the question to the
user, and the task resumes with the user's answer as this tool's result. Outside a running
graph there is nobody to ask, so `ctx.answer_provider` (used by tests and scripted evaluation)
can supply answers instead.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AskUserArgs(BaseModel):
    question: str = Field(..., min_length=3, max_length=400, description="One clear question for the user.")
    kind: Literal["missing_info", "approval", "choice"] = Field(
        "missing_info", description="approval = user must approve/reject a recommendation before it is final.")
    options: Optional[list[str]] = Field(None, max_length=6, description="Answer options, if it is a choice.")


def ask_user(args: AskUserArgs, ctx) -> dict:
    payload = {"type": "ask_user", **args.model_dump()}
    if ctx is not None and ctx.answer_provider is not None:
        answer = ctx.answer_provider(payload)
    else:
        from langgraph.types import interrupt
        answer = interrupt(payload)
    return {"answer": answer}
