from __future__ import annotations

from typing import Literal

import schemdraw
import schemdraw.elements as elm
from _lib.style import Theme, circuit_drawing, offset
from schemdraw.types import XY

CouplingElement = Literal["capacitor", "controlled-source"]


def _draw_mtl_window_markers(
    drawing: schemdraw.Drawing,
    readout_start: XY,
    qwr_start: XY,
    *,
    coupling: CouplingElement,
    dx: float,
    label: str,
) -> None:
    top = offset(readout_start, dx=dx)
    bottom = offset(qwr_start, dx=dx)
    with drawing.hold():
        drawing.move_from(top)
        elm.Line().down(0.25)
        if coupling == "capacitor":
            elm.Capacitor().toy(bottom).label(label, loc="right")
        else:
            elm.SourceControlledV().toy(bottom).label(label, loc="right")


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    with circuit_drawing(theme=theme, unit=1.55) as drawing:
        elm.Dot(open=True).label("readout in", loc="left")
        elm.Line().right(1.0)
        window_start = elm.Dot()
        elm.Line().right(3.4)
        elm.Dot()
        elm.Line().right(1.0)
        elm.Dot(open=True).label("readout out", loc="right")

        with drawing.hold():
            drawing.move_from(offset(window_start.center, dy=-1.8))
            qwr_head = elm.Dot().label("QWR head", loc="left")
            with drawing.hold():
                elm.Line().down(0.45)
                elm.Ground()
            elm.Line().right(3.4).label("quarter-wave resonator", loc="bottom")
            elm.Dot(open=True).label("open tail", loc="right")

        _draw_mtl_window_markers(
            drawing,
            window_start.center,
            qwr_head.center,
            coupling="capacitor",
            dx=1.0,
            label="$C_{12}$",
        )
        _draw_mtl_window_markers(
            drawing,
            window_start.center,
            qwr_head.center,
            coupling="controlled-source",
            dx=2.35,
            label="$K_{12}$",
        )

    return drawing
