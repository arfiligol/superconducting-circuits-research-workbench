"""Repository for TraceRecord operations."""

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import String, and_, asc, case, delete, desc, func, not_, or_
from sqlalchemy import cast as sa_cast
from sqlalchemy import select as sa_select
from sqlmodel import Session, select

from app_backend.infrastructure.local_store.models import (
    DesignRecord,
    TraceBatchTraceLink,
    TraceRecord,
    resolve_scope_ids_for_compatibility_write,
)
from app_backend.infrastructure.local_store.repositories.query_objects import TraceIndexPageQuery


def _canonical_trace_row(row: dict[str, str | int]) -> dict[str, str | int]:
    """Translate legacy row keys into trace-first row keys."""
    return {
        "id": int(row["id"]),
        "family": str(row["data_type"]),
        "parameter": str(row["parameter"]),
        "representation": str(row["representation"]),
    }


def _sideband_parameter_predicate(parameter_col: Any) -> Any:
    """Return a SQL predicate that treats zero-mode suffixes as base traces."""
    parameter_text = sa_cast(parameter_col, String)
    has_sideband_metadata = or_(
        parameter_text.ilike("% [om=%"),
        parameter_text.ilike("% [im=%"),
    )
    zero_mode_suffix = or_(
        parameter_text.ilike("% [om=(0,), im=(0,)]"),
        parameter_text.ilike("% [om=(0, 0), im=(0, 0)]"),
        parameter_text.ilike("% [om=(0,0), im=(0,0)]"),
        parameter_text.ilike("% [om=(0, 0, 0), im=(0, 0, 0)]"),
        parameter_text.ilike("% [om=(0,0,0), im=(0,0,0)]"),
    )
    return and_(has_sideband_metadata, not_(zero_mode_suffix))


