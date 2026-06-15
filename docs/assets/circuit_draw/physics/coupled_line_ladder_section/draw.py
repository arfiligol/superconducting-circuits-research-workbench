from __future__ import annotations

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import CoupledLineLadderSection


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    unit_length = 2.2
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=12) as drawing:
        drawing.add(
            CoupledLineLadderSection(
                component_id="coupled_line_section",
                unit_length=unit_length,
                track_gap_units=1.5,
                theme=theme,
                capacitive_label=r"$C_{AB}$",
                inductive_label=r"$M_{AB}$",
            )
        )

    return drawing
