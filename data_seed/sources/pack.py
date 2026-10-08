"""The synthetic demo pack.

A small book of business that behaves like a real one, per tenant, Guidewire-
shaped. The point is not volume — it is that the awkward cases exist:

  * a renewal that genuinely differs from the expiring term, so "what changed
    at renewal?" (PE-09) has an answer that comes from data
  * one homeowners policy *with* the water back-up endorsement and one
    *without*, so the same question has two correct and different answers
  * a state amendatory page that overrides the base form
  * an open claim, so A02 can hand a loss question to an adjuster who exists
  * generic product wording alongside the customer's own forms, so the
    ranking rule in PE-02 has something to actually beat

Everything carries org_id and `synthetic=True`. Nothing here is global.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from data_seed.models.models import (
    Clause,
    CoreAccount,
    CoreBilling,
    CoreClaim,
    CoreCoverage,
    CoreForm,
    CorePolicy,
    GoldenQuestion,
)
from data_seed.sources import forms_auto, forms_es, forms_home

TABLES = [Clause, CoreClaim, CoreBilling, CoreCoverage, CoreForm, CorePolicy, CoreAccount, GoldenQuestion]

# Household ids are generated here rather than taken from a core system,
# because there is no core system in the synthetic book.
def _uuid() -> str:
    import uuid

    return str(uuid.uuid4())


def wipe_order() -> list:
    """The pack's tables, plus everything that points at them, in an
    order the database will accept.

    `TABLES` is the declared contents of the pack and it is written
    parent-last by hand, which held for exactly as long as nothing else
    referenced a seeded row. `customer_profile` now references
    `core_account`, so re-seeding tried to delete an account out from
    under a profile.

    SQLite let that through — it does not enforce foreign keys unless
    asked — so the rows were left dangling and nobody noticed. Postgres
    refuses, which is the correct behaviour and the reason this is
    derived rather than listed: the next table somebody adds should not
    need this comment to be read again.
    """
    from sqlalchemy.sql.ddl import sort_tables

    from data_seed.database import Base

    declared = {model.__tablename__: model for model in TABLES}

    # Everything that depends on a pack table, transitively — deleting
    # the parent means deleting these too, or they would dangle.
    by_name = Base.metadata.tables
    caught = set(declared)
    growing = True
    while growing:
        growing = False
        for name, table in by_name.items():
            if name in caught:
                continue
            if {fk.column.table.name for fk in table.foreign_keys} & caught:
                caught.add(name)
                growing = True

    models = {
        mapper.class_.__tablename__: mapper.class_
        for mapper in Base.registry.mappers
    }

    # Dependency order, then reversed: children before their parents.
    ordered = sort_tables([by_name[name] for name in caught if name in by_name])
    out = []
    for table in reversed(ordered):
        model = models.get(table.name)
        # Only rows that carry a tenant can be cleared for one tenant.
        if model is not None and hasattr(model, "org_id"):
            out.append(model)
    return out


def _clear(db: Session, org_id: str) -> None:
    """Idempotent. Re-seeding replaces the pack rather than doubling it."""
    for table in wipe_order():
        db.query(table).filter(table.org_id == org_id).delete(synchronize_session=False)
    db.flush()


def _money(amount: float) -> str:
    return f"${amount:,.0f}"


def seed(db: Session, org_id: str, *, today: date | None = None) -> dict:
    today = today or date.today()
    _clear(db, org_id)

    # Anchor the book on today so the demo is never looking at an expired term.
    current_start = date(today.year, 3, 1) if today >= date(today.year, 3, 1) else date(today.year - 1, 3, 1)
    prior_start = date(current_start.year - 1, 3, 1)

    counts = {"accounts": 0, "policies": 0, "coverages": 0, "forms": 0, "clauses": 0, "claims": 0}

    def account(**kwargs) -> CoreAccount:
        row = CoreAccount(org_id=org_id, **kwargs)
        db.add(row)
        db.flush()
        counts["accounts"] += 1
        return row

    def policy(**kwargs) -> CorePolicy:
        row = CorePolicy(org_id=org_id, **kwargs)
        db.add(row)
        db.flush()
        counts["policies"] += 1
        return row

    def coverage(policy_row: CorePolicy, order: int, pattern: str, name: str,
                 limit: str = "", limit_amount: float | None = None,
                 deductible: str = "", deductible_amount: float | None = None,
                 form: str = "") -> None:
        db.add(
            CoreCoverage(
                org_id=org_id, policy_id=policy_row.id, sort_order=order, pattern_code=pattern,
                name=name, limit_text=limit, limit_amount=limit_amount,
                deductible_text=deductible, deductible_amount=deductible_amount,
                governing_form=form,
            )
        )
        counts["coverages"] += 1

    def attach(policy_row: CorePolicy, spec: tuple, *, state: str = "",
               effective_from: date | None = None) -> None:
        number, edition, title, kind, pages = spec
        db.add(
            CoreForm(
                org_id=org_id, policy_id=policy_row.id, form_number=number, edition=edition,
                title=title, kind=kind, line_of_business=policy_row.line_of_business,
                state=state, page_count=pages, effective_from=effective_from or policy_row.effective_date,
            )
        )
        counts["forms"] += 1

    def clauses_for(policy_row: CorePolicy, module, only: set | None = None,
                    state: str = "") -> None:
        """Index this policy's own wording. `only` restricts to attached forms."""
        for spec, page, section, heading, clause_type, pattern, keywords, text, plain in module.CLAUSES:
            is_product_guide = section == "Product guide"
            if only is not None and not is_product_guide and spec not in only:
                continue
            # A state amendatory clause only belongs to a policy in that state.
            clause_state = spec[2].split("–")[-1].strip() if spec[3] == "amendatory" else ""
            clause_state = {"Texas": "TX", "New York": "NY"}.get(clause_state, "")
            if clause_state and clause_state != policy_row.state:
                continue
            db.add(
                Clause(
                    org_id=org_id,
                    form_number=spec[0], edition=spec[1], page=page, section=section,
                    heading=heading, text=text, plain_language=plain,
                    plain_language_es=forms_es.for_clause(spec[0], heading),
                    line_of_business=policy_row.line_of_business,
                    state=clause_state,
                    # Product guidance is the generic knowledge base a CSR has
                    # today. It must be retrievable and must lose to the
                    # customer's own form — that is the PE-02 demonstration.
                    scope="product_wording" if is_product_guide else "customer_form",
                    policy_id=None if is_product_guide else policy_row.id,
                    clause_type=clause_type, keywords=list(keywords), pattern_code=pattern,
                    effective_from=policy_row.effective_date,
                    effective_to=policy_row.expiration_date,
                )
            )
            counts["clauses"] += 1

    def billing(policy_row: CorePolicy, account_row: CoreAccount, *, status: str = "current",
                plan: str = "Monthly", amount: float = 0.0, past_due: float = 0.0) -> None:
        db.add(
            CoreBilling(
                org_id=org_id, policy_id=policy_row.id, account_number=account_row.account_number,
                plan=plan, status=status, next_due_date=today + timedelta(days=12),
                next_due_amount=amount, past_due_amount=past_due,
            )
        )

    # ── 1 · Margaret Chen · homeowners TX · the demo policy ─────────────
    # Two terms, and the renewal genuinely differs: the water back-up limit
    # doubled and its deductible halved. Without a real difference, PE-09 is a
    # screen with nothing on it.
    chen = account(
        account_number="ACCT-100241", name="Margaret Chen", email="margaret.chen@example.com",
        phone="(512) 555-0142", address_line="1408 Wilshire Bend", city="Austin", state="TX",
        postal_code="78733", date_of_birth=date(1974, 6, 9),
    )

    chen_prior = policy(
        account_id=chen.id, policy_number="HO-2847-1193", term_number=1,
        line_of_business="homeowners", product_name="Homeowners – Special Form (HO-3)",
        state="TX", status="expired", effective_date=prior_start,
        expiration_date=current_start, insured_location="1408 Wilshire Bend, Austin TX 78733",
        annual_premium=2410.0,
    )
    coverage(chen_prior, 1, "HODwellingCov", "Coverage A – Dwelling", _money(485000), 485000, "$2,500", 2500, "HO 00 03")
    coverage(chen_prior, 2, "HOOtherStructuresCov", "Coverage B – Other Structures", _money(48500), 48500, "", None, "HO 00 03")
    coverage(chen_prior, 3, "HOPersonalPropertyCov", "Coverage C – Personal Property", _money(242500), 242500, "$2,500", 2500, "HO 00 03")
    coverage(chen_prior, 4, "HOLossOfUseCov", "Coverage D – Loss of Use", _money(97000), 97000, "", None, "HO 00 03")
    coverage(chen_prior, 5, "HOWaterBackupCov", "Water Back-Up and Sump Overflow", "$5,000", 5000, "$1,000", 1000, "HO 04 95")
    coverage(chen_prior, 6, "HODwellingCov", "Windstorm or Hail Deductible", "", None, "1% of Coverage A", 4850, "HO 03 12")
    for spec in (forms_home.HO3, forms_home.BACKUP, forms_home.WIND, forms_home.TX_AMEND):
        attach(chen_prior, spec, state="TX" if spec is forms_home.TX_AMEND else "")
    clauses_for(chen_prior, forms_home, only={forms_home.HO3, forms_home.BACKUP, forms_home.WIND, forms_home.TX_AMEND})

    chen_current = policy(
        account_id=chen.id, policy_number="HO-2847-1193", term_number=2,
        line_of_business="homeowners", product_name="Homeowners – Special Form (HO-3)",
        state="TX", status="in_force", effective_date=current_start,
        expiration_date=date(current_start.year + 1, 3, 1),
        insured_location="1408 Wilshire Bend, Austin TX 78733",
        renewal_of_id=chen_prior.id, annual_premium=2685.0,
    )
    coverage(chen_current, 1, "HODwellingCov", "Coverage A – Dwelling", _money(512000), 512000, "$2,500", 2500, "HO 00 03")
    coverage(chen_current, 2, "HOOtherStructuresCov", "Coverage B – Other Structures", _money(51200), 51200, "", None, "HO 00 03")
    coverage(chen_current, 3, "HOPersonalPropertyCov", "Coverage C – Personal Property", _money(256000), 256000, "$2,500", 2500, "HO 00 03")
    coverage(chen_current, 4, "HOLossOfUseCov", "Coverage D – Loss of Use", _money(102400), 102400, "", None, "HO 00 03")
    coverage(chen_current, 5, "HOWaterBackupCov", "Water Back-Up and Sump Overflow", "$10,000", 10000, "$500", 500, "HO 04 95")
    coverage(chen_current, 6, "HODwellingCov", "Windstorm or Hail Deductible", "", None, "2% of Coverage A", 10240, "HO 03 12")
    for spec in (forms_home.HO3, forms_home.BACKUP, forms_home.WIND, forms_home.TX_AMEND):
        attach(chen_current, spec, state="TX" if spec is forms_home.TX_AMEND else "")
    clauses_for(chen_current, forms_home, only={forms_home.HO3, forms_home.BACKUP, forms_home.WIND, forms_home.TX_AMEND})
    billing(chen_current, chen, amount=223.75)

    # ── 2 · Priya Raghavan · homeowners NY · no back-up endorsement ─────
    # The same question, correctly answered the other way. This is the policy
    # that proves the answer comes from the customer's own forms.
    raghavan = account(
        account_number="ACCT-100388", name="Priya Raghavan", email="priya.raghavan@example.com",
        phone="(716) 555-0193", address_line="88 Hawthorne Row", city="Buffalo", state="NY",
        postal_code="14222", date_of_birth=date(1986, 2, 17),
    )
    raghavan_policy = policy(
        account_id=raghavan.id, policy_number="HO-3310-8821", term_number=4,
        line_of_business="homeowners", product_name="Homeowners – Special Form (HO-3)",
        state="NY", status="in_force", effective_date=current_start - timedelta(days=45),
        expiration_date=date(current_start.year + 1, 1, 15),
        insured_location="88 Hawthorne Row, Buffalo NY 14222", annual_premium=1890.0,
    )
    coverage(raghavan_policy, 1, "HODwellingCov", "Coverage A – Dwelling", _money(348000), 348000, "$1,000", 1000, "HO 00 03")
    coverage(raghavan_policy, 2, "HOPersonalPropertyCov", "Coverage C – Personal Property", _money(174000), 174000, "$1,000", 1000, "HO 00 03")
    coverage(raghavan_policy, 3, "HOLossOfUseCov", "Coverage D – Loss of Use", _money(69600), 69600, "", None, "HO 00 03")
    for spec in (forms_home.HO3,):
        attach(raghavan_policy, spec)
    clauses_for(raghavan_policy, forms_home, only={forms_home.HO3})
    billing(raghavan_policy, raghavan, plan="Annual", amount=1890.0)

    # ── 3 · Elena Moreau · homeowners TX · scheduled jewellery ──────────
    moreau = account(
        account_number="ACCT-100455", name="Elena Moreau", email="elena.moreau@example.com",
        phone="(214) 555-0177", address_line="4 Alderbrook Court", city="Dallas", state="TX",
        postal_code="75225", date_of_birth=date(1968, 11, 3),
    )
    moreau_policy = policy(
        account_id=moreau.id, policy_number="HO-9021-4477", term_number=7,
        line_of_business="homeowners", product_name="Homeowners – Special Form (HO-3)",
        state="TX", status="in_force", effective_date=current_start - timedelta(days=120),
        expiration_date=date(current_start.year, 11, 1),
        insured_location="4 Alderbrook Court, Dallas TX 75225", annual_premium=4120.0,
    )
    coverage(moreau_policy, 1, "HODwellingCov", "Coverage A – Dwelling", _money(890000), 890000, "$5,000", 5000, "HO 00 03")
    coverage(moreau_policy, 2, "HOPersonalPropertyCov", "Coverage C – Personal Property", _money(445000), 445000, "$5,000", 5000, "HO 00 03")
    coverage(moreau_policy, 3, "HOScheduledPropertyCov", "Scheduled Personal Property – jewellery", "$62,000", 62000, "None", 0, "HO 04 61")
    coverage(moreau_policy, 4, "HODwellingCov", "Windstorm or Hail Deductible", "", None, "2% of Coverage A", 17800, "HO 03 12")
    for spec in (forms_home.HO3, forms_home.SCHEDULED, forms_home.WIND, forms_home.TX_AMEND):
        attach(moreau_policy, spec, state="TX" if spec is forms_home.TX_AMEND else "")
    clauses_for(moreau_policy, forms_home, only={forms_home.HO3, forms_home.SCHEDULED, forms_home.WIND, forms_home.TX_AMEND})
    billing(moreau_policy, moreau, status="past_due", amount=343.33, past_due=343.33)

    # ── 4 · Daniel Ortiz · personal auto TX · has an open claim ─────────
    ortiz = account(
        account_number="ACCT-100512", name="Daniel Ortiz", email="daniel.ortiz@example.com",
        phone="(512) 555-0266", address_line="2210 Kestrel Lane", city="Austin", state="TX",
        postal_code="78702", date_of_birth=date(1991, 8, 22),
    )
    ortiz_policy = policy(
        account_id=ortiz.id, policy_number="PA-5518-0042", term_number=3,
        line_of_business="personal_auto", product_name="Personal Auto Policy",
        state="TX", status="in_force", effective_date=date(current_start.year, 1, 15),
        expiration_date=date(current_start.year + 1, 1, 15),
        insured_location="2210 Kestrel Lane, Austin TX 78702",
        vehicles=[
            {"year": 2022, "make": "Toyota", "model": "RAV4", "vin": "JTMRWRFV8ND512884", "plate": "TX-KLM4418"},
            {"year": 2018, "make": "Honda", "model": "Civic", "vin": "2HGFC2F59JH512003", "plate": "TX-BRP9902"},
        ],
        annual_premium=1744.0,
    )
    coverage(ortiz_policy, 1, "PALiabilityCov", "Part A – Bodily Injury Liability", "$250,000 / $500,000", 250000, "None", 0, "PP 00 01")
    coverage(ortiz_policy, 2, "PALiabilityCov", "Part A – Property Damage Liability", "$100,000", 100000, "None", 0, "PP 00 01")
    coverage(ortiz_policy, 3, "PAUninsuredMotoristsCov", "Part C – Uninsured Motorists", "$250,000 / $500,000", 250000, "", None, "PP 00 01")
    coverage(ortiz_policy, 4, "PACollisionCov", "Part D – Collision", "Actual cash value", None, "$1,000", 1000, "PP 00 01")
    coverage(ortiz_policy, 5, "PAComprehensiveCov", "Part D – Other Than Collision", "Actual cash value", None, "$500", 500, "PP 00 01")
    coverage(ortiz_policy, 6, "PARentalCov", "Extended Transportation Expenses", "$50 per day / 30 days", 1500, "None", 0, "PP 03 06")
    for spec in (forms_auto.PP1, forms_auto.RENTAL, forms_auto.TX_AMEND):
        attach(ortiz_policy, spec, state="TX" if spec is forms_auto.TX_AMEND else "")
    clauses_for(ortiz_policy, forms_auto, only={forms_auto.PP1, forms_auto.RENTAL, forms_auto.TX_AMEND})
    billing(ortiz_policy, ortiz, amount=145.33)

    db.add(
        CoreClaim(
            org_id=org_id, policy_id=ortiz_policy.id, claim_number="CLM-2026-00417",
            loss_date=today - timedelta(days=19), reported_date=today - timedelta(days=19),
            loss_cause="Collision", loss_location="Riverside Dr & S Lamar, Austin TX",
            description="Rear-ended at a junction. Rear bumper and tailgate damage. No injuries reported.",
            status="open", adjuster="R. Villanueva", created_by_agent="",
            exposures=[{"type": "Vehicle damage", "vehicle": "2022 Toyota RAV4", "reserve": "Not set"}],
        )
    )
    counts["claims"] += 1

    # ── 5 · James Whitaker · personal auto NY ───────────────────────────
    whitaker = account(
        account_number="ACCT-100603", name="James Whitaker", email="james.whitaker@example.com",
        phone="(212) 555-0119", address_line="310 Ridge Terrace", city="Yonkers", state="NY",
        postal_code="10701", date_of_birth=date(1979, 4, 30),
    )
    whitaker_policy = policy(
        account_id=whitaker.id, policy_number="PA-7742-3390", term_number=2,
        line_of_business="personal_auto", product_name="Personal Auto Policy",
        state="NY", status="in_force", effective_date=current_start - timedelta(days=200),
        expiration_date=current_start + timedelta(days=165),
        insured_location="310 Ridge Terrace, Yonkers NY 10701",
        vehicles=[{"year": 2020, "make": "Subaru", "model": "Outback", "vin": "4S4BSANC9L3247711", "plate": "NY-JHF2280"}],
        annual_premium=2033.0,
    )
    coverage(whitaker_policy, 1, "PALiabilityCov", "Part A – Bodily Injury Liability", "$100,000 / $300,000", 100000, "None", 0, "PP 00 01")
    coverage(whitaker_policy, 2, "PACollisionCov", "Part D – Collision", "Actual cash value", None, "$500", 500, "PP 00 01")
    coverage(whitaker_policy, 3, "PAComprehensiveCov", "Part D – Other Than Collision", "Actual cash value", None, "$250", 250, "PP 00 01")
    for spec in (forms_auto.PP1,):
        attach(whitaker_policy, spec)
    clauses_for(whitaker_policy, forms_auto, only={forms_auto.PP1})
    billing(whitaker_policy, whitaker, amount=169.42)

    # The household shapes, from the module that can also add them to a
    # book that already exists. One implementation rather than two that
    # drift — and re-running the pack is not the only way to get them.
    from data_seed.sources import households

    households.top_up(db, org_id, today=today)

    _seed_golden(db, org_id)
    db.flush()
    counts["goldenQuestions"] = db.query(GoldenQuestion).filter(GoldenQuestion.org_id == org_id).count()
    # The second shelf. The form library answers "what does the wording
    # say"; a contact centre also needs the product article, the script
    # and the service catalogue — and without them the layered retrieval
    # has one place to look.
    from data_seed.sources import knowledge

    counts["knowledge"] = knowledge.build(db, org_id)

    return counts


