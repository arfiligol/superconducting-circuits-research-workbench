from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from schemdraw import Drawing

from ..theme import Theme

THEME_VARIANTS: tuple[Theme, Theme] = ("light", "dark")
IMAGE_FORMATS: tuple[str, str] = ("svg", "png")


def render_theme_variants(
    build_drawing: Callable[[Theme], Drawing],
    output_dir: Path,
    *,
    stem: str = "diagram",
    formats: Sequence[str] = IMAGE_FORMATS,
    dpi: int = 96,
) -> tuple[Path, ...]:
    """Render light/dark drawing variants from one topology-preserving builder."""

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for theme in THEME_VARIANTS:
        drawing = build_drawing(theme)
        for image_format in formats:
            path = output_dir / f"{stem}.{theme}.{image_format}"
            kwargs: dict[str, Any] = {"transparent": True}
            if image_format == "png":
                kwargs["dpi"] = dpi
            drawing.save(str(path), **kwargs)
            rendered.append(path)
    return tuple(rendered)
