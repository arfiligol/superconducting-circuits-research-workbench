"""Shared support helpers for persisted post-processing execution."""

from __future__ import annotations

from collections.abc import Mapping

from core.simulation.application.post_processing import (
    compensate_simulation_result_port_terminations,
)
from core.simulation.application.run_simulation import (
    SimulationSweepPointResult,
    SimulationSweepRun,
    simulation_sweep_run_from_payload,
    simulation_sweep_run_to_payload,
)
from core.simulation.application.trace_architecture import (
    is_trace_batch_bundle_payload,
    load_raw_simulation_bundle,
)
from core.simulation.domain.circuit import CircuitDefinition, SimulationResult


def port_signal_node_map(circuit_definition: CircuitDefinition) -> dict[int, str]:
    """Map each declared port index to its non-ground signal node."""
    mapping: dict[int, str] = {}
    for row in circuit_definition.expanded_definition.topology:
        if not row.is_port:
            continue
        try:
            port_index = int(row.value_ref)
        except Exception:
            continue
        if circuit_definition.is_ground_node(row.node1) and not circuit_definition.is_ground_node(
            row.node2
        ):
            mapping[port_index] = str(row.node2)
            continue
        if circuit_definition.is_ground_node(row.node2) and not circuit_definition.is_ground_node(
            row.node1
        ):
            mapping[port_index] = str(row.node1)
    return mapping


def estimate_port_ground_cap_weights(
    circuit_definition: CircuitDefinition,
    *,
    port_a: int,
    port_b: int,
) -> tuple[float, float] | None:
    """Estimate electrical-centroid weights from capacitor-to-ground totals."""
    port_nodes = port_signal_node_map(circuit_definition)
    node_a = port_nodes.get(port_a)
    node_b = port_nodes.get(port_b)
    if node_a is None or node_b is None:
        return None

    cap_to_ground: dict[str, float] = {node_a: 0.0, node_b: 0.0}
    for element in circuit_definition.to_ir().elements:
        if element.kind != "capacitor" or element.is_port or element.is_mutual_coupling:
            continue
        if not isinstance(element.value_ref, str):
            continue
        if circuit_definition.is_ground_node(element.node1) and str(element.node2) in cap_to_ground:
            cap_to_ground[str(element.node2)] += circuit_definition.resolve_component_value(
                element.value_ref
            )
        elif (
            circuit_definition.is_ground_node(element.node2) and str(element.node1) in cap_to_ground
        ):
            cap_to_ground[str(element.node1)] += circuit_definition.resolve_component_value(
                element.value_ref
            )

    weight_a = cap_to_ground[node_a]
    weight_b = cap_to_ground[node_b]
    total = weight_a + weight_b
    if total <= 0:
        return None
    return (weight_a / total, weight_b / total)


def build_compensated_simulation_sweep_payload(
    sweep_payload: Mapping[str, object],
    *,
    resistance_ohm_by_port: Mapping[int, float],
    reference_impedance_ohm: float,
) -> dict[str, object]:
    """Apply port-termination compensation point-wise across one sweep payload."""
    sweep_run = simulation_sweep_run_from_payload(dict(sweep_payload))
    compensated_points = tuple(
        SimulationSweepPointResult(
            point_index=int(point.point_index),
            axis_indices=tuple(int(index) for index in point.axis_indices),
            axis_values={
                str(target_value_ref): float(value)
                for target_value_ref, value in point.axis_values.items()
            },
            result=compensate_simulation_result_port_terminations(
                point.result,
                resistance_ohm_by_port={
                    int(port): float(value) for port, value in resistance_ohm_by_port.items()
                },
                reference_impedance_ohm=reference_impedance_ohm,
            ),
        )
        for point in sweep_run.points
    )
    return simulation_sweep_run_to_payload(
        SimulationSweepRun(
            axes=tuple(sweep_run.axes),
            points=compensated_points,
            representative_point_index=int(sweep_run.representative_point_index),
        )
    )


def extract_compensated_post_processing_payload(
    *,
    source_payload: Mapping[str, object],
    input_source: str,
    reference_impedance_ohm: float,
    resistance_ohm_by_port: Mapping[int, float] | None,
) -> tuple[dict[str, object], str]:
    """Resolve the canonical payload used by post-processing execution."""
    if str(input_source).strip() != "ptc_y":
        return (dict(source_payload), "persisted_trace_batch")

    normalized_resistances = {
        int(port): float(value) for port, value in (resistance_ohm_by_port or {}).items()
    }
    if not normalized_resistances:
        return (dict(source_payload), "persisted_trace_batch")

    if is_trace_batch_bundle_payload(source_payload):
        raw_result, sweep_payload = load_raw_simulation_bundle(source_payload)
        if isinstance(sweep_payload, Mapping):
            return (
                build_compensated_simulation_sweep_payload(
                    sweep_payload,
                    resistance_ohm_by_port=normalized_resistances,
                    reference_impedance_ohm=reference_impedance_ohm,
                ),
                "persisted_trace_batch_ptc_overlay",
            )
        return (
            compensate_simulation_result_port_terminations(
                raw_result,
                resistance_ohm_by_port=normalized_resistances,
                reference_impedance_ohm=reference_impedance_ohm,
            ).model_dump(mode="json"),
            "persisted_trace_batch_ptc_overlay",
        )

    result = SimulationResult.model_validate(dict(source_payload))
    return (
        compensate_simulation_result_port_terminations(
            result,
            resistance_ohm_by_port=normalized_resistances,
            reference_impedance_ohm=reference_impedance_ohm,
        ).model_dump(mode="json"),
        "persisted_trace_batch_ptc_overlay",
    )
