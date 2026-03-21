"""Characterization view helpers."""

from __future__ import annotations

from legacy.legacy_nicegui_archived.features.characterization.views.result_artifacts import (
    RESULT_CATEGORY_LABELS,
    artifact_categories,
    artifacts_in_category,
    build_result_artifacts_for_analysis,
)
from legacy.legacy_nicegui_archived.ui.testing import with_test_id as _with_test_id


def _result_view_controls_row_classes() -> str:
    """Shared responsive row classes for Result View controls."""
    return "w-full items-end gap-3 mt-3 mb-3 flex-wrap lg:flex-nowrap"


__all__ = [
    "RESULT_CATEGORY_LABELS",
    "_result_view_controls_row_classes",
    "_with_test_id",
    "artifact_categories",
    "artifacts_in_category",
    "build_result_artifacts_for_analysis",
]
