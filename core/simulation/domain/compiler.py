"""Simulation compiler services for lowering CircuitIR into backend tuples."""

from __future__ import annotations

from collections.abc import Callable

from core.simulation.domain.ir import CircuitIR


def compile_simulation_topology(
    circuit_ir: CircuitIR,
    *,
    is_ground_node: Callable[[str], bool],
) -> list[tuple[str, str, str, str | int]]:
    """Lower CircuitIR into the legacy tuple representation used by Julia."""
    numeric_nodes: dict[str, str] = {}

    def to_sim_node(token: str) -> str:
        if is_ground_node(token):
            return "0"
        if token not in numeric_nodes:
            numeric_nodes[token] = str(len(numeric_nodes) + 1)
        return numeric_nodes[token]

    lowered: list[tuple[str, str, str, str | int]] = []
    for element in circuit_ir.elements:
        if element.kind == "mutual_coupling":
            node1 = str(element.node1)
            node2 = str(element.node2)
        else:
            node1 = to_sim_node(element.node1)
            node2 = to_sim_node(element.node2)
        lowered.append((element.name, node1, node2, element.value_ref))
    return lowered
