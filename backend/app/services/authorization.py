"""Authorization and policy/customer relationship validation service."""

from __future__ import annotations

import logging
from typing import Optional
from fastapi import HTTPException, status

from app.core.auth import EmployeeUser
from app.models.policy import CoreAccount, CorePolicy

logger = logging.getLogger(__name__)

UNAUTHORIZED_ROLES = {"unauthorized", "suspended", "inactive"}


def validate_employee_authorization(
    employee: EmployeeUser,
    policy: CorePolicy,
    account: Optional[CoreAccount] = None,
) -> None:
    """Enforce that the authenticated employee is authorized to access the policy and customer.

    Derives authorization strictly from the authenticated employee session/identity,
    never from client-supplied IDs or payloads.
    """
    if not employee or not employee.id:
        logger.warning("Access denied: unauthenticated employee")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access policy context",
        )

    role = (employee.role or "").strip().lower()
    if role in UNAUTHORIZED_ROLES:
        logger.warning("Access denied: employee %s has unauthorized role '%s'", employee.id, role)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee is not authorized to access policy or customer records",
        )

    # If policy has a specific org_id requirement
    if policy.org_id and getattr(employee, "org_id", None):
        if policy.org_id != getattr(employee, "org_id"):
            logger.warning("Access denied: employee %s org mismatch with policy %s", employee.id, policy.id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Employee organization is not authorized to access this policy",
            )


def validate_policy_customer_relationship(
    policy: CorePolicy,
    customer_id: Optional[str],
) -> None:
    """Validate that the policy actually belongs to the specified customer.

    Prevents accidental or malicious cross-customer associations.
    """
    if not customer_id or not customer_id.strip():
        return

    clean_cid = customer_id.strip()
    if policy.account_id != clean_cid:
        logger.warning(
            "Customer mismatch: policy %s belongs to account %s, not specified customer %s",
            policy.policy_number,
            policy.account_id,
            clean_cid,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected policy does not belong to the specified customer",
        )
