"""Characterization page — unified analysis + results view."""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast
from uuid import uuid4

import pandas as pd
from nicegui import app, ui

from legacy.legacy_nicegui_archived.features.characterization.api_client import (
    ApiClientError,
    get_design_tasks,
    get_latest_characterization_result,
    get_task,
)
from legacy.legacy_nicegui_archived.features.characterization.query import (
    _completed_result_analysis_ids,
    _latest_completed_analysis_run_summaries,
)
from legacy.legacy_nicegui_archived.features.characterization.query.analysis_registry import list_dataset_analyses
from legacy.legacy_nicegui_archived.features.characterization.query.capability import evaluate_analysis_capability_gating
from legacy.legacy_nicegui_archived.features.characterization.query.trace_scope import (
    CharacterizationTraceScopeUnitOfWork,
    TraceSourceSummary,
    count_scope_trace_records,
    hydrate_trace_index_rows_with_provenance,
    list_design_scope_source_summaries,
    list_scope_compatible_trace_index_page,
    list_scope_compatible_trace_source_summaries,
)
from legacy.legacy_nicegui_archived.features.characterization.recovery import build_recovery_state
from legacy.legacy_nicegui_archived.features.characterization.state import (
    AnalysisRunAvailability,
    AnalysisRunUiState,
    AnalysisScopeCompatibility,
    CharacterizationRuntimeState,
    ResultArtifact,
)
from legacy.legacy_nicegui_archived.features.characterization.submit import (
    build_characterization_submission,
    submit_characterization_task,
)
from legacy.legacy_nicegui_archived.features.characterization.views import (
    _result_view_controls_row_classes,
    _with_test_id,
)
from legacy.legacy_nicegui_archived.features.characterization.views.result_artifacts import (
    RESULT_CATEGORY_LABELS,
    artifact_categories,
    artifacts_in_category,
    build_result_artifacts_for_analysis,
)
from legacy.legacy_nicegui_archived.services.characterization_runner import (
    SweepSupportDiagnostic,
    diagnose_analysis_sweep_support,
)
from legacy.legacy_nicegui_archived.services.dataset_profile import (
    design_profile_summary_text,
    normalize_dataset_profile,
)
from legacy.legacy_nicegui_archived.services.execution_context import build_ui_use_case_context
from legacy.legacy_nicegui_archived.ui.sections import section_card
from legacy.legacy_nicegui_archived.ui.states import render_empty_state
from core.analysis.domain import (
    ModeGroup,
    ParameterKey,
    trace_record_data_type,
    trace_record_parameter,
)
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import AnalysisRunRecord, ParameterDesignation

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_BIAS_RE = re.compile(r"^(.+?)_b(\d+)$")
_IDX_RE = re.compile(r"^(.+?)_(\d+)$")
_MODE_CANONICAL_RE = re.compile(r"^mode_(\d+)_ghz$")
_MODE_LEGACY_INDEX_RE = re.compile(r"^(?:mode_ghz|fr_ghz)_(\d+)$")
_MODE_LEGACY_SINGLE_RE = re.compile(r"^(?:mode_ghz|fr_ghz)$")
_ANALYSIS_RUN_SELECTED_KEY = "analysis_selected_run_by_dataset"
_ANALYSIS_RESULT_SELECTED_KEY = "analysis_selected_result_by_dataset"
_ANALYSIS_RESULT_CATEGORY_SELECTED_KEY = "analysis_selected_result_category_by_scope"
_ANALYSIS_RESULT_ARTIFACT_SELECTED_KEY = "analysis_selected_result_artifact_by_scope"
_ANALYSIS_RESULT_TRACE_MODE_SELECTED_KEY = "analysis_selected_result_trace_mode_by_scope"
_CATEGORY_LABELS: dict[str, str] = dict(RESULT_CATEGORY_LABELS)
_TRACE_MODE_ALL = ModeGroup.ALL.value
_TRACE_MODE_LABELS: dict[str, str] = {
    _TRACE_MODE_ALL: "All",
    ModeGroup.BASE.value: "Base",
    ModeGroup.SIDEBAND.value: "Sideband",
}
_TRACE_MODE_FILTER_OPTIONS: dict[str, str] = {
    _TRACE_MODE_ALL: "All Modes",
    ModeGroup.BASE.value: "Base",
    ModeGroup.SIDEBAND.value: "Sideband",
}
_MAX_BULK_TRACE_SELECTION = 2000
_ANALYSIS_HEARTBEAT_SECONDS = 5.0
_ANALYSIS_LONG_RUNNING_WARN_AFTER_SECONDS = 60


@dataclass(frozen=True)
class _PostRunResultViewSelection:
    """Result-view selection state to apply after a successful analysis run."""

    analysis_id: str
    trace_mode_filter: str
    category: str
    artifact_id: str


def _mode_index_from_key(name: str) -> int | None:
    match = _MODE_CANONICAL_RE.match(name)
    if match:
        return int(match.group(1))
    match = _MODE_LEGACY_INDEX_RE.match(name)
    if match:
        return int(match.group(1)) + 1
    if _MODE_LEGACY_SINGLE_RE.match(name):
        return 1
    return None


def _format_mode_label(name: str) -> str | None:
    mode_index = _mode_index_from_key(name)
    if mode_index is None:
        return None
    return f"Mode {mode_index} (GHz)"


def _display_param_name(name: str) -> str:
    mode_label = _format_mode_label(name)
    return mode_label if mode_label is not None else name


def _load_dataset_text_selection(storage_key: str, dataset_id: int) -> str:
    """Load one per-dataset string selection from user storage."""
    raw_map = app.storage.user.get(storage_key, {})
    if not isinstance(raw_map, dict):
        return ""
    selected = raw_map.get(str(dataset_id), "")
    return selected if isinstance(selected, str) else ""


def _save_dataset_text_selection(storage_key: str, dataset_id: int, token: str) -> None:
    """Save one per-dataset string selection into user storage."""
    raw_map = app.storage.user.get(storage_key, {})
    selected_map = dict(raw_map) if isinstance(raw_map, dict) else {}
    selected_map[str(dataset_id)] = token
    app.storage.user[storage_key] = selected_map


def _analysis_scope_key(dataset_id: int, analysis_id: str) -> str:
    """Build one stable scope key for dataset+analysis result-view state."""
    return f"{dataset_id}:{analysis_id}"


def _load_scope_text_selection(storage_key: str, scope_key: str) -> str:
    """Load one per-scope string selection from user storage."""
    raw_map = app.storage.user.get(storage_key, {})
    if not isinstance(raw_map, dict):
        return ""
    selected = raw_map.get(scope_key, "")
    return selected if isinstance(selected, str) else ""


def _save_scope_text_selection(storage_key: str, scope_key: str, token: str) -> None:
    """Save one per-scope string selection into user storage."""
    raw_map = app.storage.user.get(storage_key, {})
    selected_map = dict(raw_map) if isinstance(raw_map, dict) else {}
    selected_map[scope_key] = token
    app.storage.user[storage_key] = selected_map


def _resolve_selected_option(preferred: str, options: list[str]) -> str:
    """Resolve a selected option with graceful fallback."""
    if preferred in options:
        return preferred
    return options[0] if options else ""


def _build_post_run_result_view_selection(
    *,
    analysis_id: str,
    method_groups: dict[str, list],
) -> _PostRunResultViewSelection:
    """Choose a stable Result View target immediately after a successful run."""
    artifacts = build_result_artifacts_for_analysis(
        analysis_id=analysis_id,
        method_groups=_filter_method_groups_by_trace_mode(
            method_groups,
            trace_mode_filter=_TRACE_MODE_ALL,
        ),
        build_mode_vs_ljun_dataframe=_build_mode_vs_ljun_dataframe,
        build_resonator_table=_build_resonator_table,
        build_fit_parameter_table=_build_fit_parameter_table,
        is_summary_scalar=_is_summary_scalar_parameter,
    )
    if not artifacts:
        return _PostRunResultViewSelection(
            analysis_id=analysis_id,
            trace_mode_filter=_TRACE_MODE_ALL,
            category="",
            artifact_id="",
        )

    first_artifact = artifacts[0]
    return _PostRunResultViewSelection(
        analysis_id=analysis_id,
        trace_mode_filter=_TRACE_MODE_ALL,
        category=first_artifact.category,
        artifact_id=first_artifact.artifact_id,
    )


def _sync_result_view_selection_after_run(
    *,
    dataset_id: int,
    analysis: Mapping[str, object],
) -> _PostRunResultViewSelection:
    """Persist Result View state so refresh lands on the completed analysis."""
    analysis_id = str(analysis.get("id", "")).strip()
    raw_completed_methods = analysis.get("completed_methods", [])
    completed_methods = (
        set(raw_completed_methods)
        if isinstance(raw_completed_methods, Sequence)
        and not isinstance(raw_completed_methods, str | bytes)
        else set()
    )
    with get_unit_of_work() as uow:
        method_params = _group_by_method(uow.derived_params.list_by_dataset(dataset_id))
    analysis_method_groups = {
        method_key: list(method_params[method_key])
        for method_key in sorted(completed_methods)
        if method_key in method_params
    }
    selection = _build_post_run_result_view_selection(
        analysis_id=analysis_id,
        method_groups=analysis_method_groups,
    )
    _save_dataset_text_selection(
        _ANALYSIS_RESULT_SELECTED_KEY,
        dataset_id,
        selection.analysis_id,
    )
    analysis_scope_key = _analysis_scope_key(dataset_id, selection.analysis_id)
    _save_scope_text_selection(
        _ANALYSIS_RESULT_TRACE_MODE_SELECTED_KEY,
        analysis_scope_key,
        selection.trace_mode_filter,
    )
    _save_scope_text_selection(
        _ANALYSIS_RESULT_CATEGORY_SELECTED_KEY,
        analysis_scope_key,
        selection.category,
    )
    _save_scope_text_selection(
        _ANALYSIS_RESULT_ARTIFACT_SELECTED_KEY,
        analysis_scope_key,
        selection.artifact_id,
    )
    return selection


def _effective_analysis_requires(
    *,
    analysis_id: str,
    analysis_requires: dict[str, object],
) -> dict[str, object]:
    """Resolve runtime requires overrides for one analysis id."""
    resolved_requires = dict(analysis_requires)
    if analysis_id == "s21_resonance_fit":
        # Current fit execution path is fixed to S21.
        resolved_requires["parameter"] = "S21"
    return resolved_requires


def _normalize_profile_trace_index_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, str]]:
    """Normalize profile inference input so TraceRecord rows map to canonical trace kinds."""
    return [
        {
            "data_type": trace_record_data_type(row),
            "parameter": trace_record_parameter(row),
        }
        for row in rows
    ]


def _build_analysis_run_ui_state(
    *,
    has_compatible_traces: bool,
    selected_trace_count: int,
) -> AnalysisRunUiState:
    """Build availability text and run-button state from one compatibility source."""
    if not has_compatible_traces:
        return AnalysisRunUiState(
            has_compatible_traces=False,
            availability_text="Unavailable for current design scope",
            availability_class="text-warning",
            run_disabled=True,
            run_hint=(
                "No compatible traces found for the selected analysis in current design scope."
            ),
        )
    if selected_trace_count <= 0:
        return AnalysisRunUiState(
            has_compatible_traces=True,
            availability_text="Available for current design scope (no traces selected)",
            availability_class="text-positive",
            run_disabled=True,
            run_hint="Select at least one trace to run.",
        )
    return AnalysisRunUiState(
        has_compatible_traces=True,
        availability_text="Available for current design scope",
        availability_class="text-positive",
        run_disabled=False,
        run_hint="Ready to run selected analysis.",
    )


def _build_analysis_run_availability(
    *,
    profile_recommended: bool,
    profile_hints: Sequence[str],
    has_compatible_traces: bool,
) -> AnalysisRunAvailability:
    """Merge profile recommendation hints and trace compatibility into one status."""
    if not has_compatible_traces:
        return AnalysisRunAvailability(
            status="Unavailable",
            reason="No compatible traces in current design scope.",
            has_compatible_traces=False,
            profile_hints=list(profile_hints),
        )
    if profile_recommended:
        return AnalysisRunAvailability(
            status="Recommended",
            reason="Compatible traces found and design profile recommends this analysis.",
            has_compatible_traces=True,
            profile_hints=list(profile_hints),
        )
    reason = (
        "; ".join(profile_hints)
        if profile_hints
        else "Compatible traces found in current design scope."
    )
    return AnalysisRunAvailability(
        status="Available",
        reason=reason,
        has_compatible_traces=True,
        profile_hints=list(profile_hints),
    )


