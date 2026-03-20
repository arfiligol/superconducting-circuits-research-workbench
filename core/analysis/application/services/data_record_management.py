"""Service for managing DataRecords."""

from typing import Literal, cast

from core.analysis.application.dto.data_record_dtos import (
    DataRecordDetailDTO,
    DataRecordSummaryDTO,
)
from core.analysis.application.services.trace_record_materializer import materialize_trace_record
from core.analysis.domain import normalize_trace_record
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import DataRecord


class DataRecordManagementService:
    """Service to manage data records."""

    def list_records(self, dataset_id: int | None = None) -> list[DataRecordSummaryDTO]:
        """List data records, optionally filtered by dataset ID."""
        with get_unit_of_work() as uow:
            if dataset_id is not None:
                summary_rows = uow.data_records.list_summary_by_dataset(dataset_id)
                return [self._to_summary(row) for row in summary_rows]

            records = uow.data_records.list_all()
            return [self._to_summary(r) for r in records]

    def get_record(self, id: int) -> DataRecordDetailDTO | None:
        """Get data record details."""
        with get_unit_of_work() as uow:
            record = uow.data_records.get(id)
            return self._to_detail(record) if record else None

    def delete_record(self, id: int) -> bool:
        """Delete a data record."""
        with get_unit_of_work() as uow:
            record = uow.data_records.get(id)
            if not record:
                return False

            uow.data_records.delete(record)
            uow.commit()
            return True

    def auto_reorder(self, sort_by: Literal["id", "name"] = "id") -> int:
        """
        Automatically reorder IDs to be sequential (1..N).

        sort_by:
            - id: preserve current record ID order.
            - name: sort by dataset name + record identity tuple.
        """
        with get_unit_of_work() as uow:
            records = uow.data_records.list_all()
            if not records:
                return 0

            ordered = self._sort_records(records, sort_by)
            return self._reassign_sequential_ids(uow, ordered)

    def _to_summary(self, record: object) -> DataRecordSummaryDTO:
        normalized_record = normalize_trace_record(record)
        return DataRecordSummaryDTO(
            id=cast(int, normalized_record.id),
            dataset_id=cast(int, normalized_record.dataset_id),
            data_type=normalized_record.data_type,
            parameter=normalized_record.parameter,
            representation=normalized_record.representation,
            created_at=getattr(record, "created_at", None),
        )

    def _to_detail(self, record: object) -> DataRecordDetailDTO:
        normalized_record = materialize_trace_record(record)
        return DataRecordDetailDTO(
            id=cast(int, normalized_record.id),
            dataset_id=cast(int, normalized_record.dataset_id),
            data_type=normalized_record.data_type,
            parameter=normalized_record.parameter,
            representation=normalized_record.representation,
            axes=normalized_record.axes,
            values=cast(list, normalized_record.values),
            created_at=getattr(record, "created_at", None),
        )

    def _sort_records(
        self,
        records: list[DataRecord],
        sort_by: Literal["id", "name"],
    ) -> list[DataRecord]:
        """Sort data records using a deterministic key."""
        if sort_by == "id":
            return sorted(records, key=lambda record: cast(int, record.id))
        if sort_by == "name":
            return sorted(
                records,
                key=lambda record: (
                    (record.dataset.name if record.dataset else "").casefold(),
                    record.data_type.casefold(),
                    record.parameter.casefold(),
                    record.representation.casefold(),
                    cast(int, record.id),
                ),
            )
        raise ValueError(f"Unsupported sort_by mode: {sort_by}")

    def _reassign_sequential_ids(self, uow, ordered: list[DataRecord]) -> int:
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
            uow.data_records.reorder_id(old_id, old_id + temp_offset)

        moved = 0
        for old_id in current_ids:
            new_id = target_by_old_id[old_id]
            if old_id == new_id:
                continue
            uow.data_records.reorder_id(old_id + temp_offset, new_id)
            moved += 1

        uow.commit()
        return moved
