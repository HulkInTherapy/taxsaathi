"""
Shared task state for the LangGraph orchestrator, and the user-facts schema.

The state is what the checkpointer saves after every step (so a task survives page reloads and
continues across turns): goal, plan, collected facts, figures, specialist results, approvals,
findings, the trace. It holds only plain JSON data. Live resources (uploaded documents, the
mask table, the tool budget) live in the in-memory TaskContext/ToolBox for the task and are
deleted with it; nothing here contains raw document text.
"""
from __future__ import annotations

import operator
from typing import Annotated, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

Workflow = Literal["document_check", "filing_prep", "tax_saving"]
STEPS = ("documents", "facts", "figures", "itr_form", "gst", "regime", "escalation", "checklist")


class UserFacts(BaseModel):
    """Facts about the taxpayer that are not in the documents (all optional until asked)."""
    age: Optional[int] = Field(None, ge=0, le=120)
    residential_status: Optional[Literal["resident", "rnor", "non_resident"]] = None
    # income not covered by Form 16 / certificates
    freelance_receipts: Optional[int] = Field(None, ge=0, description="Gross professional/business receipts in the year")
    business_presumptive: Optional[bool] = Field(None, description="Declares business income on a presumptive basis "
                                                                    "(44AD/44ADA) without detailed books")
    cash_receipts_over_5pct: Optional[bool] = None
    salary_without_form16: Optional[int] = Field(None, ge=0, description="Salary not covered by any uploaded Form 16")
    other_interest: Optional[int] = Field(None, ge=0, description="Interest not covered by uploaded certificates")
    # for the old regime
    epf_annual: Optional[int] = Field(None, ge=0, description="Employee PF deducted from salary in the year")
    other_80c: Optional[int] = Field(None, ge=0, description="80C investments besides PF (PPF, ELSS, LIC, tuition...)")
    health_80d: Optional[int] = Field(None, ge=0, description="Health insurance premium for self/family")
    health_80d_parents: Optional[int] = Field(None, ge=0)
    parents_senior: Optional[bool] = None
    nps_80ccd1b: Optional[int] = Field(None, ge=0)
    home_loan_interest: Optional[int] = Field(None, ge=0)
    rent_monthly: Optional[int] = Field(None, ge=0, description="Rent paid per month, 0 if none")
    metro_city: Optional[bool] = Field(None, description="Lives in Delhi, Mumbai, Kolkata or Chennai")
    basic_monthly: Optional[int] = Field(None, ge=0, description="Basic salary per month (needed for HRA)")
    hra_monthly: Optional[int] = Field(None, ge=0, description="HRA received per month")
    hra_exemption_annual: Optional[int] = Field(None, ge=0, description="HRA exemption already worked out for the "
                                                                         "year (e.g. by employer or CA), if known")
    # facts that decide the ITR form / escalation
    short_term_capital_gains: Optional[bool] = None
    ltcg_112a: Optional[int] = Field(None, ge=0, description="Long-term gains on listed equity / equity funds")
    other_capital_gains: Optional[bool] = Field(None, description="Sold property, gold, debt funds etc.")
    house_properties: Optional[int] = Field(None, ge=0)
    foreign_assets_or_income: Optional[bool] = None
    company_director: Optional[bool] = None
    unlisted_shares: Optional[bool] = None
    fno_trading: Optional[bool] = None
    losses_to_carry_forward: Optional[bool] = None
    wants_gst_advice: Optional[bool] = None


class TaskState(TypedDict, total=False):
    task_id: str
    goal: str
    tax_year: str
    workflow: Workflow
    plan: list[dict]                      # [{"step", "status": pending|done|skipped, "note"}]
    facts: dict                           # UserFacts as dict (None = unknown)
    facts_rounds: int
    assumptions: list[str]
    documents_report: dict                # document agent output (report + cross_check)
    figures: dict                         # {"inputs": TaxInputs dict, "provenance": {...}, "tds": ...}
    itr: dict
    gst: dict
    regime: dict
    escalation: dict                      # {"escalate": bool, "reasons": [...], "ca_summary": md}
    checklist: dict
    approvals: dict                       # step -> {"approved": bool, "note": str}
    final: dict
    error: Optional[str]
    trace: Annotated[list[dict], operator.add]


def new_plan(steps: list[str]) -> list[dict]:
    return [{"step": s, "status": "pending", "note": ""} for s in steps]


def facts_obj(state: TaskState) -> UserFacts:
    return UserFacts(**{k: v for k, v in (state.get("facts") or {}).items() if k in UserFacts.model_fields})


NULL_STRINGS = {"none", "null", "n/a", "na", "unknown", "not mentioned", "not stated", ""}


def lenient_validate(model: type[BaseModel], args: dict) -> BaseModel:
    """Validate LLM tool arguments, treating "None"/"null" strings as missing and dropping any single field
    that still fails, instead of rejecting the whole answer."""
    from pydantic import ValidationError
    clean = {k: (None if isinstance(v, str) and v.strip().lower() in NULL_STRINGS else v) for k, v in (args or {}).items()}
    for _ in range(len(clean) + 1):
        try:
            return model.model_validate(clean)
        except ValidationError as e:
            bad = {err["loc"][0] for err in e.errors() if err["loc"]}
            if not bad or not bad & set(clean):
                raise
            for k in bad:
                clean.pop(k, None)
    return model.model_validate({})
