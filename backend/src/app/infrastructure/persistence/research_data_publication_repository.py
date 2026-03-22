from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from src.app.domain.datasets import (
    DatasetDetail,
    DesignBrowseRow,
    DesignCreateDraft,
    ResultTracePublicationDraft,
    ResultTracePublicationResult,
    SimulationResultPublicationDraft,
    SimulationResultPublicationRecord,
    SimulationResultPublicationResult,
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
    extract_selection_trace_data,
    write_complex_trace_payload,
)
from src.app.infrastructure.persistence.models import (
    RewriteDatasetDesignRecord,
    RewritePublishedSimulationResultRecord,
    RewritePublishedSimulationTraceRecord,
)
from src.app.infrastructure.persistence.storage_metadata_repository import (
    SqliteRewriteStorageMetadataRepository,
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
                            [request["trace_id"] for request in requests]
                        ),
                    )
                ).all()
            }

        materialized_requests: list[dict[str, object]] = []
        for request in requests:
            if request["trace_id"] in existing_trace_ids:
                continue
            selection = cast(ResultTraceSelection, request["selection"])
            saved_parameter = cast(str, request["parameter_name"])
            trace_id = cast(str, request["trace_id"])
            trace_data = extract_selection_trace_data(
                task,
                basis_task=basis_task,
                selection=selection,
            )
            payload_ref = write_complex_trace_payload(
                dataset_id=dataset.dataset_id,
                design_id=design.design_id,
                trace_id=trace_id,
                frequencies_ghz=trace_data.frequencies_ghz,
                values=trace_data.values,
            )
            trace_batch_record = build_metadata_record_ref(
                "trace_batch",
                f"trace_batch:published:{task.task_id}:{design.dataset_id}:{design.design_id}",
                version=1,
            )
            result_handle_record = build_metadata_record_ref(
                "result_handle",
                f"result_handle:published:{task.task_id}:{trace_id}",
                version=2,
            )
            result_handle = build_result_handle_ref(
                handle_id=f"published-result:{task.task_id}:{trace_id}",
                kind="simulation_trace",
                status="materialized",
                label=f"Published {saved_parameter} {selection.source.upper()} trace",
                metadata_record=result_handle_record,
                payload_backend="local_zarr",
                payload_format="zarr",
                payload_role="trace_payload",
                payload_locator=payload_ref.store_uri or payload_ref.store_key,
                provenance_task_id=task.task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=task.dataset_id,
                    source_task_id=task.task_id,
                    trace_batch_record=trace_batch_record,
                ),
            )
            detail = TraceDetail(
                trace_id=trace_id,
                dataset_id=dataset.dataset_id,
                design_id=design.design_id,
                axes=(
                    TraceAxis(
                        name="frequency",
                        unit="GHz",
                        length=len(trace_data.frequencies_ghz),
                    ),
                ),
                preview_payload=_build_published_trace_preview_payload(
                    task=task,
                    selection=selection,
                    saved_parameter=saved_parameter,
                    trace_data=trace_data,
                ),
                payload_ref=payload_ref,
                result_handles=(result_handle,),
            )
            summary = TraceMetadataSummary(
                trace_id=trace_id,
                dataset_id=dataset.dataset_id,
                design_id=design.design_id,
                family=selection.family,
                parameter=saved_parameter,
                representation="complex",
                trace_mode_group=selection.trace_mode_group,
                source_kind=cast(str, trace_data.source_kind),
                stage_kind=cast(str, trace_data.stage_kind),
                provenance_summary=_published_trace_provenance_summary(task, selection),
            )
            self._storage_metadata_repository.save_trace_payload(trace_batch_record, payload_ref)
            self._storage_metadata_repository.save_result_handle(result_handle)
            materialized_requests.append(
                {
                    "trace_id": trace_id,
                    "summary": summary,
                    "detail": detail,
                }
            )

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
                summary = cast(TraceMetadataSummary, request["summary"])
                detail = cast(TraceDetail, request["detail"])
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
            session.commit()
        return self._load_result_trace_publication(
            dataset=dataset,
            design=design,
            publication_key=publication_key,
            state="published" if len(materialized_requests) > 0 else "already_published",
            trace_keys=tuple(cast(str, request["trace_key"]) for request in requests),
            trace_ids=tuple(cast(str, request["trace_id"]) for request in requests),
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
            return tuple(_to_trace_summary(row) for row in rows)

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
            )

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
            trace_summaries = tuple(_to_trace_summary(row) for row in trace_rows)
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
            trace_summaries = tuple(_to_trace_summary(row) for row in publication_trace_rows)
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
                traces=tuple(_to_trace_summary(row) for row in requested_trace_rows),
            )


def _build_requested_trace_publications(
    *,
    task: TaskDetail,
    basis_task: TaskDetail,
    draft: ResultTracePublicationDraft,
) -> tuple[dict[str, object], ...]:
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
    requests: list[dict[str, object]] = []
    for trace_key, selection, saved_parameter in zip(
        unique_trace_keys,
        selections,
        parameter_names,
        strict=True,
    ):
        requests.append(
            {
                "trace_key": trace_key,
                "selection": selection,
                "parameter_name": saved_parameter,
                "trace_id": build_trace_id(
                    task_id=task.task_id,
                    selection=selection,
                    parameter_name=saved_parameter,
                ),
            }
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
    preview["history_steps"] = _build_trace_history_steps(task=task, selection=selection)
    preview["history_summary"] = " -> ".join(preview["history_steps"])
    preview["points"] = [
        [float(frequency), float(value.real), float(value.imag)]
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
    trace_data = extract_selection_trace_data(
        task,
        basis_task=task,
        selection=selection,
    )
    trace_id = f"trace_simulation_task_{task.task_id}_{family}_{source}"
    payload_ref = write_complex_trace_payload(
        dataset_id=dataset_id,
        design_id=design_id,
        trace_id=trace_id,
        frequencies_ghz=trace_data.frequencies_ghz,
        values=trace_data.values,
    )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        f"trace_batch:published:{task.task_id}:{dataset_id}:{design_id}",
        version=1,
    )
    result_handle_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:published:{task.task_id}:{family}:{source}",
        version=2,
    )
    result_handle = build_result_handle_ref(
        handle_id=f"published-result:{task.task_id}:{family}:{source}",
        kind="simulation_trace",
        status="materialized",
        label=f"Published {family.upper()} {source.upper()} result",
        metadata_record=result_handle_record,
        payload_backend="local_zarr",
        payload_format="zarr",
        payload_role="trace_payload",
        payload_locator=payload_ref.store_uri or payload_ref.store_key,
        provenance_task_id=task.task_id,
        provenance=build_result_provenance_ref(
            source_dataset_id=task.dataset_id,
            source_task_id=task.task_id,
            trace_batch_record=trace_batch_record,
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
            task=task,
            selection=selection,
            saved_parameter=build_trace_parameter(selection),
            trace_data=trace_data,
        ),
        payload_ref=payload_ref,
        result_handles=(result_handle,),
    )
    summary = TraceMetadataSummary(
        trace_id=detail.trace_id,
        dataset_id=dataset_id,
        design_id=design_id,
        family=family,
        parameter=source,
        representation="complex_matrix",
        trace_mode_group=selection.trace_mode_group,
        source_kind=cast(str, trace_data.source_kind),
        stage_kind=cast(str, trace_data.stage_kind),
        provenance_summary=f"Published from simulation task {task.task_id}",
    )
    return summary, detail


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


def _to_trace_summary(row: RewritePublishedSimulationTraceRecord) -> TraceMetadataSummary:
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
