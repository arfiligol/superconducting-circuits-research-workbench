from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import schemdraw
import schemdraw.elements as elm
from matplotlib import pyplot as plt

from schemdraw_circuit_library.theme import Theme, theme_color

type PreviewTheme = Literal["light", "dark", "both"]
type PreviewFactory = Callable[[Theme, float], elm.ElementCompound]

PREVIEW_IMAGE_FORMATS: tuple[str, str] = ("svg", "png")


@dataclass(frozen=True)
class PreviewCase:
    """One executable-preview component case for an ElementCompound module."""

    name: str
    factory: PreviewFactory


def build_preview_gallery(
    cases: Sequence[PreviewCase],
    *,
    theme: Theme,
    unit_length: float,
) -> schemdraw.Drawing:
    """Build a single drawing containing the module's curated component previews."""

    drawing = schemdraw.Drawing(show=False, transparent=True, dpi=96)
    drawing.config(unit=unit_length, color=theme_color(theme), lw=1.8, fontsize=12)

    row_gap = unit_length * 4.4
    for index, case in enumerate(cases):
        component = case.factory(theme, unit_length)
        drawing.add(component.at((0, -index * row_gap)))

    return drawing


def run_preview_cli(
    *,
    module_name: str,
    cases: Sequence[PreviewCase],
    argv: Sequence[str] | None = None,
) -> int:
    """Run a local authoring preview for a component module."""

    parser = argparse.ArgumentParser(
        description=f"Preview Schemdraw ElementCompound components from {module_name}."
    )
    parser.add_argument("--theme", choices=("light", "dark", "both"), default="light")
    parser.add_argument("--unit-length", type=float, default=3.0)
    parser.add_argument("--no-show", action="store_true")
    parser.add_argument("--save", type=Path)
    args = parser.parse_args(argv)

    themes: tuple[Theme, ...] = ("light", "dark") if args.theme == "both" else (args.theme,)

    for theme in themes:
        drawing = build_preview_gallery(cases, theme=theme, unit_length=args.unit_length)
        if args.save is not None:
            _save_preview(drawing, args.save, module_name, theme)
        if not args.no_show:
            drawing.draw(show=True)
        else:
            plt.close("all")

    return 0


def _save_preview(
    drawing: schemdraw.Drawing,
    output_dir: Path,
    module_name: str,
    theme: Theme,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for image_format in PREVIEW_IMAGE_FORMATS:
        path = output_dir / f"{module_name}.{theme}.{image_format}"
        if image_format == "png":
            drawing.save(str(path), transparent=True, dpi=96)
        else:
            drawing.save(str(path), transparent=True)
