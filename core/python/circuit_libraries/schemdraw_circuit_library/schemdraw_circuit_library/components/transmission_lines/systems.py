from __future__ import annotations

from typing import Any, ClassVar

import schemdraw.elements as elm

from ...theme import Theme, theme_color


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
        u = self.unit_length
        line = self.line_length
        filter_len = self.filter_length
        gap = self.track_gap
        stub = self.port_stub
        color = theme_color(self.theme)
        dot_radius = u / 34

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
        dot = elm.Dot(open=True, radius=self.unit_length / 34, color=color).at(anchor)
        if self.show_labels and label is not None:
            dot = dot.label(label, loc=loc, color=color)
        self.add(dot)

    def _open_dot(self, anchor: tuple[float, float]) -> None:
        if self.show_nodes:
            self.add(
                elm.Dot(
                    open=True,
                    radius=self.unit_length / 38,
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
        dot_radius = u / 34
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
        dot = elm.Dot(open=True, radius=self.unit_length / 34, color=color).at(anchor)
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
        dot_radius = u / 34
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
        dot = elm.Dot(open=True, radius=self.unit_length / 34, color=color).at(anchor)
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


__all__ = [
    "PointCoupledReadoutPurcell",
    "ReadoutLineHangingQWRMTL",
    "ReadoutPurcellHangingQWRMTL",
]
