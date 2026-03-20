"""
Circuit Visualizer using Schemdraw.

This module provides functionality to convert a CircuitDefinition
into an SVG string using the Schemdraw library.
"""

import re
from typing import Any

import schemdraw
import schemdraw.elements as elm

from core.simulation.application import layout_plan as layout_plan_service
from core.simulation.domain.circuit import CircuitDefinition
from core.simulation.domain.ir import CircuitElement

_SVG_VIEWBOX_PATTERN = re.compile(
    r'height="([0-9.eE+-]+)pt"\s+width="([0-9.eE+-]+)pt"\s+'
    r'viewBox="([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)"'
)


def _add_svg_padding(svg_text: str, pad_pt: float = 12.0) -> str:
    """Expand SVG viewBox/size to prevent edge clipping of strokes and labels."""
    match = _SVG_VIEWBOX_PATTERN.search(svg_text)
    if match is None:
        return svg_text

    height = float(match.group(1))
    width = float(match.group(2))
    x0 = float(match.group(3))
    y0 = float(match.group(4))
    view_w = float(match.group(5))
    view_h = float(match.group(6))

    replacement = (
        f'height="{height + 2 * pad_pt}pt" '
        f'width="{width + 2 * pad_pt}pt" '
        f'viewBox="{x0 - pad_pt} {y0 - pad_pt} {view_w + 2 * pad_pt} {view_h + 2 * pad_pt}"'
    )
    return _SVG_VIEWBOX_PATTERN.sub(replacement, svg_text, count=1)


def _resolve_elements(
    elements_or_circuit: list[CircuitElement] | CircuitDefinition,
) -> list[CircuitElement]:
    """Accept either a lowered element list or a CircuitDefinition."""
    if isinstance(elements_or_circuit, CircuitDefinition):
        return elements_or_circuit.to_ir().lowered_elements()
    return elements_or_circuit


def _component_label_parts(
    circuit: CircuitDefinition,
    component_name: str,
    component_kind: str,
    value_ref: str | int,
) -> tuple[str, str | None]:
    """Build display-friendly label parts: component id + optional value/unit."""
    return layout_plan_service.component_label_parts(
        circuit,
        component_name,
        component_kind,
        value_ref,
    )


def _is_ground(node_str: str) -> bool:
    """Return True when a topology node represents the ground reference."""
    return CircuitDefinition.is_ground_node(node_str)


def _classify_layout_mode(circuit: CircuitDefinition) -> str:
    """Return a coarse layout profile for domain-specific spacing heuristics."""
    return layout_plan_service._classify_layout_mode(circuit.to_ir())


def _build_shunt_cluster_metadata(
    elements_or_circuit: list[CircuitElement] | CircuitDefinition,
) -> dict[int, tuple[str, int, int]]:
    """Map topology index to (signal_node, cluster_index, cluster_total) for shunt branches."""
    return layout_plan_service._build_shunt_cluster_metadata(
        tuple(_resolve_elements(elements_or_circuit))
    )


def _estimate_component_slot_width(
    component_kind: str,
    name_label: str,
    value_label: str | None,
    layout_mode: str,
) -> float:
    """Estimate horizontal space a shunt branch should reserve around its anchor."""
    return layout_plan_service._estimate_component_slot_width(
        component_kind,
        name_label,
        value_label,
        layout_mode,
    )


def _build_shunt_branch_offsets(
    circuit: CircuitDefinition,
    elements: list[CircuitElement] | str | None = None,
    layout_mode: str = "generic",
) -> dict[int, float]:
    """Reserve horizontal slots for each shunt branch to avoid label crowding."""
    if isinstance(elements, str):
        layout_mode = elements
        resolved_elements = tuple(circuit.to_ir().elements)
    else:
        resolved_elements = tuple(elements or circuit.to_ir().elements)
    return layout_plan_service._build_shunt_branch_offsets(
        circuit,
        resolved_elements,
        layout_mode,
    )


def _build_signal_node_padding(
    shunt_cluster_metadata: dict[int, tuple[str, int, int]],
    shunt_branch_offsets: dict[int, float],
) -> dict[str, tuple[float, float]]:
    """Estimate left/right horizontal padding needed around each signal node."""
    return layout_plan_service._build_signal_node_padding(
        shunt_cluster_metadata,
        shunt_branch_offsets,
    )


