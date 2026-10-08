"""Pydantic schemas for policy details, coverages, forms, claims, and billing."""

from datetime import date
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class PolicyDetailResponse(BaseModel):
    """Detailed policy information including customer context."""

    model_config = ConfigDict(from_attributes=True)

    policy_id: str
    policy_number: str
    customer_id: str
    customer_name: str
    line_of_business: str
    product_name: Optional[str] = None
    status: str
    effective_date: date
    expiration_date: date
    term_number: int
    insured_location: str
    annual_premium: float


class CoverageResponse(BaseModel):
    """Policy coverage item response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str
    name: str
    pattern_code: Optional[str] = None
    limit_text: Optional[str] = None
    limit_amount: Optional[float] = None
    deductible_text: Optional[str] = None
    deductible_amount: Optional[float] = None
    governing_form: Optional[str] = None
    included: bool = True
    sort_order: int = 0


class FormResponse(BaseModel):
    """Attached form/endorsement specification response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: Optional[str] = None
    form_number: str
    edition: str
    title: str
    kind: str
    line_of_business: str
    state: Optional[str] = None
    page_count: int = 1
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class ClaimResponse(BaseModel):
    """Claim history item response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str
    claim_number: str
    loss_date: Optional[date] = None
    reported_date: Optional[date] = None
    loss_cause: Optional[str] = None
    loss_location: Optional[str] = None
    description: Optional[str] = None
    status: str
    adjuster: Optional[str] = None
    exposures: list[Any] = []
    contacts: list[Any] = []


class BillingResponse(BaseModel):
    """Billing and payment record response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_id: str
    account_number: Optional[str] = None
    plan: str
    status: str
    next_due_date: Optional[date] = None
    next_due_amount: float = 0.0
    past_due_amount: float = 0.0
    paid_to_date: float = 0.0
