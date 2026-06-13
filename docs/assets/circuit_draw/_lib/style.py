from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import schemdraw
import schemdraw.elements as elm
from schemdraw_circuit_library.theme import Theme, theme_color


@contextmanager
def circuit_drawing(
    *,
    theme: Theme = "light",
    unit: float = 2.0,
    fontsize: int = 12,
    dpi: int = 384,
) -> Iterator[schemdraw.Drawing]:
    elm.style(elm.STYLE_IEEE)
    with schemdraw.Drawing(show=False, transparent=True, dpi=dpi) as drawing:
        configure(drawing, theme=theme, unit=unit, fontsize=fontsize)
        yield drawing


def configure(
    drawing: schemdraw.Drawing,
    *,
    theme: Theme = "light",
    unit: float = 1.9,
    fontsize: int = 11,
) -> None:
    color = theme_color(theme)
    drawing.config(unit=unit, fontsize=fontsize, font="sans", lw=1.8, color=color)
