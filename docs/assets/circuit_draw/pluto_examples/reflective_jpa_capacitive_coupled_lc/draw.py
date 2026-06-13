from __future__ import annotations

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import ReflectiveJPACapacitiveCoupledLC


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    unit_length = 2.55
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=12) as drawing:
        drawing.add(
            ReflectiveJPACapacitiveCoupledLC(
                component_id="jpa",
                unit_length=unit_length,
                theme=theme,
                resonator_cap_label=r"$C_{\mathrm{res}}$",
                josephson_label=r"$JJ$",
                port_label=r"$P_1$",
            )
        )

    return drawing
