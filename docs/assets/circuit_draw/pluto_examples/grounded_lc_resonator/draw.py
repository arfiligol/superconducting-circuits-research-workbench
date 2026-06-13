from __future__ import annotations

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import GroundedLCResonator


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    unit_length = 3.0
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=12) as drawing:
        drawing.add(
            GroundedLCResonator(
                component_id="resonator",
                name="r",
                unit_length=unit_length,
                theme=theme,
                port_label=r"$P_1$",
            )
        )

    return drawing
