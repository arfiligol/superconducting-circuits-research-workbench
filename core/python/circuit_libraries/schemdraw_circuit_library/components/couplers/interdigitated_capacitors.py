from __future__ import annotations

from typing import Any, ClassVar

import schemdraw.elements as elm

from schemdraw_circuit_library.metadata import (
    BusSpec,
    ConnectionMarkerSpec,
    NodeLabelSpec,
    NodeMarkerSpec,
    TerminalSpec,
    render_connection_markers,
    render_physical_node_labels,
    validate_component_metadata,
)
from schemdraw_circuit_library.theme import SCHEMATIC_DOT_RADIUS, Theme, theme_color


class InterdigitatedCapacitor(elm.ElementCompound):
    """Three-branch positive-capacitance equivalent of a two-terminal IDC."""

    component_kind: ClassVar[str] = "InterdigitatedCapacitor"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        width_units: float = 1.5,
        shunt_height_units: float = 0.9,
        port_stub_units: float = 1.8,
        theme: Theme = "light",
        c1g_label: str = r"$C_{1g}$",
        c2g_label: str = r"$C_{2g}$",
        c12_label: str = r"$C_{12}$",
        terminal_1_label: str | None = None,
        terminal_2_label: str | None = None,
        show_terminals: bool = True,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.unit_length = unit_length
        self.width = unit_length * width_units
        self.shunt_height = unit_length * shunt_height_units
        self.port_stub = unit_length * port_stub_units
        self.theme: Theme = theme
        self.c1g_label = c1g_label
        self.c2g_label = c2g_label
        self.c12_label = c12_label
        self.terminal_1_label = terminal_1_label
        self.terminal_2_label = terminal_2_label
        self.show_terminals = show_terminals
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        width = self.width
        height = self.shunt_height
        stub = self.port_stub
        color = theme_color(self.theme)
        terminal_1 = (0, 0)
        terminal_2 = (width, 0)
        A = {
            "start": (-stub, 0),
            "end": (width + stub, 0),
            "terminal_1_port": (-stub, 0),
            "terminal_1": terminal_1,
            "terminal_2": terminal_2,
            "terminal_2_port": (width + stub, 0),
            "terminal_1_ground": (0, -height),
            "terminal_2_ground": (width, -height),
        }
        self.anchors.update(A)

        self.add(elm.Line(color=color).endpoints(A["terminal_1_port"], terminal_1))
        self.add(elm.Line(color=color).endpoints(terminal_2, A["terminal_2_port"]))
        self._capacitor(terminal_1, terminal_2, self.c12_label, "top")
        self._capacitor(terminal_1, A["terminal_1_ground"], self.c1g_label, "top")
        self._capacitor(terminal_2, A["terminal_2_ground"], self.c2g_label, "bottom")
        self.add(elm.Ground(color=color).at(A["terminal_1_ground"]))
        self.add(elm.Ground(color=color).at(A["terminal_2_ground"]))

        self.physical_nodes = {
            "terminal_1": ["terminal_1_port", "terminal_1"],
            "terminal_2": ["terminal_2", "terminal_2_port"],
            "gnd": ["terminal_1_ground", "terminal_2_ground"],
        }
        self.ports = {"terminal_1": "terminal_1", "terminal_2": "terminal_2"}
        self.public_terminals = {
            "terminal_1": TerminalSpec("terminal_1", "terminal_1_port", "left"),
            "terminal_2": TerminalSpec("terminal_2", "terminal_2_port", "right"),
        }
        self.buses = {
            "terminal_1_stub": BusSpec(
                "terminal_1",
                ("terminal_1_port", "terminal_1"),
            ),
            "terminal_2_stub": BusSpec(
                "terminal_2",
                ("terminal_2", "terminal_2_port"),
            ),
        }
        self.node_markers = {
            "terminal_1_junction": NodeMarkerSpec(
                "terminal_1",
                "terminal_1",
                "junction",
            ),
            "terminal_2_junction": NodeMarkerSpec(
                "terminal_2",
                "terminal_2",
                "junction",
            ),
        }
        self.physical_node_labels = {
            node: NodeLabelSpec(
                label,
                "terminal",
                node,
                loc=loc,
                offset=2 * SCHEMATIC_DOT_RADIUS,
            )
            for node, label, loc in (
                ("terminal_1", self.terminal_1_label, "left"),
                ("terminal_2", self.terminal_2_label, "right"),
            )
            if self.show_terminals and label is not None
        }
        validate_component_metadata(self)
        markers = []
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(
                    A[spec.anchor],
                    "junction",
                    node=spec.node,
                )
                for spec in self.node_markers.values()
            )
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(
                    A[spec.anchor],
                    "exposed",
                    node=spec.node,
                )
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=SCHEMATIC_DOT_RADIUS,
        )
        if self.show_labels:
            render_physical_node_labels(self, color=color)
        self.elmparams["drop"] = A["end"]

    def _capacitor(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        capacitor = elm.Capacitor(color=color).endpoints(start, end)
        if self.show_labels:
            capacitor = capacitor.label(label, loc=loc, color=color)
        self.add(capacitor)

__all__ = ["InterdigitatedCapacitor"]
