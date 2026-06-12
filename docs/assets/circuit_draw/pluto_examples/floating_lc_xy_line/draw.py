from __future__ import annotations

import schemdraw
import schemdraw.elements as elm
from _lib.style import Theme, circuit_drawing


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    with circuit_drawing(theme=theme) as drawing:
        elm.Dot(open=True).label("XY", loc="left")
        elm.Line().right(0.8)
        elm.Capacitor().right().label("$C_{xy}$")
        plus_node = elm.Dot().label("+", loc="top")

        with drawing.hold():
            drawing.move_from(plus_node.center)
            elm.Inductor().down(2.0).label("$L_q$", loc="left")
            minus_node = elm.Dot().label("-", loc="bottom")

        with drawing.hold():
            drawing.move_from(plus_node.center)
            elm.Line().right(1.2)
            elm.Capacitor().down().toy(minus_node.center).label("$C_q$", loc="right")
            elm.Line().to(minus_node.center)

        with drawing.hold():
            drawing.move_from(minus_node.center)
            elm.Line().right(0.7)
            elm.Dot(open=True).label("$q_-$", loc="right")

    return drawing
