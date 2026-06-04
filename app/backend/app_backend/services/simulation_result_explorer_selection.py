from __future__ import annotations

from collections.abc import Mapping

from app_backend.domain.tasks import SimulationSetup
from app_backend.services.service_errors import service_error
from app_backend.services.simulation_result_explorer_models import ResolvedSelection


def default_selection_trace_key(default_selection: Mapping[str, object]) -> str:
    return _resolved_selection_from_mapping(default_selection).trace_key


def serialize_parameter_sweep_bootstrap(
    setup: SimulationSetup,
    *,
    sweep_index: int | None,
    compare_axis_index: int | None,
) -> dict[str, object]:
    coordinates = decode_sweep_index(setup, sweep_index)
    axes: list[dict[str, object]] = []
    for axis_index, sweep in enumerate(setup.parameter_sweeps):
        axes.append(
            {
                "parameter": sweep.parameter,
                "label": sweep.parameter,
                "unit": sweep.unit,
                "values": [float(value) for value in sweep.values],
                "selected_value_index": (
                    coordinates[axis_index] if axis_index < len(coordinates) else 0
                ),
            }
        )
    return {
        "axes": axes,
        "point_count": sweep_point_count(setup),
        "active": len(axes) > 0,
        "compare_axis_index": compare_axis_index,
    }


def default_sweep_index(setup: SimulationSetup) -> int | None:
    return 0 if len(setup.parameter_sweeps) > 0 else None


def default_compare_axis_index(setup: SimulationSetup) -> int | None:
    return 0 if len(setup.parameter_sweeps) > 0 else None


def sweep_point_count(setup: SimulationSetup) -> int:
    if len(setup.parameter_sweeps) == 0:
        return 1
    total = 1
    for sweep in setup.parameter_sweeps:
        total *= max(len(sweep.values), 1)
    return total


def validate_sweep_index(setup: SimulationSetup, sweep_index: int | None) -> None:
    if len(setup.parameter_sweeps) == 0:
        if sweep_index not in {None, 0}:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="sweep_index is not available for this persisted result.",
            )
        return

    if sweep_index is None or sweep_index < 0 or sweep_index >= sweep_point_count(setup):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="sweep_index is outside the available parameter sweep range.",
        )


def resolve_compare_axis_index(
    setup: SimulationSetup,
    compare_axis_index: int | None,
) -> int | None:
    if len(setup.parameter_sweeps) == 0:
        if compare_axis_index is not None:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="compare_axis_index is not available for this persisted result.",
            )
        return None

    resolved_index = compare_axis_index if compare_axis_index is not None else 0
    if resolved_index < 0 or resolved_index >= len(setup.parameter_sweeps):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="compare_axis_index is outside the available parameter sweep range.",
        )
    return resolved_index


def decode_sweep_index(setup: SimulationSetup, sweep_index: int | None) -> tuple[int, ...]:
    if len(setup.parameter_sweeps) == 0:
        return ()

    resolved_index = sweep_index if sweep_index is not None else 0
    remaining = resolved_index
    coordinates = [0] * len(setup.parameter_sweeps)
    for axis_index in range(len(setup.parameter_sweeps) - 1, -1, -1):
        axis_size = max(len(setup.parameter_sweeps[axis_index].values), 1)
        coordinates[axis_index] = remaining % axis_size
        remaining //= axis_size
    return tuple(coordinates)


def encode_sweep_index(
    setup: SimulationSetup,
    coordinates: tuple[int, ...],
) -> int | None:
    if len(setup.parameter_sweeps) == 0:
        return None

    encoded = 0
    for axis_index, sweep in enumerate(setup.parameter_sweeps):
        axis_size = max(len(sweep.values), 1)
        coordinate = coordinates[axis_index] if axis_index < len(coordinates) else 0
        coordinate = min(max(coordinate, 0), axis_size - 1)
        encoded = (encoded * axis_size) + coordinate
    return encoded


def replace_sweep_index(
    selection: ResolvedSelection,
    sweep_index: int | None,
) -> ResolvedSelection:
    return ResolvedSelection(
        family=selection.family,
        source=selection.source,
        metric=selection.metric,
        sweep_index=sweep_index,
        compare_axis_index=selection.compare_axis_index,
        z0_ohm=selection.z0_ohm,
        output_port=selection.output_port,
        input_port=selection.input_port,
    )


def _resolved_selection_from_mapping(selection: Mapping[str, object]) -> ResolvedSelection:
    return ResolvedSelection(
        family=str(selection["family"]),
        source=str(selection["source"]),
        metric=str(selection["metric"]),
        sweep_index=(
            int(selection["sweep_index"]) if selection.get("sweep_index") is not None else None
        ),
        compare_axis_index=(
            int(selection["compare_axis_index"])
            if selection.get("compare_axis_index") is not None
            else None
        ),
        z0_ohm=float(selection["z0_ohm"]),
        output_port=int(selection["output_port"]),
        input_port=int(selection["input_port"]),
    )
