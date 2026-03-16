"""Repository for TraceBatchRecord operations."""

from collections.abc import Sequence
from copy import deepcopy
from datetime import datetime
from typing import Any, cast

from sc_core.storage import (
    TraceBatchLifecyclePayload,
    merge_trace_batch_summary_payload,
)
from sqlalchemy import String, and_, asc, case, delete, desc, func, not_, or_
from sqlalchemy import cast as sa_cast
from sqlalchemy import select as sa_select
from sqlmodel import Session, select

from core.shared.persistence.models import (
    TraceBatchRecord,
    TraceBatchTraceLink,
    TraceRecord,
    require_explicit_scope_ids,
    resolve_scope_ids_for_compatibility_write,
    utc_now,
)
from core.shared.persistence.repositories.analysis_run_repository import AnalysisRunRepository
from core.shared.persistence.repositories.contracts import (
    AnalysisRunSummary,
    ResultBundleAnalysisRunSummary,
    ResultBundleSnapshot,
    TraceBatchSnapshot,
)
from core.shared.persistence.repositories.query_objects import TraceIndexPageQuery


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


def _legacy_trace_row(row: dict[str, str | int]) -> dict[str, str | int]:
    """Return a legacy-compatible trace row payload."""
    return {
        "id": int(row["id"]),
        "data_type": str(row["data_type"]),
        "parameter": str(row["parameter"]),
        "representation": str(row["representation"]),
    }


def _canonical_trace_row(row: dict[str, str | int]) -> dict[str, str | int]:
    """Translate legacy row keys into trace-first row keys."""
    return {
        "id": int(row["id"]),
        "family": str(row["data_type"]),
        "parameter": str(row["parameter"]),
        "representation": str(row["representation"]),
    }


