from __future__ import annotations

from app_backend.services.simulation_result_explorer_models import (
    ExplorerSelectionRequest,
)
from app_backend.services.simulation_result_explorer_query_service import (
    SimulationResultExplorerQueryService,
)
from app_backend.services.simulation_result_explorer_view_service import (
    SimulationResultExplorerViewService,
    build_base_payload,
    build_result_basis_payload,
)


class SimulationResultExplorerService:
    def __init__(
        self,
        query_service: SimulationResultExplorerQueryService,
        view_service: SimulationResultExplorerViewService,
    ) -> None:
        self._query_service = query_service
        self._view_service = view_service

    def get_bootstrap_payload(self, task_id: int) -> dict[str, object]:
        context = self._query_service.build_context(task_id)
        payload = build_base_payload(context)
        payload["bootstrap"] = self._view_service.build_bootstrap_payload(context)
        payload["result_basis"] = build_result_basis_payload(context)
        return payload

    def get_view_payload(
        self,
        task_id: int,
        selection_request: ExplorerSelectionRequest,
    ) -> dict[str, object]:
        context = self._query_service.build_context(task_id)
        payload = build_base_payload(context)
        payload.update(
            self._view_service.build_view_payload(
                context=context,
                selection=self._query_service.resolve_selection(
                    context=context,
                    selection_request=selection_request,
                ),
            )
        )
        return payload

    def get_explorer_payload(
        self,
        task_id: int,
        selection_request: ExplorerSelectionRequest,
    ) -> dict[str, object]:
        context = self._query_service.build_context(task_id)
        payload = build_base_payload(context)
        payload["bootstrap"] = self._view_service.build_bootstrap_payload(context)
        payload["result_basis"] = build_result_basis_payload(context)
        payload.update(
            self._view_service.build_view_payload(
                context=context,
                selection=self._query_service.resolve_selection(
                    context=context,
                    selection_request=selection_request,
                ),
            )
        )
        return payload
