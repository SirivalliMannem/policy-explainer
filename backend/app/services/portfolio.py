"""Customer and portfolio questions, answered from policy records.

"How many policies does Margaret Chen have?" and "What policies do we have?" are not about the
wording of any one policy, so the grounded explainer (which searches a single policy's forms) can
never answer them. Their answers are facts in the policy system itself. This module recognises
those questions and answers them deterministically from core_policy / core_account rows — no
language model is involved, and every listed policy is a real record.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session

from app.models.policy import CoreAccount, CorePolicy
from app.services.policy_resolver import current_terms, find_accounts, line_hint, name_words

# A plural subject the question counts or lists ...
SUBJECT = r"(?:policies|policy|policyholders?|customers?|insureds?|accounts?|households?)"
# ... asked as a count or a listing.
PORTFOLIO_PATTERNS = [
    re.compile(rf"\bhow many\b.*\b{SUBJECT}\b", re.IGNORECASE),
    re.compile(r"\b(?:what|which|list|show|give|display|name)\b.*\b(?:policies|policyholders|customers|insureds|accounts)\b", re.IGNORECASE),
    re.compile(r"\b(?:any|other|all)\s+(?:other\s+)?(?:policies|policyholders|customers)\b", re.IGNORECASE),
]
# Questions about what a policy *says* stay with the grounded explainer even if they say "policies".
CONTENT_TERMS = re.compile(
    r"\b(?:cover|covers|covered|coverage|deductibles?|limits?|exclu\w*|endorsements?|forms?|claims?|"
    r"bill\w*|premium|pay\w*|wording|clause\w*|peril\w*|damage)\b",
    re.IGNORECASE,
)
HOUSEHOLD_TERMS = re.compile(r"\b(?:household|family|spouse|husband|wife|partner)\b", re.IGNORECASE)
EXPIRED_TERMS = re.compile(r"\b(?:expired|lapsed|cancell?ed|previous|prior|old)\b", re.IGNORECASE)

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
    "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
    "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}
LINE_LABEL = {"homeowners": "Homeowners", "personal_auto": "Personal Auto"}


def is_portfolio_question(question: str) -> bool:
    """True for questions that count or list policies/customers rather than ask what a policy says."""
    text = (question or "").strip()
    if not text or CONTENT_TERMS.search(text):
        return False
    return any(p.search(text) for p in PORTFOLIO_PATTERNS)


@dataclass
class PortfolioResult:
    answer: str
    scope: str  # customer | household | book
    customers: list[CoreAccount]
    policies: list[CorePolicy]  # one row per policy number (current term)
    prior_terms: dict[str, int]  # policy_number -> number of other (earlier) terms on file
    filters: dict[str, str] = field(default_factory=dict)


def _state_filter(text: str, states_on_file: set[str]) -> Optional[str]:
    lowered = text.lower()
    for name, code in US_STATES.items():
        if re.search(rf"\b{name}\b", lowered) and code in states_on_file:
            return code
    for code in states_on_file:
        # Two-letter codes only when written in capitals ("TX"), so "in" / "or" never match.
        if re.search(rf"\b{code}\b", text):
            return code
    return None


def _plural(n: int, word: str, plural: Optional[str] = None) -> str:
    return f"{n} {word if n == 1 else (plural or word + 's')}"


def _join(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def _describe(policy: CorePolicy) -> str:
    status = "in force" if policy.status == "in_force" else policy.status.replace("_", " ")
    return f"{policy.policy_number} ({LINE_LABEL.get(policy.line_of_business, policy.line_of_business)}, {status})"


def portfolio_payload(result: PortfolioResult) -> dict:
    """Serialisable view of a result, as returned to the browser and stored in the ledger."""
    return {
        "scope": result.scope,
        "customers": sorted({a.name for a in result.customers}),
        "filters": result.filters,
        "policies": [
            {
                "policy_id": p.id,
                "policy_number": p.policy_number,
                "customer_id": p.account_id,
                "customer_name": p.account.name if p.account else "",
                "line_of_business": p.line_of_business,
                "product_name": p.product_name,
                "status": p.status,
                "state": p.state,
                "term_number": p.term_number,
                "effective_date": p.effective_date.isoformat(),
                "expiration_date": p.expiration_date.isoformat(),
                "earlier_terms": result.prior_terms.get(p.policy_number, 0),
            }
            for p in result.policies
        ],
    }


def portfolio_evidence(result: PortfolioResult) -> tuple[list[dict], list[dict]]:
    """The policy records behind the answer, as evidence and citations for the ledger."""
    evidence, citations = [], []
    for index, p in enumerate(result.policies, start=1):
        line = LINE_LABEL.get(p.line_of_business, p.line_of_business)
        evidence.append({
            "source_type": "policy",
            "source_id": p.id,
            "title": f"Policy {p.policy_number}",
            "content": (
                f"{p.account.name if p.account else ''} · {line} · {p.status.replace('_', ' ')} · {p.state} · "
                f"term {p.term_number}, {p.effective_date.isoformat()} to {p.expiration_date.isoformat()}"
            ),
            "heading": p.policy_number,
            "relevance_score": 1.0,
            "evidence_index": index,
            "scope": "policy_record",
        })
        citations.append({
            "source_id": p.id,
            "source_type": "policy",
            "evidence_index": index,
            "heading": p.policy_number,
            "citation_text": f"Policy record {p.policy_number}",
        })
    return evidence, citations


def portfolio_suggestions(result: PortfolioResult) -> list[str]:
    """Follow-ups about the policies just listed."""
    if result.scope == "not_found":
        return ["What policies do we have?"]
    return [f"What does {p.policy_number} cover?" for p in result.policies[:3]]


def answer_portfolio_question(question: str, db: Session) -> PortfolioResult:
    """Answer a customer or portfolio question from policy records."""
    text = question.strip()
    accounts, _ = find_accounts(text, db)
    scope = "customer" if accounts else "book"

    # A name was given but matches nobody: say so rather than answering for the whole book.
    unmatched = name_words(text) if not accounts else []
    if unmatched:
        return PortfolioResult(
            answer=f"No policyholder named {' '.join(unmatched)} is on file. Check the spelling or use a policy number.",
            scope="not_found",
            customers=[],
            policies=[],
            prior_terms={},
        )

    # Household members are included only when asked for: listing a spouse's policies
    # unprompted would disclose a contract the caller may not be party to.
    if accounts and HOUSEHOLD_TERMS.search(text):
        household_ids = {a.household_id for a in accounts if a.household_id}
        if household_ids:
            members = db.query(CoreAccount).filter(CoreAccount.household_id.in_(household_ids)).all()
            accounts = list({a.id: a for a in [*accounts, *members]}.values())
            scope = "household"

    query = db.query(CorePolicy)
    if accounts:
        query = query.filter(CorePolicy.account_id.in_([a.id for a in accounts]))
    all_rows = query.all()
    terms_per_number = Counter(p.policy_number for p in all_rows)

    wants_expired = bool(EXPIRED_TERMS.search(text))
    if wants_expired:
        # Every term that is no longer in force, including earlier terms of renewed policies.
        policies = [p for p in all_rows if p.status != "in_force"]
        kind = "expired"
    else:
        policies = current_terms(all_rows)
        in_force = [p for p in policies if p.status == "in_force"]
        policies = in_force or policies
        kind = "current"

    filters: dict[str, str] = {}
    line = line_hint(text)
    if line:
        policies = [p for p in policies if p.line_of_business == line]
        filters["line_of_business"] = line
    state = _state_filter(text, {p.state for p in all_rows if p.state})
    if state:
        policies = [p for p in policies if p.state == state]
        filters["state"] = state

    policies.sort(key=lambda p: ((p.account.name if p.account else ""), p.line_of_business, p.policy_number, p.term_number))
    prior_terms = (
        {}
        if wants_expired
        else {p.policy_number: terms_per_number[p.policy_number] - 1 for p in policies if terms_per_number[p.policy_number] > 1}
    )

    # "2 current Personal Auto policies in TX"
    line_word = LINE_LABEL.get(filters.get("line_of_business", ""), "")
    def phrase(n: int) -> str:
        noun = "policy" if n == 1 else "policies"
        words = [str(n), kind] + ([line_word] if line_word else []) + [noun]
        return " ".join(words) + (f" in {filters['state']}" if "state" in filters else "")

    if scope in ("customer", "household"):
        names = _join(sorted({a.name for a in accounts}))
        subject = f"The household of {names}" if scope == "household" else names
        plural_subject = scope == "customer" and len(accounts) > 1
        if not policies:
            answer = f"{subject} {'have' if plural_subject else 'has'} no {phrase(0)[2:]} on file."
        else:
            answer = f"{subject} {'have' if plural_subject else 'has'} {phrase(len(policies))}: {_join([_describe(p) for p in policies])}."
    else:
        holders = sorted({p.account.name for p in policies if p.account})
        if not policies:
            answer = f"There are no {phrase(0)[2:]} on file."
        else:
            by_line = Counter(LINE_LABEL.get(p.line_of_business, p.line_of_business) for p in policies)
            mix = _join([f"{n} {label}" for label, n in sorted(by_line.items())])
            answer = (
                f"There {'is' if len(policies) == 1 else 'are'} {phrase(len(policies))} "
                f"across {_plural(len(holders), 'policyholder')}"
                + (f" ({mix})" if len(by_line) > 1 else "")
                + f": {_join(holders)}."
            )

    if prior_terms:
        notes = [f"{number} also has {_plural(n, 'earlier term')} on file" for number, n in prior_terms.items()]
        answer += " " + "; ".join(notes) + "."

    return PortfolioResult(
        answer=answer,
        scope=scope,
        customers=accounts,
        policies=policies,
        prior_terms=prior_terms,
        filters=filters,
    )
