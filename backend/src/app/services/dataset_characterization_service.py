from collections.abc import Sequence
from typing import Protocol

from src.app.domain.characterization_analysis import (
    build_characterization_registry_rows,
    derive_characterization_analysis_ids,
    project_legacy_characterization_registry_rows,
)
from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryQuery,
    CharacterizationAnalysisRegistryResult,
    CharacterizationAnalysisRegistryRow,
    CharacterizationArtifactPayload,
    CharacterizationArtifactPayloadQuery,
    CharacterizationInputResultRef,
    CharacterizationResultBrowseQuery,
    CharacterizationResultDetail,
    CharacterizationResultSummary,
    CharacterizationRunHistoryQuery,
    CharacterizationRunHistoryRow,
    CharacterizationTaggingRequest,
    CharacterizationTaggingResult,
    DatasetDetail,
    TaggedCoreMetricSummary,
    TraceDetail,
    TraceMetadataSummary,
)
from src.app.domain.session import SessionState
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error
from src.app.services.trace_collection_service import TraceCollectionService


class DatasetCharacterizationRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def list_tagged_core_metrics(
        self,
        dataset_id: str,
    ) -> Sequence[TaggedCoreMetricSummary]: ...

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

    def get_characterization_artifact_payload(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        artifact_id: str,
        query: CharacterizationArtifactPayloadQuery,
    ) -> CharacterizationArtifactPayload | None: ...

    def apply_characterization_tagging(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        request: CharacterizationTaggingRequest,
    ) -> CharacterizationTaggingResult: ...


class DatasetCharacterizationSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class DatasetCharacterizationService:
    def __init__(
        self,
        repository: DatasetCharacterizationRepository,
        session_repository: DatasetCharacterizationSessionRepository,
        authorization_service: AuthorizationService | None = None,
        trace_collection_service: TraceCollectionService | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._trace_collection_service = trace_collection_service or TraceCollectionService()

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
    ) -> CharacterizationAnalysisRegistryResult:
        self._require_visible_dataset(dataset_id)
        trace_rows = tuple(self._repository.list_trace_metadata(dataset_id, design_id))
        upstream_results = self._available_upstream_results(
            dataset_id=dataset_id,
            design_id=design_id,
        )
        input_collection_payload = self._derive_input_collection_payload(
            dataset_id=dataset_id,
            design_id=design_id,
            selected_trace_ids=query.selected_trace_ids,
        )
        if len(trace_rows) == 0 or all(
            len(trace.analysis_capabilities) == 0 for trace in trace_rows
        ):
            rows = tuple(
                project_legacy_characterization_registry_rows(
                    legacy_rows=tuple(
                        self._repository.list_characterization_analysis_registry(
                            dataset_id,
                            design_id,
                        )
                    ),
                    selected_trace_ids=query.selected_trace_ids,
                    upstream_results_by_analysis_id=upstream_results,
                    enforce_runtime_support=True,
                )
            )
            return CharacterizationAnalysisRegistryResult(
                rows=rows,
                input_collection_payload=input_collection_payload,
                data_collection_review=self._derive_collection_review(
                    dataset_id=dataset_id,
                    design_id=design_id,
                    selected_trace_ids=query.selected_trace_ids,
                    rows=rows,
                ),
            )
        included_analysis_ids = derive_characterization_analysis_ids(trace_rows)
        rows = tuple(
            build_characterization_registry_rows(
                included_analysis_ids=included_analysis_ids,
                traces=trace_rows,
                selected_trace_ids=query.selected_trace_ids,
                upstream_results_by_analysis_id=upstream_results,
                enforce_runtime_support=True,
            )
        )
        return CharacterizationAnalysisRegistryResult(
            rows=rows,
            input_collection_payload=input_collection_payload,
            data_collection_review=self._derive_collection_review(
                dataset_id=dataset_id,
                design_id=design_id,
                selected_trace_ids=query.selected_trace_ids,
                rows=rows,
            ),
        )

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

    def get_characterization_artifact_payload(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        artifact_id: str,
        query: CharacterizationArtifactPayloadQuery,
    ) -> CharacterizationArtifactPayload:
        self._require_visible_dataset(dataset_id)
        payload = self._repository.get_characterization_artifact_payload(
            dataset_id,
            design_id,
            result_id,
            artifact_id,
            query,
        )
        if payload is None:
            raise service_error(
                404,
                code="artifact_not_found",
                category="not_found",
                message=(
                    "The requested characterization artifact is not available "
                    "for the selected persisted result."
                ),
            )
        return payload

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
        return dataset

    def _derive_input_collection_payload(
        self,
        *,
        dataset_id: str,
        design_id: str,
        selected_trace_ids: tuple[str, ...],
    ):
        if len(selected_trace_ids) == 0:
            return None
        trace_details = []
        for trace_id in selected_trace_ids:
            detail = self._repository.get_trace_detail(dataset_id, design_id, trace_id)
            if detail is None:
                return None
            trace_details.append(detail)
        return self._trace_collection_service.derive_input_collection_payload_from_trace_details(
            tuple(trace_details)
        )

    def _derive_collection_review(
        self,
        *,
        dataset_id: str,
        design_id: str,
        selected_trace_ids: tuple[str, ...],
        rows: tuple[CharacterizationAnalysisRegistryRow, ...],
    ):
        if len(selected_trace_ids) == 0:
            return None
        trace_details: list[TraceDetail] = []
        for trace_id in selected_trace_ids:
            detail = self._repository.get_trace_detail(dataset_id, design_id, trace_id)
            if detail is None:
                return None
            trace_details.append(detail)
        return self._trace_collection_service.derive_data_collection_review_from_trace_details(
            tuple(trace_details),
            rows,
        )

    def _available_upstream_results(
        self,
        *,
        dataset_id: str,
        design_id: str,
    ) -> dict[str, tuple[CharacterizationInputResultRef, ...]]:
        summaries = tuple(self._repository.list_characterization_results(dataset_id, design_id))
        run_history = tuple(
            self._repository.list_characterization_run_history(dataset_id, design_id)
        )
        run_ids_by_result_id = {
            row.result_id: row.run_id
            for row in run_history
            if row.result_id is not None
        }
        refs_by_analysis_id: dict[str, list[CharacterizationInputResultRef]] = {}
        for summary in summaries:
            if summary.status != "completed":
                continue
            refs_by_analysis_id.setdefault(summary.analysis_id, []).append(
                CharacterizationInputResultRef(
                    analysis_id=summary.analysis_id,
                    result_id=summary.result_id,
                    run_id=run_ids_by_result_id.get(summary.result_id),
                    title=summary.title,
                )
            )
        return {
            analysis_id: tuple(refs)
            for analysis_id, refs in refs_by_analysis_id.items()
        }
