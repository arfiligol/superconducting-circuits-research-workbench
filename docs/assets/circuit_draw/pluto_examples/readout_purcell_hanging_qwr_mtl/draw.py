from __future__ import annotations

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import ReadoutPurcellHangingQWRMTL


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    unit_length = 1.55
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=9) as drawing:
        drawing.add(
            ReadoutPurcellHangingQWRMTL(
                component_id="readout_filter_qwr_mtl",
                unit_length=unit_length,
                track_gap_units=1.0,
                qwr_gap_units=2.05,
                window_length_units=1.15,
                theme=theme,
                filter_label=None,
                left_port_label=r"$P_1$",
                right_port_label=r"$P_2$",
            )
        )

    return drawing
