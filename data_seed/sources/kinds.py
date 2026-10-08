"""Synthetic data for all ten agents, not just the policy ones.

The generator made policyholders, policies, coverages and forms. That was
enough when three agents were live and two of them read policies; with ten it
is not, and the gap was not cosmetic — A17 could not do its job. RS-03 asks it
to match comparable *closed* claims and show what they settled at, and there
were no closed claims in the book, so every recommendation fell back to a
baseline and said so.

Each generator here produces one kind. Wording is still never generated: new
policies attach forms the tenant already holds, so every citation stays real.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.models import (
    AgentCase,
    Clause,
    CoreAccount,
    CoreClaim,
    CorePolicy,
)

# Typical indemnity by line and cause, and how widely it disperses. A
# comparables set with no spread teaches A17 nothing — real closed claims on
# the same cause settle across a range, and the range is the useful part.
SETTLEMENT = {
    ("personal_auto", "collision"): (6800, 0.55),
    ("personal_auto", "comprehensive"): (2400, 0.6),
    ("homeowners", "water"): (11500, 0.7),
    ("homeowners", "wind_hail"): (14200, 0.8),
    ("homeowners", "fire"): (48000, 0.9),
    ("homeowners", "theft"): (5200, 0.65),
}

NARRATIVES = {
    ("personal_auto", "collision"): [
        "I was rear-ended at the lights on my way to work. Bumper and tailgate are damaged, nobody is hurt.",
        "Someone pulled out of a junction and hit my passenger side. The door will not open.",
        "I clipped a bollard reversing out of a parking space and scraped the rear quarter.",
    ],
    ("personal_auto", "comprehensive"): [
        "A stone came off a truck and cracked my windscreen right across.",
        "My car was broken into overnight and the window is smashed.",
        "A deer ran out in front of me on the county road and took out the front end.",
    ],
    ("homeowners", "water"): [
        "A pipe under the kitchen sink let go overnight and the floor is soaked.",
        "The water heater failed and flooded the utility room and part of the hallway.",
        "Water backed up through the basement drain after the storm.",
    ],
    ("homeowners", "wind_hail"): [
        "The storm took shingles off the roof and water is coming into the upstairs bedroom.",
        "Hail came through in the afternoon and the siding and gutters are dented all along the south side.",
        "A tree came down across the garage in the wind.",
    ],
    ("homeowners", "fire"): [
        "There was a fire in the kitchen. The fire service attended and the room is gutted.",
        "An electrical fault started a fire in the loft. Smoke damage throughout.",
    ],
    ("homeowners", "theft"): [
        "We were burgled while we were away. They took jewellery and a laptop.",
        "Someone forced the back door and took tools from the garage.",
    ],
}

COMPLAINTS = [
    ("This is the third time I have called and nobody has called me back. It is unacceptable.", "unlabelled"),
    ("I would like to make a formal complaint about how my claim has been handled.", "explicit"),
    ("Still waiting. Nobody has told me anything for two weeks and I am getting nowhere.", "unlabelled"),
    ("I am writing from the Texas Department of Insurance regarding a complaint filed against your company.", "regulator"),
    ("Your adjuster was rude to my wife on the phone and I want to speak to a manager.", "unlabelled"),
    ("I was mis-sold this policy. Nobody explained the wind deductible to me at all.", "explicit"),
]

CONTACTS = [
    ("When is my next payment due?", "billing_status"),
    ("Can you send me a copy of my declarations page?", "documents"),
    ("Is sewer backup covered on my home policy?", "coverage_question"),
    ("I have moved house, and is sewer backup covered?", "multi_intent"),
    ("What is the status of my claim?", "claim_status"),
    ("I had an accident this morning, another car hit me.", "report_loss"),
    ("My husband passed away last week and I need to sort out the policy.", "vulnerable"),
    ("I am shopping around, your renewal quote is higher than last year.", "churn"),
]

ADJUSTERS = ["R. Villanueva", "T. Okonkwo", "M. Delacroix", "S. Hartley", "P. Nakamura"]


def _rng(org_id: str, kind: str, count: int) -> random.Random:
    return random.Random(abs(hash(f"{org_id}{kind}{count}")) % (2**31))


def _policies(db: Session, org_id: str) -> list[CorePolicy]:
    return (
        db.query(CorePolicy)
        .filter(CorePolicy.org_id == org_id, CorePolicy.status == "in_force")
        .all()
    )



def _loss_date_inside(policy, rng, *, earliest_days: int, latest_days: int) -> date:
    """A loss date that actually falls inside the policy it belongs to.

    This was picked from today's calendar and the policy period ignored, so
    two thirds of the book had losses outside their own term — and A15,
    quite correctly, reported "policy NOT in force on the loss date" for
    almost every claim. The agent was right and the data was wrong, which
    is the more embarrassing of the two.
    """
    today = date.today()
    window_start = max(policy.effective_date, today - timedelta(days=latest_days))
    window_end = min(policy.expiration_date, today - timedelta(days=earliest_days))
    if window_end < window_start:
        # The term does not overlap the window we wanted — an old expired
        # term, or one that has not started. Land inside the term itself
        # rather than outside it.
        window_start, window_end = policy.effective_date, min(policy.expiration_date, today)
    if window_end < window_start:
        return policy.effective_date
    span = (window_end - window_start).days
    return window_start + timedelta(days=rng.randrange(span + 1) if span > 0 else 0)


def _next_claim_number(db: Session, org_id: str, offset: int = 0) -> str:
    count = db.query(CoreClaim).filter(CoreClaim.org_id == org_id).count()
    return f"CLM-{date.today().year}-{count + offset + 1:05d}"


# ── closed claims — A17's comparables (RS-03) ───────────────────────────


def closed_claims(db: Session, org_id: str, count: int, *, commit: bool = False) -> dict:
    """The history A17 matches against. Without these, every recommendation
    is a baseline and the agent looks thin for a reason that is our fault."""
    rng = _rng(org_id, "closed", count)
    policies = _policies(db, org_id)
    if not policies:
        return {"created": 0, "preview": [], "note": "Seed the book first."}

    preview = []
    for index in range(count):
        policy = rng.choice(policies)
        causes = [cause for line, cause in SETTLEMENT if line == policy.line_of_business]
        if not causes:
            continue
        cause = rng.choice(causes)
        centre, spread = SETTLEMENT[(policy.line_of_business, cause)]
        # Log-normal-ish: most cluster near the centre, a few run long, which
        # is what a real closed-claim distribution looks like.
        settled = round(centre * rng.lognormvariate(0, spread), -2)
        loss_date = _loss_date_inside(policy, rng, earliest_days=120, latest_days=900)
        closed_date = loss_date + timedelta(days=rng.randrange(20, 160))
        number = _next_claim_number(db, org_id, index)
        narrative = rng.choice(NARRATIVES.get((policy.line_of_business, cause), ["Closed claim."]))

        db.add(
            CoreClaim(
                org_id=org_id, policy_id=policy.id, claim_number=number,
                loss_date=loss_date, reported_date=loss_date + timedelta(days=1),
                loss_cause=cause, loss_location=policy.insured_location,
                description=narrative, status="closed",
                adjuster=rng.choice(ADJUSTERS),
                exposures=[{
                    "type": "Indemnity", "detail": cause.replace("_", " "),
                    "settled": settled, "closedOn": closed_date.isoformat(),
                }],
                contacts=[{"role": "insured", "name": ""}],
            )
        )
        preview.append({
            "claimNumber": number, "policyNumber": policy.policy_number,
            "lossCause": cause, "lossDate": loss_date.isoformat(),
            "settled": settled, "status": "closed",
        })
    db.flush()
    return {
        "created": len(preview), "preview": preview,
        "note": "A17 matches these on line of business and loss cause, and shows what they settled at.",
    }


# ── open claims at a stage — A15, A16, A18 ──────────────────────────────

STAGES = {
    "notice_taken": "Notice taken, nothing else yet.",
    "evidence_in": "Photos and a police report on the file.",
    "estimate_loaded": "A repair estimate has been loaded.",
    "ready_to_settle": "Everything in; waiting on a reserve decision.",
}


def open_claims(db: Session, org_id: str, count: int, stage: str = "notice_taken") -> dict:
    """A16's checkpoints need claims at different stages to pass and fail."""
    rng = _rng(org_id, f"open{stage}", count)
    policies = _policies(db, org_id)
    if not policies:
        return {"created": 0, "preview": [], "note": "Seed the book first."}

    preview = []
    for index in range(count):
        policy = rng.choice(policies)
        causes = [cause for line, cause in SETTLEMENT if line == policy.line_of_business]
        cause = rng.choice(causes) if causes else "other"
        loss_date = _loss_date_inside(policy, rng, earliest_days=1, latest_days=40)
        number = _next_claim_number(db, org_id, index)
        narrative = rng.choice(NARRATIVES.get((policy.line_of_business, cause), ["Loss reported."]))

        exposure = {"type": "Indemnity", "detail": cause.replace("_", " "), "reserve": "Not set"}
        described = narrative
        if stage in ("evidence_in", "estimate_loaded", "ready_to_settle"):
            described += " Photos have been uploaded."
        if stage in ("estimate_loaded", "ready_to_settle"):
            centre = SETTLEMENT.get((policy.line_of_business, cause), (8000, 0.5))[0]
            exposure["estimate"] = round(centre * rng.uniform(0.7, 1.4), -2)

        db.add(
            CoreClaim(
                org_id=org_id, policy_id=policy.id, claim_number=number,
                loss_date=loss_date, reported_date=loss_date,
                loss_cause=cause, loss_location=policy.insured_location,
                description=described, status="open",
                adjuster=rng.choice(ADJUSTERS),
                exposures=[exposure],
                contacts=[{"role": "insured", "name": ""}],
            )
        )
        preview.append({
            "claimNumber": number, "policyNumber": policy.policy_number,
            "lossCause": cause, "lossDate": loss_date.isoformat(),
            "stage": stage, "estimate": exposure.get("estimate"),
        })
    db.flush()
    return {"created": len(preview), "preview": preview, "note": STAGES.get(stage, "")}


