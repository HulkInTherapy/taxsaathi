"""
Tiny client for the local LLM served by Ollama (http://127.0.0.1:11434).

We call the /api/chat endpoint with temperature 0 (deterministic, no creativity) and a short
output limit, because the model only has to write 2-5 sentences. One retry on network errors;
any failure raises LLMError so the caller can fall back to an extractive answer.
Model name comes from the TAXSAATHI_LLM environment variable (default qwen2.5:3b).
"""
from __future__ import annotations

import time

import requests

from src import config


class LLMError(RuntimeError):
    """Raised when the LLM cannot be reached or returns nothing useful."""


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.0,
         num_predict: int | None = None, timeout: float | None = None, retries: int = 1) -> str:
    """Send chat messages [{"role": "system"|"user", "content": str}] and return the reply text."""
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
    """True if Ollama answers and has the configured model pulled."""
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/tags", timeout=timeout)
        names = {m.get("name") for m in r.json().get("models", [])}
        return config.LLM_MODEL in names or f"{config.LLM_MODEL}:latest" in names
    except Exception:
        return False