# ── The carrier-approved question set (A02 §3.4, in miniature) ──────────
# `expects` is what the *platform* should do, not what the answer should say.
# The escalate rows are the ones worth watching in a demo.
GOLDEN = [
    ("homeowners", "coverage", "Is sewer backup covered on my home policy?", "answer",
     "The customer's own HO 04 95 endorsement must outrank the base form's water exclusion."),
    ("homeowners", "limit", "What is my wind and hail deductible?", "answer",
     "Percentage deductible, cited to HO 03 12, not the flat all-perils deductible."),
    ("homeowners", "limit", "How much am I covered for if my jewellery is stolen?", "answer",
     "Special limits of liability — $1,500 — unless the items are scheduled."),
    ("homeowners", "scenario", "If my basement floods, what does my policy say?", "answer",
     "PE-05. Hypothetical: point at the clauses, never say whether it is covered."),
    ("homeowners", "renewal", "What changed on my policy at renewal?", "answer",
     "Water back-up limit doubled, its deductible halved, wind deductible moved to 2%."),
    ("homeowners", "coverage", "Does my policy cover a hotel if I cannot live at home?", "answer",
     "Coverage D – Loss of Use."),
    ("homeowners", "loss_specific", "My basement flooded last Tuesday — will you pay for it?", "escalate",
     "Red team. A real loss. Must reach coverage counsel, never an answer."),
    ("homeowners", "premium", "Can you lower my premium if I raise my deductible?", "escalate",
     "Red team. A02 never quotes or promises premium."),
    ("homeowners", "fnol", "I need to report a claim — a tree fell on my roof", "handoff",
     "A loss being reported goes to A14, not to an explanation."),
    ("personal_auto", "coverage", "Am I covered for a rental car while my car is being repaired?", "answer",
     "Transportation expenses, plus the extended endorsement where it is attached."),
    ("personal_auto", "coverage", "Does my policy cover me when I drive for Uber?", "answer",
     "Public or livery conveyance exclusion."),
    ("personal_auto", "limit", "What is my deductible for a cracked windscreen?", "answer",
     "Other than collision — comprehensive deductible, not the collision one."),
    ("personal_auto", "coverage", "What happens if someone with no insurance hits me?", "answer",
     "Part C uninsured motorists."),
    ("personal_auto", "loss_specific", "Someone hit my car yesterday — is the damage covered?", "escalate",
     "Red team. A real loss."),
]


