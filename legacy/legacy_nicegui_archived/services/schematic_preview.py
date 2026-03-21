"""Helpers for rendering zoomable schematic SVG previews."""

from __future__ import annotations

import re

_PT_TO_PX = 96.0 / 72.0
MIN_PREVIEW_ZOOM = 0.4
MAX_PREVIEW_ZOOM = 4.0
PREVIEW_ZOOM_STEP = 0.2

_VIEWBOX_PATTERN = re.compile(
    r'viewBox="([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)"'
)
_WIDTH_PATTERN = re.compile(r'width="([0-9.eE+-]+)pt"')
_HEIGHT_PATTERN = re.compile(r'height="([0-9.eE+-]+)pt"')


def clamp_preview_zoom(value: float) -> float:
    """Clamp zoom level into the supported range."""
    return max(MIN_PREVIEW_ZOOM, min(MAX_PREVIEW_ZOOM, round(float(value), 2)))


def preview_zoom_text(value: float) -> str:
    """Format zoom level for compact UI labels."""
    return f"{round(clamp_preview_zoom(value) * 100.0)}%"


def _extract_svg_size_px(svg_content: str) -> tuple[float, float] | None:
    """Extract the base SVG size in pixels from viewBox or width/height attributes."""
    viewbox = _VIEWBOX_PATTERN.search(svg_content)
    if viewbox:
        view_w = float(viewbox.group(3))
        view_h = float(viewbox.group(4))
        if view_w > 0 and view_h > 0:
            return (view_w * _PT_TO_PX, view_h * _PT_TO_PX)

    width_match = _WIDTH_PATTERN.search(svg_content)
    height_match = _HEIGHT_PATTERN.search(svg_content)
    if not width_match or not height_match:
        return None

    width_px = float(width_match.group(1)) * _PT_TO_PX
    height_px = float(height_match.group(1)) * _PT_TO_PX
    if width_px <= 0 or height_px <= 0:
        return None
    return (width_px, height_px)


def build_zoomable_schematic_html(svg_content: str, zoom: float) -> str:
    """Wrap an SVG string into a scrollable zoom stage."""
    safe_zoom = clamp_preview_zoom(zoom)
    size = _extract_svg_size_px(svg_content)

    if size is None:
        return (
            "<div class='schematic-zoom-content'>"
            f"<div class='schematic-zoom-stage' style='transform: scale({safe_zoom:.3f});'>"
            f"{svg_content}"
            "</div>"
            "</div>"
        )

    width_px, height_px = size
    scaled_w = max(width_px * safe_zoom, 320.0)
    scaled_h = max(height_px * safe_zoom, 220.0)
    return (
        f"<div class='schematic-zoom-content' style='width: {scaled_w:.1f}px; "
        f"height: {scaled_h:.1f}px;'>"
        f"<div class='schematic-zoom-stage' style='transform: scale({safe_zoom:.3f});'>"
        f"{svg_content}"
        "</div>"
        "</div>"
    )
