"""
The single gateway between Taxot's agents and external LLM APIs.

Every agent call goes through `chat()`, which enforces in one place:
  * masking  - personal data is replaced with placeholders before anything leaves the server,
               and restored in the reply (text and tool-call arguments);
  * rate limits - a per-provider token bucket keeps us under the free-tier request limits;
  * fallback - providers are tried in order (TAXOT_LLM_PROVIDER first); rate-limit, server,
               timeout and connection errors move on to the next provider;
  * usage    - provider, model, latency and token counts are logged (logs/llm_usage.jsonl)
               and added to the task's `Usage` (needed for the "steps, latency, cost" metric).

All providers expose an OpenAI-compatible API, so one client class (langchain-openai's
ChatOpenAI) serves all of them. Models are chosen per *role* (planner / extractor / verifier)
in config.PROVIDERS.
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from src import config
from src.llm.masking import Masker

ROLES = ("planner", "extractor", "verifier")


class LLMUnavailable(RuntimeError):
    """No provider could answer (all failed, or none has an API key)."""


@dataclass
class Usage:
    """Running totals for one task."""
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    fallbacks: int = 0
    by_provider: dict[str, int] = field(default_factory=dict)

    def add(self, provider: str, latency_ms: int, tin: int, tout: int) -> None:
        self.calls += 1
        self.latency_ms += latency_ms
        self.input_tokens += tin
        self.output_tokens += tout
        self.by_provider[provider] = self.by_provider.get(provider, 0) + 1


# ------------------------------------------------------------------ provider plumbing
def provider_order(primary: str | None = None, role: str | None = None) -> list[str]:
    """Providers to try, in order, that have a key configured: the role's own order if configured,
    else the primary provider first and then the other API providers."""
    if role and primary is None and config.ROLE_PROVIDERS.get(role):
        listed = [p for p in config.ROLE_PROVIDERS[role] if p in config.PROVIDERS]
        rest = [p for p in config.PROVIDERS if p not in listed and p != "ollama"]
        return [p for p in listed + rest if _has_key(p)]
    primary = primary or config.LLM_PROVIDER
    if primary not in config.PROVIDERS:
        raise ValueError(f"unknown provider {primary!r}; choose from {list(config.PROVIDERS)}")
    order = [primary] + [p for p in config.PROVIDERS if p != primary and p != "ollama"]
    return [p for p in order if _has_key(p)]


def _has_key(provider: str) -> bool:
    env = config.PROVIDERS[provider]["key_env"]
    return env is None or bool(os.environ.get(env))


_LIMITERS: dict[str, Any] = {}
_MODELS: dict[tuple[str, str], Any] = {}
_LOCK = threading.Lock()


def _limiter(provider: str):
    from langchain_core.rate_limiters import InMemoryRateLimiter
    with _LOCK:
        if provider not in _LIMITERS:
            rpm = config.PROVIDERS[provider]["requests_per_minute"]
            _LIMITERS[provider] = InMemoryRateLimiter(requests_per_second=rpm / 60.0,
                                                      check_every_n_seconds=0.1, max_bucket_size=3)
    return _LIMITERS[provider]


def get_model(provider: str, role: str, max_tokens: int | None = None):
    """A ChatOpenAI client for this provider/role (cached). `max_tokens` overrides the role's output budget."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    key = (provider, role, max_tokens)
    with _LOCK:
        cached = _MODELS.get(key)
    if cached is not None:
        return cached
    from langchain_openai import ChatOpenAI
    p = config.PROVIDERS[provider]
    model = ChatOpenAI(
        model=p["models"][role],
        base_url=p["base_url"],
        api_key=os.environ.get(p["key_env"]) if p["key_env"] else "ollama",
        temperature=0,
        max_tokens=min(max_tokens or config.ROLE_MAX_TOKENS.get(role, config.AGENT_MAX_TOKENS),
                       p.get("max_output_tokens", 10**6)),
        timeout=config.AGENT_LLM_TIMEOUT_S,
        max_retries=1,
        rate_limiter=_limiter(provider),
    )
    with _LOCK:
        _MODELS[key] = model
    return model


def _is_retryable(err: Exception) -> bool:
    """Errors that should move us to the next provider (vs. bugs in our own request)."""
    try:
        import openai
        if isinstance(err, (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError,
                            openai.InternalServerError, openai.NotFoundError, openai.PermissionDeniedError,
                            openai.AuthenticationError)):
            return True
        if isinstance(err, openai.BadRequestError):
            # providers differ in what they accept (and some models emit malformed tool calls,
            # e.g. Groq's "Failed to call a function"), so another provider may well succeed
            return True
        if isinstance(err, openai.APIStatusError):
            return err.status_code >= 500 or err.status_code in (400, 402, 408, 409, 413, 422, 429)
    except ImportError:
        pass
    return isinstance(err, (TimeoutError, ConnectionError))