def _format_sweep_support_reason(diagnostic: SweepSupportDiagnostic) -> str:
    """Render one stable sweep-support diagnostic string for Run Analysis."""
    return f"Sweep support: {diagnostic.status} - {diagnostic.reason}"


def _is_sideband_trace_parameter(parameter: str) -> bool:
    """Return True when parameter name contains mode suffix metadata."""
    return ParameterKey.from_raw(parameter).has_sideband_suffix


def _normalize_trace_mode_group(raw_value: object) -> str:
    """Normalize trace mode provenance token used by filters and persistence."""
    normalized = ModeGroup.normalize(raw_value, allow_all=False, default=ModeGroup.UNKNOWN)
    if normalized is ModeGroup.UNKNOWN:
        return ""
    return normalized.value


def _trace_mode_group_for_selected_rows(rows: Sequence[dict[str, str | int]]) -> str:
    """Resolve one aggregate mode group for currently selected trace rows."""
    has_sideband = any(
        ModeGroup.from_trace_label(row.get("mode", ""), default=ModeGroup.BASE)
        is ModeGroup.SIDEBAND
        for row in rows
    )
    return ModeGroup.SIDEBAND.value if has_sideband else ModeGroup.BASE.value


def _trace_source_summary_payload(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Aggregate selected-trace source provenance for persistence and history."""
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        source_kind = str(row.get("source_kind", "")).strip()
        source_label = str(row.get("source_label", "")).strip()
        stage_kind = str(row.get("stage_kind", "")).strip()
        batch_id = row.get("source_batch_id")
        trace_id = row.get("id")
        if not source_kind or not isinstance(trace_id, int):
            continue
        summary = grouped.setdefault(
            source_kind,
            {
                "source_kind": source_kind,
                "source_label": source_label or source_kind.replace("_", " ").title(),
                "trace_ids": set(),
                "stage_kinds": set(),
                "source_batch_ids": set(),
            },
        )
        trace_ids = summary["trace_ids"]
        if isinstance(trace_ids, set):
            trace_ids.add(int(trace_id))
        stage_kinds = summary["stage_kinds"]
        if isinstance(stage_kinds, set) and stage_kind:
            stage_kinds.add(stage_kind)
        source_batch_ids = summary["source_batch_ids"]
        if isinstance(source_batch_ids, set) and isinstance(batch_id, int) and batch_id > 0:
            source_batch_ids.add(int(batch_id))

    payload: list[dict[str, object]] = []
    for source_kind in sorted(grouped):
        summary = grouped[source_kind]
        trace_ids = summary["trace_ids"]
        stage_kinds = summary["stage_kinds"]
        source_batch_ids = summary["source_batch_ids"]
        payload.append(
            {
                "source_kind": source_kind,
                "source_label": summary["source_label"],
                "trace_count": len(trace_ids) if isinstance(trace_ids, set) else 0,
                "stage_kinds": sorted(str(item) for item in stage_kinds)
                if isinstance(stage_kinds, set)
                else [],
                "source_batch_ids": sorted(int(item) for item in source_batch_ids)
                if isinstance(source_batch_ids, set)
                else [],
            }
        )
    return payload


def _format_trace_source_summary(
    source_summaries: Sequence[Mapping[str, object] | TraceSourceSummary],
) -> str:
    """Render concise source-count text for scope and history summaries."""
    chunks: list[str] = []
    for summary in source_summaries:
        if isinstance(summary, TraceSourceSummary):
            label = str(summary.source_label).strip()
            trace_count = int(summary.trace_count)
        else:
            label = str(summary.get("source_label", "")).strip()
            raw_trace_count = summary.get("trace_count", 0)
            trace_count = int(raw_trace_count) if isinstance(raw_trace_count, int | str) else 0
        if not label:
            continue
        chunks.append(f"{label} {trace_count}")
    return " · ".join(chunks)


def _analysis_run_selected_trace_count(run_record: AnalysisRunRecord) -> int:
    """Return persisted selected-trace count with summary fallback."""
    if run_record.input_trace_ids:
        return len(run_record.input_trace_ids)
    raw_value = run_record.summary_payload.get("selected_trace_count", 0)
    return int(raw_value) if isinstance(raw_value, int | float) else 0


def _analysis_run_source_summary(run_record: AnalysisRunRecord) -> list[dict[str, object]]:
    """Load persisted selected-source summary from one analysis run."""
    raw_value = run_record.summary_payload.get("selected_source_summary")
    if not isinstance(raw_value, list):
        return []
    return [dict(item) for item in raw_value if isinstance(item, Mapping)]


def _analysis_run_scope_text(run_record: AnalysisRunRecord) -> str:
    """Render a stable design-scope label for analysis history."""
    if str(run_record.input_scope).strip() == "all_dataset_records":
        return "Design traces"
    scope_token = str(run_record.input_scope).replace("_", " ").strip()
    return scope_token.title() if scope_token else "Design traces"


def _analysis_run_provenance_text(run_record: AnalysisRunRecord) -> str:
    """Render concise provenance text while keeping run/history boundary explicit."""
    source_summary = _analysis_run_source_summary(run_record)
    if source_summary:
        stage_labels: list[str] = []
        batch_ids: list[int] = []
        for summary in source_summary:
            raw_stage_kinds = summary.get("stage_kinds", [])
            stage_kinds = (
                raw_stage_kinds
                if isinstance(raw_stage_kinds, Sequence)
                and not isinstance(raw_stage_kinds, str | bytes)
                else []
            )
            for stage_kind in stage_kinds:
                stage_text = str(stage_kind).replace("_", " ").strip().title()
                if stage_text and stage_text not in stage_labels:
                    stage_labels.append(stage_text)
            raw_batch_ids = summary.get("source_batch_ids", [])
            batch_id_values = (
                raw_batch_ids
                if isinstance(raw_batch_ids, Sequence)
                and not isinstance(raw_batch_ids, str | bytes)
                else []
            )
            for batch_id in batch_id_values:
                if isinstance(batch_id, int) and batch_id not in batch_ids:
                    batch_ids.append(batch_id)
        stage_text = ", ".join(stage_labels) if stage_labels else "Trace-first provenance"
        if batch_ids:
            return f"{stage_text} · batches #{', #'.join(str(batch_id) for batch_id in batch_ids)}"
        return stage_text
    if run_record.input_batch_ids:
        return "Batches " + ", ".join(f"#{batch_id}" for batch_id in run_record.input_batch_ids)
    return "Design-scope trace selection"


def _param_trace_mode_group(param: object) -> str:
    """Extract persisted trace mode provenance from one DerivedParameter-like object."""
    extra = getattr(param, "extra", {})
    if isinstance(extra, dict):
        return _normalize_trace_mode_group(extra.get("trace_mode_group"))
    return ""


def _trace_mode_filter_options(method_groups: dict[str, list]) -> dict[str, str]:
    """Build stable trace-mode filter options from one method-group payload."""
    present_modes = {
        _param_trace_mode_group(param) for params in method_groups.values() for param in params
    }
    available_keys = [_TRACE_MODE_ALL]
    for mode_key in (ModeGroup.BASE.value, ModeGroup.SIDEBAND.value):
        if mode_key in present_modes:
            available_keys.append(mode_key)
    return {key: _TRACE_MODE_LABELS[key] for key in available_keys}


def _numeric_ui_default(value: object) -> float | None:
    """Normalize optional numeric defaults for NiceGUI number inputs."""
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    return None


def _filter_method_groups_by_trace_mode(
    method_groups: dict[str, list],
    *,
    trace_mode_filter: str,
) -> dict[str, list]:
    """Filter one analysis method-group mapping by persisted trace mode provenance."""
    normalized_mode = _normalize_trace_mode_group(trace_mode_filter)
    if trace_mode_filter == _TRACE_MODE_ALL:
        return {method_key: list(params) for method_key, params in method_groups.items()}

    filtered: dict[str, list] = {}
    for method_key, params in method_groups.items():
        selected = [param for param in params if _param_trace_mode_group(param) == normalized_mode]
        if selected:
            filtered[method_key] = selected
    return filtered


def _trace_row_mode_key(row: Mapping[str, str | int]) -> str:
    """Resolve canonical mode key for one trace row."""
    mode_group = ModeGroup.from_trace_label(row.get("mode", ""), default=ModeGroup.BASE)
    return mode_group.value


def _filter_trace_rows_by_mode(
    rows: Sequence[dict[str, str | int]],
    *,
    mode_filter: str,
) -> list[dict[str, str | int]]:
    """Filter trace rows by canonical mode filter (`all`/`base`/`sideband`)."""
    normalized_mode = ModeGroup.normalize(
        mode_filter,
        allow_all=True,
        default=ModeGroup.ALL,
    )
    if normalized_mode is ModeGroup.ALL:
        return list(rows)
    if normalized_mode is ModeGroup.UNKNOWN:
        return list(rows)
    return [row for row in rows if _trace_row_mode_key(row) == normalized_mode.value]


def _trace_rows_for_view(
    rows: list[dict[str, str | int]],
    *,
    search: str,
    mode_filter: str,
    sort_by: str,
    descending: bool,
) -> list[dict[str, str | int]]:
    """Filter and sort trace rows for table rendering."""
    filtered_rows = list(rows)
    search_text = search.strip().lower()
    if search_text:
        filtered_rows = [
            row
            for row in filtered_rows
            if search_text in str(row.get("parameter", "")).lower()
            or search_text in str(row.get("representation", "")).lower()
            or search_text in str(row.get("id", "")).lower()
        ]
    if mode_filter:
        filtered_rows = _filter_trace_rows_by_mode(filtered_rows, mode_filter=mode_filter)

    if sort_by == "mode":
        filtered_rows.sort(
            key=lambda row: _trace_row_mode_key(row),
            reverse=descending,
        )
    elif sort_by == "parameter":
        filtered_rows.sort(
            key=lambda row: str(row.get("parameter", "")).lower(),
            reverse=descending,
        )
    elif sort_by == "representation":
        filtered_rows.sort(
            key=lambda row: str(row.get("representation", "")).lower(),
            reverse=descending,
        )
    else:
        filtered_rows.sort(
            key=lambda row: int(row["id"]) if isinstance(row.get("id"), int) else 0,
            reverse=descending,
        )
    return filtered_rows


def _to_int(value: object, default: int) -> int:
    """Convert to int with fallback for UI state values."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


# ---------------------------------------------------------------------------
# Data helpers (from former parameters.py)
# ---------------------------------------------------------------------------


def _group_by_method(params):
    groups: dict[str, list] = defaultdict(list)
    for p in params:
        groups[p.method or "unknown"].append(p)
    return dict(sorted(groups.items()))


def _build_bias_dataframe(params) -> pd.DataFrame | None:
    rows: dict[str, dict[int, float]] = defaultdict(dict)
    sweep_axis_values: dict[int, float] = {}
    sweep_axis_unit: str = ""
    sweep_axis_label: str | None = None

    for p in params:
        m = _BIAS_RE.match(p.name)
        if m:
            base, bias = m.group(1), int(m.group(2))
            extra = p.extra if isinstance(getattr(p, "extra", {}), dict) else {}
            sweep_axis = str(extra.get("sweep_axis", "")).strip()
            if sweep_axis and base == sweep_axis:
                sweep_axis_values[bias] = p.value
                if p.unit:
                    sweep_axis_unit = p.unit
                sweep_axis_label = sweep_axis
            else:
                rows[base][bias] = p.value

    if not rows:
        return None

    df = pd.DataFrame.from_dict(rows, orient="index")
    df = df.reindex(sorted(df.columns), axis=1)
    col_map: dict[object, str]

    if sweep_axis_values:
        col_map = {
            b: f"{sweep_axis_values[b]:.4g} ({sweep_axis_unit})"
            if sweep_axis_unit
            else f"{sweep_axis_values[b]:.4g}"
            for b in df.columns
            if b in sweep_axis_values
        }
        for column_name in df.columns:
            if column_name not in col_map:
                col_map[column_name] = f"B{column_name}"
    else:
        col_map = {b: f"B{b}" for b in df.columns}
    df = df.rename(columns=col_map)

    new_index = []
    for idx in df.index:
        new_index.append(_display_param_name(str(idx)))
    df.index = new_index
    df.index.name = "Parameter"
    df.attrs["sweep_axis_label"] = sweep_axis_label or "L_jun"
    df.attrs["sweep_axis_unit"] = sweep_axis_unit or "nH"
    return df


def _build_resonator_table(params) -> pd.DataFrame | None:
    cells: dict[int, dict[str, float]] = defaultdict(dict)
    for p in params:
        if _BIAS_RE.match(p.name):
            continue

        mode_index = _mode_index_from_key(p.name)
        if mode_index is not None:
            cells[mode_index]["mode_ghz"] = p.value
            continue

        m2 = _IDX_RE.match(p.name)
        if m2:
            base, idx = m2.group(1), int(m2.group(2))
            cells[idx][base] = p.value

    if not cells:
        return None

    df = pd.DataFrame.from_dict(cells, orient="index")
    df.index.name = "Resonator"
    df = df.sort_index()

    if "mode_ghz" in df.columns:
        df = df.rename(columns={"mode_ghz": "Mode (GHz)"})

    preferred = ["Mode (GHz)", "Qi", "Qc", "Ql"]
    cols_ordered = [c for c in preferred if c in df.columns]
    cols_ordered += [c for c in sorted(df.columns) if c not in cols_ordered]
    return df[cols_ordered]


def _build_fit_parameter_table(params: list) -> pd.DataFrame | None:
    """Build per-fit parameter summary table using DerivedParameter.extra metadata."""
    rows: dict[str, dict[str, float]] = defaultdict(dict)

    for param in params:
        extra = param.extra if isinstance(getattr(param, "extra", {}), dict) else {}
        row_key = str(extra.get("mode") or "Y11")
        name = str(param.name)
        if name in {"Ls_nH", "C_eff_pF", "Ls1_nH", "Ls2_nH", "C_pF", "RMSE"}:
            rows[row_key][name] = float(param.value)
        if "rmse" in extra:
            rows[row_key]["RMSE"] = float(extra["rmse"])

    if not rows:
        return None

    df = pd.DataFrame.from_dict(rows, orient="index")
    df.index.name = "Trace"
    preferred_cols = ["Ls_nH", "C_eff_pF", "Ls1_nH", "Ls2_nH", "C_pF", "RMSE"]
    ordered_cols = [name for name in preferred_cols if name in df.columns]
    ordered_cols += [name for name in sorted(df.columns) if name not in ordered_cols]
    return df[ordered_cols].sort_index()


# ---------------------------------------------------------------------------
# Result Artifact helpers
# ---------------------------------------------------------------------------


def _build_mode_vs_ljun_dataframe(params: list) -> pd.DataFrame | None:
    """Build canonical mode-vs-sweep-axis table; synthesize a single-column form when needed."""
    bias_df = _build_bias_dataframe(params)
    if bias_df is not None and not bias_df.empty:
        return bias_df

    mode_by_index: dict[int, float] = {}
    sweep_value: float | None = None
    sweep_label = "L_jun"
    sweep_unit = "nH"
    for param in params:
        mode_index = _mode_index_from_key(str(param.name))
        if mode_index is not None:
            mode_by_index[mode_index] = float(param.value)
            continue
        extra = param.extra if isinstance(getattr(param, "extra", {}), dict) else {}
        sweep_axis = str(extra.get("sweep_axis", "")).strip()
        if sweep_axis and str(param.name) == sweep_axis:
            sweep_value = float(param.value)
            sweep_label = sweep_axis
            if getattr(param, "unit", None):
                sweep_unit = str(param.unit)

    if not mode_by_index:
        return None

    sorted_modes = sorted(mode_by_index)
    col_label = (
        f"{sweep_value:.4g} ({sweep_unit})"
        if sweep_value is not None
        else f"{sweep_label} ({sweep_unit})"
    )
    mode_rows = [f"Mode {mode_index} (GHz)" for mode_index in sorted_modes]
    values = [mode_by_index[mode_index] for mode_index in sorted_modes]
    df = pd.DataFrame({col_label: values}, index=mode_rows)
    df.index.name = "Parameter"
    df.attrs["sweep_axis_label"] = sweep_label
    df.attrs["sweep_axis_unit"] = sweep_unit
    return df


def _is_summary_scalar_parameter(param: object) -> bool:
    """Return whether one derived parameter belongs to summary scalar cards."""
    name = str(getattr(param, "name", ""))
    return not _BIAS_RE.match(name) and not _IDX_RE.match(name)


def _result_view_empty_state_message(
    *,
    selected_mode_label: str,
    selected_analysis_groups_raw: Mapping[str, list],
    selected_analysis_groups: Mapping[str, list],
    latest_completed_analysis_run_id: int | None = None,
) -> str:
    """Build one diagnosable empty-state message for Result View."""
    if selected_analysis_groups:
        method_keys = ", ".join(sorted(str(method_key) for method_key in selected_analysis_groups))
        return (
            "Persisted results found but no renderable artifacts for selected analysis "
            f"(methods: {method_keys})."
        )
    if selected_analysis_groups_raw:
        return (
            f"No artifacts available for selected analysis under trace mode: {selected_mode_label}."
        )
    if latest_completed_analysis_run_id is not None:
        return (
            "Analysis completed but did not publish any result artifacts yet "
            f"(latest analysis run #{latest_completed_analysis_run_id})."
        )
    return "No artifacts available for selected analysis."


class ResultViewQueryService:
    """Lazy payload loader for result artifacts."""

    def __init__(self, method_groups: dict[str, list]) -> None:
        self._method_groups = method_groups
        self._cache: dict[str, dict[str, Any]] = {}

    def load_payload(self, artifact: ResultArtifact) -> dict[str, Any]:
        """Load payload for one artifact with in-memory cache."""
        cached = self._cache.get(artifact.artifact_id)
        if cached is not None:
            return cached

        method_key = str(artifact.query_spec.get("method_key", ""))
        method_params = list(self._method_groups.get(method_key, []))
        payload: dict[str, Any]
        if artifact.view_kind == "matrix_table_plot":
            payload = {
                "dataframe": _build_mode_vs_ljun_dataframe(method_params),
                "method_params": method_params,
            }
        elif artifact.view_kind == "record_table":
            shape = str(artifact.query_spec.get("shape", ""))
            if shape == "fit_parameters":
                payload = {"dataframe": _build_fit_parameter_table(method_params)}
            else:
                payload = {"dataframe": _build_resonator_table(method_params)}
        elif artifact.view_kind == "scalar_cards":
            payload = {
                "scalars": [
                    param
                    for param in method_params
                    if not _BIAS_RE.match(str(param.name)) and not _IDX_RE.match(str(param.name))
                ]
            }
        else:
            payload = {}

        self._cache[artifact.artifact_id] = payload
        return payload


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------


def _render_table_df(df: pd.DataFrame, suppress_auto_header: bool = False):
    display = df.copy().reset_index()

    # Keep numeric cells numeric so ui.table sorting stays numeric (not lexicographic).
    for col in display.columns:
        if pd.api.types.is_float_dtype(display[col].dtype):
            display[col] = display[col].apply(lambda v: round(float(v), 6) if pd.notna(v) else None)

    columns = [
        {
            "name": str(column_name),
            "label": "" if suppress_auto_header and idx == 0 else str(column_name),
            "field": str(column_name),
            "align": "left",
            "sortable": True,
            "headerClasses": (
                "text-primary text-xs font-bold uppercase tracking-wider select-none"
            ),
            "classes": "text-fg",
        }
        for idx, column_name in enumerate(display.columns)
    ]
    rows = [
        {str(column_name): value for column_name, value in row.items()}
        for row in display.to_dict(orient="records")
    ]
    with ui.element("div").classes("w-full overflow-x-auto"):
        ui.table(columns=columns, rows=rows, pagination=20).classes(
            "w-full min-w-[640px] rounded-xl border border-border bg-surface"
        ).props("dense flat bordered separator=horizontal")


def _render_metric_cards(params):
    with ui.row().classes("w-full gap-4 flex-wrap"):
        for p in sorted(params, key=lambda x: x.name):
            with ui.column().classes("app-card p-4 min-w-[140px] flex-grow flex-shrink"):
                ui.label(_display_param_name(p.name)).classes(
                    "text-xs text-muted font-bold uppercase"
                )
                val = f"{p.value:.4g}" if isinstance(p.value, float) else str(p.value)
                with ui.row().classes("items-baseline gap-1 mt-1"):
                    ui.label(val).classes("text-xl font-bold text-fg")
                    if p.unit:
                        ui.label(p.unit).classes("text-xs text-muted")


def _render_bias_plotly(df: pd.DataFrame):
    import plotly.graph_objects as go

    from core.shared.visualization import get_plotly_layout

    x_labels = list(df.columns)
    x_numeric = []
    has_valid_numeric_x = False
    for label in x_labels:
        try:
            val = float(str(label).split()[0])
            x_numeric.append(val)
        except (ValueError, IndexError):
            x_numeric.append(label)

    if all(isinstance(x, int | float) for x in x_numeric):
        x_data = x_numeric
        has_valid_numeric_x = True
    else:
        x_data = x_labels

    fig = go.Figure()
    for idx, row in df.iterrows():
        mode_label = str(idx).replace(" (GHz)", "")
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=row.values,
                mode="markers",
                marker={"size": 8},
                name=mode_label,
                hovertemplate=(
                    f"<b>{mode_label}</b><br>Bias: %{{x}}<br>Freq: %{{y:.4g}} GHz<extra></extra>"
                ),
            )
        )

    is_dark = app.storage.user.get("dark_mode", True)
    theme_layout = get_plotly_layout(dark=is_dark)
    fig.update_layout(
        title="Mode Frequencies vs. Bias",
        xaxis_title="L_jun (nH)" if has_valid_numeric_x else "Bias Index",
        yaxis_title="Frequency (GHz)",
        margin=dict(l=60, r=150, t=60, b=60),
        height=400,
        legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
    )
    fig.update_layout(**theme_layout)  # type: ignore[arg-type]
    if not has_valid_numeric_x:
        fig.update_xaxes(type="category")

    ui.plotly(fig).classes("w-full")


