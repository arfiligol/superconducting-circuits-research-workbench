from __future__ import annotations

from pathlib import Path

import schemdraw
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library.rendering import (
    add_schematic_export_to_drawing,
    load_schematic_export,
)

SCHEMATIC_EXPORT_PATH = Path(__file__).with_name("schematic_export.json")


def build_drawing(theme: Theme = "light") -> schemdraw.Drawing:
    with circuit_drawing(theme=theme, unit=1.7, fontsize=9) as drawing:
        add_schematic_export_to_drawing(
            drawing,
            load_schematic_export(SCHEMATIC_EXPORT_PATH),
            theme=theme,
        )
    return drawing
