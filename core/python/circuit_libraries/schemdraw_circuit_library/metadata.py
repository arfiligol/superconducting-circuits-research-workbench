from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from math import hypot, isfinite
from typing import Any, ClassVar, Literal, Protocol

import schemdraw.elements as elm

AnchorPoint = tuple[float, float]
AnchorMap = dict[str, AnchorPoint]
PhysicalNodeMap = dict[str, list[str]]
PortMap = dict[str, str]
type TerminalFacing = Literal["left", "right", "up", "down"]
type NodeMarkerRole = Literal["connection", "junction"]
type ConnectionMarkerKind = Literal["connected", "exposed", "junction"]
type NodeLabelPlacement = Literal["bus_middle", "marker", "terminal"]


class CircuitVisualContractError(ValueError):
    """Raised when visual connectivity metadata is internally inconsistent."""


@dataclass(frozen=True, slots=True)
class TerminalSpec:
    """One externally attachable component anchor and its electrical node."""

    node: str
    anchor: str
    facing: TerminalFacing


@dataclass(frozen=True, slots=True)
class BusSpec:
    """One component-owned continuous conductor path on one electrical node."""

    node: str
    anchors: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.anchors) < 2:
            raise CircuitVisualContractError("A bus path requires at least two anchors.")


@dataclass(frozen=True, slots=True)
class NodeMarkerSpec:
    """One component-owned filled marker and why that electrical point is marked."""

    node: str
    anchor: str
    role: NodeMarkerRole


@dataclass(frozen=True, slots=True)
class NodeLabelSpec:
    """One Composer-owned physical-node label and its explicit visual target."""

    text: str
    placement: NodeLabelPlacement
    target: str
    loc: str = "top"
    offset: float | tuple[float, float] | None = None

    def __post_init__(self) -> None:
        if not self.text:
            raise CircuitVisualContractError("A physical-node label requires visible text.")
        if self.placement not in {"bus_middle", "marker", "terminal"}:
            raise CircuitVisualContractError(
                f"Unsupported physical-node label placement: {self.placement!r}."
            )
        if not self.target:
            raise CircuitVisualContractError("A physical-node label requires a target.")
        if not self.loc:
            raise CircuitVisualContractError("A physical-node label requires a location.")
        if self.offset is None:
            return
        values = self.offset if isinstance(self.offset, tuple) else (self.offset,)
        expected_length = 2 if isinstance(self.offset, tuple) else 1
        if len(values) != expected_length or not all(
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and isfinite(value)
            for value in values
        ):
            raise CircuitVisualContractError(
                "A physical-node label offset must be one finite number or two finite numbers."
            )


@dataclass(frozen=True, slots=True)
class ConnectionMarkerSpec:
    """One final marker intent emitted by the component currently composing a view."""

    point: AnchorPoint
    kind: ConnectionMarkerKind
    node: str | None = None


class CircuitVisualComponent(Protocol):
    """Metadata contract for reusable Schemdraw circuit visual components."""

    component_kind: ClassVar[str]
    anchors: AnchorMap
    physical_nodes: PhysicalNodeMap
    ports: PortMap
    public_terminals: dict[str, TerminalSpec]
    buses: dict[str, BusSpec]
    node_markers: dict[str, NodeMarkerSpec]
    physical_node_labels: dict[str, NodeLabelSpec]


def validate_component_metadata(component: CircuitVisualComponent) -> None:
    """Fail when nodes, buses, or public terminals reference inconsistent anchors."""

    component_name = getattr(component, "component_id", "") or component.component_kind
    anchor_names = set(component.anchors)
    anchor_owners: dict[str, str] = {}

    for node, aliases in component.physical_nodes.items():
        if not aliases:
            raise CircuitVisualContractError(
                f"{component_name}: physical node {node!r} has no anchors."
            )
        for anchor in aliases:
            if anchor not in anchor_names:
                raise CircuitVisualContractError(
                    f"{component_name}: physical node {node!r} references "
                    f"unknown anchor {anchor!r}."
                )
            previous_owner = anchor_owners.setdefault(anchor, node)
            if previous_owner != node:
                raise CircuitVisualContractError(
                    f"{component_name}: anchor {anchor!r} belongs to both "
                    f"{previous_owner!r} and {node!r}."
                )

    for port, node in component.ports.items():
        if node not in component.physical_nodes:
            raise CircuitVisualContractError(
                f"{component_name}: port {port!r} references unknown node {node!r}."
            )

    for terminal, spec in component.public_terminals.items():
        if spec.node not in component.physical_nodes:
            raise CircuitVisualContractError(
                f"{component_name}: terminal {terminal!r} references unknown "
                f"node {spec.node!r}."
            )
        if spec.anchor not in component.physical_nodes[spec.node]:
            raise CircuitVisualContractError(
                f"{component_name}: terminal {terminal!r} anchor {spec.anchor!r} "
                f"is not part of node {spec.node!r}."
            )

    for bus, spec in component.buses.items():
        if spec.node not in component.physical_nodes:
            raise CircuitVisualContractError(
                f"{component_name}: bus {bus!r} references unknown node {spec.node!r}."
            )
        aliases = component.physical_nodes[spec.node]
        unknown = [anchor for anchor in spec.anchors if anchor not in aliases]
        if unknown:
            raise CircuitVisualContractError(
                f"{component_name}: bus {bus!r} anchors {unknown!r} are not part "
                f"of node {spec.node!r}."
            )

    for marker, spec in getattr(component, "node_markers", {}).items():
        if spec.node not in component.physical_nodes:
            raise CircuitVisualContractError(
                f"{component_name}: marker {marker!r} references unknown "
                f"node {spec.node!r}."
            )
        if spec.anchor not in component.physical_nodes[spec.node]:
            raise CircuitVisualContractError(
                f"{component_name}: marker {marker!r} anchor {spec.anchor!r} "
                f"is not part of node {spec.node!r}."
            )

    for node, spec in getattr(component, "physical_node_labels", {}).items():
        _physical_node_label_point(component, node, spec)


