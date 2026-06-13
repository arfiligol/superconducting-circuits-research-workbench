from __future__ import annotations

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import FloatingLCXYResonator


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    unit_length = 2.35
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=11) as drawing:
        drawing.add(
            FloatingLCXYResonator(
                component_id="floating_xy",
                unit_length=unit_length,
                theme=theme,
                pad1_label=r"$P_1$",
                pad2_label=r"$P_2$",
                xy_label=r"$XY$",
            )
        )

    return drawing
