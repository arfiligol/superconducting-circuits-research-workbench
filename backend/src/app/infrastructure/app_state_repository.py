from __future__ import annotations

from src.app.infrastructure.rewrite_app_state_repository import (
    InMemoryRewriteAppStateRepository,
)

InMemoryAppStateRepository = InMemoryRewriteAppStateRepository

__all__ = ["InMemoryAppStateRepository"]
