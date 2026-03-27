from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from src.app.domain.characterization_analysis import (
    evaluate_trace_analysis_capabilities,
)
from src.app.domain.datasets import (
    DatasetDetail,
    DesignBrowseRow,
    DesignCreateDraft,
    ResultTracePublicationDraft,
    ResultTracePublicationResult,
    SimulationResultPublicationDraft,
    SimulationResultPublicationRecord,
    SimulationResultPublicationResult,
    TraceAnalysisCapability,
    TraceAxis,
    TraceDetail,
    TraceMetadataSummary,
)
from src.app.domain.result_traces import (
    ResultTraceSelection,
    build_trace_id,
    build_trace_parameter,
    resolve_saved_trace_parameter,
)
from src.app.domain.tasks import SimulationSetup, TaskDetail
from src.app.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    build_trace_preview_payload,
    delete_trace_payload_store,
    extract_selection_trace_data,
    write_complex_trace_payload,
)
from src.app.infrastructure.persistence.models import (
    RewriteDatasetDesignRecord,
    RewriteDatasetRecord,
    RewritePublishedSimulationResultRecord,
    RewritePublishedSimulationTraceRecord,
)
from src.app.infrastructure.persistence.storage_metadata_repository import (
    SqliteRewriteStorageMetadataRepository,
)
from src.app.infrastructure.persistence.trace_capability_store import (
    delete_trace_capabilities,
    load_trace_capability_map,
    replace_trace_capabilities,
)
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
)


class SqliteResearchDataPublicationRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage_metadata_repository: SqliteRewriteStorageMetadataRepository,
    ) -> None:
        self._session_factory = session_factory
        self._storage_metadata_repository = storage_metadata_repository

    def get_publication_record(
        self,
        source_task_id: int,
    ) -> SimulationResultPublicationRecord | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewritePublishedSimulationResultRecord).where(
                    RewritePublishedSimulationResultRecord.source_task_id == source_task_id
                )
            )
            if row is None:
                return None
            trace_rows = session.scalars(
                select(RewritePublishedSimulationTraceRecord)
                .where(RewritePublishedSimulationTraceRecord.publication_id == row.id)
                .order_by(RewritePublishedSimulationTraceRecord.id.asc())
            ).all()
            return _to_publication_record(row, trace_rows)

    def create_design(
        self,
        *,
        dataset_id: str,
        draft: DesignCreateDraft,
    ) -> DesignBrowseRow:
        design_id = _build_design_id(draft.name)
        updated_at = _timestamp_now()
        normalized_name = _normalize_design_name(draft.name)
        with self._session_factory() as session:
            design_row = session.scalar(
                select(RewriteDatasetDesignRecord).where(
                    RewriteDatasetDesignRecord.dataset_id == dataset_id,
                    or_(
                        RewriteDatasetDesignRecord.design_id == design_id,
                        RewriteDatasetDesignRecord.normalized_name == normalized_name,
                    ),
                )
            )
            if design_row is not None:
                raise ValueError("dataset design already exists")
            session.add(
                RewriteDatasetDesignRecord(
                    dataset_id=dataset_id,
                    design_id=design_id,
                    normalized_name=normalized_name,
                    name=draft.name,
                    updated_at=updated_at,
                )
            )
            session.commit()
        return DesignBrowseRow(
            design_id=design_id,
            dataset_id=dataset_id,
            name=draft.name,
            source_coverage=_empty_source_coverage(),
            compare_readiness="blocked",
            trace_count=0,
            updated_at=updated_at,
        )

    def publish_simulation_result(
        self,
        *,
        task: TaskDetail,
        dataset: DatasetDetail,
        draft: SimulationResultPublicationDraft,
    ) -> SimulationResultPublicationResult:
        design_id = draft.design_id or _build_design_id(draft.design_name)
        publication_key = _build_simulation_publication_key(
            task_id=task.task_id,
            dataset_id=dataset.dataset_id,
            design_id=design_id,
        )
        existing = self.get_publication_record(task.task_id)
        if existing is not None:
            if (
                existing.target_dataset_id == dataset.dataset_id
                and existing.target_design_id == design_id
            ):
                return self._load_publication_result(
                    task=task,
                    dataset=dataset,
                    publication_key=existing.publication_key,
                    state="already_published",
                )
            raise ValueError("simulation result already published elsewhere")

        published_at = _timestamp_now()
        trace_details = tuple(
            _build_persisted_simulation_publication_trace(
                task=task,
                dataset_family=dataset.family,
                dataset_id=dataset.dataset_id,
                design_id=design_id,
                family=family,
                source=source,
            )
            for family, source in _legacy_bundle_publication_targets(task)
        )
        for _summary, detail in trace_details:
            payload_ref = detail.payload_ref
            if payload_ref is None:
                raise ValueError("published simulation result is missing a trace payload")
            result_handle = detail.result_handles[0]
            trace_batch_record = result_handle.provenance.trace_batch_record
            if trace_batch_record is None:
                raise ValueError("published simulation result is missing storage metadata")
            self._storage_metadata_repository.save_trace_payload(trace_batch_record, payload_ref)
            self._storage_metadata_repository.save_result_handle(result_handle)

        with self._session_factory() as session:
            existing_row = session.scalar(
                select(RewritePublishedSimulationResultRecord).where(
                    RewritePublishedSimulationResultRecord.source_task_id == task.task_id
                )
            )
            if existing_row is not None:
                return self._load_publication_result(
                    task=task,
                    dataset=dataset,
                    publication_key=existing_row.publication_key,
                    state="already_published",
                )
            row = RewritePublishedSimulationResultRecord(
                publication_key=publication_key,
                source_task_id=task.task_id,
                source_dataset_id=task.dataset_id,
                source_result_handle_ids=[
                    handle.handle_id for handle in task.result_refs.result_handles
                ],
                target_dataset_id=dataset.dataset_id,
                target_design_id=design_id,
                target_design_name=draft.design_name,
                published_at=published_at,
            )
            session.add(row)
            session.flush()
            for summary, detail in trace_details:
                session.add(
                    RewritePublishedSimulationTraceRecord(
                        publication_id=row.id,
                        dataset_id=dataset.dataset_id,
                        design_id=design_id,
                        trace_id=detail.trace_id,
                        family=summary.family,
                        parameter=summary.parameter,
                        representation=summary.representation,
                        trace_mode_group=summary.trace_mode_group,
                        source_kind=summary.source_kind,
                        stage_kind=summary.stage_kind,
                        provenance_summary=summary.provenance_summary,
                        axes_json=[
                            {
                                "name": axis.name,
                                "unit": axis.unit,
                                "length": axis.length,
                            }
                            for axis in detail.axes
                        ],
                        preview_payload_json=detail.preview_payload,
                        payload_store_key=cast(str, detail.payload_ref.store_key),
                        result_handle_id=detail.result_handles[0].handle_id,
                        published_at=published_at,
                    )
                )
                replace_trace_capabilities(
                    session,
                    dataset_id=dataset.dataset_id,
                    design_id=design_id,
                    trace_id=detail.trace_id,
                    capabilities=summary.analysis_capabilities,
                )
            session.commit()
        return self._load_publication_result(
            task=task,
            dataset=dataset,
            publication_key=publication_key,
            state="published",
        )

    def publish_result_trace(
        self,
        *,
        task: TaskDetail,
        basis_task: TaskDetail,
        dataset: DatasetDetail,
        design: DesignBrowseRow,
        draft: ResultTracePublicationDraft,
    ) -> ResultTracePublicationResult:
        requests = _build_requested_trace_publications(
            task=task,
            basis_task=basis_task,
            draft=draft,
        )
        publication_key = _build_simulation_publication_key(
            task_id=task.task_id,
            dataset_id=dataset.dataset_id,
            design_id=design.design_id,
        )
        published_at = _timestamp_now()

        with self._session_factory() as session:
            publication_row = session.scalar(
                select(RewritePublishedSimulationResultRecord).where(
                    RewritePublishedSimulationResultRecord.source_task_id == task.task_id
                )
            )
            if publication_row is not None and (
                publication_row.target_dataset_id != dataset.dataset_id
                or publication_row.target_design_id != design.design_id
            ):
                raise ValueError("simulation result already published elsewhere")
            if publication_row is None:
                publication_row = RewritePublishedSimulationResultRecord(
                    publication_key=publication_key,
                    source_task_id=task.task_id,
                    source_dataset_id=task.dataset_id,
                    source_result_handle_ids=[
                        handle.handle_id for handle in task.result_refs.result_handles
                    ],
                    target_dataset_id=dataset.dataset_id,
                    target_design_id=design.design_id,
                    target_design_name=design.name,
                    published_at=published_at,
                )
                session.add(publication_row)
                session.flush()
            existing_trace_ids = {
                row.trace_id
                for row in session.scalars(
                    select(RewritePublishedSimulationTraceRecord).where(
                        RewritePublishedSimulationTraceRecord.publication_id == publication_row.id,
                        RewritePublishedSimulationTraceRecord.trace_id.in_(
                            [request.trace_id for request in requests]
                        ),
                    )
                ).all()
            }

        materialized_requests: list[_MaterializedPublishedTrace] = []
        for request in requests:
            if request.trace_id in existing_trace_ids:
                continue
            materialized = _materialize_published_trace(
                source_task=task,
                basis_task=basis_task,
                dataset_family=dataset.family,
                dataset_id=dataset.dataset_id,
                design_id=design.design_id,
                selection=request.selection,
                metric=draft.metric,
                trace_id=request.trace_id,
                saved_parameter=request.parameter_name,
                summary_parameter=request.parameter_name,
                summary_representation=None,
                result_handle_key=request.trace_id,
                result_handle_label=(
                    f"Published {request.parameter_name} {request.selection.source.upper()} trace"
                ),
                provenance_summary=_published_trace_provenance_summary(
                    task,
                    request.selection,
                ),
            )
            self._persist_materialized_trace_storage(materialized)
            materialized_requests.append(materialized)

        with self._session_factory() as session:
            publication_row = session.scalar(
                select(RewritePublishedSimulationResultRecord).where(
                    RewritePublishedSimulationResultRecord.source_task_id == task.task_id
                )
            )
            if publication_row is None:
                publication_row = RewritePublishedSimulationResultRecord(
                    publication_key=publication_key,
                    source_task_id=task.task_id,
                    source_dataset_id=task.dataset_id,
                    source_result_handle_ids=[
                        handle.handle_id for handle in task.result_refs.result_handles
                    ],
                    target_dataset_id=dataset.dataset_id,
                    target_design_id=design.design_id,
                    target_design_name=design.name,
                    published_at=published_at,
                )
                session.add(publication_row)
                session.flush()
            publication_row.published_at = published_at
            publication_row.target_design_name = design.name
            for request in materialized_requests:
                summary = request.summary
                detail = request.detail
                session.add(
                    RewritePublishedSimulationTraceRecord(
                        publication_id=publication_row.id,
                        dataset_id=dataset.dataset_id,
                        design_id=design.design_id,
                        trace_id=detail.trace_id,
                        family=summary.family,
                        parameter=summary.parameter,
                        representation=summary.representation,
                        trace_mode_group=summary.trace_mode_group,
                        source_kind=summary.source_kind,
                        stage_kind=summary.stage_kind,
                        provenance_summary=summary.provenance_summary,
                        axes_json=[
                            {
                                "name": axis.name,
                                "unit": axis.unit,
                                "length": axis.length,
                            }
                            for axis in detail.axes
                        ],
                        preview_payload_json=detail.preview_payload,
                        payload_store_key=cast(str, detail.payload_ref.store_key),
                        result_handle_id=detail.result_handles[0].handle_id,
                        published_at=published_at,
                    )
                )
                replace_trace_capabilities(
                    session,
                    dataset_id=dataset.dataset_id,
                    design_id=design.design_id,
                    trace_id=detail.trace_id,
                    capabilities=summary.analysis_capabilities,
                )
            session.commit()
        return self._load_result_trace_publication(
            dataset=dataset,
            design=design,
            publication_key=publication_key,
            state="published" if len(materialized_requests) > 0 else "already_published",
            trace_keys=tuple(request.trace_key for request in requests),
            trace_ids=tuple(request.trace_id for request in requests),
        )

    def list_designs(
        self,
        dataset_id: str,
    ) -> tuple[DesignBrowseRow, ...]:
        with self._session_factory() as session:
            created_design_rows = session.scalars(
                select(RewriteDatasetDesignRecord)
                .where(RewriteDatasetDesignRecord.dataset_id == dataset_id)
                .order_by(RewriteDatasetDesignRecord.design_id.asc())
            ).all()
            publication_rows = session.scalars(
                select(RewritePublishedSimulationResultRecord)
                .where(RewritePublishedSimulationResultRecord.target_dataset_id == dataset_id)
                .order_by(RewritePublishedSimulationResultRecord.target_design_id.asc())
            ).all()
            rows_by_design: dict[str, DesignBrowseRow] = {
                row.design_id: DesignBrowseRow(
                    design_id=row.design_id,
                    dataset_id=row.dataset_id,
                    name=row.name,
                    source_coverage=_empty_source_coverage(),
                    compare_readiness="blocked",
                    trace_count=0,
                    updated_at=row.updated_at,
                )
                for row in created_design_rows
            }
            if not publication_rows:
                return tuple(sorted(rows_by_design.values(), key=lambda row: row.design_id))
            publication_ids = [row.id for row in publication_rows]
            trace_rows = session.scalars(
                select(RewritePublishedSimulationTraceRecord)
                .where(RewritePublishedSimulationTraceRecord.publication_id.in_(publication_ids))
                .order_by(
                    RewritePublishedSimulationTraceRecord.design_id.asc(),
                    RewritePublishedSimulationTraceRecord.trace_id.asc(),
                )
            ).all()
            traces_by_design: dict[
                str, list[RewritePublishedSimulationTraceRecord]
            ] = defaultdict(list)
            for trace_row in trace_rows:
                traces_by_design[trace_row.design_id].append(trace_row)
            for publication_row in publication_rows:
                design_trace_rows = traces_by_design.get(publication_row.target_design_id, [])
                design_row = DesignBrowseRow(
                    design_id=publication_row.target_design_id,
                    dataset_id=dataset_id,
                    name=publication_row.target_design_name,
                    source_coverage=_build_source_coverage_from_trace_rows(
                        design_trace_rows
                    ),
                    compare_readiness=_compare_readiness_for_trace_rows(
                        design_trace_rows
                    ),
                    trace_count=len(design_trace_rows),
                    updated_at=publication_row.published_at,
                )
                existing = rows_by_design.get(design_row.design_id)
                if existing is None:
                    rows_by_design[design_row.design_id] = design_row
                    continue
                combined_coverage = {
                    key: existing.source_coverage.get(key, 0)
                    + design_row.source_coverage.get(key, 0)
                    for key in {
                        *existing.source_coverage.keys(),
                        *design_row.source_coverage.keys(),
                    }
                }
                rows_by_design[design_row.design_id] = DesignBrowseRow(
                    design_id=design_row.design_id,
                    dataset_id=dataset_id,
                    name=existing.name or design_row.name,
                    source_coverage=combined_coverage,
                    compare_readiness=_compare_readiness_for(combined_coverage),
                    trace_count=existing.trace_count + design_row.trace_count,
                    updated_at=max(existing.updated_at, design_row.updated_at),
                )
            return tuple(sorted(rows_by_design.values(), key=lambda row: row.design_id))

    def get_design(
        self,
        dataset_id: str,
        design_id: str,
    ) -> DesignBrowseRow | None:
        return next(
            (row for row in self.list_designs(dataset_id) if row.design_id == design_id),
            None,
        )

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[TraceMetadataSummary, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewritePublishedSimulationTraceRecord)
                .where(
                    RewritePublishedSimulationTraceRecord.dataset_id == dataset_id,
                    RewritePublishedSimulationTraceRecord.design_id == design_id,
                )
                .order_by(RewritePublishedSimulationTraceRecord.trace_id.asc())
            ).all()
            capability_map = self._load_or_materialize_trace_capability_map(
                session=session,
                dataset_id=dataset_id,
                design_id=design_id,
                trace_rows=rows,
            )
            return tuple(
                _to_trace_summary(
                    row,
                    analysis_capabilities=capability_map.get(row.trace_id, ()),
                )
                for row in rows
            )

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDetail | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewritePublishedSimulationTraceRecord).where(
                    RewritePublishedSimulationTraceRecord.dataset_id == dataset_id,
                    RewritePublishedSimulationTraceRecord.design_id == design_id,
                    RewritePublishedSimulationTraceRecord.trace_id == trace_id,
                )
            )
            if row is None:
                return None
            payload_ref = self._storage_metadata_repository.get_trace_payload(
                row.payload_store_key
            )
            result_handle = self._storage_metadata_repository.get_result_handle(
                row.result_handle_id
            )
            capability_map = self._load_or_materialize_trace_capability_map(
                session=session,
                dataset_id=dataset_id,
                design_id=design_id,
                trace_rows=(row,),
            )
            return TraceDetail(
                trace_id=row.trace_id,
                dataset_id=row.dataset_id,
                design_id=row.design_id,
                axes=tuple(
                    TraceAxis(
                        name=str(axis["name"]),
                        unit=str(axis["unit"]),
                        length=int(axis["length"]),
                    )
                    for axis in row.axes_json
                ),
                preview_payload=row.preview_payload_json,
                payload_ref=payload_ref,
                result_handles=((result_handle,) if result_handle is not None else ()),
                analysis_capabilities=capability_map.get(trace_id, ()),
            )

    def delete_traces(
        self,
        dataset_id: str,
        design_id: str,
        trace_ids: tuple[str, ...],
    ) -> tuple[str, ...] | None:
        requested = tuple(dict.fromkeys(trace_ids))
        if len(requested) == 0:
            return ()
        cleanup_refs: list[tuple[str, str]] = []
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewritePublishedSimulationTraceRecord)
                .where(
                    RewritePublishedSimulationTraceRecord.dataset_id == dataset_id,
                    RewritePublishedSimulationTraceRecord.design_id == design_id,
                    RewritePublishedSimulationTraceRecord.trace_id.in_(requested),
                )
                .order_by(RewritePublishedSimulationTraceRecord.id.asc())
            ).all()
            rows_by_trace_id = {row.trace_id: row for row in rows}
            if len(rows_by_trace_id) != len(requested):
                return None
            publication_ids = {row.publication_id for row in rows}
            for trace_id in requested:
                row = rows_by_trace_id[trace_id]
                cleanup_refs.append((row.payload_store_key, row.result_handle_id))
                session.delete(row)
            delete_trace_capabilities(
                session,
                dataset_id=dataset_id,
                design_id=design_id,
                trace_ids=requested,
            )
            session.flush()
            for publication_id in publication_ids:
                remaining = session.scalar(
                    select(RewritePublishedSimulationTraceRecord.id).where(
                        RewritePublishedSimulationTraceRecord.publication_id == publication_id
                    )
                )
                if remaining is not None:
                    continue
                publication_row = session.get(
                    RewritePublishedSimulationResultRecord,
                    publication_id,
                )
                if publication_row is not None:
                    session.delete(publication_row)
            session.commit()
        for payload_store_key, result_handle_id in cleanup_refs:
            self._storage_metadata_repository.delete_result_handle(result_handle_id)
            self._storage_metadata_repository.delete_trace_payload(payload_store_key)
            delete_trace_payload_store(payload_store_key)
        return requested

    def _persist_materialized_trace_storage(
        self,
        materialized: _MaterializedPublishedTrace,
    ) -> None:
        payload_ref = materialized.detail.payload_ref
        if payload_ref is None:
            raise ValueError("published simulation result is missing a trace payload")
        result_handle = materialized.detail.result_handles[0]
        trace_batch_record = result_handle.provenance.trace_batch_record
        if trace_batch_record is None:
            raise ValueError("published simulation result is missing storage metadata")
        self._storage_metadata_repository.save_trace_payload(trace_batch_record, payload_ref)
        self._storage_metadata_repository.save_result_handle(result_handle)

    def _load_publication_result(
        self,
        *,
        task: TaskDetail,
        dataset: DatasetDetail,
        publication_key: str,
        state: str,
    ) -> SimulationResultPublicationResult:
        with self._session_factory() as session:
            publication_row = session.scalar(
                select(RewritePublishedSimulationResultRecord).where(
                    RewritePublishedSimulationResultRecord.publication_key == publication_key
                )
            )
            if publication_row is None:
                raise ValueError("published simulation result record was not found")
            trace_rows = session.scalars(
                select(RewritePublishedSimulationTraceRecord)
                .where(RewritePublishedSimulationTraceRecord.publication_id == publication_row.id)
                .order_by(RewritePublishedSimulationTraceRecord.id.asc())
            ).all()
            capability_map = self._load_or_materialize_trace_capability_map(
                session=session,
                dataset_id=dataset.dataset_id,
                design_id=publication_row.target_design_id,
                trace_rows=trace_rows,
            )
            trace_summaries = tuple(
                _to_trace_summary(
                    row,
                    analysis_capabilities=capability_map.get(row.trace_id, ()),
                )
                for row in trace_rows
            )
            return SimulationResultPublicationResult(
                state=cast(str, state),
                publication_key=publication_row.publication_key,
                published_at=publication_row.published_at,
                dataset=replace(dataset, updated_at=publication_row.published_at),
                design=DesignBrowseRow(
                    design_id=publication_row.target_design_id,
                    dataset_id=publication_row.target_dataset_id,
                    name=publication_row.target_design_name,
                    source_coverage=_build_source_coverage(trace_summaries),
                    compare_readiness=_compare_readiness_for(_build_source_coverage(trace_summaries)),
                    trace_count=len(trace_summaries),
                    updated_at=publication_row.published_at,
                ),
                traces=trace_summaries,
            )

    def _load_result_trace_publication(
        self,
        *,
        dataset: DatasetDetail,
        design: DesignBrowseRow,
        publication_key: str,
        state: str,
        trace_keys: tuple[str, ...],
        trace_ids: tuple[str, ...],
    ) -> ResultTracePublicationResult:
        with self._session_factory() as session:
            publication_row = session.scalar(
                select(RewritePublishedSimulationResultRecord).where(
                    RewritePublishedSimulationResultRecord.publication_key == publication_key
                )
            )
            if publication_row is None:
                raise ValueError("published simulation result record was not found")
            publication_trace_rows = session.scalars(
                select(RewritePublishedSimulationTraceRecord)
                .where(
                    RewritePublishedSimulationTraceRecord.publication_id == publication_row.id
                )
                .order_by(RewritePublishedSimulationTraceRecord.id.asc())
            ).all()
            capability_map = self._load_or_materialize_trace_capability_map(
                session=session,
                dataset_id=dataset.dataset_id,
                design_id=design.design_id,
                trace_rows=publication_trace_rows,
            )
            trace_summaries = tuple(
                _to_trace_summary(
                    row,
                    analysis_capabilities=capability_map.get(row.trace_id, ()),
                )
                for row in publication_trace_rows
            )
            trace_rows_by_id = {row.trace_id: row for row in publication_trace_rows}
            requested_trace_rows = [
                trace_rows_by_id[trace_id] for trace_id in trace_ids if trace_id in trace_rows_by_id
            ]
            if len(requested_trace_rows) != len(trace_ids):
                raise ValueError("published result trace record was not found")
            return ResultTracePublicationResult(
                state=cast(str, state),
                publication_key=publication_row.publication_key,
                published_at=publication_row.published_at,
                dataset=replace(dataset, updated_at=publication_row.published_at),
                design=DesignBrowseRow(
                    design_id=design.design_id,
                    dataset_id=design.dataset_id,
                    name=design.name,
                    source_coverage=_build_source_coverage(trace_summaries),
                    compare_readiness=_compare_readiness_for(_build_source_coverage(trace_summaries)),
                    trace_count=len(trace_summaries),
                    updated_at=publication_row.published_at,
                ),
                trace_keys=trace_keys,
                traces=tuple(
                    _to_trace_summary(
                        row,
                        analysis_capabilities=capability_map.get(row.trace_id, ()),
                    )
                    for row in requested_trace_rows
                ),
            )

    def _load_or_materialize_trace_capability_map(
        self,
        *,
        session: Session,
        dataset_id: str,
        design_id: str,
        trace_rows: Sequence[RewritePublishedSimulationTraceRecord],
    ) -> dict[str, tuple[TraceAnalysisCapability, ...]]:
        trace_ids = tuple(row.trace_id for row in trace_rows)
        if len(trace_ids) == 0:
            return {}
        capability_map = load_trace_capability_map(
            session,
            dataset_id=dataset_id,
            design_id=design_id,
            trace_ids=trace_ids,
        )
        missing_rows = [row for row in trace_rows if row.trace_id not in capability_map]
        if len(missing_rows) == 0:
            return capability_map
        dataset_row = session.scalar(
            select(RewriteDatasetRecord).where(RewriteDatasetRecord.dataset_id == dataset_id)
        )
        if dataset_row is None:
            return capability_map
        for row in missing_rows:
            capabilities = evaluate_trace_analysis_capabilities(
                dataset_family=dataset_row.family,
                trace=_to_trace_summary(row),
                axes=tuple(
                    TraceAxis(
                        name=str(axis["name"]),
                        unit=str(axis["unit"]),
                        length=int(axis["length"]),
                    )
                    for axis in row.axes_json
                ),
            )
            replace_trace_capabilities(
                session,
                dataset_id=row.dataset_id,
                design_id=row.design_id,
                trace_id=row.trace_id,
                capabilities=capabilities,
            )
            capability_map[row.trace_id] = capabilities
        session.commit()
        return capability_map