def _build_backbone_positions(
    elements_or_circuit: list[CircuitElement] | CircuitDefinition,
    dx: float,
    origin_x: float = 1.8,
    node_padding: dict[str, tuple[float, float]] | None = None,
) -> dict[str, float] | None:
    """Return fixed x positions for simple chain-like signal backbones."""
    return layout_plan_service._build_backbone_positions(
        tuple(_resolve_elements(elements_or_circuit)),
        dx,
        origin_x=origin_x,
        node_padding=node_padding,
    )


def _shunt_branch_offset(
    component_kind: str, cluster_index: int, cluster_total: int, layout_mode: str
) -> float:
    """Return x offset from the signal-node anchor for a shunt branch."""
    if cluster_total <= 1:
        return 0.0

    centered_index = cluster_index - ((cluster_total - 1) / 2.0)
    step = 1.35 if layout_mode == "jtwpa_like" else 1.2
    offset = centered_index * step

    if component_kind == "port" and offset >= -0.25:
        offset -= 0.55
    return offset


def _shunt_label_plan(
    component_kind: str, cluster_index: int, cluster_total: int, layout_mode: str
) -> tuple[str, float, float, float]:
    """Return side, x offset, name y, value y for vertical-branch labels."""
    if cluster_total <= 1:
        if component_kind == "capacitor":
            return ("left", -0.78, 1.44, 1.14)
        return ("right", 0.82, 1.44, 1.14)

    split_at = (cluster_total + 1) // 2
    side = "left" if cluster_index < split_at else "right"
    edge_rank = cluster_index if side == "left" else (cluster_total - 1 - cluster_index)

    base_offset = 1.05 + (0.12 if layout_mode == "jtwpa_like" else 0.0)
    x_offset = base_offset + 0.36 * edge_rank
    if side == "left":
        x_offset *= -1.0

    return (side, x_offset, 1.44, 1.14)


def _estimate_label_group_box(
    x: float,
    x_offset: float,
    name_label: str,
    value_label: str | None,
    name_y: float,
    value_y: float,
) -> tuple[float, float, float, float]:
    """Approximate bbox for a two-line shunt label group in schematic coordinates."""
    longest = max(len(name_label), len(value_label or ""))
    width = max(1.0, (0.18 * longest) + 0.7)
    x_center = x + x_offset
    y_min = min(name_y, value_y) - 0.18
    y_max = max(name_y, value_y) + 0.18
    return (x_center - (width / 2.0), y_min, x_center + (width / 2.0), y_max)


def _boxes_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
    padding: float = 0.08,
) -> bool:
    """Return True when two approximate label boxes overlap."""
    left_x1, left_y1, left_x2, left_y2 = left
    right_x1, right_y1, right_x2, right_y2 = right
    return not (
        (left_x2 + padding) < right_x1
        or (right_x2 + padding) < left_x1
        or (left_y2 + padding) < right_y1
        or (right_y2 + padding) < left_y1
    )


