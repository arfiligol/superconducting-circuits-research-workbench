"""Private Schemdraw adapter for the sealed Circuit Workbench V1 plan."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import schemdraw
import schemdraw.elements as elm


class GroundedLCResonator(elm.ElementCompound):
    """Minimal grounded parallel-LC drawing with one exposed signal anchor."""

    def __init__(self, component_id: str, **kwargs: Any) -> None:
        self.component_id = component_id
        super().__init__(**kwargs)

    def setup(self) -> None:
        anchors = {
            "start": (-1.5, 0.0),
            "signal": (-1.5, 0.0),
            "cap_top": (0.0, 0.0),
            "ind_top": (3.0, 0.0),
            "cap_bottom": (0.0, -3.0),
            "ind_bottom": (3.0, -3.0),
            "end": (4.5, 0.0),
            "ground": (1.5, -3.0),
        }
        self.anchors.update(anchors)
        self.add(elm.Line().endpoints(anchors["signal"], anchors["end"]))
        self.add(elm.Capacitor().endpoints(anchors["cap_top"], anchors["cap_bottom"]))
        self.add(elm.Inductor().endpoints(anchors["ind_top"], anchors["ind_bottom"]))
        self.add(elm.Line().endpoints(anchors["cap_bottom"], anchors["ind_bottom"]))
        self.add(elm.Ground().at(anchors["ground"]))
        self.elmparams["drop"] = anchors["end"]


class RuntimeBlock(elm.ElementCompound):
    """Minimal labeled runtime leaf visual with explicit exposed-pin anchors."""

    def __init__(
        self, label: str, pin_anchors: Mapping[str, tuple[float, float]], **kwargs: Any
    ) -> None:
        self._runtime_label = label
        self.pin_anchors = pin_anchors
        super().__init__(**kwargs)

    def setup(self) -> None:
        self.anchors.update(self.pin_anchors)
        self.add(elm.Line().endpoints((-2.0, -1.0), (2.0, -1.0)))
        self.add(elm.Line().endpoints((2.0, -1.0), (2.0, 1.0)))
        self.add(elm.Line().endpoints((2.0, 1.0), (-2.0, 1.0)))
        self.add(
            elm.Line().endpoints((-2.0, 1.0), (-2.0, -1.0)).label(self._runtime_label, loc="top")
        )
        self.elmparams["drop"] = (2.0, 0.0)


_RUNTIME_BLOCKS = {
    "workbench.transmission_line.v1": ("TL", {"head": (-2.0, 0.0), "tail": (2.0, 0.0)}),
    "workbench.intrinsic_interferometric_purcell_filter.v1": (
        "IPF",
        {"readout_attachment": (-2.0, 0.0), "feedline_attachment": (2.0, 0.0)},
    ),
    "workbench.linearized_floating_qubit.v1": (
        "Q",
        {"readout_attachment": (0.0, 1.0), "island_1": (-1.0, -1.0), "island_2": (1.0, -1.0)},
    ),
}


def render_runtime_plan(plan: Mapping[str, Any]) -> schemdraw.Drawing:
    """Render the supported V1 schematic intent without workspace imports."""

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
        if not isinstance(item, Mapping):
            raise ValueError(
                "Circuit Workbench runtime has no Schemdraw mapping for this component type."
            )
        component_id = str(item.get("id", ""))
        type_id = item.get("type_id")
        if type_id == "workbench.parallel_lc_resonator.v1":
            visual = GroundedLCResonator(component_id).at((index * 8.0, 0.0))
            pins = ("signal",)
        else:
            if not isinstance(type_id, str):
                raise ValueError(
                    "Circuit Workbench runtime has no Schemdraw mapping for this component type."
                )
            block = _RUNTIME_BLOCKS.get(type_id)
            if block is None:
                raise ValueError(
                    "Circuit Workbench runtime has no Schemdraw mapping for this component type."
                )
            visual = RuntimeBlock(*block).at((index * 8.0, 0.0))
            pins = block[1]
        drawing += visual
        for pin in pins:
            anchors[f"{component_id}.{pin}"] = visual.absanchors[pin]
    for connection in intent.get("connections", []):
        if not isinstance(connection, Mapping):
            raise ValueError("Circuit Workbench schematic connection must be an object.")
        left, right = connection.get("left"), connection.get("right")
        if not isinstance(left, Mapping) or not isinstance(right, Mapping):
            raise ValueError("Circuit Workbench schematic connection endpoints must be objects.")
        left_key = f"{left.get('component_id')}.{left.get('pin_name')}"
        right_key = f"{right.get('component_id')}.{right.get('pin_name')}"
        if left_key not in anchors or right_key not in anchors:
            raise ValueError("Connection targets an unsupported runtime visual pin.")
        drawing += elm.Line().at(anchors[left_key]).to(anchors[right_key])
    for port in intent.get("ports", []):
        if not isinstance(port, Mapping) or not isinstance(port.get("endpoint"), Mapping):
            raise ValueError("Circuit Workbench schematic port must bind an endpoint.")
        endpoint = port["endpoint"]
        key = f"{endpoint.get('component_id')}.{endpoint.get('pin_name')}"
        if key not in anchors:
            raise ValueError("Port targets an unsupported runtime visual pin.")
        drawing += elm.Dot().at(anchors[key]).label(str(port.get("id", "port")), loc="right")
    return drawing
