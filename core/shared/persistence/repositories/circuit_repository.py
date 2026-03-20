"""Repository for managing CircuitRecord instances."""

from datetime import datetime
from typing import Any, cast

from sqlalchemy import asc, desc, func
from sqlmodel import Session, select

from core.shared.persistence.models import CircuitRecord


class CircuitRepository:
    """Repository for managing circuit definitions in the database."""

    def __init__(self, session: Session):
        self._session = session

    def add(self, circuit: CircuitRecord) -> CircuitRecord:
        """Add a new CircuitRecord to the database."""
        self._session.add(circuit)
        # Flush is implicitly called by the UOW on commit, but you can flush here if needed
        return circuit

    def get(self, record_id: int) -> CircuitRecord | None:
        """Get a CircuitRecord by its ID."""
        return self._session.get(CircuitRecord, record_id)

    def get_by_name(self, name: str) -> CircuitRecord | None:
        """Get a CircuitRecord by its exact name."""
        stmt = select(CircuitRecord).where(CircuitRecord.name == name)
        return self._session.exec(stmt).first()

    def list_all(self) -> list[CircuitRecord]:
        """List all CircuitRecords, ordered by name."""
        stmt = select(CircuitRecord).order_by(CircuitRecord.name)
        return list(self._session.exec(stmt).all())

    def list_summary_page(
        self,
        *,
        search: str = "",
        sort_by: str = "created_at",
        descending: bool = True,
        limit: int = 12,
        offset: int = 0,
    ) -> tuple[list[dict[str, int | str | datetime]], int]:
        """List one page of circuit summaries without loading definition_json."""
        safe_sort_columns = {
            "id": CircuitRecord.id,
            "name": CircuitRecord.name,
            "created_at": CircuitRecord.created_at,
        }
        sort_column = safe_sort_columns.get(sort_by, CircuitRecord.created_at)

        statement = select(CircuitRecord.id, CircuitRecord.name, CircuitRecord.created_at)
        count_statement = select(func.count()).select_from(CircuitRecord)

        search_text = search.strip()
        if search_text:
            like_value = f"%{search_text}%"
            name_column = cast(Any, CircuitRecord.name)
            statement = statement.where(name_column.ilike(like_value))
            count_statement = count_statement.where(name_column.ilike(like_value))

        order_expression = desc(sort_column) if descending else asc(sort_column)
        statement = statement.order_by(order_expression).offset(max(0, offset)).limit(max(1, limit))

        rows = self._session.exec(statement).all()
        total_rows = int(self._session.exec(count_statement).one())
        return (
            [
                {
                    "id": int(circuit_id),
                    "name": str(name),
                    "created_at": created_at,
                }
                for circuit_id, name, created_at in rows
                if circuit_id is not None
            ],
            total_rows,
        )

    def update(self, circuit: CircuitRecord) -> CircuitRecord:
        """Update an existing CircuitRecord."""
        self._session.add(circuit)
        return circuit

    def delete(self, record_id: int) -> bool:
        """Delete a CircuitRecord by its ID."""
        record = self.get(record_id)
        if record:
            self._session.delete(record)
            return True
        return False