@dataclass(frozen=True)
class _RequestedTracePublication:
    trace_key: str
    selection: ResultTraceSelection
    parameter_name: str
    trace_id: str


@dataclass(frozen=True)
class _MaterializedPublishedTrace:
    summary: TraceMetadataSummary
    detail: TraceDetail


@dataclass(frozen=True)
class _PublishedMetricSpec:
    metric: str
    series_id: str
    representation: str
    y_label: str
    y_unit: str | None


def _build_requested_trace_publications(
    *,
    task: TaskDetail,
    basis_task: TaskDetail,
    draft: ResultTracePublicationDraft,
) -> tuple[_RequestedTracePublication, ...]:
    unique_trace_keys = tuple(dict.fromkeys(draft.trace_keys))
    if len(unique_trace_keys) == 0:
        raise ValueError("result trace publication requires at least one trace_key")
    selections = tuple(
        ResultTraceSelection.from_trace_key(trace_key)
        for trace_key in unique_trace_keys
    )
    _validate_publication_selection_group(selections)
    parameter_names = _resolve_requested_parameter_names(
        basis_task=basis_task,
        selections=selections,
        parameter_name=draft.parameter_name,
    )
    requests: list[_RequestedTracePublication] = []
    for trace_key, selection, saved_parameter in zip(
        unique_trace_keys,
        selections,
        parameter_names,
        strict=True,
    ):
        requests.append(
            _RequestedTracePublication(
                trace_key=trace_key,
                selection=selection,
                parameter_name=saved_parameter,
                trace_id=build_trace_id(
                    task_id=task.task_id,
                    selection=selection,
                    parameter_name=saved_parameter,
                ),
            )
        )
    return tuple(requests)