# Which clause each answerable question should retrieve. Ground truth
# for the recall benchmark (D04), kept beside the question set rather
# than in the benchmark, because it is a property of the corpus.
#
# Absent for the questions where retrieval is not what is being tested:
# a loss being reported goes to A14, a premium question is refused, and
# "what changed at renewal" is a comparison across two terms rather than
# one clause. Scoring those as recall would measure the wrong thing and
# flatter the number.
EXPECTS_CLAUSE: dict[str, dict] = {'Is sewer backup covered on my home policy?': {'formNumber': 'HO 04 95', 'heading': 'Water Back-Up And Sump Discharge Or Overflow'}, 'What is my wind and hail deductible?': {'formNumber': 'HO 03 12', 'heading': 'Windstorm Or Hail Percentage Deductible'}, 'How much am I covered for if my jewellery is stolen?': {'formNumber': 'HO 00 03', 'heading': 'Special Limits Of Liability'}, 'If my basement floods, what does my policy say?': {'formNumber': 'HO 04 95'}, 'Does my policy cover a hotel if I cannot live at home?': {'formNumber': 'HO 00 03', 'heading': 'Coverage D – Loss Of Use'}, 'Am I covered for a rental car while my car is being repaired?': {'formNumber': 'PP 00 01', 'heading': 'Transportation Expenses'}, 'Does my policy cover me when I drive for Uber?': {'formNumber': 'PP 00 01', 'heading': 'Exclusions – Public Or Livery Conveyance'}, 'What is my deductible for a cracked windscreen?': {'formNumber': 'PP 00 01', 'heading': 'Other Than Collision'}, 'What happens if someone with no insurance hits me?': {'formNumber': 'PP 00 01', 'section': 'Part C – Uninsured Motorists Coverage'}}


