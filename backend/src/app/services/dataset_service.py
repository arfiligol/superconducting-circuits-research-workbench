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
    DatasetDetail,
    DatasetProfileField,
    DatasetProfileUpdate,
    DatasetProfileUpdateResult,
    DesignBrowseQuery,
    DesignBrowseRow,
    TaggedCoreMetricSummary,
    TraceBrowseQuery,
    TraceDetail,
    TraceMetadataSummary,
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

    def update_dataset_profile(
        self,
        dataset_id: str,
        update: DatasetProfileUpdate,
    ) -> DatasetDetail | None: ...

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

    def _visible_datasets(self, state: SessionState) -> list[DatasetDetail]:
        rows = [
            dataset
            for dataset in self._repository.list_dataset_details()
            if self._authorization_service.is_visible_dataset(dataset, state)
        ]
        return sorted(rows, key=lambda dataset: dataset.updated_at, reverse=True)

    def _allowed_actions(
        self,
        dataset: DatasetDetail,
        state: SessionState,
    ) -> DatasetAllowedActions:
        return self._authorization_service.build_dataset_allowed_actions(dataset, state)

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
