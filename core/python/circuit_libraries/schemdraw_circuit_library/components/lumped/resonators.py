from __future__ import annotations

from math import isclose
from typing import Any, ClassVar, Literal

import schemdraw.elements as elm

from schemdraw_circuit_library.components.ports import Port50Ohm, PortTerminal
from schemdraw_circuit_library.labels import named_math_label
from schemdraw_circuit_library.metadata import (
    BusSpec,
    ConnectionMarkerSpec,
    NodeLabelSpec,
    NodeMarkerSpec,
    TerminalSpec,
    public_terminal_point,
    render_connection_markers,
    render_physical_node_labels,
    validate_component_metadata,
)
from schemdraw_circuit_library.rendering.preview import PreviewCase, run_preview_cli
from schemdraw_circuit_library.theme import SCHEMATIC_DOT_RADIUS, Theme, theme_color

type InductiveBranchKind = Literal[
    "linear",
    "linearized_josephson",
    "josephson",
    "squid",
]
type InductiveBranchDirection = Literal["down", "right"]
type InductanceLoopElementKind = Literal["linear", "josephson"]


class UnsupportedInductiveBranchError(ValueError):
    """Raised when a renderer export asks for an unsupported branch kind."""


def _same_point(left: tuple[float, float], right: tuple[float, float]) -> bool:
    return all(isclose(a, b, abs_tol=1e-12) for a, b in zip(left, right, strict=True))


def _branch_label(
    *,
    kind: InductiveBranchKind,
    l_label: str | None,
    junction_label: str | None,
    squid_label: str | None,
) -> str:
    if kind in {"linear", "linearized_josephson"}:
        return l_label if l_label is not None else r"$L$"
    if kind == "josephson":
        return junction_label if junction_label is not None else r"$JJ$"
    if kind == "squid":
        return squid_label if squid_label is not None else r"$SQUID$"
    raise UnsupportedInductiveBranchError(f"Unsupported inductive branch kind: {kind!r}")


