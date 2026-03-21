"""Shared persisted request contract for WS8 characterization task execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legacy.legacy_nicegui_archived.api.schemas import CharacterizationTaskCreateRequest
from legacy.legacy_nicegui_archived.services.characterization_runner import CharacterizationRunRequest
from legacy.legacy_nicegui_archived.services.execution_context import ActorContext, UseCaseContext

_CHARACTERIZATION_REQUEST_KEY = "characterization_request"


def _context_payload_for_task(context: UseCaseContext) -> dict[str, Any]:
    payload = context.to_payload()
    payload.pop("requested_at", None)
    return payload


@dataclass(frozen=True)
class PersistedCharacterizationTaskRequest:
    """Worker-safe characterization inputs serialized through `TaskRecord`."""

    design_id: int
    analysis_id: str
    analysis_label: str | None
    run_id: str
    trace_record_ids: tuple[int, ...]
    selected_batch_ids: tuple[int, ...]
    selected_scope_token: str
    trace_mode_group: str | None
    config_state: dict[str, str | float | int | None]
    summary_payload: dict[str, Any]
    context_payload: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "design_id": int(self.design_id),
            "analysis_id": str(self.analysis_id),
            "run_id": str(self.run_id),
            "trace_record_ids": [int(trace_id) for trace_id in self.trace_record_ids],
            "selected_batch_ids": [int(batch_id) for batch_id in self.selected_batch_ids],
            "selected_scope_token": str(self.selected_scope_token),
            "config_state": dict(self.config_state),
            "summary_payload": dict(self.summary_payload),
        }
        if self.analysis_label is not None:
            payload["analysis_label"] = str(self.analysis_label)
        if self.trace_mode_group is not None:
            payload["trace_mode_group"] = str(self.trace_mode_group)
        if self.context_payload is not None:
            payload["context"] = dict(self.context_payload)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> PersistedCharacterizationTaskRequest:
        raw_trace_ids = payload.get("trace_record_ids", [])
        raw_batch_ids = payload.get("selected_batch_ids", [])
        raw_config_state = payload.get("config_state", {})
        raw_summary_payload = payload.get("summary_payload", {})
        raw_context = payload.get("context")
        if not isinstance(raw_trace_ids, list):
            raise ValueError("characterization_request.trace_record_ids must be a list.")
        if not isinstance(raw_batch_ids, list):
            raise ValueError("characterization_request.selected_batch_ids must be a list.")
        if not isinstance(raw_config_state, dict):
            raise ValueError("characterization_request.config_state must be an object.")
        if not isinstance(raw_summary_payload, dict):
            raise ValueError("characterization_request.summary_payload must be an object.")
        if raw_context is not None and not isinstance(raw_context, dict):
            raise ValueError("characterization_request.context must be an object.")
        analysis_id = str(payload.get("analysis_id", "")).strip()
        if not analysis_id:
            raise ValueError("characterization_request.analysis_id is required.")
        return cls(
            design_id=int(payload.get("design_id", 0) or 0),
            analysis_id=analysis_id,
            analysis_label=(
                str(payload["analysis_label"]).strip()
                if payload.get("analysis_label") is not None
                else None
            ),
            run_id=str(payload.get("run_id", "")).strip(),
            trace_record_ids=tuple(
                int(trace_id) for trace_id in raw_trace_ids if isinstance(trace_id, int)
            ),
            selected_batch_ids=tuple(
                int(batch_id) for batch_id in raw_batch_ids if isinstance(batch_id, int)
            ),
            selected_scope_token=str(payload.get("selected_scope_token", "")).strip(),
            trace_mode_group=(
                str(payload["trace_mode_group"]).strip()
                if payload.get("trace_mode_group") is not None
                else None
            ),
            config_state=dict(raw_config_state),
            summary_payload=dict(raw_summary_payload),
            context_payload=dict(raw_context) if isinstance(raw_context, dict) else None,
        )

    def use_case_context(self) -> UseCaseContext:
        payload = dict(self.context_payload or {})
        actor_payload = payload.get("actor")
        metadata = payload.get("metadata")
        raw_actor_metadata = (
            actor_payload.get("metadata") if isinstance(actor_payload, dict) else None
        )
        actor_metadata = (
            {str(key): value for key, value in raw_actor_metadata.items()}
            if isinstance(raw_actor_metadata, dict)
            else {}
        )
        return UseCaseContext(
            source=str(payload.get("source", "task_record") or "task_record"),
            task_id=int(payload["task_id"]) if payload.get("task_id") is not None else None,
            dedupe_key=(
                str(payload["dedupe_key"]).strip()
                if payload.get("dedupe_key") is not None
                else None
            ),
            force_rerun=bool(payload.get("force_rerun", False)),
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
            actor=ActorContext(
                actor_id=(
                    int(actor_payload["actor_id"])
                    if isinstance(actor_payload, dict) and actor_payload.get("actor_id") is not None
                    else None
                ),
                requested_by=(
                    str(actor_payload.get("requested_by", "task_record"))
                    if isinstance(actor_payload, dict)
                    else "task_record"
                ),
                role=(
                    str(actor_payload["role"])
                    if isinstance(actor_payload, dict) and actor_payload.get("role") is not None
                    else None
                ),
                auth_source=(
                    str(actor_payload.get("auth_source", "task_record"))
                    if isinstance(actor_payload, dict)
                    else "task_record"
                ),
                metadata=dict(actor_metadata),
            ),
        )

    def to_run_request(self) -> CharacterizationRunRequest:
        return CharacterizationRunRequest(
            analysis_id=self.analysis_id,
            analysis_label=self.analysis_label,
            dataset_id=int(self.design_id),
            config_state=dict(self.config_state),
            run_id=str(self.run_id),
            trace_record_ids=list(self.trace_record_ids),
            selected_batch_ids=list(self.selected_batch_ids),
            selected_scope_token=str(self.selected_scope_token),
            trace_mode_group=self.trace_mode_group,
            summary_payload=dict(self.summary_payload),
            context=self.use_case_context(),
        )


@dataclass(frozen=True)
class PreparedCharacterizationSubmission:
    """Canonical WS8 characterization submit payload assembled in the page layer."""

    api_request: CharacterizationTaskCreateRequest
    persisted_request: PersistedCharacterizationTaskRequest


def build_characterization_submission(
    *,
    design_id: int,
    analysis_id: str,
    analysis_label: str | None,
    run_id: str,
    trace_record_ids: list[int],
    selected_batch_ids: list[int],
    selected_scope_token: str,
    trace_mode_group: str | None,
    config_state: dict[str, str | float | int | None],
    summary_payload: dict[str, Any],
    context: UseCaseContext,
    force_rerun: bool,
) -> PreparedCharacterizationSubmission:
    """Build the persisted request payload sent to `POST /api/v1/tasks/characterization`."""
    persisted_request = PersistedCharacterizationTaskRequest(
        design_id=int(design_id),
        analysis_id=str(analysis_id),
        analysis_label=str(analysis_label) if analysis_label is not None else None,
        run_id=str(run_id),
        trace_record_ids=tuple(int(trace_id) for trace_id in trace_record_ids),
        selected_batch_ids=tuple(int(batch_id) for batch_id in selected_batch_ids),
        selected_scope_token=str(selected_scope_token),
        trace_mode_group=str(trace_mode_group) if trace_mode_group is not None else None,
        config_state=dict(config_state),
        summary_payload=dict(summary_payload),
        context_payload=_context_payload_for_task(context),
    )
    api_request = CharacterizationTaskCreateRequest(
        design_id=int(design_id),
        analysis_id=str(analysis_id),
        analysis_label=str(analysis_label) if analysis_label is not None else None,
        run_id=str(run_id),
        trace_record_ids=[int(trace_id) for trace_id in trace_record_ids],
        selected_batch_ids=[int(batch_id) for batch_id in selected_batch_ids],
        selected_scope_token=str(selected_scope_token),
        trace_mode_group=str(trace_mode_group) if trace_mode_group is not None else None,
        config_state=dict(config_state),
        summary_payload=dict(summary_payload),
        request_payload=embed_characterization_request({}, persisted_request),
        force_rerun=bool(force_rerun),
    )
    return PreparedCharacterizationSubmission(
        api_request=api_request,
        persisted_request=persisted_request,
    )


def embed_characterization_request(
    payload: dict[str, Any],
    request: PersistedCharacterizationTaskRequest,
) -> dict[str, Any]:
    normalized = dict(payload)
    normalized[_CHARACTERIZATION_REQUEST_KEY] = request.to_payload()
    return normalized


def extract_characterization_request(
    payload: dict[str, Any],
) -> PersistedCharacterizationTaskRequest | None:
    raw_request = payload.get(_CHARACTERIZATION_REQUEST_KEY)
    if not isinstance(raw_request, dict):
        return None
    return PersistedCharacterizationTaskRequest.from_payload(raw_request)


def extract_characterization_request_from_api_payload(
    payload: dict[str, Any],
) -> PersistedCharacterizationTaskRequest | None:
    nested_payload = payload.get("request_payload")
    if isinstance(nested_payload, dict):
        request = extract_characterization_request(dict(nested_payload))
        if request is not None:
            return request
    return extract_characterization_request(payload)
