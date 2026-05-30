from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import schemdraw
import schemdraw.elements as elm
from schemdraw.types import XY
from schemdraw.util import Point

ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT / "docs" / "assets"


def _configure(drawing: schemdraw.Drawing, *, unit: float = 1.9) -> None:
    drawing.config(unit=unit, fontsize=11, lw=1.7)


def _save(filename: str, draw: Callable[[Path], None]) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ASSETS_DIR / filename
    draw(output_path)
    print(f"wrote {output_path.relative_to(ROOT)}")


def _as_point(point: XY) -> Point:
    return point if isinstance(point, Point) else Point(point)


def _shunt_capacitor(drawing: schemdraw.Drawing, start: XY, label: str) -> None:
    drawing.push()
    drawing.move_from(_as_point(start), dx=0, dy=-0.05)
    drawing += elm.Capacitor().down().label(label, loc="right")
    drawing += elm.Ground()
    drawing.pop()


def draw_parallel_lc_resonator(output_path: Path) -> None:
    with schemdraw.Drawing(show=False) as d:
        _configure(d)

        d += elm.Dot(open=True).label("P1", loc="left")
        d += elm.Line().right().length(1.0)
        d += elm.Dot()

        d.push()
        d += elm.Inductor().down().label("L_r", loc="right")
        d += elm.Ground()
        d.pop()

        d += elm.Line().right().length(1.2)
        cap_node = d.here
        d += elm.Dot()
        _shunt_capacitor(d, cap_node, "C_r")

        d.save(str(output_path))


def draw_reflective_jpa_capacitive_coupled_lc(output_path: Path) -> None:
    with schemdraw.Drawing(show=False) as d:
        _configure(d)

        d += elm.Dot(open=True).label("P1 readout", loc="left")
        d += elm.Line().right().length(0.9)
        d += elm.Capacitor().right().label("C_c")
        tank_node = d.here
        d += elm.Dot()

        d.push()
        d += elm.Inductor().down().label("L_J", loc="right")
        d += elm.Ground()
        d.pop()

        d += elm.Line().right().length(1.0)
        cap_node = d.here
        d += elm.Dot()
        _shunt_capacitor(d, cap_node, "C_J")

        d.push()
        d.move_from(tank_node, dx=-0.15, dy=1.3)
        d += elm.SourceSin().down().label("pump slot", loc="left")
        d += elm.Line().down().length(0.25)
        d.pop()

        d.save(str(output_path))


def draw_floating_lc_xy_line(output_path: Path) -> None:
    with schemdraw.Drawing(show=False) as d:
        _configure(d)

        d += elm.Dot(open=True).label("XY", loc="left")
        d += elm.Line().right().length(0.8)
        d += elm.Capacitor().right().label("C_xy")
        plus_node = d.here
        d += elm.Dot().label("+", loc="top")

        d.push()
        d += elm.Inductor().down().length(2.0).label("L_q", loc="left")
        minus_node = d.here
        d += elm.Dot().label("-", loc="bottom")
        d.pop()

        d.push()
        d.move_from(plus_node)
        d += elm.Line().right().length(1.1)
        d += elm.Capacitor().down().length(2.0).label("C_q", loc="right")
        d += elm.Line().left().length(1.1)
        d.pop()

        d.push()
        d.move_from(minus_node, dx=0, dy=-0.15)
        d += elm.Line().right().length(0.55)
        d += elm.Dot(open=True).label("floating node", loc="right")
        d.pop()

        d.save(str(output_path))


def draw_transmission_line_circuit_model(output_path: Path) -> None:
    with schemdraw.Drawing(show=False) as d:
        _configure(d, unit=1.7)

        d += elm.Dot(open=True).label("head / P1", loc="left")
        for index in range(1, 5):
            d += elm.Inductor().right().label(f"L{index}", loc="top")
            section_node = d.here
            d += elm.Dot()
            _shunt_capacitor(d, section_node, f"C{index}")
        d += elm.Line().right().length(0.5)
        d += elm.Dot(open=True).label("tail / P2", loc="right")

        d.save(str(output_path))


def draw_readout_line_purcell_filter(output_path: Path) -> None:
    with schemdraw.Drawing(show=False) as d:
        _configure(d, unit=1.7)

        d += elm.Dot(open=True).label("readout in", loc="left")
        d += elm.Line().right().length(0.7)
        d += elm.Capacitor().right().label("C_in")
        first_filter_node = d.here
        d += elm.Dot()
        _shunt_capacitor(d, first_filter_node, "C_f1")

        d += elm.Inductor().right().label("L_f1", loc="top")
        middle_filter_node = d.here
        d += elm.Dot().label("Purcell filter", loc="top")
        _shunt_capacitor(d, middle_filter_node, "C_f2")

        d += elm.Inductor().right().label("L_f2", loc="top")
        last_filter_node = d.here
        d += elm.Dot()
        _shunt_capacitor(d, last_filter_node, "C_f3")

        d += elm.Capacitor().right().label("C_out")
        d += elm.Line().right().length(0.7)
        d += elm.Dot(open=True).label("readout out", loc="right")

        d.save(str(output_path))


