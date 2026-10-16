"""Source document endpoints backing the citation viewer.

The synthetic book stores policy wording as structured clause rows (form, edition, page, section,
heading, text) rather than PDF files, so the viewer is given that structured representation and is
told explicitly that no PDF exists. Every field of a source comes from the seeded form library or
the policy's own schedule; the one generated thing, an on-request plain-language explanation of a
cited clause, is returned separately and labelled as an AI explanation.
"""

from __future__ import annotations

from typing import Optional

import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import EmployeeUser, get_current_employee
from app.db.database import get_db
from app.services.ai_client import ai_client
from app.services.authorization import UNAUTHORIZED_ROLES
from app.models.policy import Clause, CoreBilling, CoreClaim, CoreCoverage, CoreForm, CorePolicy

router = APIRouter(prefix="/api/sources", tags=["sources"])
logger = logging.getLogger(__name__)


class SourcePassage(BaseModel):
    source_id: str
    page: Optional[int] = None
    section: Optional[str] = None
    heading: Optional[str] = None
    text: str
    plain_language: Optional[str] = None
    is_cited: bool = False


class SourceDocument(BaseModel):
    source_type: str
    source_id: str
    representation: str = "structured_source_text"
    pdf_available: bool = False
    scope: Optional[str] = None
    policy_id: Optional[str] = None
    policy_number: Optional[str] = None
    form_number: Optional[str] = None
    form_title: Optional[str] = None
    form_kind: Optional[str] = None
    edition: Optional[str] = None
    page: Optional[int] = None
    page_count: Optional[int] = None
    section: Optional[str] = None
    heading: Optional[str] = None
    text: str = ""
    plain_language: Optional[str] = None
    record_fields: dict[str, str] = {}
    passages: list[SourcePassage] = []


def _form_for(db: Session, form_number: Optional[str], edition: Optional[str], policy_id: Optional[str]) -> Optional[CoreForm]:
    if not form_number:
        return None
    query = db.query(CoreForm).filter(CoreForm.form_number == form_number)
    if edition:
        query = query.filter(CoreForm.edition == edition)
    if policy_id:
        attached = query.filter(CoreForm.policy_id == policy_id).first()
        if attached:
            return attached
    return query.first()


def _policy_number(db: Session, policy_id: Optional[str]) -> Optional[str]:
    if not policy_id:
        return None
    policy = db.query(CorePolicy).filter(CorePolicy.id == policy_id).first()
    return policy.policy_number if policy else None


def _passage(clause: Clause, cited_id: Optional[str]) -> SourcePassage:
    return SourcePassage(
        source_id=clause.id,
        page=clause.page,
        section=clause.section,
        heading=clause.heading,
        text=clause.text,
        plain_language=clause.plain_language or None,
        is_cited=clause.id == cited_id,
    )


def _money(value: Optional[float]) -> str:
    return f"${value:,.2f}" if value is not None else "—"


