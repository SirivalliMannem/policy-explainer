"""SQLAlchemy models for core insurance entities (read-only mapping)."""

from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class CoreAccount(Base):
    """Customer account model mapped to existing core_account table."""

    __tablename__ = "core_account"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_number: Mapped[str] = mapped_column(String(32), default="")
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    address_line: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(2), default="")
    postal_code: Mapped[str] = mapped_column(String(12), default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    household_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    household_role: Mapped[str] = mapped_column(String(40), default="")
    org_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    policies: Mapped[list[CorePolicy]] = relationship("CorePolicy", back_populates="account")


class CorePolicy(Base):
    """Policy model mapped to existing core_policy table."""

    __tablename__ = "core_policy"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("core_account.id"))
    policy_number: Mapped[str] = mapped_column(String(32))
    term_number: Mapped[int] = mapped_column(Integer, default=1)
    line_of_business: Mapped[str] = mapped_column(String(40))
    product_name: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(2), default="")
    status: Mapped[str] = mapped_column(String(20), default="in_force")
    effective_date: Mapped[date] = mapped_column(Date)
    expiration_date: Mapped[date] = mapped_column(Date)
    renewal_of_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    insured_location: Mapped[str] = mapped_column(String(200), default="")
    vehicles: Mapped[list] = mapped_column(JSON, default=list)
    annual_premium: Mapped[float] = mapped_column(Float, default=0.0)
    org_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    account: Mapped[CoreAccount] = relationship("CoreAccount", back_populates="policies")
    coverages: Mapped[list[CoreCoverage]] = relationship("CoreCoverage", back_populates="policy")
    forms: Mapped[list[CoreForm]] = relationship("CoreForm", back_populates="policy")
    claims: Mapped[list[CoreClaim]] = relationship("CoreClaim", back_populates="policy")
    billing_records: Mapped[list[CoreBilling]] = relationship("CoreBilling", back_populates="policy")


class CoreCoverage(Base):
    """Coverage items mapped to existing core_coverage table."""

    __tablename__ = "core_coverage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("core_policy.id"))
    pattern_code: Mapped[str] = mapped_column(String(60), default="")
    name: Mapped[str] = mapped_column(String(140))
    limit_text: Mapped[str] = mapped_column(String(80), default="")
    limit_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    deductible_text: Mapped[str] = mapped_column(String(80), default="")
    deductible_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    governing_form: Mapped[str] = mapped_column(String(40), default="")
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    org_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    policy: Mapped[CorePolicy] = relationship("CorePolicy", back_populates="coverages")


class CoreForm(Base):
    """Forms attached to policies mapped to existing core_form table."""

    __tablename__ = "core_form"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("core_policy.id"), nullable=True)
    form_number: Mapped[str] = mapped_column(String(40))
    edition: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="base")
    line_of_business: Mapped[str] = mapped_column(String(40), default="")
    state: Mapped[str] = mapped_column(String(2), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    org_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    policy: Mapped[CorePolicy | None] = relationship("CorePolicy", back_populates="forms")


class CoreClaim(Base):
    """Claims mapped to existing core_claim table."""

    __tablename__ = "core_claim"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("core_policy.id"))
    claim_number: Mapped[str] = mapped_column(String(32))
    loss_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reported_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    loss_cause: Mapped[str] = mapped_column(String(60), default="")
    loss_location: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="open")
    adjuster: Mapped[str] = mapped_column(String(120), default="")
    exposures: Mapped[list] = mapped_column(JSON, default=list)
    contacts: Mapped[list] = mapped_column(JSON, default=list)
    created_by_agent: Mapped[str] = mapped_column(String(10), default="")
    intake_key: Mapped[str] = mapped_column(String(80), default="")
    org_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    policy: Mapped[CorePolicy] = relationship("CorePolicy", back_populates="claims")


class CoreBilling(Base):
    """Billing state mapped to existing core_billing table."""

    __tablename__ = "core_billing"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("core_policy.id"))
    account_number: Mapped[str] = mapped_column(String(32), default="")
    plan: Mapped[str] = mapped_column(String(40), default="Monthly")
    status: Mapped[str] = mapped_column(String(30), default="current")
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_amount: Mapped[float] = mapped_column(Float, default=0.0)
    past_due_amount: Mapped[float] = mapped_column(Float, default=0.0)
    paid_to_date: Mapped[float] = mapped_column(Float, default=0.0)
    org_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    policy: Mapped[CorePolicy] = relationship("CorePolicy", back_populates="billing_records")


class Clause(Base):
    """Citable policy wording chunk mapped to existing clause table."""

    __tablename__ = "clause"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    form_number: Mapped[str] = mapped_column(String(40), index=True)
    edition: Mapped[str] = mapped_column(String(16))
    page: Mapped[int] = mapped_column(Integer, default=1)
    section: Mapped[str] = mapped_column(String(60), default="")
    heading: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[str] = mapped_column(Text)
    plain_language: Mapped[str] = mapped_column(Text, default="")
    plain_language_es: Mapped[str] = mapped_column(Text, default="")
    line_of_business: Mapped[str] = mapped_column(String(40), index=True)
    state: Mapped[str] = mapped_column(String(2), default="")
    scope: Mapped[str] = mapped_column(String(20), default="customer_form", index=True)
    clause_type: Mapped[str] = mapped_column(String(24), default="coverage")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    pattern_code: Mapped[str] = mapped_column(String(60), default="")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    org_id: Mapped[str] = mapped_column(String(36), default="")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