class InductiveBranch(elm.ElementCompound):
    """Topology-stable visual branch for linear and Josephson variants."""

    component_kind: ClassVar[str] = "InductiveBranch"

    def __init__(
        self,
        *,
        branch_kind: InductiveBranchKind = "linear",
        direction: InductiveBranchDirection = "down",
        unit_length: float = 3.0,
        height_units: float = 1.0,
        squid_width_units: float = 1.0,
        theme: Theme = "light",
        l_label: str | None = None,
        junction_label: str | None = None,
        squid_label: str | None = None,
        squid_left_label: str | None = None,
        squid_right_label: str | None = None,
        show_nodes: bool = True,
        show_terminals: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.branch_kind: InductiveBranchKind = branch_kind
        self.direction: InductiveBranchDirection = direction
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
        self.squid_left_label = squid_left_label
        self.squid_right_label = squid_right_label
        self.show_nodes = show_nodes
        self.show_terminals = show_terminals
        self.show_labels = show_labels
        self.labels = {"branch": self.branch_label}
        super().__init__(**kwargs)

    def setup(self) -> None:
        h = self.height
        offset = self.squid_width / 2
        lead = min(self.unit_length * 0.22, h * 0.24)
        color = theme_color(self.theme)
        if self.direction == "down":
            end = (0, -h)
            loop_start = (0, -lead)
            loop_end = (0, -h + lead)
            squid_terminals = (
                (-offset, -lead),
                (-offset, -h + lead),
                (offset, -lead),
                (offset, -h + lead),
            )
            squid_label_positions = (
                (-offset - self.unit_length * 0.38, -h / 2),
                (offset + self.unit_length * 0.38, -h / 2),
            )
        elif self.direction == "right":
            end = (h, 0)
            loop_start = (lead, 0)
            loop_end = (h - lead, 0)
            squid_terminals = (
                (lead, offset),
                (h - lead, offset),
                (lead, -offset),
                (h - lead, -offset),
            )
            squid_label_positions = (
                (h / 2, offset + self.unit_length * 0.30),
                (h / 2, -offset - self.unit_length * 0.30),
            )
        else:
            raise ValueError(f"Unsupported inductive branch direction: {self.direction!r}")

        A = {
            "start": (0, 0),
            "end": end,
            "top": (0, 0),
            "bottom": end,
            "loop_start": loop_start,
            "loop_end": loop_end,
            "squid_left_top": squid_terminals[0],
            "squid_left_bottom": squid_terminals[1],
            "squid_right_top": squid_terminals[2],
            "squid_right_bottom": squid_terminals[3],
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
        elif self.branch_kind in {"linearized_josephson", "squid"}:
            self.start_lead = self.add(
                elm.Line(color=color).endpoints(A["top"], A["loop_start"])
            )
            self.end_lead = self.add(
                elm.Line(color=color).endpoints(A["loop_end"], A["bottom"])
            )
            self.top_bus = self.add(
                elm.Line(color=color).endpoints(A["squid_left_top"], A["squid_right_top"])
            )
            self.bottom_bus = self.add(
                elm.Line(color=color).endpoints(
                    A["squid_left_bottom"],
                    A["squid_right_bottom"],
                )
            )
            element_type: type[elm.Element] = (
                elm.Josephson
                if self.branch_kind == "squid"
                else elm.Inductor
            )
            left = element_type(color=color).endpoints(
                A["squid_left_top"],
                A["squid_left_bottom"],
            )
            right = element_type(color=color).endpoints(
                A["squid_right_top"],
                A["squid_right_bottom"],
            )
            self.left_branch = self.add(left)
            self.right_branch = self.add(right)
            if self.branch_kind == "squid":
                self.left_junction = self.left_branch
                self.right_junction = self.right_branch
            else:
                self.left_inductor = self.left_branch
                self.right_inductor = self.right_branch
            if self.show_labels and self.squid_left_label is not None:
                self.add(
                    elm.Label(self.squid_left_label, color=color).at(
                        squid_label_positions[0]
                    )
                )
            if self.show_labels:
                self.add(
                    elm.Label(
                        self.squid_right_label or self.branch_label,
                        color=color,
                    ).at(squid_label_positions[1])
                )
        else:
            raise UnsupportedInductiveBranchError(
                f"Unsupported inductive branch kind: {self.branch_kind!r}"
            )

        if self.branch_kind in {"linearized_josephson", "squid"}:
            self.physical_nodes = {
                "top": [
                    "top",
                    "loop_start",
                    "squid_left_top",
                    "squid_right_top",
                ],
                "bottom": [
                    "bottom",
                    "loop_end",
                    "squid_left_bottom",
                    "squid_right_bottom",
                ],
            }
            self.buses = {
                "top_lead": BusSpec("top", ("top", "loop_start")),
                "top_internal": BusSpec(
                    "top",
                    ("squid_left_top", "loop_start", "squid_right_top"),
                ),
                "bottom_internal": BusSpec(
                    "bottom",
                    ("squid_left_bottom", "loop_end", "squid_right_bottom"),
                ),
                "bottom_lead": BusSpec("bottom", ("loop_end", "bottom")),
            }
            self.node_markers = {
                "top_internal": NodeMarkerSpec("top", "loop_start", "junction"),
                "bottom_internal": NodeMarkerSpec(
                    "bottom",
                    "loop_end",
                    "junction",
                ),
            }
        else:
            self.physical_nodes = {"top": ["top"], "bottom": ["bottom"]}
            self.buses = {}
            self.node_markers = {}
        self.ports = {"top": "top", "bottom": "bottom"}
        terminal_facings = (
            ("up", "down") if self.direction == "down" else ("left", "right")
        )
        self.public_terminals = {
            "top": TerminalSpec("top", "top", terminal_facings[0]),
            "bottom": TerminalSpec("bottom", "bottom", terminal_facings[1]),
        }
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
        validate_component_metadata(self)
        markers = []
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(
                    A[spec.anchor],
                    "connected" if spec.role == "connection" else "junction",
                    node=spec.node,
                )
                for spec in self.node_markers.values()
            )
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=SCHEMATIC_DOT_RADIUS,
        )
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
        show_terminals: bool = True,
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
        self.show_terminals = show_terminals
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

        left_branch = element_type(color=color).endpoints(A["left_top"], A["left_bot"])
        right_branch = element_type(color=color).endpoints(A["right_top"], A["right_bot"])
        if self.show_labels:
            left_branch = left_branch.label(self.left_label, loc="bottom", color=color)
            right_branch = right_branch.label(self.right_label, loc="bottom", color=color)
        self.left_branch = self.add(left_branch)
        self.right_branch = self.add(right_branch)
        if self.element_kind == "linear":
            self.left_inductor = self.left_branch
            self.right_inductor = self.right_branch
        else:
            self.left_junction = self.left_branch
            self.right_junction = self.right_branch

        self.physical_nodes = {
            "top": ["top", "loop_top", "left_top", "right_top"],
            "bottom": ["bottom", "loop_bottom", "left_bot", "right_bot"],
        }
        self.ports = {"top": "top", "bottom": "bottom"}
        self.public_terminals = {
            "top": TerminalSpec("top", "top", "up"),
            "bottom": TerminalSpec("bottom", "bottom", "down"),
        }
        self.buses = {
            "top_lead": BusSpec("top", ("top", "loop_top")),
            "top_internal": BusSpec("top", ("left_top", "loop_top", "right_top")),
            "bottom_internal": BusSpec(
                "bottom",
                ("left_bot", "loop_bottom", "right_bot"),
            ),
            "bottom_lead": BusSpec("bottom", ("loop_bottom", "bottom")),
        }
        self.node_markers = {
            "top_internal": NodeMarkerSpec("top", "loop_top", "junction"),
            "bottom_internal": NodeMarkerSpec("bottom", "loop_bottom", "junction"),
        }
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
        validate_component_metadata(self)
        markers = []
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "junction", node=spec.node)
                for spec in self.node_markers.values()
            )
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=SCHEMATIC_DOT_RADIUS,
        )
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
        c0_label: str | None = None,
        c_label: str | None = None,
        l_label: str | None = None,
        junction_label: str | None = None,
        squid_label: str | None = None,
        port_label: str | None = None,
        resistance_label: str | None = None,
        show_nodes: bool = True,
        show_terminals: bool = True,
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
        self.c0_label = c0_label
        self.c_label = c_label if c_label is not None else self._named_label("C")
        self.branch_label = _branch_label(
            kind=inductive_branch_kind,
            l_label=l_label if l_label is not None else self._named_label("L"),
            junction_label=junction_label,
            squid_label=squid_label,
        )
        self.port_label = port_label
        self.resistance_label = resistance_label
        self.show_nodes = show_nodes
        self.show_terminals = show_terminals
        self.show_labels = show_labels
        self.labels = {
            "ground_capacitance": self.c0_label,
            "capacitance": self.c_label,
            "inductive_branch": self.branch_label,
            "port": self.port_label,
            "resistance": self.resistance_label,
        }
        super().__init__(**kwargs)

    def _named_label(self, symbol: str) -> str:
        return named_math_label(symbol, self.name)

    def setup(self) -> None:
        w = self.spacing
        h = self.height
        lead = w / 2
        resonator_offset = w if self.c0_label is not None else 0.0
        color = theme_color(self.theme)
        has_port = self.port_label is not None

        A = {
            "start": (-lead, 0),
            "end": (resonator_offset + w + lead, 0),
            "signal": (-lead, 0),
            "cap_top": (resonator_offset, 0),
            "ind_top": (resonator_offset + w, 0),
            "cap_bot": (resonator_offset, -h),
            "ind_bot": (resonator_offset + w, -h),
            "gnd": (resonator_offset + w / 2, -h),
        }
        if self.c0_label is not None:
            A.update(
                {
                    "c0_top": (0, 0),
                    "c0_bot": (0, -h),
                    "c0_ground": (0, -h),
                }
            )
        self.anchors.update(A)

        if has_port:
            if self.resistance_label is None:
                port = PortTerminal(
                    component_id=f"{self.component_id}_port",
                    unit_length=self.unit_length,
                    side="left",
                    theme=self.theme,
                    port_label=self.port_label,
                    show_nodes=False,
                    show_labels=self.show_labels,
                )
            else:
                port = Port50Ohm(
                    component_id=f"{self.component_id}_port",
                    unit_length=self.unit_length,
                    side="left",
                    height_units=0.8,
                    theme=self.theme,
                    port_label=self.port_label,
                    resistance_label=self.resistance_label,
                    resistance_label_loc="top",
                    show_nodes=False,
                    show_labels=self.show_labels,
                )
            self.port = self.add(port.at(A["start"]))

        self.top_bus = self.add(elm.Line(color=color).endpoints(A["start"], A["end"]))

        if self.c0_label is not None:
            c0 = elm.Capacitor(color=color).endpoints(A["c0_top"], A["c0_bot"])
            if self.show_labels:
                c0 = c0.label(self.c0_label, loc="top", color=color)
            self.c0_capacitor = self.add(c0)
            self.c0_ground = self.add(elm.Ground(color=color).at(A["c0_ground"]))

        capacitor = elm.Capacitor(color=color).endpoints(A["cap_top"], A["cap_bot"])
        if self.show_labels:
            capacitor = capacitor.label(self.c_label, loc="top", color=color)
        self.capacitor = self.add(capacitor)

        self.inductive_branch = self.add(
            InductiveBranch(
                branch_kind=self.inductive_branch_kind,
                unit_length=self.unit_length,
                height_units=self.height_units,
                theme=self.theme,
                l_label=self.branch_label,
                junction_label=self.branch_label,
                squid_label=self.branch_label,
                show_nodes=self.show_nodes,
                show_terminals=False,
                show_labels=self.show_labels,
            )
            .at(A["ind_top"])
            .anchor("top")
            .theta(0)
        )
        if not _same_point(
            public_terminal_point(
                self.inductive_branch,
                "bottom",
                transformed=True,
            ),
            A["ind_bot"],
        ):
            raise ValueError("The grounded-LC branch terminals do not span its buses.")

        self.bottom_bus = self.add(elm.Line(color=color).endpoints(A["cap_bot"], A["ind_bot"]))
        self.ground = self.add(elm.Ground(color=color).at(A["gnd"]))

        self.physical_nodes = {
            "signal": ["start", "end", "signal", "cap_top", "ind_top"],
            "gnd": ["cap_bot", "ind_bot", "gnd"],
        }
        if self.c0_label is not None:
            self.physical_nodes["signal"].append("c0_top")
            self.physical_nodes["gnd"].extend(["c0_bot", "c0_ground"])
        self.ports = {"signal": "signal"}
        self.public_terminals = {
            "left": TerminalSpec("signal", "start", "left"),
            "right": TerminalSpec("signal", "end", "right"),
        }
        self.buses = {
            "signal": BusSpec(
                "signal",
                ("start", "cap_top", "ind_top", "end"),
            ),
            "ground": BusSpec("gnd", ("cap_bot", "gnd", "ind_bot")),
        }
        self.node_markers = {
            "capacitor_tap": NodeMarkerSpec("signal", "cap_top", "junction"),
            "inductive_tap": NodeMarkerSpec("signal", "ind_top", "junction"),
        }
        if self.c0_label is not None:
            self.node_markers["ground_capacitor_tap"] = NodeMarkerSpec(
                "signal",
                "c0_top",
                "junction",
            )
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
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
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=SCHEMATIC_DOT_RADIUS,
        )
        self.elmparams["drop"] = A["end"]


