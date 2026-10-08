"""Resolve which policy a free-text question is about.

An employee may name a policy number ("HO-2847-1193"), a policyholder ("Margaret Chen"), only a
surname ("Chen"), or nothing at all ("What is the deductible?"). Resolution is deterministic and
database-backed, and it never guesses: when more than one policy fits, the candidates are
returned so the employee can choose.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func, literal
from sqlalchemy.orm import Session

from app.models.policy import CoreAccount, CorePolicy

POLICY_NUMBER_PATTERN = re.compile(r"\b(HO|PA)[-\s]?(\d{4})(?:[-\s](\d{4}))?\b", re.IGNORECASE)
CAPITALISED_WORD = re.compile(r"\b([A-Z][a-zA-Z\-]{2,})(?:'s|’s)?\b")

# Capitalised words that start sentences or name products, never surnames.
NON_NAME_WORDS = {
    "does", "do", "did", "what", "which", "who", "whose", "when", "where", "why", "how", "is", "are",
    "can", "could", "would", "will", "should", "the", "this", "that", "these", "those", "and", "for",
    "with", "under", "policy", "coverage", "coverages", "endorsement", "form", "forms", "deductible",
    "water", "backup", "homeowners", "auto", "personal", "special", "texas", "new", "york", "coverage",
    "section", "part", "show", "tell", "explain", "list", "please", "has", "have", "any", "all",
    "give", "display", "name", "there", "we", "our", "us", "me", "my", "is", "are", "was", "were",
    "home", "homeowner", "customers", "customer", "policyholders", "policyholder", "insureds", "insured",
    "accounts", "account", "households", "household", "policies", "in", "on", "of", "currently", "active",
}

# Words of US state names, so "Texas" or "York" are never read as a surname.
STATE_WORDS = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut", "delaware",
    "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
    "louisiana", "maine", "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
    "montana", "nebraska", "nevada", "hampshire", "jersey", "mexico", "carolina", "dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode", "island", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west", "wisconsin", "wyoming", "north", "south",
}

HOME_HINTS = (
    "home", "house", "dwelling", "roof", "water", "backup", "back-up", "sewer", "sump", "flood",
    "basement", "hail", "wind", "windstorm", "jewelry", "jewellery", "personal property", "homeowner",
    "homeowners", "loss of use", "hotel",
    "other structures", "ho-3", "ho 00 03",
)
AUTO_HINTS = (
    "auto", "car", "cars", "vehicle", "vehicles", "collision", "comprehensive", "driver", "driving", "rental", "uber",
    "rideshare", "windshield", "windscreen", "uninsured", "motorist", "bodily injury", "crash",
)


@dataclass
class ResolutionResult:
    status: str  # resolved | ambiguous | not_found | no_reference
    matched_on: Optional[str] = None  # policy_number | customer_name | surname
    reference: Optional[str] = None
    policy: Optional[CorePolicy] = None
    candidates: list[CorePolicy] = field(default_factory=list)
    message: str = ""


def _mentions(text: str, hint: str) -> bool:
    # Whole words only: "household" must not read as "home", nor "carrier" as "car".
    return re.search(rf"(?<![a-z0-9]){re.escape(hint)}(?![a-z0-9])", text) is not None


def line_hint(question: str) -> Optional[str]:
    text = question.lower()
    home = any(_mentions(text, h) for h in HOME_HINTS)
    auto = any(_mentions(text, h) for h in AUTO_HINTS)
    if home and not auto:
        return "homeowners"
    if auto and not home:
        return "personal_auto"
    return None


def current_terms(policies: list[CorePolicy]) -> list[CorePolicy]:
    """One row per policy number: the in-force term if there is one, else the latest term."""
    by_number: dict[str, CorePolicy] = {}
    for policy in policies:
        best = by_number.get(policy.policy_number)
        rank = (policy.status == "in_force", policy.effective_date)
        if best is None or rank > (best.status == "in_force", best.effective_date):
            by_number[policy.policy_number] = policy
    return sorted(by_number.values(), key=lambda p: (p.status != "in_force", p.policy_number))


def _choose(policies: list[CorePolicy], question: str) -> list[CorePolicy]:
    """Narrow a customer's policies using status and any line-of-business hint in the question."""
    current = current_terms(policies)
    in_force = [p for p in current if p.status == "in_force"]
    if in_force:
        current = in_force
    hint = line_hint(question)
    if hint:
        hinted = [p for p in current if p.line_of_business == hint]
        if hinted:
            current = hinted
    return current