def render_connection_markers(
    owner: Any,
    markers: list[ConnectionMarkerSpec],
    *,
    color: str,
    radius: float,
) -> tuple[Any, ...]:
    """Draw one resolved marker per coordinate; exposed root ports take precedence."""

    resolved: dict[AnchorPoint, ConnectionMarkerSpec] = {}
    priority = {"connected": 1, "junction": 1, "exposed": 2}
    for marker in markers:
        point = (round(marker.point[0], 12), round(marker.point[1], 12))
        previous = resolved.get(point)
        if (
            previous is not None
            and previous.node is not None
            and marker.node is not None
            and previous.node != marker.node
        ):
            raise CircuitVisualContractError(
                f"Marker coordinate {point!r} belongs to both "
                f"{previous.node!r} and {marker.node!r}."
            )
        if previous is None:
            resolved[point] = marker
            continue
        winner = marker if priority[marker.kind] > priority[previous.kind] else previous
        resolved[point] = ConnectionMarkerSpec(
            point=point,
            kind=winner.kind,
            node=previous.node or marker.node,
        )

    elements = []
    for point, marker in resolved.items():
        dot = elm.Dot(
            open=marker.kind == "exposed",
            radius=radius,
            color=color,
        ).at(point)
        elements.append(owner.add(dot))
    return tuple(elements)


def render_physical_node_labels(
    owner: CircuitVisualComponent,
    *,
    color: str,
) -> tuple[Any, ...]:
    """Render Composer-owned labels independently from connection markers."""

    elements = []
    for node, spec in owner.physical_node_labels.items():
        point = _physical_node_label_point(owner, node, spec)
        label_kwargs: dict[str, Any] = {"loc": spec.loc, "color": color}
        if spec.offset is not None:
            label_kwargs["ofst"] = spec.offset
        label = (
            elm.Dot(open=True, radius=0, color=color)
            .at(point)
            .label(spec.text, **label_kwargs)
            .hold()
        )
        elements.append(owner.add(label))
    return tuple(elements)


def _physical_node_label_point(
    component: CircuitVisualComponent,
    node: str,
    spec: NodeLabelSpec,
) -> AnchorPoint:
    component_name = getattr(component, "component_id", "") or component.component_kind
    if node not in component.physical_nodes:
        raise CircuitVisualContractError(
            f"{component_name}: physical-node label references unknown node {node!r}."
        )

    if spec.placement == "bus_middle":
        try:
            target = component.buses[spec.target]
        except KeyError as exc:
            raise CircuitVisualContractError(
                f"{component_name}: physical-node label for {node!r} references "
                f"unknown bus {spec.target!r}."
            ) from exc
        point = _bus_middle(component, spec.target, target)
    elif spec.placement == "marker":
        try:
            target = component.node_markers[spec.target]
        except KeyError as exc:
            raise CircuitVisualContractError(
                f"{component_name}: physical-node label for {node!r} references "
                f"unknown marker {spec.target!r}."
            ) from exc
        point = component.anchors[target.anchor]
    else:
        try:
            target = component.public_terminals[spec.target]
        except KeyError as exc:
            raise CircuitVisualContractError(
                f"{component_name}: physical-node label for {node!r} references "
                f"unknown terminal {spec.target!r}."
            ) from exc
        point = component.anchors[target.anchor]

    if target.node != node:
        raise CircuitVisualContractError(
            f"{component_name}: physical-node label for {node!r} targets "
            f"{spec.target!r} on node {target.node!r}."
        )
    return (float(point[0]), float(point[1]))


