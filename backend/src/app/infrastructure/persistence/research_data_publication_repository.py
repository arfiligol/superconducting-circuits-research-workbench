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
from src.app.domain.result_traces import ResultTraceSelection
from src.app.domain.tasks import TaskDetail
from src.app.infrastructure.persistence.models import (
    RewriteDatasetDesignRecord,
    RewritePublishedSimulationResultRecord,
    RewritePublishedSimulationTraceRecord,
)
from src.app.infrastructure.persistence.storage_metadata_repository import (
    SqliteRewriteStorageMetadataRepository,
)
from src.app.infrastructure.simulation_result_publication_materializer import (
    build_result_trace_publication_detail,
    build_result_trace_publication_summary,
    build_simulation_publication_key,
    build_simulation_publication_trace_details,
    build_simulation_publication_trace_summary,
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
        publication_key = build_simulation_publication_key(
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

        published_at = "2026-03-19T11:30:00Z"
        trace_details = build_simulation_publication_trace_details(
            task=task,
            dataset_id=dataset.dataset_id,
            design_id=design_id,
        )
        for _, _, detail in trace_details:
            payload_ref = detail.payload_ref
            result_handle = detail.result_handles[0]
            trace_batch_record = result_handle.provenance.trace_batch_record
            if payload_ref is None or trace_batch_record is None:
                raise ValueError("published simulation result is missing storage metadata")
            self._storage_metadata_repository.save_trace_payload(
                trace_batch_record,
                payload_ref,
            )
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
            for family, source, detail in trace_details:
                summary = build_simulation_publication_trace_summary(
                    detail=detail,
                    task=task,
                    family=family,
                    source=source,
                )
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
        selection = ResultTraceSelection.from_trace_key(draft.trace_key)
        publication_key = build_simulation_publication_key(
            task_id=task.task_id,
            dataset_id=dataset.dataset_id,
            design_id=design.design_id,
        )
        published_at = _timestamp_now()
        detail = build_result_trace_publication_detail(
            task=task,
            basis_task=basis_task,
            dataset_id=dataset.dataset_id,
            design_id=design.design_id,
            selection=selection,
        )
        summary = build_result_trace_publication_summary(
            task=task,
            detail=detail,
            selection=selection,
        )
        payload_ref = detail.payload_ref
        result_handle = detail.result_handles[0]
        trace_batch_record = result_handle.provenance.trace_batch_record
        if payload_ref is None or trace_batch_record is None:
            raise ValueError("published result trace is missing storage metadata")
        self._storage_metadata_repository.save_trace_payload(trace_batch_record, payload_ref)
        self._storage_metadata_repository.save_result_handle(result_handle)

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

            existing_trace_row = session.scalar(
                select(RewritePublishedSimulationTraceRecord).where(
                    RewritePublishedSimulationTraceRecord.publication_id == publication_row.id,
                    RewritePublishedSimulationTraceRecord.trace_id == detail.trace_id,
                )
            )
            if existing_trace_row is not None:
                return self._load_result_trace_publication(
                    dataset=dataset,
                    design=design,
                    publication_key=publication_key,
                    state="already_published",
                    trace_key=draft.trace_key,
                    trace_id=existing_trace_row.trace_id,
                )
            publication_row.published_at = published_at
            publication_row.target_design_name = design.name
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
            state="published",
            trace_key=draft.trace_key,
            trace_id=detail.trace_id,
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
        trace_key: str,
        trace_id: str,
    ) -> ResultTracePublicationResult:
        with self._session_factory() as session:
            publication_row = session.scalar(
                select(RewritePublishedSimulationResultRecord).where(
                    RewritePublishedSimulationResultRecord.publication_key == publication_key
                )
            )
            if publication_row is None:
                raise ValueError("published simulation result record was not found")
            trace_row = session.scalar(
                select(RewritePublishedSimulationTraceRecord).where(
                    RewritePublishedSimulationTraceRecord.publication_id == publication_row.id,
                    RewritePublishedSimulationTraceRecord.trace_id == trace_id,
                )
            )
            if trace_row is None:
                raise ValueError("published result trace record was not found")
            trace_summaries = tuple(
                _to_trace_summary(row)
                for row in session.scalars(
                    select(RewritePublishedSimulationTraceRecord)
                    .where(
                        RewritePublishedSimulationTraceRecord.publication_id
                        == publication_row.id
                    )
                    .order_by(RewritePublishedSimulationTraceRecord.id.asc())
                ).all()
            )
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
                trace_key=trace_key,
                trace=_to_trace_summary(trace_row),
            )


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
