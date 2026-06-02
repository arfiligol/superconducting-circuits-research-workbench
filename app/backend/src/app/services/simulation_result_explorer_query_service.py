from __future__ import annotations

from src.app.domain.tasks import SimulationSetup, TaskDetail
from src.app.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    port_options_for_task,
)
from src.app.services.service_errors import service_error
from src.app.services.simulation_result_explorer_models import (
    FAMILY_LABELS,
    FAMILY_METRICS,
    ExplorerContext,
    ExplorerSelectionRequest,
    ResolvedSelection,
)
from src.app.services.simulation_result_explorer_selection import (
    default_compare_axis_index,
    default_sweep_index,
    resolve_compare_axis_index,
    validate_sweep_index,
)
from src.app.services.task_service import TaskService


class SimulationResultExplorerQueryService:
    def __init__(self, task_service: TaskService) -> None:
        self._task_service = task_service

    def build_context(self, task_id: int) -> ExplorerContext:
        explorer_task = self._task_service.get_task(task_id)
        self._ensure_task_ready_for_explorer(explorer_task)
        basis_task = self._resolve_basis_task(explorer_task)
        definition = self._task_service.get_circuit_definition(basis_task.definition_id)
        port_options = port_options_for_task(
            explorer_task,
            basis_task=basis_task,
            definition=definition,
        )
        return ExplorerContext(
            explorer_task=explorer_task,
            basis_task=basis_task,
            port_options=port_options,
            default_selection=_default_selection(
                explorer_task,
                basis_task=basis_task,
                port_options=port_options,
            ),
        )

    def resolve_selection(
        self,
        *,
        context: ExplorerContext,
        selection_request: ExplorerSelectionRequest,
    ) -> ResolvedSelection:
        resolved_family = selection_request.family or str(context.default_selection["family"])
        if resolved_family not in _available_families_for_task(context.explorer_task):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="family is not available for this persisted result.",
            )
        sources = _available_sources_for_task(context.explorer_task, resolved_family)
        resolved_source = selection_request.source or str(context.default_selection["source"])
        if resolved_source not in sources:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=f"source {resolved_source} is not available for family {resolved_family}.",
            )
        metric_options = FAMILY_METRICS[resolved_family]
        resolved_metric = selection_request.metric or str(context.default_selection["metric"])
        if resolved_metric not in metric_options:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=f"metric {resolved_metric} is not available for family {resolved_family}.",
            )
        resolved_sweep_index = (
            selection_request.sweep_index
            if selection_request.sweep_index is not None
            else (
                int(context.default_selection["sweep_index"])
                if context.default_selection.get("sweep_index") is not None
                else None
            )
        )
        basis_setup = context.basis_task.simulation_setup
        _validate_sweep_index(basis_setup, resolved_sweep_index)
        resolved_compare_axis_index = resolve_compare_axis_index(
            basis_setup,
            selection_request.compare_axis_index
            if selection_request.compare_axis_index is not None
            else (
                int(context.default_selection["compare_axis_index"])
                if context.default_selection.get("compare_axis_index") is not None
                else None
            ),
        )
        resolved_z0 = float(
            selection_request.z0_ohm
            if selection_request.z0_ohm is not None
            else context.default_selection["z0_ohm"]
        )
        if resolved_z0 <= 0:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="z0 must be positive.",
            )
        resolved_output_port = (
            selection_request.output_port or int(context.default_selection["output_port"])
        )
        resolved_input_port = (
            selection_request.input_port or int(context.default_selection["input_port"])
        )
        if (
            resolved_output_port not in context.port_options
            or resolved_input_port not in context.port_options
        ):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=(
                    "Requested trace selection ports are not available for this "
                    "simulation result."
                ),
            )
        return ResolvedSelection(
            family=resolved_family,
            source=resolved_source,
            metric=resolved_metric,
            sweep_index=resolved_sweep_index,
            compare_axis_index=resolved_compare_axis_index,
            z0_ohm=resolved_z0,
            output_port=resolved_output_port,
            input_port=resolved_input_port,
        )

    def _ensure_task_ready_for_explorer(self, task: TaskDetail) -> None:
        if task.kind not in {"simulation", "post_processing"}:
            raise service_error(
                409,
                code="simulation_result_explorer_task_invalid",
                category="conflict",
                message=(
                    "Simulation result explorer only supports simulation and post-processing tasks."
                ),
            )
        if task.status in {"failed", "cancelled", "terminated"}:
            raise service_error(
                409,
                code="simulation_result_explorer_unavailable",
                category="conflict",
                message="Simulation result explorer is unavailable for terminal non-success tasks.",
            )
        handoff = self._task_service.get_task_result_handoff(task.task_id)
        if handoff.availability != "ready":
            raise service_error(
                409,
                code="simulation_result_explorer_not_ready",
                category="conflict",
                message="Simulation results are not available for explorer access yet.",
            )
        if task.kind == "simulation" and task.simulation_setup is None:
            raise service_error(
                409,
                code="simulation_result_explorer_setup_missing",
                category="conflict",
                message="Simulation result explorer requires persisted simulation_setup.",
            )

    def _resolve_basis_task(self, task: TaskDetail) -> TaskDetail:
        if task.kind == "simulation":
            if task.simulation_setup is None:
                raise service_error(
                    409,
                    code="simulation_result_explorer_setup_missing",
                    category="conflict",
                    message="Simulation result explorer requires persisted simulation_setup.",
                )
            return task

        if task.upstream_task_id is None:
            raise service_error(
                409,
                code="simulation_result_explorer_upstream_missing",
                category="conflict",
                message="Post-processing explorer requires an upstream simulation task.",
            )

        upstream_task = self._task_service.get_task(task.upstream_task_id)
        if upstream_task.kind != "simulation" or upstream_task.simulation_setup is None:
            raise service_error(
                409,
                code="simulation_result_explorer_upstream_invalid",
                category="conflict",
                message="Post-processing explorer requires a persisted upstream simulation result.",
            )
        return upstream_task
