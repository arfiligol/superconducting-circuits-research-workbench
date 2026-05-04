from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Protocol, cast

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
    CharacterizationAppliedTag,
    CharacterizationArtifactAxisSpec,
    CharacterizationArtifactMetricSpec,
    CharacterizationArtifactPayload,
    CharacterizationArtifactPayloadQuery,
    CharacterizationArtifactPreset,
    CharacterizationArtifactQuerySpec,
    CharacterizationArtifactRef,
    CharacterizationArtifactViewModeDefault,
    CharacterizationDesignatedMetricOption,
    CharacterizationDiagnostic,
    CharacterizationIdentifySurface,
    CharacterizationInputResultRef,
    CharacterizationResultDetail,
    CharacterizationResultSummary,
    CharacterizationRunHistoryRow,
    CharacterizationSourceParameterOption,
    CharacterizationTaggingRequest,
    CharacterizationTaggingResult,
    DatasetAllowedActions,
    DatasetCreateDraft,
    DatasetDesignMutationResult,
    DatasetDetail,
    DatasetProfileUpdate,
    DesignBrowseRow,
    DesignCreateDraft,
    DesignRenameDraft,
    DesignScopeAllowedActions,
    DesignScopeMergeResult,
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
from src.app.domain.storage import TracePayloadRef
from src.app.domain.tasks import TaskDetail
from src.app.domain.trace_ingestion import (
    build_ingested_trace_id,
    build_ingested_trace_provenance_summary,
)
from src.app.domain.trace_structures import (
    build_axis_coordinate_digest,
    build_trace_structure_summary,
)
from src.app.infrastructure.persisted_characterization_runtime import (
    CharacterizationTaggingResultPayload,
    PersistedCharacterizationRepository,
)
from src.app.infrastructure.persisted_runtime import (
    delete_trace_payload_store,
    write_complex_trace_payload,
    write_nd_complex_trace_payload,
)
from src.app.infrastructure.persistence.models import (
    RewriteCharacterizationRegistryRecord,
    RewriteDatasetDesignRecord,
    RewriteDatasetRecord,
    RewriteDatasetTraceRecord,
    RewriteTraceCapabilityRecord,
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


TRACE_DETAIL_PREVIEW_SAMPLE_LIMIT = 800


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
                select(RewriteDatasetRecord).where(RewriteDatasetRecord.dataset_id == dataset_id)
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
            next_counter = (session.scalar(select(func.count(RewriteDatasetRecord.id))) or 0) + 100
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
                select(RewriteDatasetRecord).where(RewriteDatasetRecord.dataset_id == dataset_id)
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
                select(RewriteDatasetRecord).where(RewriteDatasetRecord.dataset_id == dataset_id)
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
        existing_trace_ids = {
            row.trace_id
            for row in self._list_raw_trace_rows(dataset_id=dataset_id, design_id=design_id)
        }
        for index, trace in enumerate(draft.traces, start=1):
            preview_payload = dict(trace.preview_payload)
            trace_id = trace.trace_id or build_ingested_trace_id(
                kind=draft.kind,
                parameter=trace.parameter,
                index=index,
                provenance_label=draft.provenance_label,
                preview_payload=preview_payload,
                existing_trace_ids=existing_trace_ids,
            )
            existing_trace_ids.add(trace_id)
            provenance_summary = build_ingested_trace_provenance_summary(
                provenance_summary=trace.provenance_summary,
                provenance_label=draft.provenance_label,
                preview_payload=preview_payload,
            )
            numeric_payload = _numeric_payload_from_preview_payload(trace.axes, preview_payload)
            stored_preview_payload = _preview_payload_for_storage(
                preview_payload,
                numeric_payload=numeric_payload,
            )
            payload_ref = _materialize_trace_payload(
                dataset_id=dataset_id,
                design_id=design_id,
                trace_id=trace_id,
                axes=trace.axes,
                numeric_payload=numeric_payload,
                representation=trace.representation,
            )
            self._persist_raw_trace_storage(
                dataset_id=dataset_id,
                design_id=design_id,
                trace_id=trace_id,
                payload_ref=payload_ref,
            )
            structure = build_trace_structure_summary(
                dataset_id=dataset_id,
                design_id=design_id,
                family=trace.family,
                parameter=trace.parameter,
                representation=trace.representation,
                trace_mode_group=trace.trace_mode_group,
                source_kind=draft.kind,
                stage_kind=trace.stage_kind,
                axes=_serialize_axes_for_storage(
                    trace.axes,
                    numeric_payload=numeric_payload,
                ),
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
                provenance_summary=provenance_summary,
                ndim=structure.ndim,
                shape=structure.shape,
                axes_summary=structure.axes_summary,
                axis_signature=structure.axis_signature,
                available_sweep_axes=structure.available_sweep_axes,
                collection_projection=structure.collection_projection,
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
                    provenance_summary=provenance_summary,
                    axes=trace.axes,
                    preview_payload=stored_preview_payload,
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

    def rename_design(
        self,
        dataset_id: str,
        design_id: str,
        draft: DesignRenameDraft,
    ) -> DatasetDesignMutationResult | None:
        result = self._publication_repository.rename_design(dataset_id, design_id, draft)
        if result is None:
            return None
        return result

    def set_design_lifecycle_state(
        self,
        dataset_id: str,
        design_id: str,
        lifecycle_state: str,
    ) -> DatasetDesignMutationResult | None:
        result = self._publication_repository.set_design_lifecycle_state(
            dataset_id,
            design_id,
            lifecycle_state,
        )
        if result is None:
            return None
        return result

    def merge_design_scopes(
        self,
        dataset_id: str,
        source_design_id: str,
        target_design_id: str,
    ) -> DesignScopeMergeResult | None:
        target_trace_ids = {
            row.trace_id
            for row in self.list_trace_metadata(dataset_id, target_design_id)
        }
        source_trace_ids = {
            row.trace_id
            for row in self.list_trace_metadata(dataset_id, source_design_id)
        }
        if target_trace_ids.intersection(source_trace_ids):
            raise ValueError("trace identity collision")

        updated_at = _current_timestamp()
        reparented_counts = {
            "raw_traces": 0,
            "trace_capabilities": 0,
            "characterization_registry_rows": 0,
            "published_simulation_results": 0,
            "published_simulation_traces": 0,
            "design_assets": 0,
        }
        with self._session_factory() as session:
            raw_rows = session.scalars(
                select(RewriteDatasetTraceRecord).where(
                    RewriteDatasetTraceRecord.dataset_id == dataset_id,
                    RewriteDatasetTraceRecord.design_id == source_design_id,
                )
            ).all()
            for row in raw_rows:
                row.design_id = target_design_id
                row.updated_at = updated_at
            reparented_counts["raw_traces"] = len(raw_rows)

            capability_rows = session.scalars(
                select(RewriteTraceCapabilityRecord).where(
                    RewriteTraceCapabilityRecord.dataset_id == dataset_id,
                    RewriteTraceCapabilityRecord.design_id == source_design_id,
                )
            ).all()
            for row in capability_rows:
                row.design_id = target_design_id
            reparented_counts["trace_capabilities"] = len(capability_rows)

            registry_rows = session.scalars(
                select(RewriteCharacterizationRegistryRecord).where(
                    RewriteCharacterizationRegistryRecord.dataset_id == dataset_id,
                    RewriteCharacterizationRegistryRecord.design_id == source_design_id,
                )
            ).all()
            for row in registry_rows:
                row.design_id = target_design_id
            reparented_counts["characterization_registry_rows"] = len(registry_rows)
            session.commit()

        published_result = self._publication_repository.merge_design_scopes(
            dataset_id,
            source_design_id,
            target_design_id,
        )
        if published_result is None:
            return None
        for record_family, count in published_result.reparented_counts.items():
            reparented_counts[record_family] = (
                reparented_counts.get(record_family, 0) + count
            )
        self._touch_design(dataset_id, target_design_id, updated_at)
        source_design = self.get_design(dataset_id, source_design_id)
        target_design = self.get_design(dataset_id, target_design_id)
        dataset = self._touch_dataset(dataset_id, updated_at)
        if source_design is None or target_design is None or dataset is None:
            return None
        return DesignScopeMergeResult(
            dataset=dataset,
            source_design=source_design,
            target_design=target_design,
            reparented_counts=reparented_counts,
            recompute_status="refreshed",
            warnings=published_result.warnings,
        )

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
        design_rows = self._load_design_rows(dataset_id)
        traces_by_design: dict[str, list[RewriteDatasetTraceRecord]] = defaultdict(list)
        for trace_row in raw_trace_rows:
            traces_by_design[trace_row.design_id].append(trace_row)
        for design_id, design_record in design_rows.items():
            if design_id not in design_state:
                design_state[design_id] = _design_row_with_lifecycle(
                    design_id=design_id,
                    dataset_id=dataset_id,
                    name=design_record.name,
                    source_coverage=_empty_source_coverage(),
                    compare_readiness="blocked",
                    trace_count=0,
                    updated_at="1970-01-01T00:00:00Z",
                    lifecycle_state=design_record.lifecycle_state,
                    redirect_design_id=design_record.redirect_design_id,
                )
        for design_id, trace_rows in traces_by_design.items():
            existing = design_state.get(design_id)
            design_record = design_rows.get(design_id)
            design_name = (
                design_record.name
                if design_record is not None
                else (
                    existing.name if existing is not None else design_id
                )
            )
            lifecycle_state = (
                design_record.lifecycle_state
                if design_record is not None
                else (existing.lifecycle_state if existing is not None else "active")
            )
            redirect_design_id = (
                design_record.redirect_design_id
                if design_record is not None
                else (existing.redirect_design_id if existing is not None else None)
            )
            raw_row = _design_row_with_lifecycle(
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
                lifecycle_state=lifecycle_state,
                redirect_design_id=redirect_design_id,
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
        if update.numeric_payload is not None:
            payload_ref = _materialize_trace_payload(
                dataset_id=dataset_id,
                design_id=design_id,
                trace_id=trace_id,
                axes=axes,
                numeric_payload=numeric_payload,
                representation=update.representation or raw_row.representation,
            )
            self._persist_raw_trace_storage(
                dataset_id=dataset_id,
                design_id=design_id,
                trace_id=trace_id,
                payload_ref=payload_ref,
            )
            raw_row.payload_store_key = payload_ref.store_key
        raw_row.parameter = update.parameter or raw_row.parameter
        raw_row.representation = update.representation or raw_row.representation
        raw_row.provenance_summary = update.provenance_summary or raw_row.provenance_summary
        if update.numeric_payload is not None:
            raw_row.axes_json = _serialize_axes_for_storage(
                axes,
                numeric_payload=numeric_payload,
            )
            raw_row.preview_payload_json = preview_payload
            raw_row.numeric_payload_json = _numeric_payload_for_storage(numeric_payload)
        raw_row.updated_at = updated_at
        structure = build_trace_structure_summary(
            dataset_id=raw_row.dataset_id,
            design_id=raw_row.design_id,
            family=raw_row.family,
            parameter=raw_row.parameter,
            representation=raw_row.representation,
            trace_mode_group=raw_row.trace_mode_group,
            source_kind=raw_row.source_kind,
            stage_kind=raw_row.stage_kind,
            axes=tuple(raw_row.axes_json),
        )
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
            ndim=structure.ndim,
            shape=structure.shape,
            axes_summary=structure.axes_summary,
            axis_signature=structure.axis_signature,
            available_sweep_axes=structure.available_sweep_axes,
            collection_projection=structure.collection_projection,
        )
        analysis_capabilities = evaluate_trace_analysis_capabilities(
            dataset_family=dataset.family,
            trace=updated_summary,
            axes=axes,
        )
        with self._session_factory() as session:
            persisted = session.scalar(
                select(RewriteDatasetTraceRecord).where(RewriteDatasetTraceRecord.id == raw_row.id)
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

    def get_characterization_artifact_payload(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        artifact_id: str,
        query: CharacterizationArtifactPayloadQuery,
    ) -> CharacterizationArtifactPayload | None:
        payload = self._characterization_repository.get_artifact_payload(
            dataset_id,
            design_id,
            result_id,
            artifact_id,
            query,
        )
        if payload is not None:
            return payload
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
            representation=summary.representation,
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
                select(RewriteDatasetRecord).where(RewriteDatasetRecord.dataset_id == dataset_id)
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

    def _load_design_rows(
        self,
        dataset_id: str,
    ) -> dict[str, RewriteDatasetDesignRecord]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteDatasetDesignRecord).where(
                    RewriteDatasetDesignRecord.dataset_id == dataset_id
                )
            ).all()
            return {row.design_id: row for row in rows}

    def _to_trace_detail(self, row: RewriteDatasetTraceRecord) -> TraceDetail:
        analysis_capabilities = self._load_trace_capabilities(
            row.dataset_id,
            row.design_id,
            row.trace_id,
        )
        structure = _trace_structure_surface_from_row(row)
        payload_ref = self._storage_metadata_repository.get_trace_payload(row.payload_store_key)
        result_handles = tuple(
            handle
            for handle_id in row.result_handle_ids_json
            if (handle := self._storage_metadata_repository.get_result_handle(handle_id))
            is not None
        )
        axes = tuple(_deserialize_axis(item) for item in row.axes_json)
        return TraceDetail(
            trace_id=row.trace_id,
            dataset_id=row.dataset_id,
            design_id=row.design_id,
            family=cast(str, row.family),
            parameter=row.parameter,
            representation=row.representation,
            trace_mode_group=cast(str, row.trace_mode_group),
            source_kind=cast(str, row.source_kind),
            stage_kind=cast(str, row.stage_kind),
            axes=axes,
            ndim=structure.ndim,
            shape=structure.shape,
            axes_summary=structure.axes_summary,
            axis_signature=structure.axis_signature,
            available_sweep_axes=structure.available_sweep_axes,
            collection_projection=structure.collection_projection,
            preview_payload=_trace_preview_payload_with_sampled_slice(
                preview_payload=dict(row.preview_payload_json),
                payload_ref=payload_ref,
                axes=axes,
                parameter=row.parameter,
                representation=row.representation,
            ),
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
                (event for event in reversed(task.events) if event.event_type == "task_completed"),
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
        row.axes_json = _serialize_axes_for_storage(
            draft.axes,
            numeric_payload=draft.numeric_payload,
        )
        row.preview_payload_json = dict(draft.preview_payload)
        row.numeric_payload_json = _numeric_payload_for_storage(draft.numeric_payload)
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
    structure = _trace_structure_surface_from_row(row)
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
        ndim=structure.ndim,
        shape=structure.shape,
        axes_summary=structure.axes_summary,
        axis_signature=structure.axis_signature,
        available_sweep_axes=structure.available_sweep_axes,
        collection_projection=structure.collection_projection,
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
        ndim=summary.ndim,
        shape=summary.shape,
        axes_summary=summary.axes_summary,
        axis_signature=summary.axis_signature,
        available_sweep_axes=summary.available_sweep_axes,
        collection_projection=summary.collection_projection,
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


def _serialize_axes_for_storage(
    axes: tuple[TraceAxis, ...],
    *,
    numeric_payload: dict[str, object],
) -> list[dict[str, object]]:
    coordinate_digests = _axis_coordinate_digests_from_numeric_payload(
        axes,
        numeric_payload=numeric_payload,
    )
    return [
        {
            **_serialize_axis(axis),
            **(
                {"coordinate_digest": coordinate_digests[axis.name]}
                if axis.name in coordinate_digests
                else {}
            ),
        }
        for axis in axes
    ]


def _deserialize_axis(payload: dict[str, object]) -> TraceAxis:
    return TraceAxis(
        name=str(payload["name"]),
        unit=str(payload["unit"]),
        length=int(payload["length"]),
    )


def _trace_structure_surface_from_row(
    row: RewriteDatasetTraceRecord,
):
    return build_trace_structure_summary(
        dataset_id=row.dataset_id,
        design_id=row.design_id,
        family=row.family,
        parameter=row.parameter,
        representation=row.representation,
        trace_mode_group=row.trace_mode_group,
        source_kind=row.source_kind,
        stage_kind=row.stage_kind,
        axes=tuple(row.axes_json),
    )


def _axis_coordinate_digests_from_numeric_payload(
    axes: tuple[TraceAxis, ...],
    *,
    numeric_payload: dict[str, object],
) -> dict[str, str]:
    if len(axes) == 0:
        return {}
    if numeric_payload.get("kind") == "nd_grid":
        return {
            axis.name: build_axis_coordinate_digest(
                axis_name=axis.name,
                unit=axis.unit,
                length=axis.length,
                values=tuple(float(value) for value in payload_axis["values"]),
            )
            for axis, payload_axis in zip(
                axes,
                _nd_grid_axes_payload(numeric_payload),
                strict=True,
            )
        }
    axis_key = _numeric_payload_axis_key(numeric_payload)
    rows = numeric_payload.get("rows")
    if not isinstance(rows, list):
        return {}
    axis_values = [
        float(row.get(axis_key))
        for row in rows
        if isinstance(row, dict) and isinstance(row.get(axis_key), int | float)
    ]
    if len(axis_values) == 0:
        return {}
    primary_axis = axes[0]
    return {
        primary_axis.name: build_axis_coordinate_digest(
            axis_name=primary_axis.name,
            unit=primary_axis.unit,
            length=primary_axis.length,
            values=axis_values,
        )
    }


def _build_dataset_id(*, workspace_id: str, name: str, counter: int) -> str:
    slug = _slugify(name)
    if workspace_id == "local-space":
        return f"local-{slug}-{counter}"
    return f"{slug}-{counter}"


def _build_design_id(name: str) -> str:
    return f"design_{_slugify(name)}"


def _slugify(value: str) -> str:
    return "-".join(
        token
        for token in "".join(
            character.lower() if character.isalnum() else "-" for character in value.strip()
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
    lifecycle_state = (
        existing.lifecycle_state
        if existing.lifecycle_state != "active"
        else incoming.lifecycle_state
    )
    redirect_design_id = existing.redirect_design_id or incoming.redirect_design_id
    return _design_row_with_lifecycle(
        design_id=incoming.design_id,
        dataset_id=incoming.dataset_id,
        name=existing.name or incoming.name,
        source_coverage=coverage,
        compare_readiness=_compare_readiness_for(coverage),
        trace_count=existing.trace_count + incoming.trace_count,
        updated_at=max(existing.updated_at, incoming.updated_at),
        lifecycle_state=lifecycle_state,
        redirect_design_id=redirect_design_id,
    )


def _design_row_with_lifecycle(
    *,
    design_id: str,
    dataset_id: str,
    name: str,
    source_coverage: dict[str, int],
    compare_readiness: str,
    trace_count: int,
    updated_at: str,
    lifecycle_state: str = "active",
    redirect_design_id: str | None = None,
) -> DesignBrowseRow:
    active = lifecycle_state == "active"
    return DesignBrowseRow(
        design_id=design_id,
        dataset_id=dataset_id,
        name=name,
        source_coverage=source_coverage,
        compare_readiness=cast(str, compare_readiness),
        trace_count=trace_count,
        updated_at=updated_at,
        lifecycle_state=cast(str, lifecycle_state),
        redirect_design_id=redirect_design_id,
        allowed_actions=DesignScopeAllowedActions(
            rename=active,
            merge=active,
            archive=active,
            delete=active,
            use_as_target=active,
        ),
        mutation_policy_summary=(
            "Active design scope; usable as a target."
            if active
            else (
                f"Archived design scope; redirected to {redirect_design_id}."
                if redirect_design_id is not None
                else f"{lifecycle_state.title()} design scope; not usable as a target."
            )
        ),
    )


def _numeric_payload_from_preview_payload(
    axes: tuple[TraceAxis, ...],
    preview_payload: dict[str, object],
) -> dict[str, object]:
    if preview_payload.get("kind") == "nd_grid":
        return _nd_grid_numeric_payload_from_preview_payload(axes, preview_payload)

    axis = axes[0] if len(axes) > 0 else TraceAxis(name="frequency", unit="GHz", length=0)
    points = preview_payload.get("points")
    rows: list[dict[str, object]] = []
    if isinstance(points, list):
        for item in points:
            if isinstance(item, list | tuple) and len(item) >= 2:
                rows.append({axis.name: item[0], "value": item[1]})
    if len(rows) == 0:
        rows = [{axis.name: float(index), "value": 0.0} for index in range(axis.length)]
    return {
        "kind": "series_table",
        "columns": [
            {"key": axis.name, "label": axis.name.title(), "unit": axis.unit, "role": "axis"},
            {"key": "value", "label": "Value", "unit": None, "role": "value"},
        ],
        "rows": rows,
    }


def _nd_grid_numeric_payload_from_preview_payload(
    axes: tuple[TraceAxis, ...],
    preview_payload: dict[str, object],
) -> dict[str, object]:
    raw_grid_axes = preview_payload.get("axes")
    if not isinstance(raw_grid_axes, list) or len(raw_grid_axes) == 0:
        raise ValueError("nd_grid preview_payload.axes must be a non-empty array.")
    if len(raw_grid_axes) != len(axes):
        raise ValueError("nd_grid axis count must match trace axes.")

    normalized_axes: list[dict[str, object]] = []
    for axis_index, (declared_axis, raw_axis) in enumerate(
        zip(axes, raw_grid_axes, strict=True)
    ):
        if not isinstance(raw_axis, dict):
            raise ValueError("nd_grid preview_payload.axes entries must be objects.")
        axis_name = str(raw_axis.get("name", declared_axis.name)).strip()
        axis_unit = str(raw_axis.get("unit", declared_axis.unit)).strip()
        if axis_name != declared_axis.name:
            raise ValueError(
                f"nd_grid axis {axis_index} name {axis_name!r} does not match "
                f"declared trace axis {declared_axis.name!r}."
            )
        if axis_unit != declared_axis.unit:
            raise ValueError(
                f"nd_grid axis {axis_index} unit {axis_unit!r} does not match "
                f"declared trace axis {declared_axis.unit!r}."
            )
        axis_values = _coerce_float_sequence(
            raw_axis.get("values"),
            field=f"nd_grid.axes[{axis_index}].values",
        )
        if len(axis_values) != declared_axis.length:
            raise ValueError(
                f"nd_grid axis {axis_name!r} has {len(axis_values)} values, "
                f"expected {declared_axis.length}."
            )
        normalized_axes.append(
            {
                "name": declared_axis.name,
                "unit": declared_axis.unit,
                "values": list(axis_values),
            }
        )

    expected_shape = tuple(len(axis["values"]) for axis in normalized_axes)
    values = np.asarray(preview_payload.get("values"), dtype=np.float64)
    if values.shape != expected_shape:
        raise ValueError(
            f"nd_grid values shape {values.shape!r} does not match axes {expected_shape!r}."
        )
    return {
        "kind": "nd_grid",
        "axes": normalized_axes,
        "shape": list(expected_shape),
        "values": values.tolist(),
    }


def _coerce_float_sequence(value: object, *, field: str) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array.")
    return tuple(float(item) for item in value)


def _numeric_payload_for_storage(numeric_payload: dict[str, object]) -> dict[str, object]:
    if numeric_payload.get("kind") != "nd_grid":
        return dict(numeric_payload)
    axes_payload = _nd_grid_axes_payload(numeric_payload)
    return {
        "kind": "nd_grid",
        "axes": [
            {
                "name": axis["name"],
                "unit": axis["unit"],
                "length": len(axis["values"]),
                "coordinate_digest": build_axis_coordinate_digest(
                    axis_name=str(axis["name"]),
                    unit=str(axis["unit"]),
                    length=len(axis["values"]),
                    values=tuple(float(value) for value in axis["values"]),
                ),
            }
            for axis in axes_payload
        ],
        "shape": list(_nd_grid_shape(numeric_payload)),
        "values_ref": "trace_store",
    }


def _preview_payload_for_storage(
    preview_payload: dict[str, object],
    *,
    numeric_payload: dict[str, object],
) -> dict[str, object]:
    if numeric_payload.get("kind") != "nd_grid":
        return dict(preview_payload)
    return {
        "kind": "nd_grid",
        "axes": [
            {
                "name": axis["name"],
                "unit": axis["unit"],
                "length": len(axis["values"]),
            }
            for axis in _nd_grid_axes_payload(numeric_payload)
        ],
        "shape": list(_nd_grid_shape(numeric_payload)),
        "values_ref": "trace_store",
    }


def _preview_payload_from_numeric_payload(numeric_payload: dict[str, object]) -> dict[str, object]:
    if numeric_payload.get("kind") == "nd_grid":
        return _nd_grid_preview_payload_from_numeric_payload(numeric_payload)
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
    if numeric_payload.get("kind") == "nd_grid":
        return _nd_grid_shape(numeric_payload)
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
    if len(lengths) == len(axes):
        return tuple(
            replace(axis, length=length)
            for axis, length in zip(axes, lengths, strict=True)
        )
    return (replace(axes[0], length=lengths[0]), *axes[1:])


def _materialize_trace_payload(
    *,
    dataset_id: str,
    design_id: str,
    trace_id: str,
    axes: tuple[TraceAxis, ...],
    numeric_payload: dict[str, object],
    representation: str,
    store_key: str | None = None,
) -> Any:
    if numeric_payload.get("kind") == "nd_grid":
        return _materialize_nd_grid_trace_payload(
            dataset_id=dataset_id,
            design_id=design_id,
            trace_id=trace_id,
            numeric_payload=numeric_payload,
            representation=representation,
            store_key=store_key,
        )

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
        values.append(float(y_value))
    if len(frequencies) == 0:
        length = axes[0].length if len(axes) > 0 else 1
        frequencies = [float(index) for index in range(length)]
        values = [0.0 for _ in range(length)]
    return write_complex_trace_payload(
        dataset_id=dataset_id,
        design_id=design_id,
        trace_id=trace_id,
        frequencies_ghz=frequencies,
        values=_component_values_as_complex(
            np.asarray(values, dtype=np.float64),
            representation=representation,
        ),
        store_key=store_key
        or f"trace_store/datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr",
    )


def _materialize_nd_grid_trace_payload(
    *,
    dataset_id: str,
    design_id: str,
    trace_id: str,
    numeric_payload: dict[str, object],
    representation: str,
    store_key: str | None,
) -> Any:
    values = np.asarray(numeric_payload.get("values"), dtype=np.float64)
    shape = _nd_grid_shape(numeric_payload)
    if values.shape != shape:
        raise ValueError(f"nd_grid values shape {values.shape!r} does not match {shape!r}.")
    return write_nd_complex_trace_payload(
        dataset_id=dataset_id,
        design_id=design_id,
        trace_id=trace_id,
        axes=tuple(
            {
                "name": axis["name"],
                "unit": axis["unit"],
                "values": np.asarray(axis["values"], dtype=np.float64),
            }
            for axis in _nd_grid_axes_payload(numeric_payload)
        ),
        values=_component_values_as_complex(values, representation=representation),
        store_key=store_key
        or f"trace_store/datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr",
    )


def _component_values_as_complex(values: np.ndarray, *, representation: str) -> np.ndarray:
    normalized_representation = representation.casefold()
    if normalized_representation in {"imag", "imaginary"}:
        return (1j * values).astype(np.complex128)
    return values.astype(np.complex128)


def _trace_preview_payload_with_sampled_slice(
    *,
    preview_payload: dict[str, object],
    payload_ref: TracePayloadRef | None,
    axes: tuple[TraceAxis, ...],
    parameter: str,
    representation: str,
) -> dict[str, object]:
    if (
        preview_payload.get("kind") != "nd_grid"
        or preview_payload.get("values_ref") != "trace_store"
        or payload_ref is None
    ):
        return preview_payload
    sampled_preview = _sample_trace_store_nd_preview(
        payload_ref=payload_ref,
        axes=axes,
        representation=representation,
    )
    if sampled_preview is None:
        return preview_payload

    return {
        **preview_payload,
        "points": sampled_preview["points"],
        "x_axis": sampled_preview["x_axis"],
        "y_axis": {
            "label": f"{parameter} · {_format_preview_representation(representation)}",
            "unit": None,
        },
        "preview_sample": sampled_preview["preview_sample"],
    }


def _sample_trace_store_nd_preview(
    *,
    payload_ref: TracePayloadRef,
    axes: tuple[TraceAxis, ...],
    representation: str,
) -> dict[str, object] | None:
    if len(axes) == 0:
        return None
    frequency_axis_index = next(
        (index for index, axis in enumerate(axes) if axis.name == "frequency"),
        0,
    )
    frequency_axis = axes[frequency_axis_index]
    try:
        from core.shared.persistence import LocalZarrTraceStore, get_trace_store_path

        trace_store = LocalZarrTraceStore(root_path=get_trace_store_path())
        store_ref = _trace_payload_ref_to_store_ref(payload_ref)
        x_values = np.asarray(
            trace_store.read_axis_slice(
                store_ref,
                axis_name=frequency_axis.name,
                selection=slice(None),
            ),
            dtype=np.float64,
        ).reshape(-1)
        selection: list[object] = []
        fixed_axes: list[dict[str, object]] = []
        for index, axis in enumerate(axes):
            if index == frequency_axis_index:
                selection.append(slice(None))
                continue
            selection.append(0)
            axis_value = _read_trace_axis_value(trace_store, store_ref, axis.name, index=0)
            fixed_axes.append(
                {
                    "name": axis.name,
                    "unit": axis.unit,
                    "index": 0,
                    "value": axis_value,
                }
            )
        raw_values = np.asarray(
            trace_store.read_trace_slice(store_ref, selection=tuple(selection))
        ).reshape(-1)
    except Exception:
        return None

    if x_values.shape[0] != raw_values.shape[0]:
        return None
    sampled_indices = _sample_indices(len(x_values), TRACE_DETAIL_PREVIEW_SAMPLE_LIMIT)
    component_values = _preview_component_values(raw_values, representation=representation)
    points = [
        [float(x_values[index]), float(component_values[index])]
        for index in sampled_indices
        if np.isfinite(x_values[index]) and np.isfinite(component_values[index])
    ]
    return {
        "points": points,
        "x_axis": {
            "label": _format_preview_axis_label(frequency_axis.name),
            "unit": frequency_axis.unit or None,
            "sampled": len(sampled_indices) < len(x_values),
        },
        "preview_sample": {
            "source": "trace_store",
            "sample_limit": TRACE_DETAIL_PREVIEW_SAMPLE_LIMIT,
            "sample_count": len(points),
            "total_point_count": len(x_values),
            "fixed_axes": fixed_axes,
        },
    }


def _trace_payload_ref_to_store_ref(payload_ref: TracePayloadRef) -> dict[str, object]:
    return {
        "backend": payload_ref.backend,
        "store_key": payload_ref.store_key,
        "store_uri": payload_ref.store_uri,
        "group_path": payload_ref.group_path,
        "array_path": payload_ref.array_path,
        "dtype": payload_ref.dtype,
        "shape": tuple(payload_ref.shape),
        "chunk_shape": tuple(payload_ref.chunk_shape),
        "schema_version": payload_ref.schema_version,
    }


def _read_trace_axis_value(
    trace_store: object,
    store_ref: dict[str, object],
    axis_name: str,
    *,
    index: int,
) -> float | None:
    try:
        raw_values = np.asarray(
            trace_store.read_axis_slice(
                store_ref,
                axis_name=axis_name,
                selection=slice(index, index + 1),
            ),
            dtype=np.float64,
        ).reshape(-1)
    except Exception:
        return None
    return float(raw_values[0]) if len(raw_values) > 0 else None


def _sample_indices(point_count: int, sample_limit: int) -> tuple[int, ...]:
    if point_count <= 0:
        return ()
    if point_count <= sample_limit:
        return tuple(range(point_count))
    return tuple(
        dict.fromkeys(
            int(index)
            for index in np.linspace(0, point_count - 1, sample_limit, dtype=np.int64)
        )
    )


def _preview_component_values(values: np.ndarray, *, representation: str) -> np.ndarray:
    normalized = representation.casefold()
    if normalized in {"imag", "imaginary"}:
        return np.asarray(values.imag, dtype=np.float64)
    if normalized in {"real", "re"}:
        return np.asarray(values.real, dtype=np.float64)
    if normalized in {"phase", "angle"}:
        return np.asarray(np.angle(values), dtype=np.float64)
    return np.asarray(np.abs(values), dtype=np.float64)


def _format_preview_axis_label(axis_name: str) -> str:
    return " ".join(part.capitalize() for part in axis_name.split("_") if part) or axis_name


def _format_preview_representation(representation: str) -> str:
    normalized = representation.casefold()
    if normalized in {"imag", "imaginary"}:
        return "Imaginary"
    if normalized in {"real", "re"}:
        return "Real"
    if normalized == "phase":
        return "Phase"
    if normalized in {"mag", "magnitude"}:
        return "Magnitude"
    return _format_preview_axis_label(representation)


def _nd_grid_axes_payload(numeric_payload: dict[str, object]) -> tuple[dict[str, object], ...]:
    raw_axes = numeric_payload.get("axes")
    if not isinstance(raw_axes, list):
        raise ValueError("nd_grid numeric payload is missing axes.")
    axes_payload: list[dict[str, object]] = []
    for axis in raw_axes:
        if not isinstance(axis, dict):
            raise ValueError("nd_grid numeric payload axes must be objects.")
        raw_values = axis.get("values")
        if not isinstance(raw_values, list):
            raise ValueError("nd_grid numeric payload axes require values.")
        axes_payload.append(
            {
                "name": str(axis.get("name", "")).strip(),
                "unit": str(axis.get("unit", "")).strip(),
                "values": [float(value) for value in raw_values],
            }
        )
    return tuple(axes_payload)


def _nd_grid_preview_payload_from_numeric_payload(
    numeric_payload: dict[str, object],
) -> dict[str, object]:
    raw_axes = numeric_payload.get("axes")
    if not isinstance(raw_axes, list):
        return {"kind": "nd_grid", "axes": [], "shape": [], "values_ref": "trace_store"}
    axes_payload: list[dict[str, object]] = []
    for axis in raw_axes:
        if not isinstance(axis, dict):
            continue
        axis_values = axis.get("values")
        axis_length = (
            len(axis_values)
            if isinstance(axis_values, list)
            else int(axis.get("length", 0))
        )
        axes_payload.append(
            {
                "name": str(axis.get("name", "")).strip(),
                "unit": str(axis.get("unit", "")).strip(),
                "length": axis_length,
            }
        )
    return {
        "kind": "nd_grid",
        "axes": axes_payload,
        "shape": [axis["length"] for axis in axes_payload],
        "values_ref": "trace_store",
    }


def _nd_grid_shape(numeric_payload: dict[str, object]) -> tuple[int, ...]:
    return tuple(len(axis["values"]) for axis in _nd_grid_axes_payload(numeric_payload))


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
    input_result_refs = payload.get("input_result_refs", ())
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
        input_result_refs=tuple(
            CharacterizationInputResultRef(
                analysis_id=str(item.get("analysis_id", "")),
                result_id=str(item.get("result_id", "")),
                run_id=str(item.get("run_id")) if isinstance(item.get("run_id"), str) else None,
                artifact_id=(
                    str(item.get("artifact_id"))
                    if isinstance(item.get("artifact_id"), str)
                    else None
                ),
                contract_version=(
                    str(item.get("contract_version"))
                    if isinstance(item.get("contract_version"), str)
                    else None
                ),
                title=str(item.get("title")) if isinstance(item.get("title"), str) else None,
            )
            for item in input_result_refs
            if isinstance(item, dict)
        ),
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
    input_result_refs = payload.get("input_result_refs", ())
    downstream_unlock_analysis_ids = payload.get("downstream_unlock_analysis_ids", ())
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
        input_result_refs=tuple(
            CharacterizationInputResultRef(
                analysis_id=str(item.get("analysis_id", "")),
                result_id=str(item.get("result_id", "")),
                run_id=str(item.get("run_id")) if isinstance(item.get("run_id"), str) else None,
                artifact_id=(
                    str(item.get("artifact_id"))
                    if isinstance(item.get("artifact_id"), str)
                    else None
                ),
                contract_version=(
                    str(item.get("contract_version"))
                    if isinstance(item.get("contract_version"), str)
                    else None
                ),
                title=str(item.get("title")) if isinstance(item.get("title"), str) else None,
            )
            for item in input_result_refs
            if isinstance(item, dict)
        ),
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
                axes=tuple(
                    CharacterizationArtifactAxisSpec(
                        axis_key=str(axis["axis_key"]),
                        label=str(axis["label"]),
                        role=str(axis["role"]),
                        unit=str(axis["unit"]) if isinstance(axis.get("unit"), str) else None,
                        length=int(axis["length"]),
                    )
                    for axis in item.get("axes", ())
                    if isinstance(axis, dict)
                ),
                metric=(
                    CharacterizationArtifactMetricSpec(
                        metric_key=str(item["metric"]["metric_key"]),
                        label=str(item["metric"]["label"]),
                        unit=(
                            str(item["metric"]["unit"])
                            if isinstance(item["metric"].get("unit"), str)
                            else None
                        ),
                    )
                    if isinstance(item.get("metric"), dict)
                    else None
                ),
                presets=tuple(
                    CharacterizationArtifactPreset(
                        preset_id=str(preset["preset_id"]),
                        label=str(preset["label"]),
                        view_kind=str(preset["view_kind"]),
                        rows_axis=(
                            str(preset["rows_axis"])
                            if isinstance(preset.get("rows_axis"), str)
                            else None
                        ),
                        columns_axis=(
                            str(preset["columns_axis"])
                            if isinstance(preset.get("columns_axis"), str)
                            else None
                        ),
                        cell_metric=(
                            str(preset["cell_metric"])
                            if isinstance(preset.get("cell_metric"), str)
                            else None
                        ),
                        x_axis=(
                            str(preset["x_axis"]) if isinstance(preset.get("x_axis"), str) else None
                        ),
                        y_metric=(
                            str(preset["y_metric"])
                            if isinstance(preset.get("y_metric"), str)
                            else None
                        ),
                        series_axis=(
                            str(preset["series_axis"])
                            if isinstance(preset.get("series_axis"), str)
                            else None
                        ),
                        compare_axis=(
                            str(preset["compare_axis"])
                            if isinstance(preset.get("compare_axis"), str)
                            else None
                        ),
                    )
                    for preset in item.get("presets", ())
                    if isinstance(preset, dict)
                ),
                default_preset_id=(
                    str(item["default_preset_id"])
                    if isinstance(item.get("default_preset_id"), str)
                    else None
                ),
                query_spec=(
                    CharacterizationArtifactQuerySpec(
                        query_style=str(item["query_spec"]["query_style"]),
                        supported_query_fields=tuple(
                            str(field)
                            for field in item["query_spec"].get("supported_query_fields", ())
                            if isinstance(field, str)
                        ),
                        supported_view_modes=tuple(
                            str(mode)
                            for mode in item["query_spec"].get("supported_view_modes", ())
                            if isinstance(mode, str)
                        ),
                        supported_preset_ids=tuple(
                            str(preset_id)
                            for preset_id in item["query_spec"].get("supported_preset_ids", ())
                            if isinstance(preset_id, str)
                        ),
                        default_preset_id=(
                            str(item["query_spec"]["default_preset_id"])
                            if isinstance(item["query_spec"].get("default_preset_id"), str)
                            else None
                        ),
                        default_presets_by_view_mode=tuple(
                            CharacterizationArtifactViewModeDefault(
                                view_mode=str(default_item["view_mode"]),
                                preset_id=str(default_item["preset_id"]),
                            )
                            for default_item in item["query_spec"].get(
                                "default_presets_by_view_mode",
                                (),
                            )
                            if isinstance(default_item, dict)
                        ),
                    )
                    if isinstance(item.get("query_spec"), dict)
                    else None
                ),
                identify_source=bool(item.get("identify_source", False)),
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
        downstream_unlock_analysis_ids=tuple(
            str(analysis_id)
            for analysis_id in downstream_unlock_analysis_ids
            if isinstance(analysis_id, str)
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
