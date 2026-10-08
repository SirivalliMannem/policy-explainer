"""SQLAlchemy models for the Policy Explainer data seed.

Contains only the models required by the synthetic demo seed:
  - CoreAccount, CorePolicy, CoreCoverage, CoreForm, CoreBilling, CoreClaim
  - Clause (citable policy wording and plain-language translations)
  - KnowledgeCollection, KnowledgeDocument (carrier guidance library)
  - GoldenQuestion (carrier-approved benchmark question set)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from data_seed.database import Base


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


class OrgScoped:
    """Mixin. Present on every seed table here."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    org_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, nullable=False)


# ── The synthetic core ──────────────────────────────────────────────────


class CoreAccount(OrgScoped, Base):
    """A policyholder. PolicyCenter calls this an Account."""

    __tablename__ = "core_account"

    account_number: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(320), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    address_line: Mapped[str] = mapped_column(String(200), default="")
    city: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(2), default="")
    postal_code: Mapped[str] = mapped_column(String(12), default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)

    household_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    household_role: Mapped[str] = mapped_column(String(40), default="")

    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class CorePolicy(OrgScoped, Base):
    """One policy period. A renewal is a second row, not an edit of the first."""

    __tablename__ = "core_policy"

    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("core_account.id"), index=True)
    policy_number: Mapped[str] = mapped_column(String(32), index=True)
    term_number: Mapped[int] = mapped_column(Integer, default=1)
    line_of_business: Mapped[str] = mapped_column(String(40), index=True)
    product_name: Mapped[str] = mapped_column(String(120), default="")
    state: Mapped[str] = mapped_column(String(2), index=True)
    status: Mapped[str] = mapped_column(String(20), default="in_force")
    effective_date: Mapped[date] = mapped_column(Date)
    expiration_date: Mapped[date] = mapped_column(Date)
    renewal_of_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    insured_location: Mapped[str] = mapped_column(String(200), default="")
    vehicles: Mapped[list] = mapped_column(JSON, default=list)
    annual_premium: Mapped[float] = mapped_column(Float, default=0.0)
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)


class CoreCoverage(OrgScoped, Base):
    """Coverages attached to a policy."""

    __tablename__ = "core_coverage"

    policy_id: Mapped[str] = mapped_column(String(36), ForeignKey("core_policy.id"), index=True)
    pattern_code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(140))
    limit_text: Mapped[str] = mapped_column(String(80), default="")
    limit_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    deductible_text: Mapped[str] = mapped_column(String(80), default="")
    deductible_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    governing_form: Mapped[str] = mapped_column(String(40), default="")
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class CoreForm(OrgScoped, Base):
    """A form attached to a policy, or product wording with no policy."""

    __tablename__ = "core_form"

    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    form_number: Mapped[str] = mapped_column(String(40), index=True)
    edition: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(30), default="base")
    line_of_business: Mapped[str] = mapped_column(String(40), index=True)
    state: Mapped[str] = mapped_column(String(2), default="")
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class CoreBilling(OrgScoped, Base):
    """BillingCenter state reduced to service conversation requirements."""

    __tablename__ = "core_billing"

    policy_id: Mapped[str] = mapped_column(String(36), index=True)
    account_number: Mapped[str] = mapped_column(String(32), default="")
    plan: Mapped[str] = mapped_column(String(40), default="Monthly")
    status: Mapped[str] = mapped_column(String(30), default="current")
    next_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_amount: Mapped[float] = mapped_column(Float, default=0.0)
    past_due_amount: Mapped[float] = mapped_column(Float, default=0.0)
    paid_to_date: Mapped[float] = mapped_column(Float, default=0.0)


class CoreClaim(OrgScoped, Base):
    """Claim details and current loss exposures."""

    __tablename__ = "core_claim"

    policy_id: Mapped[str] = mapped_column(String(36), index=True)
    claim_number: Mapped[str] = mapped_column(String(32), index=True)
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
    intake_key: Mapped[str] = mapped_column(String(80), default="", index=True)


# ── The knowledge index ─────────────────────────────────────────────────


class Clause(OrgScoped, Base):
    """One citable chunk of policy wording."""

    __tablename__ = "clause"

    form_number: Mapped[str] = mapped_column(String(40), index=True)
    edition: Mapped[str] = mapped_column(String(16))
    page: Mapped[int] = mapped_column(Integer, default=1)
    section: Mapped[str] = mapped_column(String(60), default="")
    heading: Mapped[str] = mapped_column(String(200), default="")
    text: Mapped[Text] = mapped_column(Text)
    plain_language: Mapped[str] = mapped_column(Text, default="")
    plain_language_es: Mapped[str] = mapped_column(Text, default="")
    line_of_business: Mapped[str] = mapped_column(String(40), index=True)
    state: Mapped[str] = mapped_column(String(2), default="")
    scope: Mapped[str] = mapped_column(String(20), default="product_wording", index=True)
    policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    clause_type: Mapped[str] = mapped_column(String(24), default="coverage")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    pattern_code: Mapped[str] = mapped_column(String(60), default="")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


Index("ix_clause_lookup", Clause.org_id, Clause.line_of_business, Clause.scope)


# ── Carrier guidance library ────────────────────────────────────────────


class KnowledgeCollection(OrgScoped, Base):
    """A named, owned set of documents for product guidance and service workflows."""

    __tablename__ = "knowledge_collection"

    name: Mapped[str] = mapped_column(String(160), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="product_article", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    line_of_business: Mapped[str] = mapped_column(String(40), default="", index=True)
    state: Mapped[str] = mapped_column(String(2), default="", index=True)
    channel: Mapped[str] = mapped_column(String(24), default="")
    owner: Mapped[str] = mapped_column(String(320), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    version: Mapped[str] = mapped_column(String(20), default="1")
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    seeded: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeDocument(OrgScoped, Base):
    """One article, script or procedure inside a knowledge collection."""

    __tablename__ = "knowledge_document"

    collection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("knowledge_collection.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    spoken: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[str] = mapped_column(String(20), default="1")
    approved_by: Mapped[str] = mapped_column(String(320), default="")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    seeded: Mapped[bool] = mapped_column(Boolean, default=False)


# ── Benchmark golden question set ───────────────────────────────────────


class GoldenQuestion(OrgScoped, Base):
    """Carrier-approved question set."""

    __tablename__ = "golden_question"

    line_of_business: Mapped[str] = mapped_column(String(40), index=True)
    category: Mapped[str] = mapped_column(String(40), default="coverage")
    text: Mapped[str] = mapped_column(Text)
    expects: Mapped[str] = mapped_column(String(40), default="answer")
    note: Mapped[str] = mapped_column(String(200), default="")
    expects_clause: Mapped[dict] = mapped_column(JSON, default=dict)
