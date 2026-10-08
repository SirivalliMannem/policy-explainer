"""Schemas for policy resolution candidate search and resolution."""

from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PolicyContextCandidate(BaseModel):
    """Candidate policy context representation for resolution lookup."""

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


class PolicyResolveRequest(BaseModel):
    """Request payload to resolve policy context by policy_id."""

    policy_id: str


class QuestionResolveRequest(BaseModel):
    """Request payload to resolve the policy a free-text question refers to."""

    question: str


class QuestionResolution(BaseModel):
    """Outcome of resolving a policy reference from a question."""

    status: str  # resolved | ambiguous | not_found | no_reference
    matched_on: Optional[str] = None
    reference: Optional[str] = None
    policy: Optional[PolicyContextCandidate] = None
    candidates: list[PolicyContextCandidate] = []
    message: str = ""
