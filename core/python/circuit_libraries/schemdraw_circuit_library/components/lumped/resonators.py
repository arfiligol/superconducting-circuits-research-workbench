from __future__ import annotations

from typing import Any, ClassVar, Literal

import schemdraw.elements as elm

from schemdraw_circuit_library.components.ports import Port50Ohm
from schemdraw_circuit_library.labels import named_math_label
from schemdraw_circuit_library.rendering.preview import PreviewCase, run_preview_cli
from schemdraw_circuit_library.theme import SCHEMATIC_DOT_RADIUS, Theme, theme_color

type InductiveBranchKind = Literal["linear", "josephson", "squid"]
type InductanceLoopElementKind = Literal["linear", "josephson"]


class UnsupportedInductiveBranchError(ValueError):
    """Raised when a renderer export asks for an unsupported branch kind."""


def _branch_label(
    *,
    kind: InductiveBranchKind,
    l_label: str | None,
    junction_label: str | None,
    squid_label: str | None,
) -> str:
    if kind == "linear":
        return l_label if l_label is not None else r"$L$"
    if kind == "josephson":
        return junction_label if junction_label is not None else r"$JJ$"
    if kind == "squid":
        return squid_label if squid_label is not None else r"$SQUID$"
    raise UnsupportedInductiveBranchError(f"Unsupported inductive branch kind: {kind!r}")


def _add_inductive_branch_primitives(
    owner: elm.ElementCompound,
    *,
    branch_kind: InductiveBranchKind,
    top: tuple[float, float],
    bottom: tuple[float, float],
    label: str,
    color: str,
    unit_length: float,
    show_labels: bool,
) -> None:
    if branch_kind == "linear":
        branch = elm.Inductor(color=color).endpoints(top, bottom)
        if show_labels:
            branch = branch.label(label, loc="bottom", color=color)
        owner.add(branch)
        return

    if branch_kind == "josephson":
        branch = elm.Josephson(color=color).endpoints(top, bottom)
        if show_labels:
            branch = branch.label(label, loc="bottom", color=color)
        owner.add(branch)
        return

    if branch_kind == "squid":
        x_top, y_top = top
        x_bottom, y_bottom = bottom
        dx = unit_length * 0.17
        left_top = (x_top - dx, y_top)
        right_top = (x_top + dx, y_top)
        left_bottom = (x_bottom - dx, y_bottom)
        right_bottom = (x_bottom + dx, y_bottom)
        owner.add(elm.Line(color=color).endpoints(left_top, right_top))
        owner.add(elm.Line(color=color).endpoints(left_bottom, right_bottom))
        owner.add(elm.Josephson(color=color).endpoints(left_top, left_bottom))
        right = elm.Josephson(color=color).endpoints(right_top, right_bottom)
        if show_labels:
            right = right.label(label, loc="bottom", color=color)
        owner.add(right)
        return

    raise UnsupportedInductiveBranchError(f"Unsupported inductive branch kind: {branch_kind!r}")