def _bus_middle(
    component: CircuitVisualComponent,
    bus_name: str,
    bus: BusSpec,
) -> AnchorPoint:
    points = [component.anchors[anchor] for anchor in bus.anchors]
    segments = list(pairwise(points))
    lengths = [
        hypot(right[0] - left[0], right[1] - left[1])
        for left, right in segments
    ]
    total = sum(lengths)
    if total == 0:
        component_name = getattr(component, "component_id", "") or component.component_kind
        raise CircuitVisualContractError(
            f"{component_name}: bus {bus_name!r} has zero geometric length."
        )

    remaining = total / 2
    for (left, right), length in zip(segments, lengths, strict=True):
        if remaining > length:
            remaining -= length
            continue
        fraction = remaining / length
        return (
            float(left[0] + fraction * (right[0] - left[0])),
            float(left[1] + fraction * (right[1] - left[1])),
        )
    raise AssertionError("A nonzero bus must have a geometric midpoint.")


def public_terminal_point(
    component: CircuitVisualComponent,
    terminal: str,
    *,
    transformed: bool = False,
) -> AnchorPoint:
    """Resolve a public terminal without exposing a child's internal anchors."""

    try:
        anchor = component.public_terminals[terminal].anchor
    except KeyError as exc:
        component_name = getattr(component, "component_id", "") or component.component_kind
        raise CircuitVisualContractError(
            f"{component_name}: unknown public terminal {terminal!r}."
        ) from exc

    anchors: Mapping[str, Any]
    if transformed:
        anchors = getattr(component, "absanchors", {})
        if anchor not in anchors:
            component_name = getattr(component, "component_id", "") or component.component_kind
            raise CircuitVisualContractError(
                f"{component_name}: transformed terminal {terminal!r} is unavailable "
                "before the component is placed."
            )
    else:
        anchors = component.anchors
    point = anchors[anchor]
    return (round(float(point[0]), 12), round(float(point[1]), 12))


def add_at_public_terminal(
    owner: Any,
    component: CircuitVisualComponent,
    terminal: str,
    point: AnchorPoint,
) -> Any:
    """Place and add a child by one of its public electrical terminals."""

    try:
        anchor = component.public_terminals[terminal].anchor
    except KeyError as exc:
        component_name = getattr(component, "component_id", "") or component.component_kind
        raise CircuitVisualContractError(
            f"{component_name}: unknown public terminal {terminal!r}."
        ) from exc

    expected = (round(float(point[0]), 12), round(float(point[1]), 12))
    placed = owner.add(component.at(point).anchor(anchor))
    actual = public_terminal_point(placed, terminal, transformed=True)
    if actual != expected:
        component_name = getattr(component, "component_id", "") or component.component_kind
        raise CircuitVisualContractError(
            f"{component_name}: public terminal {terminal!r} placement mismatch; "
            f"expected {expected!r}, actual {actual!r}."
        )
    return placed


def validate_block_clearance(
    blocks: Mapping[str, Any],
    *,
    clearance: float,
    include_labels: bool = False,
) -> None:
    """Fail when sibling Schemdraw component bounds overlap or violate clearance."""

    if clearance < 0:
        raise ValueError("clearance must be non-negative.")
    bounds = {
        name: block.get_bbox(transform=True, includetext=include_labels)
        for name, block in blocks.items()
    }
    names = list(bounds)
    for index, left_name in enumerate(names):
        left = bounds[left_name]
        for right_name in names[index + 1 :]:
            right = bounds[right_name]
            separated = (
                round(float(left.xmax + clearance), 12)
                <= round(float(right.xmin), 12)
                or round(float(right.xmax + clearance), 12)
                <= round(float(left.xmin), 12)
                or round(float(left.ymax + clearance), 12)
                <= round(float(right.ymin), 12)
                or round(float(right.ymax + clearance), 12)
                <= round(float(left.ymin), 12)
            )
            if not separated:
                raise CircuitVisualContractError(
                    f"Sibling blocks {left_name!r} and {right_name!r} overlap "
                    f"their required clearance {clearance:g}."
                )


__all__ = [
    "AnchorMap",
    "AnchorPoint",
    "BusSpec",
    "CircuitVisualComponent",
    "CircuitVisualContractError",
    "ConnectionMarkerKind",
    "ConnectionMarkerSpec",
    "NodeLabelPlacement",
    "NodeLabelSpec",
    "NodeMarkerRole",
    "NodeMarkerSpec",
    "PhysicalNodeMap",
    "PortMap",
    "TerminalFacing",
    "TerminalSpec",
    "add_at_public_terminal",
    "public_terminal_point",
    "render_connection_markers",
    "render_physical_node_labels",
    "validate_block_clearance",
    "validate_component_metadata",
]
