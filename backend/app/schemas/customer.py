"""Customer and policy response schemas."""

from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CustomerResponse(BaseModel):
    """Customer account response representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    phone: Optional[str] = None


class PolicySummaryResponse(BaseModel):
    """Policy summary response representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    policy_number: str
    line_of_business: str
    product_name: Optional[str] = None
    status: str
    effective_date: date
    expiration_date: date
