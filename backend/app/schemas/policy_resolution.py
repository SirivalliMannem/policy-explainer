"""Schemas for policy resolution candidate search and resolution."""

from datetime import date
from typing import Any, Optional
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
    # When given, the question's understanding is cached for that conversation's next submission,
    # and the conversation's previous question helps resolve follow-ups.
    conversation_id: Optional[str] = None


class QuestionResolution(BaseModel):
    """Outcome of resolving a policy reference from a question."""

    status: str  # resolved | ambiguous | not_found | no_reference
    # policy: about one policy's contents; portfolio: counts or lists policies/customers
    intent: str = "policy"
    matched_on: Optional[str] = None
    reference: Optional[str] = None
    policy: Optional[PolicyContextCandidate] = None
    candidates: list[PolicyContextCandidate] = []
    message: str = ""
    # How the question was understood (corrected wording, names, policy numbers, search terms).
    interpretation: Optional[dict[str, Any]] = None