def _validate_publication_selection_group(
    selections: tuple[ResultTraceSelection, ...],
) -> None:
    primary = selections[0]
    primary_signature = (
        primary.family,
        primary.source,
        primary.output_port,
        primary.input_port,
        primary.trace_mode_group,
        primary.output_mode,
        primary.input_mode,
        primary.z0_ohm,
    )
    for selection in selections[1:]:
        selection_signature = (
            selection.family,
            selection.source,
            selection.output_port,
            selection.input_port,
            selection.trace_mode_group,
            selection.output_mode,
            selection.input_mode,
            selection.z0_ohm,
        )
        if selection_signature != primary_signature:
            raise ValueError(
                "Visible trace publication requires selections from the same explorer view."
            )


def _resolve_requested_parameter_names(
    *,
    basis_task: TaskDetail,
    selections: tuple[ResultTraceSelection, ...],
    parameter_name: str | None,
) -> tuple[str, ...]:
    if len(selections) == 1:
        return (resolve_saved_trace_parameter(selections[0], parameter_name),)

    base_parameter = (
        " ".join(part for part in (parameter_name or "").strip().split() if len(part) > 0)
        or build_trace_parameter(selections[0])
    )
    suffixes = _build_selection_suffixes(
        basis_task=basis_task,
        selections=selections,
    )
    return tuple(
        (
            f"{base_parameter} · {suffix}"
            if len(suffix) > 0
            else f"{base_parameter} · Trace {index + 1}"
        )
        for index, suffix in enumerate(suffixes)
    )