# ---------------------------------------------------------------------------
# Identify Mode UI
# ---------------------------------------------------------------------------


def _render_identify_mode(ds, method: str, params: list, bias_df):
    """Render the Identify Mode UI for tagging modes with physical meaning."""
    ui.separator().classes("my-4 bg-border")
    with ui.row().classes("w-full items-center justify-between"):
        ui.label("Identify Mode").classes("text-xs text-muted font-bold uppercase tracking-wider")

    with ui.row().classes("w-full items-end gap-4 mt-2 p-4 bg-bg rounded-xl border border-border"):

        def extract_base_param(name: str) -> str:
            m_bias = _BIAS_RE.match(name)
            if m_bias:
                return m_bias.group(1)
            m_idx = _IDX_RE.match(name)
            if m_idx:
                return m_idx.group(1)
            return name

        def format_base_param(base_name: str) -> str:
            return _display_param_name(base_name)

        unique_bases = {extract_base_param(p.name) for p in params}
        param_options = {base: format_base_param(base) for base in sorted(unique_bases)}

        if not param_options:
            ui.label("No parameters to tag").classes("text-muted text-sm")
        else:
            source_select = ui.select(param_options, label="Source Parameter").classes("w-64")

            tag_options = [
                "f_q (Qubit frequency)",
                "f_r (Readout frequency)",
                "alpha (Anharmonicity)",
                "g (Coupling strength)",
            ]
            tag_select = ui.select(tag_options, label="Designated Metric", with_input=True).classes(
                "w-64"
            )

            def save_designation():
                if not source_select.value or not tag_select.value:
                    ui.notify("Please select both a parameter and a tag", type="warning")
                    return

                true_tag = tag_select.value.split(" (")[0].strip()

                try:
                    with get_unit_of_work() as uow:
                        existing = uow.designations.find_unique(
                            dataset_id=int(ds.id),
                            designated_name=true_tag,
                            source_analysis_type=method,
                            source_parameter_name=str(source_select.value),
                        )

                        if existing:
                            ui.notify(
                                f"Tag '{true_tag}' already exists for {source_select.value}",
                                type="info",
                            )
                            return

                        desig = ParameterDesignation(
                            dataset_id=ds.id,
                            designated_name=true_tag,
                            source_analysis_type=method,
                            source_parameter_name=source_select.value,
                        )
                        uow.designations.add(desig)
                        uow.commit()
                        ui.notify(
                            f"Successfully designated {source_select.value} as '{true_tag}'",
                            type="positive",
                        )

                        source_select.value = None
                        tag_select.value = None
                except Exception as e:
                    ui.notify(f"Error saving designation: {e}", type="negative")

            ui.button("Tag Parameter", icon="sell", on_click=save_designation).props(
                "outline color=primary size=sm"
            ).classes("mb-1")


