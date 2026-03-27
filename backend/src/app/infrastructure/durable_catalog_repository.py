from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.app.domain.characterization_analysis import (
    evaluate_trace_analysis_capabilities,
)
from src.app.domain.circuit_definitions import CircuitDefinitionRecord
from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryRow,
    CharacterizationAnalysisTraceCompatibility,
    CharacterizationResultDetail,
    CharacterizationResultSummary,
    CharacterizationRunHistoryRow,
    CharacterizationTaggingRequest,
    CharacterizationTaggingResult,
    DatasetAllowedActions,
    DatasetCreateDraft,
    DatasetDesignMutationResult,
    DatasetDetail,
    DatasetProfileUpdate,
    DesignBrowseRow,
    DesignCreateDraft,
    RawDataIngestionDraft,
    RawDataIngestionResult,
    ResultTracePublicationDraft,
    ResultTracePublicationResult,
    SimulationResultPublicationDraft,
    SimulationResultPublicationRecord,
    SimulationResultPublicationResult,
    TaggedCoreMetricSummary,
    TraceAllowedActions,
    TraceAnalysisCapability,
    TraceAxis,
    TraceBrowseRow,
    TraceDetail,
    TraceEditableMetadata,
    TraceEditDetail,
    TraceImmutableSummary,
    TraceMetadataSummary,
    TraceMutationPolicy,
    TraceUpdateDraft,
    TraceUpdateResult,
)
from src.app.domain.tasks import TaskDetail
from src.app.infrastructure.persisted_characterization_runtime import (
    CharacterizationTaggingResultPayload,
    PersistedCharacterizationRepository,
)
from src.app.infrastructure.persisted_runtime import (
    delete_trace_payload_store,
    write_complex_trace_payload,
)
from src.app.infrastructure.persistence.models import (
    RewriteCharacterizationRegistryRecord,
    RewriteDatasetRecord,
    RewriteDatasetTraceRecord,
)
from src.app.infrastructure.persistence.research_data_publication_repository import (
    SqliteResearchDataPublicationRepository,
)
from src.app.infrastructure.persistence.storage_metadata_repository import (
    SqliteRewriteStorageMetadataRepository,
)
from src.app.infrastructure.persistence.trace_capability_store import (
    delete_trace_capabilities,
    load_trace_capability_map,
    replace_trace_capabilities,
    trace_capabilities_equal,
)
from src.app.infrastructure.storage_reference_factory import build_metadata_record_ref


class CircuitDefinitionReadRepository(Protocol):
    def list_circuit_definitions(self) -> Sequence[CircuitDefinitionRecord]: ...

    def get_circuit_definition(self, definition_id: str) -> CircuitDefinitionRecord | None: ...


