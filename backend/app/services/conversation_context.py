"""The customer a conversation is about, and follow-ups that refer to them without naming them.

A conversation has a customer once one is identified: with a single policy ("the exclusions of
HO-9021-4477"), or alone when they have several ("What are Elena's policies?"). Follow-ups then
resolve to that customer's policies: "What are the exclusions?", "What about the second one?",
"her auto policy", "Does she have another policy?". Nothing here reads another customer's records:
every policy offered comes from the conversation's own customer.
"""

from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.policy import CoreAccount, CorePolicy
from app.services.policy_resolver import ResolutionResult, current_terms, line_hint

# A person referred to rather than named.
PRONOUN = re.compile(
    r"\b(?:she|he|her|hers|him|his|they|them|their|theirs|(?:this|that|the\s+same)\s+(?:customer|client|policyholder|insured))\b",
    re.IGNORECASE,
)
# "the second one", "the first policy", "the last one", "policy 2", "number two".
_ORDINALS = {"first": 0, "1st": 0, "one": 0, "second": 1, "2nd": 1, "two": 1, "third": 2, "3rd": 2, "three": 2,
             "fourth": 3, "4th": 3, "four": 3, "last": -1}
ORDINAL = re.compile(
    r"\b(?:the\s+)?(first|1st|second|2nd|third|3rd|fourth|4th|last)\s+(?:one|policy|polic(?:y|ies)\s+listed)\b"
    r"|\b(?:policy|number|no\.?|#)\s*(one|two|three|four|[1-4])\b",
    re.IGNORECASE,
)
OTHER_POLICY = re.compile(r"\b(?:other|another|different)\s+(?:one|policy)\b", re.IGNORECASE)
# Words left in a message that only names someone ("Elena", "look up Elena Moreau", "customer Elena?").
_LOOKUP_WORDS = {
    "customer", "client", "policyholder", "insured", "look", "up", "lookup", "find", "search", "show", "me",
    "about", "please", "check", "pull", "open", "who", "is", "the", "for", "named", "called", "name",
    "details", "info", "information", "profile", "account", "record", "records", "s", "a", "an", "on", "file",
}


def active_customer(conversation: Optional[Conversation], db: Session) -> Optional[CoreAccount]:
    """The conversation's customer: the one chosen, else the customer of the selected policy."""
    if conversation is None:
        return None
    if conversation.customer_id:
        account = db.get(CoreAccount, conversation.customer_id)
        if account is not None:
            return account
    if conversation.policy_id:
        policy = db.get(CorePolicy, conversation.policy_id)
        if policy is not None:
            return policy.account
    return None


def customer_policies(account: CoreAccount, db: Session) -> list[CorePolicy]:
    """The customer's policies in the order they are listed to the employee: one row per policy
    number (in-force term first), in-force policies when there are any, by line then number."""
    rows = db.query(CorePolicy).filter(CorePolicy.account_id == account.id).all()
    terms = current_terms(rows)
    in_force = [p for p in terms if p.status == "in_force"]
    return sorted(in_force or terms, key=lambda p: (p.line_of_business, p.policy_number))


def ordinal_index(question: str) -> Optional[int]:
    """The position a question refers to ("the second one" is 1, "the last one" is -1), if any."""
    m = ORDINAL.search(question)
    if not m:
        return None
    word = (m.group(1) or m.group(2) or "").lower()
    if word.isdigit():
        return int(word) - 1
    return _ORDINALS.get(word)


def is_name_only(question: str, accounts: list[CoreAccount]) -> bool:
    """True when the message does nothing but name the customer(s) found in it ("Elena", "Who is
    David Chen?", "look up Margaret"): a customer lookup, not a question about a policy."""
    if not accounts:
        return False
    text = question.lower()
    for account in accounts:
        for part in [account.name.lower(), *account.name.lower().split()]:
            text = re.sub(rf"\b{re.escape(part)}(?:'s|’s)?\b", " ", text)
    leftover = [w for w in re.findall(r"[a-z0-9]+", text) if w not in _LOOKUP_WORDS]
    return not leftover


def resolve_follow_up(
    question: str,
    understood: str,
    customer: CoreAccount,
    active: Optional[CorePolicy],
    db: Session,
) -> Optional[ResolutionResult]:
    """Resolve a question that names no policy or customer against the conversation's customer.

    Returns None when the conversation's selected policy already answers it (a follow-up on the
    same policy). Several of the customer's policies are returned as ambiguous: the chat answers
    for each of them, or asks which one when the reference cannot pick one.
    """
    name = customer.name
    policies = customer_policies(customer, db)

    def resolved(policy: CorePolicy) -> ResolutionResult:
        return ResolutionResult(status="resolved", matched_on="conversation", reference=name, policy=policy)

    def several(candidates: list[CorePolicy], message: str) -> ResolutionResult:
        return ResolutionResult(status="ambiguous", matched_on="conversation", reference=name, candidates=candidates, message=message)

    if not policies:
        return ResolutionResult(status="not_found", matched_on="conversation", reference=name,
                                message=f"{name} is a customer on file but has no policies.")

    # "the second one": the customer's policies in the order they were listed.
    position = ordinal_index(question)
    if position is not None:
        if -len(policies) <= position < len(policies):
            return resolved(policies[position])
        listed = ", ".join(p.policy_number for p in policies)
        return ResolutionResult(
            status="not_found", matched_on="conversation", reference=name,
            message=f"{name} has only {len(policies)} {'policy' if len(policies) == 1 else 'policies'} ({listed}).",
        )

    # "her auto policy", "the homeowners one", "is the roof covered?". A hint no policy of the
    # customer matches ("flood" on an auto policy) narrows nothing: comprehensive auto covers flood too.
    hint = line_hint(understood) or line_hint(question)
    hinted = [p for p in policies if p.line_of_business == hint] if hint else []
    if len(hinted) == 1:
        return resolved(hinted[0])
    if hinted:
        return several(hinted, f"{name} has more than one {hint.replace('_', ' ')} policy.")

    # "her other policy", "what about the other one?".
    if OTHER_POLICY.search(question):
        others = [p for p in policies if not active or p.policy_number != active.policy_number]
        if len(others) == 1:
            return resolved(others[0])
        if others:
            return several(others, f"{name} has {len(others)} other policies that could apply.")
        return ResolutionResult(status="not_found", matched_on="conversation", reference=name,
                                message=f"{name} has no other policy on file.")

    # A follow-up on the selected policy stays with it.
    if active is not None:
        return None

    # The customer without one selected policy: their only policy, or each of them.
    if len(policies) == 1:
        return resolved(policies[0])
    return several(policies, f"{name} has {len(policies)} policies.")
