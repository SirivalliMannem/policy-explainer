"""Policy context summary schema."""

from typing import Optional
from pydantic import BaseModel, ConfigDict


class PolicyContextSummary(BaseModel):
    """Context of the currently resolved policy."""

    model_config = ConfigDict(from_attributes=True)

    policy_id: str
    policy_number: str
    customer_id: str
    customer_name: str
    line_of_business: Optional[str] = None
    product_name: Optional[str] = None
    status: Optional[str] = None
