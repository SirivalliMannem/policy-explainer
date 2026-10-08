"""A carrier's library, the second shelf.

The form library answers "what does the wording say". A contact centre
also needs "what does this product actually cover", "what do I say when
somebody asks to cancel", "how does a mid-term change work" — and until
there was something on this shelf, A03's retrieval had one place to look.

Written the way a real carrier's knowledge base is: an article for the
customer, and a `spoken` line for what a CSR would actually say out loud,
because a brochure paragraph read aloud sounds like a brochure.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from data_seed.models.models import KnowledgeCollection, KnowledgeDocument

OWNER = "Product & Service Content"

# (name, kind, description, line of business, state, documents)
LIBRARY: list[tuple[str, str, str, str, str, list[tuple[str, str, str, list[str]]]]] = [
    (
        "Homeowners — what it covers",
        "product_article",
        "The plain-language product article for the HO-3 special form.",
        "homeowners", "",
        [
            (
                "Water damage: what is covered and what is not",
                "Your homeowners policy covers sudden and accidental water damage — a pipe "
                "that bursts, an appliance hose that fails, a water heater that lets go. It "
                "does not cover damage that built up slowly from a leak you could have seen, "
                "and it does not cover water that comes up from the ground or backs up "
                "through a drain unless you have bought that cover separately.",
                "Sudden is covered, gradual is not. Water coming up from outside or back up a "
                "drain needs the separate endorsement — let me check whether you have it.",
                ["water", "leak", "burst", "pipe", "flood", "sewer", "backup", "seepage"],
            ),
            (
                "Water backup and sump overflow cover",
                "Water that backs up through sewers or drains, or overflows from a sump pump, "
                "is excluded by the base policy. It can be added by endorsement, usually with "
                "its own limit — often much lower than your dwelling limit — and its own "
                "deductible.",
                "That one is an add-on rather than part of the base policy, and it carries its "
                "own limit. Let me look at what is on your declarations.",
                ["backup", "sewer", "drain", "sump", "endorsement", "basement"],
            ),
            (
                "Wind and hail: why the deductible is a percentage",
                "In states exposed to severe convective storms, the wind and hail deductible is "
                "often set as a percentage of the dwelling limit rather than a flat amount. On a "
                "larger home that can be a materially bigger number than the all-other-perils "
                "deductible, and it is set that way to keep the premium affordable.",
                "Wind and hail runs on a percentage of your dwelling limit rather than a flat "
                "figure — so it works out higher than your ordinary deductible.",
                ["wind", "hail", "deductible", "percentage", "storm", "roof"],
            ),
        ],
    ),
    (
        "Personal auto — what it covers",
        "product_article",
        "The plain-language product article for the personal auto policy.",
        "personal_auto", "",
        [
            (
                "Collision and comprehensive: which one applies",
                "Collision covers damage from hitting another vehicle or an object. "
                "Comprehensive covers almost everything else that can happen to a parked or "
                "moving car — theft, fire, vandalism, hail, a cracked windscreen, and hitting "
                "an animal. Each carries its own deductible, and comprehensive is usually the "
                "lower of the two.",
                "Hitting something is collision; almost everything else — theft, hail, an "
                "animal — is comprehensive, and that deductible is usually the lower one.",
                ["collision", "comprehensive", "deductible", "animal", "deer", "theft", "hail"],
            ),
            (
                "Rental cover while your car is repaired",
                "If you carry rental reimbursement, we pay up to a daily amount for a set number "
                "of days while a covered repair is under way. It does not apply where the loss "
                "itself is not covered, and it is capped per day rather than by what the rental "
                "company charges.",
                "If you have rental on the policy we cover a daily amount while it is being "
                "fixed — it is a daily cap rather than whatever the hire company charges.",
                ["rental", "hire car", "courtesy", "loss of use", "repair"],
            ),
        ],
    ),
    (
        "Service catalogue",
        "catalogue",
        "What a policyholder can ask for, and how each one is done.",
        "", "",
        [
            (
                "Mid-term change: adding or removing a vehicle or driver",
                "A mid-term change takes effect the day it is requested unless a later date is "
                "asked for. The premium is adjusted pro rata for the rest of the term and the "
                "difference appears on the next instalment rather than as a separate bill.",
                "I can do that from today, or from a date you choose. The premium changes pro "
                "rata and you will see it on your next instalment rather than as a separate bill.",
                ["add", "remove", "vehicle", "driver", "mid-term", "change", "endorsement"],
            ),
            (
                "Proof of insurance and certificates",
                "An ID card or a certificate of insurance can be issued immediately and sent by "
                "email, post, or to the app. A lienholder or mortgagee certificate is sent "
                "directly to them and a copy to the policyholder.",
                "I can send that to you right now — email, post or the app, whichever suits.",
                ["proof", "certificate", "id card", "lienholder", "mortgagee", "evidence"],
            ),
            (
                "Cancelling a policy mid-term",
                "A policyholder may cancel at any time. Any return premium is calculated pro "
                "rata from the cancellation date. Where a lienholder or mortgagee is listed, "
                "they are notified. Cancelling leaves a gap in cover, which can affect the "
                "price of the next policy.",
                "You can cancel whenever you like and you would get the unused premium back pro "
                "rata. One thing worth knowing: a gap in cover can put the price up next time.",
                ["cancel", "cancellation", "refund", "return premium", "lapse", "gap"],
            ),
        ],
    ),
    (
        "What to say when",
        "script",
        "Approved wording for the situations the floor finds hardest.",
        "", "",
        [
            (
                "A caller has been transferred more than once",
                "Acknowledge it first and specifically — not 'sorry for any inconvenience' but "
                "'you have had to explain this twice already, and that is on us'. Then say what "
                "you are going to do, and do not transfer again without staying on the line.",
                "You have had to explain this twice already and that is on us. I have your file "
                "in front of me, so let me take it from here.",
                ["transfer", "transferred", "repeat", "again", "third time", "explain"],
            ),
            (
                "A caller asks whether something is covered",
                "Explain what the wording says and cite it. Do not say whether their particular "
                "loss is covered — that is a coverage determination and belongs to an adjuster, "
                "who has the facts of the loss. Saying yes on a call and no in a letter is how a "
                "complaint becomes a regulatory one.",
                "I can tell you exactly what your policy says about that. Whether it applies to "
                "what happened is the adjuster's call once they have the details — I do not want "
                "to tell you one thing and have the letter say another.",
                ["covered", "coverage", "will you pay", "is it covered", "denied"],
            ),
            (
                "A caller says they are cancelling",
                "Ask what changed before offering anything. Most cancellations are about one "
                "specific event — a claim handled badly, a price rise nobody explained, a person "
                "they could not reach. A discount offered before the reason is understood buys "
                "nothing and teaches the customer to ask again.",
                "Before I do that — can I ask what changed? If something went wrong I would "
                "rather fix that than just process this.",
                ["cancel", "leaving", "switch", "competitor", "shopping", "quote elsewhere"],
            ),
        ],
    ),
    (
        "Storm season support",
        "offering",
        "The current catastrophe-season programme. Effective-dated so it stops "
        "being quoted the day it ends.",
        "homeowners", "TX",
        [
            (
                "Emergency accommodation during a named storm event",
                "Where a home is not habitable following a named storm, the carrier arranges "
                "and pays for emergency accommodation directly for the first seven nights, "
                "without requiring the policyholder to pay and claim it back.",
                "You will not be out of pocket for somewhere to stay — we arrange it and pay it "
                "directly for the first week.",
                ["storm", "hurricane", "not habitable", "accommodation", "hotel", "ale",
                 "additional living expense", "displaced"],
            ),
        ],
    ),
]


def build(db: Session, org_id: str) -> dict:
    """Seed the library. Idempotent by collection name."""
    existing = {
        row.name: row
        for row in db.query(KnowledgeCollection).filter(
            KnowledgeCollection.org_id == org_id
        ).all()
    }

    made, documents = 0, 0
    today = date.today()

    for name, kind, description, lob, state, docs in LIBRARY:
        collection = existing.get(name)
        if collection is None:
            collection = KnowledgeCollection(
                org_id=org_id, name=name, kind=kind, description=description,
                line_of_business=lob, state=state, owner=OWNER,
                status="published", version="1",
                effective_from=today - timedelta(days=120),
                # The storm programme ends, and must stop being quoted
                # the day it does — which is the thing effective dating
                # is here to prove.
                effective_to=(today + timedelta(days=90)) if kind == "offering" else None,
                seeded=True,
            )
            db.add(collection)
            db.flush()
            made += 1

        have = {
            row.title
            for row in db.query(KnowledgeDocument).filter(
                KnowledgeDocument.org_id == org_id,
                KnowledgeDocument.collection_id == collection.id,
            ).all()
        }
        for title, body, spoken, keywords in docs:
            if title in have:
                continue
            db.add(KnowledgeDocument(
                org_id=org_id, collection_id=collection.id, title=title,
                body=body, spoken=spoken, keywords=keywords,
                version="1", approved_by=OWNER, active=True, seeded=True,
            ))
            documents += 1

    db.flush()
    return {"collections": made, "documents": documents}
