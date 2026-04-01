import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from src.app.domain.admittance_result_contract import (
    AdmittanceResultSurface,
    annotate_admittance_artifact_refs,
    build_admittance_artifact_refs,
    build_admittance_identify_surface,
    query_admittance_artifact_payload,
    summarize_admittance_surface,
)
from src.app.domain.circuit_definitions import (
    CircuitDefinitionCloneDraft,
    CircuitDefinitionDraft,
    CircuitDefinitionRecord,
    CircuitDefinitionUpdate,
    DefinitionId,
    ValidationNotice,
    ValidationSummary,
)
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
    RawDataIngestionDraft,
    RawDataIngestionResult,
    ResultTracePublicationDraft,
    ResultTracePublicationResult,
    SimulationResultPublicationDraft,
    SimulationResultPublicationRecord,
    SimulationResultPublicationResult,
    TaggedCoreMetricSummary,
    TraceAllowedActions,
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
from src.app.domain.result_traces import ResultTraceSelection, build_trace_parameter
from src.app.domain.tasks import TaskDetail
from src.app.domain.trace_structures import build_trace_structure_summary
from src.app.infrastructure.persisted_characterization_runtime import (
    CharacterizationTaggingResultPayload,
    PersistedCharacterizationRepository,
)
from src.app.infrastructure.persistence.research_data_publication_repository import (
    SqliteResearchDataPublicationRepository,
)
from src.app.infrastructure.simulation_result_publication_materializer import (
    build_result_trace_publication_detail,
    build_result_trace_publication_summary,
    build_simulation_publication_key,
    build_simulation_publication_traces,
)
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)


