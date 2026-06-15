from __future__ import annotations

from typing import Literal

type Theme = Literal["light", "dark"]

SCHEMATIC_DOT_RADIUS: float = 0.1


def theme_color(theme: Theme) -> str:
    if theme == "light":
        return "#111827"
    if theme == "dark":
        return "#f8fafc"
    raise ValueError("theme must be 'light' or 'dark'")
