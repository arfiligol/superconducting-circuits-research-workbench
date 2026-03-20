"""Database engine and session management."""

import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

# Database file location
DATABASE_PATH = Path(__file__).resolve().parents[3] / "data" / "database.db"


def resolve_database_path() -> Path:
    """Resolve the metadata DB path with optional environment override."""
    override = os.getenv("SC_DATABASE_PATH")
    if override is None or not override.strip():
        return DATABASE_PATH
    return Path(override).expanduser()


@lru_cache
def get_engine():
    """Get the SQLite engine (singleton)."""
    database_path = resolve_database_path()
    # Ensure parent directory exists
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{database_path}", echo=False)


def get_session() -> Session:
    """Create a new database session."""
    return Session(get_engine())


def init_db() -> None:
    """Initialize the database (create tables if not exist)."""
    from sqlmodel import SQLModel

    from core.shared.persistence.models import (  # noqa: F401 - Import for side effects
        AuditLogRecord,
        DataRecord,
        DatasetRecord,
        DatasetTagLink,
        DerivedParameter,
        ParameterDesignation,
        ResultBundleDataLink,
        ResultBundleRecord,
        Tag,
        TaskRecord,
        UserRecord,
    )

    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _ensure_legacy_sqlite_compat_columns(engine)


def _ensure_legacy_sqlite_compat_columns(engine: Engine) -> None:
    """Add newly introduced columns when working against an older local SQLite file."""
    compat_columns = {
        "data_records": {
            "store_ref": "ALTER TABLE data_records ADD COLUMN store_ref JSON DEFAULT '{}'",
        },
        "result_bundle_records": {
            "parent_batch_id": (
                "ALTER TABLE result_bundle_records ADD COLUMN parent_batch_id INTEGER"
            ),
        },
    }
    with engine.begin() as connection:
        dialect_name = connection.dialect.name
        if dialect_name != "sqlite":
            return
        for table_name, columns in compat_columns.items():
            existing_columns = {
                str(row[1]) for row in connection.execute(text(f"PRAGMA table_info({table_name})"))
            }
            for column_name, statement in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(text(statement))