class TraceBatchRepository:
    """Repository for trace-batch metadata and membership operations."""

    def __init__(self, session: Session):
        self._session = session

    @property
    def analysis_runs(self) -> AnalysisRunRepository:
        """Expose the logical analysis-run repository over shared batch-backed storage."""
        return AnalysisRunRepository(self._session)

    def get(self, id: int) -> TraceBatchRecord | None:
        """Get a trace batch by ID."""
        return self._session.get(TraceBatchRecord, id)

    def get_trace_batch_snapshot(self, id: int) -> TraceBatchSnapshot | None:
        """Get one detached canonical snapshot for lineage/provenance reads."""
        batch = self._session.get(TraceBatchRecord, id)
        if batch is None or batch.id is None:
            return None
        if str(batch.status) != "completed":
            return None
        scope_ids = require_explicit_scope_ids(batch)
        lifecycle_payload = TraceBatchLifecyclePayload.from_persisted_batch(
            bundle_type=str(batch.bundle_type),
            role=str(batch.role),
            source_meta=dict(batch.source_meta),
            config_snapshot=dict(batch.config_snapshot),
            result_payload=dict(batch.result_payload),
        )
        return cast(
            TraceBatchSnapshot,
            {
                "id": int(batch.id),
                "dataset_id": scope_ids.dataset_id,
                "design_id": scope_ids.design_id,
                "status": str(batch.status),
                "parent_batch_id": batch.parent_batch_id,
                **lifecycle_payload.to_snapshot_payload(),
            },
        )

    def get_snapshot(self, id: int) -> ResultBundleSnapshot | None:
        """Get one detached legacy snapshot for provenance reads."""
        batch = self._session.get(TraceBatchRecord, id)
        if batch is None or batch.id is None:
            return None
        if str(batch.status) != "completed":
            return None
        scope_ids = require_explicit_scope_ids(batch)
        return {
            "id": int(batch.id),
            "dataset_id": scope_ids.dataset_id,
            "design_id": scope_ids.design_id,
            "bundle_type": str(batch.bundle_type),
            "role": str(batch.role),
            "status": str(batch.status),
            "schema_source_hash": (
                str(batch.schema_source_hash) if batch.schema_source_hash is not None else None
            ),
            "simulation_setup_hash": (
                str(batch.simulation_setup_hash)
                if batch.simulation_setup_hash is not None
                else None
            ),
            "source_meta": deepcopy(batch.source_meta),
            "config_snapshot": deepcopy(batch.config_snapshot),
            "result_payload": deepcopy(batch.result_payload),
        }

    def add(self, batch: TraceBatchRecord) -> TraceBatchRecord:
        """Add a new trace batch."""
        resolve_scope_ids_for_compatibility_write(batch)
        self._session.add(batch)
        return batch

    def mark_in_progress(
        self,
        batch_id: int,
        *,
        summary_payload: dict[str, Any] | None = None,
    ) -> TraceBatchRecord:
        """Mark one trace batch as in progress."""
        batch = self.get(batch_id)
        if batch is None:
            raise ValueError(f"Trace batch ID {batch_id} not found.")
        batch.status = "in_progress"
        batch.completed_at = None
        if isinstance(summary_payload, dict):
            batch.result_payload = cast(
                dict[str, Any],
                merge_trace_batch_summary_payload(
                    dict(batch.result_payload),
                    dict(summary_payload),
                ),
            )
        self._session.add(batch)
        self._session.flush()
        return batch

    def mark_completed(
        self,
        batch_id: int,
        *,
        summary_payload: dict[str, Any] | None = None,
    ) -> TraceBatchRecord:
        """Mark one trace batch as completed."""
        batch = self.get(batch_id)
        if batch is None:
            raise ValueError(f"Trace batch ID {batch_id} not found.")
        batch.status = "completed"
        batch.completed_at = utc_now()
        if isinstance(summary_payload, dict):
            batch.result_payload = cast(
                dict[str, Any],
                merge_trace_batch_summary_payload(
                    dict(batch.result_payload),
                    dict(summary_payload),
                ),
            )
        self._session.add(batch)
        self._session.flush()
        return batch

    def mark_failed(
        self,
        batch_id: int,
        *,
        summary_payload: dict[str, Any] | None = None,
    ) -> TraceBatchRecord:
        """Mark one trace batch as failed."""
        batch = self.get(batch_id)
        if batch is None:
            raise ValueError(f"Trace batch ID {batch_id} not found.")
        batch.status = "failed"
        batch.completed_at = utc_now()
        if isinstance(summary_payload, dict):
            batch.result_payload = cast(
                dict[str, Any],
                merge_trace_batch_summary_payload(
                    dict(batch.result_payload),
                    dict(summary_payload),
                ),
            )
        self._session.add(batch)
        self._session.flush()
        return batch

    def delete(self, batch: TraceBatchRecord) -> None:
        """Delete one trace batch and its membership links."""
        if batch.id is not None:
            self._session.exec(
                delete(TraceBatchTraceLink).where(
                    TraceBatchTraceLink.result_bundle_id == batch.id  # type: ignore[arg-type]
                )
            )
        self._session.delete(batch)

    def _scope_statement(
        self,
        *,
        scope_name: str,
        scope_id: int,
        bundle_type: str | None = None,
        role: str | None = None,
        include_cache: bool = True,
    ):
        scope_column = cast(Any, getattr(TraceBatchRecord, scope_name))
        statement = select(TraceBatchRecord).where(scope_column == scope_id)
        if bundle_type:
            statement = statement.where(TraceBatchRecord.bundle_type == bundle_type)
        if role:
            statement = statement.where(TraceBatchRecord.role == role)
        elif not include_cache:
            statement = statement.where(TraceBatchRecord.role != "cache")
        return statement

    def list_by_design(self, design_id: int) -> list[TraceBatchRecord]:
        """List all trace batches under one design."""
        statement = self._scope_statement(scope_name="design_id", scope_id=design_id).order_by(
            TraceBatchRecord.id
        )  # type: ignore[arg-type]
        return list(self._session.exec(statement).all())

    def list_by_dataset(self, dataset_id: int) -> list[TraceBatchRecord]:
        """List all result bundles under one dataset."""
        statement = self._scope_statement(scope_name="dataset_id", scope_id=dataset_id).order_by(
            TraceBatchRecord.id
        )  # type: ignore[arg-type]
        return list(self._session.exec(statement).all())

    def list_incomplete_by_dataset(self, dataset_id: int) -> list[TraceBatchRecord]:
        """List non-completed batches under one dataset."""
        statement = (
            self._scope_statement(scope_name="dataset_id", scope_id=dataset_id)
            .where(TraceBatchRecord.status != "completed")
            .order_by(TraceBatchRecord.id)  # type: ignore[arg-type]
        )
        return list(self._session.exec(statement).all())

    def list_cache_by_design(self, design_id: int) -> list[TraceBatchRecord]:
        """List cache-role batches under one design."""
        statement = self._scope_statement(
            scope_name="design_id",
            scope_id=design_id,
            role="cache",
        ).order_by(TraceBatchRecord.id)  # type: ignore[arg-type]
        return list(self._session.exec(statement).all())

    def list_cache_by_dataset(self, dataset_id: int) -> list[TraceBatchRecord]:
        """List cache-role bundles under one dataset."""
        statement = self._scope_statement(
            scope_name="dataset_id",
            scope_id=dataset_id,
            role="cache",
        ).order_by(TraceBatchRecord.id)  # type: ignore[arg-type]
        return list(self._session.exec(statement).all())

    def list_provenance_by_design(self, design_id: int) -> list[TraceBatchRecord]:
        """List non-cache provenance batches under one design."""
        statement = self._scope_statement(
            scope_name="design_id",
            scope_id=design_id,
            include_cache=False,
        ).order_by(TraceBatchRecord.id)  # type: ignore[arg-type]
        return list(self._session.exec(statement).all())

    def list_provenance_by_dataset(self, dataset_id: int) -> list[TraceBatchRecord]:
        """List non-cache provenance bundles under one dataset."""
        statement = self._scope_statement(
            scope_name="dataset_id",
            scope_id=dataset_id,
            include_cache=False,
        ).order_by(TraceBatchRecord.id)  # type: ignore[arg-type]
        return list(self._session.exec(statement).all())

    def list_child_batches(self, parent_batch_id: int) -> list[TraceBatchRecord]:
        """List immediate child batches for one parent batch."""
        statement = (
            select(TraceBatchRecord)
            .where(TraceBatchRecord.parent_batch_id == parent_batch_id)
            .order_by(TraceBatchRecord.id)  # type: ignore[arg-type]
        )
        return list(self._session.exec(statement).all())

    def list_incomplete_batches(self) -> list[TraceBatchRecord]:
        """List all non-completed trace batches across designs."""
        statement = (
            select(TraceBatchRecord)
            .where(TraceBatchRecord.status != "completed")
            .order_by(TraceBatchRecord.id)  # type: ignore[arg-type]
        )
        return list(self._session.exec(statement).all())

    def count_by_design(
        self,
        design_id: int,
        *,
        bundle_type: str | None = None,
        role: str | None = None,
        include_cache: bool = True,
    ) -> int:
        """Count batches under one design with optional semantic filters."""
        statement = self._scope_statement(
            scope_name="design_id",
            scope_id=design_id,
            bundle_type=bundle_type,
            role=role,
            include_cache=include_cache,
        )
        count_statement = sa_select(func.count()).select_from(statement.subquery())
        return int(self._session.execute(count_statement).scalar_one())

    def count_by_dataset(
        self,
        dataset_id: int,
        *,
        bundle_type: str | None = None,
        role: str | None = None,
        include_cache: bool = True,
    ) -> int:
        """Count bundles under one dataset with optional semantic filters."""
        statement = self._scope_statement(
            scope_name="dataset_id",
            scope_id=dataset_id,
            bundle_type=bundle_type,
            role=role,
            include_cache=include_cache,
        )
        count_statement = sa_select(func.count()).select_from(statement.subquery())
        return int(self._session.execute(count_statement).scalar_one())

    def list_analysis_run_summaries_by_design(self, design_id: int) -> list[AnalysisRunSummary]:
        """List primitive-only summaries for analysis runs under one design."""
        return self.analysis_runs.list_summaries_by_design(design_id)

    def list_analysis_run_summaries_by_dataset(
        self,
        dataset_id: int,
    ) -> list[ResultBundleAnalysisRunSummary]:
        """List primitive-only summaries for characterization analysis runs."""
        canonical_rows = [
            {
                "analysis_run_id": int(run.id),
                "dataset_id": int(run.dataset_id),
                "design_id": int(run.design_id),
                "analysis_id": str(run.analysis_id),
                "analysis_label": str(run.analysis_label or run.analysis_id),
                "status": str(run.status),
            }
            for run in self.analysis_runs.list_by_dataset(dataset_id)
            if run.id is not None and run.dataset_id is not None and run.analysis_id
        ]
        return [
            {
                "bundle_id": int(row["analysis_run_id"]),
                "dataset_id": int(row["dataset_id"]),
                "design_id": int(row["design_id"]),
                "analysis_id": str(row["analysis_id"]),
                "analysis_label": str(row["analysis_label"]),
                "status": str(row["status"]),
            }
            for row in canonical_rows
        ]

    def find_completed_simulation_batch(
        self,
        *,
        design_id: int,
        schema_source_hash: str,
        simulation_setup_hash: str,
    ) -> TraceBatchRecord | None:
        """Find one completed circuit-simulation batch by formal identity."""
        statement = (
            select(TraceBatchRecord)
            .where(TraceBatchRecord.design_id == design_id)
            .where(TraceBatchRecord.bundle_type == "circuit_simulation")
            .where(TraceBatchRecord.role == "cache")
            .where(TraceBatchRecord.status == "completed")
            .where(TraceBatchRecord.schema_source_hash == schema_source_hash)
            .where(TraceBatchRecord.simulation_setup_hash == simulation_setup_hash)
            .order_by(TraceBatchRecord.id.desc())  # type: ignore[union-attr]
        )
        return self._session.exec(statement).first()

    def find_simulation_cache(
        self,
        *,
        dataset_id: int,
        schema_source_hash: str,
        simulation_setup_hash: str,
    ) -> TraceBatchRecord | None:
        """Find one completed circuit-simulation cache bundle by formal identity."""
        statement = (
            select(TraceBatchRecord)
            .where(TraceBatchRecord.dataset_id == dataset_id)
            .where(TraceBatchRecord.bundle_type == "circuit_simulation")
            .where(TraceBatchRecord.role == "cache")
            .where(TraceBatchRecord.status == "completed")
            .where(TraceBatchRecord.schema_source_hash == schema_source_hash)
            .where(TraceBatchRecord.simulation_setup_hash == simulation_setup_hash)
            .order_by(TraceBatchRecord.id.desc())  # type: ignore[union-attr]
        )
        return self._session.exec(statement).first()

    def attach_traces(self, *, batch_id: int, trace_ids: list[int]) -> None:
        """Attach existing TraceRecord rows to a batch."""
        for trace_id in trace_ids:
            self._session.add(
                TraceBatchTraceLink(
                    result_bundle_id=batch_id,
                    data_record_id=trace_id,
                )
            )

    def attach_data_records(self, *, bundle_id: int, data_record_ids: list[int]) -> None:
        """Legacy wrapper for attaching existing DataRecord rows to a bundle."""
        self.attach_traces(batch_id=bundle_id, trace_ids=data_record_ids)

    def detach_trace(self, trace_id: int) -> None:
        """Remove a trace from all batches before deleting or replacing it."""
        trace_id_col = cast(Any, TraceBatchTraceLink.data_record_id)
        statement = sa_select(TraceBatchTraceLink).where(trace_id_col == trace_id)
        for link in self._session.execute(statement).scalars():
            self._session.delete(link)

    def list_traces(self, batch_id: int) -> list[TraceRecord]:
        """List all TraceRecord rows attached to one batch."""
        statement = (
            select(TraceRecord)
            .join(
                TraceBatchTraceLink,
                TraceRecord.id == TraceBatchTraceLink.data_record_id,  # type: ignore[arg-type]
            )
            .where(TraceBatchTraceLink.result_bundle_id == batch_id)
            .order_by(TraceRecord.id)  # type: ignore[arg-type]
        )
        return list(self._session.exec(statement).all())

    def list_data_records(self, bundle_id: int) -> list[TraceRecord]:
        """Legacy wrapper for bundle-linked DataRecord rows."""
        return self.list_traces(bundle_id)

    def list_trace_index(self, batch_id: int) -> list[dict[str, str | int]]:
        """List lightweight metadata for batch-linked traces only."""
        return [_canonical_trace_row(row) for row in self.list_data_record_index(batch_id)]

    def list_data_record_index(self, bundle_id: int) -> list[dict[str, str | int]]:
        """List lightweight metadata for bundle-linked DataRecord rows only."""
        statement = (
            select(
                TraceRecord.id,
                TraceRecord.data_type,
                TraceRecord.parameter,
                TraceRecord.representation,
            )
            .join(
                TraceBatchTraceLink,
                TraceRecord.id == TraceBatchTraceLink.data_record_id,  # type: ignore[arg-type]
            )
            .where(TraceBatchTraceLink.result_bundle_id == bundle_id)
            .order_by(TraceRecord.id)  # type: ignore[arg-type]
        )
        rows = self._session.exec(statement).all()
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

    def count_traces(self, batch_id: int) -> int:
        """Count trace membership rows for one batch."""
        return self.count_data_records(batch_id)

    def count_data_records(self, bundle_id: int) -> int:
        """Count trace membership rows for one bundle."""
        bundle_col = cast(Any, TraceBatchTraceLink.result_bundle_id)
        statement = sa_select(func.count()).where(bundle_col == bundle_id)
        return int(self._session.execute(statement).scalar_one())

    def list_trace_index_page(
        self,
        batch_id: int,
        *,
        query: TraceIndexPageQuery | None = None,
        **kwargs: object,
    ) -> tuple[list[dict[str, str | int]], int]:
        """List one page of canonical batch-linked trace metadata rows."""
        rows, total = cast(Any, self.list_data_record_index_page)(batch_id, query=query, **kwargs)
        return ([_canonical_trace_row(row) for row in rows], total)

    def list_data_record_index_page(
        self,
        bundle_id: int,
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
        """List one page of bundle-linked trace metadata rows."""
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
        bundle_col = cast(Any, TraceBatchTraceLink.result_bundle_id)
        link_record_col = cast(Any, TraceBatchTraceLink.data_record_id)

        statement = (
            sa_select(
                id_col,
                data_type_col,
                parameter_col,
                representation_col,
            )
            .join(
                TraceBatchTraceLink,
                id_col == link_record_col,
            )
            .where(bundle_col == bundle_id)
        )

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


ResultBundleRepository = TraceBatchRepository
