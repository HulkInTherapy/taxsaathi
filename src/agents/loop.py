"""
A tool-using agent loop shared by the specialist agents.

The LLM decides which tool to call next (autonomous tool use); the loop runs it through the
task's ToolBox (validation, 15-call budget, call log) and feeds back the result, until the
agent calls its `final` tool, whose arguments are the agent's structured answer.

Guards: a step limit, the ToolBox budget (when it runs out the agent is forced to finish), a
nudge when the model answers in prose instead of calling a tool, and tool results truncated
to keep prompts small on free-tier rate limits.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, ValidationError

from src.llm import provider as prov
from src.tools.registry import ToolBox

MAX_RESULT_CHARS = 6000


@dataclass
class AgentRun:
    agent: str
    final: dict | None = None
    steps: list[dict] = field(default_factory=list)   # trace: one entry per tool call / LLM turn
    stopped: str = "final"                              # final | max_steps | budget | error
    error: str | None = None
    ms: int = 0


def run_agent(name: str, system: str, user: str, toolbox: ToolBox, tools: list[str],
              final: type[BaseModel], role: str = "planner", max_steps: int = 10) -> AgentRun:
    run = AgentRun(agent=name)
    t0 = time.perf_counter()
    final_name = final.__name__
    specs = toolbox.schemas(tools) + [_schema(final)]
    messages: list[Any] = [SystemMessage(system), HumanMessage(user)]
    forced: str | None = None
    try:
        for step in range(1, max_steps + 1):
            if toolbox.exhausted and forced is None:
                forced = final_name
                messages.append(HumanMessage(f"The tool budget is used up. Call {final_name} now with what you have."))
                run.stopped = "budget"
            reply: AIMessage = prov.chat(messages, role=role, tools=specs, masker=toolbox.ctx.masker,
                                         usage=toolbox.ctx.usage, tool_choice=forced)
            messages.append(reply)
            if not reply.tool_calls:
                run.steps.append({"step": step, "type": "text", "text": _short(reply.content)})
                messages.append(HumanMessage(f"Do not answer in prose. Call a tool, or {final_name} to finish."))
                continue
            for call in reply.tool_calls:
                if call["name"] == final_name:
                    try:
                        run.final = final.model_validate(call["args"]).model_dump()
                    except ValidationError as e:
                        messages.append(ToolMessage(json.dumps({"error": f"invalid {final_name}: {str(e)[:500]}"}),
                                                    tool_call_id=call["id"]))
                        run.steps.append({"step": step, "type": "final_invalid", "error": str(e)[:300]})
                        continue
                    run.steps.append({"step": step, "type": "final"})
                    if run.stopped != "budget":
                        run.stopped = "final"
                    # answer any sibling tool calls so the transcript stays valid, then stop
                    return run
                result = toolbox.call(call["name"], call["args"])
                run.steps.append({"step": step, "type": "tool", "tool": call["name"], "args": call["args"],
                                  "ok": result["ok"], "error": result.get("error")})
                messages.append(ToolMessage(_short(json.dumps(result, ensure_ascii=False, default=str),
                                                   MAX_RESULT_CHARS), tool_call_id=call["id"]))
        run.stopped = "max_steps"
        # last chance: force the final answer
        reply = prov.chat(messages + [HumanMessage(f"Step limit reached. Call {final_name} now.")], role=role,
                          tools=[_schema(final)], masker=toolbox.ctx.masker, usage=toolbox.ctx.usage,
                          tool_choice=final_name)
        call = next((c for c in reply.tool_calls if c["name"] == final_name), None)
        if call:
            run.final = final.model_validate(call["args"]).model_dump()
        return run
    except (prov.LLMUnavailable, ValidationError) as e:
        run.stopped, run.error = "error", f"{type(e).__name__}: {str(e)[:300]}"
        return run
    finally:
        run.ms = int((time.perf_counter() - t0) * 1000)


def _schema(model: type[BaseModel]) -> dict:
    params = model.model_json_schema()
    params.pop("title", None)
    return {"type": "function", "function": {"name": model.__name__,
                                             "description": (model.__doc__ or "").strip(), "parameters": params}}


def _short(text: Any, n: int = 400) -> str:
    text = text if isinstance(text, str) else json.dumps(text, default=str)
    return text if len(text) <= n else text[:n] + f"... [truncated {len(text) - n} chars]"
