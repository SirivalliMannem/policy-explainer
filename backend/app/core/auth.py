"""Employee authentication and identity dependency boundary.

Provides a clean abstraction that can later be swapped with SSO/JWT without
affecting route or business logic.

DEVELOPMENT ONLY: identity is read from request headers set by the frontend's simulated
login. Any client can set these headers, so per-employee isolation built on them is not
access control. Replace this dependency with verified tokens before production.
"""

from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote

from fastapi import Header

DEFAULT_EMPLOYEE_ID = "emp_demo_01"


@dataclass
class EmployeeUser:
    """Represents the authenticated employee/operator."""

    id: str
    name: str
    email: str
    role: Optional[str] = None
    # False when no identity was sent and the placeholder employee is used.
    identified: bool = False

    @property
    def first_name(self) -> Optional[str]:
        """For addressing the employee; None for the placeholder employee."""
        if not self.identified or not self.name:
            return None
        return self.name.split()[0]


def _clean(value: Optional[str], limit: int) -> Optional[str]:
    if not value:
        return None
    text = unquote(value).strip()
    return text[:limit] or None


def get_current_employee(
    x_employee_id: str | None = Header(default=None, alias="X-Employee-Id"),
    x_employee_name: str | None = Header(default=None, alias="X-Employee-Name"),
    x_employee_role: str | None = Header(default=None, alias="X-Employee-Role"),
) -> EmployeeUser:
    """Resolve current employee identity from request headers, or the placeholder employee."""
    employee_id = _clean(x_employee_id, 100)
    if not employee_id:
        return EmployeeUser(
            id=DEFAULT_EMPLOYEE_ID,
            name="Demo Employee",
            email=f"{DEFAULT_EMPLOYEE_ID}@policyexplainer.internal",
        )
    return EmployeeUser(
        id=employee_id,
        # Names and roles arrive URL-encoded so non-ASCII names survive HTTP headers.
        name=_clean(x_employee_name, 160) or employee_id,
        email=f"{employee_id}@policyexplainer.internal",
        role=_clean(x_employee_role, 60),
        identified=True,
    )
