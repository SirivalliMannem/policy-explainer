"""Service for evaluating and auditing customer and policy context transitions."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser
from app.models.conversation import ContextSwitchAudit
from app.models.policy import CorePolicy
from app.schemas.conversation import ContextCheckResponse, CustomerSummary, PolicySummary

logger = logging.getLogger(__name__)


def evaluate_context_transition(
    current_policy: Optional[CorePolicy],
    target_policy: CorePolicy,
) -> ContextCheckResponse:
    """Determine the switch scenario between the current conversation context and target policy."""
    target_cust = CustomerSummary(
        id=target_policy.account_id,
        name=target_policy.account.name if target_policy.account else "Unknown Customer",
    )
    target_pol = PolicySummary(
        id=target_policy.id,
        policy_number=target_policy.policy_number,
        line_of_business=target_policy.line_of_business,
        product_name=target_policy.product_name,
    )

    if not current_policy:
        return ContextCheckResponse(
            switch_type="initial_selection",
            requires_confirmation=False,
            current_customer=None,
            current_policy=None,
            target_customer=target_cust,
            target_policy=target_pol,
            allowed=True,
            message="Initial policy selection for conversation.",
        )

    current_cust = CustomerSummary(
        id=current_policy.account_id,
        name=current_policy.account.name if current_policy.account else "Unknown Customer",
    )
    current_pol = PolicySummary(
        id=current_policy.id,
        policy_number=current_policy.policy_number,
        line_of_business=current_policy.line_of_business,
        product_name=current_policy.product_name,
    )

    if current_policy.id == target_policy.id:
        return ContextCheckResponse(
            switch_type="same_customer_same_policy",
            requires_confirmation=False,
            current_customer=current_cust,
            current_policy=current_pol,
            target_customer=target_cust,
            target_policy=target_pol,
            allowed=True,
            message="Target policy matches currently active context.",
        )

    if current_policy.account_id == target_policy.account_id:
        return ContextCheckResponse(
            switch_type="same_customer_different_policy",
            requires_confirmation=False,
            current_customer=current_cust,
            current_policy=current_pol,
            target_customer=target_cust,
            target_policy=target_pol,
            allowed=True,
            message=f"Switching policy for {current_cust.name} to {target_pol.policy_number}.",
        )

    # Different customer!
    return ContextCheckResponse(
        switch_type="different_customer",
        requires_confirmation=True,
        current_customer=current_cust,
        current_policy=current_pol,
        target_customer=target_cust,
        target_policy=target_pol,
        allowed=True,
        message=(
            f"You're currently discussing a policy belonging to {current_cust.name}. "
            f"The selected policy belongs to {target_cust.name}."
        ),
    )


def record_context_switch(
    db: Session,
    conversation_id: str,
    employee: EmployeeUser,
    previous_policy: Optional[CorePolicy],
    new_policy: Optional[CorePolicy],
    switch_type: str,
    outcome: str,
    reason: Optional[str] = None,
) -> ContextSwitchAudit:
    """Record a context transition event into the audit ledger."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    prev_cust_id = previous_policy.account_id if previous_policy else None
    prev_cust_name = previous_policy.account.name if previous_policy and previous_policy.account else None
    prev_pol_id = previous_policy.id if previous_policy else None
    prev_pol_num = previous_policy.policy_number if previous_policy else None

    new_cust_id = new_policy.account_id if new_policy else None
    new_cust_name = new_policy.account.name if new_policy and new_policy.account else None
    new_pol_id = new_policy.id if new_policy else None
    new_pol_num = new_policy.policy_number if new_policy else None

    audit_entry = ContextSwitchAudit(
        conversation_id=conversation_id,
        employee_id=employee.id,
        employee_name=employee.name if employee.identified else None,
        employee_role=employee.role if employee.identified else None,
        timestamp=now,
        previous_customer_id=prev_cust_id,
        previous_customer_name=prev_cust_name,
        previous_policy_id=prev_pol_id,
        previous_policy_number=prev_pol_num,
        new_customer_id=new_cust_id,
        new_customer_name=new_cust_name,
        new_policy_id=new_pol_id,
        new_policy_number=new_pol_num,
        switch_type=switch_type,
        outcome=outcome,
        reason=reason,
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(audit_entry)
    logger.info(
        "Recorded context switch for conv %s: %s -> %s (type=%s, outcome=%s)",
        conversation_id,
        prev_pol_num or "none",
        new_pol_num or "none",
        switch_type,
        outcome,
    )
    return audit_entry