class CharacterizationTaskRepository(Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...


class DurableCatalogRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        storage_metadata_repository: SqliteRewriteStorageMetadataRepository,
        publication_repository: SqliteResearchDataPublicationRepository,
        characterization_repository: PersistedCharacterizationRepository,
        circuit_definition_repository: CircuitDefinitionReadRepository,
        task_repository: CharacterizationTaskRepository,
    ) -> None:
        self._session_factory = session_factory
        self._storage_metadata_repository = storage_metadata_repository
        self._publication_repository = publication_repository
        self._characterization_repository = characterization_repository
        self._circuit_definition_repository = circuit_definition_repository
        self._task_repository = task_repository

    def list_dataset_details(self) -> tuple[DatasetDetail, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteDatasetRecord).order_by(
                    RewriteDatasetRecord.updated_at.desc(),
                    RewriteDatasetRecord.dataset_id.asc(),
                )
            ).all()
            return tuple(_to_dataset_detail(row) for row in rows)

    def get_dataset(self, dataset_id: str) -> DatasetDetail | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteDatasetRecord).where(
                    RewriteDatasetRecord.dataset_id == dataset_id
                )
            )
            return _to_dataset_detail(row) if row is not None else None

    def create_dataset(
        self,
        *,
        workspace_id: str,
        visibility_scope: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: DatasetCreateDraft,
    ) -> DatasetDetail:
        with self._session_factory() as session:
            next_counter = (
                session.scalar(select(func.count(RewriteDatasetRecord.id))) or 0
            ) + 100
            dataset_id = _build_dataset_id(
                workspace_id=workspace_id,
                name=draft.name,
                counter=next_counter,
            )
            timestamp = "2026-03-17T10:15:00Z"
            row = RewriteDatasetRecord(
                dataset_id=dataset_id,
                name=draft.name,
                family=draft.family,
                owner_display_name=owner_display_name,
                owner_user_id=owner_user_id,
                workspace_id=workspace_id,
                visibility_scope=visibility_scope,
                lifecycle_state="active",
                updated_at=timestamp,
                device_type=draft.device_type,
                capabilities_json=[],
                source=draft.source,
                status="Ready",
            )
            session.add(row)
            session.commit()
            return _to_dataset_detail(row)

    def update_dataset_profile(
        self,
        dataset_id: str,
        update: DatasetProfileUpdate,
    ) -> DatasetDetail | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteDatasetRecord).where(
                    RewriteDatasetRecord.dataset_id == dataset_id
                )
            )
            if row is None:
                return None
            row.device_type = update.device_type
            row.capabilities_json = list(update.capabilities)
            row.source = update.source
            row.updated_at = "2026-03-17T10:18:00Z"
            session.commit()
            return _to_dataset_detail(row)

    def set_dataset_lifecycle_state(
        self,
        dataset_id: str,
        lifecycle_state: str,
    ) -> DatasetDetail | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteDatasetRecord).where(
                    RewriteDatasetRecord.dataset_id == dataset_id
                )
            )
            if row is None:
                return None
            row.lifecycle_state = lifecycle_state
            row.updated_at = "2026-03-17T10:18:00Z"
            session.commit()
            return _to_dataset_detail(row)

    def ingest_raw_data(
        self,
        dataset_id: str,
        draft: RawDataIngestionDraft,
    ) -> RawDataIngestionResult | None:
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            return None
        design_id = draft.design_id or _build_design_id(draft.design_name)
        updated_at = "2026-03-17T10:20:00Z"
        self._upsert_design_row(
            dataset_id=dataset_id,
            design_id=design_id,
            name=draft.design_name,
            updated_at=updated_at,
        )
        traces: list[TraceMetadataSummary] = []
        for index, trace in enumerate(draft.traces, start=1):
            trace_id = trace.trace_id or _build_trace_id(
                kind=draft.kind,
                parameter=trace.parameter,
                index=index,
            )
            preview_payload = dict(trace.preview_payload)
            numeric_payload = _numeric_payload_from_preview_payload(trace.axes, preview_payload)
            payload_ref = _materialize_trace_payload(
                dataset_id=dataset_id,
                design_id=design_id,
                trace_id=trace_id,
                axes=trace.axes,
                numeric_payload=numeric_payload,
            )
            self._persist_raw_trace_storage(
                dataset_id=dataset_id,
                design_id=design_id,
                trace_id=trace_id,
                payload_ref=payload_ref,
            )
            summary = TraceMetadataSummary(
                trace_id=trace_id,
                dataset_id=dataset_id,
                design_id=design_id,
                family=trace.family,
                parameter=trace.parameter,
                representation=trace.representation,
                trace_mode_group=trace.trace_mode_group,
                source_kind=draft.kind,
                stage_kind=trace.stage_kind,
                provenance_summary=trace.provenance_summary,
            )
            analysis_capabilities = evaluate_trace_analysis_capabilities(
                dataset_family=dataset.family,
                trace=summary,
                axes=trace.axes,
            )
            self._upsert_raw_trace(
                _RawTraceRecordDraft(
                    dataset_id=dataset_id,
                    design_id=design_id,
                    trace_id=trace_id,
                    family=trace.family,
                    parameter=trace.parameter,
                    representation=trace.representation,
                    trace_mode_group=trace.trace_mode_group,
                    source_kind=draft.kind,
                    stage_kind=trace.stage_kind,
                    provenance_summary=trace.provenance_summary,
                    axes=trace.axes,
                    preview_payload=preview_payload,
                    numeric_payload=numeric_payload,
                    payload_store_key=payload_ref.store_key,
                    result_handle_ids=(),
                    editable=True,
                    mutation_policy_summary="Manually ingested raw trace.",
                    updated_at=updated_at,
                ),
                analysis_capabilities=analysis_capabilities,
            )
            traces.append(replace(summary, analysis_capabilities=analysis_capabilities))
        updated_dataset = self._touch_dataset(dataset_id, updated_at) or dataset
        design = self.get_design(dataset_id, design_id)
        if design is None:
            raise LookupError("Durable design row was not materialized.")
        return RawDataIngestionResult(
            dataset=updated_dataset,
            design=design,
            traces=tuple(traces),
        )

    def create_design(
        self,
        dataset_id: str,
        draft: DesignCreateDraft,
    ) -> DatasetDesignMutationResult | None:
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            return None
        design = self._publication_repository.create_design(dataset_id=dataset_id, draft=draft)
        updated_dataset = self._touch_dataset(dataset_id, design.updated_at) or dataset
        return DatasetDesignMutationResult(dataset=updated_dataset, design=design)

    def list_tagged_core_metrics(
        self,
        dataset_id: str,
    ) -> tuple[TaggedCoreMetricSummary, ...]:
        return self._characterization_repository.list_tagged_core_metrics(dataset_id)

    def list_designs(
        self,
        dataset_id: str,
    ) -> tuple[DesignBrowseRow, ...]:
        raw_trace_rows = self._list_raw_trace_rows(dataset_id=dataset_id)
        design_state: dict[str, DesignBrowseRow] = {
            row.design_id: row for row in self._publication_repository.list_designs(dataset_id)
        }
        design_names = self._load_design_names(dataset_id)
        traces_by_design: dict[str, list[RewriteDatasetTraceRecord]] = defaultdict(list)
        for trace_row in raw_trace_rows:
            traces_by_design[trace_row.design_id].append(trace_row)
        for design_id, name in design_names.items():
            if design_id not in design_state:
                design_state[design_id] = DesignBrowseRow(
                    design_id=design_id,
                    dataset_id=dataset_id,
                    name=name,
                    source_coverage=_empty_source_coverage(),
                    compare_readiness="blocked",
                    trace_count=0,
                    updated_at="1970-01-01T00:00:00Z",
                )
        for design_id, trace_rows in traces_by_design.items():
            existing = design_state.get(design_id)
            design_name = design_names.get(
                design_id,
                existing.name if existing is not None else design_id,
            )
            raw_row = DesignBrowseRow(
                design_id=design_id,
                dataset_id=dataset_id,
                name=design_name,
                source_coverage=_build_source_coverage(
                    tuple(_to_trace_summary(row) for row in trace_rows)
                ),
                compare_readiness=_compare_readiness_for(
                    _build_source_coverage(tuple(_to_trace_summary(row) for row in trace_rows))
                ),
                trace_count=len(trace_rows),
                updated_at=max(row.updated_at for row in trace_rows),
            )
            design_state[design_id] = _merge_design_rows(existing, raw_row)
        return tuple(sorted(design_state.values(), key=lambda row: row.design_id))

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
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            return ()
        rows = {
            row.trace_id: row
            for row in self._publication_repository.list_trace_metadata(
                dataset_id,
                design_id,
            )
        }
        raw_rows = self._list_raw_trace_rows(dataset_id=dataset_id, design_id=design_id)
        capability_map = self._load_or_materialize_raw_trace_capability_map(
            dataset=dataset,
            design_id=design_id,
            trace_rows=raw_rows,
        )
        for trace_row in raw_rows:
            rows[trace_row.trace_id] = _to_trace_summary(
                trace_row,
                analysis_capabilities=capability_map.get(trace_row.trace_id, ()),
            )
        return tuple(sorted(rows.values(), key=lambda row: row.trace_id))

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDetail | None:
        raw_row = self._get_raw_trace_row(dataset_id, design_id, trace_id)
        if raw_row is not None:
            return self._to_trace_detail(raw_row)
        return self._publication_repository.get_trace_detail(dataset_id, design_id, trace_id)

    def get_trace_mutation_policy(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceMutationPolicy | None:
        raw_row = self._get_raw_trace_row(dataset_id, design_id, trace_id)
        if raw_row is not None:
            return TraceMutationPolicy(
                allowed_actions=TraceAllowedActions(
                    edit=raw_row.editable,
                    delete=raw_row.editable,
                ),
                summary=raw_row.mutation_policy_summary,
            )
        published = self._publication_repository.get_trace_detail(dataset_id, design_id, trace_id)
        if published is None:
            return None
        return TraceMutationPolicy(
            allowed_actions=TraceAllowedActions(edit=False, delete=True),
            summary=(
                "Provenance-bearing or system-generated trace; delete is allowed, "
                "but edit from the source workflow."
            ),
        )

    def get_trace_edit_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceEditDetail | None:
        summary = next(
            (
                row
                for row in self.list_trace_metadata(dataset_id, design_id)
                if row.trace_id == trace_id
            ),
            None,
        )
        detail = self.get_trace_detail(dataset_id, design_id, trace_id)
        policy = self.get_trace_mutation_policy(dataset_id, design_id, trace_id)
        if summary is None or detail is None or policy is None:
            return None
        raw_row = self._get_raw_trace_row(dataset_id, design_id, trace_id)
        editable_numeric_payload = (
            dict(raw_row.numeric_payload_json)
            if raw_row is not None
            else _numeric_payload_from_preview_payload(detail.axes, detail.preview_payload)
        )
        return TraceEditDetail(
            trace_id=trace_id,
            dataset_id=dataset_id,
            design_id=design_id,
            editable_metadata=TraceEditableMetadata(
                parameter=summary.parameter,
                representation=summary.representation,
                provenance_summary=summary.provenance_summary,
            ),
            immutable_summary=TraceImmutableSummary(
                family=summary.family,
                trace_mode_group=summary.trace_mode_group,
                source_kind=summary.source_kind,
                stage_kind=summary.stage_kind,
            ),
            editable_numeric_payload=editable_numeric_payload,
            allowed_actions=policy.allowed_actions,
            mutation_policy_summary=policy.summary,
            analysis_capabilities=summary.analysis_capabilities,
        )

    def update_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        update: TraceUpdateDraft,
    ) -> TraceUpdateResult | None:
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            return None
        raw_row = self._get_raw_trace_row(dataset_id, design_id, trace_id)
        if raw_row is None or not raw_row.editable:
            return None
        updated_at = _current_timestamp()
        current_detail = self._to_trace_detail(raw_row)
        numeric_payload = (
            update.numeric_payload
            if update.numeric_payload is not None
            else dict(raw_row.numeric_payload_json)
        )
        axes = (
            _axes_with_numeric_payload(current_detail.axes, numeric_payload)
            if update.numeric_payload is not None
            else current_detail.axes
        )
        preview_payload = (
            _preview_payload_from_numeric_payload(numeric_payload)
            if update.numeric_payload is not None
            else dict(raw_row.preview_payload_json)
        )
        payload_ref = _materialize_trace_payload(
            dataset_id=dataset_id,
            design_id=design_id,
            trace_id=trace_id,
            axes=axes,
            numeric_payload=numeric_payload,
        )
        self._persist_raw_trace_storage(
            dataset_id=dataset_id,
            design_id=design_id,
            trace_id=trace_id,
            payload_ref=payload_ref,
        )
        raw_row.parameter = update.parameter or raw_row.parameter
        raw_row.representation = update.representation or raw_row.representation
        raw_row.provenance_summary = update.provenance_summary or raw_row.provenance_summary
        raw_row.axes_json = [_serialize_axis(axis) for axis in axes]
        raw_row.preview_payload_json = preview_payload
        raw_row.numeric_payload_json = numeric_payload
        raw_row.payload_store_key = payload_ref.store_key
        raw_row.updated_at = updated_at
        updated_summary = TraceMetadataSummary(
            trace_id=raw_row.trace_id,
            dataset_id=raw_row.dataset_id,
            design_id=raw_row.design_id,
            family=raw_row.family,
            parameter=raw_row.parameter,
            representation=raw_row.representation,
            trace_mode_group=raw_row.trace_mode_group,
            source_kind=raw_row.source_kind,
            stage_kind=raw_row.stage_kind,
            provenance_summary=raw_row.provenance_summary,
        )
        analysis_capabilities = evaluate_trace_analysis_capabilities(
            dataset_family=dataset.family,
            trace=updated_summary,
            axes=axes,
        )
        with self._session_factory() as session:
            persisted = session.scalar(
                select(RewriteDatasetTraceRecord).where(
                    RewriteDatasetTraceRecord.id == raw_row.id
                )
            )
            if persisted is None:
                return None
            _apply_raw_trace_row(persisted, raw_row)
            replace_trace_capabilities(
                session,
                dataset_id=dataset_id,
                design_id=design_id,
                trace_id=trace_id,
                capabilities=analysis_capabilities,
            )
            session.commit()
        self._touch_design(dataset_id, design_id, updated_at)
        self._touch_dataset(dataset_id, updated_at)
        summary = replace(updated_summary, analysis_capabilities=analysis_capabilities)
        policy = self.get_trace_mutation_policy(dataset_id, design_id, trace_id)
        if policy is None:
            return None
        return TraceUpdateResult(
            trace=_build_trace_browse_row(summary, policy),
        )

    def delete_traces(
        self,
        dataset_id: str,
        design_id: str,
        trace_ids: Sequence[str],
    ) -> tuple[str, ...] | None:
        requested = tuple(dict.fromkeys(trace_ids))
        if len(requested) == 0:
            return ()
        raw_rows_by_trace_id = {
            row.trace_id: row
            for row in self._list_raw_trace_rows(dataset_id=dataset_id, design_id=design_id)
            if row.trace_id in requested
        }
        raw_rows_to_delete: list[RewriteDatasetTraceRecord] = []
        published_trace_ids: list[str] = []
        for trace_id in requested:
            raw_row = raw_rows_by_trace_id.get(trace_id)
            if raw_row is not None:
                if not raw_row.editable:
                    return None
                raw_rows_to_delete.append(raw_row)
                continue
            published = self._publication_repository.get_trace_detail(
                dataset_id,
                design_id,
                trace_id,
            )
            if published is None:
                return None
            published_trace_ids.append(trace_id)

        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteDatasetTraceRecord).where(
                    RewriteDatasetTraceRecord.dataset_id == dataset_id,
                    RewriteDatasetTraceRecord.design_id == design_id,
                    RewriteDatasetTraceRecord.trace_id.in_(
                        [row.trace_id for row in raw_rows_to_delete]
                    ),
                )
            ).all()
            for row in rows:
                session.delete(row)
            delete_trace_capabilities(
                session,
                dataset_id=dataset_id,
                design_id=design_id,
                trace_ids=[row.trace_id for row in raw_rows_to_delete],
            )
            session.commit()
        for row in raw_rows_to_delete:
            for handle_id in row.result_handle_ids_json:
                self._storage_metadata_repository.delete_result_handle(handle_id)
            self._storage_metadata_repository.delete_trace_payload(row.payload_store_key)
            delete_trace_payload_store(row.payload_store_key)
        if len(published_trace_ids) > 0:
            deleted = self._publication_repository.delete_traces(
                dataset_id,
                design_id,
                tuple(published_trace_ids),
            )
            if deleted is None:
                return None
        updated_at = _current_timestamp()
        self._touch_design(dataset_id, design_id, updated_at)
        self._touch_dataset(dataset_id, updated_at)
        return requested

    def get_simulation_result_publication_record(
        self,
        source_task_id: int,
    ) -> SimulationResultPublicationRecord | None:
        return self._publication_repository.get_publication_record(source_task_id)

    def publish_simulation_result(
        self,
        *,
        task: TaskDetail,
        dataset_id: str,
        draft: SimulationResultPublicationDraft,
    ) -> SimulationResultPublicationResult | None:
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            return None
        return self._publication_repository.publish_simulation_result(
            task=task,
            dataset=dataset,
            draft=draft,
        )

    def publish_result_trace(
        self,
        *,
        task: TaskDetail,
        basis_task: TaskDetail,
        dataset: DatasetDetail,
        design: DesignBrowseRow,
        draft: ResultTracePublicationDraft,
    ) -> ResultTracePublicationResult | None:
        return self._publication_repository.publish_result_trace(
            task=task,
            basis_task=basis_task,
            dataset=dataset,
            design=design,
            draft=draft,
        )

    def list_characterization_results(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationResultSummary, ...]:
        persisted_rows = self._characterization_repository.list_result_summaries(
            dataset_id,
            design_id,
        )
        task_rows = tuple(
            summary
            for summary, _, _ in self._iter_task_derived_characterization_views(
                dataset_id,
                design_id,
            )
        )
        return _merge_characterization_result_rows(persisted_rows, task_rows)

    def list_characterization_analysis_registry(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationAnalysisRegistryRow, ...]:
        return self._list_persisted_characterization_registry(dataset_id, design_id)

    def list_characterization_run_history(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationRunHistoryRow, ...]:
        persisted_rows = self._characterization_repository.list_run_history(dataset_id, design_id)
        task_rows = tuple(
            row
            for _, row, _ in self._iter_task_derived_characterization_views(dataset_id, design_id)
        )
        return _merge_characterization_run_rows(persisted_rows, task_rows)

    def get_characterization_result(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> CharacterizationResultDetail | None:
        persisted = self._characterization_repository.get_result_detail(
            dataset_id,
            design_id,
            result_id,
        )
        if persisted is not None:
            return persisted
        for summary, _, detail in self._iter_task_derived_characterization_views(
            dataset_id,
            design_id,
        ):
            if summary.result_id == result_id:
                return detail
        return None

    def apply_characterization_tagging(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        request: CharacterizationTaggingRequest,
    ) -> CharacterizationTaggingResult:
        payload = self._characterization_repository.apply_tagging(
            dataset_id,
            design_id,
            result_id,
            artifact_id=request.artifact_id,
            source_parameter=request.source_parameter,
            designated_metric=request.designated_metric,
        )
        if payload is None:
            raise LookupError("Characterization result was not found.")
        return _to_characterization_tagging_result(payload)

    def list_circuit_definitions(self) -> tuple[CircuitDefinitionRecord, ...]:
        return tuple(self._circuit_definition_repository.list_circuit_definitions())

    def get_circuit_definition(self, definition_id: str) -> CircuitDefinitionRecord | None:
        return self._circuit_definition_repository.get_circuit_definition(definition_id)

    def upsert_seed_dataset(self, dataset: DatasetDetail) -> None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteDatasetRecord).where(
                    RewriteDatasetRecord.dataset_id == dataset.dataset_id
                )
            )
            if row is None:
                row = RewriteDatasetRecord(dataset_id=dataset.dataset_id)
                session.add(row)
            _apply_dataset_row(row, dataset)
            session.commit()

    def upsert_seed_design(self, design: DesignBrowseRow) -> None:
        self._upsert_design_row(
            dataset_id=design.dataset_id,
            design_id=design.design_id,
            name=design.name,
            updated_at=design.updated_at,
        )

    def upsert_seed_characterization_analysis_registry(
        self,
        *,
        dataset_id: str,
        design_id: str,
        rows: Sequence[CharacterizationAnalysisRegistryRow],
    ) -> None:
        with self._session_factory() as session:
            session.query(RewriteCharacterizationRegistryRecord).filter(
                RewriteCharacterizationRegistryRecord.dataset_id == dataset_id,
                RewriteCharacterizationRegistryRecord.design_id == design_id,
            ).delete()
            for sort_order, row in enumerate(rows):
                session.add(
                    RewriteCharacterizationRegistryRecord(
                        dataset_id=dataset_id,
                        design_id=design_id,
                        analysis_id=row.analysis_id,
                        label=row.label,
                        availability_state=row.availability_state,
                        required_config_fields_json=list(row.required_config_fields),
                        matched_trace_count=row.trace_compatibility.matched_trace_count,
                        recommended_trace_modes_json=list(
                            row.trace_compatibility.recommended_trace_modes
                        ),
                        summary=row.trace_compatibility.summary,
                        sort_order=sort_order,
                    )
                )
            session.commit()

    def upsert_seed_trace(
        self,
        *,
        summary: TraceMetadataSummary,
        detail: TraceDetail,
        editable: bool,
        mutation_policy_summary: str,
    ) -> None:
        numeric_payload = _numeric_payload_from_preview_payload(
            detail.axes,
            detail.preview_payload,
        )
        dataset = self.get_dataset(summary.dataset_id)
        if dataset is None:
            raise LookupError("Durable dataset row was not materialized.")
        analysis_capabilities = evaluate_trace_analysis_capabilities(
            dataset_family=dataset.family,
            trace=summary,
            axes=detail.axes,
        )
        payload_ref = _materialize_trace_payload(
            dataset_id=summary.dataset_id,
            design_id=summary.design_id,
            trace_id=summary.trace_id,
            axes=detail.axes,
            numeric_payload=numeric_payload,
            store_key=detail.payload_ref.store_key if detail.payload_ref is not None else None,
        )
        self._persist_raw_trace_storage(
            dataset_id=summary.dataset_id,
            design_id=summary.design_id,
            trace_id=summary.trace_id,
            payload_ref=payload_ref,
            result_handles=detail.result_handles,
        )
        self._upsert_raw_trace(
            _RawTraceRecordDraft(
                dataset_id=summary.dataset_id,
                design_id=summary.design_id,
                trace_id=summary.trace_id,
                family=summary.family,
                parameter=summary.parameter,
                representation=summary.representation,
                trace_mode_group=summary.trace_mode_group,
                source_kind=summary.source_kind,
                stage_kind=summary.stage_kind,
                provenance_summary=summary.provenance_summary,
                axes=detail.axes,
                preview_payload=detail.preview_payload,
                numeric_payload=numeric_payload,
                payload_store_key=payload_ref.store_key,
                result_handle_ids=tuple(handle.handle_id for handle in detail.result_handles),
                editable=editable,
                mutation_policy_summary=mutation_policy_summary,
                updated_at=_current_timestamp(),
            ),
            analysis_capabilities=analysis_capabilities,
        )

    def _persist_raw_trace_storage(
        self,
        *,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        payload_ref,
        result_handles: Sequence[object] = (),
    ) -> None:
        owner_record = build_metadata_record_ref(
            "trace_batch",
            f"dataset-trace:{dataset_id}:{design_id}:{trace_id}",
            version=1,
        )
        self._storage_metadata_repository.save_trace_payload(owner_record, payload_ref)
        for handle in result_handles:
            self._storage_metadata_repository.save_result_handle(handle)

    def _upsert_design_row(
        self,
        *,
        dataset_id: str,
        design_id: str,
        name: str,
        updated_at: str,
    ) -> None:
        from src.app.infrastructure.persistence.models import RewriteDatasetDesignRecord

        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteDatasetDesignRecord).where(
                    RewriteDatasetDesignRecord.dataset_id == dataset_id,
                    RewriteDatasetDesignRecord.design_id == design_id,
                )
            )
            if row is None:
                row = RewriteDatasetDesignRecord(
                    dataset_id=dataset_id,
                    design_id=design_id,
                    normalized_name=_normalize_design_name(name),
                    name=name,
                    updated_at=updated_at,
                )
                session.add(row)
            else:
                row.normalized_name = _normalize_design_name(name)
                row.name = name
                row.updated_at = updated_at
            session.commit()

    def _touch_design(self, dataset_id: str, design_id: str, updated_at: str) -> None:
        design = self.get_design(dataset_id, design_id)
        if design is None:
            return
        self._upsert_design_row(
            dataset_id=dataset_id,
            design_id=design_id,
            name=design.name,
            updated_at=updated_at,
        )

    def _touch_dataset(self, dataset_id: str, updated_at: str) -> DatasetDetail | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteDatasetRecord).where(
                    RewriteDatasetRecord.dataset_id == dataset_id
                )
            )
            if row is None:
                return None
            row.updated_at = updated_at
            session.commit()
            return _to_dataset_detail(row)

    def _upsert_raw_trace(
        self,
        draft: _RawTraceRecordDraft,
        *,
        analysis_capabilities: Sequence[TraceAnalysisCapability],
    ) -> None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteDatasetTraceRecord).where(
                    RewriteDatasetTraceRecord.dataset_id == draft.dataset_id,
                    RewriteDatasetTraceRecord.design_id == draft.design_id,
                    RewriteDatasetTraceRecord.trace_id == draft.trace_id,
                )
            )
            if row is None:
                row = RewriteDatasetTraceRecord(
                    dataset_id=draft.dataset_id,
                    design_id=draft.design_id,
                    trace_id=draft.trace_id,
                )
                session.add(row)
            _apply_raw_trace_row(row, draft)
            replace_trace_capabilities(
                session,
                dataset_id=draft.dataset_id,
                design_id=draft.design_id,
                trace_id=draft.trace_id,
                capabilities=analysis_capabilities,
            )
            session.commit()

    def _list_raw_trace_rows(
        self,
        *,
        dataset_id: str,
        design_id: str | None = None,
    ) -> tuple[RewriteDatasetTraceRecord, ...]:
        with self._session_factory() as session:
            query = select(RewriteDatasetTraceRecord).where(
                RewriteDatasetTraceRecord.dataset_id == dataset_id
            )
            if design_id is not None:
                query = query.where(RewriteDatasetTraceRecord.design_id == design_id)
            rows = session.scalars(
                query.order_by(
                    RewriteDatasetTraceRecord.design_id.asc(),
                    RewriteDatasetTraceRecord.trace_id.asc(),
                )
            ).all()
            return tuple(rows)

    def _get_raw_trace_row(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> RewriteDatasetTraceRecord | None:
        with self._session_factory() as session:
            return session.scalar(
                select(RewriteDatasetTraceRecord).where(
                    RewriteDatasetTraceRecord.dataset_id == dataset_id,
                    RewriteDatasetTraceRecord.design_id == design_id,
                    RewriteDatasetTraceRecord.trace_id == trace_id,
                )
            )

    def _load_design_names(self, dataset_id: str) -> dict[str, str]:
        from src.app.infrastructure.persistence.models import RewriteDatasetDesignRecord

        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteDatasetDesignRecord).where(
                    RewriteDatasetDesignRecord.dataset_id == dataset_id
                )
            ).all()
            return {row.design_id: row.name for row in rows}

    def _to_trace_detail(self, row: RewriteDatasetTraceRecord) -> TraceDetail:
        analysis_capabilities = self._load_trace_capabilities(
            row.dataset_id,
            row.design_id,
            row.trace_id,
        )
        payload_ref = self._storage_metadata_repository.get_trace_payload(row.payload_store_key)
        result_handles = tuple(
            handle
            for handle_id in row.result_handle_ids_json
            if (
                handle := self._storage_metadata_repository.get_result_handle(handle_id)
            )
            is not None
        )
        return TraceDetail(
            trace_id=row.trace_id,
            dataset_id=row.dataset_id,
            design_id=row.design_id,
            axes=tuple(_deserialize_axis(item) for item in row.axes_json),
            preview_payload=dict(row.preview_payload_json),
            payload_ref=payload_ref,
            result_handles=result_handles,
            analysis_capabilities=analysis_capabilities,
        )

    def _load_trace_capabilities(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> tuple[TraceAnalysisCapability, ...]:
        raw_row = self._get_raw_trace_row(dataset_id, design_id, trace_id)
        if raw_row is None:
            return self._load_trace_capability_map(
                dataset_id=dataset_id,
                design_id=design_id,
                trace_ids=(trace_id,),
            ).get(trace_id, ())
        dataset = self.get_dataset(dataset_id)
        if dataset is None:
            return ()
        return self._load_or_materialize_raw_trace_capability_map(
            dataset=dataset,
            design_id=design_id,
            trace_rows=(raw_row,),
        ).get(trace_id, ())

    def _load_or_materialize_raw_trace_capability_map(
        self,
        *,
        dataset: DatasetDetail,
        design_id: str,
        trace_rows: Sequence[RewriteDatasetTraceRecord],
    ) -> dict[str, tuple[TraceAnalysisCapability, ...]]:
        trace_ids = tuple(row.trace_id for row in trace_rows)
        if len(trace_ids) == 0:
            return {}
        with self._session_factory() as session:
            capability_map = load_trace_capability_map(
                session,
                dataset_id=dataset.dataset_id,
                design_id=design_id,
                trace_ids=trace_ids,
            )
            refreshed = False
            for row in trace_rows:
                capabilities = evaluate_trace_analysis_capabilities(
                    dataset_family=dataset.family,
                    trace=_to_trace_summary(row),
                    axes=tuple(_deserialize_axis(item) for item in row.axes_json),
                )
                if trace_capabilities_equal(
                    capability_map.get(row.trace_id, ()),
                    capabilities,
                ):
                    continue
                replace_trace_capabilities(
                    session,
                    dataset_id=row.dataset_id,
                    design_id=row.design_id,
                    trace_id=row.trace_id,
                    capabilities=capabilities,
                )
                capability_map[row.trace_id] = capabilities
                refreshed = True
            if refreshed:
                session.commit()
            return capability_map

    def _load_trace_capability_map(
        self,
        *,
        dataset_id: str,
        design_id: str,
        trace_ids: Sequence[str],
    ) -> dict[str, tuple[TraceAnalysisCapability, ...]]:
        with self._session_factory() as session:
            return load_trace_capability_map(
                session,
                dataset_id=dataset_id,
                design_id=design_id,
                trace_ids=trace_ids,
            )

    def _list_persisted_characterization_registry(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationAnalysisRegistryRow, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteCharacterizationRegistryRecord)
                .where(
                    RewriteCharacterizationRegistryRecord.dataset_id == dataset_id,
                    RewriteCharacterizationRegistryRecord.design_id == design_id,
                )
                .order_by(
                    RewriteCharacterizationRegistryRecord.sort_order.asc(),
                    RewriteCharacterizationRegistryRecord.analysis_id.asc(),
                )
            ).all()
            return tuple(_to_characterization_registry_row(row) for row in rows)

    def _iter_task_derived_characterization_views(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[
        tuple[
            CharacterizationResultSummary,
            CharacterizationRunHistoryRow,
            CharacterizationResultDetail,
        ],
        ...,
    ]:
        derived_rows: list[
            tuple[
                CharacterizationResultSummary,
                CharacterizationRunHistoryRow,
                CharacterizationResultDetail,
            ]
        ] = []
        for task in self._task_repository.list_tasks():
            if (
                task.kind != "characterization"
                or task.dataset_id != dataset_id
                or task.status != "completed"
                or task.characterization_setup is None
                or task.characterization_setup.design_id != design_id
            ):
                continue
            completion_event = next(
                (
                    event
                    for event in reversed(task.events)
                    if event.event_type == "task_completed"
                ),
                None,
            )
            if completion_event is None:
                continue
            summary = _parse_characterization_result_summary(
                completion_event.metadata.get("characterization_result_summary")
            )
            run_row = _parse_characterization_run_history_row(
                completion_event.metadata.get("characterization_run_history_row")
            )
            detail = _parse_characterization_result_detail(
                completion_event.metadata.get("characterization_result_detail")
            )
            if summary is None or run_row is None or detail is None:
                continue
            derived_rows.append((summary, run_row, detail))
        derived_rows.sort(key=lambda item: item[0].updated_at, reverse=True)
        return tuple(derived_rows)


@dataclass(frozen=True)
class _RawTraceRecordDraft:
    dataset_id: str
    design_id: str
    trace_id: str
    family: str
    parameter: str
    representation: str
    trace_mode_group: str
    source_kind: str
    stage_kind: str
    provenance_summary: str
    axes: tuple[TraceAxis, ...]
    preview_payload: dict[str, object]
    numeric_payload: dict[str, object]
    payload_store_key: str
    result_handle_ids: tuple[str, ...]
    editable: bool
    mutation_policy_summary: str
    updated_at: str


def _apply_dataset_row(row: RewriteDatasetRecord, dataset: DatasetDetail) -> None:
    row.name = dataset.name
    row.family = dataset.family
    row.owner_display_name = dataset.owner
    row.owner_user_id = dataset.owner_user_id
    row.workspace_id = dataset.workspace_id
    row.visibility_scope = dataset.visibility_scope
    row.lifecycle_state = dataset.lifecycle_state
    row.updated_at = dataset.updated_at
    row.device_type = dataset.device_type
    row.capabilities_json = list(dataset.capabilities)
    row.source = dataset.source
    row.status = dataset.status


def _to_dataset_detail(row: RewriteDatasetRecord) -> DatasetDetail:
    return DatasetDetail(
        dataset_id=row.dataset_id,
        name=row.name,
        family=row.family,
        owner=row.owner_display_name,
        owner_user_id=row.owner_user_id,
        workspace_id=row.workspace_id,
        visibility_scope=row.visibility_scope,
        lifecycle_state=row.lifecycle_state,
        updated_at=row.updated_at,
        device_type=row.device_type,
        capabilities=tuple(str(item) for item in row.capabilities_json),
        source=row.source,
        status=row.status,
        allowed_actions=DatasetAllowedActions(
            select=True,
            update_profile=True,
            publish=row.visibility_scope != "workspace" and row.workspace_id != "local-space",
            archive=True,
            delete=True,
            ingest_raw_data=True,
        ),
    )


def _apply_raw_trace_row(
    row: RewriteDatasetTraceRecord,
    draft: _RawTraceRecordDraft | RewriteDatasetTraceRecord,
) -> None:
    row.family = draft.family
    row.parameter = draft.parameter
    row.representation = draft.representation
    row.trace_mode_group = draft.trace_mode_group
    row.source_kind = draft.source_kind
    row.stage_kind = draft.stage_kind
    row.provenance_summary = draft.provenance_summary
    if isinstance(draft, RewriteDatasetTraceRecord):
        row.axes_json = list(draft.axes_json)
        row.preview_payload_json = dict(draft.preview_payload_json)
        row.numeric_payload_json = dict(draft.numeric_payload_json)
        row.result_handle_ids_json = list(draft.result_handle_ids_json)
    else:
        row.axes_json = [_serialize_axis(axis) for axis in draft.axes]
        row.preview_payload_json = dict(draft.preview_payload)
        row.numeric_payload_json = dict(draft.numeric_payload)
        row.result_handle_ids_json = list(draft.result_handle_ids)
    row.payload_store_key = draft.payload_store_key
    row.editable = draft.editable
    row.mutation_policy_summary = draft.mutation_policy_summary
    row.updated_at = draft.updated_at


def _to_trace_summary(
    row: RewriteDatasetTraceRecord,
    *,
    analysis_capabilities=(),
) -> TraceMetadataSummary:
    return TraceMetadataSummary(
        trace_id=row.trace_id,
        dataset_id=row.dataset_id,
        design_id=row.design_id,
        family=row.family,
        parameter=row.parameter,
        representation=row.representation,
        trace_mode_group=row.trace_mode_group,
        source_kind=row.source_kind,
        stage_kind=row.stage_kind,
        provenance_summary=row.provenance_summary,
        analysis_capabilities=analysis_capabilities,
    )


def _build_trace_browse_row(
    summary: TraceMetadataSummary,
    policy: TraceMutationPolicy,
) -> TraceBrowseRow:
    return TraceBrowseRow(
        trace_id=summary.trace_id,
        dataset_id=summary.dataset_id,
        design_id=summary.design_id,
        family=summary.family,
        parameter=summary.parameter,
        representation=summary.representation,
        trace_mode_group=summary.trace_mode_group,
        source_kind=summary.source_kind,
        stage_kind=summary.stage_kind,
        provenance_summary=summary.provenance_summary,
        allowed_actions=policy.allowed_actions,
        mutation_policy_summary=policy.summary,
        analysis_capabilities=summary.analysis_capabilities,
    )


def _to_characterization_registry_row(
    row: RewriteCharacterizationRegistryRecord,
) -> CharacterizationAnalysisRegistryRow:
    return CharacterizationAnalysisRegistryRow(
        analysis_id=row.analysis_id,
        label=row.label,
        availability_state=row.availability_state,
        required_config_fields=tuple(row.required_config_fields_json),
        trace_compatibility=CharacterizationAnalysisTraceCompatibility(
            matched_trace_count=row.matched_trace_count,
            selected_trace_count=0,
            recommended_trace_modes=tuple(row.recommended_trace_modes_json),
            summary=row.summary,
        ),
    )


def _serialize_axis(axis: TraceAxis) -> dict[str, object]:
    return {"name": axis.name, "unit": axis.unit, "length": axis.length}


def _deserialize_axis(payload: dict[str, object]) -> TraceAxis:
    return TraceAxis(
        name=str(payload["name"]),
        unit=str(payload["unit"]),
        length=int(payload["length"]),
    )


def _build_dataset_id(*, workspace_id: str, name: str, counter: int) -> str:
    slug = _slugify(name)
    if workspace_id == "local-space":
        return f"local-{slug}-{counter}"
    return f"{slug}-{counter}"


def _build_design_id(name: str) -> str:
    return f"design_{_slugify(name)}"


def _build_trace_id(*, kind: str, parameter: str, index: int) -> str:
    return f"trace_{_slugify(kind)}_{_slugify(parameter)}_{index}"


def _slugify(value: str) -> str:
    return "-".join(
        token
        for token in "".join(
            character.lower() if character.isalnum() else "-"
            for character in value.strip()
        ).split("-")
        if token
    )


def _normalize_design_name(name: str) -> str:
    return " ".join(name.casefold().split())


def _current_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty_source_coverage() -> dict[str, int]:
    return {"measurement": 0, "layout_simulation": 0, "circuit_simulation": 0}


def _build_source_coverage(traces: tuple[TraceMetadataSummary, ...]) -> dict[str, int]:
    coverage = _empty_source_coverage()
    for trace in traces:
        coverage[trace.source_kind] = coverage.get(trace.source_kind, 0) + 1
    return coverage


def _compare_readiness_for(source_coverage: dict[str, int]) -> str:
    if (
        source_coverage.get("measurement", 0) > 0
        and source_coverage.get("layout_simulation", 0) > 0
    ):
        return "ready"
    if sum(source_coverage.values()) > 0:
        return "inspect_only"
    return "blocked"


def _merge_design_rows(
    existing: DesignBrowseRow | None,
    incoming: DesignBrowseRow,
) -> DesignBrowseRow:
    if existing is None:
        return incoming
    coverage = {
        key: existing.source_coverage.get(key, 0) + incoming.source_coverage.get(key, 0)
        for key in {
            *existing.source_coverage.keys(),
            *incoming.source_coverage.keys(),
        }
    }
    return DesignBrowseRow(
        design_id=incoming.design_id,
        dataset_id=incoming.dataset_id,
        name=existing.name or incoming.name,
        source_coverage=coverage,
        compare_readiness=_compare_readiness_for(coverage),
        trace_count=existing.trace_count + incoming.trace_count,
        updated_at=max(existing.updated_at, incoming.updated_at),
    )


def _numeric_payload_from_preview_payload(
    axes: tuple[TraceAxis, ...],
    preview_payload: dict[str, object],
) -> dict[str, object]:
    axis = axes[0] if len(axes) > 0 else TraceAxis(name="frequency", unit="GHz", length=0)
    points = preview_payload.get("points")
    rows: list[dict[str, object]] = []
    if isinstance(points, list):
        for item in points:
            if isinstance(item, list | tuple) and len(item) >= 2:
                rows.append({axis.name: item[0], "value": item[1]})
    if len(rows) == 0:
        rows = [
            {axis.name: float(index), "value": 0.0}
            for index in range(axis.length)
        ]
    return {
        "kind": "series_table",
        "columns": [
            {"key": axis.name, "label": axis.name.title(), "unit": axis.unit, "role": "axis"},
            {"key": "value", "label": "Value", "unit": None, "role": "value"},
        ],
        "rows": rows,
    }


def _preview_payload_from_numeric_payload(numeric_payload: dict[str, object]) -> dict[str, object]:
    rows = numeric_payload.get("rows")
    if not isinstance(rows, list):
        return {"kind": "sampled_series", "points": []}
    axis_key = _numeric_payload_axis_key(numeric_payload)
    points = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if axis_key not in row or "value" not in row:
            continue
        points.append([row[axis_key], row["value"]])
    return {"kind": "sampled_series", "points": points}


def _numeric_payload_axis_key(numeric_payload: dict[str, object]) -> str:
    columns = numeric_payload.get("columns")
    if isinstance(columns, list):
        for column in columns:
            if isinstance(column, dict) and column.get("role") == "axis":
                key = column.get("key")
                if isinstance(key, str) and key:
                    return key
    return "frequency"


def _numeric_payload_axis_lengths(numeric_payload: dict[str, object]) -> tuple[int, ...] | None:
    rows = numeric_payload.get("rows")
    if not isinstance(rows, list):
        return None
    return (len(rows),)


def _axes_with_numeric_payload(
    axes: tuple[TraceAxis, ...],
    numeric_payload: dict[str, object],
) -> tuple[TraceAxis, ...]:
    lengths = _numeric_payload_axis_lengths(numeric_payload)
    if lengths is None or len(axes) == 0:
        return axes
    return (replace(axes[0], length=lengths[0]), *axes[1:])


def _materialize_trace_payload(
    *,
    dataset_id: str,
    design_id: str,
    trace_id: str,
    axes: tuple[TraceAxis, ...],
    numeric_payload: dict[str, object],
    store_key: str | None = None,
) -> Any:
    axis_key = _numeric_payload_axis_key(numeric_payload)
    rows = numeric_payload.get("rows")
    if not isinstance(rows, list):
        rows = []
    frequencies = []
    values = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        x_value = row.get(axis_key, float(index))
        y_value = row.get("value", 0.0)
        frequencies.append(float(x_value))
        values.append(complex(float(y_value), 0.0))
    if len(frequencies) == 0:
        length = axes[0].length if len(axes) > 0 else 1
        frequencies = [float(index) for index in range(length)]
        values = [0.0j for _ in range(length)]
    return write_complex_trace_payload(
        dataset_id=dataset_id,
        design_id=design_id,
        trace_id=trace_id,
        frequencies_ghz=frequencies,
        values=np.asarray(values, dtype=np.complex128),
        store_key=store_key
        or f"trace_store/datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr",
    )


def _merge_characterization_result_rows(
    persisted_rows: tuple[CharacterizationResultSummary, ...],
    task_rows: tuple[CharacterizationResultSummary, ...],
) -> tuple[CharacterizationResultSummary, ...]:
    merged: list[CharacterizationResultSummary] = []
    seen: set[str] = set()
    for row in (*persisted_rows, *task_rows):
        if row.result_id in seen:
            continue
        merged.append(row)
        seen.add(row.result_id)
    merged.sort(key=lambda row: (row.updated_at, row.result_id), reverse=True)
    merged.sort(key=lambda row: _characterization_result_status_rank(row.status))
    return tuple(merged)


def _merge_characterization_run_rows(
    persisted_rows: tuple[CharacterizationRunHistoryRow, ...],
    task_rows: tuple[CharacterizationRunHistoryRow, ...],
) -> tuple[CharacterizationRunHistoryRow, ...]:
    merged: list[CharacterizationRunHistoryRow] = []
    seen: set[str] = set()
    for row in (*persisted_rows, *task_rows):
        if row.run_id in seen:
            continue
        merged.append(row)
        seen.add(row.run_id)
    merged.sort(key=lambda row: row.updated_at, reverse=True)
    return tuple(merged)


def _characterization_result_status_rank(status: str) -> int:
    if status == "completed":
        return 0
    if status == "blocked":
        return 1
    return 2


def _parse_characterization_result_summary(
    payload: object,
) -> CharacterizationResultSummary | None:
    if not isinstance(payload, dict):
        return None
    return CharacterizationResultSummary(
        result_id=str(payload["result_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        title=str(payload["title"]),
        status=str(payload["status"]),
        freshness_summary=str(payload["freshness_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        trace_count=int(payload["trace_count"]),
        artifact_count=int(payload["artifact_count"]),
        updated_at=str(payload["updated_at"]),
    )


def _parse_characterization_run_history_row(
    payload: object,
) -> CharacterizationRunHistoryRow | None:
    if not isinstance(payload, dict):
        return None
    result_id = payload.get("result_id")
    return CharacterizationRunHistoryRow(
        run_id=str(payload["run_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        label=str(payload["label"]),
        status=str(payload["status"]),
        scope=str(payload["scope"]),
        trace_count=int(payload["trace_count"]),
        sources_summary=str(payload["sources_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        updated_at=str(payload["updated_at"]),
        result_id=str(result_id) if isinstance(result_id, str) else None,
    )


def _parse_characterization_result_detail(
    payload: object,
) -> CharacterizationResultDetail | None:
    if not isinstance(payload, dict):
        return None
    diagnostics = payload.get("diagnostics", ())
    artifact_refs = payload.get("artifact_refs", ())
    identify_surface = payload.get("identify_surface", {})
    source_parameters = identify_surface.get("source_parameters", [])
    designated_metrics = identify_surface.get("designated_metrics", [])
    applied_tags = identify_surface.get("applied_tags", [])
    input_trace_ids = payload.get("input_trace_ids", ())
    from src.app.domain.datasets import (
        CharacterizationAppliedTag,
        CharacterizationArtifactRef,
        CharacterizationDesignatedMetricOption,
        CharacterizationDiagnostic,
        CharacterizationIdentifySurface,
        CharacterizationSourceParameterOption,
    )

    return CharacterizationResultDetail(
        result_id=str(payload["result_id"]),
        dataset_id=str(payload["dataset_id"]),
        design_id=str(payload["design_id"]),
        analysis_id=str(payload["analysis_id"]),
        title=str(payload["title"]),
        status=str(payload["status"]),
        freshness_summary=str(payload["freshness_summary"]),
        provenance_summary=str(payload["provenance_summary"]),
        trace_count=int(payload["trace_count"]),
        updated_at=str(payload["updated_at"]),
        input_trace_ids=tuple(str(item) for item in input_trace_ids if isinstance(item, str)),
        payload=dict(payload.get("payload", {})),
        diagnostics=tuple(
            CharacterizationDiagnostic(
                severity=str(item["severity"]),
                code=str(item["code"]),
                message=str(item["message"]),
                blocking=bool(item["blocking"]),
            )
            for item in diagnostics
            if isinstance(item, dict)
        ),
        artifact_refs=tuple(
            CharacterizationArtifactRef(
                artifact_id=str(item["artifact_id"]),
                category=str(item["category"]),
                view_kind=str(item["view_kind"]),
                title=str(item["title"]),
                payload_format=str(item["payload_format"]),
                payload_locator=(
                    str(item["payload_locator"])
                    if isinstance(item.get("payload_locator"), str)
                    else None
                ),
            )
            for item in artifact_refs
            if isinstance(item, dict)
        ),
        identify_surface=CharacterizationIdentifySurface(
            source_parameters=tuple(
                CharacterizationSourceParameterOption(
                    artifact_id=str(item["artifact_id"]),
                    source_parameter=str(item["source_parameter"]),
                    label=str(item["label"]),
                    artifact_title=str(item["artifact_title"]),
                    current_designated_metric=(
                        str(item["current_designated_metric"])
                        if isinstance(item.get("current_designated_metric"), str)
                        else None
                    ),
                )
                for item in source_parameters
                if isinstance(item, dict)
            ),
            designated_metrics=tuple(
                CharacterizationDesignatedMetricOption(
                    metric_key=str(item["metric_key"]),
                    label=str(item["label"]),
                )
                for item in designated_metrics
                if isinstance(item, dict)
            ),
            applied_tags=tuple(
                CharacterizationAppliedTag(
                    artifact_id=str(item["artifact_id"]),
                    source_parameter=str(item["source_parameter"]),
                    designated_metric=str(item["designated_metric"]),
                    designated_metric_label=str(item["designated_metric_label"]),
                    tagged_at=str(item["tagged_at"]),
                )
                for item in applied_tags
                if isinstance(item, dict)
            ),
        ),
    )


def _to_characterization_tagging_result(
    payload: CharacterizationTaggingResultPayload,
) -> CharacterizationTaggingResult:
    return CharacterizationTaggingResult(
        tagging_status="applied",
        dataset_id=payload.dataset_id,
        design_id=payload.design_id,
        result_id=payload.result_id,
        artifact_id=payload.artifact_id,
        source_parameter=payload.source_parameter,
        designated_metric=payload.designated_metric,
        tagged_metric=payload.tagged_metric,
    )