def _draw_mtl_window_markers(
    drawing: schemdraw.Drawing,
    window_start: XY,
    *,
    readout_to_qwr_drop: float = 1.8,
) -> None:
    drawing.push()
    drawing.move_from(_as_point(window_start), dx=0.65, dy=0)
    drawing += elm.Line().down().length(0.35)
    drawing += elm.Capacitor().down().label("C12", loc="right")
    drawing += elm.Line().down().length(readout_to_qwr_drop - 1.15)
    drawing.pop()

    drawing.push()
    drawing.move_from(_as_point(window_start), dx=1.4, dy=0)
    drawing += elm.Line().down().length(0.35)
    drawing += elm.SourceControlledV().down().label("K12", loc="right")
    drawing += elm.Line().down().length(readout_to_qwr_drop - 1.15)
    drawing.pop()


def draw_readout_line_hanging_qwr_mtl(output_path: Path) -> None:
    with schemdraw.Drawing(show=False) as d:
        _configure(d, unit=1.6)

        d += elm.Dot(open=True).label("readout in", loc="left")
        d += elm.Line().right().length(1.2).label("readout line", loc="top")
        window_start = d.here
        d += elm.Dot()
        d += elm.Line().right().length(2.2).label("MTL window", loc="top")
        window_end = d.here
        d += elm.Dot()
        d += elm.Line().right().length(1.2)
        d += elm.Dot(open=True).label("readout out", loc="right")

        d.push()
        d.move_from(window_start, dx=0, dy=-1.8)
        d += elm.Dot().label("QWR head", loc="left")
        d.push()
        d += elm.Line().down().length(0.45)
        d += elm.Ground()
        d.pop()
        d += elm.Line().right().length(2.2).label("quarter-wave resonator", loc="bottom")
        d += elm.Dot(open=True).label("open tail", loc="right")
        d.pop()

        _draw_mtl_window_markers(d, window_start)

        d.push()
        d.move_from(window_end, dx=-0.1, dy=-0.35)
        d += elm.Line().left().length(2.0).label("finite coupled section", loc="bottom")
        d.pop()

        d.save(str(output_path))


def draw_readout_purcell_hanging_qwr_mtl(output_path: Path) -> None:
    with schemdraw.Drawing(show=False) as d:
        _configure(d, unit=1.45)

        d += elm.Dot(open=True).label("readout in", loc="left")
        d += elm.Capacitor().right().label("C_in")
        d += elm.Inductor().right().label("L_pf", loc="top")
        filter_node = d.here
        d += elm.Dot().label("Purcell filter", loc="top")
        _shunt_capacitor(d, filter_node, "C_pf")
        d += elm.Capacitor().right().label("C_out")

        d += elm.Line().right().length(0.9).label("readout line", loc="top")
        window_start = d.here
        d += elm.Dot()
        d += elm.Line().right().length(2.2).label("MTL window", loc="top")
        d += elm.Dot()
        d += elm.Line().right().length(0.8)
        d += elm.Dot(open=True).label("readout out", loc="right")

        d.push()
        d.move_from(window_start, dx=0, dy=-1.8)
        d += elm.Dot().label("QWR head", loc="left")
        d.push()
        d += elm.Line().down().length(0.45)
        d += elm.Ground()
        d.pop()
        d += elm.Line().right().length(2.2).label("hanging QWR", loc="bottom")
        d += elm.Dot(open=True).label("open tail", loc="right")
        d.pop()

        _draw_mtl_window_markers(d, window_start)

        d.save(str(output_path))


def main() -> None:
    outputs: list[tuple[str, Callable[[Path], None]]] = [
        ("pluto-00-parallel-lc-resonator.svg", draw_parallel_lc_resonator),
        (
            "pluto-01-reflective-jpa-capacitive-coupled-lc.svg",
            draw_reflective_jpa_capacitive_coupled_lc,
        ),
        ("pluto-02-floating-lc-xy-line.svg", draw_floating_lc_xy_line),
        ("pluto-03-transmission-line-circuit-model.svg", draw_transmission_line_circuit_model),
        ("pluto-04-readout-line-purcell-filter.svg", draw_readout_line_purcell_filter),
        ("pluto-05-readout-line-hanging-qwr-mtl.svg", draw_readout_line_hanging_qwr_mtl),
        (
            "pluto-06-readout-purcell-hanging-qwr-mtl.svg",
            draw_readout_purcell_hanging_qwr_mtl,
        ),
    ]

    for filename, draw in outputs:
        _save(filename, draw)


if __name__ == "__main__":
    main()