class FloatingParallelLC(elm.ElementCompound):
    """Pure two-terminal capacitor parallel to one declared inductive branch."""

    component_kind: ClassVar[str] = "FloatingParallelLC"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        width_units: float = 1.8,
        branch_offset_units: float = 0.55,
        terminal_stub_units: float = 0.4,
        squid_width_units: float = 1.0,
        theme: Theme = "light",
        inductive_branch_kind: InductiveBranchKind = "linear",
        c_label: str = r"$C$",
        l_label: str | None = None,
        junction_label: str | None = None,
        squid_label: str | None = None,
        squid_left_label: str | None = None,
        squid_right_label: str | None = None,
        show_nodes: bool = True,
        show_terminals: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.unit_length = unit_length
        self.width_units = width_units
        self.branch_offset_units = branch_offset_units
        self.terminal_stub_units = terminal_stub_units
        self.squid_width_units = squid_width_units
        self.width = unit_length * width_units
        self.branch_offset = unit_length * branch_offset_units
        self.terminal_stub = unit_length * terminal_stub_units
        self.theme: Theme = theme
        self.inductive_branch_kind: InductiveBranchKind = inductive_branch_kind
        self.c_label = c_label
        self.branch_label = _branch_label(
            kind=inductive_branch_kind,
            l_label=l_label,
            junction_label=junction_label,
            squid_label=squid_label,
        )
        self.squid_left_label = squid_left_label
        self.squid_right_label = squid_right_label
        self.show_nodes = show_nodes
        self.show_terminals = show_terminals
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        w = self.width
        offset = self.branch_offset
        stub = self.terminal_stub
        color = theme_color(self.theme)
        A = {
            "start": (-stub, 0),
            "end": (w + stub, 0),
            "left": (0, 0),
            "right": (w, 0),
            "cap_left": (0, offset),
            "cap_right": (w, offset),
            "branch_left": (0, -offset),
            "branch_right": (w, -offset),
        }
        self.anchors.update(A)

        self.left_stub = self.add(elm.Line(color=color).endpoints(A["start"], A["left"]))
        self.right_stub = self.add(elm.Line(color=color).endpoints(A["right"], A["end"]))
        self.left_bus = self.add(elm.Line(color=color).endpoints(A["cap_left"], A["branch_left"]))
        self.right_bus = self.add(
            elm.Line(color=color).endpoints(A["cap_right"], A["branch_right"])
        )
        capacitor = elm.Capacitor(color=color).endpoints(A["cap_left"], A["cap_right"])
        if self.show_labels:
            capacitor = capacitor.label(self.c_label, loc="top", color=color)
        self.capacitor = self.add(capacitor)
        self.inductive_branch = self.add(
            InductiveBranch(
                branch_kind=self.inductive_branch_kind,
                direction="right",
                unit_length=self.unit_length,
                height_units=self.width_units,
                squid_width_units=self.squid_width_units,
                theme=self.theme,
                l_label=self.branch_label,
                junction_label=self.branch_label,
                squid_label=self.branch_label,
                squid_left_label=self.squid_left_label,
                squid_right_label=self.squid_right_label,
                show_nodes=self.show_nodes,
                show_terminals=False,
                show_labels=self.show_labels,
            )
            .at(A["branch_left"])
            .anchor("top")
            .theta(0)
        )
        if not _same_point(
            public_terminal_point(
                self.inductive_branch,
                "bottom",
                transformed=True,
            ),
            A["branch_right"],
        ):
            raise ValueError("The floating branch terminals do not span its two buses.")
        self.physical_nodes = {
            "left": ["start", "left", "cap_left", "branch_left"],
            "right": ["end", "right", "cap_right", "branch_right"],
        }
        self.ports = {"left": "left", "right": "right"}
        self.public_terminals = {
            "left": TerminalSpec("left", "start", "left"),
            "right": TerminalSpec("right", "end", "right"),
        }
        self.buses = {
            "left_stub": BusSpec("left", ("start", "left")),
            "left_vertical": BusSpec("left", ("cap_left", "left", "branch_left")),
            "right_stub": BusSpec("right", ("right", "end")),
            "right_vertical": BusSpec("right", ("cap_right", "right", "branch_right")),
        }
        self.node_markers = {
            "left_junction": NodeMarkerSpec("left", "left", "junction"),
            "right_junction": NodeMarkerSpec("right", "right", "junction"),
        }
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
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
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=SCHEMATIC_DOT_RADIUS,
        )
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
        squid_left_label: str | None = None,
        squid_right_label: str | None = None,
        upper_port_label: str | None = None,
        lower_port_label: str | None = None,
        show_nodes: bool = True,
        show_terminals: bool = True,
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
        self.squid_left_label = squid_left_label
        self.squid_right_label = squid_right_label
        self.upper_port_label = upper_port_label
        self.lower_port_label = lower_port_label
        self.show_nodes = show_nodes
        self.show_terminals = show_terminals
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
        ground_offset = u * 0.75
        cap_x = w * 0.60
        parallel_cap_x = w * 0.30
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
            "c_r_top": (parallel_cap_x, 0),
            "c_r_bot": (parallel_cap_x, -h),
            "branch_top": (branch_x, 0),
            "branch_bot": (branch_x, -h),
            "gnd_upper": (cap_x, ground_offset),
            "gnd_lower": (cap_x, -h - ground_offset),
        }
        self.anchors.update(A)

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
        self.ground_upper = self.add(elm.Ground(color=color).at(A["gnd_upper"]).theta(180))
        self.ground_lower = self.add(elm.Ground(color=color).at(A["gnd_lower"]))
        self.c_r = self._two_terminal(
            elm.Capacitor, A["c_r_top"], A["c_r_bot"], self.c_r_label, "top"
        )
        self.inductive_branch = self.add(
            InductiveBranch(
                branch_kind=self.inductive_branch_kind,
                unit_length=self.unit_length,
                height_units=self.height_units,
                theme=self.theme,
                l_label=self.branch_label,
                junction_label=self.branch_label,
                squid_label=self.branch_label,
                squid_left_label=self.squid_left_label,
                squid_right_label=self.squid_right_label,
                show_nodes=self.show_nodes,
                show_terminals=False,
                show_labels=self.show_labels,
            )
            .at(A["branch_top"])
            .anchor("top")
            .theta(0)
        )
        if not _same_point(
            public_terminal_point(
                self.inductive_branch,
                "bottom",
                transformed=True,
            ),
            A["branch_bot"],
        ):
            raise ValueError("The floating-LC branch terminals do not span its buses.")

        self.physical_nodes = {
            "upper": ["upper", "c_01_top", "c_r_top", "branch_top"],
            "lower": ["lower", "c_02_top", "c_r_bot", "branch_bot"],
            "gnd": ["c_01_bot", "c_02_bot", "gnd_upper", "gnd_lower"],
        }
        self.ports = {"upper": "upper", "lower": "lower"}
        self.public_terminals = {
            "upper": TerminalSpec("upper", "upper", "left"),
            "lower": TerminalSpec("lower", "lower", "left"),
        }
        self.buses = {
            "upper": BusSpec(
                "upper",
                ("upper", "c_01_top", "c_r_top", "branch_top"),
            ),
            "lower": BusSpec(
                "lower",
                ("lower", "c_02_top", "c_r_bot", "branch_bot"),
            ),
        }
        self.node_markers = {
            "c01_tap": NodeMarkerSpec("upper", "c_01_top", "junction"),
            "c02_tap": NodeMarkerSpec("lower", "c_02_top", "junction"),
            "c12_upper_tap": NodeMarkerSpec("upper", "c_r_top", "junction"),
            "c12_lower_tap": NodeMarkerSpec("lower", "c_r_bot", "junction"),
            "inductive_upper": NodeMarkerSpec(
                "upper",
                "branch_top",
                "connection",
            ),
            "inductive_lower": NodeMarkerSpec(
                "lower",
                "branch_bot",
                "connection",
            ),
        }
        self.physical_node_labels = {
            node: NodeLabelSpec(label, "terminal", node, loc=loc, offset=0.28)
            for node, label, loc in (
                ("upper", self.upper_port_label, "top"),
                ("lower", self.lower_port_label, "bottom"),
            )
            if self.show_terminals and label is not None
        }
        validate_component_metadata(self)
        markers = []
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(
                    A[spec.anchor],
                    "connected" if spec.role == "connection" else "junction",
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
        if self.show_labels and not getattr(
            self,
            "_defer_physical_node_labels",
            False,
        ):
            render_physical_node_labels(self, color=color)
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
            element = element.label(label, loc=loc, ofst=0.18, color=color)
        return self.add(element)


class LinearizedFloatingQubit(FloatingLCResonator):
    """Floating C12-shunted two-branch linearized qubit."""

    component_kind: ClassVar[str] = "LinearizedFloatingQubit"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        width_units: float = 1.5,
        height_units: float = 1.25,
        theme: Theme = "light",
        c01_label: str = r"$C_{01}$",
        c02_label: str = r"$C_{02}$",
        c12_label: str = r"$C_{12,q}$",
        lj1_label: str = r"$L_{J1}$",
        lj2_label: str = r"$L_{J2}$",
        q1_label: str | None = r"$q_1$",
        q2_label: str | None = r"$q_2$",
        show_nodes: bool = True,
        show_terminals: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self._defer_physical_node_labels = True
        super().__init__(
            component_id=component_id,
            unit_length=unit_length,
            width_units=max(width_units, 3.2),
            height_units=max(height_units, 2.2),
            theme=theme,
            inductive_branch_kind="linearized_josephson",
            c_01_label=c01_label,
            c_02_label=c02_label,
            c_r_label=c12_label,
            l_label=r"$L_J$",
            squid_left_label=lj1_label,
            squid_right_label=lj2_label,
            upper_port_label=q1_label,
            lower_port_label=q2_label,
            show_nodes=show_nodes,
            show_terminals=show_terminals,
            show_labels=show_labels,
            **kwargs,
        )

    def setup(self) -> None:
        super().setup()
        self.ports = {"q1": "upper", "q2": "lower"}
        self.public_terminals = {
            "q1": TerminalSpec("upper", "upper", "left"),
            "q2": TerminalSpec("lower", "lower", "left"),
        }
        self.physical_node_labels = {
            node: NodeLabelSpec(
                spec.text,
                spec.placement,
                "q1" if node == "upper" else "q2",
                loc=spec.loc,
                offset=spec.offset,
            )
            for node, spec in self.physical_node_labels.items()
        }
        del self._defer_physical_node_labels
        validate_component_metadata(self)
        if self.show_labels:
            render_physical_node_labels(self, color=theme_color(self.theme))


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
        show_terminals: bool = True,
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
        self.show_terminals = show_terminals
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
        port_stub_units = 0.55

        A = {
            "start": (0, 0),
            "end": (2 * w + u * port_stub_units, 0),
            "resonator": (0, 0),
            "branch_top": (w, 0),
            "port_node": (2 * w, 0),
            "port_terminal": (2 * w + u * port_stub_units, 0),
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
                stub_units=port_stub_units,
                theme=self.theme,
                port_label=self.port_label,
                resistance_label=self.resistance_label,
                show_nodes=False,
                show_terminals=False,
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
        shunt_cap = elm.Capacitor(color=color).endpoints(A["resonator"], A["cap_ground"])
        if self.show_labels:
            shunt_cap = shunt_cap.label(self.c_label, loc="top", color=color)
        self.resonator_capacitor = self.add(shunt_cap)

        self.inductive_branch = self.add(
            InductiveBranch(
                branch_kind=self.inductive_branch_kind,
                unit_length=self.unit_length,
                height_units=self.height_units,
                theme=self.theme,
                l_label=self.branch_label,
                junction_label=self.branch_label,
                squid_label=self.branch_label,
                show_nodes=self.show_nodes,
                show_terminals=False,
                show_labels=self.show_labels,
            )
            .at(A["branch_top"])
            .theta(0)
        )
        self.ground_bus = self.add(elm.Line(color=color).endpoints(A["gnd_left"], A["gnd_right"]))
        self.ground = self.add(elm.Ground(color=color).at(A["gnd"]))
        if not _same_point(
            public_terminal_point(self.port, "signal", transformed=True),
            A["port_terminal"],
        ):
            raise ValueError("The coupled-LC port terminal does not match its public anchor.")
        if not _same_point(
            public_terminal_point(
                self.inductive_branch,
                "bottom",
                transformed=True,
            ),
            A["branch_ground"],
        ):
            raise ValueError("The coupled-LC branch terminals do not span its buses.")

        self.physical_nodes = {
            "port": ["port_node", "port_terminal"],
            "resonator": ["resonator", "branch_top"],
            "gnd": ["cap_ground", "branch_ground", "gnd_left", "gnd_right", "gnd"],
        }
        self.ports = {"signal": "port"}
        self.public_terminals = {
            "signal": TerminalSpec("port", "port_terminal", "right"),
        }
        self.buses = {
            "resonator": BusSpec("resonator", ("resonator", "branch_top")),
            "port_stub": BusSpec("port", ("port_node", "port_terminal")),
            "ground": BusSpec(
                "gnd",
                ("cap_ground", "gnd_left", "gnd", "gnd_right", "branch_ground"),
            ),
        }
        self.node_markers = {
            "resonator_branch": NodeMarkerSpec(
                "resonator",
                "branch_top",
                "junction",
            ),
            "port_node": NodeMarkerSpec("port", "port_node", "junction"),
        }
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
        validate_component_metadata(self)
        markers = []
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "junction", node=spec.node)
                for spec in self.node_markers.values()
            )
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=SCHEMATIC_DOT_RADIUS,
        )
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
        show_terminals: bool = True,
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
        self.show_terminals = show_terminals
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
            "pad1_port_ground": (-stub, u * 0.8),
            "pad2_port": (-2 * stub, -h),
            "pad2_port_node": (-stub, -h),
            "pad2_port_ground": (-stub, -h - u * 0.8),
            "xy_port": (xy_x + 2 * stub, y_mid),
            "xy_port_node": (xy_x + stub, y_mid),
            "xy_port_ground": (xy_x + stub, y_mid - u * 0.8),
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
                show_nodes=False,
                show_terminals=False,
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
                show_nodes=False,
                show_terminals=False,
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
                show_nodes=False,
                show_terminals=False,
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
                show_terminals=False,
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
        self.ground1 = self.add(elm.Ground(color=color).at(A["gnd1"]).theta(180))
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
                "top_bus_end",
                "c_xy1_left",
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
                "bottom_bus_end",
                "c_xy2_left",
            ],
            "xy": ["xy", "xy_port_node", "xy_port"],
            "gnd": [
                "c_g1_bot",
                "c_g2_bot",
                "gnd1",
                "gnd2",
                "pad1_port_ground",
                "pad2_port_ground",
                "xy_port_ground",
            ],
        }
        self.ports = {"pad1": "pad1", "pad2": "pad2", "xy": "xy"}
        self.public_terminals = {
            "pad1": TerminalSpec("pad1", "pad1_port", "left"),
            "pad2": TerminalSpec("pad2", "pad2_port", "left"),
            "xy": TerminalSpec("xy", "xy_port", "right"),
        }
        self.buses = {
            "pad1_port_stub": BusSpec("pad1", ("pad1_port", "pad1_port_node")),
            "pad1_connection": BusSpec("pad1", ("pad1_port_node", "pad1")),
            "pad1_signal": BusSpec(
                "pad1",
                (
                    "pad1",
                    "c_q_top",
                    "inductance_loop_top",
                    "top_bus_end",
                    "c_xy1_left",
                ),
            ),
            "pad2_port_stub": BusSpec("pad2", ("pad2_port", "pad2_port_node")),
            "pad2_connection": BusSpec("pad2", ("pad2_port_node", "pad2")),
            "pad2_signal": BusSpec(
                "pad2",
                (
                    "pad2",
                    "c_q_bot",
                    "inductance_loop_bot",
                    "bottom_bus_end",
                    "c_xy2_left",
                ),
            ),
            "xy_connection": BusSpec("xy", ("xy", "xy_port_node", "xy_port")),
        }
        self.node_markers = {
            "pad1_port_node": NodeMarkerSpec(
                "pad1",
                "pad1_port_node",
                "junction",
            ),
            "pad2_port_node": NodeMarkerSpec(
                "pad2",
                "pad2_port_node",
                "junction",
            ),
            "xy_port_node": NodeMarkerSpec("xy", "xy_port_node", "junction"),
            "pad1": NodeMarkerSpec("pad1", "pad1", "junction"),
            "pad2": NodeMarkerSpec("pad2", "pad2", "junction"),
            "c_q_top": NodeMarkerSpec("pad1", "c_q_top", "junction"),
            "c_q_bottom": NodeMarkerSpec("pad2", "c_q_bot", "junction"),
            "inductance_loop_top": NodeMarkerSpec(
                "pad1",
                "inductance_loop_top",
                "junction",
            ),
            "inductance_loop_bottom": NodeMarkerSpec(
                "pad2",
                "inductance_loop_bot",
                "junction",
            ),
            "xy": NodeMarkerSpec("xy", "xy", "junction"),
        }
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
        validate_component_metadata(self)
        for child, terminal, expected in (
            (self.pad1_port_terminal, "signal", A["pad1_port"]),
            (self.pad2_port_terminal, "signal", A["pad2_port"]),
            (self.xy_port_terminal, "signal", A["xy_port"]),
        ):
            if not _same_point(
                public_terminal_point(child, terminal, transformed=True),
                expected,
            ):
                raise ValueError("A floating-LC port terminal does not match its public anchor.")
        markers = []
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "junction", node=spec.node)
                for spec in self.node_markers.values()
            )
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=SCHEMATIC_DOT_RADIUS,
        )
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
        "floating_parallel_lc_squid",
        lambda theme, unit_length: FloatingParallelLC(
            component_id="floating_parallel_lc_squid",
            unit_length=unit_length,
            theme=theme,
            inductive_branch_kind="squid",
            c_label=r"$C$",
            squid_left_label=r"$JJ_1$",
            squid_right_label=r"$JJ_2$",
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
        "linearized_floating_qubit",
        lambda theme, unit_length: LinearizedFloatingQubit(
            component_id="linearized_floating_qubit",
            unit_length=unit_length,
            theme=theme,
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
    "FloatingParallelLC",
    "GroundedLCResonator",
    "InductanceLoop",
    "InductanceLoopElementKind",
    "InductiveBranch",
    "InductiveBranchKind",
    "LinearizedFloatingQubit",
    "UnsupportedInductiveBranchError",
]
