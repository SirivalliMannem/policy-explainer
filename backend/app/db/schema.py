"""Metadata Alembic manages for the shared Policy Explainer database.

Seed models own the carrier tables. Conversation, question, and evidence-ledger
models own the application tables. The backend also maps the carrier tables for
reads; those mappings are thinner than the seed models and are not migrated.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import MetaData

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

APP_TABLES = ("conversation", "conversation_question", "evidence_ledger")


def _prepare_paths() -> None:
    """Make ``app`` and ``data_seed`` importable from the API, seed runner, and Alembic CLI."""
    for entry in (BACKEND_DIR, REPO_ROOT):
        path = str(entry)
        if path not in sys.path:
            sys.path.insert(0, path)


def managed_metadata() -> MetaData:
    """Return one metadata object containing every table Alembic should version."""
    _prepare_paths()

    from data_seed.database import Base as SeedBase
    from data_seed.models import models as _seed_models  # noqa: F401
    import app.models.conversation as _conversation  # noqa: F401
    import app.models.ledger as _ledger  # noqa: F401
    from app.db.database import Base as AppBase

    metadata = MetaData()
    for table in SeedBase.metadata.sorted_tables:
        if table.name not in metadata.tables:
            table.to_metadata(metadata)
    for name in APP_TABLES:
        table = AppBase.metadata.tables[name]
        if table.name not in metadata.tables:
            table.to_metadata(metadata)
    return metadata
