from __future__ import annotations

import schemdraw
import schemdraw.elements as elm
from _lib.style import Theme, circuit_drawing, shunt_capacitor


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    with circuit_drawing(theme=theme, unit=1.65) as drawing:
        elm.Dot(open=True).label("head / $P_1$", loc="left")
        for index in range(1, 5):
            elm.Inductor().right().label(f"$L_{index}$", loc="top")
            section_node = elm.Dot()
            shunt_capacitor(drawing, section_node.center, f"$C_{index}$", length=1.25)
        elm.Line().right(0.6)
        elm.Dot(open=True).label("tail / $P_2$", loc="right")

    return drawing
