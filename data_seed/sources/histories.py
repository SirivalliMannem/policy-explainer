"""Customer histories — the part the core cannot give you.

Guidewire will tell you what someone holds and what they claimed. It will
not tell you that they called four times in March, that the third call went
badly, or that they have not been heard from since their claim was declined.
That is the material A05 scores churn on and A03 opens a call with, and
without it Customer 360 is a policy list with a photograph on top.

Archetypes rather than noise. A book of uniformly-average customers
demonstrates nothing: the point of the screen is that it tells the
difference between a customer who is fine and one who is about to leave, and
it can only show that if both are in the book.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.models import CoreAccount, CoreClaim, CorePolicy, CustomerEvent
from app.platform import profiles

# Each archetype is a recipe: how often they get in touch, how it tends to
# go, and what has happened to them. The proportions are deliberate — most
# customers are fine, which is exactly why the few who are not have to be
# findable.
ARCHETYPES = [
    ("steady", 0.34),
    ("new", 0.12),
    ("claim_worn", 0.16),
    ("frustrated", 0.14),
    ("going_quiet", 0.12),
    ("high_value_attentive", 0.08),
    ("disputed", 0.04),
]

# How often this customer gets in touch, and how long it has been since they
# last did. Both matter, and only together: silence means nothing on its own.
# A customer who has never called is not going quiet; one who called every
# six weeks and has not called in nine months is the clearest churn signal a
# carrier has, and the only way to model it is to give the contacts a *habit*
# and then stop them.
CADENCE: dict[str, tuple[int, int]] = {
    # archetype: (days between contacts, days since the last one)
    "steady": (120, 45),
    "new": (40, 25),
    "claim_worn": (55, 40),
    "frustrated": (32, 20),
    "going_quiet": (38, 265),
    "high_value_attentive": (150, 55),
    "disputed": (40, 30),
}

SCRIPTS: dict[str, list[tuple[str, str, float, str]]] = {
    # (kind, what was said or done, sentiment, channel)
    "steady": [
        ("contact", "Can you email me a copy of my declarations page?", 0.3, "chat"),
        ("contact", "When is my next payment due?", 0.15, "phone"),
        ("contact", "I've changed my phone number.", 0.2, "portal"),
        ("csat", "Post-contact survey", 0.7, "email"),
        ("contact", "Thanks — that was quick, appreciate it.", 0.75, "phone"),
    ],
    "new": [
        ("contact", "I've just taken the policy out — what does Coverage C mean?", 0.1, "chat"),
        ("contact", "Do I need to tell you about the extension we're building?", 0.05, "phone"),
        ("csat", "Onboarding survey", 0.6, "email"),
    ],
    "claim_worn": [
        ("contact", "I need to report some water damage in the basement.", -0.25, "phone"),
        ("contact", "What is the status of my claim? Nobody has called me back.", -0.55, "phone"),
        ("contact", "This is the third time I've had to chase this.", -0.7, "phone"),
        ("csat", "Post-claim survey", 0.25, "email"),
        ("contact", "The adjuster came out, thank you.", 0.35, "phone"),
    ],
    "frustrated": [
        ("contact", "Why has my premium gone up by 22%? Nothing has changed.", -0.5, "phone"),
        ("contact", "I was told someone would call me back and nobody did.", -0.65, "phone"),
        ("complaint", "Premium increase not explained, and two missed callbacks", -0.75, "email"),
        ("contact", "I'm seriously considering going elsewhere.", -0.8, "phone"),
        ("csat", "Post-complaint survey", 0.15, "email"),
    ],
    "going_quiet": [
        ("contact", "Is storm damage to the fence covered?", -0.1, "chat"),
        ("contact", "So the claim's been declined? I see.", -0.6, "phone"),
        ("contact", "No, that's fine. Never mind.", -0.45, "phone"),
        # And then nothing. The silence is the signal, and it is created by
        # what is *absent* from this list rather than by anything in it.
    ],
    "high_value_attentive": [
        ("contact", "I'd like to add the jewellery schedule to the policy.", 0.3, "phone"),
        ("contact", "Can we review the limits before renewal?", 0.35, "phone"),
        ("csat", "Annual review survey", 0.85, "email"),
        ("contact", "Very helpful as always, thank you.", 0.8, "phone"),
    ],
    "disputed": [
        ("contact", "I don't accept the settlement figure on this claim.", -0.6, "phone"),
        ("complaint", "Settlement disputed — valuation challenged", -0.7, "letter"),
        ("litigation", "Attorney representation notified", -0.5, "letter"),
        ("contact", "All further correspondence to go through my attorney.", -0.55, "letter"),
    ],
}

EMOTIONS = {
    (-1.01, -0.65): "angry",
    (-0.65, -0.4): "frustrated",
    (-0.4, -0.15): "anxious",
    (-0.15, 0.2): "calm",
    (0.2, 0.55): "satisfied",
    (0.55, 1.01): "satisfied",
}


def _emotion(score: float) -> str:
    for (low, high), name in EMOTIONS.items():
        if low <= score < high:
            return name
    return "calm"


def _pick(rng: random.Random) -> str:
    roll = rng.random()
    running = 0.0
    for name, weight in ARCHETYPES:
        running += weight
        if roll <= running:
            return name
    return "steady"


def build(db: Session, org_id: str, *, months: int = 30) -> dict:
    """Give every customer in the book a past.

    Idempotent by customer: a profile that already has a timeline is left
    alone, so running this twice does not double everybody's contact count
    and quietly ruin every churn score on the book.
    """
    accounts = db.query(CoreAccount).filter(CoreAccount.org_id == org_id).all()
    if not accounts:
        return {"created": 0, "customers": 0, "note": "No accounts to build a history for."}

    now = datetime.utcnow()
    made = 0
    touched = 0
    spread: dict[str, int] = {}

    for account in accounts:
        profile = profiles.ensure(db, org_id, account)
        existing = (
            db.query(CustomerEvent)
            .filter(CustomerEvent.org_id == org_id, CustomerEvent.account_id == account.id)
            .count()
        )
        if existing:
            continue

        # Seeded on the account so the same customer is the same person on
        # every reseed — a demo where the angry customer moves each time you
        # restart is a demo nobody can rehearse.
        rng = random.Random(f"{org_id}:{account.id}:history")
        archetype = _pick(rng)
        spread[archetype] = spread.get(archetype, 0) + 1
        touched += 1

        policies = (
            db.query(CorePolicy)
            .filter(CorePolicy.org_id == org_id, CorePolicy.account_id == account.id)
            .order_by(CorePolicy.effective_date.asc())
            .all()
        )
        policy_number = policies[0].policy_number if policies else ""

        # ── What the core already knows, as dated events ──
        for policy in policies:
            made += 1
            db.add(CustomerEvent(
                org_id=org_id, account_id=account.id, kind="policy",
                occurred_at=datetime.combine(policy.effective_date, datetime.min.time()),
                title=(
                    f"{policy.product_name} incepted"
                    if policy.term_number == 1
                    else f"{policy.product_name} renewed, term {policy.term_number}"
                ),
                detail=f"${policy.annual_premium:,.0f} annual premium, {policy.state}.",
                policy_number=policy.policy_number, source="core", amount=policy.annual_premium,
                outcome=policy.status,
            ))

        claims = (
            db.query(CoreClaim)
            .filter(CoreClaim.org_id == org_id)
            .filter(CoreClaim.policy_id.in_([policy.id for policy in policies] or [""]))
            .all()
        )
        for claim in claims:
            made += 1
            when = (
                datetime.combine(claim.loss_date, datetime.min.time())
                if claim.loss_date else now - timedelta(days=rng.randint(30, 500))
            )
            db.add(CustomerEvent(
                org_id=org_id, account_id=account.id, kind="claim", occurred_at=when,
                title=f"Claim {claim.claim_number} — {(claim.loss_cause or '').replace('_', ' ')}",
                detail=claim.description or "",
                claim_number=claim.claim_number, policy_number=policy_number,
                outcome=claim.status, source="core",
            ))

        # ── What only we know: how it has gone ──
        script = SCRIPTS[archetype]
        # Place the contacts backwards from the last one, at this
        # archetype's own cadence. Spreading them evenly across the whole
        # window — which is what the first cut did — makes every customer's
        # gap equal to their cadence, and "gone quiet" can then never be
        # true for anybody.
        cadence, quiet = CADENCE[archetype]
        last_index = len(script) - 1

        for index, (kind, text, base, channel) in enumerate(script):
            days_ago = quiet + (last_index - index) * cadence + rng.randint(-6, 6)
            when = now - timedelta(days=max(1, days_ago))
            jitter = rng.uniform(-0.08, 0.08)
            score = max(-1.0, min(1.0, base + jitter))
            made += 1

            if kind == "csat":
                db.add(CustomerEvent(
                    org_id=org_id, account_id=account.id, kind="csat", occurred_at=when,
                    title=text, channel=channel, source="survey",
                    csat=round(1 + 4 * (score + 1) / 2, 1),
                ))
            elif kind == "complaint":
                db.add(CustomerEvent(
                    org_id=org_id, account_id=account.id, kind="complaint", occurred_at=when,
                    title=text, channel=channel, agent_code="A04", source="A04",
                    policy_number=policy_number, outcome="closed",
                    sentiment=round(score, 2), emotion=_emotion(score),
                ))
                made += 1
                db.add(CustomerEvent(
                    org_id=org_id, account_id=account.id, kind="complaint_closed",
                    occurred_at=when + timedelta(days=rng.randint(6, 20)),
                    title="Complaint closed — upheld, goodwill applied",
                    agent_code="A04", source="A04", outcome="upheld",
                ))
            elif kind == "litigation":
                db.add(CustomerEvent(
                    org_id=org_id, account_id=account.id, kind="litigation", occurred_at=when,
                    title=text, channel=channel, source="legal",
                    policy_number=policy_number,
                ))
            else:
                db.add(CustomerEvent(
                    org_id=org_id, account_id=account.id, kind="contact", occurred_at=when,
                    title=text, channel=channel, agent_code="A01",
                    actor="Contact centre", source="A01",
                    policy_number=policy_number, outcome="completed",
                    sentiment=round(score, 2), emotion=_emotion(score),
                ))

        # A couple of fraud signals across the book, and only where there is
        # a claim to hang them on. A flag with no claim behind it is noise a
        # special-investigations team would rightly ignore.
        if claims and rng.random() < 0.07:
            made += 1
            db.add(CustomerEvent(
                org_id=org_id, account_id=account.id, kind="fraud_signal",
                occurred_at=now - timedelta(days=rng.randint(20, 300)),
                title="Prior loss at the same address within 18 months",
                claim_number=claims[0].claim_number, source="A19 signals",
                detail="A signal for a person to look at. Not a finding.",
            ))

        db.flush()
        profiles.rebuild(db, org_id, account.id)

    return {
        "created": made,
        "customers": touched,
        "archetypes": spread,
        "note": (
            "Contacts, complaints, CSAT, sentiment, claims and policy history per customer. "
            "Archetype-weighted so the book contains customers who are fine and customers "
            "who are about to leave — a uniformly-average book proves nothing."
        ),
    }