def _build_selection_suffixes(
    *,
    basis_task: TaskDetail,
    selections: tuple[ResultTraceSelection, ...],
) -> tuple[str, ...]:
    setup = basis_task.simulation_setup
    if setup is None or len(setup.parameter_sweeps) == 0:
        return tuple("" for _ in selections)

    coordinates = [
        _decode_sweep_coordinates(setup, selection.sweep_index)
        for selection in selections
    ]
    varying_axes = [
        axis_index
        for axis_index, sweep in enumerate(setup.parameter_sweeps)
        if len({point[axis_index] for point in coordinates}) > 1 and len(sweep.values) > 0
    ]
    if len(varying_axes) == 0:
        return tuple("" for _ in selections)

    suffixes: list[str] = []
    for point in coordinates:
        parts: list[str] = []
        for axis_index in varying_axes:
            sweep = setup.parameter_sweeps[axis_index]
            coordinate = min(max(point[axis_index], 0), max(len(sweep.values) - 1, 0))
            parts.append(
                _format_selection_suffix(
                    sweep.parameter,
                    float(sweep.values[coordinate]),
                    sweep.unit,
                )
            )
        suffixes.append(" · ".join(parts))
    return tuple(suffixes)


def _decode_sweep_coordinates(
    setup: SimulationSetup,
    sweep_index: int | None,
) -> tuple[int, ...]:
    if len(setup.parameter_sweeps) == 0:
        return ()

    resolved_index = sweep_index or 0
    coordinates = [0] * len(setup.parameter_sweeps)
    remaining = resolved_index
    for axis_index in range(len(setup.parameter_sweeps) - 1, -1, -1):
        axis_size = max(len(setup.parameter_sweeps[axis_index].values), 1)
        coordinates[axis_index] = remaining % axis_size
        remaining //= axis_size
    return tuple(coordinates)


