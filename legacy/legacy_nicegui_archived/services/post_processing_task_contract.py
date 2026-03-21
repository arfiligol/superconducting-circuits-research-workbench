"""Shared persisted request contract for WS7 post-processing task execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legacy.legacy_nicegui_archived.api.schemas import PostProcessingTaskCreateRequest
from legacy.legacy_nicegui_archived.services.execution_context import ActorContext, UseCaseContext
from core.simulation.domain.circuit import CircuitDefinition

_POST_PROCESSING_REQUEST_KEY = "post_processing_request"


def _context_payload_for_task(context: UseCaseContext) -> dict[str, Any]:
    payload = context.to_payload()
    payload.pop("requested_at", None)
    return payload


@dataclass(frozen=True)
class PersistedPostProcessingTaskRequest:
    """Worker-safe post-processing task inputs serialized through TaskRecord."""

    design_id: int
    source_batch_id: int
    input_source: str
    mode_filter: str
    mode_token: str
    reference_impedance_ohm: float
    step_sequence: list[dict[str, Any]]
    termination_plan_payload: dict[str, Any] | None = None
    circuit_payload: dict[str, Any] | None = None
    context_payload: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "design_id": int(self.design_id),
            "source_batch_id": int(self.source_batch_id),
            "input_source": str(self.input_source),
            "mode_filter": str(self.mode_filter),
            "mode_token": str(self.mode_token),
            "reference_impedance_ohm": float(self.reference_impedance_ohm),
            "step_sequence": [dict(step) for step in self.step_sequence],
        }
        if self.termination_plan_payload is not None:
            payload["termination_plan"] = dict(self.termination_plan_payload)
        if self.circuit_payload is not None:
            payload["circuit"] = dict(self.circuit_payload)
        if self.context_payload is not None:
            payload["context"] = dict(self.context_payload)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> PersistedPostProcessingTaskRequest:
        raw_steps = payload.get("step_sequence", [])
        raw_termination_plan = payload.get("termination_plan")
        raw_circuit = payload.get("circuit")
        raw_context = payload.get("context")
        if not isinstance(raw_steps, list):
            raise ValueError("post_processing_request.step_sequence must be a list.")
        if raw_termination_plan is not None and not isinstance(raw_termination_plan, dict):
            raise ValueError("post_processing_request.termination_plan must be an object.")
        if raw_circuit is not None and not isinstance(raw_circuit, dict):
            raise ValueError("post_processing_request.circuit must be an object.")
        if raw_context is not None and not isinstance(raw_context, dict):
            raise ValueError("post_processing_request.context must be an object.")
        source_batch_id = int(payload.get("source_batch_id", 0) or 0)
        if source_batch_id <= 0:
            raise ValueError("post_processing_request.source_batch_id must be positive.")
        return cls(
            design_id=int(payload.get("design_id", 0) or 0),
            source_batch_id=source_batch_id,
            input_source=str(payload.get("input_source", "raw_y")).strip() or "raw_y",
            mode_filter=str(payload.get("mode_filter", "base")).strip() or "base",
            mode_token=str(payload.get("mode_token", "")).strip(),
            reference_impedance_ohm=float(payload.get("reference_impedance_ohm", 50.0) or 50.0),
            step_sequence=[dict(step) for step in raw_steps if isinstance(step, dict)],
            termination_plan_payload=(
                dict(raw_termination_plan) if isinstance(raw_termination_plan, dict) else None
            ),
            circuit_payload=dict(raw_circuit) if isinstance(raw_circuit, dict) else None,
            context_payload=dict(raw_context) if isinstance(raw_context, dict) else None,
        )

    def circuit_definition(self) -> CircuitDefinition | None:
        if self.circuit_payload is None:
            return None
        return CircuitDefinition.model_validate(self.circuit_payload)

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


@dataclass(frozen=True)
class PreparedPostProcessingSubmission:
    """Canonical WS7 post-processing submit payload assembled in the page layer."""

    api_request: PostProcessingTaskCreateRequest
    persisted_request: PersistedPostProcessingTaskRequest


def build_post_processing_submission(
    *,
    design_id: int,
    source_batch_id: int,
    input_source: str,
    mode_filter: str,
    mode_token: str,
    reference_impedance_ohm: float,
    step_sequence: list[dict[str, Any]],
    termination_plan_payload: dict[str, Any] | None,
    circuit_definition: CircuitDefinition | None,
    context: UseCaseContext,
    force_rerun: bool,
) -> PreparedPostProcessingSubmission:
    """Build the persisted request payload sent to `POST /api/v1/tasks/post-processing`."""
    if int(source_batch_id) <= 0:
        raise ValueError("Post-processing requires one persisted raw source batch.")
    persisted_request = PersistedPostProcessingTaskRequest(
        design_id=int(design_id),
        source_batch_id=int(source_batch_id),
        input_source=str(input_source),
        mode_filter=str(mode_filter),
        mode_token=str(mode_token),
        reference_impedance_ohm=float(reference_impedance_ohm),
        step_sequence=[dict(step) for step in step_sequence],
        termination_plan_payload=(
            dict(termination_plan_payload) if termination_plan_payload is not None else None
        ),
        circuit_payload=(
            circuit_definition.to_source_payload()
            if isinstance(circuit_definition, CircuitDefinition)
            else None
        ),
        context_payload=_context_payload_for_task(context),
    )
    api_request = PostProcessingTaskCreateRequest(
        design_id=int(design_id),
        source_batch_id=int(source_batch_id),
        input_source=str(input_source),
        request_payload=embed_post_processing_request({}, persisted_request),
        force_rerun=bool(force_rerun),
    )
    return PreparedPostProcessingSubmission(
        api_request=api_request,
        persisted_request=persisted_request,
    )


def embed_post_processing_request(
    payload: dict[str, Any],
    request: PersistedPostProcessingTaskRequest,
) -> dict[str, Any]:
    normalized = dict(payload)
    normalized[_POST_PROCESSING_REQUEST_KEY] = request.to_payload()
    return normalized


def extract_post_processing_request(
    payload: dict[str, Any],
) -> PersistedPostProcessingTaskRequest | None:
    raw_request = payload.get(_POST_PROCESSING_REQUEST_KEY)
    if not isinstance(raw_request, dict):
        return None
    return PersistedPostProcessingTaskRequest.from_payload(raw_request)


def extract_post_processing_request_from_api_payload(
    payload: dict[str, Any],
) -> PersistedPostProcessingTaskRequest | None:
    nested_payload = payload.get("request_payload")
    if isinstance(nested_payload, dict):
        request = extract_post_processing_request(dict(nested_payload))
        if request is not None:
            return request
    return extract_post_processing_request(payload)
