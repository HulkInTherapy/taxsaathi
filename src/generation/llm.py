"""
The answer writer of the Ask/Compare pipeline: turns retrieved passages into 2-5 cited sentences.

Two backends (TAXOT_GEN_BACKEND):
  * "api" (default): the provider gateway (src/llm/provider.py, role "writer"), so answers get the
    same PII masking, rate limits, fallback and usage log as the agents;
  * "ollama": the local model (TAXOT_LLM, default qwen2.5:3b) at OLLAMA_URL, the setup the M3
    answer-quality numbers were measured with.
Temperature 0. Any failure raises LLMError so the caller can fall back to an extractive answer.
"""
from __future__ import annotations

import time

import requests

from src import config


class LLMError(RuntimeError):
    """Raised when the LLM cannot be reached or returns nothing useful."""


def backend() -> str:
    return config.GEN_BACKEND if config.GEN_BACKEND in ("api", "ollama") else "api"


def model_name() -> str:
    """The writer model answers come from (first provider with a key, for the API backend)."""
    if backend() == "ollama":
        return config.LLM_MODEL
    from src.llm.provider import provider_order
    order = provider_order(role="writer")
    return f"{order[0]}:{config.PROVIDERS[order[0]]['models']['writer']}" if order else "none"


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.0,
         num_predict: int | None = None, timeout: float | None = None, retries: int = 1) -> str:
    """Send chat messages [{"role": "system"|"user", "content": str}] and return the reply text."""
    if backend() == "api" and model is None:
        return _chat_api(messages)
    return _chat_ollama(messages, model, temperature, num_predict, timeout, retries)


def _chat_api(messages: list[dict]) -> str:
    from src.llm.provider import chat as gateway_chat
    try:
        reply = gateway_chat(messages, role="writer")
    except Exception as e:  # LLMUnavailable, or a provider error that every fallback also hit
        raise LLMError(f"LLM call failed (writer): {e}") from e
    text = reply.content if isinstance(reply.content, str) else "".join(
        b.get("text", "") for b in reply.content if isinstance(b, dict))
    text = text.strip()
    if not text:
        raise LLMError("empty response from LLM (writer)")
    return text


def _chat_ollama(messages: list[dict], model: str | None, temperature: float, num_predict: int | None,
                 timeout: float | None, retries: int) -> str:
    payload = {
        "model": model or config.LLM_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_predict": num_predict or config.LLM_NUM_PREDICT,
                    "num_ctx": 4096, "seed": 42},
        "keep_alive": "30m",
    }
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(f"{config.OLLAMA_URL}/api/chat", json=payload,
                              timeout=timeout or config.LLM_TIMEOUT_S)
            r.raise_for_status()
            text = (r.json().get("message") or {}).get("content", "").strip()
            if not text:
                raise LLMError("empty response from LLM")
            return text
        except (requests.RequestException, ValueError, LLMError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.0)
    raise LLMError(f"LLM call failed ({payload['model']}): {last_err}")


def is_available(timeout: float = 2.0) -> bool:
    """True if the writer can be used: an API provider has a key, or Ollama answers with the model pulled."""
    if backend() == "api":
        from src.llm.provider import provider_order
        return bool(provider_order(role="writer"))
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=timeout)
        names = {m.get("name") for m in r.json().get("models", [])}
        return config.LLM_MODEL in names or f"{config.LLM_MODEL}:latest" in names
    except Exception:
        return False