def _format_selection_suffix(parameter: str, value: float, unit: str | None) -> str:
    compact_value = (
        str(int(value))
        if float(value).is_integer()
        else format(float(value), ".6f").rstrip("0").rstrip(".")
    )
    if unit:
        return f"{parameter} = {compact_value} {unit}"
    return f"{parameter} = {compact_value}"


def _build_published_trace_preview_payload(
    *,
    task: TaskDetail,
    selection: ResultTraceSelection,
    metric_spec: _PublishedMetricSpec | None,
    saved_parameter: str,
    trace_data,
) -> dict[str, object]:
    preview = build_trace_preview_payload(
        selection=selection,
        trace_data=trace_data,
    )
    preview["kind"] = "series"
    preview["family"] = selection.family
    preview["source"] = selection.source
    preview["parameter"] = saved_parameter
    preview["default_parameter"] = build_trace_parameter(selection)
    preview["output_port"] = selection.output_port
    preview["input_port"] = selection.input_port
    preview["trace_mode_group"] = selection.trace_mode_group
    preview["output_mode"] = selection.output_mode
    preview["input_mode"] = selection.input_mode
    if metric_spec is not None:
        preview["metric"] = metric_spec.metric
        preview["preferred_series_id"] = metric_spec.series_id
        preview["y_axis"] = {
            "label": metric_spec.y_label,
            "unit": metric_spec.y_unit,
        }
        preview["context"] = {
            "family": selection.family,
            "family_label": _family_label(selection.family),
            "origin_kind": trace_data.source_kind,
            "origin_label": _origin_kind_label(cast(str, trace_data.source_kind)),
            "source": selection.source,
            "source_label": _selection_source_label(selection.source),
            "metric": metric_spec.metric,
            "metric_label": metric_spec.y_label,
            "metric_unit": metric_spec.y_unit,
            "output_port": selection.output_port,
            "input_port": selection.input_port,
            "port_label": f"Port {selection.output_port} -> Port {selection.input_port}",
        }
    preview["history_steps"] = _build_trace_history_steps(task=task, selection=selection)
    preview["history_summary"] = " -> ".join(preview["history_steps"])
    if metric_spec is None:
        preview["points"] = [
            [float(frequency), float(value.real), float(value.imag)]
            for frequency, value in zip(
                trace_data.frequencies_ghz,
                trace_data.values,
                strict=True,
            )
        ]
    else:
        preview["points"] = [
            [float(frequency), _metric_value_for_trace(metric_spec, value)]
            for frequency, value in zip(
                trace_data.frequencies_ghz,
                trace_data.values,
                strict=True,
            )
        ]
    return preview


def _legacy_bundle_publication_targets(task: TaskDetail) -> tuple[tuple[str, str], ...]:
    targets: list[tuple[str, str]] = [
        ("s_matrix", "raw"),
        ("y_matrix", "raw"),
        ("z_matrix", "raw"),
    ]
    if "ptc" in available_sources_for_task_family(task, "y_matrix"):
        targets.extend((("y_matrix", "ptc"), ("z_matrix", "ptc")))
    return tuple(targets)


