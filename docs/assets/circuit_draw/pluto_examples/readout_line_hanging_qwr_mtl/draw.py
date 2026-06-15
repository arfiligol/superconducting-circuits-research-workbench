from __future__ import annotations

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import ReadoutLineHangingQWRMTL


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    unit_length = 1.75
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=10) as drawing:
        drawing.add(
            ReadoutLineHangingQWRMTL(
                component_id="readout_qwr_mtl",
                unit_length=unit_length,
                track_gap_units=1.35,
                window_length_units=1.15,
                theme=theme,
                readout_label=None,
                qwr_label=r"$\lambda/4\ \mathrm{QWR}$",
                left_port_label=r"$P_1$",
                right_port_label=r"$P_2$",
            )
        )

    return drawing
