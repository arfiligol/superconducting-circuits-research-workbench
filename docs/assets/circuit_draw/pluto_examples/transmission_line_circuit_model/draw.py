from __future__ import annotations

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import PiSectionChain


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    unit_length = 1.45
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=10) as drawing:
        drawing.add(
            PiSectionChain(
                component_id="cpw",
                n=4,
                unit_length=unit_length,
                height_units=0.85,
                theme=theme,
                reduce_capacitance=True,
                left_port_label=r"$P_1$",
                right_port_label=r"$P_2$",
            )
        )

    return drawing