def find_accounts(text: str, db: Session) -> tuple[list[CoreAccount], Optional[str]]:
    """Policyholders named in the text: full names first, then a capitalised surname alone."""
    accounts = (
        db.query(CoreAccount)
        .filter(func.lower(literal(text)).contains(func.lower(CoreAccount.name)))
        .all()
    )
    if accounts:
        return accounts, "customer_name"

    words = name_words(text)
    for surname in words:
        accounts.extend(db.query(CoreAccount).filter(CoreAccount.name.ilike(f"% {surname}")).all())
    if accounts:
        return accounts, "surname"

    for first in words:
        accounts.extend(db.query(CoreAccount).filter(CoreAccount.name.ilike(f"{first} %")).all())
    return accounts, ("first_name" if accounts else None)


def name_words(text: str) -> list[str]:
    """Capitalised words that could be part of a person's name."""
    found = []
    for word in CAPITALISED_WORD.findall(text):
        lowered = word.lower()
        if lowered in NON_NAME_WORDS or lowered in STATE_WORDS or word in found:
            continue
        found.append(word)
    return found


def resolve_policy_from_question(question: str, db: Session) -> ResolutionResult:
    """Resolve the policy a question refers to, if it refers to one."""
    text = (question or "").strip()
    if not text:
        return ResolutionResult(status="no_reference", message="The question is empty.")

    # 1. Policy number, full ("HO-2847-1193") or prefix ("HO-2847").
    number_match = POLICY_NUMBER_PATTERN.search(text)
    if number_match:
        prefix, first, second = number_match.group(1).upper(), number_match.group(2), number_match.group(3)
        reference = number_match.group(0)
        query = db.query(CorePolicy)
        if second:
            policies = query.filter(CorePolicy.policy_number == f"{prefix}-{first}-{second}").all()
        else:
            policies = query.filter(CorePolicy.policy_number.like(f"{prefix}-{first}-%")).all()
        terms = current_terms(policies)
        if not terms:
            return ResolutionResult(
                status="not_found", matched_on="policy_number", reference=reference,
                message=f"No policy matches {reference}.",
            )
        if len(terms) > 1:
            return ResolutionResult(
                status="ambiguous", matched_on="policy_number", reference=reference, candidates=terms,
                message=f"{reference} matches more than one policy.",
            )
        return ResolutionResult(status="resolved", matched_on="policy_number", reference=reference, policy=terms[0])

    # 2-3. Policyholder named by full name or surname.
    accounts, matched_on = find_accounts(text, db)
    if not accounts:
        return ResolutionResult(status="no_reference", message="The question does not name a policy or policyholder.")

    reference = ", ".join(sorted({a.name for a in accounts}))
    policies = (
        db.query(CorePolicy)
        .filter(CorePolicy.account_id.in_([a.id for a in accounts]))
        .all()
    )
    choices = _choose(policies, text)
    if not choices:
        return ResolutionResult(
            status="not_found", matched_on=matched_on, reference=reference,
            message=f"No policies are on file for {reference}.",
        )
    if len(choices) > 1:
        return ResolutionResult(
            status="ambiguous", matched_on=matched_on, reference=reference, candidates=choices,
            message=f"{reference} has more than one policy that could apply.",
        )
    return ResolutionResult(status="resolved", matched_on=matched_on, reference=reference, policy=choices[0])