# ── complaint text — A04 (CG-01, CG-07) ─────────────────────────────────


def complaints(db: Session, org_id: str, count: int) -> dict:
    """Text for A04 to detect, so nobody has to paste examples in by hand."""
    rng = _rng(org_id, "complaints", count)
    policies = _policies(db, org_id)
    accounts = {row.id: row for row in db.query(CoreAccount).filter(CoreAccount.org_id == org_id)}
    preview = []
    for index in range(count):
        text, flavour = COMPLAINTS[index % len(COMPLAINTS)]
        policy = rng.choice(policies) if policies else None
        account = accounts.get(policy.account_id) if policy else None
        db.add(
            AgentCase(
                org_id=org_id, agent_code="A04", case_type="complaint_inbox",
                reference=f"IN-{date.today().year}-{index + 1:04d}",
                title=text[:160], subtitle=f"inbound · {flavour}",
                party=account.name if account else "",
                state=policy.state if policy else "",
                line_of_business=policy.line_of_business if policy else "",
                policy_number=policy.policy_number if policy else "",
                status="unread", severity="high" if flavour == "regulator" else "medium",
                payload={"text": text, "flavour": flavour, "channel": "email"},
            )
        )
        preview.append({"text": text[:90], "flavour": flavour,
                        "policyNumber": policy.policy_number if policy else ""})
    db.flush()
    return {
        "created": len(preview), "preview": preview,
        "note": "Explicit, unlabelled and regulator examples — A04 has to find all three.",
    }