class TraceRepository:
    """Repository for trace metadata operations."""

    def __init__(self, session: Session):
        self._session = session

    def get(self, id: int) -> TraceRecord | None:
        """Get a trace by ID."""
        return self._session.get(TraceRecord, id)

    def list_by_design(self, design_id: int) -> list[TraceRecord]:
        """List all traces for one design."""
        statement = select(TraceRecord).where(TraceRecord.design_id == design_id)
        return list(self._session.exec(statement).all())

    def list_by_dataset(self, dataset_id: int) -> list[TraceRecord]:
        """Legacy dataset-scoped wrapper."""
        statement = select(TraceRecord).where(TraceRecord.dataset_id == dataset_id)
        return list(self._session.exec(statement).all())

    def list_index_by_design(self, design_id: int) -> list[dict[str, str | int]]:
        """List lightweight trace metadata for one design."""
        statement = (
            select(
                TraceRecord.id,
                TraceRecord.data_type,
                TraceRecord.parameter,
                TraceRecord.representation,
            )
            .where(TraceRecord.design_id == design_id)
            .order_by(TraceRecord.id)  # type: ignore[arg-type]
        )
        rows = self._session.execute(statement).all()
        return [
            _canonical_trace_row(
                {
                    "id": int(record_id),
                    "data_type": str(data_type),
                    "parameter": str(parameter),
                    "representation": str(representation),
                }
            )
            for record_id, data_type, parameter, representation in rows
            if record_id is not None
        ]

    def list_index_by_dataset(self, dataset_id: int) -> list[dict[str, str | int]]:
        """List lightweight record metadata for one dataset."""
        statement = (
            select(
                TraceRecord.id,
                TraceRecord.data_type,
                TraceRecord.parameter,
                TraceRecord.representation,
            )
            .where(TraceRecord.dataset_id == dataset_id)
            .order_by(TraceRecord.id)  # type: ignore[arg-type]
        )
        rows = self._session.execute(statement).all()
        return [
            {
                "id": int(record_id),
                "data_type": str(data_type),
                "parameter": str(parameter),
                "representation": str(representation),
            }
            for record_id, data_type, parameter, representation in rows
            if record_id is not None
        ]

    def count_by_design(self, design_id: int) -> int:
        """Count all traces under one design."""
        design_id_col = cast(Any, TraceRecord.design_id)
        statement = sa_select(func.count()).where(design_id_col == design_id)
        return int(self._session.execute(statement).scalar_one())

    def count_by_dataset(self, dataset_id: int) -> int:
        """Count all records under one dataset."""
        dataset_id_col = cast(Any, TraceRecord.dataset_id)
        statement = sa_select(func.count()).where(dataset_id_col == dataset_id)
        return int(self._session.execute(statement).scalar_one())

    def list_distinct_index_for_profile(self, design_id: int) -> list[dict[str, str]]:
        """List distinct (family, parameter) pairs for profile inference."""
        design_id_col = cast(Any, TraceRecord.design_id)
        data_type_col = cast(Any, TraceRecord.data_type)
        parameter_col = cast(Any, TraceRecord.parameter)
        statement = (
            sa_select(data_type_col, parameter_col)
            .where(design_id_col == design_id)
            .distinct()
            .order_by(data_type_col, parameter_col)
        )
        rows = self._session.execute(statement).all()
        return [
            {
                "data_type": str(data_type),
                "family": str(data_type),
                "parameter": str(parameter),
            }
            for data_type, parameter in rows
        ]

    def list_index_page_by_design(
        self,
        design_id: int,
        *,
        query: TraceIndexPageQuery | None = None,
        **kwargs: object,
    ) -> tuple[list[dict[str, str | int]], int]:
        """List one page of canonical trace metadata rows for a design."""
        rows, total = self._list_index_page_by_scope(
            scope_name="design_id",
            scope_id=design_id,
            query=query,
            **kwargs,
        )
        return ([_canonical_trace_row(row) for row in rows], total)

    def list_index_page_by_dataset(
        self,
        dataset_id: int,
        *,
        query: TraceIndexPageQuery | None = None,
        search: str = "",
        sort_by: str = "id",
        descending: bool = False,
        data_type: str = "",
        data_types: Sequence[str] | None = None,
        parameters: Sequence[str] | None = None,
        representation: str = "",
        mode_filter: str = "all",
        ids: Sequence[int] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, str | int]], int]:
        """List one page of lightweight metadata rows for a dataset."""
        return self._list_index_page_by_scope(
            scope_name="dataset_id",
            scope_id=dataset_id,
            query=query,
            search=search,
            sort_by=sort_by,
            descending=descending,
            data_type=data_type,
            data_types=data_types,
            parameters=parameters,
            representation=representation,
            mode_filter=mode_filter,
            ids=ids,
            limit=limit,
            offset=offset,
        )

    def _list_index_page_by_scope(
        self,
        *,
        scope_name: str,
        scope_id: int,
        query: TraceIndexPageQuery | None = None,
        search: str = "",
        sort_by: str = "id",
        descending: bool = False,
        data_type: str = "",
        data_types: Sequence[str] | None = None,
        parameters: Sequence[str] | None = None,
        representation: str = "",
        mode_filter: str = "all",
        ids: Sequence[int] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, str | int]], int]:
        """List one page of lightweight metadata rows for one explicit scope column."""
        if query is not None:
            search = query.search
            sort_by = query.sort_by
            descending = query.descending
            data_type = query.data_type
            data_types = query.data_types
            parameters = query.parameters
            representation = query.representation
            mode_filter = query.mode_filter
            ids = query.ids
            limit = query.limit
            offset = query.offset

        id_col = cast(Any, TraceRecord.id)
        data_type_col = cast(Any, TraceRecord.data_type)
        parameter_col = cast(Any, TraceRecord.parameter)
        representation_col = cast(Any, TraceRecord.representation)
        scope_col = cast(Any, getattr(TraceRecord, scope_name))

        statement = sa_select(
            id_col,
            data_type_col,
            parameter_col,
            representation_col,
        ).where(scope_col == scope_id)

        sideband_predicate = _sideband_parameter_predicate(parameter_col)

        if ids is not None:
            normalized_ids = [int(record_id) for record_id in ids]
            if not normalized_ids:
                return ([], 0)
            statement = statement.where(id_col.in_(normalized_ids))

        search_text = search.strip()
        if search_text:
            like_value = f"%{search_text}%"
            statement = statement.where(
                or_(
                    sa_cast(id_col, String).ilike(like_value),
                    sa_cast(data_type_col, String).ilike(like_value),
                    sa_cast(parameter_col, String).ilike(like_value),
                    sa_cast(representation_col, String).ilike(like_value),
                )
            )

        normalized_data_types = [
            str(item).strip() for item in data_types or [] if str(item).strip()
        ]
        if normalized_data_types:
            statement = statement.where(
                or_(*[data_type_col == item for item in normalized_data_types])
            )
        elif data_type:
            statement = statement.where(data_type_col == data_type)

        normalized_parameters = [
            str(item).strip() for item in parameters or [] if str(item).strip()
        ]
        if normalized_parameters:
            statement = statement.where(
                or_(
                    *[
                        or_(
                            parameter_col == parameter_name,
                            parameter_col.ilike(f"{parameter_name} [%"),
                        )
                        for parameter_name in normalized_parameters
                    ]
                )
            )
        if representation:
            statement = statement.where(representation_col == representation)

        normalized_mode_filter = str(mode_filter or "").strip().lower()
        if normalized_mode_filter == "base":
            statement = statement.where(not_(sideband_predicate))
        elif normalized_mode_filter == "sideband":
            statement = statement.where(sideband_predicate)

        count_statement = sa_select(func.count()).select_from(statement.subquery())

        sort_columns = {
            "id": id_col,
            "mode": case((sideband_predicate, 1), else_=0),
            "data_type": data_type_col,
            "parameter": parameter_col,
            "representation": representation_col,
        }
        sort_column = sort_columns.get(sort_by, id_col)
        order_expression = desc(sort_column) if descending else asc(sort_column)
        statement = statement.order_by(order_expression).offset(max(0, offset)).limit(max(1, limit))

        rows = self._session.execute(statement).all()
        total_rows = int(self._session.execute(count_statement).scalar_one())
        return (
            [
                {
                    "id": int(record_id),
                    "data_type": str(row_data_type),
                    "parameter": str(row_parameter),
                    "representation": str(row_representation),
                }
                for record_id, row_data_type, row_parameter, row_representation in rows
                if record_id is not None
            ],
            total_rows,
        )

    def list_summary_by_design(self, design_id: int) -> list[dict[str, object]]:
        """List summary rows for one design without loading large axes/value payloads."""
        id_col = cast(Any, TraceRecord.id)
        dataset_id_col = cast(Any, TraceRecord.dataset_id)
        design_id_col = cast(Any, TraceRecord.design_id)
        data_type_col = cast(Any, TraceRecord.data_type)
        parameter_col = cast(Any, TraceRecord.parameter)
        representation_col = cast(Any, TraceRecord.representation)

        statement = (
            sa_select(
                id_col,
                dataset_id_col,
                design_id_col,
                data_type_col,
                parameter_col,
                representation_col,
            )
            .where(design_id_col == design_id)
            .order_by(id_col)
        )
        rows = self._session.execute(statement).all()
        return [
            {
                "id": int(record_id),
                "dataset_id": int(row_dataset_id),
                "design_id": int(row_design_id),
                "family": str(data_type),
                "parameter": str(parameter),
                "representation": str(representation),
                "created_at": None,
            }
            for (
                record_id,
                row_dataset_id,
                row_design_id,
                data_type,
                parameter,
                representation,
            ) in rows
            if record_id is not None and row_dataset_id is not None and row_design_id is not None
        ]

    def list_summary_by_dataset(self, dataset_id: int) -> list[dict[str, object]]:
        """List summary rows for one dataset without loading large axes/value payloads."""
        id_col = cast(Any, TraceRecord.id)
        dataset_id_col = cast(Any, TraceRecord.dataset_id)
        design_id_col = cast(Any, TraceRecord.design_id)
        data_type_col = cast(Any, TraceRecord.data_type)
        parameter_col = cast(Any, TraceRecord.parameter)
        representation_col = cast(Any, TraceRecord.representation)

        statement = (
            sa_select(
                id_col,
                dataset_id_col,
                design_id_col,
                data_type_col,
                parameter_col,
                representation_col,
            )
            .where(dataset_id_col == dataset_id)
            .order_by(id_col)
        )
        rows = self._session.execute(statement).all()
        return [
            {
                "id": int(record_id),
                "dataset_id": int(row_dataset_id),
                "design_id": int(row_design_id),
                "data_type": str(data_type),
                "parameter": str(parameter),
                "representation": str(representation),
                "created_at": None,
            }
            for (
                record_id,
                row_dataset_id,
                row_design_id,
                data_type,
                parameter,
                representation,
            ) in rows
            if record_id is not None and row_design_id is not None
        ]

    def add(self, trace: TraceRecord) -> TraceRecord:
        """Add a new trace."""
        resolve_scope_ids_for_compatibility_write(trace)
        self._session.add(trace)
        return trace

    def list_all(self, *, include_hidden: bool = False) -> list[TraceRecord]:
        """List all traces, excluding hidden-design rows by default."""
        statement = select(TraceRecord).order_by(TraceRecord.id)  # type: ignore[arg-type]
        records = list(self._session.exec(statement).all())
        if include_hidden:
            return records
        if not records:
            return []

        design_ids = {int(record.design_id) for record in records if record.design_id is not None}
        hidden_design_ids = {
            design.id
            for design in self._session.exec(select(DesignRecord)).all()
            if design.id is not None and design.source_meta.get("system_hidden")
            if design.id in design_ids
        }
        return [
            record
            for record in records
            if record.design_id is not None and record.design_id not in hidden_design_ids
        ]

    def delete(self, trace: TraceRecord) -> None:
        """Delete a trace."""
        if trace.id is not None:
            self._session.exec(
                delete(TraceBatchTraceLink).where(
                    TraceBatchTraceLink.data_record_id == trace.id  # type: ignore[arg-type]
                )
            )
        self._session.delete(trace)

    def reorder_id(self, old_id: int, new_id: int) -> TraceRecord:
        """Change trace ID."""
        if self.get(new_id):
            raise ValueError(f"Target ID {new_id} already exists.")

        trace = self.get(old_id)
        if not trace:
            raise ValueError(f"Source ID {old_id} not found.")

        from sqlmodel import update

        self._session.exec(
            update(TraceBatchTraceLink)
            .where(TraceBatchTraceLink.data_record_id == old_id)  # type: ignore[arg-type]
            .values(data_record_id=new_id)
        )
        self._session.exec(
            update(TraceRecord).where(TraceRecord.id == old_id).values(id=new_id)  # type: ignore[arg-type]
        )

        self._session.expire(trace)
        updated = self.get(new_id)
        if updated is None:
            raise ValueError(f"Failed to reload trace after reordering id to {new_id}.")
        return updated


DataRecordRepository = TraceRepository
