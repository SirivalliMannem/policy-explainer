"""Employee authentication and identity dependency boundary.

Provides a clean abstraction that can later be swapped with SSO/JWT without
affecting route or business logic.
"""

from dataclasses import dataclass
from fastapi import Header


@dataclass
class EmployeeUser:
    """Represents the authenticated employee/operator."""

    id: str
    name: str
    email: str


def get_current_employee(
    x_employee_id: str | None = Header(default=None, alias="X-Employee-Id"),
) -> EmployeeUser:
    """Resolve current employee identity from request header or default session."""
    employee_id = x_employee_id.strip() if x_employee_id and x_employee_id.strip() else "emp_demo_01"
    return EmployeeUser(
        id=employee_id,
        name="Demo Employee",
        email=f"{employee_id}@policyexplainer.internal",
    )
