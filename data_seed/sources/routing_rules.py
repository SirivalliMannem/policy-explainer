"""The carrier's starting routing rules.

Every one of these is a line in a BRD's hand-off lane, not our invention —
which matters, because the first thing a claims operations lead will do is
read them and decide whether we understood their business.

Ordered, first match wins, and the last one matches everything. "Nobody" is
never an outcome: a file with no owner is how something ages past its
service standard with no one accountable.

Seeded as defaults and marked as such, so it is obvious which ones the
carrier has actually looked at.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import RoutingRule

# (position, name, description, conditions, outcome)
DEFAULTS: list[tuple[int, str, str, list, dict]] = [
    (
        10, "Fatality or injury to a senior adjuster",
        "A14's safety lane and A15's triage both stop on injury. A bodily-injury "
        "file handled by a new starter is the most expensive routing mistake a "
        "carrier makes.",
        [{"field": "injury", "op": "is_true"}],
        {"type": "role", "value": "adjuster", "kindLabel": "senior adjuster",
         "queue": "claims", "slaHours": 1},
    ),
    (
        20, "A vulnerable customer goes to a team lead",
        "A01 SF-07: a vulnerable contact is never kept by an agent. It is also "
        "never left in a pool — somebody is accountable for it by name.",
        [{"field": "vulnerable", "op": "is_true"}],
        {"type": "role", "value": "team_lead", "kindLabel": "team lead",
         "queue": "claims", "slaHours": 1},
    ),
    (
        30, "Fraud signals to SIU",
        "A19's signals are for a person, never a finding. They go to special "
        "investigations rather than to the adjuster whose file it is.",
        [{"field": "fraudSignal", "op": "is_true"}],
        {"type": "role", "value": "claims_manager", "kindLabel": "SIU",
         "queue": "claims", "slaHours": 8},
    ),
    (
        40, "Anything in litigation to coverage counsel",
        "Once attorneys are involved the coverage position is counsel's, "
        "wherever in the organisation the file sits.",
        [{"field": "litigation", "op": "is_true"}],
        {"type": "role", "value": "coverage_counsel", "kindLabel": "coverage counsel",
         "queue": "coverage", "slaHours": 8},
    ),
    (
        50, "Coverage questions to coverage counsel",
        "A02 §3.1 step 6 and A15's escalation: a loss-specific or ambiguous "
        "coverage question is a decision, and A02 is not permitted to make it.",
        [{"field": "queue", "op": "eq", "value": "coverage"}],
        {"type": "role", "value": "coverage_counsel", "kindLabel": "coverage counsel",
         "queue": "coverage", "slaHours": 4},
    ),
    (
        60, "A reserve above authority goes up the line",
        "A17: above the adjuster's limit means approval, not a warning. The "
        "approver is named before the figure can be committed.",
        [{"field": "agent", "op": "eq", "value": "A17"},
         {"field": "amount", "op": "gt", "value": 50000}],
        {"type": "role", "value": "claims_manager", "kindLabel": "claims manager",
         "queue": "claims", "slaHours": 8},
    ),
    (
        70, "Complaints to a named complaints handler",
        "A04: every complaint gets a named owner at creation, with the "
        "chronology and a drafted response. The clock is already running.",
        [{"field": "agent", "op": "eq", "value": "A04"}],
        {"type": "role", "value": "compliance_officer", "kindLabel": "complaints handler",
         "queue": "claims", "slaHours": 4},
    ),
    (
        80, "Premium and billing questions to the service team",
        "A02 routes these away from the coverage queue on purpose — sending "
        "billing questions to counsel buries the decisions that matter.",
        [{"field": "reason", "op": "in", "value": ["premium_promise", "billing", "premium_question"]}],
        {"type": "role", "value": "csr", "kindLabel": "customer service",
         "queue": "claims", "slaHours": 8},
    ),
    (
        90, "High severity to a senior adjuster",
        "Severity is exposure. A16 and A15 both score it, and it is the "
        "signal a claims desk actually staffs against.",
        [{"field": "severity", "op": "eq", "value": "high"}],
        {"type": "role", "value": "adjuster", "kindLabel": "senior adjuster",
         "queue": "claims", "slaHours": 4},
    ),
    (
        1000, "Everything else to the claims desk",
        "The default, and it matches everything. A file with no owner is how "
        "something ages past its service standard with nobody accountable, so "
        "there is always a last rule and it always names somebody.",
        [],
        {"type": "role", "value": "adjuster", "kindLabel": "adjuster",
         "queue": "claims"},
    ),
]


def backfill(db: Session, org_id: str) -> int:
    """Give the work already on the book an owner.

    Anything handed over before the rules existed sits unassigned, and a
    workbench showing a column of dashes says the opposite of what this
    feature is for. Runs the live rules over those files only — it never
    touches one a person has already been given.
    """
    from app.models.models import QueueItem
    from app.platform import routing

    orphans = (
        db.query(QueueItem)
        .filter(
            QueueItem.org_id == org_id,
            QueueItem.assignee_id.is_(None),
            QueueItem.status.in_(["waiting", "in_review"]),
        )
        .all()
    )
    for item in orphans:
        assignment = routing.decide(db, org_id, {
            "agent": item.agent_code, "reason": item.reason, "queue": item.queue,
            "kind": item.kind, "lineOfBusiness": item.line_of_business,
            "state": item.state, "severity": item.severity, "amount": item.amount,
        })
        routing.apply_to(db, item, assignment, by="routing (backfill)")
    db.flush()
    return len(orphans)


def build(db: Session, org_id: str) -> dict:
    """Seed the defaults. Idempotent by name, and never overwrites a rule
    the carrier has edited — the whole point is that these are theirs."""
    existing = {
        row.name: row
        for row in db.query(RoutingRule).filter(RoutingRule.org_id == org_id).all()
    }
    created = 0
    for position, name, description, conditions, outcome in DEFAULTS:
        if name in existing:
            continue
        db.add(RoutingRule(
            org_id=org_id, name=name, description=description, position=position,
            conditions=conditions, outcome=outcome, active=True,
            version="1", updated_by="FI360 (default)", seeded=True,
        ))
        created += 1
    db.flush()
    filled = backfill(db, org_id)
    return {
        "created": created,
        "total": len(DEFAULTS),
        "backfilled": filled,
        "note": (
            "Every rule is a line from a BRD hand-off lane rather than our "
            "invention. Ordered, first match wins, and the last one matches "
            "everything — no file is ever left without an owner. Work handed "
            "over before the rules existed is given an owner too; anything "
            "already assigned to a person is left alone."
        ),
    }
