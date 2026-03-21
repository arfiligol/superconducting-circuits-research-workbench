"""Typed state contracts for Characterization page orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AnalysisScopeCompatibility:
    """Compatibility summary for one analysis under current record scope."""

    compatible_trace_rows: list[dict[str, str | int]]
    compatible_trace_count: int
    has_compatible_traces: bool
    status: str
    message: str


@dataclass(frozen=True)
class AnalysisRunUiState:
    """UI contract for availability label and run-button enabled state."""

    has_compatible_traces: bool
    availability_text: str
    availability_class: str
    run_disabled: bool
    run_hint: str


@dataclass(frozen=True)
class AnalysisRunAvailability:
    """Profile recommendation + scope compatibility for one analysis."""

    status: str
    reason: str
    has_compatible_traces: bool
    profile_hints: list[str]


@dataclass(frozen=True)
class ResultArtifact:
    """Declarative contract for one result-view unit."""

    artifact_id: str
    analysis_id: str
    category: str
    view_kind: str
    tab_label: str
    title: str
    subtitle: str | None
    query_spec: dict[str, Any]
    meta: dict[str, Any]


@dataclass
class CharacterizationRuntimeState:
    """Single mutable state source for Characterization page runtime."""

    analysis_status_history: list[dict[str, str]]
    analysis_log_container: Any | None
    current_task_id: int | None
    current_task_status: str | None
    current_analysis_run_id: int | None
    current_task_error: str | None
    current_task_analysis_id: str | None
    last_task_poll_signature: str | None
    long_running_warning_shown: bool
    selected_trace_ids_by_scope: dict[str, set[int]]
    trace_table_state_by_scope: dict[str, dict[str, object]]
    analysis_scope_compatibility_cache: dict[str, AnalysisScopeCompatibility]
    active_log_context: dict[str, str]

    @classmethod
    def create(cls) -> CharacterizationRuntimeState:
        """Build default page runtime state."""
        return cls(
            analysis_status_history=[],
            analysis_log_container=None,
            current_task_id=None,
            current_task_status=None,
            current_analysis_run_id=None,
            current_task_error=None,
            current_task_analysis_id=None,
            last_task_poll_signature=None,
            long_running_warning_shown=False,
            selected_trace_ids_by_scope={},
            trace_table_state_by_scope={},
            analysis_scope_compatibility_cache={},
            active_log_context={},
        )

    def set_log_context(self, **tokens: object) -> None:
        """Replace active log context tokens for subsequent status lines."""
        self.active_log_context = {
            str(key): str(value) for key, value in tokens.items() if value not in (None, "")
        }

    def clear_log_context(self) -> None:
        """Clear active log context tokens."""
        self.active_log_context = {}

    def append_status(
        self,
        level: str,
        message: str,
        *,
        time_label: str,
        limit: int = 50,
    ) -> None:
        """Append one analysis log row with bounded history."""
        context_prefix = ""
        if self.active_log_context:
            token_text = " ".join(
                f"{key}={value}" for key, value in sorted(self.active_log_context.items())
            )
            context_prefix = f"[{token_text}] "
        self.analysis_status_history.append(
            {
                "level": level,
                "message": f"{context_prefix}{message}",
                "time": time_label,
            }
        )
        if len(self.analysis_status_history) > limit:
            self.analysis_status_history.pop(0)

    def ensure_trace_table_state(
        self,
        scope_key: str,
        *,
        default_mode_filter: str,
    ) -> dict[str, object]:
        """Ensure one scoped trace table state payload exists."""
        if scope_key not in self.trace_table_state_by_scope:
            self.trace_table_state_by_scope[scope_key] = {
                "search": "",
                "trace_mode_filter": default_mode_filter,
                "sort_by": "id",
                "descending": False,
                "page": 1,
                "page_size": 20,
            }
        return self.trace_table_state_by_scope[scope_key]

    def ensure_selected_trace_ids(
        self,
        scope_key: str,
        *,
        default_ids: set[int] | None = None,
    ) -> set[int]:
        """Ensure one scoped selected-trace set exists."""
        if scope_key not in self.selected_trace_ids_by_scope:
            self.selected_trace_ids_by_scope[scope_key] = set(default_ids or set())
        return self.selected_trace_ids_by_scope[scope_key]

    def set_selected_trace_ids(self, scope_key: str, trace_ids: set[int]) -> None:
        """Replace one scoped selected-trace set."""
        self.selected_trace_ids_by_scope[scope_key] = set(int(trace_id) for trace_id in trace_ids)
