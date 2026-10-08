"""Apply Alembic migrations to the configured database."""

from pathlib import Path

from alembic import command
from alembic.config import Config

BACKEND_DIR = Path(__file__).resolve().parents[2]


def run_migrations() -> None:
    """Upgrade the database to the latest Alembic revision."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")
