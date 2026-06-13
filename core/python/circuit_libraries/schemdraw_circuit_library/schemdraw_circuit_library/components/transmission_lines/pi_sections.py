from __future__ import annotations

from typing import Any, ClassVar

import schemdraw.elements as elm

from ...theme import Theme, theme_color


class PiSectionChain(elm.ElementCompound):
    """Telegraph-model pi-section chain with optional capacitance reduction."""

    component_kind: ClassVar[str] = "PiSectionChain"

    def __init__(
        self,
        *,
        component_id: str = "",
        n: int = 4,
        unit_length: float = 3.0,
        spacing_units: float = 1.0,
        height_units: float = 0.9,
        port_stub_units: float = 0.45,
        reduce_capacitance: bool = True,
        cap_pair_offset_units: float = 0.12,
        theme: Theme = "light",
        l_label_template: str = r"$L_{{\Delta,{index}}}$",
        c_half_label: str = r"$C_{\Delta}/2$",
        c_reduced_label: str = r"$C_{\Delta}$",
        left_port_label: str | None = None,
        right_port_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.n = n
        self.unit_length = unit_length
        self.spacing_units = spacing_units
        self.height_units = height_units
        self.port_stub_units = port_stub_units
        self.reduce_capacitance = reduce_capacitance
        self.cap_pair_offset_units = cap_pair_offset_units
        self.spacing = unit_length * spacing_units
        self.height = unit_length * height_units
        self.port_stub = unit_length * port_stub_units
        self.cap_pair_offset = unit_length * cap_pair_offset_units
        self.theme: Theme = theme
        self.l_label_template = l_label_template
        self.c_half_label = c_half_label
        self.c_reduced_label = c_reduced_label
        self.left_port_label = left_port_label
        self.right_port_label = right_port_label
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        if self.n < 1:
            raise ValueError("PiSectionChain requires n >= 1.")

        n = self.n
        u = self.unit_length
        w = self.spacing
        h = self.height
        stub = self.port_stub
        dx = self.cap_pair_offset
        split_y = -u * 0.18
        color = theme_color(self.theme)
        dot_radius = u / 34

        A: dict[str, tuple[float, float]] = {
            "start": (-stub, 0),
            "end": (n * w + stub, 0),
            "left_couple": (-stub, 0),
            "right_couple": (n * w + stub, 0),
        }
        for k in range(n + 1):
            x = k * w
            A[f"node{k}"] = (x, 0)
            A[f"gnd{k}"] = (x, -h)
            A[f"cap{k}_top"] = (x, 0)
            A[f"cap{k}_bot"] = (x, -h)
            A[f"cap{k}_split"] = (x, split_y)
            A[f"cap{k}_left_top"] = (x - dx, split_y)
            A[f"cap{k}_left_bot"] = (x - dx, -h)
            A[f"cap{k}_right_top"] = (x + dx, split_y)
            A[f"cap{k}_right_bot"] = (x + dx, -h)
        self.anchors.update(A)

        self.left_stub_line = self.add(
            elm.Line(color=color).endpoints(A["left_couple"], A["node0"])
        )
        self.right_stub_line = self.add(
            elm.Line(color=color).endpoints(A[f"node{n}"], A["right_couple"])
        )
        self.left_port_dot = self._port_dot(A["left_couple"], self.left_port_label, "left")
        self.right_port_dot = self._port_dot(A["right_couple"], self.right_port_label, "right")

        if self.show_nodes:
            for k in range(n + 1):
                self.add(elm.Dot(radius=dot_radius, color=color).at(A[f"node{k}"]))

        for k in range(n):
            inductor = elm.Inductor(color=color).endpoints(A[f"node{k}"], A[f"node{k + 1}"])
            if self.show_labels:
                inductor = inductor.label(
                    self.l_label_template.format(index=k + 1),
                    loc="top",
                    color=color,
                )
            self.add(inductor)

        if self.reduce_capacitance:
            self._draw_reduced_capacitances(A)
        else:
            self._draw_unreduced_capacitances(A)

        self.physical_nodes = {}
        for k in range(n + 1):
            node_anchors = [f"node{k}", f"cap{k}_top"]
            if not self.reduce_capacitance and 0 < k < n:
                node_anchors.extend([f"cap{k}_split", f"cap{k}_left_top", f"cap{k}_right_top"])
            self.physical_nodes[f"n{k}"] = node_anchors
        self.physical_nodes["gnd"] = [f"gnd{k}" for k in range(n + 1)]
        self.ports = {"left": "n0", "right": f"n{n}"}
        self.elmparams["drop"] = A["end"]

    def _port_dot(
        self,
        anchor: tuple[float, float],
        label: str | None,
        loc: str,
    ) -> elm.Element:
        color = theme_color(self.theme)
        dot = elm.Dot(open=True, radius=self.unit_length / 34, color=color).at(anchor)
        if self.show_labels and label is not None:
            dot = dot.label(label, loc=loc, color=color)
        return self.add(dot)

    def _draw_reduced_capacitances(self, anchors: dict[str, tuple[float, float]]) -> None:
        color = theme_color(self.theme)
        for k in range(self.n + 1):
            label = self.c_half_label if k in {0, self.n} else self.c_reduced_label
            loc = "top" if k == 0 else "bottom"
            capacitor = elm.Capacitor(color=color).endpoints(
                anchors[f"cap{k}_top"],
                anchors[f"cap{k}_bot"],
            )
            if self.show_labels:
                capacitor = capacitor.label(label, loc=loc, color=color)
            self.add(capacitor)
            self.add(elm.Ground(color=color).at(anchors[f"gnd{k}"]))

    def _draw_unreduced_capacitances(self, anchors: dict[str, tuple[float, float]]) -> None:
        color = theme_color(self.theme)
        for k in range(self.n + 1):
            if k == 0 or k == self.n:
                loc = "top" if k == 0 else "bottom"
                capacitor = elm.Capacitor(color=color).endpoints(
                    anchors[f"cap{k}_top"],
                    anchors[f"cap{k}_bot"],
                )
                if self.show_labels:
                    capacitor = capacitor.label(self.c_half_label, loc=loc, color=color)
                self.add(capacitor)
                self.add(elm.Ground(color=color).at(anchors[f"gnd{k}"]))
                continue

            self.add(
                elm.Line(color=color).endpoints(
                    anchors[f"node{k}"],
                    anchors[f"cap{k}_split"],
                )
            )
            self.add(
                elm.Line(color=color).endpoints(
                    anchors[f"cap{k}_left_top"],
                    anchors[f"cap{k}_right_top"],
                )
            )
            left_cap = elm.Capacitor(color=color).endpoints(
                anchors[f"cap{k}_left_top"],
                anchors[f"cap{k}_left_bot"],
            )
            right_cap = elm.Capacitor(color=color).endpoints(
                anchors[f"cap{k}_right_top"],
                anchors[f"cap{k}_right_bot"],
            )
            if self.show_labels:
                left_cap = left_cap.label(self.c_half_label, loc="top", color=color)
                right_cap = right_cap.label(self.c_half_label, loc="bottom", color=color)
            self.add(left_cap)
            self.add(right_cap)
            self.add(
                elm.Line(color=color).endpoints(
                    anchors[f"cap{k}_left_bot"],
                    anchors[f"cap{k}_right_bot"],
                )
            )
            self.add(elm.Ground(color=color).at(anchors[f"gnd{k}"]))


class TransmissionLineSegment(elm.ElementCompound):
    """Renderer-side visual for one labelled transmission-line track segment."""

    component_kind: ClassVar[str] = "TransmissionLineSegment"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        length_units: float = 2.0,
        theme: Theme = "light",
        label: str | None = None,
        left_label: str | None = None,
        right_label: str | None = None,
        left_terminal: str = "open",
        right_terminal: str = "open",
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.unit_length = unit_length
        self.length_units = length_units
        self.length = unit_length * length_units
        self.theme: Theme = theme
        self.line_label = label
        self.left_label = left_label
        self.right_label = right_label
        self.left_terminal = left_terminal
        self.right_terminal = right_terminal
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        length = self.length
        color = theme_color(self.theme)
        dot_radius = u / 34
        ground_drop = u * 0.45

        A = {
            "start": (0, 0),
            "end": (length, 0),
            "head": (0, 0),
            "tail": (length, 0),
            "mid": (length / 2, 0),
            "head_ground": (0, -ground_drop),
            "tail_ground": (length, -ground_drop),
        }
        self.anchors.update(A)

        line = elm.Line(color=color).endpoints(A["head"], A["tail"])
        if self.show_labels and self.line_label is not None:
            line = line.label(self.line_label, loc="top", color=color)
        self.line = self.add(line)
        if self.show_nodes:
            self.head_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["head"]))
            self.tail_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["tail"]))

        self._terminal(A["head"], A["head_ground"], self.left_terminal, self.left_label, "left")
        self._terminal(
            A["tail"],
            A["tail_ground"],
            self.right_terminal,
            self.right_label,
            "right",
        )

        self.physical_nodes = {"head": ["head"], "tail": ["tail"]}
        self.ports = {"head": "head", "tail": "tail"}
        self.elmparams["drop"] = A["end"]

    def _terminal(
        self,
        node: tuple[float, float],
        ground: tuple[float, float],
        terminal: str,
        label: str | None,
        loc: str,
    ) -> None:
        color = theme_color(self.theme)
        if terminal == "ground":
            self.add(elm.Line(color=color).endpoints(node, ground))
            self.add(elm.Ground(color=color).at(ground))
            return
        if terminal == "open":
            dot = elm.Dot(open=True, radius=self.unit_length / 34, color=color).at(node)
            if self.show_labels and label is not None:
                dot = dot.label(label, loc=loc, color=color)
            self.add(dot)


__all__ = [
    "PiSectionChain",
    "TransmissionLineSegment",
]