class InductiveBranch(elm.ElementCompound):
    """Topology-stable visual branch for linear, Josephson, and SQUID variants."""

    component_kind: ClassVar[str] = "InductiveBranch"

    def __init__(
        self,
        *,
        branch_kind: InductiveBranchKind = "linear",
        unit_length: float = 3.0,
        height_units: float = 1.0,
        squid_width_units: float = 0.34,
        theme: Theme = "light",
        l_label: str | None = None,
        junction_label: str | None = None,
        squid_label: str | None = None,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.branch_kind: InductiveBranchKind = branch_kind
        self.unit_length = unit_length
        self.height_units = height_units
        self.squid_width_units = squid_width_units
        self.height = unit_length * height_units
        self.squid_width = unit_length * squid_width_units
        self.theme: Theme = theme
        self.branch_label = _branch_label(
            kind=branch_kind,
            l_label=l_label,
            junction_label=junction_label,
            squid_label=squid_label,
        )
        self.show_labels = show_labels
        self.labels = {"branch": self.branch_label}
        super().__init__(**kwargs)

    def setup(self) -> None:
        h = self.height
        x = self.squid_width / 2
        color = theme_color(self.theme)

        A = {
            "start": (0, 0),
            "end": (0, -h),
            "top": (0, 0),
            "bottom": (0, -h),
            "squid_left_top": (-x, 0),
            "squid_left_bottom": (-x, -h),
            "squid_right_top": (x, 0),
            "squid_right_bottom": (x, -h),
        }
        self.anchors.update(A)

        if self.branch_kind == "linear":
            branch = elm.Inductor(color=color).endpoints(A["top"], A["bottom"])
            if self.show_labels:
                branch = branch.label(self.branch_label, loc="bottom", color=color)
            self.branch = self.add(branch)
        elif self.branch_kind == "josephson":
            branch = elm.Josephson(color=color).endpoints(A["top"], A["bottom"])
            if self.show_labels:
                branch = branch.label(self.branch_label, loc="bottom", color=color)
            self.branch = self.add(branch)
        elif self.branch_kind == "squid":
            self.top_bus = self.add(
                elm.Line(color=color).endpoints(A["squid_left_top"], A["squid_right_top"])
            )
            self.bottom_bus = self.add(
                elm.Line(color=color).endpoints(
                    A["squid_left_bottom"],
                    A["squid_right_bottom"],
                )
            )
            self.left_junction = self.add(
                elm.Josephson(color=color).endpoints(
                    A["squid_left_top"],
                    A["squid_left_bottom"],
                )
            )
            right = elm.Josephson(color=color).endpoints(
                A["squid_right_top"],
                A["squid_right_bottom"],
            )
            if self.show_labels:
                right = right.label(self.branch_label, loc="bottom", color=color)
            self.right_junction = self.add(right)
        else:
            raise UnsupportedInductiveBranchError(
                f"Unsupported inductive branch kind: {self.branch_kind!r}"
            )

        self.physical_nodes = {"top": ["top"], "bottom": ["bottom"]}
        self.ports = {"top": "top", "bottom": "bottom"}
        self.elmparams["drop"] = A["end"]


class InductanceLoop(elm.ElementCompound):
    """Grouped visual loop for two parallel inductive elements between one node pair."""

    component_kind: ClassVar[str] = "InductanceLoop"

    def __init__(
        self,
        *,
        component_id: str = "",
        element_kind: InductanceLoopElementKind = "linear",
        unit_length: float = 3.0,
        width_units: float = 0.55,
        height_units: float = 1.25,
        theme: Theme = "light",
        left_label: str | None = None,
        right_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.element_kind: InductanceLoopElementKind = element_kind
        self.unit_length = unit_length
        self.width_units = width_units
        self.height_units = height_units
        self.width = unit_length * width_units
        self.height = unit_length * height_units
        self.theme: Theme = theme
        self.left_label = left_label if left_label is not None else self._default_label(1)
        self.right_label = right_label if right_label is not None else self._default_label(2)
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        self.labels = {"left": self.left_label, "right": self.right_label}
        super().__init__(**kwargs)

    def _default_label(self, index: int) -> str:
        if self.element_kind == "linear":
            return rf"$L_{{{index}}}$"
        if self.element_kind == "josephson":
            return rf"$JJ_{{{index}}}$"
        raise UnsupportedInductiveBranchError(
            f"Unsupported inductance loop element kind: {self.element_kind!r}"
        )

    def setup(self) -> None:
        if self.element_kind not in {"linear", "josephson"}:
            raise UnsupportedInductiveBranchError(
                f"Unsupported inductance loop element kind: {self.element_kind!r}"
            )

        half_width = self.width / 2
        h = self.height
        lead = self.unit_length * 0.18
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS

        A = {
            "start": (0, 0),
            "end": (0, -h),
            "top": (0, 0),
            "bottom": (0, -h),
            "loop_top": (0, -lead),
            "loop_bottom": (0, -h + lead),
            "left_top": (-half_width, -lead),
            "left_bot": (-half_width, -h + lead),
            "right_top": (half_width, -lead),
            "right_bot": (half_width, -h + lead),
        }
        self.anchors.update(A)

        self.top_lead = self.add(elm.Line(color=color).endpoints(A["top"], A["loop_top"]))
        self.bottom_lead = self.add(elm.Line(color=color).endpoints(A["loop_bottom"], A["bottom"]))
        self.top_bus = self.add(elm.Line(color=color).endpoints(A["left_top"], A["right_top"]))
        self.bottom_bus = self.add(elm.Line(color=color).endpoints(A["left_bot"], A["right_bot"]))

        element_type: type[elm.Element] = (
            elm.Inductor if self.element_kind == "linear" else elm.Josephson
        )

        left_inductor = element_type(color=color).endpoints(A["left_top"], A["left_bot"])
        right_inductor = element_type(color=color).endpoints(A["right_top"], A["right_bot"])
        if self.show_labels:
            left_inductor = left_inductor.label(self.left_label, loc="bottom", color=color)
            right_inductor = right_inductor.label(self.right_label, loc="bottom", color=color)
        self.left_inductor = self.add(left_inductor)
        self.right_inductor = self.add(right_inductor)

        if self.show_nodes:
            self.top_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["top"]))
            self.bottom_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["bottom"]))

        self.physical_nodes = {
            "top": ["top", "loop_top", "left_top", "right_top"],
            "bottom": ["bottom", "loop_bottom", "left_bot", "right_bot"],
        }
        self.ports = {"top": "top", "bottom": "bottom"}
        self.elmparams["drop"] = A["end"]


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
        theme: Theme = "light",
        inductive_branch_kind: InductiveBranchKind = "linear",
        c_label: str | None = None,
        l_label: str | None = None,
        junction_label: str | None = None,
        squid_label: str | None = None,
        port_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.name = component_id if name is None else name
        self.unit_length = unit_length
        self.spacing_units = spacing_units
        self.height_units = height_units
        self.spacing = unit_length * spacing_units
        self.height = unit_length * height_units
        self.theme: Theme = theme
        self.inductive_branch_kind: InductiveBranchKind = inductive_branch_kind
        self.c_label = c_label if c_label is not None else self._named_label("C")
        self.branch_label = _branch_label(
            kind=inductive_branch_kind,
            l_label=l_label if l_label is not None else self._named_label("L"),
            junction_label=junction_label,
            squid_label=squid_label,
        )
        self.port_label = port_label
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        self.labels = {
            "capacitance": self.c_label,
            "inductive_branch": self.branch_label,
            "port": self.port_label,
        }
        super().__init__(**kwargs)

    def _named_label(self, symbol: str) -> str:
        return named_math_label(symbol, self.name)

    def setup(self) -> None:
        w = self.spacing
        h = self.height
        dot_radius = SCHEMATIC_DOT_RADIUS
        color = theme_color(self.theme)

        A = {
            "start": (0, 0),
            "end": (w, 0),
            "signal": (0, 0),
            "cap_top": (0, 0),
            "ind_top": (w, 0),
            "cap_bot": (0, -h),
            "ind_bot": (w, -h),
            "gnd": (w / 2, -h),
        }
        self.anchors.update(A)

        if self.show_nodes:
            self.signal_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["signal"]))
            self.ind_top_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["ind_top"]))

        self.top_bus = self.add(elm.Line(color=color).endpoints(A["cap_top"], A["ind_top"]))

        capacitor = elm.Capacitor(color=color).endpoints(A["cap_top"], A["cap_bot"])
        if self.show_labels:
            capacitor = capacitor.label(self.c_label, loc="top", color=color)
        self.capacitor = self.add(capacitor)

        _add_inductive_branch_primitives(
            self,
            branch_kind=self.inductive_branch_kind,
            top=A["ind_top"],
            bottom=A["ind_bot"],
            label=self.branch_label,
            color=color,
            unit_length=self.unit_length,
            show_labels=self.show_labels,
        )

        self.bottom_bus = self.add(elm.Line(color=color).endpoints(A["cap_bot"], A["ind_bot"]))
        self.ground = self.add(elm.Ground(color=color).at(A["gnd"]))

        self.physical_nodes = {
            "signal": ["signal", "cap_top", "ind_top"],
            "gnd": ["cap_bot", "ind_bot", "gnd"],
        }
        self.ports = {"signal": "signal"}
        self.elmparams["drop"] = A["end"]


