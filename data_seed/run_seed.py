"""Synthetic data seed runner for Policy Explainer.

Executes pack.seed() against the application's PostgreSQL database using
the designated seed organization identifier.
"""

from __future__ import annotations

import sys
from data_seed.database import Base, SessionLocal, engine
from data_seed.models.models import (
    Clause,
    CoreAccount,
    CoreBilling,
    CoreClaim,
    CoreCoverage,
    CoreForm,
    CorePolicy,
    GoldenQuestion,
    KnowledgeCollection,
    KnowledgeDocument,
)
from data_seed.sources import pack

# Standalone organization identifier for synthetic demo data
ORG_ID = "ORG-POLICY-EXPLAINER"


def run_seed(org_id: str = ORG_ID) -> dict:
    """Execute synthetic demo pack seeding.

    Args:
        org_id: Organization identifier for tenant-scoped seed data.

    Returns:
        dict: Seeding counts and metrics summary.
    """
    print(f"Creating required tables for org_id='{org_id}'...")
    Base.metadata.create_all(bind=engine)

    print(f"Starting seed process for org_id='{org_id}'...")
    db = SessionLocal()
    try:
        counts = pack.seed(db, org_id)
        db.commit()
        print("Seed completed successfully!")
        for key, val in counts.items():
            print(f"  - {key}: {val}")
        return counts
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}", file=sys.stderr)
        raise
    finally:
        db.close()


def main():
    """Main entry point. Kept for manual execution when database is ready."""
    try:
        run_seed()
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