def _build_persisted_simulation_publication_trace(
    *,
    task: TaskDetail,
    dataset_family: str,
    dataset_id: str,
    design_id: str,
    family: str,
    source: str,
) -> tuple[TraceMetadataSummary, TraceDetail]:
    selection = ResultTraceSelection(
        family=family,
        source=source,
        output_port=1,
        input_port=1,
        z0_ohm=50.0 if family in {"y_matrix", "z_matrix"} else None,
    )
    materialized = _materialize_published_trace(
        source_task=task,
        basis_task=task,
        dataset_family=dataset_family,
        dataset_id=dataset_id,
        design_id=design_id,
        selection=selection,
        metric=None,
        trace_id=f"trace_simulation_task_{task.task_id}_{family}_{source}",
        saved_parameter=build_trace_parameter(selection),
        summary_parameter=source,
        summary_representation="complex_matrix",
        result_handle_key=f"{family}:{source}",
        result_handle_label=f"Published {family.upper()} {source.upper()} result",
        provenance_summary=f"Published from simulation task {task.task_id}",
    )
    return materialized.summary, materialized.detail


def _build_trace_history_steps(
    *,
    task: TaskDetail,
    selection: ResultTraceSelection,
) -> list[str]:
    history = ["PTC" if selection.source == "ptc" else "Raw"]
    if task.kind != "post_processing" or task.post_processing_setup is None:
        return history
    for operation in task.post_processing_setup.operations:
        if not operation.enabled:
            continue
        history.append(_humanize_post_processing_operation(operation.operation))
    return history


def _humanize_post_processing_operation(operation: str) -> str:
    if operation == "coordinate_transform":
        return "Coordinate Transformation"
    if operation == "kron_reduction":
        return "Kron Reduction"
    return operation.replace("_", " ").title()


def _published_trace_provenance_summary(
    task: TaskDetail,
    selection: ResultTraceSelection,
) -> str:
    if task.kind == "post_processing":
        return (
            f"Published from post-processing task {task.task_id} "
            f"({selection.source.upper()} {build_trace_parameter(selection)})"
        )
    return f"Published from simulation task {task.task_id}"


def _materialize_published_trace(
    *,
    source_task: TaskDetail,
    basis_task: TaskDetail,
    dataset_family: str,
    dataset_id: str,
    design_id: str,
    selection: ResultTraceSelection,
    metric: str | None,
    trace_id: str,
    saved_parameter: str,
    summary_parameter: str,
    summary_representation: str | None,
    result_handle_key: str,
    result_handle_label: str,
    provenance_summary: str,
) -> _MaterializedPublishedTrace:
    trace_data = extract_selection_trace_data(
        source_task,
        basis_task=basis_task,
        selection=selection,
    )
    metric_spec = (
        _resolve_published_metric_spec(
            family=selection.family,
            metric=metric,
        )
        if metric is not None
        else None
    )
    payload_ref = write_complex_trace_payload(
        dataset_id=dataset_id,
        design_id=design_id,
        trace_id=trace_id,
        frequencies_ghz=trace_data.frequencies_ghz,
        values=trace_data.values,
    )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:published:{source_task.task_id}:{dataset_id}:{design_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:published:{source_task.task_id}:{result_handle_key}",
        version=2,
    )
    result_handle = build_result_handle_ref(
        handle_id=f"published-result:{source_task.task_id}:{result_handle_key}",
        kind="simulation_trace",
        status="materialized",
        label=result_handle_label,
        metadata_record=result_handle_record,
        payload_backend="local_zarr",
        payload_format="zarr",
        payload_role="trace_payload",
        payload_locator=payload_ref.store_uri or payload_ref.store_key,
        provenance_task_id=source_task.task_id,
        provenance=build_result_provenance_ref(
            source_dataset_id=source_task.dataset_id,
            source_task_id=source_task.task_id,
            trace_batch_record=trace_batch_record,
        ),
    )
    summary = TraceMetadataSummary(
        trace_id=trace_id,
        dataset_id=dataset_id,
        design_id=design_id,
        family=selection.family,
        parameter=summary_parameter,
        representation=summary_representation
        or (metric_spec.representation if metric_spec is not None else "complex"),
        trace_mode_group=selection.trace_mode_group,
        source_kind=cast(str, trace_data.source_kind),
        stage_kind=cast(str, trace_data.stage_kind),
        provenance_summary=provenance_summary,
    )
    analysis_capabilities = evaluate_trace_analysis_capabilities(
        dataset_family=dataset_family,
        trace=summary,
        axes=(
            TraceAxis(
                name="frequency",
                unit="GHz",
                length=len(trace_data.frequencies_ghz),
            ),
        ),
    )
    detail = TraceDetail(
        trace_id=trace_id,
        dataset_id=dataset_id,
        design_id=design_id,
        axes=(
            TraceAxis(
                name="frequency",
                unit="GHz",
                length=len(trace_data.frequencies_ghz),
            ),
        ),
        preview_payload=_build_published_trace_preview_payload(
            task=source_task,
            selection=selection,
            metric_spec=metric_spec,
            saved_parameter=saved_parameter,
            trace_data=trace_data,
        ),
        payload_ref=payload_ref,
        result_handles=(result_handle,),
        analysis_capabilities=analysis_capabilities,
    )
    return _MaterializedPublishedTrace(
        summary=replace(summary, analysis_capabilities=analysis_capabilities),
        detail=detail,
    )


