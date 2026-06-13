"""Package-local logging helpers for Python analysis code."""

from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a standard library logger for analysis modules."""
    return logging.getLogger(name)
