from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .from_schematic_export import (
        UnsupportedSchematicComponentError,
        add_schematic_export_to_drawing,
        load_schematic_export,
    )
    from .preview import (
        PREVIEW_IMAGE_FORMATS,
        PreviewCase,
        build_preview_gallery,
        run_preview_cli,
    )
    from .variants import IMAGE_FORMATS, THEME_VARIANTS, render_theme_variants

__all__ = [
    "IMAGE_FORMATS",
    "PREVIEW_IMAGE_FORMATS",
    "THEME_VARIANTS",
    "PreviewCase",
    "UnsupportedSchematicComponentError",
    "add_schematic_export_to_drawing",
    "build_preview_gallery",
    "load_schematic_export",
    "render_theme_variants",
    "run_preview_cli",
]


def __getattr__(name: str) -> Any:
    if name in {
        "UnsupportedSchematicComponentError",
        "add_schematic_export_to_drawing",
        "load_schematic_export",
    }:
        from . import from_schematic_export

        return getattr(from_schematic_export, name)

    if name in {
        "PREVIEW_IMAGE_FORMATS",
        "PreviewCase",
        "build_preview_gallery",
        "run_preview_cli",
    }:
        from . import preview

        return getattr(preview, name)

    if name in {"IMAGE_FORMATS", "THEME_VARIANTS", "render_theme_variants"}:
        from . import variants

        return getattr(variants, name)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
