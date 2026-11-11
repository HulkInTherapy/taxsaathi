"""
Live smoke test of the agent LLM gateway (uses real API keys from .env).

    python -m scripts.llm_smoke

Checks, per provider and role: a tool call comes back with the right arguments, personal data
never reaches the provider (we inspect what was sent) and comes back restored, and a forced
failure of the primary provider falls back to the next one.
"""
from __future__ import annotations

import sys

from pydantic import BaseModel, Field

from src import config
from src.llm import provider as prov
from src.llm.masking import Masker


class calculate_tax(BaseModel):
    """Compare Indian income tax under the old and new regimes."""
    gross_salary: int = Field(description="annual gross salary in rupees")
    deductions_80c: int = Field(0, description="section 80C deductions in rupees")
    pan: str = Field("", description="taxpayer PAN, if given")


PROMPT = ("I am Asha Rao, PAN ABCDE1234F. Salary 15 lakh a year, 1.5 lakh in 80C. "
          "Which regime is better? Use the tool and pass my PAN.")


def check(provider: str, role: str) -> bool:
    masker = Masker()
    masker.add("Asha Rao")
    sent = {}
    real_get = prov.get_model

    def spy(p, r):  # capture the exact messages that leave the server
        model = real_get(p, r)

        class Spy:
            model_name = model.model_name

            def bind_tools(self, tools, tool_choice=None):
                bound = model.bind_tools(tools, tool_choice=tool_choice)

                class B:
                    def invoke(self, msgs):
                        sent["text"] = " ".join(str(m.content) for m in msgs)
                        return bound.invoke(msgs)
                return B()
        return Spy()

    prov.get_model = spy
    try:
        usage = prov.Usage()
        out = prov.chat([{"role": "user", "content": PROMPT}], role=role, tools=[calculate_tax],
                        masker=masker, usage=usage, providers=[provider])
    except prov.LLMUnavailable as e:
        print(f"  ✗ {provider}/{role}: {e}")
        return False
    finally:
        prov.get_model = real_get
    leaked = [s for s in ("ABCDE1234F", "Asha Rao") if s in sent.get("text", "")]
    call = out.tool_calls[0] if out.tool_calls else None
    ok = (not leaked and call is not None and call["name"] == "calculate_tax"
          and int(call["args"].get("gross_salary", 0)) == 1_500_000
          and int(call["args"].get("deductions_80c", 0)) == 150_000)
    pan_back = call and call["args"].get("pan") == "ABCDE1234F"
    print(f"  {'✓' if ok else '✗'} {provider}/{role} [{out.response_metadata['taxot_model']}] "
          f"{usage.latency_ms} ms, {usage.input_tokens}+{usage.output_tokens} tokens, "
          f"args={call['args'] if call else None}, leaked={leaked or 'none'}, PAN restored={bool(pan_back)}")
    return ok


def check_fallback() -> bool:
    order = prov.provider_order()
    if len(order) < 2:
        print("  - fallback: skipped (only one provider has a key)")
        return True
    primary = order[0]
    saved = config.PROVIDERS[primary]["models"]["planner"]
    config.PROVIDERS[primary]["models"]["planner"] = "no-such-model/for-fallback-test"
    prov._MODELS.clear()
    try:
        usage = prov.Usage()
        out = prov.chat([{"role": "user", "content": "Reply with the single word OK."}], usage=usage)
        served = out.response_metadata["taxot_provider"]
        ok = served != primary and usage.fallbacks == 1
        print(f"  {'✓' if ok else '✗'} fallback: {primary} failed -> served by {served}")
        return ok
    except prov.LLMUnavailable as e:
        print(f"  ✗ fallback: {e}")
        return False
    finally:
        config.PROVIDERS[primary]["models"]["planner"] = saved
        prov._MODELS.clear()


def main() -> int:
    order = prov.provider_order()
    print(f"providers with keys (in order): {order}")
    results = []
    for p in order:
        for role in sorted({r for r in prov.ROLES}, key=prov.ROLES.index):
            results.append(check(p, role))
    results.append(check_fallback())
    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