def _resolve_shunt_label_layout(
    x: float,
    component_kind: str,
    name_label: str,
    value_label: str | None,
    cluster_index: int,
    cluster_total: int,
    layout_mode: str,
    occupied_boxes: list[tuple[float, float, float, float]],
    preferred_side: str | None = None,
) -> tuple[str, float, float, float, tuple[float, float, float, float]]:
    """Choose the first non-overlapping candidate layout for a shunt label group."""
    base_side, base_offset, base_name_y, base_value_y = _shunt_label_plan(
        component_kind=component_kind,
        cluster_index=cluster_index,
        cluster_total=cluster_total,
        layout_mode=layout_mode,
    )
    alternate_side = "right" if base_side == "left" else "left"
    base_magnitude = abs(base_offset)

    if preferred_side in {"left", "right"}:
        side_order = (preferred_side, "right" if preferred_side == "left" else "left")
    else:
        side_order = (base_side, alternate_side)

    candidates: list[tuple[str, float, float, float]] = []
    for side in side_order:
        sign = -1.0 if side == "left" else 1.0
        for outward in (0.0, 0.35, 0.7):
            candidate_offset = sign * (base_magnitude + outward)
            for y_shift in (0.0, 0.16, -0.16, 0.3, -0.3):
                name_y = min(2.0, max(1.2, base_name_y + y_shift))
                value_y = min(1.6, max(0.82, base_value_y + y_shift))
                candidates.append((side, candidate_offset, name_y, value_y))

    for side, x_offset, name_y, value_y in candidates:
        candidate_box = _estimate_label_group_box(
            x=x,
            x_offset=x_offset,
            name_label=name_label,
            value_label=value_label,
            name_y=name_y,
            value_y=value_y,
        )
        if not any(_boxes_overlap(candidate_box, box) for box in occupied_boxes):
            return side, x_offset, name_y, value_y, candidate_box

    side, x_offset, name_y, value_y = candidates[-1]
    return (
        side,
        x_offset,
        name_y,
        value_y,
        _estimate_label_group_box(
            x=x,
            x_offset=x_offset,
            name_label=name_label,
            value_label=value_label,
            name_y=name_y,
            value_y=value_y,
        ),
    )


def _ensure_node_label(
    drawing: schemdraw.Drawing,
    labeled_nodes: set[str],
    node_str: str,
    x: float,
    y: float,
    loc: str,
) -> None:
    """Render each node label at most once."""
    if node_str in labeled_nodes:
        return

    if _is_ground(node_str) and loc in {"top", "bottom"}:
        label_y = y + 0.34 if loc == "top" else y - 0.4
        drawing.add(
            elm.Label().at((x, label_y)).label(node_str, loc="center", color="gray", fontsize=8)
        )
    else:
        drawing.add(elm.Label().at((x, y)).label(node_str, loc=loc, color="gray", fontsize=8))
    labeled_nodes.add(node_str)


def _add_shunt_labels(
    drawing: schemdraw.Drawing,
    x: float,
    component_kind: str,
    name_label: str,
    value_label: str | None,
    cluster_index: int,
    cluster_total: int,
    layout_mode: str,
    occupied_boxes: list[tuple[float, float, float, float]],
    preferred_side: str | None = None,
) -> None:
    """Place shunt labels with cluster-aware offsets to reduce overlap."""
    side, x_offset, name_y, value_y, candidate_box = _resolve_shunt_label_layout(
        x=x,
        component_kind=component_kind,
        name_label=name_label,
        value_label=value_label,
        cluster_index=cluster_index,
        cluster_total=cluster_total,
        layout_mode=layout_mode,
        occupied_boxes=occupied_boxes,
        preferred_side=preferred_side,
    )
    halign = "right" if side == "left" else "left"

    drawing.add(
        elm.Label()
        .at((x + x_offset, name_y))
        .label(name_label, loc="center", fontsize=11, halign=halign)
    )
    if value_label:
        drawing.add(
            elm.Label()
            .at((x + x_offset, value_y))
            .label(value_label, loc="center", fontsize=10, halign=halign)
        )
    occupied_boxes.append(candidate_box)


def _label_element(
    element: Any,
    component_kind: str,
    name_label: str,
    value_label: str | None,
    is_shunt: bool,
) -> Any:
    """Attach label with type-aware defaults to avoid overlaps."""
    if isinstance(element, elm.Dot):
        return element.label(name_label, loc="top", fontsize=11)

    # Port sources need extra room from nearby shunt elements.
    if component_kind == "port":
        return element.label(name_label, loc="right", ofst=0.45, halign="left", fontsize=11)

    # Dense shunt branches are handled by cluster-aware absolute labels.
    if is_shunt:
        return element

    # Series path labels sit above/below the line for readability.
    element.label(name_label, loc="top", ofst=0.32, fontsize=11)
    if value_label:
        element.label(value_label, loc="bottom", ofst=0.28, fontsize=10)
    return element


def _parallel_branch_y(cluster_index: int, cluster_total: int, base_y: float = 3.0) -> float:
    """Return a stable y lane for a parallel branch group."""
    if cluster_total <= 1:
        return base_y
    centered_index = cluster_index - ((cluster_total - 1) / 2.0)
    return base_y + (centered_index * 1.6)


