"""Customer verification: the first step of answering a question.

Before any policy information is retrieved, the customer the question refers to must exist in the
customer records and be identified uniquely. The result is one of:

- verified   exactly one customer, by name, an identifier (email, phone, claim, account, VIN, ...),
             a policy number, or the customer already selected in the conversation
- ambiguous  more than one customer matches; the employee is asked which one
- not_found  a customer or identifier is named but is not in the records; the employee is asked
- not_named  the question names no customer and the conversation has none selected yet

The result is cached for the conversation and question so the answer, when it is given, records
how its customer was verified.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Optional

from sqlalchemy.orm import Session

from app.models.policy import CoreAccount, CorePolicy
from app.schemas.policy_resolution import CustomerVerification, VerifiedCustomer
from app.services.policy_resolver import NON_NAME_WORDS, STATE_WORDS, ResolutionResult, find_accounts

# Two capitalised words in a row ("John Smith") or a capitalised possessive ("Smith's").
_FULL_NAME = re.compile(r"\b([A-Z][a-z]{1,}\s+[A-Z][a-z]{1,})\b")
_POSSESSIVE = re.compile(r"\b([A-Z][a-zA-Z\-]{1,}(?:\s+[A-Z][a-zA-Z\-]{1,})?)(?:'s|’s)\b")

_TTL_SECONDS = 600
_cache: dict[tuple[str, str], tuple[float, dict]] = {}
_lock = threading.Lock()


def _key(conversation_id: str, question: str) -> tuple[str, str]:
    return conversation_id, " ".join(question.lower().split())


def remember(conversation_id: Optional[str], question: str, verification: CustomerVerification) -> None:
    if not conversation_id:
        return
    with _lock:
        if len(_cache) > 500:
            for stale in sorted(_cache, key=lambda k: _cache[k][0])[:100]:
                _cache.pop(stale, None)
        _cache[_key(conversation_id, question)] = (time.monotonic(), verification.model_dump())


def recall(conversation_id: str, question: str) -> Optional[dict]:
    # Not removed on read: one question may be answered for several of a customer's policies.
    with _lock:
        hit = _cache.get(_key(conversation_id, question))
    if hit and time.monotonic() - hit[0] < _TTL_SECONDS:
        return hit[1]
    return None


def _customer(account: CoreAccount) -> VerifiedCustomer:
    return VerifiedCustomer(customer_id=account.id, name=account.name, account_number=account.account_number or None)


_POLICY_NUMBER_OR_CLAIM = re.compile(r"\b(?:HO|PA|CLM)[-\s]?\d+", re.IGNORECASE)


# Words that are never a person's name in a question, beyond the resolver's non-name words: pronouns,
# articles and common question words ("does it have", "is the account past due").
_NOT_A_NAME = {
    "it", "its", "this", "that", "these", "those", "they", "them", "he", "she", "him", "her", "his", "hers",
    "i", "you", "your", "yours", "we", "our", "ours", "me", "my", "the", "a", "an", "any", "all", "some",
    "no", "not", "what", "which", "who", "whom", "how", "when", "where", "why", "if", "and", "or",
    "anyone", "someone", "everyone", "nobody", "somebody", "everybody", "past", "due", "now", "today",
    "coverage", "covered", "cover", "covers", "policy", "deductible", "endorsement", "endorsements",
    "form", "forms", "clause", "clauses", "wording", "mold", "water", "backup", "theft", "fire",
}

# A person is named in these phrases whatever the case ("policies of sirivalli", "does ravi have").
_NAME = r"([A-Za-z][A-Za-z'\-]+(?:\s+[A-Z][A-Za-z'\-]+)?)"
_PERSON_PHRASES = (
    re.compile(rf"\bpolic(?:y|ies)\s+(?:of|for|held\s+by|owned\s+by)\s+{_NAME}", re.IGNORECASE),
    re.compile(rf"\b(?:does|do|did|has)\s+{_NAME}\s+(?:have|has|hold|own|got)\b", re.IGNORECASE),
    re.compile(rf"\b(?:customer|policyholder|insured|client)\s+(?:named|called)\s+{_NAME}", re.IGNORECASE),
)
# After "for / of / about / regarding" only a capitalised name counts ("the deductible for Priya"):
# "the exclusion for mold" or "the account of the insured" name nobody.
_CAPITALISED_AFTER = re.compile(r"\b(?:for|of|about|regarding)\s+([A-Z][a-z][A-Za-z'\-]*(?:\s+[A-Z][a-z][A-Za-z'\-]*)?)")


def _as_name(candidate: str) -> Optional[str]:
    """The candidate as a name, with non-name words trimmed from its edges ("Is Priya" is "Priya"),
    or None when what is left is not a name."""
    blocked = NON_NAME_WORDS | STATE_WORDS | _NOT_A_NAME
    words = candidate.split()
    while words and words[0].lower() in blocked:
        words.pop(0)
    while words and words[-1].lower() in blocked:
        words.pop()
    name = " ".join(words)
    if not words or _POLICY_NUMBER_OR_CLAIM.search(name) or any(w.lower() in blocked for w in words):
        return None
    return name


def _named_people(question: str, interpretation: Optional[dict]) -> list[str]:
    """People the question names. Only what was typed counts: the interpreter's names (it keeps only
    names on file or typed in the question), capitalised full names and possessives, and names in a
    phrase that is about a person ("policies of X", "does X have", "customer named X"). Ordinary words
    ("past due", "mold") are never a customer, so a question about them is not a customer lookup."""
    names = [n for n in (interpretation or {}).get("policyholders") or [] if isinstance(n, str) and n.strip()]
    if (interpretation or {}).get("policyholder_name"):
        stated = interpretation["policyholder_name"].strip()
        if stated and stated not in names and stated.lower() in question.lower():
            names.append(stated)
    if names:
        return names

    text = question.strip().rstrip("?.!")
    found: list[str] = []
    for m in _POSSESSIVE.finditer(text):
        found.append(m.group(1).strip())
    for pattern in _PERSON_PHRASES:
        for m in pattern.finditer(text):
            found.append(m.group(1).strip())
    for m in _CAPITALISED_AFTER.finditer(text):
        found.append(m.group(1).strip())
    for m in _FULL_NAME.finditer(text):
        found.append(m.group(1).strip())
    found = [name for name in (_as_name(f) for f in found) if name]

    # A full name covers its own words ("Margaret Chen" is not also "Margaret").
    multi = [f for f in found if " " in f]
    found = [f for f in found if " " in f or not any(f in m.split() for m in multi)]
    return list(dict.fromkeys(found))


def verify_customer(
    result: ResolutionResult,
    question: str,
    interpretation: Optional[dict],
    active: Optional[CorePolicy],
    db: Session,
    customer: Optional[CoreAccount] = None,
) -> CustomerVerification:
    """Verify the customer a question refers to, from the policy resolution and the customer records.

    ``customer`` is the conversation's customer when it has no single selected policy.
    """
    current = active.account if active is not None and active.account is not None else customer
    if result.status == "resolved" and result.policy and result.policy.account:
        return CustomerVerification(
            status="verified",
            matched_on=result.matched_on,
            reference=result.reference,
            customers=[_customer(result.policy.account)],
            message=f"{result.policy.account.name} is in the customer records, matched on "
            f"{(result.matched_on or 'reference').replace('_', ' ')}.",
        )

    if result.status == "ambiguous":
        accounts = {p.account_id: p.account for p in result.candidates if p.account}
        if len(accounts) == 1:
            account = next(iter(accounts.values()))
            return CustomerVerification(
                status="verified",
                matched_on=result.matched_on,
                reference=result.reference,
                customers=[_customer(account)],
                message=f"{account.name} is in the customer records and has more than one matching policy.",
            )
        # The customer already selected in this conversation is one of them: keep with that customer.
        if current is not None and current.id in accounts:
            return CustomerVerification(
                status="verified",
                matched_on="conversation",
                reference=result.reference,
                customers=[_customer(accounts[current.id])],
                message=f"Several customers match; continuing with {accounts[current.id].name}, "
                "the customer already selected in this conversation.",
            )
        names = sorted(a.name for a in accounts.values())
        return CustomerVerification(
            status="ambiguous",
            matched_on=result.matched_on,
            reference=result.reference,
            customers=[_customer(a) for a in sorted(accounts.values(), key=lambda a: a.name)],
            message=f"{len(names)} customers in the records match: {', '.join(names[:-1])} and {names[-1]}.",
        )

    if result.status == "not_found":
        return CustomerVerification(
            status="not_found",
            matched_on=result.matched_on,
            reference=result.reference,
            message=result.message or f"No customer in the records matches {result.reference}.",
        )

    # Check whether any customer was named in the question
    people = _named_people(question, interpretation)
    known = []
    unknown = []
    for p in people:
        accs, _ = find_accounts(p, db)
        if accs:
            known.extend(accs)
        else:
            unknown.append(p)

    # A customer was explicitly named but not found in the customer records:
    # NEVER fall back to active conversation context; fail verification.
    if unknown:
        name = unknown[0]
        return CustomerVerification(
            status="not_found",
            matched_on="customer_name",
            reference=name,
            message=f"I couldn't find a matching customer for '{name}'. Please verify the customer name or provide a valid policy number.",
        )

    if known:
        unique_known = {a.id: a for a in known}
        if len(unique_known) == 1:
            a = next(iter(unique_known.values()))
            return CustomerVerification(
                status="verified",
                matched_on="customer_name",
                reference=a.name,
                customers=[_customer(a)],
                message=f"{a.name} is in the customer records.",
            )
        else:
            names = sorted(a.name for a in unique_known.values())
            return CustomerVerification(
                status="ambiguous",
                matched_on="customer_name",
                reference=people[0] if people else None,
                customers=[_customer(a) for a in unique_known.values()],
                message=f"{len(names)} customers in the records match: {', '.join(names[:-1])} and {names[-1]}.",
            )

    # No customer named in question: use verified active context if available
    if current is not None:
        return CustomerVerification(
            status="verified",
            matched_on="conversation",
            reference=current.name,
            customers=[_customer(current)],
            message=f"{current.name}, the customer already selected in this conversation.",
        )
    return CustomerVerification(status="not_named", message="The question does not name a customer yet.")


def verification_for_answer(conversation_id: str, question: str, policy: Optional[CorePolicy]) -> Optional[dict]:
    """How the customer of an answer was verified: the cached result, else the answered policy's customer."""
    cached = recall(conversation_id, question)
    if cached and cached.get("status") == "verified":
        return cached
    if policy is not None and policy.account is not None:
        return CustomerVerification(
            status="verified",
            matched_on="selected_policy",
            reference=policy.policy_number,
            customers=[_customer(policy.account)],
            message=f"{policy.account.name} is the customer on policy {policy.policy_number}.",
        ).model_dump()
    return cached
