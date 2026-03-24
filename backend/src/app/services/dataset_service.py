import logging
from collections.abc import Sequence
from typing import Protocol

from src.app.domain.audit import AuditRecord
from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryQuery,
    CharacterizationAnalysisRegistryRow,
    CharacterizationAnalysisTraceCompatibility,
    CharacterizationResultBrowseQuery,
    CharacterizationResultDetail,
    CharacterizationResultSummary,
    CharacterizationRunHistoryQuery,
    CharacterizationRunHistoryRow,
    CharacterizationTaggingRequest,
    CharacterizationTaggingResult,
    DatasetAllowedActions,
    DatasetCatalogRow,
    DatasetCreateDraft,
    DatasetDesignMutationResult,
    DatasetDetail,
    DatasetLifecycleMutationResult,
    DatasetProfileField,
    DatasetProfileUpdate,
    DatasetProfileUpdateResult,
    DesignBrowseQuery,
    DesignBrowseRow,
    DesignCreateDraft,
    RawDataIngestionDraft,
    RawDataIngestionResult,
    TaggedCoreMetricSummary,
    TraceBrowseQuery,
    TraceDeleteResult,
    TraceDetail,
    TraceMetadataSummary,
    TraceMutationPolicy,
    TraceUpdateDraft,
    TraceUpdateResult,
)
from src.app.domain.session import SessionState
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error

logger = logging.getLogger(__name__)


