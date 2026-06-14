from __future__ import annotations

from typing import ClassVar, Protocol

AnchorPoint = tuple[float, float]
AnchorMap = dict[str, AnchorPoint]
PhysicalNodeMap = dict[str, list[str]]
PortMap = dict[str, str]


class CircuitVisualComponent(Protocol):
    """Metadata contract for reusable Schemdraw circuit visual components."""

    component_kind: ClassVar[str]
    physical_nodes: PhysicalNodeMap
    ports: PortMap
