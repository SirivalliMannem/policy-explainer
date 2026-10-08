"""Baseline schema for carrier data and application tables.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-08

Creates any missing table from the current models, then brings databases that
were previously built with ``create_all`` up to those models. That older path
never altered an existing table, so columns, indexes, and nullability could
lag behind the models. This revision only adds or relaxes; it does not drop
columns, tables, or constraints.

Fresh databases and already-seeded databases both converge here. Later schema
changes belong in new revisions (``alembic revision --autogenerate``).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.schema import managed_metadata

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger("alembic.runtime.migration")


def upgrade() -> None:
    bind = op.get_bind()
    metadata = managed_metadata()
    metadata.create_all(bind=bind)
    inspector = sa.inspect(bind)
    for table in metadata.sorted_tables:
        if table.name not in set(inspector.get_table_names()):
            continue
        _align_table(bind, inspector, table)


def downgrade() -> None:
    """Drop every table this project versions. Carrier and application rows go with them."""
    managed_metadata().drop_all(bind=op.get_bind())


def _align_table(bind, inspector, table: sa.Table) -> None:
    existing_columns = {column["name"]: column for column in inspector.get_columns(table.name)}
    row_count = _row_count(bind, table.name) if _needs_row_count(table, existing_columns) else 0

    for column in table.columns:
        current = existing_columns.get(column.name)
        if current is None:
            if column.primary_key:
                raise RuntimeError(f"Refusing to add primary key {table.name}.{column.name} in place")
            _add_column(table, column, row_count)
        else:
            _align_nullability(table, column, current)

    _align_indexes(inspector, table)
    _align_foreign_keys(inspector, table)


def _needs_row_count(table: sa.Table, existing_columns: dict) -> bool:
    for column in table.columns:
        current = existing_columns.get(column.name)
        if current is None and not column.nullable:
            return True
        if current is not None and not column.nullable and current["nullable"]:
            return True
    return False


def _add_column(table: sa.Table, column: sa.Column, row_count: int) -> None:
    server_default = None
    drop_default = False
    if row_count and not column.nullable:
        literal = _sql_default(column)
        if literal is None:
            raise RuntimeError(
                f"Cannot add NOT NULL column {table.name}.{column.name} without a default"
            )
        server_default = sa.text(literal)
        drop_default = column.server_default is None
    op.add_column(
        table.name,
        sa.Column(column.name, column.type, nullable=column.nullable, server_default=server_default),
    )
    if drop_default:
        op.alter_column(table.name, column.name, server_default=None)
    log.info("Added column %s.%s", table.name, column.name)


def _align_nullability(table: sa.Table, column: sa.Column, current: dict) -> None:
    if column.nullable == current["nullable"]:
        return
    if not column.nullable:
        literal = _sql_default(column)
        if literal is None:
            raise RuntimeError(f"Cannot set {table.name}.{column.name} NOT NULL without a default")
        op.execute(
            sa.text(
                f'UPDATE {_q(table.name)} SET {_q(column.name)} = {literal} '
                f'WHERE {_q(column.name)} IS NULL'
            )
        )
    op.alter_column(table.name, column.name, existing_type=column.type, nullable=column.nullable)
    log.info("Set %s.%s nullable=%s", table.name, column.name, column.nullable)


def _align_indexes(inspector, table: sa.Table) -> None:
    existing = inspector.get_indexes(table.name)
    by_columns = {tuple(index["column_names"]): index for index in existing}
    names = {index["name"] for index in existing}
    for index in table.indexes:
        columns = tuple(col.name for col in index.columns)
        if not columns or not index.name:
            continue
        current = by_columns.get(columns)
        if current is not None:
            if current["name"] != index.name:
                op.execute(sa.text(f'ALTER INDEX {_q(current["name"])} RENAME TO {_q(index.name)}'))
                log.info("Renamed index %s to %s", current["name"], index.name)
            continue
        if index.name in names:
            continue
        op.create_index(index.name, table.name, list(columns), unique=bool(index.unique))
        log.info("Created index %s", index.name)


def _align_foreign_keys(inspector, table: sa.Table) -> None:
    existing = {tuple(fk["constrained_columns"]): fk for fk in inspector.get_foreign_keys(table.name)}
    for constraint in table.foreign_key_constraints:
        columns = tuple(col.name for col in constraint.columns)
        if columns in existing or not constraint.elements:
            continue
        referred = constraint.elements[0].column.table.name
        op.create_foreign_key(
            constraint.name,
            table.name,
            referred,
            list(columns),
            [element.column.name for element in constraint.elements],
        )
        log.info("Created foreign key on %s.%s", table.name, ", ".join(columns))


def _row_count(bind, table_name: str) -> int:
    return int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {_q(table_name)}")).scalar_one())


def _sql_default(column: sa.Column) -> str | None:
    default = column.default
    arg = getattr(default, "arg", None)
    if isinstance(arg, bool):
        return "true" if arg else "false"
    if isinstance(arg, int):
        return str(arg)
    if isinstance(arg, float):
        return repr(arg)
    if isinstance(arg, str):
        return "'" + arg.replace("'", "''") + "'"
    if arg is list or arg == []:
        return "'[]'::json"
    if arg is dict or arg == {}:
        return "'{}'::json"
    if callable(arg):
        visit = type(column.type).__visit_name__
        if visit == "JSON":
            return "'{}'::json" if arg is dict else "'[]'::json"
        if visit == "datetime":
            return "CURRENT_TIMESTAMP"
        if visit == "date":
            return "CURRENT_DATE"
    visit = type(column.type).__visit_name__
    fallback = {
        "datetime": "CURRENT_TIMESTAMP",
        "date": "CURRENT_DATE",
        "boolean": "false",
        "integer": "0",
        "float": "0",
        "string": "''",
        "text": "''",
        "JSON": "'[]'::json",
    }
    return fallback.get(visit)


def _q(name: str) -> str:
    if not name.replace("_", "").isalnum():
        raise RuntimeError(f"Unexpected SQL identifier: {name}")
    return f'"{name}"'