class CharacterizationTaskRepository(Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...


class DurableCircuitDefinitionRepository(Protocol):
    def list_all_circuit_definitions(self) -> Sequence[CircuitDefinitionRecord]: ...

    def save_circuit_definition(self, record: CircuitDefinitionRecord) -> None: ...


LOCAL_SPACE_RESONATOR_DEFINITION_ID = "c8f08463-bf18-4f8e-a5d5-735f3d7b0d6e"
FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID = "8f2e5b78-7d1f-4c4f-9f3a-4be4f9e63211"
FLUXONIUM_READOUT_CHAIN_DEFINITION_ID = "3c412c9f-3304-4efe-9f7f-1d0c9a2b7d44"
COUPLER_DETUNING_DEMO_DEFINITION_ID = "f4b9ac3e-8ef1-4a8d-b7ae-6f9d24804d1a"


class InMemoryRewriteCatalogRepository:
    def __init__(
        self,
        durable_definition_repository: DurableCircuitDefinitionRepository | None = None,
        durable_publication_repository: SqliteResearchDataPublicationRepository | None = None,
        durable_characterization_repository: PersistedCharacterizationRepository | None = None,
        task_repository: CharacterizationTaskRepository | None = None,
    ) -> None:
        self._datasets = {dataset.dataset_id: dataset for dataset in _seed_datasets()}
        self._tagged_core_metrics = _seed_tagged_core_metrics()
        self._designs = _seed_designs()
        self._trace_summaries = _seed_trace_summaries()
        self._trace_details = _seed_trace_details()
        self._trace_edit_payloads = {
            key: _editable_numeric_payload_from_detail(detail)
            for key, detail in self._trace_details.items()
        }
        self._mutable_trace_keys: set[tuple[str, str, str]] = set()
        self._characterization_analysis_registry = _seed_characterization_analysis_registry()
        self._characterization_run_history = _seed_characterization_run_history()
        self._characterization_results = _seed_characterization_results()
        self._characterization_result_details = _seed_characterization_result_details()
        self._characterization_artifact_surfaces = _seed_characterization_artifact_surfaces()
        self._durable_definition_repository = durable_definition_repository
        self._circuit_definitions = {
            definition.definition_id: definition for definition in _seed_circuit_definitions()
        }
        durable_definitions = tuple(
            self._durable_definition_repository.list_all_circuit_definitions()
            if self._durable_definition_repository is not None
            else ()
        )
        for definition in durable_definitions:
            if definition.lifecycle_state == "deleted":
                self._circuit_definitions.pop(definition.definition_id, None)
                continue
            self._circuit_definitions[definition.definition_id] = definition
        self._durable_publication_repository = durable_publication_repository
        self._durable_characterization_repository = durable_characterization_repository
        self._task_repository = task_repository
        self._next_dataset_id = 100
        self._next_definition_sequence = len(self._circuit_definitions) + 1

    def list_dataset_details(self) -> list[DatasetDetail]:
        return list(self._datasets.values())

    def get_dataset(self, dataset_id: str) -> DatasetDetail | None:
        return self._datasets.get(dataset_id)

    def create_dataset(
        self,
        *,
        workspace_id: str,
        visibility_scope: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: DatasetCreateDraft,
    ) -> DatasetDetail:
        dataset_id = _build_dataset_id(
            workspace_id=workspace_id,
            name=draft.name,
            counter=self._next_dataset_id,
        )
        created = DatasetDetail(
            dataset_id=dataset_id,
            name=draft.name,
            family=draft.family,
            owner=owner_display_name,
            owner_user_id=owner_user_id,
            workspace_id=workspace_id,
            visibility_scope=visibility_scope,
            lifecycle_state="active",
            updated_at="2026-03-17T10:15:00Z",
            device_type=draft.device_type,
            capabilities=(),
            source=draft.source,
            status="Ready",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=visibility_scope != "workspace" and workspace_id != "local-space",
                archive=True,
                delete=True,
                ingest_raw_data=True,
            ),
        )
        self._datasets[dataset_id] = created
        self._tagged_core_metrics[dataset_id] = ()
        self._designs[dataset_id] = ()
        self._next_dataset_id += 1
        return created

    def set_dataset_lifecycle_state(
        self,
        dataset_id: str,
        lifecycle_state: str,
    ) -> DatasetDetail | None:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            return None
        updated_dataset = replace(
            dataset,
            lifecycle_state=lifecycle_state,
            updated_at="2026-03-17T10:18:00Z",
        )
        self._datasets[dataset_id] = updated_dataset
        return updated_dataset

    def ingest_raw_data(
        self,
        dataset_id: str,
        draft: RawDataIngestionDraft,
    ) -> RawDataIngestionResult | None:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            return None
        design_id = draft.design_id or _build_design_id(draft.design_name)
        trace_rows: list[TraceMetadataSummary] = list(
            self._trace_summaries.get((dataset_id, design_id), ())
        )
        ingested_trace_rows: list[TraceMetadataSummary] = []
        for index, trace in enumerate(draft.traces, start=1):
            trace_id = trace.trace_id or _build_trace_id(
                kind=draft.kind,
                parameter=trace.parameter,
                index=index,
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
            detail = TraceDetail(
                trace_id=trace_id,
                dataset_id=dataset_id,
                design_id=design_id,
                axes=trace.axes,
                preview_payload=trace.preview_payload,
                payload_ref=build_trace_payload_ref(
                    payload_role="dataset_primary",
                    store_key=f"trace_store/datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr",
                    store_uri=f"trace_store/datasets/{dataset_id}/designs/{design_id}/{trace_id}.zarr",
                    group_path=f"/datasets/{dataset_id}/designs/{design_id}",
                    array_path=trace_id,
                    dtype="complex64",
                    shape=tuple(axis.length for axis in trace.axes),
                    chunk_shape=tuple(axis.length for axis in trace.axes),
                ),
                result_handles=(),
            )
            self._trace_details[(dataset_id, design_id, trace_id)] = detail
            self._trace_edit_payloads[(dataset_id, design_id, trace_id)] = (
                _editable_numeric_payload_from_preview_payload(
                    trace.axes,
                    trace.preview_payload,
                )
            )
            self._mutable_trace_keys.add((dataset_id, design_id, trace_id))
            trace_rows = [row for row in trace_rows if row.trace_id != trace_id]
            trace_rows.append(summary)
            ingested_trace_rows.append(summary)
        self._trace_summaries[(dataset_id, design_id)] = tuple(
            sorted(trace_rows, key=lambda row: row.trace_id)
        )

        design_rows = list(self._designs.get(dataset_id, ()))
        source_coverage = _build_source_coverage(self._trace_summaries[(dataset_id, design_id)])
        design_row = DesignBrowseRow(
            design_id=design_id,
            dataset_id=dataset_id,
            name=draft.design_name,
            source_coverage=source_coverage,
            compare_readiness=_compare_readiness_for(source_coverage),
            trace_count=len(self._trace_summaries[(dataset_id, design_id)]),
            updated_at="2026-03-17T10:20:00Z",
        )
        design_rows = [row for row in design_rows if row.design_id != design_id]
        design_rows.append(design_row)
        self._designs[dataset_id] = tuple(sorted(design_rows, key=lambda row: row.design_id))

        updated_dataset = replace(dataset, updated_at="2026-03-17T10:20:00Z")
        self._datasets[dataset_id] = updated_dataset
        return RawDataIngestionResult(
            dataset=updated_dataset,
            design=design_row,
            traces=tuple(ingested_trace_rows),
        )

    def create_design(
        self,
        dataset_id: str,
        draft: DesignCreateDraft,
    ) -> DatasetDesignMutationResult | None:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            return None
        design_id = _build_design_id(draft.name)
        if any(
            row.design_id == design_id or row.name.casefold() == draft.name.casefold()
            for row in self.list_designs(dataset_id)
        ):
            raise ValueError("dataset design already exists")
        if self._durable_publication_repository is not None:
            design_row = self._durable_publication_repository.create_design(
                dataset_id=dataset_id,
                draft=draft,
            )
        else:
            source_coverage = _build_source_coverage(())
            design_row = DesignBrowseRow(
                design_id=design_id,
                dataset_id=dataset_id,
                name=draft.name,
                source_coverage=source_coverage,
                compare_readiness=_compare_readiness_for(source_coverage),
                trace_count=0,
                updated_at="2026-03-19T11:20:00Z",
            )
        design_rows = list(self._designs.get(dataset_id, ()))
        design_rows = [row for row in design_rows if row.design_id != design_row.design_id]
        design_rows.append(design_row)
        self._designs[dataset_id] = tuple(sorted(design_rows, key=lambda row: row.design_id))
        updated_dataset = replace(dataset, updated_at=design_row.updated_at)
        self._datasets[dataset_id] = updated_dataset
        return DatasetDesignMutationResult(
            dataset=updated_dataset,
            design=design_row,
        )

    def publish_simulation_result(
        self,
        *,
        task: TaskDetail,
        dataset_id: str,
        draft: SimulationResultPublicationDraft,
    ) -> SimulationResultPublicationResult | None:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            return None
        if self._durable_publication_repository is not None:
            return self._durable_publication_repository.publish_simulation_result(
                task=task,
                dataset=dataset,
                draft=draft,
            )
        design_id = draft.design_id or _build_design_id(draft.design_name)
        publication_key = build_simulation_publication_key(
            task_id=task.task_id,
            dataset_id=dataset_id,
            design_id=design_id,
        )
        trace_rows = list(self._trace_summaries.get((dataset_id, design_id), ()))
        published_trace_rows: list[TraceMetadataSummary] = []
        published_traces = build_simulation_publication_traces(
            task=task,
            dataset_family=dataset.family,
            dataset_id=dataset_id,
            design_id=design_id,
        )
        already_published = all(
            any(existing.trace_id == trace.detail.trace_id for existing in trace_rows)
            for trace in published_traces
        )
        for trace in published_traces:
            summary = trace.summary
            detail = trace.detail
            self._trace_details[(dataset_id, design_id, detail.trace_id)] = detail
            trace_rows = [row for row in trace_rows if row.trace_id != detail.trace_id]
            trace_rows.append(summary)
            published_trace_rows.append(summary)
        self._trace_summaries[(dataset_id, design_id)] = tuple(
            sorted(trace_rows, key=lambda row: row.trace_id)
        )

        design_rows = list(self._designs.get(dataset_id, ()))
        source_coverage = _build_source_coverage(self._trace_summaries[(dataset_id, design_id)])
        design_row = DesignBrowseRow(
            design_id=design_id,
            dataset_id=dataset_id,
            name=draft.design_name,
            source_coverage=source_coverage,
            compare_readiness=_compare_readiness_for(source_coverage),
            trace_count=len(self._trace_summaries[(dataset_id, design_id)]),
            updated_at="2026-03-19T11:30:00Z",
        )
        design_rows = [row for row in design_rows if row.design_id != design_id]
        design_rows.append(design_row)
        self._designs[dataset_id] = tuple(sorted(design_rows, key=lambda row: row.design_id))

        updated_dataset = replace(dataset, updated_at="2026-03-19T11:30:00Z")
        self._datasets[dataset_id] = updated_dataset
        return SimulationResultPublicationResult(
            state="already_published" if already_published else "published",
            publication_key=publication_key,
            published_at="2026-03-19T11:30:00Z",
            dataset=updated_dataset,
            design=design_row,
            traces=tuple(published_trace_rows),
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
        if self._durable_publication_repository is not None:
            return self._durable_publication_repository.publish_result_trace(
                task=task,
                basis_task=basis_task,
                dataset=dataset,
                design=design,
                draft=draft,
            )
        selections = tuple(
            ResultTraceSelection.from_trace_key(trace_key) for trace_key in draft.trace_keys
        )
        if len(selections) == 0:
            raise ValueError("result trace publication requires at least one trace_key")
        selection = selections[0]
        publication_key = build_simulation_publication_key(
            task_id=task.task_id,
            dataset_id=dataset.dataset_id,
            design_id=design.design_id,
        )
        trace_rows = list(self._trace_summaries.get((dataset.dataset_id, design.design_id), ()))
        result_summaries: list[TraceMetadataSummary] = []
        any_published = False
        for selection_index, selection in enumerate(selections):
            saved_parameter = (
                draft.parameter_name
                if len(selections) == 1
                else (
                    f"{draft.parameter_name or build_trace_parameter(selection)} "
                    f"{selection_index + 1}"
                )
            )
            detail = build_result_trace_publication_detail(
                task=task,
                basis_task=basis_task,
                dataset_id=dataset.dataset_id,
                design_id=design.design_id,
                selection=selection,
                parameter_name=saved_parameter,
            )
            summary = build_result_trace_publication_summary(
                task=task,
                detail=detail,
                selection=selection,
                parameter_name=saved_parameter,
            )
            already_published = any(row.trace_id == detail.trace_id for row in trace_rows)
            any_published = any_published or not already_published
            self._trace_details[(dataset.dataset_id, design.design_id, detail.trace_id)] = detail
            trace_rows = [row for row in trace_rows if row.trace_id != detail.trace_id]
            trace_rows.append(summary)
            result_summaries.append(summary)
        self._trace_summaries[(dataset.dataset_id, design.design_id)] = tuple(
            sorted(trace_rows, key=lambda row: row.trace_id)
        )
        design_rows = list(self._designs.get(dataset.dataset_id, ()))
        source_coverage = _build_source_coverage(
            self._trace_summaries[(dataset.dataset_id, design.design_id)]
        )
        design_row = DesignBrowseRow(
            design_id=design.design_id,
            dataset_id=dataset.dataset_id,
            name=design.name,
            source_coverage=source_coverage,
            compare_readiness=_compare_readiness_for(source_coverage),
            trace_count=len(self._trace_summaries[(dataset.dataset_id, design.design_id)]),
            updated_at="2026-03-20T00:00:00Z",
        )
        design_rows = [row for row in design_rows if row.design_id != design.design_id]
        design_rows.append(design_row)
        self._designs[dataset.dataset_id] = tuple(
            sorted(design_rows, key=lambda row: row.design_id)
        )
        updated_dataset = replace(dataset, updated_at="2026-03-20T00:00:00Z")
        self._datasets[dataset.dataset_id] = updated_dataset
        return ResultTracePublicationResult(
            state="published" if any_published else "already_published",
            publication_key=publication_key,
            published_at="2026-03-20T00:00:00Z",
            dataset=updated_dataset,
            design=design_row,
            trace_keys=draft.trace_keys,
            traces=tuple(result_summaries),
        )

    def update_dataset_profile(
        self,
        dataset_id: str,
        update: DatasetProfileUpdate,
    ) -> DatasetDetail | None:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            return None

        updated_dataset = replace(
            dataset,
            device_type=update.device_type,
            capabilities=update.capabilities,
            source=update.source,
            updated_at="2026-03-15T00:30:00Z",
        )
        self._datasets[dataset_id] = updated_dataset
        return updated_dataset

    def list_tagged_core_metrics(
        self,
        dataset_id: str,
    ) -> tuple[TaggedCoreMetricSummary, ...]:
        persisted_metrics = (
            self._durable_characterization_repository.list_tagged_core_metrics(dataset_id)
            if self._durable_characterization_repository is not None
            else ()
        )
        return _merge_tagged_core_metrics(
            self._tagged_core_metrics.get(dataset_id, ()),
            persisted_metrics,
        )

    def list_designs(
        self,
        dataset_id: str,
    ) -> tuple[DesignBrowseRow, ...]:
        in_memory_rows = self._designs.get(dataset_id, ())
        if self._durable_publication_repository is None:
            return in_memory_rows
        return _merge_design_rows(
            in_memory_rows,
            self._durable_publication_repository.list_designs(dataset_id),
        )

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
        in_memory_rows = tuple(
            _enrich_in_memory_trace_summary(
                summary,
                self._trace_details.get((dataset_id, design_id, summary.trace_id)),
            )
            for summary in self._trace_summaries.get((dataset_id, design_id), ())
        )
        if self._durable_publication_repository is None:
            return in_memory_rows
        return _merge_trace_summaries(
            in_memory_rows,
            self._durable_publication_repository.list_trace_metadata(dataset_id, design_id),
        )

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDetail | None:
        detail = self._trace_details.get((dataset_id, design_id, trace_id))
        if detail is not None or self._durable_publication_repository is None:
            if detail is None:
                return None
            summary = next(
                (
                    row
                    for row in self.list_trace_metadata(dataset_id, design_id)
                    if row.trace_id == trace_id
                ),
                None,
            )
            return _enrich_in_memory_trace_detail(detail, summary=summary)
        return self._durable_publication_repository.get_trace_detail(
            dataset_id,
            design_id,
            trace_id,
        )

    def get_trace_mutation_policy(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceMutationPolicy | None:
        key = (dataset_id, design_id, trace_id)
        if key in self._mutable_trace_keys and key in self._trace_details:
            return TraceMutationPolicy(
                allowed_actions=TraceAllowedActions(edit=True, delete=True),
                summary="Manually ingested raw trace.",
            )
        if not any(
            row.trace_id == trace_id for row in self.list_trace_metadata(dataset_id, design_id)
        ):
            return None
        return TraceMutationPolicy(
            allowed_actions=TraceAllowedActions(edit=False, delete=False),
            summary=(
                "Provenance-bearing or system-generated trace; mutate from the source workflow."
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
        edit_payload = self._trace_edit_payloads.get(
            (dataset_id, design_id, trace_id),
            _editable_numeric_payload_from_detail(detail),
        )
        return TraceEditDetail(
            trace_id=detail.trace_id,
            dataset_id=detail.dataset_id,
            design_id=detail.design_id,
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
            editable_numeric_payload=edit_payload,
            allowed_actions=policy.allowed_actions,
            mutation_policy_summary=policy.summary,
        )

    def update_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        update: TraceUpdateDraft,
    ) -> TraceUpdateResult | None:
        key = (dataset_id, design_id, trace_id)
        if key not in self._mutable_trace_keys:
            return None
        current_detail = self._trace_details.get(key)
        current_edit_payload = self._trace_edit_payloads.get(key)
        current_rows = list(self._trace_summaries.get((dataset_id, design_id), ()))
        current_summary = next((row for row in current_rows if row.trace_id == trace_id), None)
        if current_detail is None or current_summary is None or current_edit_payload is None:
            return None
        updated_at = _current_timestamp()
        updated_edit_payload = (
            update.numeric_payload if update.numeric_payload is not None else current_edit_payload
        )
        updated_preview_payload = _preview_payload_from_numeric_payload(updated_edit_payload)
        updated_axes = _axes_with_numeric_payload(current_detail.axes, updated_edit_payload)
        updated_payload_ref = current_detail.payload_ref
        axis_lengths = _numeric_payload_axis_lengths(updated_edit_payload)
        if updated_payload_ref is not None and axis_lengths is not None:
            updated_payload_ref = replace(
                updated_payload_ref,
                shape=axis_lengths,
                chunk_shape=axis_lengths,
            )
        updated_detail = replace(
            current_detail,
            axes=updated_axes,
            preview_payload=updated_preview_payload,
            payload_ref=updated_payload_ref,
        )
        updated_summary = replace(
            current_summary,
            parameter=(
                update.parameter if update.parameter is not None else current_summary.parameter
            ),
            representation=(
                update.representation
                if update.representation is not None
                else current_summary.representation
            ),
            provenance_summary=(
                update.provenance_summary
                if update.provenance_summary is not None
                else current_summary.provenance_summary
            ),
        )
        self._trace_details[key] = updated_detail
        self._trace_edit_payloads[key] = updated_edit_payload
        self._trace_summaries[(dataset_id, design_id)] = tuple(
            sorted(
                (updated_summary if row.trace_id == trace_id else row for row in current_rows),
                key=lambda row: row.trace_id,
            )
        )
        self._refresh_design_row(dataset_id, design_id, updated_at=updated_at)
        self._refresh_dataset(dataset_id, updated_at=updated_at)
        policy = self.get_trace_mutation_policy(dataset_id, design_id, trace_id)
        if policy is None:
            return None
        return TraceUpdateResult(
            trace=_build_trace_browse_row(updated_summary, policy),
        )

    def delete_traces(
        self,
        dataset_id: str,
        design_id: str,
        trace_ids: Sequence[str],
    ) -> tuple[str, ...] | None:
        keys = tuple((dataset_id, design_id, trace_id) for trace_id in trace_ids)
        if any(key not in self._mutable_trace_keys for key in keys):
            return None
        current_rows = list(self._trace_summaries.get((dataset_id, design_id), ()))
        if any(
            key not in self._trace_details
            or not any(row.trace_id == key[2] for row in current_rows)
            for key in keys
        ):
            return None
        trace_id_set = {trace_id for _, _, trace_id in keys}
        for key in keys:
            self._trace_details.pop(key, None)
            self._trace_edit_payloads.pop(key, None)
            self._mutable_trace_keys.discard(key)
        self._trace_summaries[(dataset_id, design_id)] = tuple(
            row for row in current_rows if row.trace_id not in trace_id_set
        )
        updated_at = _current_timestamp()
        self._refresh_design_row(dataset_id, design_id, updated_at=updated_at)
        self._refresh_dataset(dataset_id, updated_at=updated_at)
        return tuple(trace_ids)

    def _refresh_design_row(
        self,
        dataset_id: str,
        design_id: str,
        *,
        updated_at: str,
    ) -> None:
        design_rows = list(self._designs.get(dataset_id, ()))
        current_design = next((row for row in design_rows if row.design_id == design_id), None)
        if current_design is None:
            return
        trace_rows = self._trace_summaries.get((dataset_id, design_id), ())
        source_coverage = _build_source_coverage(trace_rows)
        refreshed_design = replace(
            current_design,
            source_coverage=source_coverage,
            compare_readiness=_compare_readiness_for(source_coverage),
            trace_count=len(trace_rows),
            updated_at=updated_at,
        )
        design_rows = [row for row in design_rows if row.design_id != design_id]
        design_rows.append(refreshed_design)
        self._designs[dataset_id] = tuple(sorted(design_rows, key=lambda row: row.design_id))

    def _refresh_dataset(
        self,
        dataset_id: str,
        *,
        updated_at: str,
    ) -> None:
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            return
        self._datasets[dataset_id] = replace(dataset, updated_at=updated_at)

    def get_simulation_result_publication_record(
        self,
        source_task_id: int,
    ) -> SimulationResultPublicationRecord | None:
        if self._durable_publication_repository is None:
            return None
        return self._durable_publication_repository.get_publication_record(source_task_id)

    def list_characterization_results(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationResultSummary, ...]:
        persisted_rows = (
            self._durable_characterization_repository.list_result_summaries(dataset_id, design_id)
            if self._durable_characterization_repository is not None
            else ()
        )
        return _merge_characterization_result_rows(
            self._characterization_results.get((dataset_id, design_id), ()),
            (
                *persisted_rows,
                *self._task_derived_characterization_result_rows(dataset_id, design_id),
            ),
        )

    def list_characterization_analysis_registry(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationAnalysisRegistryRow, ...]:
        return _merge_characterization_registry_rows(
            self._characterization_analysis_registry.get((dataset_id, design_id), ()),
            self._derive_characterization_registry_rows(dataset_id, design_id),
        )

    def list_characterization_run_history(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationRunHistoryRow, ...]:
        persisted_rows = (
            self._durable_characterization_repository.list_run_history(dataset_id, design_id)
            if self._durable_characterization_repository is not None
            else ()
        )
        return _merge_characterization_run_rows(
            self._characterization_run_history.get((dataset_id, design_id), ()),
            (*persisted_rows, *self._task_derived_characterization_run_rows(dataset_id, design_id)),
        )

    def get_characterization_result(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> CharacterizationResultDetail | None:
        cached = self._characterization_result_details.get((dataset_id, design_id, result_id))
        if cached is not None:
            return cached
        if self._durable_characterization_repository is not None:
            persisted = self._durable_characterization_repository.get_result_detail(
                dataset_id,
                design_id,
                result_id,
            )
            if persisted is not None:
                self._characterization_result_details[(dataset_id, design_id, result_id)] = (
                    persisted
                )
                return persisted
        derived = self._task_derived_characterization_result_detail(
            dataset_id,
            design_id,
            result_id,
        )
        if derived is not None:
            self._characterization_result_details[(dataset_id, design_id, result_id)] = derived
        return derived

    def get_characterization_artifact_payload(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        artifact_id: str,
        query: CharacterizationArtifactPayloadQuery,
    ) -> CharacterizationArtifactPayload | None:
        surface = self._characterization_artifact_surfaces.get((dataset_id, design_id, result_id))
        if surface is not None:
            return query_admittance_artifact_payload(
                surface=surface,
                artifact_id=artifact_id,
                query=query,
            )
        if self._durable_characterization_repository is not None:
            return self._durable_characterization_repository.get_artifact_payload(
                dataset_id,
                design_id,
                result_id,
                artifact_id,
                query,
            )
        return None

    def apply_characterization_tagging(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        request: CharacterizationTaggingRequest,
    ) -> CharacterizationTaggingResult:
        if self._durable_characterization_repository is not None:
            persisted = self._durable_characterization_repository.apply_tagging(
                dataset_id,
                design_id,
                result_id,
                artifact_id=request.artifact_id,
                source_parameter=request.source_parameter,
                designated_metric=request.designated_metric,
            )
            if persisted is not None:
                detail = self._durable_characterization_repository.get_result_detail(
                    dataset_id,
                    design_id,
                    result_id,
                )
                if detail is not None:
                    self._characterization_result_details[(dataset_id, design_id, result_id)] = (
                        detail
                    )
                return _to_characterization_tagging_result(persisted)
        detail_key = (dataset_id, design_id, result_id)
        detail = self._characterization_result_details[detail_key]
        metric_option = next(
            option
            for option in detail.identify_surface.designated_metrics
            if option.metric_key == request.designated_metric
        )
        tagged_metric = TaggedCoreMetricSummary(
            metric_id=_build_tagged_metric_id(dataset_id, request.designated_metric),
            label=metric_option.label,
            source_parameter=request.source_parameter,
            designated_metric=request.designated_metric,
            tagged_at="2026-03-15T12:10:00Z",
        )

        dataset_metrics = list(self._tagged_core_metrics.get(dataset_id, ()))
        dataset_metrics.append(tagged_metric)
        self._tagged_core_metrics[dataset_id] = tuple(dataset_metrics)

        updated_source_parameters = tuple(
            replace(
                option,
                current_designated_metric=request.designated_metric,
            )
            if option.artifact_id == request.artifact_id
            and option.source_parameter == request.source_parameter
            else option
            for option in detail.identify_surface.source_parameters
        )
        updated_applied_tags = (
            *(
                tag
                for tag in detail.identify_surface.applied_tags
                if not (
                    tag.artifact_id == request.artifact_id
                    and tag.source_parameter == request.source_parameter
                )
            ),
            CharacterizationAppliedTag(
                artifact_id=request.artifact_id,
                source_parameter=request.source_parameter,
                designated_metric=request.designated_metric,
                designated_metric_label=metric_option.label,
                tagged_at=tagged_metric.tagged_at,
            ),
        )
        self._characterization_result_details[detail_key] = replace(
            detail,
            identify_surface=replace(
                detail.identify_surface,
                source_parameters=updated_source_parameters,
                applied_tags=updated_applied_tags,
            ),
        )

        return CharacterizationTaggingResult(
            tagging_status="applied",
            dataset_id=dataset_id,
            design_id=design_id,
            result_id=result_id,
            artifact_id=request.artifact_id,
            source_parameter=request.source_parameter,
            designated_metric=request.designated_metric,
            tagged_metric=tagged_metric,
        )

    def _derive_characterization_registry_rows(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationAnalysisRegistryRow, ...]:
        trace_rows = self.list_trace_metadata(dataset_id, design_id)
        compatible_traces = tuple(
            trace
            for trace in trace_rows
            if trace.family == "y_matrix" and trace.trace_mode_group == "base"
        )
        source_kinds = {trace.source_kind for trace in compatible_traces}
        if (
            len(compatible_traces) < 2
            or "measurement" not in source_kinds
            or not ({"layout_simulation", "circuit_simulation"} & source_kinds)
        ):
            return ()
        return (
            CharacterizationAnalysisRegistryRow(
                analysis_id="admittance_extraction",
                label="Admittance Resonance Extraction",
                availability_state="recommended",
                required_config_fields=("fit_window", "residual_tolerance"),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=len(compatible_traces),
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary=(
                        f"{len(compatible_traces)} design traces are eligible for "
                        "admittance resonance extraction."
                    ),
                ),
            ),
        )

    def _task_derived_characterization_result_rows(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationResultSummary, ...]:
        return tuple(
            summary
            for summary, _, _ in self._iter_task_derived_characterization_views(
                dataset_id,
                design_id,
            )
        )

    def _task_derived_characterization_run_rows(
        self,
        dataset_id: str,
        design_id: str,
    ) -> tuple[CharacterizationRunHistoryRow, ...]:
        return tuple(
            run_row
            for _, run_row, _ in self._iter_task_derived_characterization_views(
                dataset_id,
                design_id,
            )
        )

    def _task_derived_characterization_result_detail(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> CharacterizationResultDetail | None:
        for summary, _, detail in self._iter_task_derived_characterization_views(
            dataset_id,
            design_id,
        ):
            if summary.result_id == result_id:
                return detail
        return None

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
        if self._task_repository is None:
            return ()
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

    def list_circuit_definitions(self) -> list[CircuitDefinitionRecord]:
        return list(self._circuit_definitions.values())

    def get_circuit_definition(
        self,
        definition_id: DefinitionId,
    ) -> CircuitDefinitionRecord | None:
        return self._circuit_definitions.get(definition_id)

    def create_circuit_definition(
        self,
        *,
        workspace_id: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: CircuitDefinitionDraft,
    ) -> CircuitDefinitionRecord:
        definition_id = _build_definition_id()
        created_at = _timestamp_for_definition_sequence(self._next_definition_sequence)
        definition = _build_circuit_definition_record(
            definition_id=definition_id,
            workspace_id=workspace_id,
            visibility_scope=draft.visibility_scope,
            owner_user_id=owner_user_id,
            owner_display_name=owner_display_name,
            name=draft.name,
            created_at=created_at,
            updated_at=created_at,
            concurrency_token=f"etag_{definition_id}_1",
            source_text=draft.source_text,
        )
        self._circuit_definitions[definition.definition_id] = definition
        self._persist_circuit_definition(definition)
        self._next_definition_sequence += 1
        return definition

    def update_circuit_definition(
        self,
        definition_id: DefinitionId,
        update: CircuitDefinitionUpdate,
    ) -> CircuitDefinitionRecord | None:
        definition = self._circuit_definitions.get(definition_id)
        if definition is None:
            return None
        if (
            update.concurrency_token is not None
            and update.concurrency_token != definition.concurrency_token
        ):
            return None
        inspection = _inspect_circuit_definition(update.source_text)

        updated_definition = replace(
            definition,
            name=update.name or definition.name,
            updated_at=_advance_definition_timestamp(definition.updated_at, minutes=1),
            concurrency_token=_next_concurrency_token(definition.concurrency_token),
            source_text=update.source_text,
            source_hash=_source_hash(update.source_text),
            normalized_output=inspection.normalized_output,
            validation_notices=inspection.validation_notices,
            validation_summary=inspection.validation_summary,
        )
        self._circuit_definitions[definition_id] = updated_definition
        self._persist_circuit_definition(updated_definition)
        return updated_definition

    def publish_circuit_definition(
        self,
        definition_id: DefinitionId,
    ) -> CircuitDefinitionRecord | None:
        definition = self._circuit_definitions.get(definition_id)
        if definition is None:
            return None
        published_definition = replace(
            definition,
            visibility_scope="workspace",
            updated_at=_advance_definition_timestamp(definition.updated_at, minutes=2),
            concurrency_token=_next_concurrency_token(definition.concurrency_token),
        )
        self._circuit_definitions[definition_id] = published_definition
        self._persist_circuit_definition(published_definition)
        return published_definition

    def clone_circuit_definition(
        self,
        *,
        source_definition_id: DefinitionId,
        workspace_id: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: CircuitDefinitionCloneDraft,
    ) -> CircuitDefinitionRecord | None:
        source_definition = self._circuit_definitions.get(source_definition_id)
        if source_definition is None:
            return None
        definition_id = _build_definition_id()
        created_at = _timestamp_for_definition_sequence(self._next_definition_sequence)
        cloned_definition = _build_circuit_definition_record(
            definition_id=definition_id,
            workspace_id=workspace_id,
            visibility_scope="local" if workspace_id == "local-space" else "private",
            owner_user_id=owner_user_id,
            owner_display_name=owner_display_name,
            name=draft.name or f"{source_definition.name} Copy",
            created_at=created_at,
            updated_at=created_at,
            concurrency_token=f"etag_{definition_id}_1",
            source_text=source_definition.source_text,
            lineage_parent_id=source_definition.definition_id,
        )
        self._circuit_definitions[cloned_definition.definition_id] = cloned_definition
        self._persist_circuit_definition(cloned_definition)
        self._next_definition_sequence += 1
        return cloned_definition

    def delete_circuit_definition(self, definition_id: DefinitionId) -> bool:
        existing = self._circuit_definitions.pop(definition_id, None)
        if existing is not None:
            deleted_definition = replace(
                existing,
                lifecycle_state="deleted",
                updated_at=_advance_definition_timestamp(existing.updated_at, minutes=3),
                concurrency_token=_next_concurrency_token(existing.concurrency_token),
            )
            self._persist_circuit_definition(deleted_definition)
        return existing is not None

    def _persist_circuit_definition(self, definition: CircuitDefinitionRecord) -> None:
        if self._durable_definition_repository is None:
            return
        self._durable_definition_repository.save_circuit_definition(definition)


def _build_circuit_definition_record(
    definition_id: DefinitionId,
    workspace_id: str,
    visibility_scope: str,
    owner_user_id: str,
    owner_display_name: str,
    name: str,
    created_at: str,
    updated_at: str,
    concurrency_token: str,
    source_text: str,
    *,
    lineage_parent_id: DefinitionId | None = None,
) -> CircuitDefinitionRecord:
    inspection = _inspect_circuit_definition(source_text)
    return CircuitDefinitionRecord(
        definition_id=definition_id,
        workspace_id=workspace_id,
        visibility_scope=visibility_scope,
        lifecycle_state="active",
        owner_user_id=owner_user_id,
        owner_display_name=owner_display_name,
        name=name,
        created_at=created_at,
        updated_at=updated_at,
        concurrency_token=concurrency_token,
        source_hash=_source_hash(source_text),
        source_text=source_text,
        normalized_output=inspection.normalized_output,
        validation_notices=inspection.validation_notices,
        validation_summary=inspection.validation_summary,
        preview_artifacts=(
            "expanded-netlist.json",
            "validation-summary.json",
            "schemdraw-preview.svg",
        ),
        lineage_parent_id=lineage_parent_id,
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


def _current_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    )


def _enrich_in_memory_trace_summary(
    summary: TraceMetadataSummary,
    detail: TraceDetail | None,
) -> TraceMetadataSummary:
    if detail is None:
        return summary
    structure = build_trace_structure_summary(
        dataset_id=summary.dataset_id,
        design_id=summary.design_id,
        family=summary.family,
        parameter=summary.parameter,
        representation=summary.representation,
        trace_mode_group=summary.trace_mode_group,
        source_kind=summary.source_kind,
        stage_kind=summary.stage_kind,
        axes=tuple(detail.axes),
    )
    return replace(
        summary,
        ndim=structure.ndim,
        shape=structure.shape,
        axes_summary=structure.axes_summary,
        axis_signature=structure.axis_signature,
        available_sweep_axes=structure.available_sweep_axes,
        collection_projection=structure.collection_projection,
    )


def _enrich_in_memory_trace_detail(
    detail: TraceDetail,
    *,
    summary: TraceMetadataSummary | None,
) -> TraceDetail:
    structure = build_trace_structure_summary(
        dataset_id=detail.dataset_id,
        design_id=detail.design_id,
        family=summary.family if summary is not None else detail.family,
        parameter=summary.parameter if summary is not None else detail.parameter,
        representation=(summary.representation if summary is not None else detail.representation),
        trace_mode_group=(
            summary.trace_mode_group if summary is not None else detail.trace_mode_group
        ),
        source_kind=summary.source_kind if summary is not None else detail.source_kind,
        stage_kind=summary.stage_kind if summary is not None else detail.stage_kind,
        axes=tuple(detail.axes),
    )
    return replace(
        detail,
        family=summary.family if summary is not None else detail.family,
        parameter=summary.parameter if summary is not None else detail.parameter,
        representation=(summary.representation if summary is not None else detail.representation),
        trace_mode_group=(
            summary.trace_mode_group if summary is not None else detail.trace_mode_group
        ),
        source_kind=summary.source_kind if summary is not None else detail.source_kind,
        stage_kind=summary.stage_kind if summary is not None else detail.stage_kind,
        ndim=structure.ndim,
        shape=structure.shape,
        axes_summary=structure.axes_summary,
        axis_signature=structure.axis_signature,
        available_sweep_axes=structure.available_sweep_axes,
        collection_projection=structure.collection_projection,
    )


def _editable_numeric_payload_from_detail(detail: TraceDetail) -> dict[str, object]:
    return _editable_numeric_payload_from_preview_payload(detail.axes, detail.preview_payload)


def _editable_numeric_payload_from_preview_payload(
    axes: tuple[TraceAxis, ...],
    preview_payload: dict[str, object],
) -> dict[str, object]:
    axis = axes[0] if len(axes) > 0 else TraceAxis(name="axis", unit="", length=0)
    points = preview_payload.get("points")
    if isinstance(points, list):
        rows = []
        for point in points:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                rows.append({axis.name: point[0], "value": point[1]})
        return {
            "kind": "series_table",
            "columns": [
                {"key": axis.name, "label": axis.name.title(), "unit": axis.unit, "role": "axis"},
                {"key": "value", "label": "Value", "unit": None, "role": "value"},
            ],
            "rows": rows,
        }
    return {
        "kind": "series_table",
        "columns": [
            {"key": axis.name, "label": axis.name.title(), "unit": axis.unit, "role": "axis"},
            {"key": "value", "label": "Value", "unit": None, "role": "value"},
        ],
        "rows": [],
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


def _build_source_coverage(
    traces: tuple[TraceMetadataSummary, ...],
) -> dict[str, int]:
    coverage = {
        "measurement": 0,
        "layout_simulation": 0,
        "circuit_simulation": 0,
    }
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
    base_rows: tuple[DesignBrowseRow, ...],
    durable_rows: tuple[DesignBrowseRow, ...],
) -> tuple[DesignBrowseRow, ...]:
    merged: dict[str, DesignBrowseRow] = {row.design_id: row for row in base_rows}
    for durable_row in durable_rows:
        existing = merged.get(durable_row.design_id)
        if existing is None:
            merged[durable_row.design_id] = durable_row
            continue
        combined_coverage = {
            key: existing.source_coverage.get(key, 0) + durable_row.source_coverage.get(key, 0)
            for key in {
                *existing.source_coverage.keys(),
                *durable_row.source_coverage.keys(),
            }
        }
        merged[durable_row.design_id] = replace(
            durable_row,
            name=durable_row.name or existing.name,
            source_coverage=combined_coverage,
            compare_readiness=_compare_readiness_for(combined_coverage),
            trace_count=existing.trace_count + durable_row.trace_count,
            updated_at=max(existing.updated_at, durable_row.updated_at),
        )
    return tuple(sorted(merged.values(), key=lambda row: row.design_id))


def _merge_trace_summaries(
    base_rows: tuple[TraceMetadataSummary, ...],
    durable_rows: tuple[TraceMetadataSummary, ...],
) -> tuple[TraceMetadataSummary, ...]:
    merged = {row.trace_id: row for row in base_rows}
    for durable_row in durable_rows:
        merged[durable_row.trace_id] = durable_row
    return tuple(sorted(merged.values(), key=lambda row: row.trace_id))


def _merge_characterization_registry_rows(
    base_rows: tuple[CharacterizationAnalysisRegistryRow, ...],
    derived_rows: tuple[CharacterizationAnalysisRegistryRow, ...],
) -> tuple[CharacterizationAnalysisRegistryRow, ...]:
    merged = {row.analysis_id: row for row in base_rows}
    for row in derived_rows:
        merged.setdefault(row.analysis_id, row)
    return tuple(merged.values())


def _merge_characterization_result_rows(
    base_rows: tuple[CharacterizationResultSummary, ...],
    derived_rows: tuple[CharacterizationResultSummary, ...],
) -> tuple[CharacterizationResultSummary, ...]:
    merged_rows: list[CharacterizationResultSummary] = []
    seen_result_ids: set[str] = set()
    for row in derived_rows:
        if row.result_id in seen_result_ids:
            continue
        merged_rows.append(row)
        seen_result_ids.add(row.result_id)
    for row in base_rows:
        if row.result_id in seen_result_ids:
            continue
        merged_rows.append(row)
        seen_result_ids.add(row.result_id)
    return tuple(merged_rows)


def _merge_characterization_run_rows(
    base_rows: tuple[CharacterizationRunHistoryRow, ...],
    derived_rows: tuple[CharacterizationRunHistoryRow, ...],
) -> tuple[CharacterizationRunHistoryRow, ...]:
    merged_rows: list[CharacterizationRunHistoryRow] = []
    seen_run_ids: set[str] = set()
    for row in derived_rows:
        if row.run_id in seen_run_ids:
            continue
        merged_rows.append(row)
        seen_run_ids.add(row.run_id)
    for row in base_rows:
        if row.run_id in seen_run_ids:
            continue
        merged_rows.append(row)
        seen_run_ids.add(row.run_id)
    return tuple(merged_rows)


def _merge_tagged_core_metrics(
    base_rows: tuple[TaggedCoreMetricSummary, ...],
    persisted_rows: tuple[TaggedCoreMetricSummary, ...],
) -> tuple[TaggedCoreMetricSummary, ...]:
    merged_rows: list[TaggedCoreMetricSummary] = []
    seen_pairs: set[tuple[str, str]] = set()
    for row in persisted_rows:
        pair = (row.source_parameter, row.designated_metric)
        if pair in seen_pairs:
            continue
        merged_rows.append(row)
        seen_pairs.add(pair)
    for row in base_rows:
        pair = (row.source_parameter, row.designated_metric)
        if pair in seen_pairs:
            continue
        merged_rows.append(row)
        seen_pairs.add(pair)
    return tuple(merged_rows)


def _parse_characterization_result_summary(
    payload: object,
) -> CharacterizationResultSummary | None:
    body = _parse_json_mapping(payload)
    if body is None:
        return None
    return CharacterizationResultSummary(
        result_id=str(body["result_id"]),
        dataset_id=str(body["dataset_id"]),
        design_id=str(body["design_id"]),
        analysis_id=str(body["analysis_id"]),
        title=str(body["title"]),
        status=str(body["status"]),
        freshness_summary=str(body["freshness_summary"]),
        provenance_summary=str(body["provenance_summary"]),
        trace_count=int(body["trace_count"]),
        artifact_count=int(body["artifact_count"]),
        updated_at=str(body["updated_at"]),
    )


def _parse_characterization_run_history_row(
    payload: object,
) -> CharacterizationRunHistoryRow | None:
    body = _parse_json_mapping(payload)
    if body is None:
        return None
    result_id = body.get("result_id")
    return CharacterizationRunHistoryRow(
        run_id=str(body["run_id"]),
        dataset_id=str(body["dataset_id"]),
        design_id=str(body["design_id"]),
        analysis_id=str(body["analysis_id"]),
        label=str(body["label"]),
        status=str(body["status"]),
        scope=str(body["scope"]),
        trace_count=int(body["trace_count"]),
        sources_summary=str(body["sources_summary"]),
        provenance_summary=str(body["provenance_summary"]),
        updated_at=str(body["updated_at"]),
        result_id=str(result_id) if isinstance(result_id, str) else None,
    )


def _parse_characterization_result_detail(
    payload: object,
) -> CharacterizationResultDetail | None:
    body = _parse_json_mapping(payload)
    if body is None:
        return None
    diagnostics = body.get("diagnostics", ())
    artifact_refs = body.get("artifact_refs", ())
    identify_surface = body.get("identify_surface", {})
    source_parameters = identify_surface.get("source_parameters", [])
    designated_metrics = identify_surface.get("designated_metrics", [])
    applied_tags = identify_surface.get("applied_tags", [])
    input_trace_ids = body.get("input_trace_ids", ())
    return CharacterizationResultDetail(
        result_id=str(body["result_id"]),
        dataset_id=str(body["dataset_id"]),
        design_id=str(body["design_id"]),
        analysis_id=str(body["analysis_id"]),
        title=str(body["title"]),
        status=str(body["status"]),
        freshness_summary=str(body["freshness_summary"]),
        provenance_summary=str(body["provenance_summary"]),
        trace_count=int(body["trace_count"]),
        updated_at=str(body["updated_at"]),
        input_trace_ids=tuple(
            str(trace_id) for trace_id in input_trace_ids if isinstance(trace_id, str)
        ),
        payload=dict(body.get("payload", {})),
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
    )


def _parse_json_mapping(payload: object) -> dict[str, object] | None:
    if isinstance(payload, dict):
        return payload
    if not isinstance(payload, str):
        return None
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _slugify(value: str) -> str:
    return "-".join(
        token
        for token in "".join(
            character.lower() if character.isalnum() else "-" for character in value.strip()
        ).split("-")
        if token
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


class _CircuitInspectionResult:
    def __init__(
        self,
        *,
        normalized_output: str,
        validation_notices: tuple[ValidationNotice, ...],
        validation_summary: ValidationSummary,
    ) -> None:
        self.normalized_output = normalized_output
        self.validation_notices = validation_notices
        self.validation_summary = validation_summary


def _load_circuit_domain() -> tuple[Any, Any, Any, Any, type[Exception]]:
    workspace_src = Path(__file__).resolve().parents[4] / "src"
    if str(workspace_src) not in sys.path:
        sys.path.insert(0, str(workspace_src))

    from core.simulation.domain.circuit import (
        expand_circuit_definition,
        format_circuit_definition,
        format_expanded_circuit_definition,
        parse_circuit_definition_source,
    )
    from core.simulation.domain.validators import CircuitValidationError

    return (
        parse_circuit_definition_source,
        expand_circuit_definition,
        format_circuit_definition,
        format_expanded_circuit_definition,
        CircuitValidationError,
    )


def _inspect_circuit_definition(source_text: str) -> _CircuitInspectionResult:
    (
        parse_circuit_definition_source,
        expand_circuit_definition,
        format_circuit_definition,
        format_expanded_circuit_definition,
        validation_error_type,
    ) = _load_circuit_domain()
    try:
        parsed = parse_circuit_definition_source(source_text)
        expanded = expand_circuit_definition(parsed)
    except validation_error_type as exc:
        raise ValueError(str(exc)) from exc
    except (TypeError, ValueError) as exc:
        raise ValueError(str(exc)) from exc

    notices = (
        ValidationNotice(
            severity="info",
            code="definition_parsed",
            message="Circuit definition source was parsed successfully.",
            source="circuit_netlist",
            blocking=False,
        ),
        ValidationNotice(
            severity="info",
            code="definition_expanded",
            message=(
                f"Expanded netlist contains {len(expanded.components)} components and "
                f"{len(expanded.topology)} topology rows."
            ),
            source="circuit_netlist",
            blocking=False,
        ),
        ValidationNotice(
            severity="info",
            code="layout_profile_inferred",
            message=f"Preview layout profile: {parsed.effective_layout_profile}.",
            source="circuit_netlist",
            blocking=False,
        ),
    )
    return _CircuitInspectionResult(
        normalized_output=_normalized_output(
            parsed,
            format_circuit_definition=format_circuit_definition,
            format_expanded_circuit_definition=format_expanded_circuit_definition,
        ),
        validation_notices=notices,
        validation_summary=ValidationSummary(
            status="valid",
            notice_count=len(notices),
            warning_count=0,
            blocking_notice_count=0,
        ),
    )


def _normalized_output(
    parsed: Any,
    *,
    format_circuit_definition: Any,
    format_expanded_circuit_definition: Any,
) -> str:
    return (
        "{\n"
        f'  "source": {format_circuit_definition(parsed)!r},\n'
        f'  "expanded": {format_expanded_circuit_definition(parsed)!r}\n'
        "}"
    )


def _source_hash(source_text: str) -> str:
    return sha256(source_text.encode("utf-8")).hexdigest()[:12]


def _next_concurrency_token(current_token: str) -> str:
    prefix, _, suffix = current_token.rpartition("_")
    if suffix.isdigit():
        return f"{prefix}_{int(suffix) + 1}"
    return f"{current_token}_next"


def _build_definition_id() -> DefinitionId:
    return str(uuid4())


def _timestamp_for_definition_sequence(sequence: int) -> str:
    minute_offset = max(sequence - 1, 0)
    timestamp = datetime(2026, 3, 18, 9, 0, tzinfo=UTC) + timedelta(minutes=minute_offset)
    return timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def _advance_definition_timestamp(current_timestamp: str, *, minutes: int) -> str:
    parsed = datetime.fromisoformat(current_timestamp.replace("Z", "+00:00"))
    return (parsed + timedelta(minutes=minutes)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_datasets() -> tuple[DatasetDetail, ...]:
    return (
        DatasetDetail(
            dataset_id="local-dataset-001",
            name="Local Space Flux Sandbox",
            family="Fluxonium",
            owner="Local Space",
            owner_user_id="local-operator",
            workspace_id="local-space",
            visibility_scope="local",
            lifecycle_state="active",
            updated_at="2026-03-17T08:30:00Z",
            device_type="Fluxonium",
            capabilities=("characterization", "simulation_review", "local_runtime"),
            source="manual",
            status="Ready",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=False,
                archive=True,
            ),
        ),
        DatasetDetail(
            dataset_id="fluxonium-2025-031",
            name="Fluxonium sweep 031",
            family="Fluxonium",
            owner="Device Lab",
            owner_user_id="researcher-01",
            workspace_id="ws-device-lab",
            visibility_scope="private",
            lifecycle_state="active",
            updated_at="2026-03-14T10:20:00Z",
            device_type="Fluxonium",
            capabilities=("characterization", "simulation_review"),
            source="inferred",
            status="Ready",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=True,
                archive=True,
            ),
        ),
        DatasetDetail(
            dataset_id="resonator-chip-002",
            name="Readout resonator validation 002",
            family="Resonator",
            owner="Device Lab",
            owner_user_id="researcher-02",
            workspace_id="ws-device-lab",
            visibility_scope="workspace",
            lifecycle_state="active",
            updated_at="2026-03-13T16:45:00Z",
            device_type="Resonator",
            capabilities=("measurement_review",),
            source="manual",
            status="Queued",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=False,
                archive=True,
            ),
        ),
        DatasetDetail(
            dataset_id="transmon-coupler-014",
            name="Coupler detuning 014",
            family="Transmon",
            owner="Modeling",
            owner_user_id="modeler-07",
            workspace_id="ws-modeling",
            visibility_scope="workspace",
            lifecycle_state="active",
            updated_at="2026-03-14T09:10:00Z",
            device_type="Transmon",
            capabilities=("cross-resonance",),
            source="imported",
            status="Review",
            allowed_actions=DatasetAllowedActions(
                select=True,
                update_profile=True,
                publish=False,
                archive=False,
            ),
        ),
    )


def _seed_tagged_core_metrics() -> dict[str, tuple[TaggedCoreMetricSummary, ...]]:
    return {
        "local-dataset-001": (
            TaggedCoreMetricSummary(
                metric_id="metric-local-f01",
                label="Local Transition",
                source_parameter="Im(Y11)",
                designated_metric="f01",
                tagged_at="2026-03-17T08:40:00Z",
            ),
        ),
        "fluxonium-2025-031": (
            TaggedCoreMetricSummary(
                metric_id="metric-fluxonium-lowest-observed-frequency-ghz",
                label="Lowest Observed Frequency",
                source_parameter="lowest_observed_frequency_ghz",
                designated_metric="lowest_observed_frequency_ghz",
                tagged_at="2026-03-14T11:05:00Z",
            ),
            TaggedCoreMetricSummary(
                metric_id="metric-fluxonium-residual-rms-max",
                label="Max Residual RMS",
                source_parameter="residual_rms_max",
                designated_metric="residual_rms_max",
                tagged_at="2026-03-14T11:08:00Z",
            ),
        ),
        "resonator-chip-002": (),
        "transmon-coupler-014": (
            TaggedCoreMetricSummary(
                metric_id="metric-coupler-chi",
                label="Coupler Shift",
                source_parameter="chi_fit",
                designated_metric="chi",
                tagged_at="2026-03-14T09:30:00Z",
            ),
        ),
    }


def _seed_designs() -> dict[str, tuple[DesignBrowseRow, ...]]:
    return {
        "local-dataset-001": (
            DesignBrowseRow(
                design_id="design_local_flux_playground",
                dataset_id="local-dataset-001",
                name="Local Flux Playground",
                source_coverage={"measurement": 1, "circuit_simulation": 1},
                compare_readiness="ready",
                trace_count=2,
                updated_at="2026-03-17T08:35:00Z",
            ),
        ),
        "fluxonium-2025-031": (
            DesignBrowseRow(
                design_id="design_flux_scan_a",
                dataset_id="fluxonium-2025-031",
                name="Flux Scan A",
                source_coverage={"measurement": 2, "layout_simulation": 1},
                compare_readiness="ready",
                trace_count=3,
                updated_at="2026-03-14T10:24:00Z",
            ),
            DesignBrowseRow(
                design_id="design_flux_scan_b",
                dataset_id="fluxonium-2025-031",
                name="Flux Scan B",
                source_coverage={"measurement": 1},
                compare_readiness="inspect_only",
                trace_count=1,
                updated_at="2026-03-14T09:50:00Z",
            ),
        ),
        "resonator-chip-002": (
            DesignBrowseRow(
                design_id="design_resonator_temp",
                dataset_id="resonator-chip-002",
                name="Temperature Sweep",
                source_coverage={"measurement": 1},
                compare_readiness="blocked",
                trace_count=1,
                updated_at="2026-03-13T16:00:00Z",
            ),
        ),
        "transmon-coupler-014": (
            DesignBrowseRow(
                design_id="design_coupler_detuning",
                dataset_id="transmon-coupler-014",
                name="Coupler Detuning",
                source_coverage={"circuit_simulation": 1, "measurement": 1},
                compare_readiness="ready",
                trace_count=2,
                updated_at="2026-03-14T09:20:00Z",
            ),
        ),
    }


def _seed_trace_summaries() -> dict[tuple[str, str], tuple[TraceMetadataSummary, ...]]:
    return {
        (
            "local-dataset-001",
            "design_local_flux_playground",
        ): (
            TraceMetadataSummary(
                trace_id="trace_local_flux_measurement",
                dataset_id="local-dataset-001",
                design_id="design_local_flux_playground",
                family="y_matrix",
                parameter="Y11",
                representation="imaginary",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="postprocess",
                provenance_summary="Local Measurement · Post-Processed · batch #1",
            ),
            TraceMetadataSummary(
                trace_id="trace_local_flux_preview",
                dataset_id="local-dataset-001",
                design_id="design_local_flux_playground",
                family="y_matrix",
                parameter="Y11",
                representation="imaginary",
                trace_mode_group="base",
                source_kind="circuit_simulation",
                stage_kind="raw",
                provenance_summary="Local Runtime · Raw · preview batch",
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
        ): (
            TraceMetadataSummary(
                trace_id="trace_flux_a_measurement",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                family="y_matrix",
                parameter="Y11",
                representation="imaginary",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="postprocess",
                provenance_summary="Measurement · Post-Processed · batch #4",
            ),
            TraceMetadataSummary(
                trace_id="trace_flux_a_layout",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                family="y_matrix",
                parameter="Y11",
                representation="imaginary",
                trace_mode_group="base",
                source_kind="layout_simulation",
                stage_kind="raw",
                provenance_summary="Layout Simulation · Raw · batch #2",
            ),
            TraceMetadataSummary(
                trace_id="trace_flux_a_phase",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                family="y_matrix",
                parameter="Y11",
                representation="phase",
                trace_mode_group="sideband",
                source_kind="measurement",
                stage_kind="postprocess",
                provenance_summary="Measurement · Phase Projection · batch #4",
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
        ): (
            TraceMetadataSummary(
                trace_id="trace_flux_b_measurement",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_b",
                family="s_matrix",
                parameter="S21",
                representation="magnitude",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="raw",
                provenance_summary="Measurement · Raw · batch #7",
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
        ): (
            TraceMetadataSummary(
                trace_id="trace_res_temp_measurement",
                dataset_id="resonator-chip-002",
                design_id="design_resonator_temp",
                family="s_matrix",
                parameter="S21",
                representation="magnitude",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="raw",
                provenance_summary="Measurement · Raw · batch #12",
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
        ): (
            TraceMetadataSummary(
                trace_id="trace_coupler_measurement",
                dataset_id="transmon-coupler-014",
                design_id="design_coupler_detuning",
                family="z_matrix",
                parameter="Z21",
                representation="real",
                trace_mode_group="base",
                source_kind="measurement",
                stage_kind="postprocess",
                provenance_summary="Measurement · Fit Input · batch #12",
            ),
            TraceMetadataSummary(
                trace_id="trace_coupler_simulation",
                dataset_id="transmon-coupler-014",
                design_id="design_coupler_detuning",
                family="z_matrix",
                parameter="Z21",
                representation="real",
                trace_mode_group="base",
                source_kind="circuit_simulation",
                stage_kind="raw",
                provenance_summary="Circuit Simulation · Raw · batch #5",
            ),
        ),
    }


def _seed_trace_details() -> dict[tuple[str, str, str], TraceDetail]:
    return {
        (
            "local-dataset-001",
            "design_local_flux_playground",
            "trace_local_flux_measurement",
        ): TraceDetail(
            trace_id="trace_local_flux_measurement",
            dataset_id="local-dataset-001",
            design_id="design_local_flux_playground",
            axes=(TraceAxis(name="frequency", unit="GHz", length=51),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": [
                    "Measurement",
                    "PTC",
                    "Coordinate Transformation",
                    "Kron Reduction",
                ],
                "history_summary": (
                    "Measurement -> PTC -> Coordinate Transformation -> Kron Reduction"
                ),
                "points": _build_interpolated_series_points(
                    anchors=((4.82, 0.13), (5.01, 0.16), (5.19, 0.12)),
                    length=51,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/local-dataset-001/designs/design_local_flux_playground/measurement.zarr",
                store_uri="trace_store/local/local-dataset-001/design_local_flux_playground/measurement.zarr",
                group_path="/traces/trace_local_flux_measurement",
                array_path="values",
                dtype="float64",
                shape=(51,),
                chunk_shape=(51,),
            ),
            result_handles=(),
        ),
        (
            "local-dataset-001",
            "design_local_flux_playground",
            "trace_local_flux_preview",
        ): TraceDetail(
            trace_id="trace_local_flux_preview",
            dataset_id="local-dataset-001",
            design_id="design_local_flux_playground",
            axes=(TraceAxis(name="frequency", unit="GHz", length=51),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": ["Raw"],
                "history_summary": "Raw",
                "points": _build_interpolated_series_points(
                    anchors=((4.8, 0.11), (5.0, 0.13), (5.2, 0.1)),
                    length=51,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/local-dataset-001/designs/design_local_flux_playground/preview.zarr",
                store_uri="trace_store/local/local-dataset-001/design_local_flux_playground/preview.zarr",
                group_path="/traces/trace_local_flux_preview",
                array_path="values",
                dtype="float64",
                shape=(51,),
                chunk_shape=(51,),
            ),
            result_handles=(),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "trace_flux_a_measurement",
        ): TraceDetail(
            trace_id="trace_flux_a_measurement",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            axes=(TraceAxis(name="frequency", unit="GHz", length=401),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": ["Measurement", "Post-Processed"],
                "history_summary": "Measurement -> Post-Processed",
                "points": _build_interpolated_series_points(
                    anchors=((5.71, 0.013), (5.78, 0.018), (5.84, 0.015)),
                    length=401,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_4.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_4.zarr",
                group_path="/traces/trace_flux_a_measurement",
                array_path="values",
                dtype="float64",
                shape=(401,),
                chunk_shape=(401,),
            ),
            result_handles=(
                build_result_handle_ref(
                    handle_id="result:fluxonium-2025-031:fit-summary",
                    kind="fit_summary",
                    status="materialized",
                    label="Fluxonium fit summary",
                    metadata_record=build_metadata_record_ref(
                        "result_handle",
                        "result_handle:501",
                        version=2,
                    ),
                    payload_backend="json_artifact",
                    payload_format="json",
                    payload_role="report_artifact",
                    payload_locator="artifacts/fit-summary.json",
                    provenance_task_id=303,
                    provenance=build_result_provenance_ref(
                        source_dataset_id="fluxonium-2025-031",
                        source_task_id=303,
                        trace_batch_record=build_metadata_record_ref(
                            "trace_batch",
                            "trace_batch:88",
                            version=1,
                        ),
                    ),
                ),
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "trace_flux_a_layout",
        ): TraceDetail(
            trace_id="trace_flux_a_layout",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            axes=(TraceAxis(name="frequency", unit="GHz", length=401),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": ["Layout Simulation", "Raw"],
                "history_summary": "Layout Simulation -> Raw",
                "points": _build_interpolated_series_points(
                    anchors=((5.71, 0.011), (5.78, 0.017), (5.84, 0.014)),
                    length=401,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_2.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_2.zarr",
                group_path="/traces/trace_flux_a_layout",
                array_path="values",
                dtype="float64",
                shape=(401,),
                chunk_shape=(401,),
            ),
            result_handles=(),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "trace_flux_a_phase",
        ): TraceDetail(
            trace_id="trace_flux_a_phase",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            axes=(TraceAxis(name="frequency", unit="GHz", length=401),),
            preview_payload={
                "kind": "series",
                "parameter": "Y11",
                "default_parameter": "Y11",
                "history_steps": ["Measurement", "Phase Projection"],
                "history_summary": "Measurement -> Phase Projection",
                "points": _build_interpolated_series_points(
                    anchors=((5.71, -0.16), (5.78, -0.02), (5.84, 0.14)),
                    length=401,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_4_phase.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/designs/design_flux_scan_a/batches/batch_4_phase.zarr",
                group_path="/traces/trace_flux_a_phase",
                array_path="values",
                dtype="float64",
                shape=(401,),
                chunk_shape=(401,),
            ),
            result_handles=(),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
            "trace_flux_b_measurement",
        ): TraceDetail(
            trace_id="trace_flux_b_measurement",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_b",
            axes=(TraceAxis(name="frequency", unit="GHz", length=201),),
            preview_payload={
                "kind": "series",
                "parameter": "S21",
                "default_parameter": "S21",
                "history_steps": ["Measurement", "Raw"],
                "history_summary": "Measurement -> Raw",
                "points": _build_interpolated_series_points(
                    anchors=((6.1, 0.42), (6.18, 0.51), (6.24, 0.47)),
                    length=201,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/fluxonium-2025-031/designs/design_flux_scan_b/batches/batch_7.zarr",
                store_uri="trace_store/datasets/fluxonium-2025-031/designs/design_flux_scan_b/batches/batch_7.zarr",
                group_path="/traces/trace_flux_b_measurement",
                array_path="values",
                dtype="float64",
                shape=(201,),
                chunk_shape=(201,),
            ),
            result_handles=(),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
            "trace_res_temp_measurement",
        ): TraceDetail(
            trace_id="trace_res_temp_measurement",
            dataset_id="resonator-chip-002",
            design_id="design_resonator_temp",
            axes=(TraceAxis(name="temperature", unit="mK", length=31),),
            preview_payload={
                "kind": "series",
                "points": _build_interpolated_series_points(
                    anchors=((10, 0.91), (20, 0.88), (30, 0.81)),
                    length=31,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/resonator-chip-002/designs/design_resonator_temp/batches/batch_12.zarr",
                store_uri="trace_store/datasets/resonator-chip-002/designs/design_resonator_temp/batches/batch_12.zarr",
                group_path="/traces/trace_res_temp_measurement",
                array_path="values",
                dtype="float64",
                shape=(31,),
                chunk_shape=(31,),
            ),
            result_handles=(),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
            "trace_coupler_measurement",
        ): TraceDetail(
            trace_id="trace_coupler_measurement",
            dataset_id="transmon-coupler-014",
            design_id="design_coupler_detuning",
            axes=(TraceAxis(name="bias", unit="V", length=76),),
            preview_payload={
                "kind": "series",
                "points": _build_interpolated_series_points(
                    anchors=((-0.28, 11.2), (-0.265, 10.8), (-0.25, 10.4)),
                    length=76,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/transmon-coupler-014/designs/design_coupler_detuning/batches/batch_12.zarr",
                store_uri="trace_store/datasets/transmon-coupler-014/designs/design_coupler_detuning/batches/batch_12.zarr",
                group_path="/traces/trace_coupler_measurement",
                array_path="values",
                dtype="float64",
                shape=(76,),
                chunk_shape=(76,),
            ),
            result_handles=(
                build_result_handle_ref(
                    handle_id="result:transmon-coupler-014:characterization-report",
                    kind="characterization_report",
                    status="materialized",
                    label="Coupler characterization report",
                    metadata_record=build_metadata_record_ref(
                        "result_handle",
                        "result_handle:612",
                        version=3,
                    ),
                    payload_backend="markdown_artifact",
                    payload_format="markdown",
                    payload_role="report_artifact",
                    payload_locator="artifacts/fit-report.md",
                    provenance_task_id=305,
                    provenance=build_result_provenance_ref(
                        source_dataset_id="transmon-coupler-014",
                        source_task_id=305,
                        analysis_run_record=build_metadata_record_ref(
                            "analysis_run",
                            "analysis_run:12",
                            version=4,
                        ),
                    ),
                ),
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
            "trace_coupler_simulation",
        ): TraceDetail(
            trace_id="trace_coupler_simulation",
            dataset_id="transmon-coupler-014",
            design_id="design_coupler_detuning",
            axes=(TraceAxis(name="bias", unit="V", length=76),),
            preview_payload={
                "kind": "series",
                "points": _build_interpolated_series_points(
                    anchors=((-0.28, 11.0), (-0.265, 10.7), (-0.25, 10.3)),
                    length=76,
                ),
            },
            payload_ref=build_trace_payload_ref(
                payload_role="dataset_primary",
                store_key="datasets/transmon-coupler-014/designs/design_coupler_detuning/batches/batch_5.zarr",
                store_uri="trace_store/datasets/transmon-coupler-014/designs/design_coupler_detuning/batches/batch_5.zarr",
                group_path="/traces/trace_coupler_simulation",
                array_path="values",
                dtype="float64",
                shape=(76,),
                chunk_shape=(76,),
            ),
            result_handles=(),
        ),
    }


def _build_interpolated_series_points(
    *,
    anchors: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
    length: int,
) -> list[list[float]]:
    if length <= 1:
        return [[round(anchors[0][0], 6), round(anchors[0][1], 6)]]

    start, middle, end = anchors
    middle_index = length // 2
    last_index = length - 1

    def _interpolate(
        left: tuple[float, float],
        right: tuple[float, float],
        ratio: float,
    ) -> list[float]:
        x = left[0] + ((right[0] - left[0]) * ratio)
        y = left[1] + ((right[1] - left[1]) * ratio)
        return [round(x, 6), round(y, 6)]

    points: list[list[float]] = []
    for index in range(length):
        if index <= middle_index:
            ratio = 0.0 if middle_index == 0 else index / middle_index
            points.append(_interpolate(start, middle, ratio))
            continue
        ratio = (index - middle_index) / max(last_index - middle_index, 1)
        points.append(_interpolate(middle, end, ratio))
    return points


def _seed_characterization_analysis_registry() -> dict[
    tuple[str, str],
    tuple[CharacterizationAnalysisRegistryRow, ...],
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
        ): (
            CharacterizationAnalysisRegistryRow(
                analysis_id="admittance_extraction",
                label="Admittance Resonance Extraction",
                availability_state="recommended",
                required_config_fields=("fit_window", "residual_tolerance"),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=2,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary="2 design traces are eligible for admittance resonance extraction.",
                ),
            ),
            CharacterizationAnalysisRegistryRow(
                analysis_id="sideband_comparison",
                label="Sideband Comparison",
                availability_state="available",
                required_config_fields=("comparison_window",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=1,
                    selected_trace_count=0,
                    recommended_trace_modes=("sideband",),
                    summary=(
                        "One compatible sideband trace is visible, but "
                        "comparison coverage remains thin."
                    ),
                ),
            ),
            CharacterizationAnalysisRegistryRow(
                analysis_id="junction_parameter_identification",
                label="Junction Parameter Identification",
                availability_state="unavailable",
                required_config_fields=("fit_window", "prior_family"),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=0,
                    selected_trace_count=0,
                    recommended_trace_modes=("base", "sideband"),
                    summary=(
                        "No compatible trace bundle currently satisfies the "
                        "identification prerequisites."
                    ),
                ),
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
        ): (
            CharacterizationAnalysisRegistryRow(
                analysis_id="screening_summary",
                label="Screening Summary",
                availability_state="available",
                required_config_fields=("screening_mode",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=1,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary="A single base trace is available for summary-only screening.",
                ),
            ),
            CharacterizationAnalysisRegistryRow(
                analysis_id="sideband_comparison",
                label="Sideband Comparison",
                availability_state="unavailable",
                required_config_fields=("comparison_window",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=0,
                    selected_trace_count=0,
                    recommended_trace_modes=("sideband",),
                    summary="No sideband trace is available in this design scope yet.",
                ),
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
        ): (
            CharacterizationAnalysisRegistryRow(
                analysis_id="quality_factor_fit",
                label="Quality Factor Fit",
                availability_state="recommended",
                required_config_fields=("temperature_window",),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=1,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary=(
                        "The temperature sweep exposes one high-quality base "
                        "trace for resonator fitting."
                    ),
                ),
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
        ): (
            CharacterizationAnalysisRegistryRow(
                analysis_id="coupler_shift_fit",
                label="Coupler Shift Fit",
                availability_state="recommended",
                required_config_fields=("fit_window", "cross_check_mode"),
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=2,
                    selected_trace_count=0,
                    recommended_trace_modes=("base",),
                    summary="Measurement and simulation traces are both visible for a coupled fit.",
                ),
            ),
        ),
    }


def _seed_characterization_run_history() -> dict[
    tuple[str, str],
    tuple[CharacterizationRunHistoryRow, ...],
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
        ): (
            CharacterizationRunHistoryRow(
                run_id="run-flux-a-004",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                analysis_id="sideband_comparison",
                label="Flux Scan A sideband comparison",
                status="failed",
                scope="design_traces",
                trace_count=1,
                sources_summary="Y phase 1",
                provenance_summary="Measurement sideband trace · batch #4",
                updated_at="2026-03-14T11:20:00Z",
                result_id="char-sideband-flux-a-02",
            ),
            CharacterizationRunHistoryRow(
                run_id="run-flux-a-003",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                analysis_id="admittance_extraction",
                label="Flux Scan A admittance resonance extraction",
                status="completed",
                scope="design_traces",
                trace_count=2,
                sources_summary="Y base 2",
                provenance_summary="Measurement batch #4 + layout batch #2",
                updated_at="2026-03-14T11:12:00Z",
                result_id="char-fit-flux-a-01",
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
        ): (
            CharacterizationRunHistoryRow(
                run_id="run-flux-b-001",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_b",
                analysis_id="screening_summary",
                label="Flux Scan B screening summary",
                status="blocked",
                scope="design_traces",
                trace_count=1,
                sources_summary="S21 1",
                provenance_summary="Measurement raw trace · batch #7",
                updated_at="2026-03-14T09:54:00Z",
                result_id="char-flux-b-screening",
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
        ): (
            CharacterizationRunHistoryRow(
                run_id="run-res-temp-002",
                dataset_id="resonator-chip-002",
                design_id="design_resonator_temp",
                analysis_id="quality_factor_fit",
                label="Temperature sweep quality factor fit",
                status="completed",
                scope="design_traces",
                trace_count=1,
                sources_summary="Temperature sweep 1",
                provenance_summary="Measurement batch #12",
                updated_at="2026-03-13T18:00:00Z",
                result_id="char-resonator-temp-qi",
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
        ): (
            CharacterizationRunHistoryRow(
                run_id="run-coupler-011",
                dataset_id="transmon-coupler-014",
                design_id="design_coupler_detuning",
                analysis_id="coupler_shift_fit",
                label="Coupler detuning chi fit",
                status="completed",
                scope="design_traces",
                trace_count=2,
                sources_summary="Measurement 1 + simulation 1",
                provenance_summary="Measurement + simulation cross-check",
                updated_at="2026-03-14T09:35:00Z",
                result_id="char-coupler-detuning-chi",
            ),
        ),
    }


def _seed_characterization_results() -> dict[
    tuple[str, str],
    tuple[CharacterizationResultSummary, ...],
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
        ): (
            CharacterizationResultSummary(
                result_id="char-fit-flux-a-01",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                analysis_id="admittance_extraction",
                title="Flux Scan A admittance resonance extraction",
                status="completed",
                freshness_summary="Materialized 14 minutes ago",
                provenance_summary="Measurement batch #4 + layout batch #2",
                trace_count=2,
                artifact_count=3,
                updated_at="2026-03-14T11:12:00Z",
            ),
            CharacterizationResultSummary(
                result_id="char-sideband-flux-a-02",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_a",
                analysis_id="sideband_comparison",
                title="Flux Scan A sideband comparison",
                status="failed",
                freshness_summary="Failed 6 minutes ago",
                provenance_summary="Measurement phase trace only",
                trace_count=1,
                artifact_count=1,
                updated_at="2026-03-14T11:20:00Z",
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
        ): (
            CharacterizationResultSummary(
                result_id="char-flux-b-screening",
                dataset_id="fluxonium-2025-031",
                design_id="design_flux_scan_b",
                analysis_id="screening_summary",
                title="Flux Scan B screening summary",
                status="blocked",
                freshness_summary="Awaiting compatible trace bundle",
                provenance_summary="Single measurement trace only",
                trace_count=1,
                artifact_count=0,
                updated_at="2026-03-14T09:54:00Z",
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
        ): (
            CharacterizationResultSummary(
                result_id="char-resonator-temp-qi",
                dataset_id="resonator-chip-002",
                design_id="design_resonator_temp",
                analysis_id="quality_factor_fit",
                title="Temperature sweep quality factor fit",
                status="completed",
                freshness_summary="Materialized 2 hours ago",
                provenance_summary="Measurement batch #12",
                trace_count=1,
                artifact_count=2,
                updated_at="2026-03-13T18:00:00Z",
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
        ): (
            CharacterizationResultSummary(
                result_id="char-coupler-detuning-chi",
                dataset_id="transmon-coupler-014",
                design_id="design_coupler_detuning",
                analysis_id="coupler_shift_fit",
                title="Coupler detuning chi fit",
                status="completed",
                freshness_summary="Materialized 38 minutes ago",
                provenance_summary="Measurement + simulation cross-check",
                trace_count=2,
                artifact_count=3,
                updated_at="2026-03-14T09:35:00Z",
            ),
        ),
    }


def _seed_characterization_result_details() -> dict[
    tuple[str, str, str],
    CharacterizationResultDetail,
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "char-fit-flux-a-01",
        ): CharacterizationResultDetail(
            result_id="char-fit-flux-a-01",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            analysis_id="admittance_extraction",
            title="Flux Scan A admittance resonance extraction",
            status="completed",
            freshness_summary="Materialized 14 minutes ago",
            provenance_summary="Measurement batch #4 + layout batch #2",
            trace_count=2,
            updated_at="2026-03-14T11:12:00Z",
            input_trace_ids=("trace_flux_a_measurement", "trace_flux_a_layout"),
            payload=summarize_admittance_surface(
                analysis_run_id=101,
                analysis_config={
                    "fit_window": [5.4, 6.0],
                    "residual_tolerance": 0.02,
                },
                surface=_seed_admittance_flux_scan_a_surface(),
            ),
            diagnostics=_seed_admittance_flux_scan_a_surface().diagnostics,
            artifact_refs=annotate_admittance_artifact_refs(
                build_admittance_artifact_refs(result_id="char-fit-flux-a-01"),
                _seed_admittance_flux_scan_a_surface(),
            ),
            identify_surface=build_admittance_identify_surface(
                result_id="char-fit-flux-a-01",
                surface=_seed_admittance_flux_scan_a_surface(),
                applied_tags=(
                    CharacterizationAppliedTag(
                        artifact_id="char-fit-flux-a-01:identify-summary",
                        source_parameter="lowest_observed_frequency_ghz",
                        designated_metric="lowest_observed_frequency_ghz",
                        designated_metric_label="Lowest Observed Frequency",
                        tagged_at="2026-03-14T11:05:00Z",
                    ),
                    CharacterizationAppliedTag(
                        artifact_id="char-fit-flux-a-01:identify-summary",
                        source_parameter="residual_rms_max",
                        designated_metric="residual_rms_max",
                        designated_metric_label="Max Residual RMS",
                        tagged_at="2026-03-14T11:08:00Z",
                    ),
                ),
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "char-sideband-flux-a-02",
        ): CharacterizationResultDetail(
            result_id="char-sideband-flux-a-02",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_a",
            analysis_id="sideband_comparison",
            title="Flux Scan A sideband comparison",
            status="failed",
            freshness_summary="Failed 6 minutes ago",
            provenance_summary="Measurement phase trace only",
            trace_count=1,
            updated_at="2026-03-14T11:20:00Z",
            input_trace_ids=("trace_flux_a_phase",),
            payload={
                "comparison_window": {"center": 5.81, "unit": "GHz"},
                "failure_summary": "Sideband peaks fell below the comparison threshold.",
            },
            diagnostics=(
                CharacterizationDiagnostic(
                    severity="error",
                    code="sideband_peak_missing",
                    message="No stable sideband peak was detected in the selected trace bundle.",
                    blocking=True,
                ),
            ),
            artifact_refs=(
                CharacterizationArtifactRef(
                    artifact_id="artifact-sideband-report-flux-a-02",
                    category="report",
                    view_kind="text",
                    title="Failure report",
                    payload_format="markdown",
                    payload_locator="artifacts/characterization/flux-a-sideband-report.md",
                ),
            ),
            identify_surface=_build_identify_surface(
                source_parameters=(),
                designated_metrics=(
                    CharacterizationDesignatedMetricOption(
                        metric_key="sideband_offset",
                        label="Sideband Offset",
                    ),
                ),
                applied_tags=(),
            ),
        ),
        (
            "fluxonium-2025-031",
            "design_flux_scan_b",
            "char-flux-b-screening",
        ): CharacterizationResultDetail(
            result_id="char-flux-b-screening",
            dataset_id="fluxonium-2025-031",
            design_id="design_flux_scan_b",
            analysis_id="screening_summary",
            title="Flux Scan B screening summary",
            status="blocked",
            freshness_summary="Awaiting compatible trace bundle",
            provenance_summary="Single measurement trace only",
            trace_count=1,
            updated_at="2026-03-14T09:54:00Z",
            input_trace_ids=("trace_flux_b_measurement",),
            payload={
                "blocking_reason": (
                    "At least one comparison trace is required before "
                    "screening can produce persisted artifacts."
                ),
            },
            diagnostics=(
                CharacterizationDiagnostic(
                    severity="warning",
                    code="trace_selection_incomplete",
                    message=(
                        "The selected design scope does not yet expose a "
                        "compatible comparison pair."
                    ),
                    blocking=True,
                ),
            ),
            artifact_refs=(),
            identify_surface=_build_identify_surface(
                source_parameters=(),
                designated_metrics=(),
                applied_tags=(),
            ),
        ),
        (
            "resonator-chip-002",
            "design_resonator_temp",
            "char-resonator-temp-qi",
        ): CharacterizationResultDetail(
            result_id="char-resonator-temp-qi",
            dataset_id="resonator-chip-002",
            design_id="design_resonator_temp",
            analysis_id="quality_factor_fit",
            title="Temperature sweep quality factor fit",
            status="completed",
            freshness_summary="Materialized 2 hours ago",
            provenance_summary="Measurement batch #12",
            trace_count=1,
            updated_at="2026-03-13T18:00:00Z",
            input_trace_ids=("trace_res_temp_measurement",),
            payload={
                "fit_table": [
                    {"parameter": "Qi_low_temp", "value": 18200, "unit": ""},
                    {"parameter": "Qi_high_temp", "value": 13100, "unit": ""},
                ],
            },
            diagnostics=(),
            artifact_refs=(
                CharacterizationArtifactRef(
                    artifact_id="artifact-resonator-temp-table",
                    category="fit_table",
                    view_kind="table",
                    title="Quality factor table",
                    payload_format="json",
                    payload_locator="artifacts/characterization/resonator-temp-fit-table.json",
                ),
                CharacterizationArtifactRef(
                    artifact_id="artifact-resonator-temp-plot",
                    category="plot",
                    view_kind="plot",
                    title="Temperature fit plot",
                    payload_format="svg",
                    payload_locator="artifacts/characterization/resonator-temp-fit-plot.svg",
                ),
            ),
            identify_surface=_build_identify_surface(
                source_parameters=(
                    CharacterizationSourceParameterOption(
                        artifact_id="artifact-resonator-temp-table",
                        source_parameter="Qi_low_temp",
                        label="Qi low temp",
                        artifact_title="Quality factor table",
                        current_designated_metric=None,
                    ),
                    CharacterizationSourceParameterOption(
                        artifact_id="artifact-resonator-temp-table",
                        source_parameter="Qi_high_temp",
                        label="Qi high temp",
                        artifact_title="Quality factor table",
                        current_designated_metric=None,
                    ),
                ),
                designated_metrics=(
                    CharacterizationDesignatedMetricOption(
                        metric_key="qi_low_temp",
                        label="Low Temperature Qi",
                    ),
                    CharacterizationDesignatedMetricOption(
                        metric_key="qi_high_temp",
                        label="High Temperature Qi",
                    ),
                    CharacterizationDesignatedMetricOption(
                        metric_key="thermal_rolloff",
                        label="Thermal Rolloff",
                    ),
                ),
                applied_tags=(),
            ),
        ),
        (
            "transmon-coupler-014",
            "design_coupler_detuning",
            "char-coupler-detuning-chi",
        ): CharacterizationResultDetail(
            result_id="char-coupler-detuning-chi",
            dataset_id="transmon-coupler-014",
            design_id="design_coupler_detuning",
            analysis_id="coupler_shift_fit",
            title="Coupler detuning chi fit",
            status="completed",
            freshness_summary="Materialized 38 minutes ago",
            provenance_summary="Measurement + simulation cross-check",
            trace_count=2,
            updated_at="2026-03-14T09:35:00Z",
            input_trace_ids=("trace_coupler_measurement", "trace_coupler_simulation"),
            payload={
                "fit_table": [
                    {"parameter": "chi", "value": 2.31, "unit": "MHz"},
                    {"parameter": "detuning_zero", "value": -0.247, "unit": "V"},
                ],
                "cross_check": {
                    "measurement_peak": 10.8,
                    "simulation_peak": 10.7,
                },
            },
            diagnostics=(
                CharacterizationDiagnostic(
                    severity="info",
                    code="simulation_cross_check_passed",
                    message="Simulation-backed cross-check stayed within tolerance.",
                    blocking=False,
                ),
            ),
            artifact_refs=(
                CharacterizationArtifactRef(
                    artifact_id="artifact-coupler-fit-table",
                    category="fit_table",
                    view_kind="table",
                    title="Chi fit table",
                    payload_format="json",
                    payload_locator="artifacts/characterization/coupler-fit-table.json",
                ),
                CharacterizationArtifactRef(
                    artifact_id="artifact-coupler-fit-plot",
                    category="plot",
                    view_kind="plot",
                    title="Detuning fit plot",
                    payload_format="svg",
                    payload_locator="artifacts/characterization/coupler-fit-plot.svg",
                ),
                CharacterizationArtifactRef(
                    artifact_id="artifact-coupler-report",
                    category="report",
                    view_kind="text",
                    title="Research summary",
                    payload_format="markdown",
                    payload_locator="artifacts/characterization/coupler-report.md",
                ),
            ),
            identify_surface=_build_identify_surface(
                source_parameters=(
                    CharacterizationSourceParameterOption(
                        artifact_id="artifact-coupler-fit-table",
                        source_parameter="chi",
                        label="chi",
                        artifact_title="Chi fit table",
                        current_designated_metric="chi",
                    ),
                    CharacterizationSourceParameterOption(
                        artifact_id="artifact-coupler-fit-table",
                        source_parameter="detuning_zero",
                        label="Detuning zero",
                        artifact_title="Chi fit table",
                        current_designated_metric=None,
                    ),
                ),
                designated_metrics=(
                    CharacterizationDesignatedMetricOption(
                        metric_key="chi",
                        label="Coupler Shift",
                    ),
                    CharacterizationDesignatedMetricOption(
                        metric_key="detuning_zero",
                        label="Zero Detuning Bias",
                    ),
                ),
                applied_tags=(
                    CharacterizationAppliedTag(
                        artifact_id="artifact-coupler-fit-table",
                        source_parameter="chi",
                        designated_metric="chi",
                        designated_metric_label="Coupler Shift",
                        tagged_at="2026-03-14T09:30:00Z",
                    ),
                ),
            ),
        ),
    }


def _seed_characterization_artifact_surfaces() -> dict[
    tuple[str, str, str],
    AdmittanceResultSurface,
]:
    return {
        (
            "fluxonium-2025-031",
            "design_flux_scan_a",
            "char-fit-flux-a-01",
        ): _seed_admittance_flux_scan_a_surface(),
    }


def _seed_admittance_flux_scan_a_surface() -> AdmittanceResultSurface:
    return AdmittanceResultSurface(
        input_axis_key="flux_bias",
        input_axis_label="Flux bias",
        input_axis_unit="mA",
        input_axis_values=(7.4, 7.6, 7.8),
        frequency_grid_by_input=(
            (5.612, 5.846),
            (5.587, 5.821),
            (None, None),
        ),
        residual_rms_by_input=(0.0118, 0.0131, None),
        fit_window_ghz=(5.4, 6.0),
        masked_input_indices=(2,),
        diagnostics=(
            CharacterizationDiagnostic(
                severity="info",
                code="fit_residual_rms_evaluated",
                message=(
                    "All persisted input positions stay within the configured residual tolerance."
                ),
                blocking=False,
            ),
            CharacterizationDiagnostic(
                severity="warning",
                code="masked_input_positions_preserved",
                message=(
                    "1 input positions remained fully masked and were preserved "
                    "in the persisted result surface."
                ),
                blocking=False,
            ),
        ),
    )


def _build_identify_surface(
    *,
    source_parameters: tuple[CharacterizationSourceParameterOption, ...],
    designated_metrics: tuple[CharacterizationDesignatedMetricOption, ...],
    applied_tags: tuple[CharacterizationAppliedTag, ...],
) -> CharacterizationIdentifySurface:
    return CharacterizationIdentifySurface(
        source_parameters=source_parameters,
        designated_metrics=designated_metrics,
        applied_tags=applied_tags,
    )


def _build_tagged_metric_id(dataset_id: str, designated_metric: str) -> str:
    normalized_dataset = dataset_id.replace("_", "-")
    normalized_metric = designated_metric.replace("_", "-")
    return f"metric-{normalized_dataset}-{normalized_metric}"


def _seed_circuit_definitions() -> tuple[CircuitDefinitionRecord, ...]:
    floating_qubit_source = """{
    "name": "FloatingQubitWithXYLine",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 100.0, "unit": "fF"},
        {"name": "Lj1", "default": 1000.0, "unit": "pH"},
        {"name": "C2", "default": 1000.0, "unit": "fF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("Lj1", "2", "0", "Lj1"),
        ("C2", "2", "0", "C2")
    ]
}"""
    readout_chain_source = """{
    "name": "FluxoniumReadoutChain",
    "parameters": [
        {"name": "Lj", "default": 1000.0, "unit": "pH"},
        {"name": "Cj", "default": 1000.0, "unit": "fF"}
    ],
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 100.0, "unit": "fF"},
        {"name": "Lj1", "value_ref": "Lj", "unit": "pH"},
        {"name": "C2", "value_ref": "Cj", "unit": "fF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("Lj1", "2", "0", "Lj1"),
        ("C2", "2", "0", "C2")
    ]
}"""
    coupler_demo_source = """{
    "name": "CouplerDetuningDemo",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 80.0, "unit": "fF"},
        {"name": "Lj1", "default": 850.0, "unit": "pH"},
        {"name": "C2", "default": 950.0, "unit": "fF"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("Lj1", "2", "0", "Lj1"),
        ("C2", "2", "0", "C2")
    ]
}"""
    local_resonator_source = """{
    "name": "LocalSpaceResonator",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
        {"name": "C1", "default": 120.0, "unit": "fF"},
        {"name": "L1", "default": 900.0, "unit": "pH"}
    ],
    "topology": [
        ("P1", "1", "0", 1),
        ("R1", "1", "0", "R1"),
        ("C1", "1", "2", "C1"),
        ("L1", "2", "0", "L1")
    ]
}"""
    return (
        _build_circuit_definition_record(
            definition_id=LOCAL_SPACE_RESONATOR_DEFINITION_ID,
            workspace_id="local-space",
            visibility_scope="local",
            owner_user_id="local-operator",
            owner_display_name="Local Operator",
            name="LocalSpaceResonator",
            created_at="2026-03-17T08:15:00Z",
            updated_at="2026-03-17T08:15:00Z",
            concurrency_token=f"etag_{LOCAL_SPACE_RESONATOR_DEFINITION_ID}_1",
            source_text=local_resonator_source,
        ),
        _build_circuit_definition_record(
            definition_id=FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID,
            workspace_id="ws-device-lab",
            visibility_scope="private",
            owner_user_id="researcher-01",
            owner_display_name="Ari",
            name="FloatingQubitWithXYLine",
            created_at="2026-03-08T18:19:42Z",
            updated_at="2026-03-14T08:30:00Z",
            concurrency_token=f"etag_{FLOATING_QUBIT_WITH_XY_LINE_DEFINITION_ID}_3",
            source_text=floating_qubit_source,
        ),
        _build_circuit_definition_record(
            definition_id=FLUXONIUM_READOUT_CHAIN_DEFINITION_ID,
            workspace_id="ws-device-lab",
            visibility_scope="workspace",
            owner_user_id="researcher-01",
            owner_display_name="Ari",
            name="FluxoniumReadoutChain",
            created_at="2026-03-05T11:14:03Z",
            updated_at="2026-03-14T07:42:00Z",
            concurrency_token=f"etag_{FLUXONIUM_READOUT_CHAIN_DEFINITION_ID}_2",
            source_text=readout_chain_source,
        ),
        _build_circuit_definition_record(
            definition_id=COUPLER_DETUNING_DEMO_DEFINITION_ID,
            workspace_id="ws-device-lab",
            visibility_scope="workspace",
            owner_user_id="collaborator-02",
            owner_display_name="Device Lab",
            name="CouplerDetuningDemo",
            created_at="2026-02-25T09:43:18Z",
            updated_at="2026-03-13T16:10:00Z",
            concurrency_token=f"etag_{COUPLER_DETUNING_DEMO_DEFINITION_ID}_4",
            source_text=coupler_demo_source,
        ),
    )
