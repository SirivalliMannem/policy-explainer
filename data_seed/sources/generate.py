"""Adding to the synthetic book — with AI where a key is configured.

Two legs, the same shape as everything else in the service:

  with a key  gpt-4.1-mini invents the policyholders and the shape of their
              cover — names, addresses, limits, deductibles, the endorsements
              they bought — constrained to a JSON schema and to this tenant's
              existing form library.

  without     the same fields, varied deterministically from the seed
              templates. The demo does not depend on the network.

What the model is *not* allowed to invent is policy wording. New policies
attach forms that already exist in the tenant's library and reuse their
clauses. A generated form number would be a fabricated citation, which is the
one thing this whole system exists to prevent.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models.models import Clause, CoreAccount, CoreBilling, CoreCoverage, CoreForm, CorePolicy
from app.platform.llm import gateway
from app.seed import forms_auto, forms_home

GENERATE_SYSTEM = """You generate synthetic US property & casualty policyholders for a demo.
They must look like real carrier records and must not be real people.
Return ONLY JSON: {"policies":[{
 "insuredName":"","email":"","phone":"(xxx) xxx-xxxx","addressLine":"","city":"","postalCode":"",
 "dwellingLimit":0,"allPerilDeductible":0,"hasWaterBackup":true,"waterBackupLimit":0,
 "waterBackupDeductible":0,"windDeductiblePercent":0,
 "liabilityLimit":0,"collisionDeductible":0,"comprehensiveDeductible":0,
 "vehicle":{"year":0,"make":"","model":""},
 "annualPremium":0}]}
