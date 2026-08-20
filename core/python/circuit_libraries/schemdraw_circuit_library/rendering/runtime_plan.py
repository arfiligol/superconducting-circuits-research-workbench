"""Minimal Schemdraw adapter for the public Circuit Workbench plan schema."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import schemdraw
import schemdraw.elements as elm

from ..components.lumped import GroundedLCResonator
from .from_schematic_export import UnsupportedSchematicComponentError


def render_runtime_plan(plan: Mapping[str, Any]) -> schemdraw.Drawing:
    """Render supported public runtime leaves; unsupported visual types fail closed."""

    intent = plan.get("schematic_intent")
    if (
        not isinstance(intent, Mapping)
        or intent.get("schema") != "circuit-workbench-schematic-intent.v1"
    ):
        raise ValueError("Circuit Workbench plan lacks a renderable schematic intent.")
    components = intent.get("components")
    if not isinstance(components, Sequence):
        raise ValueError("Circuit Workbench schematic intent components must be a sequence.")
    drawing = schemdraw.Drawing(show=False, transparent=True, dpi=96)
    anchors: dict[str, tuple[float, float]] = {}
    for index, item in enumerate(components):
        if (
            not isinstance(item, Mapping)
            or item.get("type_id") != "workbench.parallel_lc_resonator.v1"
        ):
            raise UnsupportedSchematicComponentError(
                "Circuit Workbench runtime has no Schemdraw mapping for this component type."
            )
        component_id = str(item.get("id", ""))
        visual = GroundedLCResonator(component_id=component_id).at((index * 8.0, 0.0))
        drawing += visual
        anchors[f"{component_id}.signal"] = visual.absanchors["signal"]
    for connection in intent.get("connections", []):
        if not isinstance(connection, Mapping):
            raise ValueError("Circuit Workbench schematic connection must be an object.")
        left = connection.get("left")
        right = connection.get("right")
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            raise ValueError("Circuit Workbench schematic connection endpoints must be objects.")
        left_key = f"{left.get('component_id')}.{left.get('pin_name')}"
        right_key = f"{right.get('component_id')}.{right.get('pin_name')}"
        if left_key not in anchors or right_key not in anchors:
            raise UnsupportedSchematicComponentError(
                "Connection targets an unsupported runtime visual pin."
            )
        drawing += elm.Line().at(anchors[left_key]).to(anchors[right_key])
    for port in intent.get("ports", []):
        if not isinstance(port, Mapping) or not isinstance(port.get("endpoint"), Mapping):
            raise ValueError("Circuit Workbench schematic port must bind an endpoint.")
        endpoint = port["endpoint"]
        key = f"{endpoint.get('component_id')}.{endpoint.get('pin_name')}"
        if key not in anchors:
            raise UnsupportedSchematicComponentError(
                "Port targets an unsupported runtime visual pin."
            )
        drawing += elm.Dot().at(anchors[key]).label(str(port.get("id", "port")), loc="right")
    return drawing