def _add_parallel_branch_labels(
    drawing: schemdraw.Drawing,
    x1: float,
    x2: float,
    branch_y: float,
    name_label: str,
    value_label: str | None,
) -> None:
    """Place labels for non-overlapping parallel branches away from the center lane."""
    label_x = (x1 + x2) / 2.0
    if branch_y >= 3.0:
        name_y = branch_y + 0.66
        value_y = branch_y + 0.32
    else:
        name_y = branch_y - 0.68
        value_y = branch_y - 1.04

    drawing.add(elm.Label().at((label_x, name_y)).label(name_label, loc="center", fontsize=11))
    if value_label:
        drawing.add(
            elm.Label().at((label_x, value_y)).label(value_label, loc="center", fontsize=10)
        )


def _build_parallel_node_side_preferences(
    parallel_cluster_metadata: dict[int, tuple[tuple[str, str], int, int]],
    backbone_positions: dict[str, float] | None,
) -> dict[str, str]:
    """Prefer outer-side labels for nodes that belong to a parallel branch group."""
    if not backbone_positions:
        return {}

    preferences: dict[str, str] = {}
    seen_pairs: set[frozenset[str]] = set()
    for pair_key, _, _ in parallel_cluster_metadata.values():
        frozen_pair = frozenset(pair_key)
        if frozen_pair in seen_pairs:
            continue
        seen_pairs.add(frozen_pair)
        node_a, node_b = pair_key
        if backbone_positions.get(node_a, 0.0) <= backbone_positions.get(node_b, 0.0):
            left_node, right_node = node_a, node_b
        else:
            left_node, right_node = node_b, node_a
        preferences[left_node] = "left"
        preferences[right_node] = "right"
    return preferences


def _label_parallel_node_anchor(
    drawing: schemdraw.Drawing,
    labeled_nodes: set[str],
    node_str: str,
    x: float,
    preferred_side: str,
) -> None:
    """Place node labels above the backbone but outside the parallel-branch bundle."""
    if node_str in labeled_nodes:
        return

    if preferred_side == "left":
        label_x = x - 0.18
        halign = "right"
    else:
        label_x = x + 0.18
        halign = "left"

    drawing.add(
        elm.Label()
        .at((label_x, 3.38))
        .label(node_str, loc="center", color="gray", fontsize=8, halign=halign)
    )
    labeled_nodes.add(node_str)


