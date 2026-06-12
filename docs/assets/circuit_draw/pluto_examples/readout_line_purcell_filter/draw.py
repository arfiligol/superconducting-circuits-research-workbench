from __future__ import annotations

import schemdraw
import schemdraw.elements as elm
from _lib.style import Theme, circuit_drawing, shunt_capacitor


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    with circuit_drawing(theme=theme, unit=1.65) as drawing:
        elm.Dot(open=True).label("readout in", loc="left")
        elm.Line().right(0.8)
        elm.Capacitor().right().label("$C_{in}$")
        first_filter_node = elm.Dot()
        shunt_capacitor(
            drawing,
            first_filter_node.center,
            "$C_{f1}$",
            length=1.25,
            loc="left",
        )

        elm.Line().right(0.35)
        elm.Inductor().right().label("$L_{f1}$", loc="top")
        middle_filter_node = elm.Dot()
        shunt_capacitor(drawing, middle_filter_node.center, "$C_{f2}$", length=1.25)

        elm.Line().right(0.35)
        elm.Inductor().right().label("$L_{f2}$", loc="top")
        last_filter_node = elm.Dot()
        shunt_capacitor(drawing, last_filter_node.center, "$C_{f3}$", length=1.25)

        elm.Capacitor().right().label("$C_{out}$")
        elm.Line().right(0.8)
        elm.Dot(open=True).label("readout out", loc="right")

    return drawing
