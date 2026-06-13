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


class FloatingLCXYResonator(elm.ElementCompound):
    """Floating LC resonator with two island pads and one XY coupling node."""

    component_kind: ClassVar[str] = "FloatingLCXYResonator"

    def __init__(
        self,
        *,
        component_id: str = "",
        name: str | None = None,
        unit_length: float = 3.0,
        width_units: float = 1.6,
        height_units: float = 1.25,
        xy_offset_units: float = 0.9,
        port_stub_units: float = 0.45,
        theme: Theme = "light",
        c_g1_label: str | None = None,
        c_g2_label: str | None = None,
        c_q_label: str | None = None,
        l_q1_label: str | None = None,
        l_q2_label: str | None = None,
        c_xy1_label: str | None = None,
        c_xy2_label: str | None = None,
        pad1_label: str | None = None,
        pad2_label: str | None = None,
        xy_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.name = component_id if name is None else name
        self.unit_length = unit_length
        self.width_units = width_units
        self.height_units = height_units
        self.xy_offset_units = xy_offset_units
        self.port_stub_units = port_stub_units
        self.width = unit_length * width_units
        self.height = unit_length * height_units
        self.xy_offset = unit_length * xy_offset_units
        self.port_stub = unit_length * port_stub_units
        self.theme: Theme = theme
        self.c_g1_label = c_g1_label if c_g1_label is not None else r"$C_{g1}$"
        self.c_g2_label = c_g2_label if c_g2_label is not None else r"$C_{g2}$"
        self.c_q_label = c_q_label if c_q_label is not None else r"$C_q$"
        self.l_q1_label = l_q1_label if l_q1_label is not None else r"$L_{q1}$"
        self.l_q2_label = l_q2_label if l_q2_label is not None else r"$L_{q2}$"
        self.c_xy1_label = c_xy1_label if c_xy1_label is not None else r"$C_{xy1}$"
        self.c_xy2_label = c_xy2_label if c_xy2_label is not None else r"$C_{xy2}$"
        self.pad1_label = pad1_label
        self.pad2_label = pad2_label
        self.xy_label = xy_label
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        w = self.width
        h = self.height
        xy_dx = self.xy_offset
        stub = self.port_stub
        color = theme_color(self.theme)
        dot_radius = u / 32

        branch_x = {
            "c_q": w * 0.25,
            "l_q1": w * 0.52,
            "l_q2": w * 0.79,
        }
        xy_x = w + xy_dx
        y_mid = -h / 2
        upper_gnd_y = u * 0.75
        lower_gnd_y = -h - u * 0.75

        A = {
            "start": (-stub, 0),
            "end": (xy_x + stub, y_mid),
            "pad1_port": (-stub, 0),
            "pad2_port": (-stub, -h),
            "xy_port": (xy_x + stub, y_mid),
            "pad1": (0, 0),
            "pad2": (0, -h),
            "xy": (xy_x, y_mid),
            "top_bus_end": (w, 0),
            "bottom_bus_end": (w, -h),
            "c_q_top": (branch_x["c_q"], 0),
            "c_q_bot": (branch_x["c_q"], -h),
            "l_q1_top": (branch_x["l_q1"], 0),
            "l_q1_bot": (branch_x["l_q1"], -h),
            "l_q2_top": (branch_x["l_q2"], 0),
            "l_q2_bot": (branch_x["l_q2"], -h),
            "c_g1_top": (w * 0.08, 0),
            "c_g1_bot": (w * 0.08, upper_gnd_y),
            "c_g2_top": (w * 0.08, -h),
            "c_g2_bot": (w * 0.08, lower_gnd_y),
            "gnd1": (w * 0.08, upper_gnd_y),
            "gnd2": (w * 0.08, lower_gnd_y),
            "c_xy1_left": (w, 0),
            "c_xy2_left": (w, -h),
        }
        self.anchors.update(A)

        self.pad1_port_line = self.add(elm.Line(color=color).endpoints(A["pad1_port"], A["pad1"]))
        self.pad2_port_line = self.add(elm.Line(color=color).endpoints(A["pad2_port"], A["pad2"]))
        self.xy_port_line = self.add(elm.Line(color=color).endpoints(A["xy"], A["xy_port"]))

        if self.show_nodes:
            self.pad1_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["pad1"]))
            self.pad2_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["pad2"]))
            self.xy_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["xy"]))

        self.pad1_port_dot = self._open_port_dot(A["pad1_port"], self.pad1_label, "left")
        self.pad2_port_dot = self._open_port_dot(A["pad2_port"], self.pad2_label, "left")
        self.xy_port_dot = self._open_port_dot(A["xy_port"], self.xy_label, "right")

        self.top_bus = self.add(elm.Line(color=color).endpoints(A["pad1"], A["top_bus_end"]))
        self.bottom_bus = self.add(elm.Line(color=color).endpoints(A["pad2"], A["bottom_bus_end"]))

        self.c_q = self._vertical_element(
            elm.Capacitor,
            A["c_q_top"],
            A["c_q_bot"],
            self.c_q_label,
            "top",
        )
        self.l_q1 = self._vertical_element(
            elm.Inductor,
            A["l_q1_top"],
            A["l_q1_bot"],
            self.l_q1_label,
            "bottom",
        )
        self.l_q2 = self._vertical_element(
            elm.Inductor,
            A["l_q2_top"],
            A["l_q2_bot"],
            self.l_q2_label,
            "bottom",
        )

        self.c_g1 = self._vertical_element(
            elm.Capacitor,
            A["c_g1_top"],
            A["c_g1_bot"],
            self.c_g1_label,
            "top",
        )
        self.c_g2 = self._vertical_element(
            elm.Capacitor,
            A["c_g2_top"],
            A["c_g2_bot"],
            self.c_g2_label,
            "bottom",
        )
        self.ground1 = self.add(elm.Ground(color=color).at(A["gnd1"]))
        self.ground2 = self.add(elm.Ground(color=color).at(A["gnd2"]))

        self.c_xy1 = self._two_terminal(
            elm.Capacitor,
            A["c_xy1_left"],
            A["xy"],
            self.c_xy1_label,
            "top",
        )
        self.c_xy2 = self._two_terminal(
            elm.Capacitor,
            A["c_xy2_left"],
            A["xy"],
            self.c_xy2_label,
            "bottom",
        )

        self.physical_nodes = {
            "pad1": ["pad1_port", "pad1", "c_q_top", "l_q1_top", "l_q2_top", "c_g1_top"],
            "pad2": ["pad2_port", "pad2", "c_q_bot", "l_q1_bot", "l_q2_bot", "c_g2_top"],
            "xy": ["xy", "xy_port"],
            "gnd": ["c_g1_bot", "c_g2_bot", "gnd1", "gnd2"],
        }
        self.ports = {"pad1": "pad1", "pad2": "pad2", "xy": "xy"}
        self.elmparams["drop"] = A["end"]

    def _open_port_dot(
        self,
        anchor: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> elm.Element:
        color = theme_color(self.theme)
        dot = elm.Dot(open=True, radius=self.unit_length / 32, color=color).at(anchor)
        if self.show_labels and label is not None:
            dot = dot.label(label, loc=loc, color=color)
        return self.add(dot)

    def _vertical_element(
        self,
        element_type: type[elm.Element],
        start: tuple[float, float],
        end: tuple[float, float],
        label: str,
        loc: str,
    ) -> elm.Element:
        return self._two_terminal(element_type, start, end, label, loc)

    def _two_terminal(
        self,
        element_type: type[elm.Element],
        start: tuple[float, float],
        end: tuple[float, float],
        label: str,
        loc: str,
    ) -> elm.Element:
        color = theme_color(self.theme)
        element = element_type(color=color).endpoints(start, end)
        if self.show_labels:
            element = element.label(label, loc=loc, color=color)
        return self.add(element)


class ReflectiveJPACapacitiveCoupledLC(elm.ElementCompound):
    """Capacitively coupled reflective JPA resonator visual component."""

    component_kind: ClassVar[str] = "ReflectiveJPACapacitiveCoupledLC"

    def __init__(
        self,
        *,
        component_id: str = "",
        name: str | None = None,
        unit_length: float = 3.0,
        spacing_units: float = 1.45,
        height_units: float = 1.0,
        port_stub_units: float = 0.45,
        theme: Theme = "light",
        coupling_label: str | None = None,
        resonator_cap_label: str | None = None,
        josephson_label: str | None = None,
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
        self.coupling_label = coupling_label if coupling_label is not None else r"$C_c$"
        self.resonator_cap_label = (
            resonator_cap_label if resonator_cap_label is not None else r"$C_{\mathrm{res}}$"
        )
        self.josephson_label = josephson_label if josephson_label is not None else r"$L_J$"
        self.port_label = port_label
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        w = self.spacing
        h = self.height
        stub = self.port_stub
        color = theme_color(self.theme)
        dot_radius = u / 32

        A = {
            "start": (-stub, 0),
            "end": (w * 1.65, 0),
            "port": (-stub, 0),
            "signal": (0, 0),
            "resonator": (w, 0),
            "cap_ground": (w, -h),
            "jj_top": (w * 1.45, 0),
            "jj_ground": (w * 1.45, -h),
            "gnd_left": (w, -h),
            "gnd_right": (w * 1.45, -h),
            "gnd": (w * 1.225, -h),
        }
        self.anchors.update(A)

        port = elm.Dot(open=True, radius=dot_radius, color=color).at(A["port"])
        if self.show_labels and self.port_label is not None:
            port = port.label(self.port_label, loc="left", color=color)
        self.port_dot = self.add(port)
        self.port_stub_line = self.add(elm.Line(color=color).endpoints(A["port"], A["signal"]))

        coupling = elm.Capacitor(color=color).endpoints(A["signal"], A["resonator"])
        if self.show_labels:
            coupling = coupling.label(self.coupling_label, loc="top", color=color)
        self.coupling_capacitor = self.add(coupling)

        self.resonator_bus = self.add(elm.Line(color=color).endpoints(A["resonator"], A["jj_top"]))
        if self.show_nodes:
            self.resonator_dot = self.add(
                elm.Dot(radius=dot_radius, color=color).at(A["resonator"])
            )
            self.jj_top_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["jj_top"]))

        shunt_cap = elm.Capacitor(color=color).endpoints(A["resonator"], A["cap_ground"])
        josephson = elm.Josephson(color=color).endpoints(A["jj_top"], A["jj_ground"])
        if self.show_labels:
            shunt_cap = shunt_cap.label(self.resonator_cap_label, loc="top", color=color)
            josephson = josephson.label(self.josephson_label, loc="bottom", color=color)
        self.resonator_capacitor = self.add(shunt_cap)
        self.josephson = self.add(josephson)
        self.ground_bus = self.add(elm.Line(color=color).endpoints(A["gnd_left"], A["gnd_right"]))
        self.ground = self.add(elm.Ground(color=color).at(A["gnd"]))

        self.physical_nodes = {
            "signal": ["port", "signal"],
            "resonator": ["resonator", "jj_top"],
            "gnd": ["cap_ground", "jj_ground", "gnd_left", "gnd_right", "gnd"],
        }
        self.ports = {"signal": "signal"}
        self.elmparams["drop"] = A["end"]