# ---------------------------------------------------------------------------
# Result artifact renderer
# ---------------------------------------------------------------------------


def _render_result_artifact(
    *,
    ds,
    artifact: ResultArtifact,
    payload: dict[str, Any],
) -> None:
    """Render one artifact payload using view-kind specific renderer."""
    with (
        ui.row().classes("w-full items-center justify-between gap-3 flex-wrap mb-2"),
        ui.column().classes("gap-1"),
    ):
        ui.label(artifact.title).classes("text-xs text-muted font-bold uppercase tracking-wider")
        if artifact.subtitle:
            ui.label(artifact.subtitle).classes("text-xs text-muted")

    if artifact.view_kind == "matrix_table_plot":
        bias_df = payload.get("dataframe")
        if not isinstance(bias_df, pd.DataFrame) or bias_df.empty:
            ui.label("No rows available for this artifact.").classes("text-sm text-muted")
            return
        toggle = ui.toggle(["Table", "Plot"], value="Table").props(
            "size=md no-caps outline color=primary"
        )
        with ui.column().classes("w-full"):

            @ui.refreshable
            def render_matrix_view():
                if toggle.value == "Table":
                    _render_table_df(bias_df, suppress_auto_header=True)
                else:
                    _render_bias_plotly(bias_df)

            toggle.on_value_change(lambda _: render_matrix_view.refresh())
            render_matrix_view()

        method_params = payload.get("method_params")
        if isinstance(method_params, list):
            method_key = str(artifact.query_spec.get("method_key", ""))
            _render_identify_mode(ds, method_key, method_params, bias_df)
        return

    if artifact.view_kind == "record_table":
        resonator_df = payload.get("dataframe")
        if not isinstance(resonator_df, pd.DataFrame) or resonator_df.empty:
            ui.label("No rows available for this artifact.").classes("text-sm text-muted")
            return
        _render_table_df(resonator_df)
        return

    if artifact.view_kind == "scalar_cards":
        scalars = payload.get("scalars")
        if isinstance(scalars, list) and scalars:
            _render_metric_cards(scalars)
        else:
            ui.label("No scalar metrics available for this artifact.").classes("text-sm text-muted")
        return

    ui.label(f"Unsupported artifact view kind: {artifact.view_kind}").classes("text-warning")