class DatasetRepository(Protocol):
    def list_dataset_details(self) -> Sequence[DatasetDetail]: ...

    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def create_dataset(
        self,
        *,
        workspace_id: str,
        visibility_scope: str,
        owner_user_id: str,
        owner_display_name: str,
        draft: DatasetCreateDraft,
    ) -> DatasetDetail: ...

    def update_dataset_profile(
        self,
        dataset_id: str,
        update: DatasetProfileUpdate,
    ) -> DatasetDetail | None: ...

    def set_dataset_lifecycle_state(
        self,
        dataset_id: str,
        lifecycle_state: str,
    ) -> DatasetDetail | None: ...

    def ingest_raw_data(
        self,
        dataset_id: str,
        draft: RawDataIngestionDraft,
    ) -> RawDataIngestionResult | None: ...

    def create_design(
        self,
        dataset_id: str,
        draft: DesignCreateDraft,
    ) -> DatasetDesignMutationResult | None: ...

    def list_tagged_core_metrics(
        self,
        dataset_id: str,
    ) -> Sequence[TaggedCoreMetricSummary]: ...

    def list_designs(
        self,
        dataset_id: str,
    ) -> Sequence[DesignBrowseRow]: ...

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[TraceMetadataSummary]: ...

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDetail | None: ...

    def get_trace_mutation_policy(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceMutationPolicy | None: ...

    def update_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        update: TraceUpdateDraft,
    ) -> TraceUpdateResult | None: ...

    def delete_traces(
        self,
        dataset_id: str,
        design_id: str,
        trace_ids: Sequence[str],
    ) -> tuple[str, ...] | None: ...

    def list_characterization_results(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[CharacterizationResultSummary]: ...

    def list_characterization_analysis_registry(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[CharacterizationAnalysisRegistryRow]: ...

    def list_characterization_run_history(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[CharacterizationRunHistoryRow]: ...

    def get_characterization_result(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> CharacterizationResultDetail | None: ...

    def apply_characterization_tagging(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        request: CharacterizationTaggingRequest,
    ) -> CharacterizationTaggingResult: ...


class SessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class DatasetAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class DatasetService:
    def __init__(
        self,
        repository: DatasetRepository,
        session_repository: SessionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: DatasetAuditRepository | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository

    def list_dataset_catalog(self) -> list[DatasetCatalogRow]:
        state = self._session_repository.get_session_state()
        return [
            DatasetCatalogRow(
                dataset_id=dataset.dataset_id,
                name=dataset.name,
                visibility_scope=dataset.visibility_scope,
                lifecycle_state=dataset.lifecycle_state,
                device_type=dataset.device_type,
                updated_at=dataset.updated_at,
                allowed_actions=self._allowed_actions(dataset, state),
                family=dataset.family,
                owner_display_name=dataset.owner,
            )
            for dataset in self._visible_datasets(state)
        ]

    def create_dataset(self, draft: DatasetCreateDraft) -> DatasetLifecycleMutationResult:
        state = self._session_repository.get_session_state()
        if not self._can_manage_datasets(state):
            raise service_error(
                403,
                code="dataset_create_denied",
                category="permission_denied",
                message="The active session cannot create datasets in the current context.",
            )
        visibility_scope = "local" if state.runtime_mode == "local" else "private"
        owner_user_id = state.user.user_id if state.user is not None else "local-operator"
        owner_display_name = (
            state.user.display_name if state.user is not None else "Local Operator"
        )
        created = self._repository.create_dataset(
            workspace_id=state.workspace_id,
            visibility_scope=visibility_scope,
            owner_user_id=owner_user_id,
            owner_display_name=owner_display_name,
            draft=draft,
        )
        dataset = self._with_allowed_actions(created, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.created",
            dataset=dataset,
            payload={
                "dataset_id": dataset.dataset_id,
                "visibility_scope": dataset.visibility_scope,
            },
        )
        return DatasetLifecycleMutationResult(
            dataset=dataset,
            catalog_row=self._catalog_row(dataset, state),
        )

    def get_dataset_profile(self, dataset_id: str) -> DatasetDetail:
        return self._require_visible_dataset(dataset_id)

    def update_dataset_profile(
        self,
        dataset_id: str,
        update: DatasetProfileUpdate,
    ) -> DatasetProfileUpdateResult:
        current = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        allowed_actions = self._allowed_actions(current, state)
        if not allowed_actions.update_profile:
            raise service_error(
                403,
                code="dataset_profile_update_denied",
                category="permission_denied",
                message="The active session cannot update this dataset profile.",
            )

        updated = self._repository.update_dataset_profile(dataset_id, update)
        if updated is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        updated = DatasetDetail(
            **{
                **updated.__dict__,
                "allowed_actions": self._allowed_actions(updated, state),
            }
        )
        updated_fields = self._updated_fields(current, updated)
        logger.info("Dataset profile updated dataset_id=%s", dataset_id)
        if self._audit_repository is not None:
            self._audit_repository.append(
                build_audit_record(
                    state=state,
                    action_kind="dataset.profile_updated",
                    resource_kind="dataset",
                    resource_id=dataset_id,
                    outcome="completed",
                    payload={
                        "dataset_id": dataset_id,
                        "updated_fields": [
                            field if isinstance(field, str) else field.value
                            for field in updated_fields
                        ],
                    },
                    workspace_id=updated.workspace_id,
                )
            )
        return DatasetProfileUpdateResult(
            dataset=updated,
            updated_fields=updated_fields,
        )

    def archive_dataset(self, dataset_id: str) -> DatasetLifecycleMutationResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        allowed_actions = self._allowed_actions(dataset, state)
        if not allowed_actions.archive:
            raise service_error(
                403,
                code="dataset_archive_denied",
                category="permission_denied",
                message="The active session cannot archive this dataset.",
            )
        updated = self._repository.set_dataset_lifecycle_state(dataset_id, "archived")
        if updated is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        dataset = self._with_allowed_actions(updated, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.archived",
            dataset=dataset,
            payload={"dataset_id": dataset_id},
        )
        return DatasetLifecycleMutationResult(
            dataset=dataset,
            catalog_row=self._catalog_row(dataset, state),
        )

    def delete_dataset(self, dataset_id: str) -> DatasetLifecycleMutationResult:
        dataset = self._require_manageable_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        if not self._can_manage_datasets(state):
            raise service_error(
                403,
                code="dataset_delete_denied",
                category="permission_denied",
                message="The active session cannot delete this dataset.",
            )
        updated = self._repository.set_dataset_lifecycle_state(dataset_id, "deleted")
        if updated is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        dataset = self._with_allowed_actions(updated, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.deleted",
            dataset=dataset,
            payload={"dataset_id": dataset_id},
        )
        return DatasetLifecycleMutationResult(
            dataset=dataset,
            catalog_row=self._catalog_row(dataset, state),
        )

    def ingest_raw_data(
        self,
        dataset_id: str,
        draft: RawDataIngestionDraft,
    ) -> RawDataIngestionResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        allowed_actions = self._allowed_actions(dataset, state)
        if not allowed_actions.ingest_raw_data:
            raise service_error(
                403,
                code="dataset_ingestion_denied",
                category="permission_denied",
                message="The active session cannot ingest raw data into this dataset.",
            )
        result = self._repository.ingest_raw_data(dataset_id, draft)
        if result is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        materialized_dataset = self._with_allowed_actions(result.dataset, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.raw_data_ingested",
            dataset=materialized_dataset,
            payload={
                "dataset_id": dataset_id,
                "ingestion_kind": draft.kind,
                "design_id": result.design.design_id,
                "trace_ids": [trace.trace_id for trace in result.traces],
            },
        )
        return RawDataIngestionResult(
            dataset=materialized_dataset,
            design=result.design,
            traces=result.traces,
        )

    def create_design(
        self,
        dataset_id: str,
        draft: DesignCreateDraft,
    ) -> DatasetDesignMutationResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        allowed_actions = self._allowed_actions(dataset, state)
        if not allowed_actions.ingest_raw_data:
            raise service_error(
                403,
                code="dataset_design_create_denied",
                category="permission_denied",
                message="The active session cannot create designs in this dataset.",
            )

        requested_design_id = _build_design_id(draft.name)
        conflict = next(
            (
                row
                for row in self._repository.list_designs(dataset_id)
                if row.design_id == requested_design_id
                or row.name.casefold() == draft.name.casefold()
            ),
            None,
        )
        if conflict is not None:
            raise service_error(
                409,
                code="dataset_design_conflict",
                category="conflict",
                message=(
                    "A design with this name already exists in the selected dataset. "
                    "Select the existing design instead of creating a duplicate."
                ),
            )

        try:
            result = self._repository.create_design(dataset_id, draft)
        except ValueError as exc:
            raise service_error(
                409,
                code="dataset_design_conflict",
                category="conflict",
                message=(
                    "A design with this name already exists in the selected dataset. "
                    "Select the existing design instead of creating a duplicate."
                ),
            ) from exc
        if result is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )

        updated_dataset = self._with_allowed_actions(result.dataset, state)
        self._append_audit_record(
            state=state,
            action_kind="dataset.design_created",
            dataset=updated_dataset,
            payload={
                "dataset_id": dataset_id,
                "design_id": result.design.design_id,
                "design_name": result.design.name,
            },
        )
        return DatasetDesignMutationResult(
            dataset=updated_dataset,
            design=result.design,
        )

    def list_tagged_core_metrics(self, dataset_id: str) -> list[TaggedCoreMetricSummary]:
        self._require_visible_dataset(dataset_id)
        return list(self._repository.list_tagged_core_metrics(dataset_id))

    def list_designs(
        self,
        dataset_id: str,
        query: DesignBrowseQuery,
    ) -> list[DesignBrowseRow]:
        self._require_visible_dataset(dataset_id)
        rows = list(self._repository.list_designs(dataset_id))
        if query.search is None:
            return rows
        token = query.search.casefold()
        return [row for row in rows if token in row.name.casefold()]

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
        query: TraceBrowseQuery,
    ) -> list[TraceMetadataSummary]:
        self._require_visible_dataset(dataset_id)
        rows = list(self._repository.list_trace_metadata(dataset_id, design_id))
        filtered = rows
        if query.search is not None:
            token = query.search.casefold()
            filtered = [
                row
                for row in filtered
                if token in row.parameter.casefold() or token in row.provenance_summary.casefold()
            ]
        if query.family is not None:
            filtered = [row for row in filtered if row.family == query.family]
        if query.representation is not None:
            normalized = query.representation.casefold()
            filtered = [row for row in filtered if row.representation.casefold() == normalized]
        if query.source_kind is not None:
            filtered = [row for row in filtered if row.source_kind == query.source_kind]
        if query.trace_mode_group is not None:
            filtered = [row for row in filtered if row.trace_mode_group == query.trace_mode_group]
        return filtered

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDetail:
        self._require_visible_dataset(dataset_id)
        detail = self._repository.get_trace_detail(dataset_id, design_id, trace_id)
        if detail is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        return detail

    def update_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        update: TraceUpdateDraft,
    ) -> TraceUpdateResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        if not dataset.allowed_actions.ingest_raw_data:
            raise service_error(
                403,
                code="trace_update_denied",
                category="permission_denied",
                message="The active session cannot update traces in the selected dataset.",
            )
        self._require_trace_mutation_policy(
            dataset_id,
            design_id,
            trace_id,
            allow_update=True,
            denied_code="trace_update_denied",
            denied_action="updated",
        )
        result = self._repository.update_trace(dataset_id, design_id, trace_id, update)
        if result is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        self._append_audit_record(
            state=state,
            action_kind="dataset.trace_updated",
            dataset=dataset,
            payload={
                "dataset_id": dataset_id,
                "design_id": design_id,
                "trace_id": trace_id,
                "updated_fields": self._updated_trace_fields(update),
            },
        )
        return result

    def delete_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDeleteResult:
        return self.delete_traces(dataset_id, design_id, (trace_id,))

    def delete_traces(
        self,
        dataset_id: str,
        design_id: str,
        trace_ids: Sequence[str],
    ) -> TraceDeleteResult:
        dataset = self._require_visible_dataset(dataset_id)
        state = self._session_repository.get_session_state()
        if not dataset.allowed_actions.ingest_raw_data:
            raise service_error(
                403,
                code="trace_batch_delete_denied" if len(trace_ids) > 1 else "trace_delete_denied",
                category="permission_denied",
                message="The active session cannot delete traces in the selected dataset.",
            )
        denied_code = "trace_batch_delete_denied" if len(trace_ids) > 1 else "trace_delete_denied"
        deleted_trace_ids: list[str] = []
        for trace_id in trace_ids:
            self._require_trace_mutation_policy(
                dataset_id,
                design_id,
                trace_id,
                allow_update=False,
                denied_code=denied_code,
                denied_action="deleted",
            )
            deleted_trace_ids.append(trace_id)
        deleted = self._repository.delete_traces(dataset_id, design_id, tuple(deleted_trace_ids))
        if deleted is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        design = self._current_design_row(dataset_id, design_id)
        if design is None:
            raise service_error(
                404,
                code="design_not_found",
                category="not_found",
                message=f"Design {design_id} was not found in dataset {dataset_id}.",
            )
        self._append_audit_record(
            state=state,
            action_kind="dataset.trace_deleted",
            dataset=dataset,
            payload={
                "dataset_id": dataset_id,
                "design_id": design_id,
                "trace_ids": list(deleted),
            },
        )
        return TraceDeleteResult(
            design=design,
            deleted_trace_ids=deleted,
        )

    def list_characterization_results(
        self,
        dataset_id: str,
        design_id: str,
        query: CharacterizationResultBrowseQuery,
    ) -> list[CharacterizationResultSummary]:
        self._require_visible_dataset(dataset_id)
        rows = list(self._repository.list_characterization_results(dataset_id, design_id))
        filtered = rows
        if query.search is not None:
            token = query.search.casefold()
            filtered = [
                row
                for row in filtered
                if token in row.title.casefold()
                or token in row.analysis_id.casefold()
                or token in row.provenance_summary.casefold()
            ]
        if query.status is not None:
            filtered = [row for row in filtered if row.status == query.status]
        if query.analysis_id is not None:
            normalized_analysis_id = query.analysis_id.casefold()
            filtered = [
                row for row in filtered if row.analysis_id.casefold() == normalized_analysis_id
            ]
        return filtered

    def list_characterization_analysis_registry(
        self,
        dataset_id: str,
        design_id: str,
        query: CharacterizationAnalysisRegistryQuery,
    ) -> list[CharacterizationAnalysisRegistryRow]:
        self._require_visible_dataset(dataset_id)
        rows = list(self._repository.list_characterization_analysis_registry(dataset_id, design_id))
        if len(query.selected_trace_ids) == 0:
            return rows

        selected_trace_count = len(query.selected_trace_ids)
        return [
            CharacterizationAnalysisRegistryRow(
                analysis_id=row.analysis_id,
                label=row.label,
                availability_state=row.availability_state,
                required_config_fields=row.required_config_fields,
                trace_compatibility=CharacterizationAnalysisTraceCompatibility(
                    matched_trace_count=row.trace_compatibility.matched_trace_count,
                    selected_trace_count=selected_trace_count,
                    recommended_trace_modes=row.trace_compatibility.recommended_trace_modes,
                    summary=row.trace_compatibility.summary,
                ),
            )
            for row in rows
        ]

    def list_characterization_run_history(
        self,
        dataset_id: str,
        design_id: str,
        query: CharacterizationRunHistoryQuery,
    ) -> list[CharacterizationRunHistoryRow]:
        self._require_visible_dataset(dataset_id)
        rows = list(self._repository.list_characterization_run_history(dataset_id, design_id))
        if query.analysis_id is None:
            return rows
        normalized_analysis_id = query.analysis_id.casefold()
        return [row for row in rows if row.analysis_id.casefold() == normalized_analysis_id]

    def get_characterization_result(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ) -> CharacterizationResultDetail:
        self._require_visible_dataset(dataset_id)
        detail = self._repository.get_characterization_result(dataset_id, design_id, result_id)
        if detail is None:
            raise service_error(
                404,
                code="run_not_found",
                category="not_found",
                message=(
                    "The requested characterization result is not available "
                    "in the selected design scope."
                ),
            )
        return detail

    def apply_characterization_tagging(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        request: CharacterizationTaggingRequest,
    ) -> CharacterizationTaggingResult:
        detail = self.get_characterization_result(dataset_id, design_id, result_id)
        source_option = next(
            (
                option
                for option in detail.identify_surface.source_parameters
                if option.artifact_id == request.artifact_id
                and option.source_parameter == request.source_parameter
            ),
            None,
        )
        if source_option is None:
            raise service_error(
                400,
                code="trace_selection_invalid",
                category="validation_error",
                message=(
                    "The requested source parameter is not available in this "
                    "persisted result detail."
                ),
            )

        metric_option = next(
            (
                option
                for option in detail.identify_surface.designated_metrics
                if option.metric_key == request.designated_metric
            ),
            None,
        )
        if metric_option is None:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="The requested designated metric is not available for this dataset.",
            )

        current_metrics = list(self._repository.list_tagged_core_metrics(dataset_id))
        exact_match = next(
            (
                metric
                for metric in current_metrics
                if metric.source_parameter == request.source_parameter
                and metric.designated_metric == request.designated_metric
            ),
            None,
        )
        if exact_match is not None:
            return CharacterizationTaggingResult(
                tagging_status="already_applied",
                dataset_id=dataset_id,
                design_id=design_id,
                result_id=result_id,
                artifact_id=request.artifact_id,
                source_parameter=request.source_parameter,
                designated_metric=request.designated_metric,
                tagged_metric=exact_match,
            )

        conflicting_metric = next(
            (
                metric
                for metric in current_metrics
                if (
                    metric.designated_metric == request.designated_metric
                    and metric.source_parameter != request.source_parameter
                )
                or (
                    metric.source_parameter == request.source_parameter
                    and metric.designated_metric != request.designated_metric
                )
            ),
            None,
        )
        if conflicting_metric is not None:
            raise service_error(
                409,
                code="tagging_conflict",
                category="conflict",
                message=(
                    "The selected source parameter or designated metric is "
                    "already tagged to a different pairing."
                ),
            )

        return self._repository.apply_characterization_tagging(
            dataset_id,
            design_id,
            result_id,
            request,
        )

    def _require_visible_dataset(self, dataset_id: str) -> DatasetDetail:
        state = self._session_repository.get_session_state()
        dataset = self._repository.get_dataset(dataset_id)
        if dataset is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        if not self._authorization_service.is_visible_dataset(dataset, state):
            raise service_error(
                403,
                code="dataset_not_visible_in_workspace",
                category="permission_denied",
                message="The selected dataset is not visible in the active workspace.",
            )
        return DatasetDetail(
            **{
                **dataset.__dict__,
                "allowed_actions": self._allowed_actions(dataset, state),
            }
        )

    def _require_manageable_dataset(self, dataset_id: str) -> DatasetDetail:
        state = self._session_repository.get_session_state()
        dataset = self._repository.get_dataset(dataset_id)
        if dataset is None or dataset.lifecycle_state == "deleted":
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {dataset_id} was not found.",
            )
        if not self._is_dataset_manageable_in_context(dataset, state):
            raise service_error(
                403,
                code="dataset_not_visible_in_workspace",
                category="permission_denied",
                message="The selected dataset is not visible in the active workspace.",
            )
        return DatasetDetail(
            **{
                **dataset.__dict__,
                "allowed_actions": self._allowed_actions(dataset, state),
            }
        )

    def _visible_datasets(self, state: SessionState) -> list[DatasetDetail]:
        rows = [
            dataset
            for dataset in self._repository.list_dataset_details()
            if dataset.lifecycle_state != "deleted"
            if self._authorization_service.is_visible_dataset(dataset, state)
        ]
        return sorted(rows, key=lambda dataset: dataset.updated_at, reverse=True)

    def _allowed_actions(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> DatasetAllowedActions:
        return self._authorization_service.build_dataset_allowed_actions(dataset, state)

    def _current_design_row(
        self,
        dataset_id: str,
        design_id: str,
    ) -> DesignBrowseRow | None:
        design_rows = self._repository.list_designs(dataset_id)
        return next(
            (row for row in design_rows if row.design_id == design_id),
            None,
        )

    def _require_trace_mutation_policy(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        *,
        allow_update: bool,
        denied_code: str,
        denied_action: str,
    ) -> None:
        policy = self._repository.get_trace_mutation_policy(dataset_id, design_id, trace_id)
        if policy is None:
            raise service_error(
                404,
                code="trace_not_found",
                category="not_found",
                message="The requested trace is not available in the selected design scope.",
            )
        allowed = policy.update if allow_update else policy.delete
        if allowed:
            return
        raise service_error(
            409,
            code=denied_code,
            category="conflict",
            message=f"Trace {trace_id} cannot be {denied_action}. {policy.summary}",
        )

    def _updated_trace_fields(
        self,
        update: TraceUpdateDraft,
    ) -> list[str]:
        updated_fields: list[str] = []
        if update.parameter is not None:
            updated_fields.append("parameter")
        if update.representation is not None:
            updated_fields.append("representation")
        if update.provenance_summary is not None:
            updated_fields.append("provenance_summary")
        if update.axes is not None:
            updated_fields.append("axes")
        if update.preview_payload is not None:
            updated_fields.append("preview_payload")
        return updated_fields

    def _is_dataset_manageable_in_context(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> bool:
        if state.runtime_mode == "local":
            return (
                dataset.workspace_id == state.workspace_id
                and dataset.visibility_scope == "local"
            )
        if dataset.workspace_id != state.workspace_id:
            return False
        if dataset.visibility_scope == "workspace":
            return True
        if state.user is not None and state.user.platform_role == "admin":
            return True
        return dataset.owner_user_id == state.user.user_id if state.user is not None else False

    def _updated_fields(
        self,
        current: DatasetDetail,
        updated: DatasetDetail,
    ) -> tuple[DatasetProfileField, ...]:
        changed_fields: list[DatasetProfileField] = []
        if current.device_type != updated.device_type:
            changed_fields.append("device_type")
        if current.capabilities != updated.capabilities:
            changed_fields.append("capabilities")
        if current.source != updated.source:
            changed_fields.append("source")
        return tuple(changed_fields)

    def _with_allowed_actions(self, dataset: DatasetDetail, state: SessionState) -> DatasetDetail:
        return DatasetDetail(
            **{
                **dataset.__dict__,
                "allowed_actions": self._allowed_actions(dataset, state),
            }
        )

    def _catalog_row(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> DatasetCatalogRow:
        return DatasetCatalogRow(
            dataset_id=dataset.dataset_id,
            name=dataset.name,
            visibility_scope=dataset.visibility_scope,
            lifecycle_state=dataset.lifecycle_state,
            device_type=dataset.device_type,
            updated_at=dataset.updated_at,
            allowed_actions=self._allowed_actions(dataset, state),
            family=dataset.family,
            owner_display_name=dataset.owner,
        )

    def _can_manage_datasets(self, state: SessionState) -> bool:
        if state.runtime_mode == "local":
            return True
        return self._authorization_service.build_session_capabilities(state).can_manage_datasets

    def _append_audit_record(
        self,
        *,
        state: SessionState,
        action_kind: str,
        dataset: DatasetDetail,
        payload: dict[str, object],
    ) -> None:
        if self._audit_repository is None:
            return
        self._audit_repository.append(
            build_audit_record(
                state=state,
                action_kind=action_kind,
                resource_kind="dataset",
                resource_id=dataset.dataset_id,
                outcome="completed",
                payload=payload,
                workspace_id=dataset.workspace_id,
            )
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
