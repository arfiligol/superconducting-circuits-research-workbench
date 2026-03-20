"""Explicit intermediate representation for Schematic Netlist compilation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CircuitElement:
    """Lowered internal element representation for preview and compilation."""

    name: str
    kind: str
    node1: str
    node2: str
    value_ref: str | int
    role: str | None = None

    @property
    def is_port(self) -> bool:
        return self.kind == "port"

    @property
    def is_mutual_coupling(self) -> bool:
        return self.kind == "mutual_coupling"


@dataclass(frozen=True)
class CircuitIR:
    """Stable internal representation between parsing and downstream compilers."""

    circuit_name: str
    layout_direction: str
    layout_profile: str
    available_port_indices: tuple[int, ...]
    elements: tuple[CircuitElement, ...]

    def lowered_elements(self) -> list[CircuitElement]:
        """Return a list copy for legacy consumers."""
        return list(self.elements)