@router.get("/{source_type}/{source_id}", response_model=SourceDocument)
def get_source(source_type: str, source_id: str, db: Session = Depends(get_db)):
    """Return the stored source behind a citation, with its surrounding form passages."""
    if source_type == "clause":
        clause = db.query(Clause).filter(Clause.id == source_id).first()
        if not clause:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clause not found")
        form = _form_for(db, clause.form_number, clause.edition, clause.policy_id)
        same_page = db.query(Clause).filter(
            Clause.form_number == clause.form_number,
            Clause.edition == clause.edition,
            Clause.page == clause.page,
        )
        if clause.policy_id:
            same_page = same_page.filter(Clause.policy_id == clause.policy_id)
        else:
            same_page = same_page.filter(
                Clause.policy_id.is_(None), Clause.line_of_business == clause.line_of_business
            )
        passages, seen = [], set()
        for row in same_page.order_by(Clause.created_at.asc()).all():
            key = (row.section, row.heading)
            if key in seen and row.id != clause.id:
                continue  # product wording is stored once per seeded policy
            seen.add(key)
            passages.append(_passage(row, clause.id))
        if not any(p.is_cited for p in passages):
            passages.append(_passage(clause, clause.id))
        return SourceDocument(
            source_type="clause",
            source_id=clause.id,
            scope=clause.scope,
            policy_id=clause.policy_id,
            policy_number=_policy_number(db, clause.policy_id),
            form_number=clause.form_number,
            form_title=form.title if form else None,
            form_kind=form.kind if form else None,
            edition=clause.edition,
            page=clause.page,
            page_count=form.page_count if form else None,
            section=clause.section,
            heading=clause.heading,
            text=clause.text,
            plain_language=clause.plain_language or None,
            passages=passages,
        )

    if source_type == "coverage":
        coverage = db.query(CoreCoverage).filter(CoreCoverage.id == source_id).first()
        if not coverage:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Coverage not found")
        form = _form_for(db, coverage.governing_form or None, None, coverage.policy_id)
        governing = []
        if coverage.governing_form and coverage.pattern_code:
            governing = (
                db.query(Clause)
                .filter(
                    Clause.policy_id == coverage.policy_id,
                    Clause.form_number == coverage.governing_form,
                    Clause.pattern_code == coverage.pattern_code,
                )
                .order_by(Clause.page.asc(), Clause.created_at.asc())
                .all()
            )
        return SourceDocument(
            source_type="coverage",
            source_id=coverage.id,
            scope="policy_record",
            policy_id=coverage.policy_id,
            policy_number=_policy_number(db, coverage.policy_id),
            form_number=coverage.governing_form or None,
            form_title=form.title if form else None,
            form_kind=form.kind if form else None,
            edition=form.edition if form else None,
            page_count=form.page_count if form else None,
            heading=coverage.name,
            text=f"Declarations schedule entry for {coverage.name}.",
            record_fields={
                "Coverage": coverage.name,
                "Limit": coverage.limit_text or _money(coverage.limit_amount),
                "Deductible": coverage.deductible_text or _money(coverage.deductible_amount),
                "Governing form": coverage.governing_form or "—",
                "Included": "Yes" if coverage.included else "No",
            },
            passages=[_passage(c, None) for c in governing],
        )

    if source_type == "form":
        form = db.query(CoreForm).filter(CoreForm.id == source_id).first()
        if not form:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found")
        clauses = (
            db.query(Clause)
            .filter(
                Clause.policy_id == form.policy_id,
                Clause.form_number == form.form_number,
                Clause.edition == form.edition,
            )
            .order_by(Clause.page.asc(), Clause.created_at.asc())
            .all()
        )
        return SourceDocument(
            source_type="form",
            source_id=form.id,
            scope="policy_record",
            policy_id=form.policy_id,
            policy_number=_policy_number(db, form.policy_id),
            form_number=form.form_number,
            form_title=form.title,
            form_kind=form.kind,
            edition=form.edition,
            page=1,
            page_count=form.page_count,
            heading=form.title,
            text=f"{form.title} ({form.kind}) is attached to this policy.",
            record_fields={
                "Kind": form.kind,
                "State": form.state or "Standard",
                "Pages": str(form.page_count),
            },
            passages=[_passage(c, None) for c in clauses],
        )

    if source_type == "claim":
        claim = db.query(CoreClaim).filter(CoreClaim.id == source_id).first()
        if not claim:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found")
        return SourceDocument(
            source_type="claim",
            source_id=claim.id,
            scope="policy_record",
            policy_id=claim.policy_id,
            policy_number=_policy_number(db, claim.policy_id),
            heading=f"Claim {claim.claim_number}",
            text=claim.description or "",
            record_fields={
                "Claim number": claim.claim_number,
                "Status": claim.status,
                "Loss cause": claim.loss_cause or "—",
                "Loss date": str(claim.loss_date or "—"),
                "Adjuster": claim.adjuster or "—",
            },
        )

    if source_type == "billing":
        bill = db.query(CoreBilling).filter(CoreBilling.id == source_id).first()
        if not bill:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Billing record not found")
        return SourceDocument(
            source_type="billing",
            source_id=bill.id,
            scope="policy_record",
            policy_id=bill.policy_id,
            policy_number=_policy_number(db, bill.policy_id),
            heading="Billing record",
            text="",
            record_fields={
                "Plan": bill.plan,
                "Status": bill.status,
                "Next due": str(bill.next_due_date or "—"),
                "Next amount": _money(bill.next_due_amount),
                "Past due": _money(bill.past_due_amount),
            },
        )

    if source_type == "policy":
        policy = db.query(CorePolicy).filter(CorePolicy.id == source_id).first()
        if not policy:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found")
        return SourceDocument(
            source_type="policy",
            source_id=policy.id,
            scope="policy_record",
            policy_id=policy.id,
            policy_number=policy.policy_number,
            heading=f"Policy {policy.policy_number}",
            text="Policy record from the policy administration system.",
            record_fields={
                "Policyholder": policy.account.name if policy.account else "—",
                "Product": policy.product_name or policy.line_of_business,
                "Status": policy.status.replace("_", " "),
                "State": policy.state or "—",
                "Term": f"{policy.term_number} · {policy.effective_date} to {policy.expiration_date}",
            },
        )

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported source type '{source_type}'")


class PlainLanguageExplanation(BaseModel):
    """An AI explanation of one clause's wording. Never approved wording and never a coverage decision."""

    source_id: str
    status: str  # explained | unavailable
    explanation: str = ""
    model_used: Optional[str] = None
    provider: Optional[str] = None
    reason: Optional[str] = None
    # The carrier's approved explanation, when one exists, so the two are never confused.
    approved_plain_language: Optional[str] = None


# Explanations are kept per clause wording, so the same clause is not sent to the model again.
_EXPLAINED: dict[tuple[str, str], PlainLanguageExplanation] = {}


@router.post("/clause/{clause_id}/plain-language", response_model=PlainLanguageExplanation)
def explain_clause_plainly(
    clause_id: str,
    employee: EmployeeUser = Depends(get_current_employee),
    db: Session = Depends(get_db),
):
    """Explain a cited clause in plain words with the language model, from the clause's own text."""
    if (employee.role or "").strip().lower() in UNAUTHORIZED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee is not authorized to view policy wording")
    clause = db.query(Clause).filter(Clause.id == clause_id).first()
    if clause is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clause not found")

    key = (clause.id, hashlib.sha1((clause.text or "").encode("utf-8")).hexdigest())
    cached = _EXPLAINED.get(key)
    if cached is not None:
        return cached
    result = ai_client.plain_language(clause.heading or "", clause.form_number or "", clause.text or "")
    explanation = PlainLanguageExplanation(
        source_id=clause.id,
        status=result.get("status") or "unavailable",
        explanation=result.get("explanation") or "",
        model_used=result.get("model_used"),
        provider=result.get("provider"),
        reason=result.get("reason"),
        approved_plain_language=clause.plain_language or None,
    )
    logger.info("Plain-language explanation for clause %s requested by %s: %s", clause.id, employee.id, explanation.status)
    if explanation.status == "explained":
        _EXPLAINED[key] = explanation  # an unavailable result is not kept, so a retry can succeed
    return explanation
