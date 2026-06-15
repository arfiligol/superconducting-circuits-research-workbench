from __future__ import annotations

from typing import Any, ClassVar

import schemdraw.elements as elm

from schemdraw_circuit_library.rendering.preview import PreviewCase, run_preview_cli
from schemdraw_circuit_library.theme import SCHEMATIC_DOT_RADIUS, Theme, theme_color


class CoupledLineLadderSection(elm.ElementCompound):
    """Two single-line ladder sections with capacitive and inductive coupling relations."""

    component_kind: ClassVar[str] = "CoupledLineLadderSection"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        spacing_units: float = 1.35,
        track_gap_units: float = 1.0,
        port_stub_units: float = 0.45,
        theme: Theme = "light",
        top_name: str = "A",
        bottom_name: str = "B",
        top_input_label: str | None = r"$A_{\mathrm{in}}$",
        top_output_label: str | None = r"$A_{\mathrm{out}}$",
        bottom_input_label: str | None = r"$B_{\mathrm{in}}$",
        bottom_output_label: str | None = r"$B_{\mathrm{out}}$",
        capacitive_label: str = r"$C_{AB}$",
        inductive_label: str = r"$M_{AB}$",
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ):
        self.component_id = component_id
        self.unit_length = unit_length
        self.spacing = unit_length * spacing_units
        self.track_gap = unit_length * track_gap_units
        self.port_stub = unit_length * port_stub_units
        self.theme: Theme = theme
        self.top_name = top_name
        self.bottom_name = bottom_name
        self.top_input_label = top_input_label
        self.top_output_label = top_output_label
        self.bottom_input_label = bottom_input_label
        self.bottom_output_label = bottom_output_label
        self.capacitive_label = capacitive_label
        self.inductive_label = inductive_label
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        super().__init__(**kwargs)

    def setup(self) -> None:
        u = self.unit_length
        w = self.spacing
        gap = self.track_gap
        stub = self.port_stub
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        shunt_drop = u * 0.5
        relation_margin = u * 0.18

        A = {
            "start": (-stub, 0),
            "end": (w * 2 + stub, 0),
            "a_in_port": (-stub, 0),
            "a_in": (0, 0),
            "a_mid": (w, 0),
            "a_out": (w * 2, 0),
            "a_out_port": (w * 2 + stub, 0),
            "a_shunt_bot": (w * 2, -shunt_drop),
            "a_ground": (w * 2, -shunt_drop),
            "b_in_port": (-stub, -gap),
            "b_in": (0, -gap),
            "b_mid": (w, -gap),
            "b_out": (w * 2, -gap),
            "b_out_port": (w * 2 + stub, -gap),
            "b_shunt_bot": (w * 2, -gap - shunt_drop),
            "b_ground": (w * 2, -gap - shunt_drop),
            "mutual_top": (w * 1.18, -relation_margin),
            "mutual_bottom": (w * 1.18, -gap + relation_margin),
            "cap_top": (w * 1.58, 0),
            "cap_bottom": (w * 1.58, -gap),
        }
        self.anchors.update(A)

        self.add(elm.Line(color=color).endpoints(A["a_in_port"], A["a_in"]))
        self.add(elm.Line(color=color).endpoints(A["a_out"], A["a_out_port"]))
        self.add(elm.Line(color=color).endpoints(A["b_in_port"], A["b_in"]))
        self.add(elm.Line(color=color).endpoints(A["b_out"], A["b_out_port"]))
        self._port_dot(A["a_in_port"], self.top_input_label, "left")
        self._port_dot(A["a_out_port"], self.top_output_label, "right")
        self._port_dot(A["b_in_port"], self.bottom_input_label, "left")
        self._port_dot(A["b_out_port"], self.bottom_output_label, "right")

        self._inductor(A["a_in"], A["a_mid"], rf"$L_{{{self.top_name}}}$", "top")
        self._line(A["a_mid"], A["a_out"], None, "top")
        self._inductor(A["b_in"], A["b_mid"], rf"$L_{{{self.bottom_name}}}$", "bottom")
        self._line(A["b_mid"], A["b_out"], None, "bottom")
        self._shunt_capacitor(
            A["a_out"],
            A["a_shunt_bot"],
            rf"$C_{{{self.top_name}}}$",
            "bottom",
        )
        self._shunt_capacitor(
            A["b_out"],
            A["b_shunt_bot"],
            rf"$C_{{{self.bottom_name}}}$",
            "bottom",
        )

        self._controlled_relation(
            A["mutual_top"],
            A["mutual_bottom"],
            self.inductive_label,
            "top",
        )
        self._capacitor(A["cap_top"], A["cap_bottom"], self.capacitive_label, "bottom")

        if self.show_nodes:
            for anchor in ["a_in", "a_mid", "a_out", "b_in", "b_mid", "b_out"]:
                self.add(elm.Dot(radius=dot_radius, color=color).at(A[anchor]))

        self.physical_nodes = {
            "a_in": ["a_in_port", "a_in"],
            "a_out": ["a_out", "a_out_port"],
            "b_in": ["b_in_port", "b_in"],
            "b_out": ["b_out", "b_out_port"],
            "gnd": ["a_shunt_bot", "a_ground", "b_shunt_bot", "b_ground"],
        }
        self.ports = {
            "a_in": "a_in",
            "a_out": "a_out",
            "b_in": "b_in",
            "b_out": "b_out",
        }
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

    def _shunt_capacitor(
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
        self.add(elm.Ground(color=color).at(end))

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

    def _port_dot(self, anchor: tuple[float, float], label: str | None, loc: str) -> None:
        color = theme_color(self.theme)
        dot = elm.Dot(open=True, radius=SCHEMATIC_DOT_RADIUS, color=color).at(anchor)
        if self.show_labels and label is not None:
            dot = dot.label(label, loc=loc, color=color)
        self.add(dot)


PREVIEW_CASES: tuple[PreviewCase, ...] = (
    PreviewCase(
        "coupled_line_ladder_section",
        lambda theme, unit_length: CoupledLineLadderSection(
            component_id="coupled_line_ladder_section",
            unit_length=unit_length,
            theme=theme,
        ),
    ),
)


def main(argv: list[str] | None = None) -> int:
    return run_preview_cli(module_name="coupled_line_ladder", cases=PREVIEW_CASES, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["CoupledLineLadderSection"]