def _default_selection(
    task: TaskDetail,
    *,
    basis_task: TaskDetail,
    port_options: dict[int, str],
) -> dict[str, object]:
    default_port = min(port_options) if len(port_options) > 0 else 1
    basis_setup = basis_task.simulation_setup
    default_sweep_index_value = (
        default_sweep_index(basis_setup) if basis_setup is not None else None
    )
    default_compare_axis_index_value = (
        default_compare_axis_index(basis_setup) if basis_setup is not None else None
    )
    if task.kind == "post_processing" and task.post_processing_setup is not None:
        selection = (
            task.post_processing_setup.selections[0]
            if task.post_processing_setup.selections
            else None
        )
        if selection is not None:
            family = (
                selection.trace_family
                if selection.trace_family in FAMILY_LABELS
                else "s_matrix"
            )
            available_sources = _available_sources_for_task(task, family)
            return {
                "family": family,
                "source": available_sources[0],
                "metric": _metric_from_post_processing_representation(
                    family,
                    selection.representation,
                ),
                "sweep_index": default_sweep_index_value,
                "compare_axis_index": default_compare_axis_index_value,
                "z0_ohm": 50.0,
                "output_port": default_port,
                "input_port": default_port,
            }

    return {
        "family": "s_matrix",
        "source": "raw",
        "metric": "magnitude_db",
        "sweep_index": default_sweep_index_value,
        "compare_axis_index": default_compare_axis_index_value,
        "z0_ohm": 50.0,
        "output_port": default_port,
        "input_port": default_port,
    }


def _metric_from_post_processing_representation(family: str, representation: str) -> str:
    normalized = representation.strip().lower()
    if normalized in {"imag", "imaginary"}:
        candidate = "imag"
    elif normalized == "real":
        candidate = "real"
    elif normalized == "phase":
        candidate = "phase_deg"
    elif normalized in {"db", "magnitude_db", "magnitude"}:
        candidate = "magnitude_db" if family == "s_matrix" else "magnitude"
    else:
        candidate = "magnitude_db" if family == "s_matrix" else "magnitude"

    if candidate in FAMILY_METRICS[family]:
        return candidate
    return next(iter(FAMILY_METRICS[family]))


def _available_families_for_task(task: TaskDetail) -> tuple[str, ...]:
    return tuple(
        family
        for family in ("s_matrix", "y_matrix", "z_matrix")
        if len(_available_sources_for_task(task, family)) > 0
    )


def _available_sources_for_task(task: TaskDetail, family: str) -> tuple[str, ...]:
    return available_sources_for_task_family(task, family)


def _validate_sweep_index(setup: SimulationSetup, sweep_index: int | None) -> None:
    validate_sweep_index(setup, sweep_index)
