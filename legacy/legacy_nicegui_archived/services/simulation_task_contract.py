"""Shared persisted request contract for WS6 simulation task execution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from legacy.legacy_nicegui_archived.services.execution_context import ActorContext, UseCaseContext
from core.simulation.domain.circuit import CircuitDefinition, FrequencyRange, SimulationConfig

_SIMULATION_REQUEST_KEY = "simulation_request"


@dataclass(frozen=True)
class PersistedSimulationTaskRequest:
    """Worker-safe simulation task inputs serialized through TaskRecord."""

    design_id: int
    design_name: str
    circuit_payload: dict[str, Any]
    freq_range_payload: dict[str, Any]
    config_payload: dict[str, Any]
    config_snapshot: dict[str, Any]
    source_meta: dict[str, Any]
    schema_source_hash: str
    simulation_setup_hash: str
    sweep_setup_payload: dict[str, Any] | None = None
    sweep_setup_hash: str | None = None
    context_payload: dict[str, Any] | None = None

    def to_payload(self) -> dict[str, Any]:
        """Return the JSON-safe persisted task payload."""
        payload: dict[str, Any] = {
            "design_id": int(self.design_id),
            "design_name": str(self.design_name),
            "circuit": dict(self.circuit_payload),
            "freq_range": dict(self.freq_range_payload),
            "config": dict(self.config_payload),
            "config_snapshot": dict(self.config_snapshot),
            "source_meta": dict(self.source_meta),
            "schema_source_hash": str(self.schema_source_hash),
            "simulation_setup_hash": str(self.simulation_setup_hash),
        }
        if self.sweep_setup_payload is not None:
            payload["sweep_setup_payload"] = dict(self.sweep_setup_payload)
        if self.sweep_setup_hash is not None:
            payload["sweep_setup_hash"] = str(self.sweep_setup_hash)
        if self.context_payload is not None:
            payload["context"] = dict(self.context_payload)
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> PersistedSimulationTaskRequest:
        """Validate and normalize one persisted simulation request payload."""
        raw_circuit = payload.get("circuit")
        raw_freq_range = payload.get("freq_range")
        raw_config = payload.get("config")
        raw_config_snapshot = payload.get("config_snapshot")
        raw_source_meta = payload.get("source_meta")
        if not isinstance(raw_circuit, dict):
            raise ValueError("simulation_request.circuit must be an object.")
        if not isinstance(raw_freq_range, dict):
            raise ValueError("simulation_request.freq_range must be an object.")
        if not isinstance(raw_config, dict):
            raise ValueError("simulation_request.config must be an object.")
        if not isinstance(raw_config_snapshot, dict):
            raise ValueError("simulation_request.config_snapshot must be an object.")
        if not isinstance(raw_source_meta, dict):
            raise ValueError("simulation_request.source_meta must be an object.")
        schema_source_hash = str(payload.get("schema_source_hash", "")).strip()
        simulation_setup_hash = str(payload.get("simulation_setup_hash", "")).strip()
        if not schema_source_hash:
            raise ValueError("simulation_request.schema_source_hash is required.")
        if not simulation_setup_hash:
            raise ValueError("simulation_request.simulation_setup_hash is required.")
        raw_sweep_setup_payload = payload.get("sweep_setup_payload")
        if raw_sweep_setup_payload is not None and not isinstance(raw_sweep_setup_payload, dict):
            raise ValueError("simulation_request.sweep_setup_payload must be an object.")
        raw_context = payload.get("context")
        if raw_context is not None and not isinstance(raw_context, dict):
            raise ValueError("simulation_request.context must be an object.")
        return cls(
            design_id=int(payload.get("design_id", 0) or 0),
            design_name=str(payload.get("design_name", "")).strip() or "design",
            circuit_payload=dict(raw_circuit),
            freq_range_payload=dict(raw_freq_range),
            config_payload=dict(raw_config),
            config_snapshot=dict(raw_config_snapshot),
            source_meta=dict(raw_source_meta),
            schema_source_hash=schema_source_hash,
            simulation_setup_hash=simulation_setup_hash,
            sweep_setup_payload=(
                dict(raw_sweep_setup_payload) if isinstance(raw_sweep_setup_payload, dict) else None
            ),
            sweep_setup_hash=(
                str(payload.get("sweep_setup_hash")).strip()
                if payload.get("sweep_setup_hash") is not None
                else None
            ),
            context_payload=dict(raw_context) if isinstance(raw_context, dict) else None,
        )

    def circuit_definition(self) -> CircuitDefinition:
        """Rebuild the circuit domain object."""
        return CircuitDefinition.model_validate(self.circuit_payload)

    def frequency_range(self) -> FrequencyRange:
        """Rebuild the frequency-range object."""
        return FrequencyRange.model_validate(self.freq_range_payload)

    def simulation_config(self) -> SimulationConfig:
        """Rebuild the simulation config object."""
        return SimulationConfig.model_validate(self.config_payload)

    def use_case_context(self) -> UseCaseContext:
        """Rebuild the execution context carried through TaskRecord."""
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


def embed_simulation_request(
    payload: dict[str, Any],
    request: PersistedSimulationTaskRequest,
) -> dict[str, Any]:
    """Attach the canonical simulation request to one API task payload."""
    normalized = dict(payload)
    normalized[_SIMULATION_REQUEST_KEY] = request.to_payload()
    return normalized


def extract_simulation_request(payload: dict[str, Any]) -> PersistedSimulationTaskRequest | None:
    """Return the persisted simulation request if the task payload carries one."""
    raw_request = payload.get(_SIMULATION_REQUEST_KEY)
    if not isinstance(raw_request, dict):
        return None
    return PersistedSimulationTaskRequest.from_payload(raw_request)


def extract_simulation_request_from_api_payload(
    payload: dict[str, Any],
) -> PersistedSimulationTaskRequest | None:
    """Return the persisted simulation request from one API task payload shape."""
    nested_payload = payload.get("request_payload")
    if isinstance(nested_payload, dict):
        request = extract_simulation_request(dict(nested_payload))
        if request is not None:
            return request
    return extract_simulation_request(payload)
