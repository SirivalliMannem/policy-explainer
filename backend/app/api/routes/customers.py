"""Customer and policy lookup API endpoints."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.models.policy import CoreAccount, CorePolicy
from app.schemas.customer import CustomerResponse, PolicySummaryResponse

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    search: Optional[str] = Query(None, description="Search by customer name, email, or account number"),
    limit: int = Query(50, ge=1, le=100),
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Retrieve list of customers with optional name/email/account_number search filter."""
    if (employee.role or "").strip().lower() in {"unauthorized", "suspended", "inactive"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employee is not authorized to search customer records",
        )

    query = db.query(CoreAccount)
    if search and search.strip():
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            or_(
                CoreAccount.name.ilike(search_filter),
                CoreAccount.email.ilike(search_filter),
                CoreAccount.account_number.ilike(search_filter),
            )
        )
    accounts = query.order_by(CoreAccount.name.asc()).limit(limit).all()
    return [
        CustomerResponse(
            id=acc.id,
            name=acc.name,
            account_number=acc.account_number or "",
            email=acc.email or "",
            phone=acc.phone or None,
            policy_count=len(acc.policies) if acc.policies else 0,
        )
        for acc in accounts
    ]


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve a specific customer by ID."""
    customer = db.query(CoreAccount).filter(CoreAccount.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )
    return customer


@router.get("/{customer_id}/policies", response_model=list[PolicySummaryResponse])
def get_customer_policies(
    customer_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve all policies associated with a customer."""
    customer = db.query(CoreAccount).filter(CoreAccount.id == customer_id).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found",
        )

    policies = (
        db.query(CorePolicy)
        .filter(CorePolicy.account_id == customer_id)
        .order_by(CorePolicy.effective_date.desc())
        .all()
    )
    return policies
