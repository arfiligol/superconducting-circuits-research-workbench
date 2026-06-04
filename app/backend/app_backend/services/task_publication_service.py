from __future__ import annotations

from app_backend.domain.datasets import (
    ResultTracePublicationDraft,
    ResultTracePublicationResult,
    SimulationResultPublicationDraft,
    SimulationResultPublicationResult,
)
from app_backend.services.result_trace_publication_service import (
    ResultTracePublicationHost,
    ResultTracePublicationService,
)
from app_backend.services.simulation_result_publication_service import (
    SimulationResultPublicationHost,
    SimulationResultPublicationService,
)


class TaskPublicationService:
    def __init__(
        self,
        simulation_result_service: SimulationResultPublicationService,
        result_trace_service: ResultTracePublicationService,
    ) -> None:
        self._simulation_result_service = simulation_result_service
        self._result_trace_service = result_trace_service

    def publish_simulation_result(
        self,
        task_id: int,
        draft: SimulationResultPublicationDraft,
        *,
        dataset_id: str | None,
        host: SimulationResultPublicationHost,
    ) -> SimulationResultPublicationResult:
        return self._simulation_result_service.publish_simulation_result(
            task_id,
            draft,
            dataset_id=dataset_id,
            host=host,
        )

    def publish_result_trace(
        self,
        task_id: int,
        draft: ResultTracePublicationDraft,
        *,
        host: ResultTracePublicationHost,
    ) -> ResultTracePublicationResult:
        return self._result_trace_service.publish_result_trace(
            task_id,
            draft,
            host=host,
        )
