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
from schemdraw_circuit_library.rendering.preview import PreviewCase, run_preview_cli
from schemdraw_circuit_library.theme import SCHEMATIC_DOT_RADIUS, Theme, theme_color


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
        show_terminals: bool = True,
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
        self.show_terminals = show_terminals
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
        dot_radius = SCHEMATIC_DOT_RADIUS

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
            if k == 0:
                node_anchors.append("left_couple")
            if k == n:
                node_anchors.append("right_couple")
            if not self.reduce_capacitance and 0 < k < n:
                node_anchors.extend([f"cap{k}_split", f"cap{k}_left_top", f"cap{k}_right_top"])
            self.physical_nodes[f"n{k}"] = node_anchors
        ground_anchors = [f"gnd{k}" for k in range(n + 1)]
        ground_anchors.extend([f"cap{k}_bot" for k in (0, n)])
        if self.reduce_capacitance:
            ground_anchors.extend(f"cap{k}_bot" for k in range(1, n))
        else:
            for k in range(1, n):
                ground_anchors.extend([f"cap{k}_left_bot", f"cap{k}_right_bot"])
        self.physical_nodes["gnd"] = ground_anchors
        self.ports = {"left": "n0", "right": f"n{n}"}
        self.public_terminals = {
            "left": TerminalSpec("n0", "left_couple", "left"),
            "right": TerminalSpec(f"n{n}", "right_couple", "right"),
        }
        self.buses = {
            "left_stub": BusSpec("n0", ("left_couple", "node0")),
            "right_stub": BusSpec(f"n{n}", (f"node{n}", "right_couple")),
        }
        if not self.reduce_capacitance:
            for k in range(1, n):
                self.buses[f"cap{k}_top"] = BusSpec(
                    f"n{k}",
                    (f"cap{k}_left_top", f"cap{k}_split", f"cap{k}_right_top"),
                )
                self.buses[f"cap{k}_tap"] = BusSpec(
                    f"n{k}",
                    (f"node{k}", f"cap{k}_split"),
                )
                self.buses[f"cap{k}_ground"] = BusSpec(
                    "gnd",
                    (f"cap{k}_left_bot", f"gnd{k}", f"cap{k}_right_bot"),
                )
        self.node_markers = {
            f"node{k}": NodeMarkerSpec(f"n{k}", f"node{k}", "junction")
            for k in range(n + 1)
        }
        self.physical_node_labels = {
            node: NodeLabelSpec(
                label,
                "terminal",
                terminal,
                loc=loc,
                offset=2 * dot_radius,
            )
            for node, terminal, label, loc in (
                ("n0", "left", self.left_port_label, "left"),
                (f"n{n}", "right", self.right_port_label, "right"),
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
            radius=dot_radius,
        )
        if self.show_labels:
            render_physical_node_labels(self, color=color)
        self.elmparams["drop"] = A["end"]

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
        boxed: bool = False,
        box_height_units: float = 0.8,
        line_color: str | None = None,
        line_width: float | None = None,
        show_nodes: bool = True,
        show_terminals: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.unit_length = unit_length
        self.length_units = length_units
        self.lead_length = unit_length * 0.5 if boxed else 0
        self.length = unit_length * length_units + 2 * self.lead_length
        self.theme: Theme = theme
        self.line_label = label
        self.left_label = left_label
        self.right_label = right_label
        self.left_terminal = left_terminal
        self.right_terminal = right_terminal
        self.boxed = boxed
        self.box_height = unit_length * box_height_units
        self.line_color = line_color
        self.line_width = line_width
        self.show_nodes = show_nodes
        self.show_terminals = show_terminals
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        length = self.length
        color = self.line_color or theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        ground_drop = u * 0.45

        A = {
            "start": (0, 0),
            "end": (length, 0),
            "head": (0, 0),
            "tail": (length, 0),
            "mid": (length / 2, 0),
            "body_head": (self.lead_length, 0),
            "body_tail": (length - self.lead_length, 0),
            "head_ground": (0, -ground_drop),
            "tail_ground": (length, -ground_drop),
        }
        self.anchors.update(A)

        if self.boxed:
            half_height = self.box_height / 2
            lead_length = self.lead_length
            box_left = (lead_length, 0)
            box_right = (length - lead_length, 0)
            self.add(
                elm.Rect(
                    (box_left[0], half_height),
                    (box_right[0], -half_height),
                    color=color,
                    lw=1.8,
                )
            )
            self.add(
                elm.Line(color=color, lw=self.line_width).endpoints(
                    A["head"],
                    box_left,
                )
            )
            self.add(
                elm.Line(color=color, lw=self.line_width).endpoints(
                    box_right,
                    A["tail"],
                )
            )
            if self.show_labels and self.line_label is not None:
                self.add(elm.Label(self.line_label, color=color).at(A["mid"]))
        else:
            line = elm.Line(color=color, lw=self.line_width).endpoints(
                A["head"],
                A["tail"],
            )
            if self.show_labels and self.line_label is not None:
                line = line.label(self.line_label, loc="top", color=color)
            self.line = self.add(line)
        self._terminal(A["head"], A["head_ground"], self.left_terminal)
        self._terminal(
            A["tail"],
            A["tail_ground"],
            self.right_terminal,
        )

        left_node = "gnd" if self.left_terminal == "ground" else "head"
        right_node = "gnd" if self.right_terminal == "ground" else "tail"
        self.physical_nodes = {}
        for node, anchors in (
            (left_node, ["head"]),
            (right_node, ["tail"]),
        ):
            self.physical_nodes.setdefault(node, []).extend(anchors)
        if self.boxed:
            self.physical_nodes[left_node].append("body_head")
            self.physical_nodes[right_node].append("body_tail")
        if self.left_terminal == "ground":
            self.physical_nodes["gnd"].append("head_ground")
        if self.right_terminal == "ground":
            self.physical_nodes["gnd"].append("tail_ground")
        self.ports = {"head": left_node, "tail": right_node}
        self.public_terminals = {
            "head": TerminalSpec(left_node, "head", "left"),
            "tail": TerminalSpec(right_node, "tail", "right"),
        }
        self.buses = {}
        if self.boxed:
            self.buses["head_lead"] = BusSpec(left_node, ("head", "body_head"))
            self.buses["tail_lead"] = BusSpec(right_node, ("body_tail", "tail"))
        if self.left_terminal == "ground":
            self.buses["head_ground"] = BusSpec("gnd", ("head", "head_ground"))
        if self.right_terminal == "ground":
            self.buses["tail_ground"] = BusSpec("gnd", ("tail", "tail_ground"))
        self.node_markers = {}
        self.physical_node_labels = {
            node: NodeLabelSpec(
                label,
                "terminal",
                terminal,
                loc=loc,
                offset=2 * dot_radius,
            )
            for node, terminal, kind, label, loc in (
                (left_node, "head", self.left_terminal, self.left_label, "left"),
                (right_node, "tail", self.right_terminal, self.right_label, "right"),
            )
            if kind == "open" and label is not None
        }
        validate_component_metadata(self)
        markers = []
        if self.show_terminals:
            markers.extend(
                ConnectionMarkerSpec(
                    A[self.public_terminals[terminal].anchor],
                    "exposed",
                    node=self.public_terminals[terminal].node,
                )
                for terminal, kind in (
                    ("head", self.left_terminal),
                    ("tail", self.right_terminal),
                )
                if kind == "open"
            )
        render_connection_markers(
            self,
            markers,
            color=color,
            radius=dot_radius,
        )
        if self.show_terminals and self.show_labels:
            render_physical_node_labels(self, color=color)
        self.elmparams["drop"] = A["end"]

    def _terminal(
        self,
        node: tuple[float, float],
        ground: tuple[float, float],
        terminal: str,
    ) -> None:
        color = theme_color(self.theme)
        if terminal == "ground":
            self.add(elm.Line(color=color).endpoints(node, ground))
            self.add(elm.Ground(color=color).at(ground))
            return
        if terminal == "open":
            return
        if terminal != "none":
            raise ValueError("TransmissionLineSegment terminal must be open, ground, or none.")


PREVIEW_CASES: tuple[PreviewCase, ...] = (
    PreviewCase(
        "pi_chain_reduced",
        lambda theme, unit_length: PiSectionChain(
            component_id="pi_chain_reduced",
            n=3,
            unit_length=unit_length,
            reduce_capacitance=True,
            theme=theme,
            left_port_label=r"$P_1$",
            right_port_label=r"$P_2$",
        ),
    ),
    PreviewCase(
        "pi_chain_unreduced",
        lambda theme, unit_length: PiSectionChain(
            component_id="pi_chain_unreduced",
            n=3,
            unit_length=unit_length,
            reduce_capacitance=False,
            theme=theme,
            left_port_label=r"$P_1$",
            right_port_label=r"$P_2$",
        ),
    ),
    PreviewCase(
        "transmission_line_segment",
        lambda theme, unit_length: TransmissionLineSegment(
            component_id="segment",
            unit_length=unit_length,
            theme=theme,
            label=r"$Z_0,\ell$",
            left_label=r"$P_1$",
            right_label=r"$P_2$",
        ),
    ),
)


def main(argv: list[str] | None = None) -> int:
    return run_preview_cli(
        module_name="transmission_line_pi_sections",
        cases=PREVIEW_CASES,
        argv=argv,
    )


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "PiSectionChain",
    "TransmissionLineSegment",
]
