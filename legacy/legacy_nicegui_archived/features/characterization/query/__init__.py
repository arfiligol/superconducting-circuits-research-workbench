"""Characterization query helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from legacy.legacy_nicegui_archived.features.characterization.query.analysis_registry import (
    ANALYSIS_REGISTRY,
    AnalysisCapabilityDecision,
    AnalysisConfigField,
    AnalysisDescriptor,
    evaluate_analysis_capability_gating,
    get_analysis_descriptor,
    get_available_analyses,
    is_analysis_completed,
    list_cross_dataset_analyses,
    list_dataset_analyses,
)
from legacy.legacy_nicegui_archived.features.characterization.query.trace_scope import (
    CharacterizationTraceScopeUnitOfWork,
    TraceSourceSummary,
    count_scope_trace_records,
    hydrate_trace_index_rows_with_provenance,
    list_design_scope_source_summaries,
    list_scope_compatible_trace_index_page,
    list_scope_compatible_trace_source_summaries,
)


def _latest_completed_analysis_run_summaries(
    summaries: Sequence[Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    """Collapse primitive run summaries to the latest completed row per analysis id."""
    latest_by_analysis: dict[str, dict[str, object]] = {}
    for summary in summaries:
        analysis_id = str(summary.get("analysis_id", "")).strip()
        if not analysis_id or str(summary.get("status", "")).strip() != "completed":
            continue
        raw_analysis_run_id = summary.get("analysis_run_id", summary.get("bundle_id", 0))
        analysis_run_id = (
            int(raw_analysis_run_id) if isinstance(raw_analysis_run_id, int | str) else 0
        )
        current = latest_by_analysis.get(analysis_id)
        current_analysis_run_id = 0
        if current is not None:
            raw_current_run_id = current.get("analysis_run_id", current.get("bundle_id", 0))
            if isinstance(raw_current_run_id, int | str):
                current_analysis_run_id = int(raw_current_run_id)
        if current is None or analysis_run_id >= current_analysis_run_id:
            latest_by_analysis[analysis_id] = dict(summary)
    return latest_by_analysis


def _completed_result_analysis_ids(
    *,
    analyses: Sequence[Mapping[str, object]],
    analysis_method_groups: Mapping[str, Mapping[str, list]],
    latest_completed_runs: Mapping[str, Mapping[str, object]],
) -> list[str]:
    """Return result-view analysis ids in registry order."""
    completed_ids: list[str] = []
    for analysis in analyses:
        analysis_id = str(analysis.get("id", "")).strip()
        if not analysis_id:
            continue
        if analysis_method_groups.get(analysis_id) or analysis_id in latest_completed_runs:
            completed_ids.append(analysis_id)
    return completed_ids


__all__ = [
    "ANALYSIS_REGISTRY",
    "AnalysisCapabilityDecision",
    "AnalysisConfigField",
    "AnalysisDescriptor",
    "CharacterizationTraceScopeUnitOfWork",
    "TraceSourceSummary",
    "_completed_result_analysis_ids",
    "_latest_completed_analysis_run_summaries",
    "count_scope_trace_records",
    "evaluate_analysis_capability_gating",
    "get_analysis_descriptor",
    "get_available_analyses",
    "hydrate_trace_index_rows_with_provenance",
    "is_analysis_completed",
    "list_cross_dataset_analyses",
    "list_dataset_analyses",
    "list_design_scope_source_summaries",
    "list_scope_compatible_trace_index_page",
    "list_scope_compatible_trace_source_summaries",
]
