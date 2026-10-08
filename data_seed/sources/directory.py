"""A team to demonstrate the hierarchy with.

RBAC is unshowable with one user. The claim — *a manager sees their reports
and their reports' reports; a peer sees neither* — needs three levels and
two sibling teams before it can be seen to be true rather than asserted.

So the shape is chosen to make every rule falsifiable on screen:

- two claims teams that are **siblings**, which is the case that proves
  peers are blind to each other;
- a director above both, which proves the subtree rule;
- a compliance officer sitting **outside** the tree entirely, which proves
  that tenant-wide reach comes from the role and not from a position.

Nothing here sends email, by any path. Fifteen invitations arriving in a
real inbox during a demo is a mistake that cannot be taken back, so seeded
members carry `notify=False` and the directory has no send at all.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import TenantMember

# The customer's own address sits at the top; everyone below uses
# plus-addressing on one real mailbox, so the whole tree is deliverable in
# principle and distinct in practice — while we still send nothing.
TOP_EMAIL = "sumitju03203@gmail.com"


def _at(index: int) -> str:
    return "sbhowmick@conimble.com" if index == 0 else f"sbhowmick+{index}@conimble.com"


# (key, name, title, role, team, manager key)
PEOPLE: list[tuple[str, str, str, str, str, str | None]] = [
    # A Director of Claims Operations, which is a claims_manager: the tree
    # needs somebody holding that role or the authority rules have nobody
    # to escalate to. The account owner being locked out of tenant admin
    # was a separate bug, fixed where it belonged — an IAM administrator
    # now keeps the run of their own tenant whatever the directory says.
    ("director",   "Priya Raghunathan", "Director, Claims Operations", "claims_manager", "Claims", None),
    ("lead_north", "Marcus Bell",       "Team Lead, Claims North",     "team_lead",      "Claims North", "director"),
    ("lead_south", "Dana Whitfield",    "Team Lead, Claims South",     "team_lead",      "Claims South", "director"),

    # Claims North — four adjusters under Marcus.
    ("adj_n1", "Alina Kovacs",   "Claims Adjuster",        "adjuster", "Claims North", "lead_north"),
    ("adj_n2", "Tomas Brennan",  "Claims Adjuster",        "adjuster", "Claims North", "lead_north"),
    ("adj_n3", "Renee Okafor",   "Senior Claims Adjuster", "adjuster", "Claims North", "lead_north"),
    ("csr_n1", "Bea Lindqvist",  "Customer Service Rep",   "csr",      "Claims North", "lead_north"),

    # Claims South — the sibling team. Nobody here may see anybody above.
    ("adj_s1", "Hugo Martins",   "Claims Adjuster",        "adjuster", "Claims South", "lead_south"),
    ("adj_s2", "Wen Li",         "Claims Adjuster",        "adjuster", "Claims South", "lead_south"),
    ("csr_s1", "Grace Adeyemi",  "Customer Service Rep",   "csr",      "Claims South", "lead_south"),
    ("csr_s2", "Ivan Petrov",    "Customer Service Rep",   "csr",      "Claims South", "lead_south"),

    # Quality reports to the director, so their coaching scope is the
    # claims organisation and not the whole carrier.
    ("quality", "Sofia Delgado", "Quality Lead", "quality_lead", "Quality", "director"),

    # Outside the claims line on purpose: their reach comes from the role.
    ("compliance", "Nadia Haddad", "Compliance Officer", "compliance_officer", "Compliance", None),
    ("counsel",    "Oliver Grant", "Coverage Counsel",   "coverage_counsel",   "Legal",      None),
    ("admin",      "Sam Ortiz",    "Platform Administrator", "tenant_admin",   "IT",         None),
]


def build(db: Session, org_id: str) -> dict:
    """Create the demonstration directory. Idempotent by email."""
    existing = {
        row.email: row
        for row in db.query(TenantMember).filter(TenantMember.org_id == org_id).all()
    }

    by_key: dict[str, TenantMember] = {}
    created = 0
    # The director takes the customer's own address; everyone else takes a
    # plus-address, counted separately so the plain `sbhowmick@conimble.com`
    # is actually used. Numbering by the list index skipped it.
    plus = 0

    # Two passes: everybody exists before any manager is pointed at.
    for key, name, title, role, team, _manager in PEOPLE:
        if key == "director":
            email = TOP_EMAIL
        else:
            email = _at(plus)
            plus += 1
        row = existing.get(email)
        if row is None:
            row = TenantMember(
                org_id=org_id, email=email, name=name, title=title,
                role=role, team=team, status="active", seeded=True, notify=False,
            )
            db.add(row)
            created += 1
        else:
            row.name, row.title, row.role, row.team = name, title, role, team
        by_key[key] = row
    db.flush()

    for key, _name, _title, _role, _team, manager in PEOPLE:
        by_key[key].manager_id = by_key[manager].id if manager else None
    db.flush()

    return {
        "created": created,
        "total": len(PEOPLE),
        "levels": 3,
        "top": TOP_EMAIL,
        "emailsSent": 0,
        "note": (
            "Two sibling claims teams under one director, plus compliance and "
            "coverage counsel outside the tree — so 'a peer sees nothing' and "
            "'tenant-wide comes from the role' can both be checked on screen. "
            "No email is sent to anyone."
        ),
    }