class FloatingLCResonator(elm.ElementCompound):
    """Floating LC resonator with two physical nodes and ground parasitics."""

    component_kind: ClassVar[str] = "FloatingLCResonator"

    def __init__(
        self,
        *,
        component_id: str = "",
        name: str | None = None,
        unit_length: float = 3.0,
        width_units: float = 1.5,
        height_units: float = 1.25,
        theme: Theme = "light",
        inductive_branch_kind: InductiveBranchKind = "linear",
        c_01_label: str | None = None,
        c_02_label: str | None = None,
        c_r_label: str | None = None,
        l_label: str | None = None,
        junction_label: str | None = None,
        squid_label: str | None = None,
        upper_port_label: str | None = None,
        lower_port_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.name = component_id if name is None else name
        self.unit_length = unit_length
        self.width_units = width_units
        self.height_units = height_units
        self.width = unit_length * width_units
        self.height = unit_length * height_units
        self.theme: Theme = theme
        self.inductive_branch_kind: InductiveBranchKind = inductive_branch_kind
        self.c_01_label = c_01_label if c_01_label is not None else r"$C_{01}$"
        self.c_02_label = c_02_label if c_02_label is not None else r"$C_{02}$"
        self.c_r_label = c_r_label if c_r_label is not None else r"$C_r$"
        self.branch_label = _branch_label(
            kind=inductive_branch_kind,
            l_label=l_label if l_label is not None else r"$L_r$",
            junction_label=junction_label,
            squid_label=squid_label,
        )
        self.upper_port_label = upper_port_label
        self.lower_port_label = lower_port_label
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        self.labels = {
            "c_01": self.c_01_label,
            "c_02": self.c_02_label,
            "c_r": self.c_r_label,
            "inductive_branch": self.branch_label,
            "upper_port": self.upper_port_label,
            "lower_port": self.lower_port_label,
        }
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        w = self.width
        h = self.height
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        ground_offset = u * 0.75
        cap_x = w * 0.18
        branch_x = w

        A = {
            "start": (0, 0),
            "end": (branch_x, 0),
            "upper": (0, 0),
            "lower": (0, -h),
            "upper_bus_end": (branch_x, 0),
            "lower_bus_end": (branch_x, -h),
            "c_01_top": (cap_x, 0),
            "c_01_bot": (cap_x, ground_offset),
            "c_02_top": (cap_x, -h),
            "c_02_bot": (cap_x, -h - ground_offset),
            "c_r_top": (w * 0.45, 0),
            "c_r_bot": (w * 0.45, -h),
            "branch_top": (branch_x, 0),
            "branch_bot": (branch_x, -h),
            "gnd_upper": (cap_x, ground_offset),
            "gnd_lower": (cap_x, -h - ground_offset),
        }
        self.anchors.update(A)

        if self.show_nodes:
            self.upper_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["upper"]))
            self.lower_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["lower"]))
            self.branch_top_dot = self.add(
                elm.Dot(radius=dot_radius, color=color).at(A["branch_top"])
            )
            self.branch_bot_dot = self.add(
                elm.Dot(radius=dot_radius, color=color).at(A["branch_bot"])
            )

        self.upper_bus = self.add(elm.Line(color=color).endpoints(A["upper"], A["upper_bus_end"]))
        self.lower_bus = self.add(elm.Line(color=color).endpoints(A["lower"], A["lower_bus_end"]))

        self.c_01 = self._two_terminal(
            elm.Capacitor, A["c_01_top"], A["c_01_bot"], self.c_01_label, "top"
        )
        self.c_02 = self._two_terminal(
            elm.Capacitor,
            A["c_02_top"],
            A["c_02_bot"],
            self.c_02_label,
            "bottom",
        )
        self.ground_upper = self.add(elm.Ground(color=color).at(A["gnd_upper"]).up())
        self.ground_lower = self.add(elm.Ground(color=color).at(A["gnd_lower"]))
        self.c_r = self._two_terminal(
            elm.Capacitor, A["c_r_top"], A["c_r_bot"], self.c_r_label, "top"
        )
        _add_inductive_branch_primitives(
            self,
            branch_kind=self.inductive_branch_kind,
            top=A["branch_top"],
            bottom=A["branch_bot"],
            label=self.branch_label,
            color=color,
            unit_length=self.unit_length,
            show_labels=self.show_labels,
        )

        self.physical_nodes = {
            "upper": ["upper", "c_01_top", "c_r_top", "branch_top"],
            "lower": ["lower", "c_02_top", "c_r_bot", "branch_bot"],
            "gnd": ["c_01_bot", "c_02_bot", "gnd_upper", "gnd_lower"],
        }
        self.ports = {"upper": "upper", "lower": "lower"}
        self.elmparams["drop"] = A["end"]

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


