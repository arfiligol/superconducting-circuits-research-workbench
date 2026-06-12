from __future__ import annotations

import schemdraw
import schemdraw.elements as elm
from _lib.style import Theme, circuit_drawing, offset, shunt_capacitor, shunt_josephson


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    with circuit_drawing(theme=theme, unit=1.85) as drawing:
        elm.Dot(open=True).label("$P_1$", loc="left")
        elm.Line().right(0.8)
        elm.Capacitor().right().label("$C_c$")
        tank_node = elm.Dot()
        shunt_josephson(drawing, tank_node.center, "$L_J$")

        elm.Line().right(1.3)
        capacitance_node = elm.Dot()
        shunt_capacitor(drawing, capacitance_node.center, "$C_J$")

        with drawing.hold():
            drawing.move_from(offset(tank_node.center, dx=-0.8, dy=1.8))
            elm.Dot(open=True).label("pump", loc="left")
            elm.Line().right(0.8)
            pump_tap = elm.Dot()
            elm.Line().right(0.8)
            elm.Dot(open=True)

            with drawing.hold():
                drawing.move_from(pump_tap.center)
                elm.Capacitor().down().toy(tank_node.center).label("$C_p$", loc="right")

    return drawing
