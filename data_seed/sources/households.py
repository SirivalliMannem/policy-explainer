"""Households, added to a book that already exists.

The seed pack replaces what it owns: re-running it deletes the tenant's
accounts and policies and writes them again. That is right for a fresh
tenant and wrong for a running one — a demo book with two hundred
generated claims on it loses them, and "add a spouse" is not worth
that.

So the household shapes live here, written to be **idempotent and
additive**: run it on a book that already has them and nothing
changes; run it on one that does not and it adds only what is missing.
`pack.seed` calls it too, so there is one implementation rather than
two that drift.

Three shapes, because they behave differently:

  the Chens   two names, one address, three policies — the case where
              "your policies" and "your household's policies" are
              different answers, and telling somebody the wrong one
              exposes their spouse's contract;
  Moreau      one name, two products — the ordinary multi-line
              customer, and the one retention cares about most;
  Ortiz       one name, a home he lives in and a rental he does not.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, timedelta

from sqlalchemy.orm import Session

from data_seed.models.models import (
    CoreAccount,
    CoreBilling,
    CoreCoverage,
    CoreForm,
    CorePolicy,
)
from data_seed.sources import forms_auto, forms_es, forms_home

logger = logging.getLogger(__name__)


def _uuid() -> str:
    return str(uuid.uuid4())


def _account(db: Session, org_id: str, number: str) -> CoreAccount | None:
    return (
        db.query(CoreAccount)
        .filter(CoreAccount.org_id == org_id, CoreAccount.account_number == number)
        .one_or_none()
    )


def _policy_exists(db: Session, org_id: str, number: str) -> bool:
    return (
        db.query(CorePolicy)
        .filter(CorePolicy.org_id == org_id, CorePolicy.policy_number == number)
        .first()
        is not None
    )


def top_up(db: Session, org_id: str, *, today: date | None = None) -> dict:
    """Add the household shapes to this tenant's book, if they are missing.

    Returns what it actually did, so a caller can tell "already there"
    from "nothing matched" — the second means the book was not seeded
    from the standard pack and a silent no-op would be misleading.
    """
    today = today or date.today()
    current_start = (
        date(today.year, 3, 1) if today >= date(today.year, 3, 1)
        else date(today.year - 1, 3, 1)
    )

    added = {"accounts": 0, "policies": 0, "coverages": 0, "forms": 0, "billing": 0}
    missing: list[str] = []

    def coverage(policy: CorePolicy, order: int, pattern: str, name: str,
                 limit: str = "", limit_amount: float | None = None,
                 deductible: str = "", deductible_amount: float | None = None,
                 form: str = "") -> None:
        db.add(CoreCoverage(
            org_id=org_id, policy_id=policy.id, sort_order=order,
            pattern_code=pattern, name=name, limit_text=limit,
            limit_amount=limit_amount, deductible_text=deductible,
            deductible_amount=deductible_amount, governing_form=form,
        ))
        added["coverages"] += 1

    def attach(policy: CorePolicy, spec: tuple, *, state: str = "") -> None:
        number, edition, title, kind, pages = spec
        db.add(CoreForm(
            org_id=org_id, policy_id=policy.id, form_number=number, edition=edition,
            title=title, kind=kind, line_of_business=policy.line_of_business,
            state=state, page_count=pages, effective_from=policy.effective_date,
        ))
        added["forms"] += 1

    def clauses_for(policy: CorePolicy, module, only: set) -> None:
        from data_seed.models.models import Clause

        for spec, page, section, heading, clause_type, pattern, keywords, text, plain in module.CLAUSES:
            is_product_guide = section == "Product guide"
            if not is_product_guide and spec not in only:
                continue
            # A state amendatory clause belongs only to a policy in that
            # state — the same rule the pack applies, because a Texas
            # page on a Massachusetts policy is a wrong citation.
            clause_state = spec[2].split("–")[-1].strip() if spec[3] == "amendatory" else ""
            clause_state = {"Texas": "TX", "New York": "NY"}.get(clause_state, "")
            if clause_state and clause_state != policy.state:
                continue
            db.add(Clause(
                org_id=org_id,
                form_number=spec[0], edition=spec[1], page=page, section=section,
                heading=heading, text=text, plain_language=plain,
                plain_language_es=forms_es.for_clause(spec[0], heading),
                line_of_business=policy.line_of_business,
                state=clause_state,
                scope="product_wording" if is_product_guide else "customer_form",
                policy_id=None if is_product_guide else policy.id,
                clause_type=clause_type, keywords=list(keywords), pattern_code=pattern,
                effective_from=policy.effective_date,
                effective_to=policy.expiration_date,
            ))

    def billing(policy: CorePolicy, account: CoreAccount, *, status: str = "current",
                amount: float = 0.0, past_due: float = 0.0) -> None:
        db.add(CoreBilling(
            org_id=org_id, policy_id=policy.id, account_number=account.account_number,
            plan="Monthly", status=status,
            next_due_date=today + timedelta(days=12), next_due_amount=amount,
            past_due_amount=past_due,
        ))
        added["billing"] += 1

    def policy(**kwargs) -> CorePolicy:
        row = CorePolicy(org_id=org_id, **kwargs)
        db.add(row)
        db.flush()
        added["policies"] += 1
        return row

    # ── The Chens: two names, one address ──────────────────────────────
    chen = _account(db, org_id, "ACCT-100241")
    if chen is None:
        missing.append("ACCT-100241 (Margaret Chen)")
    else:
        david = _account(db, org_id, "ACCT-100242")
        if david is None:
            david = CoreAccount(
                org_id=org_id, account_number="ACCT-100242", name="David Chen",
                email="david.chen@example.com", phone="(512) 555-0143",
                address_line="1408 Wilshire Bend", city="Austin", state="TX",
                postal_code="78733", date_of_birth=date(1972, 11, 3),
            )
            db.add(david)
            db.flush()
            added["accounts"] += 1

        household_id = chen.household_id or david.household_id or _uuid()
        chen.household_id = household_id
        chen.household_role = chen.household_role or "Named insured"
        david.household_id = household_id
        david.household_role = david.household_role or "Spouse"

        if not _policy_exists(db, org_id, "PA-6120-7741"):
            row = policy(
                account_id=david.id, policy_number="PA-6120-7741", term_number=5,
                line_of_business="personal_auto", product_name="Personal Auto Policy",
                state="TX", status="in_force",
                effective_date=current_start - timedelta(days=95),
                expiration_date=current_start + timedelta(days=270),
                insured_location="1408 Wilshire Bend, Austin TX 78733",
                vehicles=[{"year": 2021, "make": "Ford", "model": "F-150",
                           "vin": "1FTFW1E85MFA31220", "plate": "TX-DWC7714"}],
                annual_premium=1612.0,
            )
            coverage(row, 1, "PALiabilityCov", "Part A – Bodily Injury Liability", "$250,000 / $500,000", 250000, "None", 0, "PP 00 01")
            coverage(row, 2, "PALiabilityCov", "Part A – Property Damage Liability", "$100,000", 100000, "None", 0, "PP 00 01")
            coverage(row, 3, "PACollisionCov", "Part D – Collision", "Actual cash value", None, "$500", 500, "PP 00 01")
            coverage(row, 4, "PAComprehensiveCov", "Part D – Other Than Collision", "Actual cash value", None, "$250", 250, "PP 00 01")
            for spec in (forms_auto.PP1, forms_auto.TX_AMEND):
                attach(row, spec, state="TX" if spec is forms_auto.TX_AMEND else "")
            clauses_for(row, forms_auto, {forms_auto.PP1, forms_auto.TX_AMEND})
            billing(row, david, amount=134.33)

        if not _policy_exists(db, org_id, "PA-6120-7742"):
            row = policy(
                account_id=chen.id, policy_number="PA-6120-7742", term_number=5,
                line_of_business="personal_auto", product_name="Personal Auto Policy",
                state="TX", status="in_force",
                effective_date=current_start - timedelta(days=95),
                expiration_date=current_start + timedelta(days=270),
                insured_location="1408 Wilshire Bend, Austin TX 78733",
                vehicles=[{"year": 2023, "make": "Lexus", "model": "RX 350",
                           "vin": "2T2BAMCA1PC012947", "plate": "TX-MGC1182"}],
                annual_premium=1489.0,
            )
            coverage(row, 1, "PALiabilityCov", "Part A – Bodily Injury Liability", "$250,000 / $500,000", 250000, "None", 0, "PP 00 01")
            coverage(row, 2, "PALiabilityCov", "Part A – Property Damage Liability", "$100,000", 100000, "None", 0, "PP 00 01")
            coverage(row, 3, "PAUninsuredMotoristsCov", "Part C – Uninsured Motorists", "$250,000 / $500,000", 250000, "", None, "PP 00 01")
            coverage(row, 4, "PACollisionCov", "Part D – Collision", "Actual cash value", None, "$500", 500, "PP 00 01")
            coverage(row, 5, "PAComprehensiveCov", "Part D – Other Than Collision", "Actual cash value", None, "$250", 250, "PP 00 01")
            for spec in (forms_auto.PP1, forms_auto.TX_AMEND):
                attach(row, spec, state="TX" if spec is forms_auto.TX_AMEND else "")
            clauses_for(row, forms_auto, {forms_auto.PP1, forms_auto.TX_AMEND})
            billing(row, chen, amount=124.08)

    # ── Moreau: home and auto on one name ──────────────────────────────
    moreau = _account(db, org_id, "ACCT-100455")
    if moreau is None:
        moreau = (
            db.query(CoreAccount)
            .filter(CoreAccount.org_id == org_id, CoreAccount.name == "Elena Moreau")
            .one_or_none()
        )
    if moreau is None:
        missing.append("Elena Moreau")
    elif not _policy_exists(db, org_id, "PA-8830-2215"):
        home = (
            db.query(CorePolicy)
            .filter(CorePolicy.org_id == org_id, CorePolicy.account_id == moreau.id)
            .first()
        )
        row = policy(
            account_id=moreau.id, policy_number="PA-8830-2215", term_number=2,
            line_of_business="personal_auto", product_name="Personal Auto Policy",
            state=(home.state if home else "MA"), status="in_force",
            effective_date=current_start - timedelta(days=40),
            expiration_date=current_start + timedelta(days=325),
            insured_location=(home.insured_location if home else ""),
            vehicles=[{"year": 2019, "make": "Volvo", "model": "XC60",
                       "vin": "YV4102RK8K1345518", "plate": "MA-4KLZ21"}],
            annual_premium=1358.0,
        )
        coverage(row, 1, "PALiabilityCov", "Part A – Bodily Injury Liability", "$100,000 / $300,000", 100000, "None", 0, "PP 00 01")
        coverage(row, 2, "PACollisionCov", "Part D – Collision", "Actual cash value", None, "$500", 500, "PP 00 01")
        coverage(row, 3, "PAComprehensiveCov", "Part D – Other Than Collision", "Actual cash value", None, "$250", 250, "PP 00 01")
        attach(row, forms_auto.PP1)
        clauses_for(row, forms_auto, {forms_auto.PP1})
        # Deliberately in arrears: "is everything paid up?" is only an
        # interesting question when the answer is sometimes no, and the
        # policy in arrears is not the one the customer calls about.
        billing(row, moreau, status="past_due", amount=113.17, past_due=226.34)

    # ── Ortiz: the home he lives in, and a rental he does not ──────────
    ortiz = _account(db, org_id, "ACCT-100512")
    if ortiz is None:
        missing.append("ACCT-100512 (Daniel Ortiz)")
    elif not _policy_exists(db, org_id, "HO-4417-6653"):
        row = policy(
            account_id=ortiz.id, policy_number="HO-4417-6653", term_number=2,
            line_of_business="homeowners", product_name="Homeowners – Special Form (HO-3)",
            state="TX", status="in_force", effective_date=current_start,
            expiration_date=current_start + timedelta(days=365),
            insured_location="2210 Kestrel Lane, Austin TX 78702",
            annual_premium=1980.0,
        )
        coverage(row, 1, "HODwellingCov", "Coverage A – Dwelling", "$320,000", 320000, "$2,000", 2000, "HO 00 03")
        coverage(row, 2, "HOPersonalPropertyCov", "Coverage C – Personal Property", "$160,000", 160000, "", None, "HO 00 03")
        coverage(row, 3, "HOLossOfUseCov", "Coverage D – Loss of Use", "$64,000", 64000, "", None, "HO 00 03")
        for spec in (forms_home.HO3, forms_home.TX_AMEND):
            attach(row, spec, state="TX" if spec is forms_home.TX_AMEND else "")
        clauses_for(row, forms_home, {forms_home.HO3, forms_home.TX_AMEND})
        billing(row, ortiz, amount=165.00)

    db.flush()
    return {
        "added": added,
        "missing": missing,
        "says": (
            f"Added {added['policies']} policies and {added['accounts']} accounts."
            if any(added.values())
            else "Already there — nothing to add."
        ),
    }
