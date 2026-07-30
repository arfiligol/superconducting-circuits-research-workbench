from __future__ import annotations

from pathlib import Path

from circuit_plans.d3_auxiliary import build_auxiliary_drawing
from _lib.style import Theme


SCHEMATIC_EXPORT_PATH = Path(__file__).with_name("schematic_export.json")


def build_drawing(theme: Theme = "light"):
    return build_auxiliary_drawing(
        str(SCHEMATIC_EXPORT_PATH),
        kind="linewidth_la_hybridized",
        theme=theme,
    )
