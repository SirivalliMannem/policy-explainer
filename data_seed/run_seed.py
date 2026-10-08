"""Synthetic data seed runner for Policy Explainer.

Executes pack.seed() against the application's PostgreSQL database using
the designated seed organization identifier.
"""

from __future__ import annotations

import sys
from pathlib import Path

from data_seed.database import SessionLocal
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
    print(f"Applying database migrations for org_id='{org_id}'...")
    _apply_migrations()

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


def _apply_migrations() -> None:
    """Upgrade the shared database before inserting seed rows."""
    backend_dir = Path(__file__).resolve().parents[1] / "backend"
    backend_path = str(backend_dir)
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from app.db.migrate import run_migrations

    run_migrations()


def main():
    """Main entry point. Kept for manual execution when database is ready."""
    try:
        run_seed()
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
