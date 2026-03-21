"""Registry-driven post-processing step helpers for Simulation page."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core.simulation.application.post_processing import (
    PortMatrixSweep,
    apply_coordinate_transform,
    build_common_differential_transform,
    kron_reduce,
)
from core.simulation.domain.circuit import CircuitDefinition

POST_PROCESS_STEP_OPTIONS: dict[str, str] = {
    "coordinate_transform": "Coordinate Transformation",
    "kron_reduction": "Kron Reduction",
}


@dataclass(frozen=True)
class PostProcessingStepExecution:
    """Result payload after one registry step execution."""

    sweep: PortMatrixSweep
    flow_step: dict[str, Any]
    normalized_step: dict[str, Any]


def build_default_step_config(
    step_type: str,
    *,
    default_port_a: int,
    default_port_b: int,
) -> dict[str, Any]:
    """Build one default step config from step type token."""
    normalized = str(step_type).strip().lower()
    if normalized == "kron_reduction":
        return {
            "type": "kron_reduction",
            "enabled": True,
            "keep_labels": [],
        }
    return {
        "type": "coordinate_transform",
        "enabled": True,
        "template": "cm_dm",
        "weight_mode": "auto",
        "alpha": 0.5,
        "beta": 0.5,
        "port_a": default_port_a,
        "port_b": default_port_b,
    }


def serialize_post_processing_step(step: dict[str, Any]) -> dict[str, Any]:
    """Serialize one in-memory step for setup persistence."""
    step_type = str(step.get("type", "coordinate_transform"))
    if step_type == "kron_reduction":
        return {
            "type": "kron_reduction",
            "enabled": bool(step.get("enabled", True)),
            "keep_labels": [str(label) for label in (step.get("keep_labels") or [])],
        }
    return {
        "type": "coordinate_transform",
        "enabled": bool(step.get("enabled", True)),
        "template": str(step.get("template", "cm_dm")),
        "weight_mode": str(step.get("weight_mode", "auto")),
        "alpha": float(step.get("alpha", 0.5)),
        "beta": float(step.get("beta", 0.5)),
        "port_a": step.get("port_a"),
        "port_b": step.get("port_b"),
    }


def normalize_saved_step_config(
    *,
    raw_step: dict[str, Any],
    step_id: int,
    default_port_a: int,
    default_port_b: int,
) -> dict[str, Any]:
    """Normalize one saved setup step payload into runtime step state."""
    normalized = build_default_step_config(
        str(raw_step.get("type", "coordinate_transform")),
        default_port_a=default_port_a,
        default_port_b=default_port_b,
    )
    normalized["id"] = step_id
    normalized["enabled"] = bool(raw_step.get("enabled", normalized["enabled"]))
    if normalized["type"] == "coordinate_transform":
        normalized["template"] = str(raw_step.get("template", normalized["template"]))
        normalized["weight_mode"] = str(raw_step.get("weight_mode", normalized["weight_mode"]))
        normalized["alpha"] = float(raw_step.get("alpha", normalized["alpha"]))
        normalized["beta"] = float(raw_step.get("beta", normalized["beta"]))
        normalized["port_a"] = raw_step.get("port_a", normalized["port_a"])
        normalized["port_b"] = raw_step.get("port_b", normalized["port_b"])
    else:
        normalized["keep_labels"] = [str(label) for label in (raw_step.get("keep_labels") or [])]
    return normalized


def preview_pipeline_labels(
    *,
    initial_labels: tuple[str, ...],
    step_sequence: list[dict[str, Any]],
    stop_before_step_id: int | None = None,
) -> tuple[str, ...]:
    """Preview basis labels after enabled steps without touching sweep values."""
    labels = initial_labels
    for step in step_sequence:
        if stop_before_step_id is not None and int(step.get("id", -1)) == stop_before_step_id:
            break
        if not bool(step.get("enabled", True)):
            continue
        labels = _preview_step_labels(labels, step)
    return labels


def run_post_processing_step(
    *,
    sweep: PortMatrixSweep,
    step: dict[str, Any],
    circuit_definition: CircuitDefinition | None,
    estimate_auto_weights: Callable[[CircuitDefinition, int, int], tuple[float, float] | None],
) -> PostProcessingStepExecution:
    """Execute one registry step and return normalized step + flow snapshot."""
    step_type = str(step.get("type", "coordinate_transform"))
    if step_type == "kron_reduction":
        keep_tokens = {str(label) for label in (step.get("keep_labels") or [])}
        selected_keep_labels = [label for label in sweep.labels if label in keep_tokens]
        keep_indices = [index for index, label in enumerate(sweep.labels) if label in keep_tokens]
        if not keep_indices:
            raise ValueError("Kron reduction requires at least one kept basis label.")
        next_sweep = kron_reduce(sweep, keep_indices=keep_indices)
        normalized_step = dict(step)
        normalized_step["keep_labels"] = selected_keep_labels
        return PostProcessingStepExecution(
            sweep=next_sweep,
            flow_step={
                "step_id": int(step.get("id", -1)),
                "type": "kron_reduction",
                "keep_indices": list(keep_indices),
                "keep_labels": selected_keep_labels,
            },
            normalized_step=normalized_step,
        )

    template = str(step.get("template", "identity"))
    if template != "cm_dm":
        return PostProcessingStepExecution(
            sweep=sweep,
            flow_step={
                "step_id": int(step.get("id", -1)),
                "type": "coordinate_transform",
                "template": "identity",
            },
            normalized_step=dict(step),
        )

    if sweep.dimension < 2:
        raise ValueError("Common/Differential transform requires at least two available ports.")
    default_label = sweep.labels[0] if sweep.labels else "1"
    fallback_port = int(default_label) if default_label.isdigit() else 1
    selected_port_a = _coerce_int_value(step.get("port_a"), fallback_port)
    selected_port_b = _coerce_int_value(step.get("port_b"), fallback_port)
    if selected_port_a == selected_port_b:
        raise ValueError("Port A and Port B must be different.")

    label_to_index = {int(label): idx for idx, label in enumerate(sweep.labels) if label.isdigit()}
    if selected_port_a not in label_to_index or selected_port_b not in label_to_index:
        raise ValueError("Selected ports are not available in current sweep basis.")

    weight_mode = str(step.get("weight_mode", "auto"))
    if weight_mode == "auto":
        if circuit_definition is None:
            raise ValueError("Auto weight mode requires a loaded circuit definition.")
        estimated = estimate_auto_weights(circuit_definition, selected_port_a, selected_port_b)
        if estimated is None:
            raise ValueError(
                "Unable to estimate auto weights from capacitor-to-ground topology. "
                "Switch to manual mode."
            )
        alpha, beta = estimated
    else:
        alpha = float(step.get("alpha", 0.0))
        beta = float(step.get("beta", 0.0))

    transform = build_common_differential_transform(
        dimension=sweep.dimension,
        first_index=label_to_index[selected_port_a],
        second_index=label_to_index[selected_port_b],
        alpha=alpha,
        beta=beta,
    )
    labels = list(sweep.labels)
    idx_a = label_to_index[selected_port_a]
    idx_b = label_to_index[selected_port_b]
    labels[idx_a] = f"cm({selected_port_a},{selected_port_b})"
    labels[idx_b] = f"dm({selected_port_a},{selected_port_b})"
    next_sweep = apply_coordinate_transform(
        sweep,
        transform_matrix=transform,
        labels=tuple(labels),
    )

    normalized_step = dict(step)
    normalized_step["port_a"] = selected_port_a
    normalized_step["port_b"] = selected_port_b
    normalized_step["alpha"] = alpha
    normalized_step["beta"] = beta
    normalized_step["template"] = "cm_dm"
    normalized_step["weight_mode"] = weight_mode

    return PostProcessingStepExecution(
        sweep=next_sweep,
        flow_step={
            "step_id": int(step.get("id", -1)),
            "type": "coordinate_transform",
            "template": "cm_dm",
            "weight_mode": weight_mode,
            "port_a": selected_port_a,
            "port_b": selected_port_b,
            "alpha": alpha,
            "beta": beta,
        },
        normalized_step=normalized_step,
    )


def _preview_step_labels(labels: tuple[str, ...], step: dict[str, Any]) -> tuple[str, ...]:
    """Preview label rewrite for one step only."""
    step_type = str(step.get("type", ""))
    if step_type == "kron_reduction":
        keep_labels = [str(label) for label in (step.get("keep_labels") or [])]
        filtered = [label for label in labels if label in set(keep_labels)]
        return tuple(filtered) if filtered else labels

    if step_type != "coordinate_transform":
        return labels
    if str(step.get("template", "identity")) != "cm_dm":
        return labels
    if not labels:
        return labels

    port_a = _coerce_int_value(step.get("port_a"), int(labels[0]) if labels[0].isdigit() else 1)
    port_b = _coerce_int_value(step.get("port_b"), int(labels[-1]) if labels[-1].isdigit() else 1)
    label_to_index = {int(label): idx for idx, label in enumerate(labels) if str(label).isdigit()}
    if port_a == port_b or port_a not in label_to_index or port_b not in label_to_index:
        return labels

    updated = list(labels)
    idx_a = label_to_index[port_a]
    idx_b = label_to_index[port_b]
    updated[idx_a] = f"cm({port_a},{port_b})"
    updated[idx_b] = f"dm({port_a},{port_b})"
    return tuple(updated)


def _coerce_int_value(value: object, fallback: int) -> int:
    """Convert one raw form value to int with fallback."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return int(fallback)
    return int(fallback)


__all__ = [
    "POST_PROCESS_STEP_OPTIONS",
    "PostProcessingStepExecution",
    "build_default_step_config",
    "normalize_saved_step_config",
    "preview_pipeline_labels",
    "run_post_processing_step",
    "serialize_post_processing_step",
]
