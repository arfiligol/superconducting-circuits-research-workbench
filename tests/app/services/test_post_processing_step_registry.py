"""Tests for Simulation post-processing step registry service."""

from __future__ import annotations

import numpy as np
import pytest

from legacy.legacy_nicegui_archived.services.post_processing_step_registry import (
    build_default_step_config,
    preview_pipeline_labels,
    run_post_processing_step,
    serialize_post_processing_step,
)
from core.simulation.application.post_processing import PortMatrixSweep


def _sample_sweep() -> PortMatrixSweep:
    frequencies = (1.0, 2.0)
    labels = ("1", "2", "3")
    base = np.array(
        [
            [1.0 + 0.0j, 0.0 + 0.0j, 0.0 + 0.0j],
            [0.0 + 0.0j, 2.0 + 0.0j, 0.0 + 0.0j],
            [0.0 + 0.0j, 0.0 + 0.0j, 3.0 + 0.0j],
        ],
        dtype=np.complex128,
    )
    return PortMatrixSweep(
        frequencies_ghz=frequencies,
        mode=(0,),
        labels=labels,
        y_matrices=(base, base.copy()),
        source_kind="y",
    )


def test_build_default_step_config_returns_expected_shapes() -> None:
    coordinate = build_default_step_config(
        "coordinate_transform",
        default_port_a=1,
        default_port_b=2,
    )
    kron = build_default_step_config(
        "kron_reduction",
        default_port_a=1,
        default_port_b=2,
    )

    assert coordinate["type"] == "coordinate_transform"
    assert coordinate["weight_mode"] == "auto"
    assert coordinate["port_a"] == 1
    assert coordinate["port_b"] == 2
    assert kron == {"type": "kron_reduction", "enabled": True, "keep_labels": []}


def test_preview_pipeline_labels_applies_coordinate_and_kron_steps() -> None:
    labels = ("1", "2", "3")
    sequence = [
        {
            "id": 1,
            "type": "coordinate_transform",
            "enabled": True,
            "template": "cm_dm",
            "port_a": 1,
            "port_b": 2,
        },
        {
            "id": 2,
            "type": "kron_reduction",
            "enabled": True,
            "keep_labels": ["dm(1,2)", "3"],
        },
    ]

    preview = preview_pipeline_labels(initial_labels=labels, step_sequence=sequence)
    assert preview == ("dm(1,2)", "3")


def test_run_post_processing_step_coordinate_transform_manual_mode() -> None:
    sweep = _sample_sweep()
    step = {
        "id": 1,
        "type": "coordinate_transform",
        "enabled": True,
        "template": "cm_dm",
        "weight_mode": "manual",
        "alpha": 0.5,
        "beta": 0.5,
        "port_a": 1,
        "port_b": 2,
    }

    execution = run_post_processing_step(
        sweep=sweep,
        step=step,
        circuit_definition=None,
        estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
    )
    assert execution.sweep.labels[0] == "cm(1,2)"
    assert execution.sweep.labels[1] == "dm(1,2)"
    assert execution.flow_step["type"] == "coordinate_transform"
    assert execution.normalized_step["alpha"] == 0.5


def test_run_post_processing_step_coordinate_transform_auto_requires_definition() -> None:
    sweep = _sample_sweep()
    step = {
        "id": 1,
        "type": "coordinate_transform",
        "enabled": True,
        "template": "cm_dm",
        "weight_mode": "auto",
        "port_a": 1,
        "port_b": 2,
    }

    with pytest.raises(ValueError, match="Auto weight mode requires a loaded circuit definition"):
        run_post_processing_step(
            sweep=sweep,
            step=step,
            circuit_definition=None,
            estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
        )


def test_run_post_processing_step_kron_reduction_normalizes_keep_labels() -> None:
    step = {
        "id": 2,
        "type": "kron_reduction",
        "enabled": True,
        "keep_labels": ["2", "3"],
    }
    execution = run_post_processing_step(
        sweep=_sample_sweep(),
        step=step,
        circuit_definition=None,
        estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
    )
    assert execution.sweep.labels == ("2", "3")
    assert execution.flow_step["keep_labels"] == ["2", "3"]
    assert execution.normalized_step["keep_labels"] == ["2", "3"]
    assert serialize_post_processing_step(execution.normalized_step)["type"] == "kron_reduction"
