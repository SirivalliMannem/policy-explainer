"""Additive schema upgrades for application-owned tables.

The backend creates its own tables with ``create_all``, which never alters a table that already
exists. Columns added to those tables after a database was first created are applied here. Every
statement is additive and idempotent, and seeded core tables are never touched.
"""

from sqlalchemy import Engine, inspect, text

LEDGER_COLUMNS = {
    "employee_id": "VARCHAR(100)",
    "outcome": "VARCHAR(30)",
    "guardrail_checks": "JSON",
    "model_used": "VARCHAR(80)",
    "provider": "VARCHAR(30)",
    "is_fallback": "BOOLEAN",
    "fallback_reason": "TEXT",
    "latency_ms": "INTEGER",
    "timings_ms": "JSON",
    "retrieval": "JSON",
}


def ensure_ledger_columns(engine: Engine) -> list[str]:
    """Add any missing evidence_ledger audit columns. Returns the columns that were added."""
    inspector = inspect(engine)
    if "evidence_ledger" not in inspector.get_table_names():
        return []
    existing = {column["name"] for column in inspector.get_columns("evidence_ledger")}
    missing = [name for name in LEDGER_COLUMNS if name not in existing]
    if missing:
        with engine.begin() as conn:
            for name in missing:
                conn.execute(text(f"ALTER TABLE evidence_ledger ADD COLUMN {name} {LEDGER_COLUMNS[name]}"))
    return missing