def build_page() -> None:
    def content():
        ui.label("Characterization").classes("text-2xl font-bold text-fg mb-6")
        owner_client = ui.context.client

        selected_dataset_ids = app.storage.user.get("selected_datasets", [])
        runtime_state = CharacterizationRuntimeState.create()
        poll_timer: Any | None = None
        pending_tasks: set[asyncio.Task[Any]] = set()

        def _spawn_background_task(coro: Any) -> None:
            task = asyncio.create_task(coro)
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)

        def _active_design_id() -> int | None:
            active_id = app.storage.user.get("analysis_current_dataset")
            if isinstance(active_id, int):
                return active_id
            return None

        def append_analysis_status(level: str, message: str) -> None:
            runtime_state.append_status(
                level=level,
                message=message,
                time_label=pd.Timestamp.now().strftime("%H:%M:%S"),
            )
            render_analysis_status()

        def render_analysis_status() -> None:
            if runtime_state.analysis_log_container is None:
                return

            icon_map = {
                "info": "info",
                "warning": "warning",
                "negative": "error",
                "positive": "check_circle",
            }
            color_map = {
                "info": "text-primary",
                "warning": "text-warning",
                "negative": "text-danger",
                "positive": "text-positive",
            }

            runtime_state.analysis_log_container.clear()
            with runtime_state.analysis_log_container:
                if not runtime_state.analysis_status_history:
                    ui.label("No analysis logs yet. Run one analysis to see status.").classes(
                        "text-sm text-muted"
                    )
                    return

                for item in runtime_state.analysis_status_history:
                    with ui.row().classes("w-full items-start gap-2"):
                        ui.icon(icon_map.get(item["level"], "info"), size="xs").classes(
                            color_map.get(item["level"], "text-primary mt-1")
                        )
                        ui.label(f"[{item['time']}] {item['message']}").classes(
                            "text-sm text-fg whitespace-pre-wrap break-all"
                        )

        def _apply_polled_characterization_task_status(task: Any | None) -> None:
            if task is None:
                runtime_state.current_task_status = None
                runtime_state.current_task_error = None
                runtime_state.last_task_poll_signature = None
                return

            runtime_state.current_task_id = int(task.id)
            runtime_state.current_task_status = str(task.status)
            runtime_state.current_analysis_run_id = (
                int(task.analysis_run_id) if task.analysis_run_id is not None else None
            )
            runtime_state.current_task_analysis_id = str(
                task.request_payload.get("parameters", {}).get("analysis_id", "")
            )
            error_payload = getattr(task, "error_payload", {}) or {}
            runtime_state.current_task_error = (
                str(error_payload.get("summary"))
                if isinstance(error_payload, Mapping) and error_payload.get("summary")
                else None
            )
            status_signature = (
                f"{task.id}:{task.status}:{task.analysis_run_id}:"
                f"{task.completed_at.isoformat() if task.completed_at is not None else ''}:"
                f"{runtime_state.current_task_error or ''}"
            )
            if status_signature == runtime_state.last_task_poll_signature:
                return
            runtime_state.last_task_poll_signature = status_signature

            if task.status == "queued":
                append_analysis_status(
                    "info",
                    f"Characterization queued: task=#{int(task.id)}, run={task.analysis_run_id}.",
                )
            elif task.status == "running":
                append_analysis_status(
                    "info",
                    f"Characterization running: task=#{int(task.id)}, run={task.analysis_run_id}.",
                )
            elif task.status == "completed":
                runtime_state.long_running_warning_shown = False
                append_analysis_status(
                    "positive",
                    (
                        f"Characterization completed: task=#{int(task.id)}, "
                        f"run={task.analysis_run_id}."
                    ),
                )
            elif task.status == "failed":
                runtime_state.long_running_warning_shown = False
                append_analysis_status(
                    "negative",
                    (
                        f"Characterization failed: task=#{int(task.id)}, "
                        f"run={task.analysis_run_id}. "
                        f"{runtime_state.current_task_error or 'See task error payload.'}"
                    ),
                )

        async def _refresh_characterization_authority(
            *,
            preferred_task_id: int | None = None,
        ) -> None:
            active_id = _active_design_id()
            if active_id is None:
                return
            try:
                tasks_response = await get_design_tasks(active_id, client=owner_client)
                latest_result = await get_latest_characterization_result(
                    active_id,
                    client=owner_client,
                )
            except ApiClientError as exc:
                if exc.status_code != 404:
                    raise
                runtime_state.current_task_id = None
                runtime_state.current_task_status = None
                runtime_state.current_analysis_run_id = None
                runtime_state.current_task_error = None
                if poll_timer is not None:
                    poll_timer.active = False
                append_analysis_status(
                    "warning",
                    "Active dataset is unavailable; characterization persistence view is paused.",
                )
                render_dataset_view.refresh()
                return
            recovery_state = build_recovery_state(
                tasks_response=tasks_response,
                latest_result=latest_result,
            )
            task = recovery_state.task
            if preferred_task_id is not None:
                fetched_task = await get_task(preferred_task_id, client=owner_client)
                if fetched_task.task_kind == "characterization":
                    task = fetched_task
            if task is not None:
                _apply_polled_characterization_task_status(task)
                progress_payload = dict(task.progress_payload)
                warning = str(progress_payload.get("warning", "")).strip()
                if warning and not runtime_state.long_running_warning_shown:
                    runtime_state.long_running_warning_shown = True
                    append_analysis_status("warning", warning)
            if recovery_state.long_running_warning and not runtime_state.long_running_warning_shown:
                runtime_state.long_running_warning_shown = True
                append_analysis_status(
                    "warning",
                    "Long-running analysis detected; persisted heartbeat polling is active.",
                )
            if poll_timer is not None:
                poll_timer.active = recovery_state.should_poll
            if latest_result is not None and latest_result.analysis_run_id:
                runtime_state.current_analysis_run_id = int(latest_result.analysis_run_id)
            if task is None and latest_result is not None:
                render_dataset_view.refresh()

        async def _poll_current_characterization_task() -> None:
            if runtime_state.current_task_id is None:
                if poll_timer is not None:
                    poll_timer.active = False
                return
            try:
                task = await get_task(int(runtime_state.current_task_id), client=owner_client)
                _apply_polled_characterization_task_status(task)
                progress_payload = dict(task.progress_payload)
                warning = str(progress_payload.get("warning", "")).strip()
                if warning and not runtime_state.long_running_warning_shown:
                    runtime_state.long_running_warning_shown = True
                    append_analysis_status("warning", warning)
                if task.status in {"completed", "failed"}:
                    if poll_timer is not None:
                        poll_timer.active = False
                    await _refresh_characterization_authority(preferred_task_id=int(task.id))
                    return
                if task.status == "running" and task.analysis_run_id is not None:
                    runtime_state.current_analysis_run_id = int(task.analysis_run_id)
            except ApiClientError as exc:
                append_analysis_status("negative", f"Characterization polling failed: {exc.detail}")
                if poll_timer is not None:
                    poll_timer.active = False

        def _handle_characterization_dispatch(dispatch: Any) -> None:
            runtime_state.current_task_id = int(dispatch.task.id)
            runtime_state.current_task_status = str(dispatch.task.status)
            runtime_state.current_analysis_run_id = (
                int(dispatch.task.analysis_run_id)
                if dispatch.task.analysis_run_id is not None
                else None
            )
            runtime_state.current_task_error = None
            runtime_state.current_task_analysis_id = str(
                dispatch.task.request_payload.get("parameters", {}).get("analysis_id", "")
            )
            runtime_state.long_running_warning_shown = False
            runtime_state.last_task_poll_signature = None
            append_analysis_status(
                "info",
                (
                    f"Characterization queued: task=#{dispatch.task.id}, "
                    f"run={dispatch.task.analysis_run_id}, worker={dispatch.worker_task_name}."
                ),
            )
            if poll_timer is not None:
                poll_timer.active = True

        if not selected_dataset_ids:
            render_empty_state(
                icon="science",
                title="No Designs Selected",
                message="Select active designs from the header or the Raw Data page.",
            )
            return

        try:
            with get_unit_of_work() as uow:
                ds_options = {}
                for ds_id in selected_dataset_ids:
                    ds = uow.datasets.get(ds_id)
                    if ds:
                        ds_options[ds_id] = ds.name

                if not ds_options:
                    ui.label("Error: Active designs not found.").classes("text-danger")
                    return

                current_ds_id = app.storage.user.get("analysis_current_dataset")
                if current_ds_id not in ds_options:
                    current_ds_id = next(iter(ds_options.keys()))
                    app.storage.user["analysis_current_dataset"] = current_ds_id

                @ui.refreshable
                def render_dataset_view():
                    nonlocal runtime_state
                    active_id = app.storage.user.get("analysis_current_dataset")
                    if not active_id or active_id not in ds_options:
                        return

                    with get_unit_of_work() as refresh_uow:
                        ds = refresh_uow.datasets.get(active_id)
                        if not ds:
                            return
                        active_design_id = int(ds.id) if ds.id is not None else None
                        active_design_name = str(ds.name)

                        dataset_profile_index = (
                            refresh_uow.data_records.list_distinct_index_for_profile(active_id)
                        )
                        provenance_bundle_count = refresh_uow.result_bundles.count_by_dataset(
                            active_id,
                            include_cache=False,
                        )
                        typed_refresh_uow = cast(CharacterizationTraceScopeUnitOfWork, refresh_uow)
                        selected_bundle_id = None
                        selected_scope_token = "all_dataset_records"
                        scoped_trace_count = count_scope_trace_records(
                            uow=typed_refresh_uow,
                            dataset_id=active_id,
                            selected_bundle_id=selected_bundle_id,
                        )

                        ds_params = refresh_uow.derived_params.list_by_dataset(active_id)
                        analysis_run_records = (
                            refresh_uow.result_bundles.analysis_runs.list_by_design(active_id)
                        )
                        analysis_run_summaries = (
                            refresh_uow.result_bundles.analysis_runs.list_summaries_by_design(
                                active_id
                            )
                        )
                        design_source_summaries = list_design_scope_source_summaries(
                            uow=typed_refresh_uow,
                            dataset_id=active_id,
                        )
                        method_params = _group_by_method(ds_params)
                        analyses = list_dataset_analyses()
                        if not analyses:
                            ui.label("No per-design analyses are registered.").classes(
                                "text-danger"
                            )
                            return
                        dataset_profile = normalize_dataset_profile(
                            ds.source_meta,
                            record_index=_normalize_profile_trace_index_rows(dataset_profile_index),
                        )

                        analysis_scope_compatibility: dict[str, AnalysisScopeCompatibility] = {}
                        analysis_run_availability_by_id: dict[str, AnalysisRunAvailability] = {}
                        scope_revision = f"{scoped_trace_count}:{selected_scope_token}"
                        for analysis in analyses:
                            analysis_id = str(analysis["id"])
                            effective_requires = _effective_analysis_requires(
                                analysis_id=analysis_id,
                                analysis_requires=dict(analysis.get("requires", {})),
                            )
                            compatibility_cache_key = (
                                f"{active_id}:{selected_scope_token}:{scope_revision}:{analysis_id}"
                            )
                            compatibility = runtime_state.analysis_scope_compatibility_cache.get(
                                compatibility_cache_key
                            )
                            if compatibility is None:
                                _, compatible_trace_count = list_scope_compatible_trace_index_page(
                                    uow=typed_refresh_uow,
                                    dataset_id=active_id,
                                    selected_bundle_id=selected_bundle_id,
                                    analysis_requires=effective_requires,
                                    limit=1,
                                    offset=0,
                                )
                                has_compatible_traces = compatible_trace_count > 0
                                compatibility = AnalysisScopeCompatibility(
                                    compatible_trace_rows=[],
                                    compatible_trace_count=compatible_trace_count,
                                    has_compatible_traces=has_compatible_traces,
                                    status=(
                                        "available" if has_compatible_traces else "unavailable"
                                    ),
                                    message=(
                                        "Available for current design scope"
                                        if has_compatible_traces
                                        else "Unavailable for current design scope"
                                    ),
                                )
                                runtime_state.analysis_scope_compatibility_cache[
                                    compatibility_cache_key
                                ] = compatibility
                            analysis_scope_compatibility[analysis_id] = compatibility
                            capability_decision = evaluate_analysis_capability_gating(
                                analysis,
                                dataset_profile=dataset_profile,
                            )
                            analysis_run_availability_by_id[analysis_id] = (
                                _build_analysis_run_availability(
                                    profile_recommended=capability_decision.recommended,
                                    profile_hints=capability_decision.reasons,
                                    has_compatible_traces=compatibility.has_compatible_traces,
                                )
                            )

                        analysis_options = {
                            str(analysis["id"]): (
                                f"{analysis['label']} "
                                f"[{analysis_run_availability_by_id[str(analysis['id'])].status}]"
                            )
                            for analysis in analyses
                        }
                        analysis_ids = list(analysis_options)
                        selected_run_analysis_id = _resolve_selected_option(
                            _load_dataset_text_selection(_ANALYSIS_RUN_SELECTED_KEY, active_id),
                            analysis_ids,
                        )
                        _save_dataset_text_selection(
                            _ANALYSIS_RUN_SELECTED_KEY,
                            active_id,
                            selected_run_analysis_id,
                        )
                        selected_run_analysis = next(
                            (
                                analysis
                                for analysis in analyses
                                if str(analysis["id"]) == selected_run_analysis_id
                            ),
                            analyses[0],
                        )
                        selected_run_availability = analysis_run_availability_by_id[
                            selected_run_analysis_id
                        ]
                        selected_analysis_requires = _effective_analysis_requires(
                            analysis_id=selected_run_analysis_id,
                            analysis_requires=dict(selected_run_analysis.get("requires", {})),
                        )

                        def _compatible_trace_page(
                            *,
                            search: str = "",
                            sort_by: str = "id",
                            descending: bool = False,
                            mode_filter: str = _TRACE_MODE_ALL,
                            ids: Sequence[int] | None = None,
                            limit: int = 20,
                            offset: int = 0,
                        ) -> tuple[list[dict[str, str | int]], int]:
                            return list_scope_compatible_trace_index_page(
                                uow=typed_refresh_uow,
                                dataset_id=active_id,
                                selected_bundle_id=selected_bundle_id,
                                analysis_requires=selected_analysis_requires,
                                search=search,
                                sort_by=sort_by,
                                descending=descending,
                                mode_filter=mode_filter,
                                ids=ids,
                                limit=limit,
                                offset=offset,
                            )

                        trace_scope_key = (
                            f"{active_id}:{selected_scope_token}:{selected_run_analysis_id}"
                        )
                        if trace_scope_key not in runtime_state.selected_trace_ids_by_scope:
                            base_rows, _ = _compatible_trace_page(
                                mode_filter="base",
                                limit=1,
                                offset=0,
                            )
                            if base_rows:
                                runtime_state.set_selected_trace_ids(
                                    trace_scope_key,
                                    {int(base_rows[0]["id"])},
                                )
                            else:
                                first_rows, _ = _compatible_trace_page(limit=1, offset=0)
                                runtime_state.set_selected_trace_ids(
                                    trace_scope_key,
                                    {int(first_rows[0]["id"])} if first_rows else set(),
                                )
                        if trace_scope_key not in runtime_state.trace_table_state_by_scope:
                            _, base_trace_count = _compatible_trace_page(
                                mode_filter="base",
                                limit=1,
                                offset=0,
                            )
                            runtime_state.ensure_trace_table_state(
                                trace_scope_key,
                                default_mode_filter=(
                                    "base" if base_trace_count > 0 else _TRACE_MODE_ALL
                                ),
                            )

                        def _current_mode_filter() -> str:
                            table_state = runtime_state.trace_table_state_by_scope[trace_scope_key]
                            return str(table_state.get("trace_mode_filter", _TRACE_MODE_ALL))

                        def current_mode_trace_total() -> int:
                            _, total = _compatible_trace_page(
                                mode_filter=_current_mode_filter(),
                                limit=1,
                                offset=0,
                            )
                            return total

                        def current_selected_trace_ids() -> set[int]:
                            scope_selected_ids = runtime_state.selected_trace_ids_by_scope.get(
                                trace_scope_key,
                                set(),
                            )
                            if not scope_selected_ids:
                                return set()
                            validated_rows, _ = _compatible_trace_page(
                                mode_filter=_current_mode_filter(),
                                ids=sorted(scope_selected_ids),
                                limit=max(1, len(scope_selected_ids)),
                                offset=0,
                            )
                            validated_ids = {
                                int(row["id"])
                                for row in validated_rows
                                if isinstance(row.get("id"), int)
                            }
                            runtime_state.set_selected_trace_ids(trace_scope_key, validated_ids)
                            return validated_ids

                        def current_selected_trace_rows() -> list[dict[str, str | int]]:
                            selected_ids = sorted(current_selected_trace_ids())
                            if not selected_ids:
                                return []
                            rows, _ = _compatible_trace_page(
                                mode_filter=_current_mode_filter(),
                                ids=selected_ids,
                                limit=max(1, len(selected_ids)),
                                offset=0,
                            )
                            return hydrate_trace_index_rows_with_provenance(
                                uow=typed_refresh_uow,
                                dataset_id=active_id,
                                rows=rows,
                            )

                        def set_selected_trace_ids(updated_ids: set[int]) -> None:
                            runtime_state.set_selected_trace_ids(trace_scope_key, updated_ids)

                        def current_compatible_source_summaries() -> list[TraceSourceSummary]:
                            return list_scope_compatible_trace_source_summaries(
                                uow=typed_refresh_uow,
                                dataset_id=active_id,
                                selected_bundle_id=selected_bundle_id,
                                analysis_requires=selected_analysis_requires,
                                mode_filter=_current_mode_filter(),
                            )

                        def current_sweep_support_diagnostic() -> SweepSupportDiagnostic | None:
                            selected_ids = sorted(current_selected_trace_ids())
                            if not selected_ids:
                                return None
                            return diagnose_analysis_sweep_support(
                                analysis_id=selected_run_analysis_id,
                                dataset_id=active_id,
                                trace_record_ids=selected_ids,
                            )

                        def bulk_select_for_mode(mode_filter: str) -> None:
                            rows, total = _compatible_trace_page(
                                mode_filter=mode_filter,
                                sort_by="id",
                                descending=False,
                                limit=_MAX_BULK_TRACE_SELECTION + 1,
                                offset=0,
                            )
                            selected_ids = {
                                int(row["id"])
                                for row in rows[:_MAX_BULK_TRACE_SELECTION]
                                if isinstance(row.get("id"), int)
                            }
                            set_selected_trace_ids(selected_ids)
                            if total > _MAX_BULK_TRACE_SELECTION:
                                ui.notify(
                                    (
                                        "Large selection truncated to "
                                        f"{_MAX_BULK_TRACE_SELECTION} traces for stability."
                                    ),
                                    type="warning",
                                )

                        def current_run_ui_state() -> AnalysisRunUiState:
                            base_state = _build_analysis_run_ui_state(
                                has_compatible_traces=current_mode_trace_total() > 0,
                                selected_trace_count=len(current_selected_trace_ids()),
                            )
                            sweep_diagnostic = current_sweep_support_diagnostic()
                            if (
                                sweep_diagnostic is not None
                                and sweep_diagnostic.status == "blocked"
                                and len(current_selected_trace_ids()) > 0
                            ):
                                return AnalysisRunUiState(
                                    has_compatible_traces=True,
                                    availability_text="Blocked for selected sweep",
                                    availability_class="text-warning",
                                    run_disabled=True,
                                    run_hint=_format_sweep_support_reason(sweep_diagnostic),
                                )
                            return base_state

                        analysis_method_groups: dict[str, dict[str, list]] = {}
                        for analysis in analyses:
                            raw_completed_methods = analysis.get("completed_methods", [])
                            completed_methods = (
                                set(raw_completed_methods)
                                if isinstance(raw_completed_methods, Sequence)
                                and not isinstance(raw_completed_methods, str | bytes)
                                else set()
                            )
                            analysis_method_groups[str(analysis["id"])] = {
                                method_key: list(method_params[method_key])
                                for method_key in sorted(completed_methods)
                                if method_key in method_params
                            }

                        latest_completed_runs = _latest_completed_analysis_run_summaries(
                            analysis_run_summaries
                        )
                        completed_analysis_ids = _completed_result_analysis_ids(
                            analyses=analyses,
                            analysis_method_groups=analysis_method_groups,
                            latest_completed_runs=latest_completed_runs,
                        )
                        selected_result_analysis_id = _resolve_selected_option(
                            _load_dataset_text_selection(_ANALYSIS_RESULT_SELECTED_KEY, active_id),
                            completed_analysis_ids,
                        )
                        _save_dataset_text_selection(
                            _ANALYSIS_RESULT_SELECTED_KEY,
                            active_id,
                            selected_result_analysis_id,
                        )

                        with ui.column().classes("w-full gap-4"):
                            with _with_test_id(
                                section_card(),
                                "characterization-source-scope-card",
                            ):
                                with ui.row().classes(
                                    "w-full items-center justify-between gap-4 flex-wrap"
                                ):
                                    ui.icon("inventory_2", size="sm").classes("text-primary")
                                    ui.label("Design Scope").classes("text-lg font-bold text-fg")
                                ui.label(
                                    "Design-centric scope is active. Run Analysis uses the "
                                    "selected design's trace index, keeps one analysis model "
                                    "across circuit/layout/measurement traces, and applies "
                                    "trace-first compatibility filtering."
                                ).classes("text-sm text-muted mt-2")
                                with ui.row().classes("w-full gap-4 mt-3 flex-wrap"):
                                    with ui.column().classes(
                                        "bg-bg rounded-lg border border-border p-3 min-w-[160px]"
                                    ):
                                        ui.label("Selection").classes(
                                            "text-xs text-muted font-bold uppercase"
                                        )
                                        ui.label("All Design Traces").classes("text-sm text-fg")
                                    with ui.column().classes(
                                        "bg-bg rounded-lg border border-border p-3 min-w-[160px]"
                                    ):
                                        ui.label("Traces").classes(
                                            "text-xs text-muted font-bold uppercase"
                                        )
                                        ui.label(str(scoped_trace_count)).classes("text-sm text-fg")
                                    with ui.column().classes(
                                        "bg-bg rounded-lg border border-border p-3 min-w-[160px]"
                                    ):
                                        ui.label("Trace Batches").classes(
                                            "text-xs text-muted font-bold uppercase"
                                        )
                                        ui.label(str(provenance_bundle_count)).classes(
                                            "text-sm text-fg"
                                        )
                                ui.label(
                                    "Source coverage is provenance only. Availability and run "
                                    "gating still depend on compatible traces, not on source kind."
                                ).classes("text-xs text-muted mt-3")
                                with ui.row().classes("w-full gap-4 mt-3 flex-wrap"):
                                    with ui.column().classes(
                                        "bg-bg rounded-lg border border-border p-3 "
                                        "min-w-[280px] flex-1"
                                    ):
                                        ui.label("Design Sources").classes(
                                            "text-xs text-muted font-bold uppercase"
                                        )
                                        if design_source_summaries:
                                            for summary in design_source_summaries:
                                                source_summary_text = (
                                                    f"{summary.source_label}: "
                                                    f"{summary.trace_count} trace(s) across "
                                                    f"{summary.batch_count} batch(es) "
                                                    f"[{summary.stage_summary}]"
                                                )
                                                ui.label(source_summary_text).classes(
                                                    "text-sm text-fg"
                                                )
                                        else:
                                            ui.label(
                                                "No saved trace provenance found yet."
                                            ).classes("text-sm text-muted")
                                    with ui.column().classes(
                                        "bg-bg rounded-lg border border-border p-3 "
                                        "min-w-[280px] flex-1"
                                    ):
                                        ui.label("Compatible Sources").classes(
                                            "text-xs text-muted font-bold uppercase"
                                        )
                                        compatible_source_summaries = (
                                            current_compatible_source_summaries()
                                        )
                                        if compatible_source_summaries:
                                            for summary in compatible_source_summaries:
                                                compatible_source_text = (
                                                    f"{summary.source_label}: "
                                                    f"{summary.trace_count} compatible trace(s) "
                                                    f"[{summary.stage_summary}]"
                                                )
                                                ui.label(compatible_source_text).classes(
                                                    "text-sm text-fg"
                                                )
                                        else:
                                            ui.label(
                                                "No compatible traces in current design scope."
                                            ).classes("text-sm text-muted")

                            with _with_test_id(
                                section_card(),
                                "characterization-run-analysis-card",
                            ):
                                run_config_selects: dict[str, Any] = {}
                                run_config_numbers: dict[str, Any] = {}
                                run_button: Any = None
                                availability_label: Any | None = None
                                analysis_reason_label: Any | None = None

                                def refresh_run_controls() -> None:
                                    ui_state = current_run_ui_state()
                                    has_selected_traces = len(current_selected_trace_ids()) > 0
                                    sweep_diagnostic = current_sweep_support_diagnostic()
                                    if not ui_state.has_compatible_traces:
                                        availability_text = "Unavailable for current design scope"
                                        availability_class = "text-warning"
                                        reason_text = (
                                            "No compatible traces in current design scope."
                                        )
                                        run_disabled = True
                                    elif (
                                        sweep_diagnostic is not None
                                        and sweep_diagnostic.status == "blocked"
                                    ):
                                        availability_text = ui_state.availability_text
                                        availability_class = ui_state.availability_class
                                        reason_text = ui_state.run_hint
                                        run_disabled = True
                                    elif selected_run_availability.status == "Recommended":
                                        availability_text = "Recommended for current design scope"
                                        availability_class = "text-positive"
                                        reason_text = (
                                            "Select at least one trace to run."
                                            if not has_selected_traces
                                            else selected_run_availability.reason
                                        )
                                        run_disabled = not has_selected_traces
                                    else:
                                        availability_text = "Available for current design scope"
                                        availability_class = ui_state.availability_class
                                        reason_text = (
                                            "Select at least one trace to run."
                                            if not has_selected_traces
                                            else selected_run_availability.reason
                                        )
                                        run_disabled = not has_selected_traces

                                    compatible_source_text = _format_trace_source_summary(
                                        current_compatible_source_summaries()
                                    )
                                    if compatible_source_text and ui_state.has_compatible_traces:
                                        base_reason = str(reason_text).strip()
                                        compatibility_reason = (
                                            f"Compatible sources: {compatible_source_text}."
                                        )
                                        reason_text = (
                                            f"{base_reason}; {compatibility_reason}"
                                            if base_reason
                                            else compatibility_reason
                                        )

                                    if (
                                        sweep_diagnostic is not None
                                        and sweep_diagnostic.status != "blocked"
                                        and has_selected_traces
                                    ):
                                        base_reason = str(reason_text).strip()
                                        sweep_reason = _format_sweep_support_reason(
                                            sweep_diagnostic
                                        )
                                        reason_text = (
                                            f"{base_reason}; {sweep_reason}"
                                            if base_reason
                                            else sweep_reason
                                        )

                                    if availability_label is not None:
                                        availability_label.set_text(availability_text)
                                        availability_label.classes(
                                            replace=(f"text-sm font-semibold {availability_class}")
                                        )
                                    if analysis_reason_label is not None:
                                        analysis_reason_label.set_text(reason_text)
                                        analysis_reason_label.classes(
                                            replace=(
                                                "text-sm text-warning mb-2"
                                                if run_disabled
                                                else "text-sm text-muted mb-2"
                                            )
                                        )
                                    if run_button is not None:
                                        if run_disabled:
                                            run_button.disable()
                                        else:
                                            run_button.enable()

                                with ui.row().classes(
                                    "w-full items-center justify-between gap-3 flex-wrap mb-3"
                                ):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon("play_circle", size="sm").classes("text-primary")
                                        ui.label("Run Analysis").classes(
                                            "text-lg font-bold text-fg"
                                        )

                                    async def run_selected_analysis() -> None:
                                        analysis_id = str(selected_run_analysis["id"])
                                        run_id = f"char-{uuid4().hex[:10]}"
                                        runtime_state.set_log_context(
                                            run_id=run_id,
                                            dataset_id=active_design_id,
                                            analysis_id=analysis_id,
                                        )
                                        run_trace_ids = sorted(current_selected_trace_ids())
                                        config_fields = selected_run_analysis.get(
                                            "config_fields",
                                            [],
                                        )
                                        config_state: dict[str, str | float | int | None] = {
                                            str(field["name"]): field.get("default")
                                            for field in config_fields
                                            if field.get("name")
                                        }
                                        for field in config_fields:
                                            name = str(field.get("name", ""))
                                            if not name:
                                                continue
                                            if field["type"] == "select":
                                                config_state[name] = run_config_selects[name].value
                                            elif field["type"] == "number":
                                                config_state[name] = run_config_numbers[name].value

                                        run_ui_state = current_run_ui_state()
                                        if not run_ui_state.has_compatible_traces:
                                            append_analysis_status(
                                                "warning",
                                                run_ui_state.run_hint,
                                            )
                                            return
                                        if not run_trace_ids:
                                            append_analysis_status(
                                                "warning",
                                                "Select at least one trace to run.",
                                            )
                                            return
                                        sweep_diagnostic = current_sweep_support_diagnostic()
                                        if (
                                            sweep_diagnostic is not None
                                            and sweep_diagnostic.status == "blocked"
                                        ):
                                            append_analysis_status(
                                                "warning",
                                                _format_sweep_support_reason(sweep_diagnostic),
                                            )
                                            return

                                        selected_trace_rows = current_selected_trace_rows()
                                        selected_source_summary = _trace_source_summary_payload(
                                            selected_trace_rows
                                        )
                                        selected_mode_group = _trace_mode_group_for_selected_rows(
                                            selected_trace_rows
                                        )
                                        if run_button is not None:
                                            run_button.props("loading")
                                        append_analysis_status(
                                            "info",
                                            (
                                                f"Running {selected_run_analysis['label']} on "
                                                f"design {active_design_name} "
                                                f"(id={active_design_id}) with "
                                                f"{len(run_trace_ids)} trace(s)"
                                                + (
                                                    " from "
                                                    f"{_format_trace_source_summary(selected_source_summary)}."
                                                    if selected_source_summary
                                                    else "."
                                                )
                                            ),
                                        )
                                        if (
                                            sweep_diagnostic is not None
                                            and sweep_diagnostic.status == "partial"
                                        ):
                                            append_analysis_status(
                                                "warning",
                                                _format_sweep_support_reason(sweep_diagnostic),
                                            )
                                        try:
                                            if active_design_id is None:
                                                raise ValueError("Active design id is missing.")
                                            selected_batch_ids: list[int] = []
                                            for summary in selected_source_summary:
                                                if not isinstance(summary, Mapping):
                                                    continue
                                                raw_batch_ids = summary.get("source_batch_ids", [])
                                                if not isinstance(
                                                    raw_batch_ids, Sequence
                                                ) or isinstance(raw_batch_ids, str | bytes):
                                                    continue
                                                for batch_id in raw_batch_ids:
                                                    if isinstance(batch_id, int):
                                                        selected_batch_ids.append(int(batch_id))
                                            submission = build_characterization_submission(
                                                design_id=active_design_id,
                                                analysis_id=analysis_id,
                                                analysis_label=str(selected_run_analysis["label"]),
                                                run_id=run_id,
                                                trace_record_ids=run_trace_ids,
                                                selected_batch_ids=selected_batch_ids,
                                                selected_scope_token=selected_scope_token,
                                                trace_mode_group=selected_mode_group,
                                                config_state=config_state,
                                                summary_payload={
                                                    "selected_trace_count": len(run_trace_ids),
                                                    "selected_source_summary": (
                                                        selected_source_summary
                                                    ),
                                                },
                                                context=build_ui_use_case_context(
                                                    metadata={
                                                        "flow": "characterization",
                                                        "analysis_id": analysis_id,
                                                        "dataset_id": active_design_id,
                                                    }
                                                ),
                                                force_rerun=False,
                                            )
                                            dispatch = await submit_characterization_task(
                                                submission.api_request,
                                                client=owner_client,
                                            )
                                            _handle_characterization_dispatch(dispatch)
                                        except NotImplementedError:
                                            append_analysis_status(
                                                "warning",
                                                (
                                                    f"{selected_run_analysis['label']} is not "
                                                    "implemented yet."
                                                ),
                                            )
                                        except Exception as exc:
                                            append_analysis_status(
                                                "negative",
                                                f"{selected_run_analysis['label']} failed: {exc}",
                                            )
                                        finally:
                                            if run_button is not None:
                                                run_button.props(remove="loading")

                                    run_button = (
                                        ui.button(
                                            "Run Selected Analysis",
                                            on_click=run_selected_analysis,
                                            icon="play_arrow",
                                        )
                                        .props("unelevated color=primary")
                                        .classes("font-bold")
                                    )
                                    _with_test_id(
                                        run_button,
                                        "characterization-run-analysis-button",
                                    )

                                ui.label(
                                    "Run control is centralized here. Choose one analysis, set "
                                    "parameters, then execute."
                                ).classes("text-sm text-muted mb-3")
                                ui.label(design_profile_summary_text(dataset_profile)).classes(
                                    "text-xs text-muted mb-2"
                                )

                                with ui.row().classes("w-full items-end gap-4 flex-wrap"):
                                    analysis_select = (
                                        ui.select(
                                            options=analysis_options,
                                            value=selected_run_analysis_id,
                                            label="Analysis",
                                            on_change=lambda e: (
                                                _save_dataset_text_selection(
                                                    _ANALYSIS_RUN_SELECTED_KEY,
                                                    active_id,
                                                    str(e.value),
                                                ),
                                                render_dataset_view.refresh(),
                                            ),
                                        )
                                        .props("dense outlined options-dense")
                                        .classes("w-72")
                                    )
                                    _with_test_id(
                                        analysis_select,
                                        "characterization-analysis-select",
                                    )

                                    availability_label = ui.label("").classes(
                                        "text-sm font-semibold"
                                    )
                                    _with_test_id(
                                        availability_label,
                                        "characterization-availability-label",
                                    )
                                analysis_reason_label = ui.label("").classes(
                                    "text-sm text-muted mb-2"
                                )
                                _with_test_id(
                                    analysis_reason_label,
                                    "characterization-availability-reason",
                                )
                                refresh_run_controls()

                                ui.separator().classes("my-4 bg-border")

                                @ui.refreshable
                                def render_trace_selection() -> None:
                                    table_state = runtime_state.trace_table_state_by_scope[
                                        trace_scope_key
                                    ]
                                    mode_filter = str(
                                        table_state.get("trace_mode_filter", _TRACE_MODE_ALL)
                                    )
                                    mode_total = current_mode_trace_total()

                                    with ui.row().classes(
                                        "w-full items-center justify-between gap-3 flex-wrap"
                                    ):
                                        ui.label("Trace Selection").classes(
                                            "text-sm font-bold text-fg uppercase tracking-wider"
                                        )
                                        with ui.row().classes("items-center gap-2"):
                                            ui.label(
                                                f"{len(current_selected_trace_ids())} / "
                                                f"{mode_total} selected"
                                            ).classes("text-xs text-muted")

                                            ui.button(
                                                "Base",
                                                on_click=lambda: (
                                                    bulk_select_for_mode("base"),
                                                    refresh_run_controls(),
                                                    render_trace_selection.refresh(),
                                                ),
                                            ).props("flat dense no-caps color=primary")
                                            ui.button(
                                                "All",
                                                on_click=lambda: (
                                                    bulk_select_for_mode(
                                                        str(
                                                            table_state.get(
                                                                "trace_mode_filter",
                                                                _TRACE_MODE_ALL,
                                                            )
                                                        )
                                                    ),
                                                    refresh_run_controls(),
                                                    render_trace_selection.refresh(),
                                                ),
                                            ).props("flat dense no-caps color=primary")
                                            ui.button(
                                                "Clear",
                                                on_click=lambda: (
                                                    set_selected_trace_ids(set()),
                                                    refresh_run_controls(),
                                                    render_trace_selection.refresh(),
                                                ),
                                            ).props("flat dense no-caps color=primary")

                                    if mode_total <= 0:
                                        ui.label(
                                            "No compatible traces found for the selected analysis "
                                            "under selected trace mode filter."
                                        ).classes("text-sm text-muted mb-2")
                                        return

                                    search_text = str(table_state.get("search", ""))
                                    sort_by = str(table_state.get("sort_by", "id"))
                                    descending = bool(table_state.get("descending", False))
                                    page_size = max(
                                        1,
                                        _to_int(table_state.get("page_size", 20), 20),
                                    )
                                    _, total_filtered = _compatible_trace_page(
                                        search=search_text,
                                        mode_filter=mode_filter,
                                        sort_by=sort_by,
                                        descending=descending,
                                        limit=1,
                                        offset=0,
                                    )
                                    total_pages = max(
                                        1,
                                        (total_filtered + page_size - 1) // page_size,
                                    )
                                    current_page = max(
                                        1,
                                        min(_to_int(table_state.get("page", 1), 1), total_pages),
                                    )
                                    table_state["page"] = current_page
                                    page_offset = (current_page - 1) * page_size
                                    visible_trace_rows, _ = _compatible_trace_page(
                                        search=search_text,
                                        mode_filter=mode_filter,
                                        sort_by=sort_by,
                                        descending=descending,
                                        limit=page_size,
                                        offset=page_offset,
                                    )
                                    hydrated_visible_trace_rows = (
                                        hydrate_trace_index_rows_with_provenance(
                                            uow=typed_refresh_uow,
                                            dataset_id=active_id,
                                            rows=visible_trace_rows,
                                        )
                                    )

                                    with ui.row().classes("w-full gap-3 items-end flex-wrap mb-2"):
                                        filter_input = (
                                            ui.input(
                                                label="Filter Traces",
                                                value=str(table_state.get("search", "")),
                                                on_change=lambda e: (
                                                    table_state.__setitem__(
                                                        "search", str(e.value or "")
                                                    ),
                                                    table_state.__setitem__("page", 1),
                                                    render_trace_selection.refresh(),
                                                ),
                                            )
                                            .props("dense outlined clearable")
                                            .classes("min-w-[220px] flex-1")
                                        )
                                        _with_test_id(
                                            filter_input,
                                            "characterization-trace-filter-input",
                                        )
                                        run_trace_mode_filter = (
                                            ui.select(
                                                _TRACE_MODE_FILTER_OPTIONS,
                                                value=str(
                                                    table_state.get(
                                                        "trace_mode_filter",
                                                        _TRACE_MODE_ALL,
                                                    )
                                                ),
                                                label="Trace Mode Filter",
                                                on_change=lambda e: (
                                                    table_state.__setitem__(
                                                        "trace_mode_filter",
                                                        str(e.value or _TRACE_MODE_ALL),
                                                    ),
                                                    table_state.__setitem__("page", 1),
                                                    set_selected_trace_ids(set()),
                                                    refresh_run_controls(),
                                                    render_trace_selection.refresh(),
                                                ),
                                            )
                                            .props("dense outlined options-dense")
                                            .classes("w-40")
                                        )
                                        _with_test_id(
                                            run_trace_mode_filter,
                                            "characterization-run-trace-mode-filter-select",
                                        )
                                        ui.select(
                                            {
                                                "id": "ID",
                                                "mode": "Mode",
                                                "parameter": "Parameter",
                                                "representation": "Representation",
                                            },
                                            value=str(table_state.get("sort_by", "id")),
                                            label="Sort By",
                                            on_change=lambda e: (
                                                table_state.__setitem__("sort_by", str(e.value)),
                                                table_state.__setitem__("page", 1),
                                                render_trace_selection.refresh(),
                                            ),
                                        ).props("dense outlined options-dense").classes("w-44")
                                        ui.select(
                                            {False: "Ascending", True: "Descending"},
                                            value=bool(table_state.get("descending", False)),
                                            label="Order",
                                            on_change=lambda e: (
                                                table_state.__setitem__(
                                                    "descending",
                                                    bool(e.value),
                                                ),
                                                table_state.__setitem__("page", 1),
                                                render_trace_selection.refresh(),
                                            ),
                                        ).props("dense outlined options-dense").classes("w-40")

                                    selected_ids = current_selected_trace_ids()
                                    trace_selection_rows = [
                                        {
                                            "selected": (
                                                "✓"
                                                if _to_int(row.get("id"), 0) in selected_ids
                                                else ""
                                            ),
                                            "id": _to_int(row.get("id"), 0),
                                            "mode": (
                                                "Sideband"
                                                if _trace_row_mode_key(row) == "sideband"
                                                else "Base"
                                            ),
                                            "source": str(row.get("source_label", "Untracked")),
                                            "parameter": str(row["parameter"]),
                                            "representation": str(row["representation"]),
                                            "provenance": str(
                                                row.get(
                                                    "provenance_label",
                                                    "Untracked trace provenance",
                                                )
                                            ),
                                        }
                                        for row in hydrated_visible_trace_rows
                                    ]
                                    trace_selection_columns = [
                                        {
                                            "name": "selected",
                                            "label": "",
                                            "field": "selected",
                                            "align": "center",
                                            "sortable": False,
                                        },
                                        {
                                            "name": "id",
                                            "label": "ID",
                                            "field": "id",
                                            "align": "left",
                                            "sortable": True,
                                        },
                                        {
                                            "name": "mode",
                                            "label": "Mode",
                                            "field": "mode",
                                            "align": "left",
                                            "sortable": True,
                                        },
                                        {
                                            "name": "parameter",
                                            "label": "Parameter",
                                            "field": "parameter",
                                            "align": "left",
                                            "sortable": True,
                                        },
                                        {
                                            "name": "source",
                                            "label": "Source",
                                            "field": "source",
                                            "align": "left",
                                            "sortable": False,
                                        },
                                        {
                                            "name": "representation",
                                            "label": "Representation",
                                            "field": "representation",
                                            "align": "left",
                                            "sortable": True,
                                        },
                                        {
                                            "name": "provenance",
                                            "label": "Provenance",
                                            "field": "provenance",
                                            "align": "left",
                                            "sortable": False,
                                        },
                                    ]
                                    trace_table = (
                                        ui.table(
                                            columns=trace_selection_columns,
                                            rows=trace_selection_rows,
                                            row_key="id",
                                            pagination=0,
                                        )
                                        .classes("w-full mb-2")
                                        .props("dense flat bordered separator=horizontal")
                                    )

                                    def on_trace_row_click(event: Any) -> None:
                                        row_data = event.args[1] if len(event.args) > 1 else {}
                                        if not isinstance(row_data, dict):
                                            return
                                        row_id = row_data.get("id")
                                        if not isinstance(row_id, int):
                                            return
                                        updated_ids = current_selected_trace_ids()
                                        if row_id in updated_ids:
                                            updated_ids.remove(row_id)
                                        else:
                                            updated_ids.add(row_id)
                                        set_selected_trace_ids(updated_ids)
                                        refresh_run_controls()
                                        render_trace_selection.refresh()

                                    trace_table.on("rowClick", on_trace_row_click)
                                    with ui.row().classes(
                                        "w-full justify-between items-center flex-wrap gap-2 mb-2"
                                    ):
                                        ui.label(
                                            f"Filtered {total_filtered} traces · "
                                            f"Page {current_page} / {total_pages}"
                                        ).classes("text-xs text-muted")
                                        with ui.row().classes("items-center gap-2"):
                                            ui.select(
                                                {
                                                    10: "10 / page",
                                                    20: "20 / page",
                                                    50: "50 / page",
                                                },
                                                value=page_size,
                                                on_change=lambda e: (
                                                    table_state.__setitem__(
                                                        "page_size",
                                                        _to_int(e.value, page_size),
                                                    ),
                                                    table_state.__setitem__("page", 1),
                                                    render_trace_selection.refresh(),
                                                ),
                                            ).props("dense outlined options-dense").classes("w-28")
                                            prev_button = ui.button(
                                                "Prev",
                                                on_click=lambda: (
                                                    table_state.__setitem__(
                                                        "page",
                                                        max(1, current_page - 1),
                                                    ),
                                                    render_trace_selection.refresh(),
                                                ),
                                            ).props("dense flat no-caps")
                                            if current_page <= 1:
                                                prev_button.disable()
                                            next_button = ui.button(
                                                "Next",
                                                on_click=lambda: (
                                                    table_state.__setitem__(
                                                        "page",
                                                        min(total_pages, current_page + 1),
                                                    ),
                                                    render_trace_selection.refresh(),
                                                ),
                                            ).props("dense flat no-caps")
                                            if current_page >= total_pages:
                                                next_button.disable()

                                render_trace_selection()

                                config_fields = selected_run_analysis.get("config_fields", [])
                                if config_fields:
                                    with ui.row().classes("w-full gap-4 mt-3 flex-wrap"):
                                        for field in config_fields:
                                            field_name = str(field.get("name", ""))
                                            if not field_name:
                                                continue
                                            if field["type"] == "select":
                                                options = field.get("options", {})
                                                run_config_selects[field_name] = (
                                                    ui.select(
                                                        options=(
                                                            options
                                                            if isinstance(options, Mapping)
                                                            else {}
                                                        ),
                                                        value=field.get("default"),
                                                        label=field["label"],
                                                    )
                                                    .props("dense outlined options-dense")
                                                    .classes("w-44")
                                                )
                                            elif field["type"] == "number":
                                                run_config_numbers[field_name] = (
                                                    ui.number(
                                                        label=field["label"],
                                                        value=_numeric_ui_default(
                                                            field.get("default")
                                                        ),
                                                    )
                                                    .props("dense outlined")
                                                    .classes("w-40")
                                                )

                                ui.separator().classes("my-4 bg-border")
                                with ui.row().classes("w-full items-center gap-2 mb-2"):
                                    ui.icon("terminal", size="xs").classes("text-primary")
                                    ui.label("Analysis Log").classes(
                                        "text-sm font-bold text-fg uppercase tracking-wider"
                                    )
                                runtime_state.analysis_log_container = ui.column().classes(
                                    "w-full gap-2"
                                )
                                render_analysis_status()

                            with _with_test_id(
                                ui.card().classes("w-full bg-surface rounded-xl p-6"),
                                "characterization-run-history-card",
                            ):
                                with ui.row().classes(
                                    "w-full items-center justify-between gap-3 flex-wrap mb-3"
                                ):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon("history", size="sm").classes("text-primary")
                                        ui.label("Run History").classes("text-lg font-bold text-fg")
                                    ui.label(
                                        "Each row is one persisted analysis run with explicit "
                                        "trace-first scope and provenance."
                                    ).classes("text-sm text-muted")
                                if not analysis_run_records:
                                    ui.label(
                                        "No analysis run recorded for this design yet."
                                    ).classes("text-sm text-muted")
                                else:
                                    history_rows = [
                                        {
                                            "run": (
                                                f"#{run_record.id}"
                                                if run_record.id is not None
                                                else str(run_record.run_id or "pending")
                                            ),
                                            "analysis": str(
                                                run_record.analysis_label or run_record.analysis_id
                                            ),
                                            "status": str(run_record.status).title(),
                                            "scope": _analysis_run_scope_text(run_record),
                                            "traces": _analysis_run_selected_trace_count(
                                                run_record
                                            ),
                                            "sources": (
                                                _format_trace_source_summary(
                                                    _analysis_run_source_summary(run_record)
                                                )
                                                or "Unspecified"
                                            ),
                                            "provenance": _analysis_run_provenance_text(run_record),
                                        }
                                        for run_record in reversed(analysis_run_records[-10:])
                                    ]
                                    ui.table(
                                        columns=[
                                            {
                                                "name": "run",
                                                "label": "Run",
                                                "field": "run",
                                                "align": "left",
                                            },
                                            {
                                                "name": "analysis",
                                                "label": "Analysis",
                                                "field": "analysis",
                                                "align": "left",
                                            },
                                            {
                                                "name": "status",
                                                "label": "Status",
                                                "field": "status",
                                                "align": "left",
                                            },
                                            {
                                                "name": "scope",
                                                "label": "Scope",
                                                "field": "scope",
                                                "align": "left",
                                            },
                                            {
                                                "name": "traces",
                                                "label": "Traces",
                                                "field": "traces",
                                                "align": "left",
                                            },
                                            {
                                                "name": "sources",
                                                "label": "Sources",
                                                "field": "sources",
                                                "align": "left",
                                            },
                                            {
                                                "name": "provenance",
                                                "label": "Provenance",
                                                "field": "provenance",
                                                "align": "left",
                                            },
                                        ],
                                        rows=history_rows,
                                        row_key="run",
                                        pagination=0,
                                    ).classes("w-full").props(
                                        "dense flat bordered separator=horizontal"
                                    )

                            with _with_test_id(
                                section_card(),
                                "characterization-result-view-card",
                            ):
                                with ui.row().classes(
                                    "w-full items-center justify-between gap-3 flex-wrap mb-3"
                                ):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon("insights", size="sm").classes("text-primary")
                                        ui.label("Result View").classes("text-lg font-bold text-fg")
                                    ui.label(
                                        "Switch tabs to inspect completed analyses "
                                        "without rerunning."
                                    ).classes("text-sm text-muted")

                                if not completed_analysis_ids:
                                    with ui.column().classes(
                                        "w-full py-8 items-center justify-center"
                                    ):
                                        ui.icon("hourglass_empty", size="md").classes(
                                            "text-muted opacity-40 mb-2"
                                        )
                                        ui.label("No completed analysis yet.").classes(
                                            "text-sm text-muted"
                                        )
                                else:
                                    tab_options = {
                                        str(analysis["id"]): str(analysis["label"])
                                        for analysis in analyses
                                        if str(analysis["id"]) in completed_analysis_ids
                                    }
                                    tabs = ui.tabs().classes("w-full")
                                    tabs.set_value(selected_result_analysis_id)
                                    for analysis_id, label in tab_options.items():
                                        ui.tab(analysis_id, label=label)
                                    tabs.on_value_change(
                                        lambda e: (
                                            _save_dataset_text_selection(
                                                _ANALYSIS_RESULT_SELECTED_KEY,
                                                active_id,
                                                str(e.value),
                                            ),
                                            render_dataset_view.refresh(),
                                        )
                                    )
                                    selected_analysis_groups_raw = analysis_method_groups.get(
                                        selected_result_analysis_id,
                                        {},
                                    )
                                    analysis_scope_key = _analysis_scope_key(
                                        active_id,
                                        selected_result_analysis_id,
                                    )
                                    trace_mode_options = _trace_mode_filter_options(
                                        selected_analysis_groups_raw
                                    )
                                    selected_trace_mode_filter = _resolve_selected_option(
                                        _load_scope_text_selection(
                                            _ANALYSIS_RESULT_TRACE_MODE_SELECTED_KEY,
                                            analysis_scope_key,
                                        ),
                                        list(trace_mode_options),
                                    )
                                    _save_scope_text_selection(
                                        _ANALYSIS_RESULT_TRACE_MODE_SELECTED_KEY,
                                        analysis_scope_key,
                                        selected_trace_mode_filter,
                                    )
                                    selected_analysis_groups = _filter_method_groups_by_trace_mode(
                                        selected_analysis_groups_raw,
                                        trace_mode_filter=selected_trace_mode_filter,
                                    )
                                    artifacts = build_result_artifacts_for_analysis(
                                        analysis_id=selected_result_analysis_id,
                                        method_groups=selected_analysis_groups,
                                        build_mode_vs_ljun_dataframe=_build_mode_vs_ljun_dataframe,
                                        build_resonator_table=_build_resonator_table,
                                        build_fit_parameter_table=_build_fit_parameter_table,
                                        is_summary_scalar=_is_summary_scalar_parameter,
                                    )
                                    categories = artifact_categories(artifacts)
                                    category_options = {
                                        category: _CATEGORY_LABELS.get(
                                            category,
                                            category.replace("_", " ").title(),
                                        )
                                        for category in categories
                                    }
                                    selected_category = _resolve_selected_option(
                                        _load_scope_text_selection(
                                            _ANALYSIS_RESULT_CATEGORY_SELECTED_KEY,
                                            analysis_scope_key,
                                        ),
                                        categories,
                                    )
                                    if categories:
                                        _save_scope_text_selection(
                                            _ANALYSIS_RESULT_CATEGORY_SELECTED_KEY,
                                            analysis_scope_key,
                                            selected_category,
                                        )

                                    with ui.row().classes(_result_view_controls_row_classes()):
                                        result_trace_mode_filter = (
                                            ui.select(
                                                options=trace_mode_options,
                                                value=selected_trace_mode_filter,
                                                label="Trace Mode Filter",
                                                on_change=lambda e: (
                                                    _save_scope_text_selection(
                                                        _ANALYSIS_RESULT_TRACE_MODE_SELECTED_KEY,
                                                        analysis_scope_key,
                                                        str(e.value),
                                                    ),
                                                    render_dataset_view.refresh(),
                                                ),
                                            )
                                            .props("dense outlined options-dense")
                                            .classes("w-64")
                                        )
                                        _with_test_id(
                                            result_trace_mode_filter,
                                            "characterization-result-trace-mode-filter-select",
                                        )
                                        if category_options:
                                            result_category_select = (
                                                ui.select(
                                                    options=category_options,
                                                    value=selected_category,
                                                    label="Category",
                                                    on_change=lambda e: (
                                                        _save_scope_text_selection(
                                                            _ANALYSIS_RESULT_CATEGORY_SELECTED_KEY,
                                                            analysis_scope_key,
                                                            str(e.value),
                                                        ),
                                                        render_dataset_view.refresh(),
                                                    ),
                                                )
                                                .props("dense outlined options-dense")
                                                .classes("w-64")
                                            )
                                            _with_test_id(
                                                result_category_select,
                                                "characterization-result-category-select",
                                            )
                                        else:
                                            category_placeholder = ui.select(
                                                options={"": "Category (N/A)"},
                                                value="",
                                                label="Category",
                                            ).props("dense outlined")
                                            category_placeholder.classes("w-64")
                                            category_placeholder.disable()

                                    if not artifacts:
                                        selected_mode_label = trace_mode_options.get(
                                            selected_trace_mode_filter,
                                            "All",
                                        )
                                        latest_completed_analysis_run_id = None
                                        latest_completed_run = latest_completed_runs.get(
                                            selected_result_analysis_id
                                        )
                                        if latest_completed_run is not None:
                                            raw_latest_run_id = latest_completed_run.get(
                                                "analysis_run_id",
                                                latest_completed_run.get("bundle_id", 0),
                                            )
                                            latest_completed_analysis_run_id = (
                                                int(raw_latest_run_id)
                                                if isinstance(raw_latest_run_id, int | str)
                                                else None
                                            )
                                        ui.label(
                                            _result_view_empty_state_message(
                                                selected_mode_label=selected_mode_label,
                                                selected_analysis_groups_raw=(
                                                    selected_analysis_groups_raw
                                                ),
                                                selected_analysis_groups=selected_analysis_groups,
                                                latest_completed_analysis_run_id=(
                                                    latest_completed_analysis_run_id
                                                ),
                                            )
                                        ).classes("text-sm text-muted mt-3")
                                    else:
                                        artifacts_for_category = artifacts_in_category(
                                            artifacts,
                                            category=selected_category,
                                        )
                                        artifact_ids = [
                                            artifact.artifact_id
                                            for artifact in artifacts_for_category
                                        ]
                                        selected_artifact_id = _resolve_selected_option(
                                            _load_scope_text_selection(
                                                _ANALYSIS_RESULT_ARTIFACT_SELECTED_KEY,
                                                analysis_scope_key,
                                            ),
                                            artifact_ids,
                                        )
                                        _save_scope_text_selection(
                                            _ANALYSIS_RESULT_ARTIFACT_SELECTED_KEY,
                                            analysis_scope_key,
                                            selected_artifact_id,
                                        )

                                        artifact_tabs = ui.tabs().classes("w-full")
                                        _with_test_id(
                                            artifact_tabs,
                                            "characterization-result-artifact-tabs",
                                        )
                                        artifact_tabs.set_value(selected_artifact_id)
                                        for artifact in artifacts_for_category:
                                            ui.tab(artifact.artifact_id, label=artifact.tab_label)
                                        artifact_tabs.on_value_change(
                                            lambda e: (
                                                _save_scope_text_selection(
                                                    _ANALYSIS_RESULT_ARTIFACT_SELECTED_KEY,
                                                    analysis_scope_key,
                                                    str(e.value),
                                                ),
                                                render_dataset_view.refresh(),
                                            )
                                        )

                                        artifact_lookup = {
                                            artifact.artifact_id: artifact
                                            for artifact in artifacts_for_category
                                        }
                                        selected_artifact = artifact_lookup[selected_artifact_id]
                                        payload = ResultViewQueryService(
                                            selected_analysis_groups
                                        ).load_payload(selected_artifact)
                                        _render_result_artifact(
                                            ds=ds,
                                            artifact=selected_artifact,
                                            payload=payload,
                                        )

                # --- Layout ---
                with ui.row().classes("w-full items-center gap-4 mb-4"):
                    ui.label("Design:").classes("text-sm font-bold text-fg")

                    def on_change(e):
                        app.storage.user["analysis_current_dataset"] = e.value
                        runtime_state.current_task_id = None
                        runtime_state.current_task_status = None
                        runtime_state.current_analysis_run_id = None
                        runtime_state.current_task_error = None
                        runtime_state.current_task_analysis_id = None
                        runtime_state.last_task_poll_signature = None
                        runtime_state.long_running_warning_shown = False
                        render_dataset_view.refresh()
                        _spawn_background_task(_refresh_characterization_authority())

                    dataset_select = (
                        ui.select(
                            options=ds_options,
                            value=current_ds_id,
                            on_change=on_change,
                        )
                        .props("dense outlined options-dense")
                        .classes("w-64")
                    )
                    _with_test_id(dataset_select, "characterization-dataset-select")

                render_dataset_view()
                poll_timer = ui.timer(
                    2.0,
                    callback=lambda: _spawn_background_task(_poll_current_characterization_task()),
                    active=False,
                )
                ui.timer(
                    0.2,
                    callback=lambda: _spawn_background_task(_refresh_characterization_authority()),
                    active=True,
                    once=True,
                )

        except Exception as e:
            ui.label(f"Error loading characterization: {e}").classes("text-danger")

    content()
