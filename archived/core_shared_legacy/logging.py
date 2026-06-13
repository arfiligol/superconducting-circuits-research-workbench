"""Colored logging setup with Rich."""

import logging
from typing import Literal

from rich.logging import RichHandler

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def setup_logging(
    level: LogLevel = "INFO",
    show_path: bool = False,
    show_time: bool = True,
) -> None:
    """
    Configure root logger with Rich colored output.

    Call this once at CLI entry point (scripts/) before using any core/ modules.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        show_path: Show file path in log output
        show_time: Show timestamp in log output

    Example:
        ```python
        from core.shared.logging import setup_logging

        def main() -> None:
            setup_logging(level="DEBUG")
            # Now all core/ logging will be colored
        ```
    """
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                show_path=show_path,
                show_time=show_time,
                markup=True,
            )
        ],
    )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Convenience wrapper for logging.getLogger().

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance

    Example:
        ```python
        from core.shared.logging import get_logger

        logger = get_logger(__name__)
        logger.info("Processing %s", filename)
        ```
    """
    return logging.getLogger(name)
