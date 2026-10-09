"""Alembic environment for the Policy Explainer database."""

from __future__ import annotations

import logging
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
for entry in (BACKEND_DIR, REPO_ROOT):
    path = str(entry)
    if path not in sys.path:
        sys.path.insert(0, path)

from app.core.config import settings
from app.db.schema import managed_metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

if config.config_file_name is not None and not logging.getLogger().handlers:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = managed_metadata()
MANAGED_TABLES = set(target_metadata.tables)


def include_object(object, name, type_, reflected, compare_to) -> bool:
    """Keep autogenerate on the tables this project versions."""
    if type_ == "table":
        return name in MANAGED_TABLES
    table = getattr(object, "table", None)
    if table is not None and getattr(table, "name", None) not in MANAGED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
