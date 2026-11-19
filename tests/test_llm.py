"""Tests for the LLM gateway: reversible masking, provider order, fallback and unmasking.
No network: provider models are replaced with fakes."""
import openai
import pytest
from langchain_core.messages import AIMessage

from src import config
from src.llm import provider as prov
from src.llm.masking import Masker


# ------------------------------------------------------------------ masking
def test_mask_roundtrip_and_stable_placeholders():
    m = Masker()
    m.add("Asha Rao")
    text = ("Employee Asha Rao, PAN ABCDE1234F, Aadhaar 2345 6789 0123, phone +91 98765 43210, "
            "asha@example.com, A/c No: 123456789012. ASHA RAO again; PAN ABCDE1234F again.")
    masked = m.mask(text)
    for secret in ["Asha Rao", "ASHA RAO", "ABCDE1234F", "2345 6789 0123", "98765 43210",
                   "asha@example.com", "123456789012"]:
        assert secret not in masked
    assert masked.count("<PAN_1>") == 2 and masked.count("<NAME_1>") == 2
    assert "<ACCOUNT_1>" in masked and "<AADHAAR_1>" in masked
    # restoring gives the original values back (names restored in their registered spelling)
    assert "ABCDE1234F" in m.unmask(masked) and "123456789012" in m.unmask(masked)


def test_mask_leaves_amounts_and_sections_alone():
    m = Masker()
    text = "Gross salary 1250000, interest 42,000, deduction u/s 80C of 150000 in FY 2025-26."
    assert m.mask(text) == text


def test_two_different_pans_get_different_placeholders():
    m = Masker()
    out = m.mask("Form 16 PAN ABCDE1234F, certificate PAN ABCDE1234G")
    assert "<PAN_1>" in out and "<PAN_2>" in out


def test_mask_obj_nested():
    m = Masker()
    obj = m.mask_obj({"a": ["PAN ABCDE1234F", 5], "b": {"c": "x"}})
    assert obj == {"a": ["PAN <PAN_1>", 5], "b": {"c": "x"}}
    assert m.unmask_obj(obj)["a"][0] == "PAN ABCDE1234F"


# ------------------------------------------------------------------ provider
class FakeModel:
    """Stands in for ChatOpenAI; records what it was sent."""

    def __init__(self, name, reply=None, error=None):
        self.model_name, self.reply, self.error, self.sent = name, reply, error, None

    def bind_tools(self, tools, tool_choice=None):
        return self

    def invoke(self, messages):
        self.sent = messages
        if self.error:
            raise self.error
        return self.reply


def _rate_limit_error():
    import httpx
    resp = httpx.Response(429, request=httpx.Request("POST", "https://x"))
    return openai.RateLimitError("rate limited", response=resp, body=None)


@pytest.fixture
def keys(monkeypatch, tmp_path):
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "REGOLO_API_KEY"):   # tests control exactly which providers have keys
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("NVIDIA_API_KEY", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "y")
    monkeypatch.setattr(config, "LLM_USAGE_LOG", tmp_path / "usage.jsonl")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path)


def test_provider_order(keys, monkeypatch):
    assert prov.provider_order("nvidia") == ["nvidia", "openrouter"]
    assert prov.provider_order("openrouter") == ["openrouter", "nvidia"]
    monkeypatch.delenv("OPENROUTER_API_KEY")
    assert prov.provider_order("nvidia") == ["nvidia"]


def test_chat_masks_outgoing_and_unmasks_reply(keys, monkeypatch):
    reply = AIMessage(content="PAN <PAN_1> has interest missing",
                      tool_calls=[{"name": "flag", "args": {"pan": "<PAN_1>"}, "id": "1"}],
                      usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15})
    fake = FakeModel("m", reply=reply)
    monkeypatch.setattr(prov, "get_model", lambda p, r, mt=None: fake)
    usage = prov.Usage()
    out = prov.chat([{"role": "user", "content": "My PAN is ABCDE1234F"}], usage=usage, providers=["nvidia"])
    assert "ABCDE1234F" not in fake.sent[0].content and "<PAN_1>" in fake.sent[0].content
    assert out.content == "PAN ABCDE1234F has interest missing"
    assert out.tool_calls[0]["args"] == {"pan": "ABCDE1234F"}
    assert usage.calls == 1 and usage.input_tokens == 10 and usage.by_provider == {"nvidia": 1}
    assert out.response_metadata["taxot_provider"] == "nvidia"


def test_chat_falls_back_on_rate_limit(keys, monkeypatch):
    models = {"nvidia": FakeModel("a", error=_rate_limit_error()),
              "openrouter": FakeModel("b", reply=AIMessage(content="ok"))}
    monkeypatch.setattr(prov, "get_model", lambda p, r, mt=None: models[p])
    usage = prov.Usage()
    out = prov.chat([{"role": "user", "content": "hi"}], usage=usage, providers=["nvidia", "openrouter"])
    assert out.content == "ok" and out.response_metadata["taxot_provider"] == "openrouter"
    assert usage.fallbacks == 1


def test_chat_does_not_swallow_programming_errors(keys, monkeypatch):
    models = {"nvidia": FakeModel("a", error=ValueError("bad request shape")),
              "openrouter": FakeModel("b", reply=AIMessage(content="ok"))}
    monkeypatch.setattr(prov, "get_model", lambda p, r, mt=None: models[p])
    with pytest.raises(prov.LLMUnavailable):
        prov.chat([{"role": "user", "content": "hi"}], providers=["nvidia", "openrouter"])


def test_chat_without_keys_raises(monkeypatch):
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "REGOLO_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(prov.LLMUnavailable):
        prov.chat([{"role": "user", "content": "hi"}])


def test_waits_and_retries_when_every_provider_is_rate_limited(keys, monkeypatch):
    calls = {"n": 0}

    class Flaky(FakeModel):
        def invoke(self, messages):
            calls["n"] += 1
            if calls["n"] <= 2:           # first round: both providers 429
                raise _rate_limit_error()
            return AIMessage(content="ok")
    models = {"nvidia": Flaky("a"), "openrouter": Flaky("b")}
    monkeypatch.setattr(prov, "get_model", lambda p, r, mt=None: models[p])
    slept = []
    monkeypatch.setattr(prov.time, "sleep", lambda s: slept.append(s))
    out = prov.chat([{"role": "user", "content": "hi"}], providers=["nvidia", "openrouter"])
    assert out.content == "ok" and slept == [prov.RATE_LIMIT_BACKOFF_S[0]]


def test_gives_up_after_backoff(keys, monkeypatch):
    models = {"nvidia": FakeModel("a", error=_rate_limit_error()), "openrouter": FakeModel("b", error=_rate_limit_error())}
    monkeypatch.setattr(prov, "get_model", lambda p, r, mt=None: models[p])
    monkeypatch.setattr(prov.time, "sleep", lambda s: None)
    with pytest.raises(prov.LLMUnavailable, match="rate-limited"):
        prov.chat([{"role": "user", "content": "hi"}], providers=["nvidia", "openrouter"])


def test_unmask_accepts_placeholders_without_brackets():
    m = Masker()
    m.mask("PAN ABCDE1234F")
    assert m.unmask("pan: PAN_1") == "pan: ABCDE1234F" and m.unmask("<PAN_1>") == "ABCDE1234F"
    assert m.unmask("SECTION_80 and PAN_7") == "SECTION_80 and PAN_7"   # unknown tokens untouched