# ── contacts and transcripts — A01, A03 (SF-04, LA-01) ──────────────────


def contacts(db: Session, org_id: str, count: int) -> dict:
    rng = _rng(org_id, "contacts", count)
    policies = _policies(db, org_id)
    accounts = {row.id: row for row in db.query(CoreAccount).filter(CoreAccount.org_id == org_id)}
    preview = []
    for index in range(count):
        text, intent = CONTACTS[index % len(CONTACTS)]
        policy = rng.choice(policies) if policies else None
        account = accounts.get(policy.account_id) if policy else None
        transcript = [
            {"speaker": "csr", "text": "Thanks for holding — how can I help?"},
            {"speaker": "customer", "text": text},
        ]
        db.add(
            AgentCase(
                org_id=org_id, agent_code="A01", case_type="contact_inbox",
                reference=f"CT-{date.today().year}-{index + 1:04d}",
                title=text[:160], subtitle=f"{intent} · chat",
                party=account.name if account else "",
                state=policy.state if policy else "",
                policy_number=policy.policy_number if policy else "",
                status="unread",
                payload={"transcript": transcript, "expectedIntent": intent, "channel": "chat"},
            )
        )
        preview.append({"text": text[:80], "intent": intent,
                        "policyNumber": policy.policy_number if policy else ""})
    db.flush()
    return {
        "created": len(preview), "preview": preview,
        "note": "Drives A01's triage and A03's live-assist console, including multi-intent and vulnerability.",
    }


