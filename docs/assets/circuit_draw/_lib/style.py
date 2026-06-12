from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import schemdraw
import schemdraw.elements as elm
from schemdraw.types import XY
from schemdraw.util import Point

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


def as_point(point: XY) -> Point:
    return point if isinstance(point, Point) else Point(point)


def offset(point: XY, *, dx: float = 0, dy: float = 0) -> Point:
    base = as_point(point)
    return Point((base.x + dx, base.y + dy))


def shunt_capacitor(
    drawing: schemdraw.Drawing,
    start: XY,
    label: str,
    *,
    length: float = 1.5,
    loc: str = "right",
) -> None:
    with drawing.hold():
        drawing.move_from(as_point(start))
        elm.Capacitor().down(length).label(label, loc=loc)
        elm.Ground()


def shunt_inductor(
    drawing: schemdraw.Drawing,
    start: XY,
    label: str,
    *,
    length: float = 1.5,
    loc: str = "right",
) -> None:
    with drawing.hold():
        drawing.move_from(as_point(start))
        elm.Inductor().down(length).label(label, loc=loc)
        elm.Ground()


def shunt_josephson(
    drawing: schemdraw.Drawing,
    start: XY,
    label: str,
    *,
    length: float = 1.5,
    loc: str = "right",
) -> None:
    with drawing.hold():
        drawing.move_from(as_point(start))
        elm.Josephson().down(length).label(label, loc=loc)
        elm.Ground()


def save_svg(drawing: schemdraw.Drawing, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    drawing.save(str(output_path))
