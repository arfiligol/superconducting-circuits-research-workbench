from __future__ import annotations

from typing import Any, ClassVar, Literal

import schemdraw.elements as elm

from schemdraw_circuit_library.rendering.preview import PreviewCase, run_preview_cli
from schemdraw_circuit_library.theme import SCHEMATIC_DOT_RADIUS, Theme, theme_color

type PortSide = Literal["left", "right"]
type PortLoadDirection = Literal["up", "down"]
type LabelLocation = Literal["top", "bottom", "left", "right"]


class PortTerminal(elm.ElementCompound):
    """Open terminal plus physical port node, without drawing the reference load."""

    component_kind: ClassVar[str] = "PortTerminal"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        side: PortSide = "right",
        stub_units: float = 0.45,
        theme: Theme = "light",
        port_label: str | None = None,
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.unit_length = unit_length
        self.side = side
        self.stub_units = stub_units
        self.stub = unit_length * stub_units
        self.theme: Theme = theme
        self.port_label = port_label
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        self.labels = {"port": self.port_label}
        super().__init__(**kwargs)

    def setup(self) -> None:
        if self.side not in {"left", "right"}:
            raise ValueError("PortTerminal side must be 'left' or 'right'.")

        sign = 1 if self.side == "right" else -1
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        terminal_label_loc = "right" if self.side == "right" else "left"

        A = {
            "start": (0, 0),
            "end": (sign * self.stub, 0),
            "node": (0, 0),
            "terminal": (sign * self.stub, 0),
        }
        self.anchors.update(A)

        self.stub_line = self.add(elm.Line(color=color).endpoints(A["node"], A["terminal"]))
        terminal = elm.Dot(open=True, radius=dot_radius, color=color).at(A["terminal"])
        if self.show_labels and self.port_label is not None:
            terminal = terminal.label(self.port_label, loc=terminal_label_loc, color=color)
        self.terminal_dot = self.add(terminal)

        if self.show_nodes:
            self.node_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["node"]))

        self.physical_nodes = {"port": ["node", "terminal"]}
        self.ports = {"signal": "port"}
        self.elmparams["drop"] = A["end"]


class Port50Ohm(elm.ElementCompound):
    """Open port terminal with a 50 ohm reference resistor to ground."""

    component_kind: ClassVar[str] = "Port50Ohm"

    def __init__(
        self,
        *,
        component_id: str = "",
        unit_length: float = 3.0,
        side: PortSide = "right",
        stub_units: float = 0.45,
        height_units: float = 1.0,
        load_direction: PortLoadDirection = "down",
        theme: Theme = "light",
        port_label: str | None = None,
        resistance_label: str | None = None,
        resistance_label_loc: LabelLocation = "bottom",
        show_nodes: bool = True,
        show_labels: bool = True,
        **kwargs: Any,
    ) -> None:
        self.component_id = component_id
        self.unit_length = unit_length
        self.side = side
        self.stub_units = stub_units
        self.height_units = height_units
        self.load_direction: PortLoadDirection = load_direction
        self.stub = unit_length * stub_units
        self.height = unit_length * height_units
        self.theme: Theme = theme
        self.port_label = port_label
        self.resistance_label = resistance_label if resistance_label is not None else r"$R_{50}$"
        self.resistance_label_loc: LabelLocation = resistance_label_loc
        self.show_nodes = show_nodes
        self.show_labels = show_labels
        self.labels = {"port": self.port_label, "resistance": self.resistance_label}
        super().__init__(**kwargs)

    def setup(self) -> None:
        if self.side not in {"left", "right"}:
            raise ValueError("Port50Ohm side must be 'left' or 'right'.")
        if self.load_direction not in {"up", "down"}:
            raise ValueError("Port50Ohm load_direction must be 'up' or 'down'.")

        sign = 1 if self.side == "right" else -1
        load_sign = 1 if self.load_direction == "up" else -1
        color = theme_color(self.theme)
        dot_radius = SCHEMATIC_DOT_RADIUS
        terminal_label_loc = "right" if self.side == "right" else "left"
        load_end = (0, load_sign * self.height)

        A = {
            "start": (0, 0),
            "end": (sign * self.stub, 0),
            "node": (0, 0),
            "terminal": (sign * self.stub, 0),
            "res_top": (0, 0),
            "res_bot": load_end,
            "gnd": load_end,
        }
        self.anchors.update(A)

        self.stub_line = self.add(elm.Line(color=color).endpoints(A["node"], A["terminal"]))
        terminal = elm.Dot(open=True, radius=dot_radius, color=color).at(A["terminal"])
        if self.show_labels and self.port_label is not None:
            terminal = terminal.label(self.port_label, loc=terminal_label_loc, color=color)
        self.terminal_dot = self.add(terminal)

        if self.show_nodes:
            self.node_dot = self.add(elm.Dot(radius=dot_radius, color=color).at(A["node"]))

        resistor = elm.Resistor(color=color).endpoints(A["res_top"], A["res_bot"])
        if self.show_labels:
            resistor = resistor.label(
                self.resistance_label, loc=self.resistance_label_loc, color=color
            )
        self.resistor = self.add(resistor)
        ground = elm.Ground(color=color).at(A["gnd"])
        if self.load_direction == "up":
            ground = ground.up()
        self.ground = self.add(ground)

        self.physical_nodes = {
            "port": ["node", "terminal", "res_top"],
            "gnd": ["res_bot", "gnd"],
        }
        self.ports = {"signal": "port"}
        self.elmparams["drop"] = A["end"]


PREVIEW_CASES: tuple[PreviewCase, ...] = (
    PreviewCase(
        "left_terminal",
        lambda theme, unit_length: PortTerminal(
            unit_length=unit_length,
            side="left",
            theme=theme,
            port_label=r"$P_1$",
        ),
    ),
    PreviewCase(
        "right_terminal",
        lambda theme, unit_length: PortTerminal(
            unit_length=unit_length,
            side="right",
            theme=theme,
            port_label=r"$P_2$",
        ),
    ),
    PreviewCase(
        "left_50_ohm_up",
        lambda theme, unit_length: Port50Ohm(
            unit_length=unit_length,
            side="left",
            load_direction="up",
            theme=theme,
            port_label=r"$P_1$",
            resistance_label_loc="top",
        ),
    ),
    PreviewCase(
        "right_50_ohm_down",
        lambda theme, unit_length: Port50Ohm(
            unit_length=unit_length,
            side="right",
            load_direction="down",
            theme=theme,
            port_label=r"$P_2$",
        ),
    ),
)


def main(argv: list[str] | None = None) -> int:
    return run_preview_cli(module_name="ports_terminations", cases=PREVIEW_CASES, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["LabelLocation", "Port50Ohm", "PortLoadDirection", "PortSide", "PortTerminal"]
