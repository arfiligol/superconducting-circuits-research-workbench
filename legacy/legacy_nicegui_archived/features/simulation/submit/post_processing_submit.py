"""Post-processing submit orchestration helpers."""

from __future__ import annotations

from typing import Any

from legacy.legacy_nicegui_archived.features.simulation.api_client import submit_post_processing_task
from legacy.legacy_nicegui_archived.features.simulation.submit.request_builders import build_post_processing_submit_request


async def submit_post_processing_intent(
    intent: dict[str, Any],
    *,
    owner_client: Any,
) -> Any:
    """Submit one post-processing intent through the persisted task API."""
    submission = build_post_processing_submit_request(intent)
    return await submit_post_processing_task(
        submission.api_request,
        client=owner_client,
    )
