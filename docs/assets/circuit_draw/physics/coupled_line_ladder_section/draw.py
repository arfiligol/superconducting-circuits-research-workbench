from __future__ import annotations

import schemdraw
import schemdraw.elements as elm
from _lib.style import Theme, circuit_drawing, offset, shunt_capacitor


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    with circuit_drawing(theme=theme, unit=1.85, fontsize=13) as drawing:
        top_input = elm.Dot(open=True).label("$A_{in}$", loc="left")
        elm.Inductor().right().label("$L_A$", loc="top")
        top_mid = elm.Dot()
        elm.Line().right(1.3)
        top_shunt = elm.Dot()
        elm.Line().right(0.8)
        elm.Dot(open=True).label("$A_{out}$", loc="right")

        drawing.move_from(offset(top_input.center, dy=-2.7))
        elm.Dot(open=True).label("$B_{in}$", loc="left")
        elm.Inductor().right().label("$L_B$", loc="bottom")
        bottom_mid = elm.Dot()
        elm.Line().right(1.3)
        bottom_shunt = elm.Dot()
        elm.Line().right(0.8)
        elm.Dot(open=True).label("$B_{out}$", loc="right")

        shunt_capacitor(drawing, top_shunt.center, "$C_A$", length=1.05, loc="right")
        shunt_capacitor(drawing, bottom_shunt.center, "$C_B$", length=1.05, loc="right")

        with drawing.hold():
            drawing.move_from(offset(top_mid.center, dx=-0.35))
            elm.SourceControlledV().toy(offset(bottom_mid.center, dx=-0.35)).label(
                "$K_{AB}$",
                loc="right",
            )

        with drawing.hold():
            drawing.move_from(offset(top_mid.center, dx=0.65))
            elm.Capacitor().toy(offset(bottom_mid.center, dx=0.65)).label(
                "$C_{AB}$",
                loc="right",
            )

    return drawing
