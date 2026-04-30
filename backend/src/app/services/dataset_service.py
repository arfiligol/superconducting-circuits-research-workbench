from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryQuery,
    CharacterizationArtifactPayloadQuery,
    CharacterizationResultBrowseQuery,
    CharacterizationRunHistoryQuery,
    CharacterizationTaggingRequest,
    DatasetCreateDraft,
    DatasetLifecycleMutationResult,
    DatasetProfileUpdate,
    DatasetProfileUpdateResult,
    DesignBrowseQuery,
    DesignCreateDraft,
    DesignMergeDraft,
    DesignRenameDraft,
    RawDataIngestionDraft,
    RawDataIngestionResult,
    TraceBrowseQuery,
    TraceDeleteResult,
    TraceUpdateDraft,
)
from src.app.services.dataset_catalog_service import DatasetCatalogService
from src.app.services.dataset_characterization_service import (
    DatasetCharacterizationService,
)
from src.app.services.dataset_trace_service import DatasetTraceService


class DatasetService:
    def __init__(
        self,
        catalog_service: DatasetCatalogService,
        trace_service: DatasetTraceService,
        characterization_service: DatasetCharacterizationService,
    ) -> None:
        self._catalog_service = catalog_service
        self._trace_service = trace_service
        self._characterization_service = characterization_service

    def list_dataset_catalog(self):
        return self._catalog_service.list_dataset_catalog()

    def create_dataset(self, draft: DatasetCreateDraft) -> DatasetLifecycleMutationResult:
        return self._catalog_service.create_dataset(draft)

    def get_dataset_profile(self, dataset_id: str):
        return self._catalog_service.get_dataset_profile(dataset_id)

    def update_dataset_profile(
        self,
        dataset_id: str,
        update: DatasetProfileUpdate,
    ) -> DatasetProfileUpdateResult:
        return self._catalog_service.update_dataset_profile(dataset_id, update)

    def archive_dataset(self, dataset_id: str) -> DatasetLifecycleMutationResult:
        return self._catalog_service.archive_dataset(dataset_id)

    def delete_dataset(self, dataset_id: str) -> DatasetLifecycleMutationResult:
        return self._catalog_service.delete_dataset(dataset_id)

    def ingest_raw_data(
        self,
        dataset_id: str,
        draft: RawDataIngestionDraft,
    ) -> RawDataIngestionResult:
        return self._catalog_service.ingest_raw_data(dataset_id, draft)

    def create_design(
        self,
        dataset_id: str,
        draft: DesignCreateDraft,
    ):
        return self._catalog_service.create_design(dataset_id, draft)

    def rename_design(
        self,
        dataset_id: str,
        design_id: str,
        draft: DesignRenameDraft,
    ):
        return self._catalog_service.rename_design(dataset_id, design_id, draft)

    def archive_design(self, dataset_id: str, design_id: str):
        return self._catalog_service.archive_design(dataset_id, design_id)

    def delete_design(self, dataset_id: str, design_id: str):
        return self._catalog_service.delete_design(dataset_id, design_id)

    def merge_design_scopes(
        self,
        dataset_id: str,
        source_design_id: str,
        draft: DesignMergeDraft,
    ):
        return self._catalog_service.merge_design_scopes(dataset_id, source_design_id, draft)

    def list_tagged_core_metrics(self, dataset_id: str):
        return self._catalog_service.list_tagged_core_metrics(dataset_id)

    def list_designs(
        self,
        dataset_id: str,
        query: DesignBrowseQuery,
    ):
        return self._catalog_service.list_designs(dataset_id, query)

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
        query: TraceBrowseQuery,
    ):
        return self._trace_service.list_trace_metadata(dataset_id, design_id, query)

    def get_trace_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ):
        return self._trace_service.get_trace_detail(dataset_id, design_id, trace_id)

    def get_trace_edit_detail(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ):
        return self._trace_service.get_trace_edit_detail(dataset_id, design_id, trace_id)

    def update_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
        update: TraceUpdateDraft,
    ):
        return self._trace_service.update_trace(dataset_id, design_id, trace_id, update)

    def delete_trace(
        self,
        dataset_id: str,
        design_id: str,
        trace_id: str,
    ) -> TraceDeleteResult:
        return self._trace_service.delete_trace(dataset_id, design_id, trace_id)

    def delete_traces(
        self,
        dataset_id: str,
        design_id: str,
        trace_ids: tuple[str, ...],
    ) -> TraceDeleteResult:
        return self._trace_service.delete_traces(dataset_id, design_id, trace_ids)

    def list_characterization_results(
        self,
        dataset_id: str,
        design_id: str,
        query: CharacterizationResultBrowseQuery,
    ):
        return self._characterization_service.list_characterization_results(
            dataset_id,
            design_id,
            query,
        )

    def list_characterization_analysis_registry(
        self,
        dataset_id: str,
        design_id: str,
        query: CharacterizationAnalysisRegistryQuery,
    ):
        return self._characterization_service.list_characterization_analysis_registry(
            dataset_id,
            design_id,
            query,
        )

    def list_characterization_run_history(
        self,
        dataset_id: str,
        design_id: str,
        query: CharacterizationRunHistoryQuery,
    ):
        return self._characterization_service.list_characterization_run_history(
            dataset_id,
            design_id,
            query,
        )

    def get_characterization_result(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
    ):
        return self._characterization_service.get_characterization_result(
            dataset_id,
            design_id,
            result_id,
        )

    def get_characterization_artifact_payload(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        artifact_id: str,
        query: CharacterizationArtifactPayloadQuery,
    ):
        return self._characterization_service.get_characterization_artifact_payload(
            dataset_id,
            design_id,
            result_id,
            artifact_id,
            query,
        )

    def apply_characterization_tagging(
        self,
        dataset_id: str,
        design_id: str,
        result_id: str,
        request: CharacterizationTaggingRequest,
    ):
        return self._characterization_service.apply_characterization_tagging(
            dataset_id,
            design_id,
            result_id,
            request,
        )
