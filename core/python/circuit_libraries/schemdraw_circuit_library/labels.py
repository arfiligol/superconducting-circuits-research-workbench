from __future__ import annotations


def named_math_label(symbol: str, name: str | None = None) -> str:
    """Build a compact Schemdraw math label for an optionally named symbol."""

    if not name:
        return rf"${symbol}$"
    return rf"${symbol}_{{{name}}}$"