Use amounts that are plausible for the state given. Homeowners policies need the dwelling fields,
auto policies the liability and deductible fields."""

FIRST = ["Rosa", "Aaron", "Neha", "Marcus", "Lena", "Tomas", "Aisha", "Grant", "Yuki", "Devon",
         "Camille", "Ibrahim", "Sofia", "Wesley", "Nadia"]
LAST = ["Alvarez", "Bramley", "Castellanos", "Doyle", "Ferreira", "Hollis", "Iyer", "Keane",
        "Lindqvist", "Marchetti", "Novak", "Okafor", "Pemberton", "Rasmussen", "Teixeira"]
STREETS = ["Juniper Hollow", "Bellwood Rise", "Cypress Reach", "Marlowe Bend", "Tanner Ridge",
           "Ashgrove Lane", "Silverbrook Way", "Hallow Creek Road"]
CITIES = {
    "TX": [("Austin", "78704"), ("Dallas", "75206"), ("Houston", "77006"), ("San Antonio", "78209")],
    "NY": [("Buffalo", "14213"), ("Yonkers", "10704"), ("Rochester", "14607"), ("Albany", "12208")],
    "FL": [("Tampa", "33606"), ("Orlando", "32801"), ("Sarasota", "34236")],
    "CA": [("Pasadena", "91106"), ("Fresno", "93704"), ("Sacramento", "95818")],
}
MAKES = [("Toyota", "Camry"), ("Honda", "CR-V"), ("Ford", "F-150"), ("Subaru", "Forester"),
         ("Mazda", "CX-5"), ("Hyundai", "Tucson")]


def _fallback(line: str, state: str, count: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    cities = CITIES.get(state, CITIES["TX"])
    generated = []
    for _ in range(count):
        city, postal = rng.choice(cities)
        dwelling = rng.randrange(240, 920) * 1000
        entry = {
            "insuredName": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
            "addressLine": f"{rng.randrange(2, 4800)} {rng.choice(STREETS)}",
            "city": city,
            "postalCode": postal,
            "phone": f"({rng.randrange(200, 989)}) 555-{rng.randrange(1000, 9999)}",
            "annualPremium": 0,
        }
        entry["email"] = entry["insuredName"].lower().replace(" ", ".") + "@example.com"
        if line == "homeowners":
            entry |= {
                "dwellingLimit": dwelling,
                "allPerilDeductible": rng.choice([1000, 2500, 5000]),
                "hasWaterBackup": rng.random() > 0.45,
                "waterBackupLimit": rng.choice([5000, 10000, 25000]),
                "waterBackupDeductible": rng.choice([500, 1000]),
                "windDeductiblePercent": rng.choice([1, 2]) if state in ("TX", "FL") else 0,
                "annualPremium": round(dwelling * rng.uniform(0.0042, 0.0061), 2),
            }
        else:
            year, (make, model) = rng.randrange(2017, 2025), rng.choice(MAKES)
            entry |= {
                "liabilityLimit": rng.choice([100000, 250000, 300000]),
                "collisionDeductible": rng.choice([500, 1000]),
                "comprehensiveDeductible": rng.choice([250, 500]),
                "vehicle": {"year": year, "make": make, "model": model},
                "annualPremium": round(rng.uniform(1280, 2450), 2),
            }
        generated.append(entry)
    return generated


def generate(
    db: Session,
    *,
    org_id: str,
    line_of_business: str,
    state: str,
    count: int,
    notes: str = "",
    commit: bool = False,
) -> dict:
    seed_value = abs(hash(f"{org_id}{line_of_business}{state}{count}{notes}")) % (2**31)
    source = "deterministic"

    prompt = (
        f"Generate {count} {line_of_business.replace('_', ' ')} policyholders in {state}."
        + (f" Scenario notes from the carrier: {notes}" if notes else "")
    )
    parsed = gateway.extract_json(system=GENERATE_SYSTEM, prompt=prompt)
    rows = (parsed or {}).get("policies") if parsed else None
    if rows:
        source = gateway.model_name
        rows = rows[:count]
    else:
        rows = _fallback(line_of_business, state, count, seed_value)

    today = date.today()
    effective = today - timedelta(days=90)
    expiration = effective.replace(year=effective.year + 1)
    sequence = db.query(CorePolicy).filter(CorePolicy.org_id == org_id).count()

    preview = []
    for index, row in enumerate(rows):
        number = (
            f"{'HO' if line_of_business == 'homeowners' else 'PA'}-"
            f"{(seed_value + index) % 9000 + 1000}-{(sequence + index + 1) * 7 % 9000 + 1000}"
        )
        account = CoreAccount(
            org_id=org_id,
            account_number=f"ACCT-2{(sequence + index + 41):05d}",
            name=row.get("insuredName", "Generated Insured"),
            email=row.get("email", ""),
            phone=row.get("phone", ""),
            address_line=row.get("addressLine", ""),
            city=row.get("city", ""),
            state=state,
            postal_code=str(row.get("postalCode", "")),
        )
        db.add(account)
        db.flush()

        policy = CorePolicy(
            org_id=org_id, account_id=account.id, policy_number=number, term_number=1,
            line_of_business=line_of_business,
            product_name="Homeowners – Special Form (HO-3)" if line_of_business == "homeowners" else "Personal Auto Policy",
            state=state, status="in_force", effective_date=effective, expiration_date=expiration,
            insured_location=f"{row.get('addressLine', '')}, {row.get('city', '')} {state} {row.get('postalCode', '')}",
            vehicles=(
                [] if line_of_business == "homeowners"
                else [{
                    "year": (row.get("vehicle") or {}).get("year", 2021),
                    "make": (row.get("vehicle") or {}).get("make", "Toyota"),
                    "model": (row.get("vehicle") or {}).get("model", "Camry"),
                    "vin": f"GEN{(seed_value + index) % 10**14:014d}",
                    "plate": f"{state}-GEN{(index + 1) * 137 % 9000 + 1000}",
                }]
            ),
            annual_premium=float(row.get("annualPremium") or 0),
        )
        db.add(policy)
        db.flush()

        specs, coverages = _shape(line_of_business, row)
        for order, (pattern, name, limit, limit_amount, deductible, deductible_amount, form) in enumerate(coverages, 1):
            db.add(
                CoreCoverage(
                    org_id=org_id, policy_id=policy.id, sort_order=order, pattern_code=pattern,
                    name=name, limit_text=limit, limit_amount=limit_amount,
                    deductible_text=deductible, deductible_amount=deductible_amount,
                    governing_form=form,
                )
            )

        module = forms_home if line_of_business == "homeowners" else forms_auto
        for spec in specs:
            db.add(
                CoreForm(
                    org_id=org_id, policy_id=policy.id, form_number=spec[0], edition=spec[1],
                    title=spec[2], kind=spec[3], line_of_business=line_of_business,
                    page_count=spec[4], effective_from=effective,
                )
            )
        # Wording is never generated. The new policy is indexed against the
        # clauses the tenant's form library already holds.
        attached = set(specs)
        for spec, page, section, heading, clause_type, pattern, keywords, text, plain in module.CLAUSES:
            if spec not in attached or section == "Product guide":
                continue
            db.add(
                Clause(
                    org_id=org_id, form_number=spec[0], edition=spec[1], page=page, section=section,
                    heading=heading, text=text, plain_language=plain,
                    line_of_business=line_of_business, state="",
                    scope="customer_form", policy_id=policy.id, clause_type=clause_type,
                    keywords=list(keywords), pattern_code=pattern,
                    effective_from=effective, effective_to=expiration,
                )
            )

        db.add(
            CoreBilling(
                org_id=org_id, policy_id=policy.id, account_number=account.account_number,
                plan="Monthly", status="current", next_due_date=today + timedelta(days=20),
                next_due_amount=round(float(row.get("annualPremium") or 1200) / 12, 2),
            )
        )

        preview.append(
            {
                "policyNumber": number,
                "insuredName": account.name,
                "lineOfBusiness": line_of_business,
                "state": state,
                "location": f"{account.city}, {state}",
                "effectiveDate": effective.isoformat(),
                "coverages": [
                    {"name": name, "limit": limit, "deductible": deductible}
                    for _, name, limit, _, deductible, _, _ in coverages
                ],
                "forms": [f"{spec[0]} ({spec[1]})" for spec in specs],
                "annualPremium": policy.annual_premium,
            }
        )

    db.flush()
    return {
        "generated": len(preview),
        "committed": commit,
        "source": source,
        "prompt": prompt,
        "preview": preview,
        "note": (
            "Wording is never generated. Each policy attaches forms already in your library and "
            "reuses their clauses, so every citation stays real."
        ),
    }


def _shape(line: str, row: dict) -> tuple[list, list]:
    """Which forms get attached, and what the dec page says."""
    def money(amount) -> str:
        try:
            return f"${float(amount):,.0f}"
        except (TypeError, ValueError):
            return "—"

    if line == "homeowners":
        dwelling = float(row.get("dwellingLimit") or 350000)
        deductible = float(row.get("allPerilDeductible") or 1000)
        specs = [forms_home.HO3]
        coverages = [
            ("HODwellingCov", "Coverage A – Dwelling", money(dwelling), dwelling, money(deductible), deductible, "HO 00 03"),
            ("HOPersonalPropertyCov", "Coverage C – Personal Property", money(dwelling * 0.5), dwelling * 0.5, money(deductible), deductible, "HO 00 03"),
            ("HOLossOfUseCov", "Coverage D – Loss of Use", money(dwelling * 0.2), dwelling * 0.2, "", None, "HO 00 03"),
        ]
        if row.get("hasWaterBackup"):
            specs.append(forms_home.BACKUP)
            backup_limit = float(row.get("waterBackupLimit") or 10000)
            backup_deductible = float(row.get("waterBackupDeductible") or 500)
            coverages.append((
                "HOWaterBackupCov", "Water Back-Up and Sump Overflow", money(backup_limit),
                backup_limit, money(backup_deductible), backup_deductible, "HO 04 95",
            ))
        percent = float(row.get("windDeductiblePercent") or 0)
        if percent:
            specs.append(forms_home.WIND)
            coverages.append((
                "HODwellingCov", "Windstorm or Hail Deductible", "", None,
                f"{percent:g}% of Coverage A", dwelling * percent / 100, "HO 03 12",
            ))
        return specs, coverages

    liability = float(row.get("liabilityLimit") or 100000)
    collision = float(row.get("collisionDeductible") or 500)
    comprehensive = float(row.get("comprehensiveDeductible") or 250)
    return [forms_auto.PP1], [
        ("PALiabilityCov", "Part A – Bodily Injury Liability", f"{money(liability)} / {money(liability * 2)}", liability, "None", 0, "PP 00 01"),
        ("PACollisionCov", "Part D – Collision", "Actual cash value", None, money(collision), collision, "PP 00 01"),
        ("PAComprehensiveCov", "Part D – Other Than Collision", "Actual cash value", None, money(comprehensive), comprehensive, "PP 00 01"),
    ]


__all__ = ["generate"]