def _is_rate_limit(err: Exception) -> bool:
    try:
        import openai
        if isinstance(err, openai.RateLimitError):
            return True
    except ImportError:
        pass
    return "429" in str(err) or "RateLimit" in type(err).__name__


def _log(record: dict) -> None:
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.LLM_USAGE_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass


# ------------------------------------------------------------------ public API
def chat(messages: Sequence, role: str = "planner", tools: Sequence | None = None,
         masker: Masker | None = None, usage: Usage | None = None,
         providers: Sequence[str] | None = None, tool_choice: str | None = None, max_tokens: int | None = None):
    """
    Send `messages` (LangChain messages or {"role","content"} dicts) and return an AIMessage
    whose text and tool-call arguments have real values restored.

    `tools`: LangChain tools / pydantic models / OpenAI tool dicts the model may call.
    `masker`: share one Masker per task so placeholders stay stable across calls.
    `max_tokens`: output budget for this call (reasoning models need room for long structured replies).
    """
    from langchain_core.messages import AIMessage, convert_to_messages

    masker = masker or Masker()
    outgoing = [_mask_message(m, masker) for m in convert_to_messages(list(messages))]
    order = list(providers) if providers else provider_order(role=role)
    if not order:
        raise LLMUnavailable("no LLM provider has an API key; fill in .env (see .env.example)")

    for attempt in range(len(RATE_LIMIT_BACKOFF_S) + 1):
        try:
            return _chat_once(outgoing, role, tools, masker, usage, order, tool_choice, max_tokens)
        except _AllRateLimited as e:
            if attempt == len(RATE_LIMIT_BACKOFF_S):
                raise LLMUnavailable(f"all providers rate-limited: {e}") from e
            wait = RATE_LIMIT_BACKOFF_S[attempt]
            _log({"ts": _now(), "role": role, "provider": "*", "ok": False, "ms": 0,
                  "error": f"all providers rate-limited; waiting {wait}s"})
            time.sleep(wait)


class _AllRateLimited(RuntimeError):
    pass


# Waits before retrying when every provider says 429 (per-minute limits recover; daily caps do not).
RATE_LIMIT_BACKOFF_S = (20, 45, 90)


def _chat_once(outgoing, role, tools, masker, usage, order, tool_choice, max_tokens=None):
    errors, limited = [], 0
    for i, provider in enumerate(order):
        model = get_model(provider, role, max_tokens)
        runnable = model.bind_tools(list(tools), tool_choice=tool_choice) if tools else model
        t0 = time.perf_counter()
        try:
            reply: AIMessage = runnable.invoke(outgoing)
        except Exception as e:  # noqa: BLE001 - classified below
            ms = int((time.perf_counter() - t0) * 1000)
            _log({"ts": _now(), "role": role, "provider": provider, "model": model.model_name,
                  "ok": False, "ms": ms, "error": f"{type(e).__name__}: {str(e)[:200]}"})
            errors.append(f"{provider}: {type(e).__name__}")
            limited += _is_rate_limit(e)
            if _is_retryable(e) and i < len(order) - 1:
                if usage:
                    usage.fallbacks += 1
                continue
            if limited == len(order):
                raise _AllRateLimited("; ".join(errors)) from e
            raise LLMUnavailable("; ".join(errors)) from e
        ms = int((time.perf_counter() - t0) * 1000)
        um = reply.usage_metadata or {}
        tin, tout = int(um.get("input_tokens", 0)), int(um.get("output_tokens", 0))
        if usage:
            usage.add(provider, ms, tin, tout)
        _log({"ts": _now(), "role": role, "provider": provider, "model": model.model_name, "ok": True,
              "ms": ms, "input_tokens": tin, "output_tokens": tout, "tool_calls": len(reply.tool_calls)})
        return _unmask_reply(reply, masker, provider, model.model_name)
    raise LLMUnavailable("; ".join(errors))


def _mask_message(msg, masker: Masker):
    update: dict[str, Any] = {}
    if isinstance(msg.content, str):
        update["content"] = masker.mask(msg.content)
    else:  # multi-part content (text + images)
        update["content"] = masker.mask_obj(msg.content)
    if getattr(msg, "tool_calls", None):  # earlier AI turns that called tools
        update["tool_calls"] = [{**tc, "args": masker.mask_obj(tc["args"])} for tc in msg.tool_calls]
    return msg.model_copy(update=update)


def _unmask_reply(reply, masker: Masker, provider: str, model_name: str):
    meta = {**(reply.response_metadata or {}), "taxot_provider": provider, "taxot_model": model_name}
    return reply.model_copy(update={
        "content": masker.unmask_obj(reply.content),
        "tool_calls": [{**tc, "args": masker.unmask_obj(tc["args"])} for tc in reply.tool_calls],
        "response_metadata": meta,
    })


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