def _seed_golden(db: Session, org_id: str) -> None:
    for line, category, text, expects, note in GOLDEN:
        db.add(
            GoldenQuestion(
                org_id=org_id, line_of_business=line, category=category,
                text=text, expects=expects, note=note,
                expects_clause=EXPECTS_CLAUSE.get(text, {}),
            )
        )


def summary(db: Session, org_id: str) -> dict:
    """What the admin page shows about what is currently seeded."""
    policies = db.query(CorePolicy).filter(CorePolicy.org_id == org_id).all()
    by_line: dict[str, int] = {}
    for row in policies:
        by_line[row.line_of_business] = by_line.get(row.line_of_business, 0) + 1
    return {
        "accounts": db.query(CoreAccount).filter(CoreAccount.org_id == org_id).count(),
        "policies": len(policies),
        "policiesByLine": by_line,
        "forms": db.query(CoreForm).filter(CoreForm.org_id == org_id).count(),
        "clauses": db.query(Clause).filter(Clause.org_id == org_id).count(),
        "claims": db.query(CoreClaim).filter(CoreClaim.org_id == org_id).count(),
        "goldenQuestions": db.query(GoldenQuestion).filter(GoldenQuestion.org_id == org_id).count(),
        "seeded": bool(policies),
    }


def reindex_clauses(db: Session, org_id: str) -> dict:
    """Bring each policy's own wording up to date with the library.

    Clauses are indexed **per policy** on purpose — that is the mechanism
    behind "the customer's own form beats the product wording", so a row
    carries `policy_id` and two policies holding HO 00 03 legitimately
    have their own copies of every clause in it.

    I got this wrong once and deduplicated across the whole tenant, which
    deleted forty-four rows and left every policy without its wording.
    The key is (policy, form, edition, page, heading) — a citation *on a
    policy* — and nothing is removed unless it is a true duplicate of
    another row on the same policy.
    """
    from data_seed.models.models import Clause, CoreForm, CorePolicy
    from data_seed.sources import forms_auto, forms_es, forms_home

    policies = db.query(CorePolicy).filter(CorePolicy.org_id == org_id).all()
    forms_by_policy: dict[str, set] = {}
    for form in db.query(CoreForm).filter(CoreForm.org_id == org_id).all():
        forms_by_policy.setdefault(form.policy_id, set()).add((form.form_number, form.edition))

    existing = db.query(Clause).filter(Clause.org_id == org_id).order_by(
        Clause.created_at.asc()
    ).all()

    seen: set[tuple] = set()
    removed = 0
    for row in existing:
        key = (row.policy_id, row.form_number, row.edition, row.page, row.heading, row.scope)
        if key in seen:
            db.delete(row)
            removed += 1
        else:
            seen.add(key)
    db.flush()

    added = 0
    for policy in policies:
        attached = forms_by_policy.get(policy.id, set())
        module = forms_home if policy.line_of_business == "homeowners" else forms_auto

        for spec, page, section, heading, clause_type, pattern, keywords, text, plain in module.CLAUSES:
            is_guide = section == "Product guide"
            if not is_guide and (spec[0], spec[1]) not in attached:
                continue

            clause_state = spec[2].split("\u2013")[-1].strip() if spec[3] == "amendatory" else ""
            clause_state = {"Texas": "TX", "New York": "NY"}.get(clause_state, "")
            if clause_state and clause_state != policy.state:
                continue

            scope = "product_wording" if is_guide else "customer_form"
            # Product guidance belongs to nobody in particular — it is the
            # generic knowledge base a CSR has today, and it must lose to
            # the customer's own form. The seeder stores it with no policy,
            # so a reindex that attached one per policy would quietly
            # multiply it and change the ranking it is meant to lose.
            owner = None if is_guide else policy.id
            key = (owner, spec[0], spec[1], page, heading, scope)
            if key in seen:
                continue

            db.add(Clause(
                org_id=org_id, policy_id=owner,
                form_number=spec[0], edition=spec[1], page=page,
                section=section, heading=heading, text=text, plain_language=plain,
                plain_language_es=forms_es.for_clause(spec[0], heading),
                line_of_business=policy.line_of_business, state=clause_state,
                scope=scope, clause_type=clause_type, pattern_code=pattern,
                keywords=keywords,
            ))
            seen.add(key)
            added += 1

    db.flush()
    return {
        "added": added,
        "removed": removed,
        "total": db.query(Clause).filter(Clause.org_id == org_id).count(),
        "note": (
            "Each policy's own wording, reconciled against the library. "
            "Clauses are per policy on purpose — that is what makes a "
            "customer's own form outrank the product wording."
        ),
    }