# ── everything, coherent ────────────────────────────────────────────────


def everything(db: Session, org_id: str) -> dict:
    """One action that produces a book exercising all ten agents."""
    from app.seed import directory as directory_seed, histories, routing_rules

    result = {
        "closedClaims": closed_claims(db, org_id, 24),
        "openClaims": {
            stage: open_claims(db, org_id, 2, stage=stage) for stage in STAGES
        },
        "complaints": complaints(db, org_id, 6),
        "contacts": contacts(db, org_id, 8),
    }
    # Last, deliberately: a customer history is built from the claims and
    # policies that exist at the time, so it has to run after them.
    result["customerHistories"] = histories.build(db, org_id)
    # The org chart, so the access rules have people to apply to, and the
    # routing rules, so a hand-off has somebody to land on.
    result["directory"] = directory_seed.build(db, org_id)
    result["routingRules"] = routing_rules.build(db, org_id)
    # Anything already on the book with an impossible loss date.
    result["lossDateRepair"] = repair_loss_dates(db, org_id)
    return result


def counts(db: Session, org_id: str) -> dict:
    """What exists now, by kind — so the page can show the book rather than
    only offer to enlarge it."""
    closed = (
        db.query(CoreClaim)
        .filter(CoreClaim.org_id == org_id, CoreClaim.status == "closed")
        .count()
    )
    open_count = (
        db.query(CoreClaim)
        .filter(CoreClaim.org_id == org_id, CoreClaim.status == "open")
        .count()
    )
    inbox = (
        db.query(AgentCase)
        .filter(AgentCase.org_id == org_id, AgentCase.case_type.in_(["complaint_inbox", "contact_inbox"]))
        .count()
    )
    from app.platform import profiles

    return {
        "closedClaims": closed,
        "openClaims": open_count,
        "inbox": inbox,
        "clauses": db.query(Clause).filter(Clause.org_id == org_id).count(),
        **profiles.counts(db, org_id),
    }


def repair_loss_dates(db: Session, org_id: str) -> dict:
    """Move claims whose loss date sits outside their own policy term.

    Two thirds of the seeded book was like this, so every triage reported
    "policy NOT in force on the loss date". Nothing was wrong with A15 —
    it was reading the data correctly, and the data was nonsense.
    """
    import random

    moved = []
    # Every policy, not only the in-force ones. A claim on last year's term
    # is still a claim, and the first pass skipped them — which left most
    # of the book still reporting "not in force".
    policies = {
        policy.id: policy
        for policy in db.query(CorePolicy).filter(CorePolicy.org_id == org_id).all()
    }
    for claim in db.query(CoreClaim).filter(CoreClaim.org_id == org_id).all():
        policy = policies.get(claim.policy_id)
        if policy is None or claim.loss_date is None:
            continue
        if policy.effective_date <= claim.loss_date <= policy.expiration_date:
            continue

        rng = random.Random(f"{org_id}:{claim.id}:lossdate")
        was = claim.loss_date
        claim.loss_date = _loss_date_inside(
            policy, rng,
            earliest_days=(120 if claim.status == "closed" else 1),
            latest_days=(900 if claim.status == "closed" else 40),
        )
        if claim.reported_date and claim.reported_date < claim.loss_date:
            claim.reported_date = claim.loss_date + timedelta(days=1)
        moved.append({
            "claimNumber": claim.claim_number,
            "was": was.isoformat(),
            "now": claim.loss_date.isoformat(),
            "policy": policy.policy_number,
        })
    db.flush()
    return {
        "moved": len(moved),
        "preview": moved[:6],
        "note": (
            "Claims whose loss date fell outside their own policy term. A15 was "
            "reporting them as not in force, which was correct — the book was wrong."
        ),
    }
