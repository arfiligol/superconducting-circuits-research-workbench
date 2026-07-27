from __future__ import annotations

from typing import Any, ClassVar

import schemdraw.elements as elm

from schemdraw_circuit_library.components.couplers import InterdigitatedCapacitor
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
        self._port_dot(A["input_port"], self.left_port_label, "left")
        self._port_dot(A["output_port"], self.right_port_label, "right")

        self._line(A["input"], A["input_tail"], self.input_line_label, "top")
        self._line(A["filter_head"], A["filter_tail"], self.filter_label, "bottom")
        self._line(A["output_head"], A["output"], self.output_line_label, "top")
        self._open_dot(A["input_tail"])
        self._open_dot(A["filter_head"])
        self._open_dot(A["filter_tail"])
        self._open_dot(A["output_head"])

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

        if self.show_nodes:
            self.add(elm.Dot(radius=dot_radius, color=color).at(A["input"]))
            self.add(elm.Dot(radius=dot_radius, color=color).at(A["output"]))

        self.physical_nodes = {
            "input": ["input_port", "input"],
            "input_tail": ["input_tail"],
            "filter_head": ["filter_head"],
            "filter_tail": ["filter_tail"],
            "output_head": ["output_head"],
            "output": ["output", "output_port"],
        }
        self.ports = {"input": "input", "output": "output"}
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

    def _port_dot(self, anchor: tuple[float, float], label: str | None, loc: str) -> None:
        color = theme_color(self.theme)
        dot = elm.Dot(open=True, radius=SCHEMATIC_DOT_RADIUS, color=color).at(anchor)
        if self.show_labels and label is not None:
            dot = dot.label(label, loc=loc, color=color)
        self.add(dot)

    def _open_dot(self, anchor: tuple[float, float]) -> None:
        if self.show_nodes:
            self.add(
                elm.Dot(
                    open=True,
                    radius=SCHEMATIC_DOT_RADIUS,
                    color=theme_color(self.theme),
                ).at(anchor)
            )


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
        self._port_dot(A["input_port"], self.left_port_label, "left")
        self._port_dot(A["output_port"], self.right_port_label, "right")

        self._line(A["readout_head"], A["readout_tail"], self.readout_label, "top")
        self._line(A["qwr_grounded_head"], A["qwr_open_tail"], self.qwr_label, "bottom")
        self.add(elm.Line(color=color).endpoints(A["qwr_grounded_head"], A["qwr_ground"]))
        self.add(elm.Ground(color=color).at(A["qwr_ground"]))
        self.add(elm.Dot(open=True, radius=dot_radius, color=color).at(A["qwr_open_tail"]))

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

        if self.show_nodes:
            for anchor in [
                "readout_head",
                "readout_tail",
                "qwr_grounded_head",
                "readout_window_left",
                "readout_window_right",
            ]:
                self.add(elm.Dot(radius=dot_radius, color=color).at(A[anchor]))

        self.physical_nodes = {
            "input": ["input_port", "readout_head"],
            "output": ["readout_tail", "output_port"],
            "qwr_grounded_head": ["qwr_grounded_head", "qwr_ground"],
            "qwr_open_tail": ["qwr_open_tail"],
        }
        self.ports = {"input": "input", "output": "output"}
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

    def _port_dot(self, anchor: tuple[float, float], label: str | None, loc: str) -> None:
        color = theme_color(self.theme)
        dot = elm.Dot(open=True, radius=SCHEMATIC_DOT_RADIUS, color=color).at(anchor)
        if self.show_labels and label is not None:
            dot = dot.label(label, loc=loc, color=color)
        self.add(dot)

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
        self._port_dot(A["input_port"], self.left_port_label, "left")
        self._port_dot(A["output_port"], self.right_port_label, "right")
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
        self.add(elm.Dot(open=True, radius=dot_radius, color=color).at(A["qwr_open_tail"]))
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

        if self.show_nodes:
            for anchor in [
                "input",
                "input_tail",
                "filter_head",
                "filter_tail",
                "output_head",
                "output",
                "qwr_grounded_head",
                "filter_window_left",
                "filter_window_right",
            ]:
                self.add(elm.Dot(radius=dot_radius, color=color).at(A[anchor]))

        self.physical_nodes = {
            "input": ["input_port", "input"],
            "input_tail": ["input_tail"],
            "filter_head": ["filter_head"],
            "filter_tail": ["filter_tail"],
            "output_head": ["output_head"],
            "output": ["output", "output_port"],
            "qwr_grounded_head": ["qwr_grounded_head", "qwr_ground"],
            "qwr_open_tail": ["qwr_open_tail"],
        }
        self.ports = {"input": "input", "output": "output"}
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

    def _port_dot(self, anchor: tuple[float, float], label: str | None, loc: str) -> None:
        color = theme_color(self.theme)
        dot = elm.Dot(open=True, radius=SCHEMATIC_DOT_RADIUS, color=color).at(anchor)
        if self.show_labels and label is not None:
            dot = dot.label(label, loc=loc, color=color)
        self.add(dot)

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
        self.elmparams["drop"] = readout_end


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
        readout_attachment_label: str | None = r"$r$",
        feedline_attachment_label: str | None = r"$f_{\mathrm{attach}}$",
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
        self.readout_attachment_label = readout_attachment_label
        self.feedline_attachment_label = feedline_attachment_label
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
                show_nodes=self.show_nodes,
                show_labels=self.show_labels,
            )
            .at((A["filter_open_tail"][0] + idc_stub, A["filter_open_tail"][1]))
            .right()
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
        self._terminal_dot(
            A["feedline_attachment"],
            self.feedline_attachment_label,
            "right",
        )
        if self.show_readout_terminal:
            self._terminal_dot(
                A["readout_attachment"],
                self.readout_attachment_label,
                "right",
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

        if self.show_nodes:
            for anchor in [
                "readout_grounded_head",
                "filter_grounded_head",
                "filter_open_tail",
                "readout_window_left",
                "readout_window_right",
                "filter_window_left",
                "filter_window_right",
            ]:
                self.add(elm.Dot(radius=dot_radius, color=color).at(A[anchor]))
            if not self.show_readout_terminal:
                self.add(
                    elm.Dot(radius=dot_radius, color=color).at(A["readout_attachment"])
                )

        self.physical_nodes = {
            "readout_grounded_head": ["readout_grounded_head", "readout_ground"],
            "readout_attachment": ["readout_attachment"],
            "filter_grounded_head": ["filter_grounded_head", "filter_ground"],
            "filter_open_tail": ["filter_open_tail"],
            "feedline_attachment": ["feedline_attachment"],
        }
        self.ports = {
            "readout_attachment": "readout_attachment",
            "feedline_attachment": "feedline_attachment",
        }
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

    def _terminal_dot(
        self,
        anchor: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        dot = elm.Dot(open=True, radius=SCHEMATIC_DOT_RADIUS, color=color).at(anchor)
        if self.show_labels and label is not None:
            dot = dot.label(label, loc=loc, color=color)
        self.add(dot)

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


class IntrinsicInterferometricPurcellFilterWithQubit(
    IntrinsicInterferometricPurcellFilter
):
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
        c0r_label: str | None = r"$C_{0r}$",
        island_1_label: str | None = r"$q_1$",
        island_2_label: str | None = r"$q_2$",
        **kwargs: Any,
    ) -> None:
        self.c01_label = c01_label
        self.c02_label = c02_label
        self.qubit_c12_label = qubit_c12_label
        self.cr1_label = cr1_label
        self.cr2_label = cr2_label
        self.lj1_label = lj1_label
        self.lj2_label = lj2_label
        self.island_1_label = island_1_label
        self.island_2_label = island_2_label
        super().__init__(
            c0r_label=c0r_label,
            show_readout_terminal=False,
            **kwargs,
        )

    def setup(self) -> None:
        super().setup()
        u = self.unit_length
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        readout = self.anchors["readout_attachment"]
        island_left_x = readout[0] + u * 2.0
        island_right_x = island_left_x + u * 2.4
        island_1 = (island_right_x, u * 2.7)
        island_2 = (island_right_x, u * 1.2)
        lj1_x = island_left_x + u * 0.55
        c12_x = island_left_x + u * 1.2
        lj2_x = island_left_x + u * 1.85
        c01_x = island_left_x + u * 0.2
        c02_x = island_right_x - u * 0.2
        A = {
            "island_1": island_1,
            "island_2": island_2,
            "island_1_bus_left": (island_left_x, island_1[1]),
            "island_2_bus_left": (island_left_x, island_2[1]),
            "lj1_top": (lj1_x, island_1[1]),
            "lj1_bottom": (lj1_x, island_2[1]),
            "c12_top": (c12_x, island_1[1]),
            "c12_bottom": (c12_x, island_2[1]),
            "lj2_top": (lj2_x, island_1[1]),
            "lj2_bottom": (lj2_x, island_2[1]),
            "c01_top": (c01_x, island_1[1]),
            "c01_ground": (c01_x, island_1[1] + u * 0.8),
            "c02_top": (c02_x, island_2[1]),
            "c02_ground": (c02_x, island_2[1] - u * 0.8),
        }
        self.anchors.update(A)

        self._capacitor(readout, A["island_1_bus_left"], self.cr1_label, "top")
        self._record_visual_branch(
            "qubit_cr1",
            "capacitor",
            "readout_attachment",
            "island_1",
        )
        self._capacitor(readout, A["island_2_bus_left"], self.cr2_label, "bottom")
        self._record_visual_branch(
            "qubit_cr2",
            "capacitor",
            "readout_attachment",
            "island_2",
        )
        self.add(
            elm.Line(color=color).endpoints(A["island_1_bus_left"], island_1)
        )
        self.add(
            elm.Line(color=color).endpoints(A["island_2_bus_left"], island_2)
        )
        self._capacitor(
            A["c12_top"],
            A["c12_bottom"],
            self.qubit_c12_label,
            "bottom",
        )
        self._record_visual_branch(
            "qubit_c12",
            "capacitor",
            "island_1",
            "island_2",
        )
        self._inductor(A["lj1_top"], A["lj1_bottom"], self.lj1_label, "top")
        self._record_visual_branch(
            "qubit_lj1",
            "inductor",
            "island_1",
            "island_2",
        )
        self._inductor(A["lj2_top"], A["lj2_bottom"], self.lj2_label, "bottom")
        self._record_visual_branch(
            "qubit_lj2",
            "inductor",
            "island_1",
            "island_2",
        )
        self._capacitor(A["c01_top"], A["c01_ground"], self.c01_label, "top")
        self._record_visual_branch(
            "qubit_c01",
            "capacitor",
            "island_1",
            "ground",
        )
        self._capacitor(A["c02_top"], A["c02_ground"], self.c02_label, "bottom")
        self._record_visual_branch(
            "qubit_c02",
            "capacitor",
            "island_2",
            "ground",
        )
        self.add(elm.Ground(color=color).at(A["c01_ground"]).theta(180))
        self.add(elm.Ground(color=color).at(A["c02_ground"]))

        self._terminal_dot(island_1, self.island_1_label, "right")
        self._terminal_dot(island_2, self.island_2_label, "right")
        if self.show_nodes:
            self.add(elm.Dot(radius=dot_radius, color=color).at(readout))

        self.physical_nodes.update(
            {
                "island_1": ["island_1", "lj1_top", "lj2_top"],
                "island_2": ["island_2", "lj1_bottom", "lj2_bottom"],
            }
        )
        self.ports = {
            "island_1": "island_1",
            "island_2": "island_2",
            "feedline_attachment": "feedline_attachment",
        }
        self.elmparams["drop"] = (
            max(self.anchors["feedline_attachment"][0], island_right_x),
            0,
        )

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
)


def main(argv: list[str] | None = None) -> int:
    return run_preview_cli(module_name="transmission_line_systems", cases=PREVIEW_CASES, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CoupledCPWTransmissionLine",
    "IntrinsicInterferometricPurcellFilter",
    "IntrinsicInterferometricPurcellFilterWithQubit",
    "PointCoupledReadoutPurcell",
    "ReadoutLineHangingQWRMTL",
    "ReadoutPurcellHangingQWRMTL",
]
