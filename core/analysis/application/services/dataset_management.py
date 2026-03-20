"""Service for managing datasets (List, Get, Delete, Reorder)."""

from typing import Literal, cast

from core.analysis.application.dto.dataset_dtos import DatasetDetailDTO, DatasetSummaryDTO
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import DatasetRecord


class DatasetManagementService:
    """Service to manage datasets using Clean Architecture."""

    def list_datasets(self) -> list[DatasetSummaryDTO]:
        """List all datasets with summary info."""
        with get_unit_of_work() as uow:
            records = uow.datasets.list_all()
            return [self._to_summary(r) for r in records]

    def get_dataset(self, identifier: str) -> DatasetDetailDTO | None:
        """
        Get dataset details by ID (int as str) or Name (str).

        Args:
            identifier: ID or Name of the dataset.

        Returns:
            DatasetDetailDTO if found, None otherwise.
        """
        with get_unit_of_work() as uow:
            record = self._find_record(uow, identifier)
            if not record:
                return None

            # Count data records explicitly if needed, or rely on relationship lazy load
            # Here we assume relationship is available.
            # Note: In async/detached scenarios, lazy loading might fail.
            # But SqliteUnitOfWork keeps session open in context.
            record_count = len(record.data_records)

            return self._to_detail(record, record_count)

    def delete_dataset(self, identifier: str) -> bool:
        """
        Delete a dataset by ID or Name.

        Returns:
            True if deleted, False if not found.
        """
        with get_unit_of_work() as uow:
            record = self._find_record(uow, identifier)
            if not record:
                return False

            uow.datasets.delete(record)
            uow.commit()
            return True

    def auto_reorder(self, sort_by: Literal["id", "name"] = "id") -> int:
        """
        Automatically reorder IDs to be sequential (1..N).
        Supports sorting by current ID or dataset name before reassignment.
        """
        with get_unit_of_work() as uow:
            records = uow.datasets.list_all()
            if not records:
                return 0

            ordered = self._sort_records(records, sort_by)
            return self._reassign_sequential_ids(uow, ordered)

    def _find_record(self, uow, identifier: str) -> DatasetRecord | None:
        """Helper to find record by ID or Name."""
        if identifier.isdigit():
            return uow.datasets.get(int(identifier))
        return uow.datasets.get_by_name(identifier)

    def _sort_records(
        self,
        records: list[DatasetRecord],
        sort_by: Literal["id", "name"],
    ) -> list[DatasetRecord]:
        """Sort datasets using a deterministic key."""
        if sort_by == "id":
            return sorted(records, key=lambda record: cast(int, record.id))
        if sort_by == "name":
            return sorted(
                records,
                key=lambda record: (record.name.casefold(), cast(int, record.id)),
            )
        raise ValueError(f"Unsupported sort_by mode: {sort_by}")

    def _reassign_sequential_ids(self, uow, ordered: list[DatasetRecord]) -> int:
        """
        Reassign IDs to 1..N without collisions using two-pass remapping.

        Pass 1: move all changed IDs to temporary high IDs.
        Pass 2: move temporary IDs to final sequential IDs.
        """
        current_ids = [cast(int, record.id) for record in ordered]
        target_by_old_id = {old_id: new_id for new_id, old_id in enumerate(current_ids, start=1)}
        unchanged = sum(1 for old_id, new_id in target_by_old_id.items() if old_id == new_id)
        if unchanged == len(current_ids):
            return 0

        temp_offset = max(current_ids) + len(current_ids) + 1000

        for old_id in current_ids:
            new_id = target_by_old_id[old_id]
            if old_id == new_id:
                continue
            uow.datasets.reorder_id(old_id, old_id + temp_offset)

        moved = 0
        for old_id in current_ids:
            new_id = target_by_old_id[old_id]
            if old_id == new_id:
                continue
            uow.datasets.reorder_id(old_id + temp_offset, new_id)
            moved += 1

        uow.commit()
        return moved

    def _to_summary(self, record: DatasetRecord) -> DatasetSummaryDTO:
        """Convert Model to Summary DTO."""
        tags = [t.name for t in record.tags]
        origin = record.source_meta.get("origin") if record.source_meta else None

        return DatasetSummaryDTO(
            id=cast(int, record.id),
            name=record.name,
            created_at=record.created_at,
            tags=tags,
            origin=cast(str | None, origin),
        )

    def _to_detail(self, record: DatasetRecord, record_count: int) -> DatasetDetailDTO:
        """Convert Model to Detail DTO."""
        tags = [t.name for t in record.tags]
        meta = record.source_meta or {}
        origin = meta.get("origin")
        raw_files = meta.get("raw_files", [])

        return DatasetDetailDTO(
            id=cast(int, record.id),
            name=record.name,
            created_at=record.created_at,
            origin=cast(str | None, origin),
            source_files=cast(list[str], raw_files),
            tags=tags,
            parameters=record.parameters or {},
            data_records_count=record_count,
        )