def _resolve_published_metric_spec(*, family: str, metric: str) -> _PublishedMetricSpec:
    if family == "s_matrix":
        if metric == "magnitude_db":
            return _PublishedMetricSpec(
                metric=metric,
                series_id="magnitude_db",
                representation="magnitude",
                y_label="Magnitude",
                y_unit="dB",
            )
        if metric == "phase_deg":
            return _PublishedMetricSpec(
                metric=metric,
                series_id="phase_deg",
                representation="phase",
                y_label="Phase",
                y_unit="deg",
            )
        if metric == "real":
            return _PublishedMetricSpec(
                metric=metric,
                series_id="real",
                representation="real",
                y_label="Real",
                y_unit="unitless",
            )
        if metric == "imag":
            return _PublishedMetricSpec(
                metric=metric,
                series_id="imaginary",
                representation="imaginary",
                y_label="Imaginary",
                y_unit="unitless",
            )
    if family in {"y_matrix", "z_matrix"}:
        unit = "S" if family == "y_matrix" else "ohm"
        if metric == "magnitude":
            return _PublishedMetricSpec(
                metric=metric,
                series_id="magnitude",
                representation="magnitude",
                y_label="Magnitude",
                y_unit=unit,
            )
        if metric == "real":
            return _PublishedMetricSpec(
                metric=metric,
                series_id="real",
                representation="real",
                y_label="Real",
                y_unit=unit,
            )
        if metric == "imag":
            return _PublishedMetricSpec(
                metric=metric,
                series_id="imaginary",
                representation="imaginary",
                y_label="Imaginary",
                y_unit=unit,
            )
    raise ValueError(f"Unsupported published metric '{metric}' for family '{family}'.")


def _metric_value_for_trace(metric_spec: _PublishedMetricSpec, value: complex) -> float:
    if metric_spec.metric == "real":
        return float(value.real)
    if metric_spec.metric == "imag":
        return float(value.imag)
    if metric_spec.metric == "magnitude":
        return float(abs(value))
    if metric_spec.metric == "magnitude_db":
        return float(20 * math.log10(max(abs(value), 1e-12)))
    if metric_spec.metric == "phase_deg":
        return float(math.degrees(math.atan2(value.imag, value.real)))
    raise ValueError(f"Unsupported published metric '{metric_spec.metric}'.")


def _family_label(family: str) -> str:
    if family == "s_matrix":
        return "S Matrix"
    if family == "y_matrix":
        return "Y Matrix"
    if family == "z_matrix":
        return "Z Matrix"
    return family


def _selection_source_label(source: str) -> str:
    if source == "ptc":
        return "PTC"
    if source == "raw":
        return "Raw"
    return source


def _origin_kind_label(source_kind: str) -> str:
    if source_kind == "circuit_simulation":
        return "Circuit sim"
    if source_kind == "layout_simulation":
        return "Layout sim"
    if source_kind == "measurement":
        return "Measurement"
    return source_kind


def _to_publication_record(
    row: RewritePublishedSimulationResultRecord,
    trace_rows: list[RewritePublishedSimulationTraceRecord],
) -> SimulationResultPublicationRecord:
    return SimulationResultPublicationRecord(
        publication_key=row.publication_key,
        published_at=row.published_at,
        source_task_id=row.source_task_id,
        source_dataset_id=row.source_dataset_id,
        source_result_handle_ids=tuple(row.source_result_handle_ids),
        target_dataset_id=row.target_dataset_id,
        target_design_id=row.target_design_id,
        target_design_name=row.target_design_name,
        published_trace_ids=tuple(trace_row.trace_id for trace_row in trace_rows),
    )


def _to_trace_summary(
    row: RewritePublishedSimulationTraceRecord,
    *,
    analysis_capabilities: tuple[TraceAnalysisCapability, ...] = (),
) -> TraceMetadataSummary:
    return TraceMetadataSummary(
        trace_id=row.trace_id,
        dataset_id=row.dataset_id,
        design_id=row.design_id,
        family=cast(str, row.family),
        parameter=row.parameter,
        representation=row.representation,
        trace_mode_group=cast(str, row.trace_mode_group),
        source_kind=cast(str, row.source_kind),
        stage_kind=cast(str, row.stage_kind),
        provenance_summary=row.provenance_summary,
        analysis_capabilities=analysis_capabilities,
    )


def _build_simulation_publication_key(
    *,
    task_id: int,
    dataset_id: str,
    design_id: str,
) -> str:
    return f"simulation-publication:{task_id}:{dataset_id}:{design_id}"


def _build_design_id(name: str) -> str:
    return f"design_{_slugify(name)}"


def _slugify(value: str) -> str:
    return "-".join(
        token
        for token in "".join(
            character.lower() if character.isalnum() else "-"
            for character in value.strip()
        ).split("-")
        if token
    )


def _build_source_coverage(
    traces: tuple[TraceMetadataSummary, ...],
) -> dict[str, int]:
    coverage = _empty_source_coverage()
    for trace in traces:
        coverage[trace.source_kind] = coverage.get(trace.source_kind, 0) + 1
    return coverage


def _build_source_coverage_from_trace_rows(
    trace_rows: list[RewritePublishedSimulationTraceRecord],
) -> dict[str, int]:
    coverage = _empty_source_coverage()
    for trace in trace_rows:
        coverage[trace.source_kind] = coverage.get(trace.source_kind, 0) + 1
    return coverage


def _compare_readiness_for(
    source_coverage: dict[str, int],
) -> str:
    if (
        source_coverage.get("measurement", 0) > 0
        and source_coverage.get("layout_simulation", 0) > 0
    ):
        return "ready"
    if sum(source_coverage.values()) > 0:
        return "inspect_only"
    return "blocked"


def _compare_readiness_for_trace_rows(
    trace_rows: list[RewritePublishedSimulationTraceRecord],
) -> str:
    return _compare_readiness_for(_build_source_coverage_from_trace_rows(trace_rows))


def _empty_source_coverage() -> dict[str, int]:
    return {
        "measurement": 0,
        "layout_simulation": 0,
        "circuit_simulation": 0,
    }


def _normalize_design_name(value: str) -> str:
    return value.strip().casefold()


def _timestamp_now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
