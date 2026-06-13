from __future__ import annotations

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import PointCoupledReadoutPurcell


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    unit_length = 1.85
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=10) as drawing:
        drawing.add(
            PointCoupledReadoutPurcell(
                component_id="readout_filter",
                unit_length=unit_length,
                theme=theme,
                input_line_label=None,
                output_line_label=None,
                left_port_label=r"$P_1$",
                right_port_label=r"$P_2$",
            )
        )

    return drawing
