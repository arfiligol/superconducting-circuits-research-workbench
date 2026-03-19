from __future__ import annotations

from pathlib import Path

import schemdraw
import schemdraw.elements as elm

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIRS = [
    ROOT / "docs" / "assets",
    ROOT / "docs" / "docs_zhtw" / "assets",
]


def draw_coupled_line_ladder_section(output_path: Path) -> None:
    with schemdraw.Drawing(show=False) as d:
        d.config(unit=2.0, fontsize=13)

        top_start = d.here
        d += elm.Dot(open=True)
        d += elm.Inductor().right().label("L_A")
        top_mid = d.here
        d += elm.Line().right().length(1.2)
        d += elm.Dot(open=True)

        d.push()
        d.move_from(top_mid, dx=0, dy=-0.1)
        d += elm.Capacitor().down().label("C_A")
        d += elm.Ground()
        d.pop()

        d.push()
        d.move_from(top_mid, dx=0.4, dy=0.15)
        d += elm.Line().down().length(1.5)
        d += elm.Capacitor().label("C_AB", loc="bottom")
        d += elm.Line().down().length(0.8)
        d.pop()

        d.move_from(top_start, dy=-2.4)
        d += elm.Dot(open=True)
        d += elm.Inductor().right().label("L_B")
        bot_mid = d.here
        d += elm.Line().right().length(1.2)
        d += elm.Dot(open=True)

        d.push()
        d.move_from(bot_mid, dx=0, dy=-0.1)
        d += elm.Capacitor().down().label("C_B")
        d += elm.Ground()
        d.pop()

        d.push()
        d.move_from(top_mid, dx=-0.45, dy=0.05)
        d += elm.Line().down().length(0.35)
        d += elm.SourceControlledV().down().label("K", loc="right")
        d += elm.Line().down().length(0.35)
        d.pop()

        d.save(str(output_path))


def main() -> None:
    for output_dir in OUTPUT_DIRS:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "coupled-line-ladder-section.svg"
        draw_coupled_line_ladder_section(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
