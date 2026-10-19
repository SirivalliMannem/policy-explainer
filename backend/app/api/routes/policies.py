from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.models.policy import (
    CoreAccount,
    CoreBilling,
    CoreClaim,
    CoreCoverage,
    CoreForm,
    CorePolicy,
)
from app.schemas.policy import (
    BillingResponse,
    ClaimResponse,
    CoverageResponse,
    FormResponse,
    PolicyDetailResponse,
    PolicyListItemResponse,
)

router = APIRouter(prefix="/api/policies", tags=["policies"])


@router.get("", response_model=list[PolicyListItemResponse])
def list_policies(
    search: Optional[str] = Query(None, description="Search by policy number, customer name, account number, or line of business"),
    customer_id: Optional[str] = Query(None, description="Filter by customer account ID"),
    limit: int = Query(50, ge=1, le=100),
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Search and list policies with customer context and authorization checks."""
    if (employee.role or "").strip().lower() in {"unauthorized", "suspended", "inactive"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee is not authorized to search policy records",
        )

    query = db.query(CorePolicy).join(CoreAccount, CorePolicy.account_id == CoreAccount.id)

    if customer_id and customer_id.strip():
        query = query.filter(CorePolicy.account_id == customer_id.strip())

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                CorePolicy.policy_number.ilike(term),
                CoreAccount.name.ilike(term),
                CoreAccount.account_number.ilike(term),
                CorePolicy.line_of_business.ilike(term),
                CorePolicy.product_name.ilike(term),
            )
        )

    policies = query.order_by(CorePolicy.effective_date.desc()).limit(limit).all()

    return [
        PolicyListItemResponse(
            id=p.id,
            policy_number=p.policy_number,
            customer_id=p.account_id,
            customer_name=p.account.name if p.account else "",
            customer_account_number=p.account.account_number if p.account else None,
            line_of_business=p.line_of_business,
            product_name=p.product_name,
            status=p.status,
            effective_date=p.effective_date,
            expiration_date=p.expiration_date,
        )
        for p in policies
    ]


def _get_policy_or_404(policy_id: str, db: Session) -> CorePolicy:
    """Helper to verify policy existence or raise 404."""
    policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id.strip()).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    return policy


@router.get("/{policy_id}", response_model=PolicyDetailResponse)
def get_policy_details(
    policy_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve comprehensive details for a specific policy."""
    policy = _get_policy_or_404(policy_id, db)
    return PolicyDetailResponse(
        policy_id=policy.id,
        policy_number=policy.policy_number,
        customer_id=policy.account_id,
        customer_name=policy.account.name if policy.account else "",
        line_of_business=policy.line_of_business,
        product_name=policy.product_name,
        status=policy.status,
        effective_date=policy.effective_date,
        expiration_date=policy.expiration_date,
        term_number=policy.term_number,
        insured_location=policy.insured_location,
        annual_premium=policy.annual_premium,
    )


@router.get("/{policy_id}/coverages", response_model=list[CoverageResponse])
def get_policy_coverages(
    policy_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve structured coverages associated with a policy."""
    _get_policy_or_404(policy_id, db)
    coverages = (
        db.query(CoreCoverage)
        .filter(CoreCoverage.policy_id == policy_id)
        .order_by(CoreCoverage.sort_order.asc(), CoreCoverage.name.asc())
        .all()
    )
    return coverages


@router.get("/{policy_id}/forms", response_model=list[FormResponse])
def get_policy_forms(
    policy_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve forms and endorsements attached to a policy."""
    _get_policy_or_404(policy_id, db)
    forms = (
        db.query(CoreForm)
        .filter(CoreForm.policy_id == policy_id)
        .order_by(CoreForm.form_number.asc())
        .all()
    )
    return forms


@router.get("/{policy_id}/claims", response_model=list[ClaimResponse])
def get_policy_claims(
    policy_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve claims associated with a policy."""
    _get_policy_or_404(policy_id, db)
    claims = (
        db.query(CoreClaim)
        .filter(CoreClaim.policy_id == policy_id)
        .order_by(CoreClaim.loss_date.desc().nullslast())
        .all()
    )
    return claims


@router.get("/{policy_id}/billing", response_model=list[BillingResponse])
def get_policy_billing(
    policy_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve billing and payment schedule for a policy."""
    _get_policy_or_404(policy_id, db)
    billing_records = (
        db.query(CoreBilling)
        .filter(CoreBilling.policy_id == policy_id)
        .all()
    )
    return billing_records
