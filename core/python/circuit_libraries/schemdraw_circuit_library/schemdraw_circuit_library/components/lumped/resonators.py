from __future__ import annotations

from typing import Any, ClassVar

import schemdraw.elements as elm

from ...labels import named_math_label
from ...theme import Theme, theme_color


class GroundedLCResonator(elm.ElementCompound):
    """Grounded LC resonator visual component."""

    component_kind: ClassVar[str] = "GroundedLCResonator"

    def __init__(
        self,
        *,
        component_id: str = "",
        name: str | None = None,
        unit_length: float = 3.0,
        spacing_units: float = 1.0,
        height_units: float = 1.0,
        port_stub_units: float = 0.5,
        theme: Theme = "light",
        c_label: str | None = None,
        l_label: str | None = None,
        port_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.name = component_id if name is None else name
        self.unit_length = unit_length
        self.spacing_units = spacing_units
        self.height_units = height_units
        self.port_stub_units = port_stub_units
        self.spacing = unit_length * spacing_units
        self.height = unit_length * height_units
        self.port_stub = unit_length * port_stub_units
        self.theme: Theme = theme
        self.c_label = c_label if c_label is not None else self._named_label("C")
        self.l_label = l_label if l_label is not None else self._named_label("L")
        self.port_label = port_label
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def _named_label(self, symbol: str) -> str:
        return named_math_label(symbol, self.name)

    def setup(self) -> None:
        u = self.unit_length
        w = self.spacing
        h = self.height
        stub = self.port_stub
        dot_radius = u / 30
        color = theme_color(self.theme)

        A = {
            "start": (-stub, 0),
            "end": (w, 0),
            "port": (-stub, 0),
            "signal": (0, 0),
            "cap_top": (0, 0),
            "ind_top": (w, 0),
            "cap_bot": (0, -h),
            "ind_bot": (w, -h),
            "gnd": (w / 2, -h),
        }
        self.anchors.update(A)

        port = elm.Dot(open=True, radius=dot_radius, color=color).at(A["port"])
        if self.show_labels and self.port_label is not None:
            port = port.label(self.port_label, loc="left", color=color)
        self.port_dot = self.add(port)

        self.port_stub_line = self.add(elm.Line(color=color).endpoints(A["port"], A["signal"]))

        if self.show_nodes:
            self.signal_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["signal"]))
            self.ind_top_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["ind_top"]))

        self.top_bus = self.add(elm.Line(color=color).endpoints(A["cap_top"], A["ind_top"]))

        capacitor = elm.Capacitor(color=color).endpoints(A["cap_top"], A["cap_bot"])
        inductor = elm.Inductor(color=color).endpoints(A["ind_top"], A["ind_bot"])
        if self.show_labels:
            capacitor = capacitor.label(self.c_label, loc="top", color=color)
            inductor = inductor.label(self.l_label, loc="bottom", color=color)
        self.capacitor = self.add(capacitor)
        self.inductor = self.add(inductor)

        self.bottom_bus = self.add(elm.Line(color=color).endpoints(A["cap_bot"], A["ind_bot"]))
        self.ground = self.add(elm.Ground(color=color).at(A["gnd"]))

        self.physical_nodes = {
            "signal": ["port", "signal", "cap_top", "ind_top"],
            "gnd": ["cap_bot", "ind_bot", "gnd"],
        }
        self.ports = {"signal": "signal"}
        self.elmparams["drop"] = A["end"]