class CapacitivelyCoupledGroundedLCResonator(elm.ElementCompound):
    """Grounded resonator capacitively coupled to a 50 ohm port node."""

    component_kind: ClassVar[str] = "CapacitivelyCoupledGroundedLCResonator"

    def __init__(
        self,
        *,
        component_id: str = "",
        name: str | None = None,
        unit_length: float = 3.0,
        spacing_units: float = 1.15,
        height_units: float = 1.0,
        theme: Theme = "light",
        inductive_branch_kind: InductiveBranchKind = "josephson",
        coupling_label: str | None = None,
        c_label: str | None = None,
        l_label: str | None = None,
        junction_label: str | None = None,
        squid_label: str | None = None,
        port_label: str | None = None,
        resistance_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.name = component_id if name is None else name
        self.unit_length = unit_length
        self.spacing_units = spacing_units
        self.height_units = height_units
        self.spacing = unit_length * spacing_units
        self.height = unit_length * height_units
        self.theme: Theme = theme
        self.inductive_branch_kind: InductiveBranchKind = inductive_branch_kind
        self.coupling_label = coupling_label if coupling_label is not None else r"$C_c$"
        self.c_label = c_label if c_label is not None else r"$C_r$"
        self.branch_label = _branch_label(
            kind=inductive_branch_kind,
            l_label=l_label if l_label is not None else r"$L_r$",
            junction_label=junction_label,
            squid_label=squid_label,
        )
        self.port_label = port_label
        self.resistance_label = resistance_label if resistance_label is not None else r"$R_{50}$"
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        self.labels = {
            "coupling": self.coupling_label,
            "capacitance": self.c_label,
            "inductive_branch": self.branch_label,
            "port": self.port_label,
            "resistance": self.resistance_label,
        }
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        w = self.spacing
        h = self.height
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS

        A = {
            "start": (0, 0),
            "end": (2 * w + u * 0.55, 0),
            "resonator": (0, 0),
            "branch_top": (w, 0),
            "port_node": (2 * w, 0),
            "port_terminal": (2 * w + u * 0.55, 0),
            "cap_ground": (0, -h),
            "branch_ground": (w, -h),
            "gnd_left": (0, -h),
            "gnd_right": (w, -h),
            "gnd": (w / 2, -h),
        }
        self.anchors.update(A)

        self.port = self.add(
            Port50Ohm(
                unit_length=self.unit_length,
                side="right",
                theme=self.theme,
                port_label=self.port_label,
                resistance_label=self.resistance_label,
                show_labels=self.show_labels,
            ).at(A["port_node"])
        )

        coupling = elm.Capacitor(color=color).endpoints(A["branch_top"], A["port_node"])
        if self.show_labels:
            coupling = coupling.label(self.coupling_label, loc="top", color=color)
        self.coupling_capacitor = self.add(coupling)
        self.resonator_bus = self.add(
            elm.Line(color=color).endpoints(A["resonator"], A["branch_top"])
        )
        if self.show_nodes:
            self.resonator_dot = self.add(
                elm.Dot(radius=dot_radius, color=color).at(A["resonator"])
            )
            self.branch_top_dot = self.add(
                elm.Dot(radius=dot_radius, color=color).at(A["branch_top"])
            )

        shunt_cap = elm.Capacitor(color=color).endpoints(A["resonator"], A["cap_ground"])
        if self.show_labels:
            shunt_cap = shunt_cap.label(self.c_label, loc="top", color=color)
        self.resonator_capacitor = self.add(shunt_cap)

        _add_inductive_branch_primitives(
            self,
            branch_kind=self.inductive_branch_kind,
            top=A["branch_top"],
            bottom=A["branch_ground"],
            label=self.branch_label,
            color=color,
            unit_length=self.unit_length,
            show_labels=self.show_labels,
        )
        self.ground_bus = self.add(elm.Line(color=color).endpoints(A["gnd_left"], A["gnd_right"]))
        self.ground = self.add(elm.Ground(color=color).at(A["gnd"]))

        self.physical_nodes = {
            "port": ["port_node", "port_terminal"],
            "resonator": ["resonator", "branch_top"],
            "gnd": ["cap_ground", "branch_ground", "gnd_left", "gnd_right", "gnd"],
        }
        self.ports = {"signal": "port"}
        self.elmparams["drop"] = A["end"]


class FloatingLCXYResonator(elm.ElementCompound):
    """Floating LC resonator with an XY coupling node."""

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
        inductive_branch_kind: InductiveBranchKind = "linear",
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
        port_resistance_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
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
        self.inductive_branch_kind: InductiveBranchKind = inductive_branch_kind
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
        self.port_resistance_label = (
            port_resistance_label if port_resistance_label is not None else r"$R_{50}$"
        )
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        self.labels = {
            "c_g1": self.c_g1_label,
            "c_g2": self.c_g2_label,
            "c_q": self.c_q_label,
            "l_q1": self.l_q1_label,
            "l_q2": self.l_q2_label,
            "c_xy1": self.c_xy1_label,
            "c_xy2": self.c_xy2_label,
            "pad1": self.pad1_label,
            "pad2": self.pad2_label,
            "xy": self.xy_label,
            "port_resistance": self.port_resistance_label,
        }
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        w = self.width
        h = self.height
        xy_dx = self.xy_offset
        stub = self.port_stub
        color = theme_color(self.theme)
        if self.inductive_branch_kind not in {"linear", "josephson"}:
            raise UnsupportedInductiveBranchError(
                "FloatingLCXYResonator supports linear or Josephson inductance loops."
            )
        loop_element_kind: InductanceLoopElementKind = (
            "linear" if self.inductive_branch_kind == "linear" else "josephson"
        )

        c_q_x = w * 0.28
        inductor_branch_x = w * 0.66
        inductor_branch_width = u * 0.55
        cap_stem = u * 0.14
        pad1 = (0, 0)
        pad2 = (0, -h)
        xy_x = w + xy_dx
        y_mid = -h / 2
        xy = (xy_x, y_mid)
        upper_gnd_y = u * 0.75
        lower_gnd_y = -h - u * 0.75

        A = {
            "start": (-2 * stub, 0),
            "end": (xy_x + 2 * stub, y_mid),
            "pad1_port": (-2 * stub, 0),
            "pad1_port_node": (-stub, 0),
            "pad2_port": (-2 * stub, -h),
            "pad2_port_node": (-stub, -h),
            "xy_port": (xy_x + 2 * stub, y_mid),
            "xy_port_node": (xy_x + stub, y_mid),
            "pad1": pad1,
            "pad2": pad2,
            "xy": xy,
            "top_bus_end": (w, 0),
            "bottom_bus_end": (w, -h),
            "c_q_top": (c_q_x, 0),
            "c_q_cap_top": (c_q_x, -cap_stem),
            "c_q_cap_bot": (c_q_x, -h + cap_stem),
            "c_q_bot": (c_q_x, -h),
            "inductance_loop_top": (inductor_branch_x, 0),
            "inductance_loop_bot": (inductor_branch_x, -h),
            "l_q1_top": (inductor_branch_x - inductor_branch_width / 2, -u * 0.18),
            "l_q1_bot": (inductor_branch_x - inductor_branch_width / 2, -h + u * 0.18),
            "l_q2_top": (inductor_branch_x + inductor_branch_width / 2, -u * 0.18),
            "l_q2_bot": (inductor_branch_x + inductor_branch_width / 2, -h + u * 0.18),
            "c_g1_top": pad1,
            "c_g1_bot": (0, upper_gnd_y),
            "c_g2_top": pad2,
            "c_g2_bot": (0, lower_gnd_y),
            "gnd1": (0, upper_gnd_y),
            "gnd2": (0, lower_gnd_y),
            "c_xy1_left": (w, 0),
            "c_xy2_left": (w, -h),
        }
        self.anchors.update(A)

        self.pad1_port_terminal = self.add(
            Port50Ohm(
                component_id=f"{self.component_id}_pad1_port",
                unit_length=self.unit_length,
                side="left",
                stub_units=self.port_stub_units,
                height_units=0.8,
                load_direction="up",
                theme=self.theme,
                port_label=self.pad1_label,
                resistance_label=self.port_resistance_label,
                resistance_label_loc="top",
                show_nodes=self.show_nodes,
                show_labels=self.show_labels,
            ).at(A["pad1_port_node"])
        )
        self.pad2_port_terminal = self.add(
            Port50Ohm(
                component_id=f"{self.component_id}_pad2_port",
                unit_length=self.unit_length,
                side="left",
                stub_units=self.port_stub_units,
                height_units=0.8,
                load_direction="down",
                theme=self.theme,
                port_label=self.pad2_label,
                resistance_label=self.port_resistance_label,
                resistance_label_loc="top",
                show_nodes=self.show_nodes,
                show_labels=self.show_labels,
            ).at(A["pad2_port_node"])
        )
        self.xy_port_terminal = self.add(
            Port50Ohm(
                component_id=f"{self.component_id}_xy_port",
                unit_length=self.unit_length,
                side="right",
                stub_units=self.port_stub_units,
                height_units=0.8,
                load_direction="down",
                theme=self.theme,
                port_label=self.xy_label,
                resistance_label=self.port_resistance_label,
                show_nodes=self.show_nodes,
                show_labels=self.show_labels,
            ).at(A["xy_port_node"])
        )

        self.pad1_port_connection = self.add(
            elm.Line(color=color).endpoints(A["pad1_port_node"], A["pad1"])
        )
        self.pad2_port_connection = self.add(
            elm.Line(color=color).endpoints(A["pad2_port_node"], A["pad2"])
        )
        self.xy_port_connection = self.add(
            elm.Line(color=color).endpoints(A["xy"], A["xy_port_node"])
        )
        self.top_bus = self.add(elm.Line(color=color).endpoints(A["pad1"], A["top_bus_end"]))
        self.bottom_bus = self.add(elm.Line(color=color).endpoints(A["pad2"], A["bottom_bus_end"]))
        self.c_q = self._stemmed_two_terminal(
            elm.Capacitor,
            A["c_q_top"],
            A["c_q_cap_top"],
            A["c_q_cap_bot"],
            A["c_q_bot"],
            self.c_q_label,
            "top",
        )
        self.parallel_inductor_branch = self.add(
            InductanceLoop(
                component_id=f"{self.component_id}_inductance_loop",
                element_kind=loop_element_kind,
                unit_length=self.unit_length,
                width_units=inductor_branch_width / u,
                height_units=self.height_units,
                theme=self.theme,
                left_label=self.l_q1_label,
                right_label=self.l_q2_label,
                show_nodes=self.show_nodes,
                show_labels=self.show_labels,
            )
            .at(A["inductance_loop_top"])
            .theta(0)
        )
        self.c_g1 = self._two_terminal(
            elm.Capacitor, A["c_g1_top"], A["c_g1_bot"], self.c_g1_label, "bottom"
        )
        self.c_g2 = self._two_terminal(
            elm.Capacitor, A["c_g2_top"], A["c_g2_bot"], self.c_g2_label, "bottom"
        )
        self.ground1 = self.add(elm.Ground(color=color).at(A["gnd1"]).up())
        self.ground2 = self.add(elm.Ground(color=color).at(A["gnd2"]))
        self.c_xy1 = self._two_terminal(
            elm.Capacitor, A["c_xy1_left"], A["xy"], self.c_xy1_label, "top"
        )
        self.c_xy2 = self._two_terminal(
            elm.Capacitor,
            A["c_xy2_left"],
            A["xy"],
            self.c_xy2_label,
            "bottom",
        )

        self.physical_nodes = {
            "pad1": [
                "pad1_port",
                "pad1_port_node",
                "pad1",
                "c_q_top",
                "c_q_cap_top",
                "inductance_loop_top",
                "l_q1_top",
                "l_q2_top",
                "c_g1_top",
            ],
            "pad2": [
                "pad2_port",
                "pad2_port_node",
                "pad2",
                "c_q_bot",
                "c_q_cap_bot",
                "inductance_loop_bot",
                "l_q1_bot",
                "l_q2_bot",
                "c_g2_top",
            ],
            "xy": ["xy", "xy_port_node", "xy_port"],
            "gnd": ["c_g1_bot", "c_g2_bot", "gnd1", "gnd2"],
        }
        self.ports = {"pad1": "pad1", "pad2": "pad2", "xy": "xy"}
        self.elmparams["drop"] = A["end"]

    def _stemmed_two_terminal(
        self,
        element_type: type[elm.Element],
        top_node: tuple[float, float],
        element_top: tuple[float, float],
        element_bot: tuple[float, float],
        bottom_node: tuple[float, float],
        label: str,
        loc: str,
    ) -> elm.Element:
        color = theme_color(self.theme)
        self.add(elm.Line(color=color).endpoints(top_node, element_top))
        element = element_type(color=color).endpoints(element_top, element_bot)
        if self.show_labels:
            element = element.label(label, loc=loc, color=color)
        added = self.add(element)
        self.add(elm.Line(color=color).endpoints(element_bot, bottom_node))
        return added

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


PREVIEW_CASES: tuple[PreviewCase, ...] = (
    PreviewCase(
        "inductive_branch_linear",
        lambda theme, unit_length: InductiveBranch(
            branch_kind="linear",
            unit_length=unit_length,
            theme=theme,
            l_label=r"$L_r$",
        ),
    ),
    PreviewCase(
        "inductive_branch_josephson",
        lambda theme, unit_length: InductiveBranch(
            branch_kind="josephson",
            unit_length=unit_length,
            theme=theme,
            junction_label=r"$JJ$",
        ),
    ),
    PreviewCase(
        "inductive_branch_squid",
        lambda theme, unit_length: InductiveBranch(
            branch_kind="squid",
            unit_length=unit_length,
            theme=theme,
            squid_label=r"$SQUID$",
        ),
    ),
    PreviewCase(
        "inductance_loop_linear",
        lambda theme, unit_length: InductanceLoop(
            component_id="linear_loop",
            element_kind="linear",
            unit_length=unit_length,
            theme=theme,
            left_label=r"$L_{q1}$",
            right_label=r"$L_{q2}$",
        ),
    ),
    PreviewCase(
        "inductance_loop_josephson",
        lambda theme, unit_length: InductanceLoop(
            component_id="josephson_loop",
            element_kind="josephson",
            unit_length=unit_length,
            theme=theme,
            left_label=r"$JJ_1$",
            right_label=r"$JJ_2$",
        ),
    ),
    PreviewCase(
        "grounded_lc",
        lambda theme, unit_length: GroundedLCResonator(
            component_id="grounded_lc",
            name="r",
            unit_length=unit_length,
            theme=theme,
        ),
    ),
    PreviewCase(
        "floating_lc",
        lambda theme, unit_length: FloatingLCResonator(
            component_id="floating_lc",
            unit_length=unit_length,
            theme=theme,
            upper_port_label=r"$P_1$",
            lower_port_label=r"$P_2$",
        ),
    ),
    PreviewCase(
        "capacitively_coupled_grounded_lc",
        lambda theme, unit_length: CapacitivelyCoupledGroundedLCResonator(
            component_id="reflective_jpa",
            unit_length=unit_length,
            theme=theme,
            port_label=r"$P$",
        ),
    ),
    PreviewCase(
        "floating_lc_xy",
        lambda theme, unit_length: FloatingLCXYResonator(
            component_id="floating_lc_xy",
            unit_length=unit_length,
            theme=theme,
            pad1_label=r"$P_1$",
            pad2_label=r"$P_2$",
            xy_label=r"$XY$",
        ),
    ),
)


def main(argv: list[str] | None = None) -> int:
    return run_preview_cli(module_name="lumped_resonators", cases=PREVIEW_CASES, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CapacitivelyCoupledGroundedLCResonator",
    "FloatingLCResonator",
    "FloatingLCXYResonator",
    "GroundedLCResonator",
    "InductanceLoop",
    "InductanceLoopElementKind",
    "InductiveBranch",
    "InductiveBranchKind",
    "UnsupportedInductiveBranchError",
]
