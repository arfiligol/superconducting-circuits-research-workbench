from __future__ import annotations

from collections.abc import Mapping
from typing import Any, ClassVar

import schemdraw.elements as elm

from schemdraw_circuit_library.components.couplers import InterdigitatedCapacitor
from schemdraw_circuit_library.components.lumped import (
    FloatingParallelLC,
    GroundedLCResonator,
    InductiveBranchKind,
    LinearizedFloatingQubit,
)
from schemdraw_circuit_library.metadata import (
    BusSpec,
    ConnectionMarkerSpec,
    NodeLabelSpec,
    NodeMarkerSpec,
    TerminalSpec,
    public_terminal_point,
    render_connection_markers,
    render_physical_node_labels,
    validate_block_clearance,
    validate_component_metadata,
)
from schemdraw_circuit_library.rendering.preview import PreviewCase, run_preview_cli
from schemdraw_circuit_library.theme import SCHEMATIC_DOT_RADIUS, Theme, theme_color

if __package__:
    from .pi_sections import TransmissionLineSegment
else:
    from pi_sections import TransmissionLineSegment


class PointCoupledReadoutPurcell(elm.ElementCompound):
    """Input CPW, Purcell/filter CPW, and output CPW with localized capacitive coupling."""

    component_kind: ClassVar[str] = "PointCoupledReadoutPurcell"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        line_units: float = 1.45,
        filter_units: float = 2.2,
        track_gap_units: float = 0.9,
        port_stub_units: float = 0.45,
        theme: Theme = "light",
        input_line_label: str | None = r"$\mathrm{input\ CPW}$",
        filter_label: str | None = r"$\mathrm{filter\ CPW}$",
        output_line_label: str | None = r"$\mathrm{output\ CPW}$",
        input_coupling_label: str = r"$C_{c,\mathrm{in}}$",
        output_coupling_label: str = r"$C_{c,\mathrm{out}}$",
        left_port_label: str | None = None,
        right_port_label: str | None = None,
        show_nodes: bool = True,
        show_terminals: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.unit_length = unit_length
        self.line_length = unit_length * line_units
        self.filter_length = unit_length * filter_units
        self.track_gap = unit_length * track_gap_units
        self.port_stub = unit_length * port_stub_units
        self.theme: Theme = theme
        self.input_line_label = input_line_label
        self.filter_label = filter_label
        self.output_line_label = output_line_label
        self.input_coupling_label = input_coupling_label
        self.output_coupling_label = output_coupling_label
        self.left_port_label = left_port_label
        self.right_port_label = right_port_label
        self.show_nodes = show_nodes
        self.show_terminals = show_terminals
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        line = self.line_length
        filter_len = self.filter_length
        gap = self.track_gap
        stub = self.port_stub
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS

        filter_x0 = line
        output_x0 = filter_x0 + filter_len
        output_x1 = output_x0 + line

        A = {
            "start": (-stub, 0),
            "end": (output_x1 + stub, 0),
            "input_port": (-stub, 0),
            "output_port": (output_x1 + stub, 0),
            "input": (0, 0),
            "input_tail": (line, 0),
            "filter_head": (filter_x0, -gap),
            "filter_tail": (output_x0, -gap),
            "output_head": (output_x0, 0),
            "output": (output_x1, 0),
        }
        self.anchors.update(A)

        self.add(elm.Line(color=color).endpoints(A["input_port"], A["input"]))
        self.add(elm.Line(color=color).endpoints(A["output"], A["output_port"]))
        self._line(A["input"], A["input_tail"], self.input_line_label, "top")
        self._line(A["filter_head"], A["filter_tail"], self.filter_label, "bottom")
        self._line(A["output_head"], A["output"], self.output_line_label, "top")

        self._capacitor(
            A["input_tail"],
            A["filter_head"],
            self.input_coupling_label,
            "bottom",
        )
        self._capacitor(
            A["filter_tail"],
            A["output_head"],
            self.output_coupling_label,
            "bottom",
        )

        self.physical_nodes = {
            "input": ["input_port", "input"],
            "input_tail": ["input_tail"],
            "filter_head": ["filter_head"],
            "filter_tail": ["filter_tail"],
            "output_head": ["output_head"],
            "output": ["output", "output_port"],
        }
        self.ports = {"input": "input", "output": "output"}
        self.public_terminals = {
            "input": TerminalSpec("input", "input_port", "left"),
            "output": TerminalSpec("output", "output_port", "right"),
        }
        self.buses = {
            "input_stub": BusSpec("input", ("input_port", "input")),
            "output_stub": BusSpec("output", ("output", "output_port")),
        }
        self.node_markers: dict[str, NodeMarkerSpec] = {}
        self.physical_node_labels = {
            node: NodeLabelSpec(label, "terminal", terminal, loc=loc)
            for node, terminal, label, loc in (
                ("input", "input", self.left_port_label, "left"),
                ("output", "output", self.right_port_label, "right"),
            )
            if label is not None
        }
        validate_component_metadata(self)
        markers = []
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=dot_radius,
        )
        if self.show_labels:
            render_physical_node_labels(self, color=color)
        self.elmparams["drop"] = A["end"]

    def _line(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        line = elm.Line(color=color).endpoints(start, end)
        if self.show_labels and label is not None:
            line = line.label(label, loc=loc, color=color)
        self.add(line)

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

class ReadoutLineHangingQWRMTL(elm.ElementCompound):
    """Through readout CPW coupled to a grounded-head/open-tail QWR by an MTL window."""

    component_kind: ClassVar[str] = "ReadoutLineHangingQWRMTL"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        length_units: float = 3.6,
        track_gap_units: float = 1.0,
        window_start_units: float = 1.15,
        window_length_units: float = 0.9,
        port_stub_units: float = 0.45,
        theme: Theme = "light",
        readout_label: str | None = r"$\mathrm{readout\ CPW}$",
        qwr_label: str | None = r"$\lambda/4\ \mathrm{QWR}$",
        capacitive_label: str = r"$C_{12}$",
        inductive_label: str = r"$M_{12}$",
        left_port_label: str | None = None,
        right_port_label: str | None = None,
        show_window_markers: bool = False,
        show_nodes: bool = True,
        show_terminals: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.unit_length = unit_length
        self.length = unit_length * length_units
        self.track_gap = unit_length * track_gap_units
        self.window_start = unit_length * window_start_units
        self.window_length = unit_length * window_length_units
        self.port_stub = unit_length * port_stub_units
        self.theme: Theme = theme
        self.readout_label = readout_label
        self.qwr_label = qwr_label
        self.capacitive_label = capacitive_label
        self.inductive_label = inductive_label
        self.left_port_label = left_port_label
        self.right_port_label = right_port_label
        self.show_window_markers = show_window_markers
        self.show_nodes = show_nodes
        self.show_terminals = show_terminals
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        length = self.length
        gap = self.track_gap
        win0 = self.window_start
        win1 = self.window_start + self.window_length
        stub = self.port_stub
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        relation_margin = u * 0.16

        A = {
            "start": (-stub, 0),
            "end": (length + stub, 0),
            "input_port": (-stub, 0),
            "output_port": (length + stub, 0),
            "readout_head": (0, 0),
            "readout_tail": (length, 0),
            "qwr_grounded_head": (0, -gap),
            "qwr_open_tail": (length, -gap),
            "readout_window_left": (win0, 0),
            "readout_window_right": (win1, 0),
            "qwr_window_left": (win0, -gap),
            "qwr_window_right": (win1, -gap),
            "cap_top": (win0 + self.window_length * 0.42, 0),
            "cap_bottom": (win0 + self.window_length * 0.42, -gap),
            "mutual_top": (win0 + self.window_length * 0.72, -relation_margin),
            "mutual_bottom": (
                win0 + self.window_length * 0.72,
                -gap + relation_margin,
            ),
            "qwr_ground": (0, -gap - u * 0.42),
        }
        self.anchors.update(A)

        self.add(elm.Line(color=color).endpoints(A["input_port"], A["readout_head"]))
        self.add(elm.Line(color=color).endpoints(A["readout_tail"], A["output_port"]))
        self._line(A["readout_head"], A["readout_tail"], self.readout_label, "top")
        self._line(A["qwr_grounded_head"], A["qwr_open_tail"], self.qwr_label, "bottom")
        self.add(elm.Line(color=color).endpoints(A["qwr_grounded_head"], A["qwr_ground"]))
        self.add(elm.Ground(color=color).at(A["qwr_ground"]))

        if self.show_window_markers:
            self._window_marker(A["readout_window_left"], A["qwr_window_left"])
            self._window_marker(A["readout_window_right"], A["qwr_window_right"])
        self._capacitor(A["cap_top"], A["cap_bottom"], self.capacitive_label, "top")
        self._controlled_relation(
            A["mutual_top"],
            A["mutual_bottom"],
            self.inductive_label,
            "bottom",
        )

        self.physical_nodes = {
            "input": ["input_port", "readout_head"],
            "output": ["readout_tail", "output_port"],
            "qwr_grounded_head": ["qwr_grounded_head", "qwr_ground"],
            "qwr_open_tail": ["qwr_open_tail"],
            "readout_coupling": ["cap_top"],
            "qwr_coupling": ["cap_bottom"],
        }
        self.ports = {"input": "input", "output": "output"}
        self.public_terminals = {
            "input": TerminalSpec("input", "input_port", "left"),
            "output": TerminalSpec("output", "output_port", "right"),
        }
        self.buses = {
            "input_stub": BusSpec("input", ("input_port", "readout_head")),
            "output_stub": BusSpec("output", ("readout_tail", "output_port")),
            "qwr_ground_stub": BusSpec(
                "qwr_grounded_head",
                ("qwr_grounded_head", "qwr_ground"),
            ),
        }
        self.node_markers = {
            "readout_coupling": NodeMarkerSpec(
                "readout_coupling",
                "cap_top",
                "junction",
            ),
            "qwr_coupling": NodeMarkerSpec(
                "qwr_coupling",
                "cap_bottom",
                "junction",
            ),
        }
        self.physical_node_labels = {
            node: NodeLabelSpec(label, "terminal", terminal, loc=loc)
            for node, terminal, label, loc in (
                ("input", "input", self.left_port_label, "left"),
                ("output", "output", self.right_port_label, "right"),
            )
            if label is not None
        }
        validate_component_metadata(self)
        markers = []
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(
                    self.anchors[spec.anchor],
                    "junction" if spec.role == "junction" else "connected",
                    node=spec.node,
                )
                for spec in self.node_markers.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=dot_radius,
        )
        if self.show_labels:
            render_physical_node_labels(self, color=color)
        self.elmparams["drop"] = A["end"]

    def _line(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        line = elm.Line(color=color).endpoints(start, end)
        if self.show_labels and label is not None:
            line = line.label(label, loc=loc, color=color)
        self.add(line)

    def _window_marker(
        self,
        top: tuple[float, float],
        bottom: tuple[float, float],
    ) -> None:
        margin = self.unit_length * 0.12
        if top[1] >= bottom[1]:
            start = (top[0], top[1] - margin)
            end = (bottom[0], bottom[1] + margin)
        else:
            start = (top[0], top[1] + margin)
            end = (bottom[0], bottom[1] - margin)
        self.add(elm.Line(color=theme_color(self.theme), ls=":").endpoints(start, end))

    def _capacitor(
        self,
        top: tuple[float, float],
        bottom: tuple[float, float],
        label: str,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        capacitor = elm.Capacitor(color=color).endpoints(top, bottom)
        if self.show_labels:
            capacitor = capacitor.label(label, loc=loc, color=color)
        self.add(capacitor)

    def _controlled_relation(
        self,
        top: tuple[float, float],
        bottom: tuple[float, float],
        label: str,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        relation = elm.Line(color=color, ls="--").endpoints(top, bottom)
        if self.show_labels:
            relation = relation.label(label, loc=loc, color=color)
        self.add(relation)


class ReadoutPurcellHangingQWRMTL(elm.ElementCompound):
    """Point-coupled readout/Purcell chain with a QWR MTL window on the filter line."""

    component_kind: ClassVar[str] = "ReadoutPurcellHangingQWRMTL"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        line_units: float = 1.35,
        filter_units: float = 2.6,
        track_gap_units: float = 0.85,
        qwr_gap_units: float = 1.75,
        window_start_fraction: float = 0.42,
        window_length_units: float = 0.8,
        port_stub_units: float = 0.45,
        theme: Theme = "light",
        left_port_label: str | None = None,
        right_port_label: str | None = None,
        input_line_label: str | None = None,
        filter_label: str | None = r"$\mathrm{filter\ CPW}$",
        output_line_label: str | None = None,
        qwr_label: str | None = r"$\lambda/4\ \mathrm{QWR}$",
        input_coupling_label: str = r"$C_{c,\mathrm{in}}$",
        output_coupling_label: str = r"$C_{c,\mathrm{out}}$",
        capacitive_label: str = r"$C_{12}$",
        inductive_label: str = r"$M_{12}$",
        show_window_markers: bool = False,
        show_nodes: bool = True,
        show_terminals: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.unit_length = unit_length
        self.line_length = unit_length * line_units
        self.filter_length = unit_length * filter_units
        self.track_gap = unit_length * track_gap_units
        self.qwr_gap = unit_length * qwr_gap_units
        self.window_start_fraction = window_start_fraction
        self.window_length = unit_length * window_length_units
        self.port_stub = unit_length * port_stub_units
        self.theme: Theme = theme
        self.left_port_label = left_port_label
        self.right_port_label = right_port_label
        self.input_line_label = input_line_label
        self.filter_label = filter_label
        self.output_line_label = output_line_label
        self.qwr_label = qwr_label
        self.input_coupling_label = input_coupling_label
        self.output_coupling_label = output_coupling_label
        self.capacitive_label = capacitive_label
        self.inductive_label = inductive_label
        self.show_window_markers = show_window_markers
        self.show_nodes = show_nodes
        self.show_terminals = show_terminals
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        line = self.line_length
        filter_len = self.filter_length
        gap = self.track_gap
        qwr_gap = self.qwr_gap
        stub = self.port_stub
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        relation_margin = u * 0.16

        filter_x0 = line
        filter_x1 = filter_x0 + filter_len
        output_x1 = filter_x1 + line
        win0 = filter_x0 + filter_len * self.window_start_fraction
        win1 = win0 + self.window_length

        A = {
            "start": (-stub, 0),
            "end": (output_x1 + stub, 0),
            "input_port": (-stub, 0),
            "output_port": (output_x1 + stub, 0),
            "input": (0, 0),
            "input_tail": (line, 0),
            "filter_head": (filter_x0, -gap),
            "filter_tail": (filter_x1, -gap),
            "output_head": (filter_x1, 0),
            "output": (output_x1, 0),
            "qwr_grounded_head": (filter_x0, -qwr_gap),
            "qwr_open_tail": (filter_x1, -qwr_gap),
            "filter_window_left": (win0, -gap),
            "filter_window_right": (win1, -gap),
            "qwr_window_left": (win0, -qwr_gap),
            "qwr_window_right": (win1, -qwr_gap),
            "cap_top": (win0 + self.window_length * 0.42, -gap),
            "cap_bottom": (win0 + self.window_length * 0.42, -qwr_gap),
            "mutual_top": (
                win0 + self.window_length * 0.72,
                -gap - relation_margin,
            ),
            "mutual_bottom": (
                win0 + self.window_length * 0.72,
                -qwr_gap + relation_margin,
            ),
            "qwr_ground": (filter_x0, -qwr_gap - u * 0.42),
        }
        self.anchors.update(A)

        self.add(elm.Line(color=color).endpoints(A["input_port"], A["input"]))
        self.add(elm.Line(color=color).endpoints(A["output"], A["output_port"]))
        self._line(A["input"], A["input_tail"], self.input_line_label, "top")
        self._line(A["filter_head"], A["filter_tail"], self.filter_label, "bottom")
        self._line(A["output_head"], A["output"], self.output_line_label, "top")
        self._line(
            A["qwr_grounded_head"],
            A["qwr_open_tail"],
            self.qwr_label,
            "bottom",
        )

        self._capacitor(
            A["input_tail"],
            A["filter_head"],
            self.input_coupling_label,
            "bottom",
        )
        self._capacitor(
            A["filter_tail"],
            A["output_head"],
            self.output_coupling_label,
            "bottom",
        )
        self.add(elm.Line(color=color).endpoints(A["qwr_grounded_head"], A["qwr_ground"]))
        self.add(elm.Ground(color=color).at(A["qwr_ground"]))
        if self.show_window_markers:
            self._window_marker(A["filter_window_left"], A["qwr_window_left"])
            self._window_marker(A["filter_window_right"], A["qwr_window_right"])
        self._capacitor(A["cap_top"], A["cap_bottom"], self.capacitive_label, "top")
        self._controlled_relation(
            A["mutual_top"],
            A["mutual_bottom"],
            self.inductive_label,
            "bottom",
        )

        self.physical_nodes = {
            "input": ["input_port", "input"],
            "input_tail": ["input_tail"],
            "filter_head": ["filter_head"],
            "filter_tail": ["filter_tail"],
            "output_head": ["output_head"],
            "output": ["output", "output_port"],
            "qwr_grounded_head": ["qwr_grounded_head", "qwr_ground"],
            "qwr_open_tail": ["qwr_open_tail"],
            "filter_coupling": ["cap_top"],
            "qwr_coupling": ["cap_bottom"],
        }
        self.ports = {"input": "input", "output": "output"}
        self.public_terminals = {
            "input": TerminalSpec("input", "input_port", "left"),
            "output": TerminalSpec("output", "output_port", "right"),
        }
        self.buses = {
            "input_stub": BusSpec("input", ("input_port", "input")),
            "output_stub": BusSpec("output", ("output", "output_port")),
            "qwr_ground_stub": BusSpec(
                "qwr_grounded_head",
                ("qwr_grounded_head", "qwr_ground"),
            ),
        }
        self.node_markers = {
            "filter_coupling": NodeMarkerSpec(
                "filter_coupling",
                "cap_top",
                "junction",
            ),
            "qwr_coupling": NodeMarkerSpec(
                "qwr_coupling",
                "cap_bottom",
                "junction",
            ),
        }
        self.physical_node_labels = {
            node: NodeLabelSpec(label, "terminal", terminal, loc=loc)
            for node, terminal, label, loc in (
                ("input", "input", self.left_port_label, "left"),
                ("output", "output", self.right_port_label, "right"),
            )
            if label is not None
        }
        validate_component_metadata(self)
        markers = []
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(A[spec.anchor], "exposed", node=spec.node)
                for spec in self.public_terminals.values()
            )
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(
                    self.anchors[spec.anchor],
                    "junction" if spec.role == "junction" else "connected",
                    node=spec.node,
                )
                for spec in self.node_markers.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=dot_radius,
        )
        if self.show_labels:
            render_physical_node_labels(self, color=color)
        self.elmparams["drop"] = A["end"]

    def _line(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        line = elm.Line(color=color).endpoints(start, end)
        if self.show_labels and label is not None:
            line = line.label(label, loc=loc, color=color)
        self.add(line)

    def _window_marker(
        self,
        top: tuple[float, float],
        bottom: tuple[float, float],
    ) -> None:
        margin = self.unit_length * 0.12
        if top[1] >= bottom[1]:
            start = (top[0], top[1] - margin)
            end = (bottom[0], bottom[1] + margin)
        else:
            start = (top[0], top[1] + margin)
            end = (bottom[0], bottom[1] - margin)
        self.add(elm.Line(color=theme_color(self.theme), ls=":").endpoints(start, end))

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

    def _controlled_relation(
        self,
        top: tuple[float, float],
        bottom: tuple[float, float],
        label: str,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        relation = elm.Line(color=color, ls="--").endpoints(top, bottom)
        if self.show_labels:
            relation = relation.label(label, loc=loc, color=color)
        self.add(relation)


class CoupledCPWTransmissionLine(elm.ElementCompound):
    """One finite MTL window containing two coupled CPW tracks."""

    component_kind: ClassVar[str] = "CoupledCPWTransmissionLine"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        width_units: float = 1.5,
        track_gap_units: float = 2.4,
        track_height_units: float = 0.8,
        theme: Theme = "light",
        label: str | None = r"$\mathrm{MTL}\ \ell_c$",
        show_label: bool = True,
        show_terminals: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.unit_length = unit_length
        self.width = unit_length * width_units
        self.track_gap = unit_length * track_gap_units
        self.track_height = unit_length * track_height_units
        self.theme: Theme = theme
        self.window_label = label
        self.show_label = show_label
        self.show_terminals = show_terminals
        super().__init__(**kwargs)

    def setup(self) -> None:
        readout_color = "#dc4c4c" if self.theme == "light" else "#fb7185"
        filter_color = "#4774cf" if self.theme == "light" else "#60a5fa"
        window_color = "#8a50d0" if self.theme == "light" else "#c084fc"
        half_height = self.track_height / 2
        lead_length = self.unit_length * 0.5
        total_width = self.width + 2 * lead_length
        readout_start = (0, 0)
        readout_end = (total_width, 0)
        filter_start = (0, -self.track_gap)
        filter_end = (total_width, -self.track_gap)
        box_left = lead_length
        box_right = lead_length + self.width
        self.anchors.update(
            {
                "start": readout_start,
                "end": readout_end,
                "readout_start": readout_start,
                "readout_end": readout_end,
                "filter_start": filter_start,
                "filter_end": filter_end,
            }
        )
        self.add(
            elm.Rect(
                (box_left, half_height),
                (box_right, -self.track_gap - half_height),
                color=window_color,
                lw=2.2,
            )
        )
        for color, y in (
            (readout_color, readout_start[1]),
            (filter_color, filter_start[1]),
        ):
            self.add(
                elm.Line(color=color, lw=3.0).endpoints(
                    (0, y),
                    (box_left, y),
                )
            )
            self.add(
                elm.Line(color=color, lw=3.0).endpoints(
                    (box_right, y),
                    (total_width, y),
                )
            )
        if self.show_label and self.window_label is not None:
            self.add(
                elm.Label(self.window_label, color=window_color).at(
                    (total_width / 2, -self.track_gap / 2)
                )
            )
        self.physical_nodes = {
            "readout_start": ["readout_start"],
            "readout_end": ["readout_end"],
            "filter_start": ["filter_start"],
            "filter_end": ["filter_end"],
        }
        self.ports = {
            "readout_start": "readout_start",
            "readout_end": "readout_end",
            "filter_start": "filter_start",
            "filter_end": "filter_end",
        }
        self.public_terminals = {
            "readout_start": TerminalSpec(
                "readout_start",
                "readout_start",
                "left",
            ),
            "readout_end": TerminalSpec(
                "readout_end",
                "readout_end",
                "right",
            ),
            "filter_start": TerminalSpec(
                "filter_start",
                "filter_start",
                "left",
            ),
            "filter_end": TerminalSpec(
                "filter_end",
                "filter_end",
                "right",
            ),
        }
        self.buses: dict[str, BusSpec] = {}
        self.node_markers: dict[str, NodeMarkerSpec] = {}
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
        validate_component_metadata(self)
        markers = []
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(
                    self.anchors[spec.anchor],
                    "exposed",
                    node=spec.node,
                )
                for spec in self.public_terminals.values()
            )
        render_connection_markers(
            self,
            markers,
            color=theme_color(self.theme),
            radius=SCHEMATIC_DOT_RADIUS,
        )
        self.elmparams["drop"] = readout_end


def _finish_physical_node_labels(component: Any) -> None:
    component.physical_node_labels = component._pending_physical_node_labels
    del component._pending_physical_node_labels
    if hasattr(component, "_defer_physical_node_labels"):
        del component._defer_physical_node_labels
    validate_component_metadata(component)
    if component.show_labels:
        render_physical_node_labels(component, color=theme_color(component.theme))


class IntrinsicInterferometricPurcellFilter(elm.ElementCompound):
    """Two MTL-coupled QWRs with a three-branch feedline-attachment IDC."""

    component_kind: ClassVar[str] = "IntrinsicInterferometricPurcellFilter"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        length_units: float = 6.2,
        track_gap_units: float = 2.4,
        window_start_units: float = 2.15,
        window_length_units: float = 1.65,
        idc_width_units: float = 1.55,
        theme: Theme = "light",
        readout_label: str | None = r"$\lambda/4\ \mathrm{readout}$",
        filter_label: str | None = r"$\lambda/4\ \mathrm{filter}$",
        readout_head_label: str | None = None,
        readout_tail_label: str | None = None,
        filter_head_label: str | None = None,
        filter_tail_label: str | None = None,
        mtl_label: str | None = r"$\mathrm{MTL}\ \ell_c$",
        capacitive_label: str = r"$C_m$",
        inductive_label: str = r"$M$",
        c1g_label: str = r"$C_{1g}$",
        c2g_label: str = r"$C_{2g}$",
        c12_label: str = r"$C_{12}$",
        c0r_label: str | None = None,
        physical_node_labels: Mapping[str, NodeLabelSpec] | None = None,
        show_readout_terminal: bool = True,
        show_window_markers: bool = False,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.unit_length = unit_length
        self.length = unit_length * length_units
        self.track_gap = unit_length * track_gap_units
        self.window_start = unit_length * window_start_units
        self.window_length = unit_length * window_length_units
        self.idc_width_units = idc_width_units
        self.idc_width = unit_length * idc_width_units
        self.theme: Theme = theme
        self.readout_label = readout_label
        self.filter_label = filter_label
        self.readout_head_label = readout_head_label or readout_label
        self.readout_tail_label = readout_tail_label or readout_label
        self.filter_head_label = filter_head_label or filter_label
        self.filter_tail_label = filter_tail_label or filter_label
        self.mtl_label = mtl_label
        self.capacitive_label = capacitive_label
        self.inductive_label = inductive_label
        self.c1g_label = c1g_label
        self.c2g_label = c2g_label
        self.c12_label = c12_label
        self.c0r_label = c0r_label
        self._pending_physical_node_labels = dict(physical_node_labels or {})
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
        self.show_readout_terminal = show_readout_terminal
        self.show_window_markers = show_window_markers
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        length = self.length
        gap = self.track_gap
        win0 = self.window_start
        win1 = win0 + self.window_length
        lead = u * 0.5
        visual_win0 = win0 + 2 * lead
        visual_win1 = visual_win0 + self.window_length + 2 * lead
        visual_length = visual_win1 + (length - win1) + 2 * lead
        idc_stub_units = 0.5
        idc_stub = u * idc_stub_units
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        A = {
            "start": (0, 0),
            "end": (visual_length + self.idc_width + 2 * idc_stub, 0),
            "readout_grounded_head": (0, 0),
            "readout_attachment": (visual_length, 0),
            "filter_grounded_head": (0, -gap),
            "filter_open_tail": (visual_length, -gap),
            "feedline_attachment": (
                visual_length + self.idc_width + 2 * idc_stub,
                -gap,
            ),
            "readout_ground": (0, -u * 0.42),
            "filter_ground": (0, -gap - u * 0.42),
            "readout_window_left": (visual_win0, 0),
            "readout_window_right": (visual_win1, 0),
            "filter_window_left": (visual_win0, -gap),
            "filter_window_right": (visual_win1, -gap),
            "c0r_ground": (visual_length, -u * 0.82),
        }
        self.anchors.update(A)
        self.visual_netlist: list[dict[str, str]] = []

        self.readout_head_cpw = self.add(
            TransmissionLineSegment(
                component_id=f"{self.component_id}_readout_head_cpw",
                unit_length=u,
                length_units=self.window_start / u,
                theme=self.theme,
                label=None,
                left_terminal="none",
                right_terminal="none",
                boxed=True,
                box_height_units=0.62,
                line_color="#dc4c4c" if self.theme == "light" else "#fb7185",
                line_width=3.0,
                show_nodes=False,
                show_labels=False,
            ).at(A["readout_grounded_head"])
        )
        self._record_visual_branch(
            "readout_head_cpw",
            "cpw",
            "readout_grounded_head",
            "readout_window_left",
        )
        self.filter_head_cpw = self.add(
            TransmissionLineSegment(
                component_id=f"{self.component_id}_filter_head_cpw",
                unit_length=u,
                length_units=self.window_start / u,
                theme=self.theme,
                label=None,
                left_terminal="none",
                right_terminal="none",
                boxed=True,
                box_height_units=0.62,
                line_color="#4774cf" if self.theme == "light" else "#60a5fa",
                line_width=3.0,
                show_nodes=False,
                show_labels=False,
            ).at(A["filter_grounded_head"])
        )
        self._record_visual_branch(
            "filter_head_cpw",
            "cpw",
            "filter_grounded_head",
            "filter_window_left",
        )
        self.mtl_window = self.add(
            CoupledCPWTransmissionLine(
                component_id=f"{self.component_id}_mtl_window",
                unit_length=u,
                width_units=self.window_length / u,
                track_gap_units=self.track_gap / u,
                theme=self.theme,
                label=None,
                show_label=False,
                show_terminals=False,
            ).at(A["readout_window_left"])
        )
        self._record_visual_branch(
            "readout_mtl_track",
            "mtl_track",
            "readout_window_left",
            "readout_window_right",
        )
        self._record_visual_branch(
            "filter_mtl_track",
            "mtl_track",
            "filter_window_left",
            "filter_window_right",
        )
        self._record_visual_branch(
            "mtl_coupling",
            "mtl_coupling_same_direction",
            "readout_mtl_track",
            "filter_mtl_track",
        )
        tail_width_units = (length - win1) / u
        self.readout_tail_cpw = self.add(
            TransmissionLineSegment(
                component_id=f"{self.component_id}_readout_tail_cpw",
                unit_length=u,
                length_units=tail_width_units,
                theme=self.theme,
                label=None,
                left_terminal="none",
                right_terminal="none",
                boxed=True,
                box_height_units=0.62,
                line_color="#dc4c4c" if self.theme == "light" else "#fb7185",
                line_width=3.0,
                show_nodes=False,
                show_labels=False,
            ).at(A["readout_window_right"])
        )
        self._record_visual_branch(
            "readout_tail_cpw",
            "cpw",
            "readout_window_right",
            "readout_attachment",
        )
        self.filter_tail_cpw = self.add(
            TransmissionLineSegment(
                component_id=f"{self.component_id}_filter_tail_cpw",
                unit_length=u,
                length_units=tail_width_units,
                theme=self.theme,
                label=None,
                left_terminal="none",
                right_terminal="none",
                boxed=True,
                box_height_units=0.62,
                line_color="#4774cf" if self.theme == "light" else "#60a5fa",
                line_width=3.0,
                show_nodes=False,
                show_labels=False,
            ).at(A["filter_window_right"])
        )
        self._record_visual_branch(
            "filter_tail_cpw",
            "cpw",
            "filter_window_right",
            "filter_open_tail",
        )
        if self.show_labels:
            readout_color = "#dc4c4c" if self.theme == "light" else "#fb7185"
            filter_color = "#4774cf" if self.theme == "light" else "#60a5fa"
            window_color = "#8a50d0" if self.theme == "light" else "#c084fc"
            self._block_label(
                (lead + win0 / 2, 0),
                self.readout_head_label,
                readout_color,
            )
            self._block_label(
                (visual_win1 + lead + (length - win1) / 2, 0),
                self.readout_tail_label,
                readout_color,
            )
            self._block_label(
                (lead + win0 / 2, -gap),
                self.filter_head_label,
                filter_color,
            )
            self._block_label(
                (visual_win1 + lead + (length - win1) / 2, -gap),
                self.filter_tail_label,
                filter_color,
            )
            self._block_label(
                (visual_win0 + lead + self.window_length / 2, -gap / 2),
                self.mtl_label,
                window_color,
            )
        self.add(
            elm.Line(color=color).endpoints(
                A["readout_grounded_head"],
                A["readout_ground"],
            )
        )
        self.add(elm.Ground(color=color).at(A["readout_ground"]))
        self._record_visual_branch(
            "readout_head_termination",
            "ground",
            "readout_grounded_head",
            "ground",
        )
        self.add(
            elm.Line(color=color).endpoints(
                A["filter_grounded_head"],
                A["filter_ground"],
            )
        )
        self.add(elm.Ground(color=color).at(A["filter_ground"]))
        self._record_visual_branch(
            "filter_head_termination",
            "ground",
            "filter_grounded_head",
            "ground",
        )

        if self.show_window_markers:
            self._window_marker(A["readout_window_left"], A["filter_window_left"])
            self._window_marker(A["readout_window_right"], A["filter_window_right"])

        self.feedline_idc = self.add(
            InterdigitatedCapacitor(
                component_id=f"{self.component_id}_feedline_idc",
                unit_length=u,
                width_units=self.idc_width_units,
                shunt_height_units=0.78,
                port_stub_units=idc_stub_units,
                theme=self.theme,
                c1g_label=self.c1g_label,
                c2g_label=self.c2g_label,
                c12_label=self.c12_label,
                show_terminals=False,
                show_nodes=False,
                show_labels=self.show_labels,
            )
            .at((A["filter_open_tail"][0] + idc_stub, A["filter_open_tail"][1]))
            .right()
        )
        idc_filter_terminal = public_terminal_point(
            self.feedline_idc,
            "terminal_1",
            transformed=True,
        )
        idc_feedline_terminal = public_terminal_point(
            self.feedline_idc,
            "terminal_2",
            transformed=True,
        )
        self.anchors.update(
            {
                "idc_filter_terminal": idc_filter_terminal,
                "idc_feedline_terminal": idc_feedline_terminal,
            }
        )
        self._record_visual_branch(
            "idc_c1g",
            "capacitor",
            "filter_open_tail",
            "ground",
        )
        self._record_visual_branch(
            "idc_c2g",
            "capacitor",
            "feedline_attachment",
            "ground",
        )
        self._record_visual_branch(
            "idc_c12",
            "capacitor",
            "filter_open_tail",
            "feedline_attachment",
        )
        if self.c0r_label is not None:
            self._capacitor(
                A["readout_attachment"],
                A["c0r_ground"],
                None,
                "top",
            )
            if self.show_labels:
                self._block_label(
                    (visual_length - u * 0.25, -u * 0.48),
                    self.c0r_label,
                    color,
                )
            self.add(elm.Ground(color=color).at(A["c0r_ground"]))
            self._record_visual_branch(
                "c0r",
                "capacitor",
                "readout_attachment",
                "ground",
            )

        self.physical_nodes = {
            "readout_grounded_head": ["readout_grounded_head", "readout_ground"],
            "readout_attachment": ["readout_attachment"],
            "readout_window_left": ["readout_window_left"],
            "readout_window_right": ["readout_window_right"],
            "filter_grounded_head": ["filter_grounded_head", "filter_ground"],
            "filter_window_left": ["filter_window_left"],
            "filter_window_right": ["filter_window_right"],
            "filter_open_tail": ["filter_open_tail", "idc_filter_terminal"],
            "feedline_attachment": [
                "feedline_attachment",
                "idc_feedline_terminal",
            ],
        }
        self.ports = {
            "readout_attachment": "readout_attachment",
            "feedline_attachment": "feedline_attachment",
        }
        self.public_terminals = {
            "readout_attachment": TerminalSpec(
                "readout_attachment",
                "readout_attachment",
                "right",
            ),
            "feedline_attachment": TerminalSpec(
                "feedline_attachment",
                "feedline_attachment",
                "right",
            ),
        }
        self.buses = {
            "filter_to_idc": BusSpec(
                "filter_open_tail",
                ("filter_open_tail", "idc_filter_terminal"),
            ),
            "idc_to_feedline": BusSpec(
                "feedline_attachment",
                ("idc_feedline_terminal", "feedline_attachment"),
            ),
        }
        self.node_markers = {
            name: NodeMarkerSpec(name, name, "connection")
            for name in (
                "readout_grounded_head",
                "readout_window_left",
                "readout_window_right",
                "filter_grounded_head",
                "filter_window_left",
                "filter_window_right",
                "filter_open_tail",
            )
        }
        self.node_markers["idc_filter_terminal"] = NodeMarkerSpec(
            "filter_open_tail",
            "idc_filter_terminal",
            "connection",
        )
        validate_component_metadata(self)
        markers = [
            ConnectionMarkerSpec(
                A["feedline_attachment"],
                "exposed",
                node="feedline_attachment",
            )
        ]
        if self.show_readout_terminal:
            markers.append(
                ConnectionMarkerSpec(
                    A["readout_attachment"],
                    "exposed",
                    node="readout_attachment",
                )
            )
        elif self.show_nodes:
            markers.append(
                ConnectionMarkerSpec(
                    A["readout_attachment"],
                    "connected",
                    node="readout_attachment",
                )
            )
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(
                    self.anchors[spec.anchor],
                    "connected",
                    node=spec.node,
                )
                for spec in self.node_markers.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=dot_radius,
        )
        if not getattr(self, "_defer_physical_node_labels", False):
            _finish_physical_node_labels(self)
        self.visual_components = (
            "readout_head_cpw",
            "filter_head_cpw",
            "mtl_window",
            "readout_tail_cpw",
            "filter_tail_cpw",
        )
        self.elmparams["drop"] = A["end"]

    def _line(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        line = elm.Line(color=color).endpoints(start, end)
        if self.show_labels and label is not None:
            line = line.label(label, loc=loc, color=color)
        self.add(line)

    def _block_label(
        self,
        at: tuple[float, float],
        label: str | None,
        color: str,
    ) -> None:
        if label is not None:
            self.add(elm.Label(label, color=color).at(at))

    def _record_visual_branch(
        self,
        branch_id: str,
        kind: str,
        from_node: str,
        to_node: str,
    ) -> None:
        self.visual_netlist.append(
            {
                "id": branch_id,
                "kind": kind,
                "from": from_node,
                "to": to_node,
            }
        )

    def _capacitor(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        capacitor = elm.Capacitor(color=color).endpoints(start, end)
        if self.show_labels and label is not None:
            capacitor = capacitor.label(label, loc=loc, color=color)
        self.add(capacitor)

    def _controlled_relation(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        relation = elm.Line(color=color, ls="--").endpoints(start, end)
        if self.show_labels:
            relation = relation.label(label, loc=loc, color=color)
        self.add(relation)

    def _window_marker(
        self,
        top: tuple[float, float],
        bottom: tuple[float, float],
    ) -> None:
        margin = self.unit_length * 0.12
        self.add(
            elm.Line(color=theme_color(self.theme), ls=":").endpoints(
                (top[0], top[1] - margin),
                (bottom[0], bottom[1] + margin),
            )
        )


def _add_floating_qubit_projection(component: Any) -> None:
    if component.qubit_inductive_branch_kind != "linearized_josephson":
        raise ValueError(
            "The linearized floating qubit requires two ordinary "
            "Josephson-inductance branches."
        )
    u = component.unit_length
    color = theme_color(component.theme)
    dot_radius = SCHEMATIC_DOT_RADIUS
    readout = component.anchors["readout_attachment"]
    qubit_origin = (readout[0] + u * 4.0, u * 4.8)
    component.qubit_block = component.add(
        LinearizedFloatingQubit(
            component_id=f"{component.component_id}_qubit",
            unit_length=u,
            theme=component.theme,
            c01_label=component.c01_label,
            c02_label=component.c02_label,
            c12_label=component.qubit_c12_label,
            lj1_label=component.lj1_label,
            lj2_label=component.lj2_label,
            q1_label=None,
            q2_label=None,
            show_nodes=False,
            show_terminals=False,
            show_labels=component.show_labels,
        )
        .at(qubit_origin)
        .theta(0)
    )
    island_1 = public_terminal_point(component.qubit_block, "q1", transformed=True)
    island_2 = public_terminal_point(component.qubit_block, "q2", transformed=True)
    trunk_q1 = (readout[0], island_1[1])
    trunk_q2 = (readout[0], island_2[1])
    anchors = {
        "island_1": island_1,
        "island_2": island_2,
        "qubit_trunk_start": readout,
        "qubit_trunk_q1": trunk_q1,
        "qubit_trunk_q2": trunk_q2,
    }
    component.anchors.update(anchors)

    component.qubit_readout_trunk = component.add(
        elm.Line(color=color).endpoints(readout, trunk_q1)
    )
    component._capacitor(trunk_q1, island_1, component.cr1_label, "top")
    component._record_visual_branch("qubit_cr1", "capacitor", "readout_attachment", "island_1")
    component._capacitor(trunk_q2, island_2, component.cr2_label, "bottom")
    component._record_visual_branch("qubit_cr2", "capacitor", "readout_attachment", "island_2")
    component._record_visual_branch("qubit_c12", "capacitor", "island_1", "island_2")
    component._record_visual_branch(
        "qubit_lj1",
        "inductor",
        "island_1",
        "island_2",
    )
    component._record_visual_branch(
        "qubit_lj2",
        "inductor",
        "island_1",
        "island_2",
    )
    component._record_visual_branch("qubit_c01", "capacitor", "island_1", "ground")
    component._record_visual_branch("qubit_c02", "capacitor", "island_2", "ground")
    component.physical_nodes["readout_attachment"].extend(
        ["qubit_trunk_start", "qubit_trunk_q1", "qubit_trunk_q2"]
    )
    component.physical_nodes.update({"island_1": ["island_1"], "island_2": ["island_2"]})
    component.ports = {
        "island_1": "island_1",
        "island_2": "island_2",
        "feedline_attachment": "feedline_attachment",
    }
    component.public_terminals = {
        "feedline_attachment": TerminalSpec(
            "feedline_attachment",
            "feedline_attachment",
            "right",
        )
    }
    component.buses = {
        **getattr(component, "buses", {}),
        "qubit_readout_trunk": BusSpec(
            "readout_attachment",
            ("qubit_trunk_start", "qubit_trunk_q2", "qubit_trunk_q1"),
        ),
    }
    component.node_markers.update(
        {
            "readout_attachment": NodeMarkerSpec(
                "readout_attachment",
                "readout_attachment",
                "connection",
            ),
            "qubit_q1_terminal": NodeMarkerSpec(
                "island_1",
                "island_1",
                "connection",
            ),
            "qubit_q2_terminal": NodeMarkerSpec(
                "island_2",
                "island_2",
                "connection",
            ),
        }
    )

    base_blocks = {
        name: getattr(component, name)
        for name in (
            "readout_head_cpw",
            "filter_head_cpw",
            "mtl_window",
            "readout_tail_cpw",
            "filter_tail_cpw",
            "readout_resonator",
            "filter_resonator",
            "bridge_resonator",
            "feedline_idc",
        )
        if hasattr(component, name)
    }
    for name, block in base_blocks.items():
        validate_block_clearance(
            {name: block, "qubit": component.qubit_block},
            clearance=u * 0.25,
            include_labels=False,
        )
    validate_component_metadata(component)
    if component.show_nodes:
        render_connection_markers(
            component,
            [
                ConnectionMarkerSpec(
                    island_1,
                    "connected",
                    node="island_1",
                ),
                ConnectionMarkerSpec(
                    island_2,
                    "connected",
                    node="island_2",
                ),
            ],
            color=color,
            radius=dot_radius,
        )
    _finish_physical_node_labels(component)
    qubit_bbox = component.qubit_block.get_bbox(transform=True, includetext=False)
    component.elmparams["drop"] = (
        max(component.anchors["feedline_attachment"][0], qubit_bbox.xmax),
        0,
    )


class IntrinsicInterferometricPurcellFilterWithQubit(IntrinsicInterferometricPurcellFilter):
    """Intrinsic interferometric Purcell filter composed with a floating qubit."""

    component_kind: ClassVar[str] = "IntrinsicInterferometricPurcellFilterWithQubit"

    def __init__(
        self,
        *,
        c01_label: str = r"$C_{01}$",
        c02_label: str = r"$C_{02}$",
        qubit_c12_label: str = r"$C_{12,q}$",
        cr1_label: str = r"$C_{r1}$",
        cr2_label: str = r"$C_{r2}$",
        lj1_label: str = r"$L_{J1}$",
        lj2_label: str = r"$L_{J2}$",
        qubit_inductive_branch_kind: InductiveBranchKind = "linearized_josephson",
        c0r_label: str | None = r"$C_{0r}$",
        **kwargs: Any,
    ) -> None:
        self.c01_label = c01_label
        self.c02_label = c02_label
        self.qubit_c12_label = qubit_c12_label
        self.cr1_label = cr1_label
        self.cr2_label = cr2_label
        self.lj1_label = lj1_label
        self.lj2_label = lj2_label
        self.qubit_inductive_branch_kind = qubit_inductive_branch_kind
        self._defer_physical_node_labels = True
        super().__init__(
            c0r_label=c0r_label,
            show_readout_terminal=False,
            **kwargs,
        )

    def setup(self) -> None:
        super().setup()
        _add_floating_qubit_projection(self)

    def _inductor(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        inductor = elm.Inductor(color=color).endpoints(start, end)
        if self.show_labels:
            inductor = inductor.label(label, loc=loc, color=color)
        self.add(inductor)


class IntrinsicInterferometricPurcellFilterEquivalent(elm.ElementCompound):
    """Response-matched two-resonator LC equivalent with a three-branch IDC."""

    component_kind: ClassVar[str] = "IntrinsicInterferometricPurcellFilterEquivalent"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        resonator_separation_units: float = 4.4,
        bridge_connection_units: float = 0.5,
        idc_width_units: float = 1.55,
        theme: Theme = "light",
        cr_label: str = r"$C_r$",
        lr_label: str = r"$L_r$",
        cp_label: str = r"$C_p$",
        lp_label: str = r"$L_p$",
        cn_label: str = r"$C_n$",
        ln_label: str = r"$L_n$",
        cpg_label: str = r"$C_{pG}^{\mathrm{IDC}}$",
        cfcg_label: str = r"$C_{f_cG}^{\mathrm{IDC}}$",
        cpfc_label: str = r"$C_{pf_c}^{\mathrm{IDC}}$",
        c0r_label: str | None = None,
        physical_node_labels: Mapping[str, NodeLabelSpec] | None = None,
        show_readout_terminal: bool = True,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.unit_length = unit_length
        self.resonator_separation = unit_length * resonator_separation_units
        self.bridge_connection = unit_length * bridge_connection_units
        self.idc_width_units = idc_width_units
        self.idc_width = unit_length * idc_width_units
        self.theme: Theme = theme
        self.cr_label = cr_label
        self.lr_label = lr_label
        self.cp_label = cp_label
        self.lp_label = lp_label
        self.cn_label = cn_label
        self.ln_label = ln_label
        self.cpg_label = cpg_label
        self.cfcg_label = cfcg_label
        self.cpfc_label = cpfc_label
        self.c0r_label = c0r_label
        self._pending_physical_node_labels = dict(physical_node_labels or {})
        self.physical_node_labels: dict[str, NodeLabelSpec] = {}
        self.show_readout_terminal = show_readout_terminal
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        idc_stub_units = 1.3
        readout = (0.0, 0.0)
        filter_node = (
            self.resonator_separation + (u if self.c0r_label is not None else 0.0),
            0.0,
        )
        self.visual_netlist: list[dict[str, str]] = []

        self.readout_resonator = self.add(
            GroundedLCResonator(
                component_id=f"{self.component_id}_readout_resonator",
                unit_length=u,
                spacing_units=1.0,
                height_units=1.15,
                theme=self.theme,
                c0_label=self.c0r_label,
                c_label=self.cr_label,
                l_label=self.lr_label,
                show_nodes=False,
                show_terminals=False,
                show_labels=self.show_labels,
            )
            .at(readout)
            .anchor("start")
        )
        self._record_visual_branch("readout_cr", "capacitor", "readout_attachment", "ground")
        self._record_visual_branch("readout_lr", "inductor", "readout_attachment", "ground")
        if self.c0r_label is not None:
            self._record_visual_branch("c0r", "capacitor", "readout_attachment", "ground")

        self.filter_resonator = self.add(
            GroundedLCResonator(
                component_id=f"{self.component_id}_filter_resonator",
                unit_length=u,
                spacing_units=1.0,
                height_units=1.15,
                theme=self.theme,
                c_label=self.cp_label,
                l_label=self.lp_label,
                show_nodes=False,
                show_terminals=False,
                show_labels=self.show_labels,
            )
            .at(filter_node)
            .anchor("start")
        )
        self._record_visual_branch("filter_cp", "capacitor", "filter", "ground")
        self._record_visual_branch("filter_lp", "inductor", "filter", "ground")

        readout_output = public_terminal_point(
            self.readout_resonator,
            "right",
            transformed=True,
        )
        filter_input = public_terminal_point(
            self.filter_resonator,
            "left",
            transformed=True,
        )
        bridge_left = readout_output
        bridge_right = filter_input
        bridge_width = bridge_right[0] - bridge_left[0] - 2 * self.bridge_connection
        if bridge_width <= 0:
            raise ValueError(
                "resonator separation leaves no room for the bridge and its connections."
            )
        self.bridge_resonator = self.add(
            FloatingParallelLC(
                component_id=f"{self.component_id}_bridge_resonator",
                unit_length=u,
                width_units=bridge_width / u,
                branch_offset_units=bridge_width / (2 * u),
                terminal_stub_units=self.bridge_connection / u,
                theme=self.theme,
                inductive_branch_kind="linear",
                c_label=self.cn_label,
                l_label=self.ln_label,
                show_nodes=False,
                show_terminals=False,
                show_labels=self.show_labels,
            )
            .at(bridge_left)
            .anchor("start")
        )
        bridge_terminal_right = public_terminal_point(
            self.bridge_resonator,
            "right",
            transformed=True,
        )
        if any(
            abs(actual - expected) > 1e-9
            for actual, expected in zip(bridge_terminal_right, filter_input, strict=True)
        ):
            raise ValueError("The bridge terminal stubs do not span the resonator gap.")
        self._record_visual_branch("bridge_cn", "capacitor", "readout_attachment", "filter")
        self._record_visual_branch("bridge_ln", "inductor", "readout_attachment", "filter")

        filter_output = public_terminal_point(
            self.filter_resonator,
            "right",
            transformed=True,
        )
        idc_start = filter_output
        self.feedline_idc = self.add(
            InterdigitatedCapacitor(
                component_id=f"{self.component_id}_feedline_idc",
                unit_length=u,
                width_units=self.idc_width_units,
                shunt_height_units=1.0,
                port_stub_units=idc_stub_units,
                theme=self.theme,
                c1g_label=self.cpg_label,
                c2g_label=self.cfcg_label,
                c12_label=self.cpfc_label,
                show_terminals=False,
                show_nodes=False,
                show_labels=self.show_labels,
            )
            .at(idc_start)
            .anchor("terminal_1_port")
        )
        feedline = public_terminal_point(
            self.feedline_idc,
            "terminal_2",
            transformed=True,
        )
        if (
            public_terminal_point(
                self.feedline_idc,
                "terminal_1",
                transformed=True,
            )
            != filter_output
        ):
            raise ValueError("The IDC must connect directly to the filter terminal.")
        anchors = {
            "start": readout,
            "end": feedline,
            "readout_attachment": readout,
            "filter": filter_node,
            "feedline_attachment": feedline,
            "readout_terminal": readout,
            "readout_output": readout_output,
            "bridge_left": bridge_left,
            "bridge_right": bridge_right,
            "filter_input": filter_input,
            "filter_output": filter_output,
            "idc_start": idc_start,
        }
        self.anchors.update(anchors)
        self._record_visual_branch("idc_cpg", "capacitor", "filter", "ground")
        self._record_visual_branch("idc_cfcg", "capacitor", "feedline_attachment", "ground")
        self._record_visual_branch("idc_cpfc", "capacitor", "filter", "feedline_attachment")

        self.physical_nodes = {
            "readout_attachment": [
                "readout_attachment",
                "readout_output",
                "bridge_left",
            ],
            "filter": [
                "filter",
                "bridge_right",
                "filter_input",
                "filter_output",
                "idc_start",
            ],
            "feedline_attachment": ["feedline_attachment"],
        }
        self.ports = {
            "readout_attachment": "readout_attachment",
            "feedline_attachment": "feedline_attachment",
        }
        self.public_terminals = {
            "readout_attachment": TerminalSpec(
                "readout_attachment",
                "readout_attachment",
                "left",
            ),
            "feedline_attachment": TerminalSpec(
                "feedline_attachment",
                "feedline_attachment",
                "right",
            ),
        }
        self.buses = {
            "readout_signal": BusSpec(
                "readout_attachment",
                ("readout_attachment", "readout_output"),
            ),
            "filter_signal": BusSpec(
                "filter",
                ("filter_input", "filter_output"),
            ),
        }
        self.node_markers = {
            "readout_resonator_output": NodeMarkerSpec(
                "readout_attachment",
                "readout_output",
                "connection",
            ),
            "bridge_readout_terminal": NodeMarkerSpec(
                "readout_attachment",
                "bridge_left",
                "connection",
            ),
            "bridge_filter_terminal": NodeMarkerSpec(
                "filter",
                "bridge_right",
                "connection",
            ),
            "filter_resonator_input": NodeMarkerSpec(
                "filter",
                "filter_input",
                "connection",
            ),
            "filter_resonator_output": NodeMarkerSpec(
                "filter",
                "filter_output",
                "connection",
            ),
            "idc_filter_terminal": NodeMarkerSpec(
                "filter",
                "idc_start",
                "connection",
            ),
        }
        validate_component_metadata(self)
        markers = [
            ConnectionMarkerSpec(
                feedline,
                "exposed",
                node="feedline_attachment",
            ),
        ]
        if self.show_readout_terminal:
            markers.append(
                ConnectionMarkerSpec(
                    readout,
                    "exposed",
                    node="readout_attachment",
                )
            )
        elif self.show_nodes:
            markers.append(
                ConnectionMarkerSpec(
                    readout,
                    "connected",
                    node="readout_attachment",
                )
            )
        if self.show_nodes:
            markers.extend(
                ConnectionMarkerSpec(
                    anchors[spec.anchor],
                    "connected",
                    node=spec.node,
                )
                for spec in self.node_markers.values()
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=dot_radius,
        )
        if not getattr(self, "_defer_physical_node_labels", False):
            _finish_physical_node_labels(self)
        self.elmparams["drop"] = feedline

    def _record_visual_branch(
        self,
        branch_id: str,
        kind: str,
        from_node: str,
        to_node: str,
    ) -> None:
        self.visual_netlist.append(
            {"id": branch_id, "kind": kind, "from": from_node, "to": to_node}
        )

    def _capacitor(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        capacitor = elm.Capacitor(color=color).endpoints(start, end)
        if self.show_labels and label is not None:
            capacitor = capacitor.label(label, loc=loc, color=color)
        self.add(capacitor)

    def _inductor(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        label: str,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        inductor = elm.Inductor(color=color).endpoints(start, end)
        if self.show_labels:
            inductor = inductor.label(label, loc=loc, color=color)
        self.add(inductor)


class IntrinsicInterferometricPurcellFilterEquivalentWithQubit(
    IntrinsicInterferometricPurcellFilterEquivalent
):
    """Response-matched intrinsic-filter equivalent with a floating qubit."""

    component_kind: ClassVar[str] = "IntrinsicInterferometricPurcellFilterEquivalentWithQubit"

    def __init__(
        self,
        *,
        c01_label: str = r"$C_{01}$",
        c02_label: str = r"$C_{02}$",
        qubit_c12_label: str = r"$C_{12,q}$",
        cr1_label: str = r"$C_{r1}$",
        cr2_label: str = r"$C_{r2}$",
        lj1_label: str = r"$L_{J1}$",
        lj2_label: str = r"$L_{J2}$",
        qubit_inductive_branch_kind: InductiveBranchKind = "linearized_josephson",
        c0r_label: str | None = r"$C_{0r}$",
        **kwargs: Any,
    ) -> None:
        self.c01_label = c01_label
        self.c02_label = c02_label
        self.qubit_c12_label = qubit_c12_label
        self.cr1_label = cr1_label
        self.cr2_label = cr2_label
        self.lj1_label = lj1_label
        self.lj2_label = lj2_label
        self.qubit_inductive_branch_kind = qubit_inductive_branch_kind
        self._defer_physical_node_labels = True
        super().__init__(
            c0r_label=c0r_label,
            show_readout_terminal=False,
            **kwargs,
        )

    def setup(self) -> None:
        super().setup()
        _add_floating_qubit_projection(self)


PREVIEW_CASES: tuple[PreviewCase, ...] = (
    PreviewCase(
        "point_coupled_readout_purcell",
        lambda theme, unit_length: PointCoupledReadoutPurcell(
            component_id="point_coupled_readout_purcell",
            unit_length=unit_length,
            theme=theme,
            input_line_label=None,
            filter_label=None,
            output_line_label=None,
            left_port_label=r"$P_1$",
            right_port_label=r"$P_2$",
        ),
    ),
    PreviewCase(
        "readout_line_hanging_qwr_mtl",
        lambda theme, unit_length: ReadoutLineHangingQWRMTL(
            component_id="readout_line_hanging_qwr_mtl",
            unit_length=unit_length,
            theme=theme,
            readout_label=None,
            qwr_label=None,
            left_port_label=r"$P_1$",
            right_port_label=r"$P_2$",
        ),
    ),
    PreviewCase(
        "readout_purcell_hanging_qwr_mtl",
        lambda theme, unit_length: ReadoutPurcellHangingQWRMTL(
            component_id="readout_purcell_hanging_qwr_mtl",
            unit_length=unit_length,
            theme=theme,
            input_line_label=None,
            filter_label=None,
            output_line_label=None,
            qwr_label=None,
            left_port_label=r"$P_1$",
            right_port_label=r"$P_2$",
        ),
    ),
    PreviewCase(
        "intrinsic_interferometric_purcell_filter",
        lambda theme, unit_length: IntrinsicInterferometricPurcellFilter(
            component_id="intrinsic_filter",
            unit_length=unit_length,
            theme=theme,
        ),
    ),
    PreviewCase(
        "intrinsic_interferometric_purcell_filter_with_qubit",
        lambda theme, unit_length: IntrinsicInterferometricPurcellFilterWithQubit(
            component_id="intrinsic_filter_with_qubit",
            unit_length=unit_length,
            theme=theme,
        ),
    ),
    PreviewCase(
        "intrinsic_interferometric_purcell_filter_equivalent",
        lambda theme, unit_length: IntrinsicInterferometricPurcellFilterEquivalent(
            component_id="intrinsic_filter_equivalent",
            unit_length=unit_length,
            theme=theme,
        ),
    ),
    PreviewCase(
        "intrinsic_interferometric_purcell_filter_equivalent_with_qubit",
        lambda theme, unit_length: IntrinsicInterferometricPurcellFilterEquivalentWithQubit(
            component_id="intrinsic_filter_equivalent_with_qubit",
            unit_length=unit_length,
            theme=theme,
        ),
    ),
)


def main(argv: list[str] | None = None) -> int:
    return run_preview_cli(module_name="transmission_line_systems", cases=PREVIEW_CASES, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CoupledCPWTransmissionLine",
    "IntrinsicInterferometricPurcellFilter",
    "IntrinsicInterferometricPurcellFilterEquivalent",
    "IntrinsicInterferometricPurcellFilterEquivalentWithQubit",
    "IntrinsicInterferometricPurcellFilterWithQubit",
    "PointCoupledReadoutPurcell",
    "ReadoutLineHangingQWRMTL",
    "ReadoutPurcellHangingQWRMTL",
]
