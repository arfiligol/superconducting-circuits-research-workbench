"""Repository for DesignRecord operations."""

from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from core.shared.persistence.models import (
    DerivedParameter,
    DesignRecord,
    DesignTagLink,
    Tag,
    TraceBatchRecord,
    TraceRecord,
)


class DesignRepository:
    """Repository for design-scoped persistence operations."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, id: int) -> DesignRecord | None:
        """Get a design by ID."""
        return self._session.get(DesignRecord, id)

    def get_by_name(self, name: str) -> DesignRecord | None:
        """Get a design by unique name."""
        statement = select(DesignRecord).where(DesignRecord.name == name)
        return self._session.exec(statement).first()

    @staticmethod
    def _is_hidden(design: DesignRecord) -> bool:
        """Return whether this design should stay hidden from normal listings."""
        return bool(design.source_meta.get("system_hidden"))

    def list_all(self, *, include_hidden: bool = False) -> list[DesignRecord]:
        """List designs, excluding system-hidden containers by default."""
        statement = select(DesignRecord).order_by(DesignRecord.id)  # type: ignore[arg-type]
        records = list(self._session.exec(statement).all())
        if include_hidden:
            return records
        return [record for record in records if not self._is_hidden(record)]

    def list_summary_page(
        self,
        *,
        search: str = "",
        sort_by: str = "id",
        descending: bool = False,
        limit: int = 20,
        offset: int = 0,
        include_hidden: bool = False,
    ) -> tuple[list[dict[str, int | str | datetime]], int]:
        """List one page of design summaries for UI tables/cards."""
        records = self.list_all(include_hidden=include_hidden)

        search_text = search.strip().lower()
        if search_text:
            records = [record for record in records if search_text in record.name.lower()]

        if sort_by == "name":
            records.sort(key=lambda record: record.name.lower(), reverse=descending)
        elif sort_by == "created_at":
            records.sort(key=lambda record: record.created_at, reverse=descending)
        else:
            records.sort(key=lambda record: int(record.id or 0), reverse=descending)

        total = len(records)
        page_rows = records[offset : offset + max(1, limit)]
        return (
            [
                {
                    "id": int(record.id or 0),
                    "name": record.name,
                    "created_at": record.created_at,
                }
                for record in page_rows
            ],
            total,
        )

    def list_by_tag(self, tag_name: str, *, include_hidden: bool = False) -> list[DesignRecord]:
        """List designs with a specific tag."""
        statement = (
            select(DesignRecord)
            .join(DesignTagLink, DesignRecord.id == DesignTagLink.dataset_id)  # type: ignore[arg-type]
            .join(Tag, DesignTagLink.tag_id == Tag.id)  # type: ignore[arg-type]
            .where(Tag.name == tag_name)
            .order_by(DesignRecord.id)  # type: ignore[arg-type]
        )
        records = list(self._session.exec(statement).all())
        if include_hidden:
            return records
        return [record for record in records if not self._is_hidden(record)]

    def add(self, design: DesignRecord) -> DesignRecord:
        """Add a new design."""
        self._session.add(design)
        return design

    def update_design_meta(self, design_id: int, design_meta: dict[str, Any]) -> DesignRecord:
        """Replace one design's metadata payload."""
        design = self.get(design_id)
        if design is None:
            raise ValueError(f"Design ID {design_id} not found.")
        design.design_meta = dict(design_meta)
        self._session.add(design)
        return design

    def update_source_meta(self, dataset_id: int, source_meta: dict[str, Any]) -> DesignRecord:
        """Legacy wrapper for dataset-scoped callers."""
        return self.update_design_meta(dataset_id, source_meta)

    def delete(self, design: DesignRecord) -> None:
        """Delete a design."""
        self._session.delete(design)

    def reorder_id(self, old_id: int, new_id: int) -> DesignRecord:
        """Change a design ID and update all dependencies."""
        if self.get(new_id):
            raise ValueError(f"Target ID {new_id} already exists.")

        design = self.get(old_id)
        if not design:
            raise ValueError(f"Source ID {old_id} not found.")

        temp_name = f"{design.name}_TEMP_{new_id}"
        new_design = DesignRecord(
            id=new_id,
            name=temp_name,
            source_meta=design.source_meta,
            parameters=design.parameters,
            created_at=design.created_at,
        )
        self._session.add(new_design)
        self._session.flush()

        from sqlmodel import update

        self._session.exec(
            update(TraceRecord)
            .where(TraceRecord.dataset_id == old_id)  # type: ignore[arg-type]
            .values(dataset_id=new_id)
        )
        self._session.exec(
            update(TraceRecord)
            .where(TraceRecord.design_id == old_id)  # type: ignore[arg-type]
            .values(design_id=new_id)
        )
        self._session.exec(
            update(DerivedParameter)
            .where(DerivedParameter.dataset_id == old_id)  # type: ignore[arg-type]
            .values(dataset_id=new_id)
        )
        self._session.exec(
            update(DerivedParameter)
            .where(DerivedParameter.design_id == old_id)  # type: ignore[arg-type]
            .values(design_id=new_id)
        )
        self._session.exec(
            update(TraceBatchRecord)
            .where(TraceBatchRecord.dataset_id == old_id)  # type: ignore[arg-type]
            .values(dataset_id=new_id)
        )
        self._session.exec(
            update(TraceBatchRecord)
            .where(TraceBatchRecord.design_id == old_id)  # type: ignore[arg-type]
            .values(design_id=new_id)
        )
        self._session.exec(
            update(DesignTagLink)
            .where(DesignTagLink.dataset_id == old_id)  # type: ignore[arg-type]
            .values(dataset_id=new_id)
        )

        original_name = design.name
        self._session.delete(design)
        self._session.flush()

        new_design.name = original_name
        self._session.add(new_design)
        self._session.flush()
        return new_design


DatasetRepository = DesignRepository