def generate_circuit_svg(circuit: CircuitDefinition) -> str:
    """
    Generate an SVG string representation of a CircuitDefinition.

    This uses a simple layout heuristic to draw the components.

    Args:
        circuit: The circuit definition to visualize.

    Returns:
        A string containing the raw SVG data.
    """
    # SVG backend scales with drawing extents naturally and avoids matplotlib figure accumulation.
    d = schemdraw.Drawing(canvas="svg", show=False)
    plan = layout_plan_service.build_layout_plan(circuit)
    layout_mode = plan.layout_mode

    x_pos = 0.0
    dx = plan.dx
    gap = plan.gap
    elements = list(plan.elements)
    shunt_cluster_metadata = plan.shunt_cluster_metadata
    parallel_cluster_metadata = plan.parallel_cluster_metadata
    shunt_branch_offsets = plan.shunt_branch_offsets
    backbone_positions = plan.backbone_positions or {}
    use_backbone_layout = plan.use_backbone_layout
    parallel_node_side_preferences = _build_parallel_node_side_preferences(
        parallel_cluster_metadata,
        backbone_positions,
    )

    node_latest_x: dict[str, float] = {}
    node_bridge_y: dict[str, float] = {}
    tip_node_top = None
    next_bridge_y = 4.5
    labeled_nodes: set[str] = set()
    occupied_shunt_label_boxes: list[tuple[float, float, float, float]] = []

    def wire_node(node_str: str, target_x: float, target_y: float) -> None:
        nonlocal next_bridge_y
        if node_str in node_latest_x:
            prev_x = node_latest_x[node_str]
            dist = abs(target_x - prev_x)
            if dist > 2.0:
                # Reuse one bridge lane per node to keep the same net visually coherent.
                bridge_y = node_bridge_y.get(node_str)
                if bridge_y is None:
                    bridge_y = next_bridge_y
                    node_bridge_y[node_str] = bridge_y
                    next_bridge_y += 0.6

                d.add(elm.Line().at((prev_x, target_y)).to((prev_x, bridge_y)))
                d.add(elm.Line().at((prev_x, bridge_y)).to((target_x, bridge_y)))
                d.add(elm.Line().at((target_x, bridge_y)).to((target_x, target_y)))
            elif dist > 0.1:
                d.add(elm.Line().at((prev_x, target_y)).to((target_x, target_y)))

        node_latest_x[node_str] = max(node_latest_x.get(node_str, 0.0), target_x)

    last_ground_x: float | None = None
    ground_drawn = False

    def wire_ground(target_x: float) -> None:
        nonlocal last_ground_x, ground_drawn
        if not ground_drawn:
            d.add(elm.Ground().at((target_x, 0.0)))
            ground_drawn = True

        if last_ground_x is not None:
            dist = abs(target_x - last_ground_x)
            if dist > 0.1:
                d.add(elm.Line().at((last_ground_x, 0.0)).to((target_x, 0.0)))
        last_ground_x = target_x

    for topo_index, lowered in enumerate(elements):
        comp_name = lowered.name
        component_kind = lowered.kind
        node1_str = lowered.node1
        node2_str = lowered.node2
        value_ref = lowered.value_ref
        name_label, value_label = _component_label_parts(
            circuit,
            comp_name,
            component_kind,
            value_ref,
        )

        if component_kind == "port":
            element = elm.SourceSin()
        elif component_kind == "capacitor":
            element = elm.Capacitor()
        elif component_kind == "inductor":
            element = elm.Inductor()
        elif component_kind == "resistor":
            element = elm.Resistor()
        elif component_kind == "josephson_junction":
            element = elm.Josephson()
        elif component_kind == "mutual_coupling":
            element = elm.Dot(open=True).label(f"K({comp_name})")
        else:
            element = elm.Dot(open=True).label(f"? {comp_name}")

        is_gnd1 = _is_ground(node1_str)
        is_gnd2 = _is_ground(node2_str)

        y1 = 0.0 if is_gnd1 else 3.0
        y2 = 0.0 if is_gnd2 else 3.0
        is_shunt = y1 != y2

        if is_shunt:
            signal_node, cluster_index, cluster_total = shunt_cluster_metadata.get(
                topo_index, (node1_str if not is_gnd1 else node2_str, 0, 1)
            )

            if use_backbone_layout:
                node_anchor_x = backbone_positions[signal_node]
                branch_x = node_anchor_x + shunt_branch_offsets.get(
                    topo_index,
                    _shunt_branch_offset(
                        component_kind=component_kind,
                        cluster_index=cluster_index,
                        cluster_total=cluster_total,
                        layout_mode=layout_mode,
                    ),
                )
            else:
                node_anchor_x = x_pos
                branch_x = x_pos

            if not use_backbone_layout and tip_node_top is not None and tip_node_top != signal_node:
                x_pos += gap

            x = branch_x
            if isinstance(element, elm.Dot):
                d.add(element.at((x, 1.5)))
            else:
                d.add(
                    _label_element(
                        element.at((x, 0.0)).to((x, 3.0)),
                        component_kind,
                        name_label,
                        value_label,
                        True,
                    )
                )
                if component_kind != "port":
                    _add_shunt_labels(
                        drawing=d,
                        x=x,
                        component_kind=component_kind,
                        name_label=name_label,
                        value_label=value_label,
                        cluster_index=cluster_index,
                        cluster_total=cluster_total,
                        layout_mode=layout_mode,
                        occupied_boxes=occupied_shunt_label_boxes,
                        preferred_side=parallel_node_side_preferences.get(signal_node),
                    )

            if use_backbone_layout and abs(branch_x - node_anchor_x) > 0.1:
                d.add(elm.Line().at((node_anchor_x, 3.0)).to((branch_x, 3.0)))

            wire_ground(x)

            should_label_nodes = component_kind != "port"

            if should_label_nodes:
                loc1 = "top" if y1 > y2 else "bottom"
                loc2 = "bottom" if y1 > y2 else "top"
                if not is_gnd1 and node1_str in parallel_node_side_preferences:
                    pass
                else:
                    label_x1 = node_anchor_x if not is_gnd1 else x
                    _ensure_node_label(d, labeled_nodes, node1_str, label_x1, y1, loc1)

                if not is_gnd2 and node2_str in parallel_node_side_preferences:
                    pass
                else:
                    label_x2 = node_anchor_x if not is_gnd2 else x
                    _ensure_node_label(d, labeled_nodes, node2_str, label_x2, y2, loc2)

            if use_backbone_layout:
                node_latest_x[signal_node] = node_anchor_x
            else:
                wire_node(signal_node, x, 3.0)
            tip_node_top = signal_node
            if not use_backbone_layout:
                dense_cluster_pitch = gap
                if cluster_total > 1:
                    dense_cluster_pitch += 0.7 + 0.25 * min(cluster_total - 1, 3)
                x_pos = x + dense_cluster_pitch
            continue

        if is_gnd1 and is_gnd2:
            if tip_node_top is not None:
                x_pos += gap
            x1 = x_pos
            x2 = x_pos + dx
            wire_ground(x1)
            wire_ground(x2)
            x_pos = x2
            continue

        if not use_backbone_layout and tip_node_top is not None and tip_node_top != node1_str:
            x_pos += gap

        if use_backbone_layout:
            x1 = backbone_positions.get(node1_str)
            x2 = backbone_positions.get(node2_str)
            if x1 is None or x2 is None:
                x1 = x_pos
                x2 = x_pos + dx
        else:
            x1 = x_pos
            x2 = x_pos + dx

        parallel_group = parallel_cluster_metadata.get(
            topo_index, ((tuple(sorted((node1_str, node2_str)))), 0, 1)
        )
        _, parallel_index, parallel_total = parallel_group
        branch_y = 3.0
        if use_backbone_layout and parallel_total > 1:
            branch_y = _parallel_branch_y(parallel_index, parallel_total)

        if abs(branch_y - 3.0) > 0.05:
            d.add(elm.Line().at((x1, 3.0)).to((x1, branch_y)))
            d.add(elm.Line().at((x2, 3.0)).to((x2, branch_y)))

        if isinstance(element, elm.Dot):
            d.add(element.at(((x1 + x2) / 2, branch_y)))
        elif use_backbone_layout and parallel_total > 1:
            d.add(element.at((x1, branch_y)).to((x2, branch_y)))
            _add_parallel_branch_labels(d, x1, x2, branch_y, name_label, value_label)
        else:
            d.add(
                _label_element(
                    element.at((x1, branch_y)).to((x2, branch_y)),
                    component_kind,
                    name_label,
                    value_label,
                    is_shunt=False,
                )
            )

        node1_parallel_side = parallel_node_side_preferences.get(node1_str)
        node2_parallel_side = parallel_node_side_preferences.get(node2_str)
        if node1_parallel_side:
            _label_parallel_node_anchor(d, labeled_nodes, node1_str, x1, node1_parallel_side)
        else:
            loc1 = "left" if x1 < x2 else "right"
            _ensure_node_label(d, labeled_nodes, node1_str, x1, 3.0, loc1)

        if node2_parallel_side:
            _label_parallel_node_anchor(d, labeled_nodes, node2_str, x2, node2_parallel_side)
        else:
            loc2 = "right" if x1 < x2 else "left"
            _ensure_node_label(d, labeled_nodes, node2_str, x2, 3.0, loc2)

        if use_backbone_layout:
            node_latest_x[node1_str] = x1
            node_latest_x[node2_str] = x2
        else:
            wire_node(node1_str, x1, 3.0)
            wire_node(node2_str, x2, 3.0)

        tip_node_top = node2_str
        if not use_backbone_layout:
            x_pos = x2

    svg_bytes = d.get_imagedata("svg")
    return _add_svg_padding(svg_bytes.decode("utf-8"))
