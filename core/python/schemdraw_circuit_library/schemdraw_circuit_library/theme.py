from __future__ import annotations

from typing import Literal

type Theme = Literal["light", "dark"]


def theme_color(theme: Theme) -> str:
    if theme == "light":
        return "#111827"
    if theme == "dark":
        return "#f8fafc"
    raise ValueError("theme must be 'light' or 'dark'")
