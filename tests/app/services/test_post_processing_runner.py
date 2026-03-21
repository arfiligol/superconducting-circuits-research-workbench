"""Tests for Simulation post-processing runner use-case service."""

from __future__ import annotations

import pytest

from legacy.legacy_nicegui_archived.services.execution_context import ActorContext, UseCaseContext
from legacy.legacy_nicegui_archived.services.post_processing_runner import (
    PostProcessingInputSource,
    PostProcessingRunRequest,
    execute_post_processing_pipeline,
)
from core.simulation.application.post_processing import PortMatrixSweepRun
from core.simulation.application.run_simulation import (
    SimulationSweepAxis,
    SimulationSweepPointResult,
    SimulationSweepRun,
    simulation_sweep_run_to_payload,
)
from core.simulation.domain.circuit import SimulationResult


def _sample_result() -> SimulationResult:
    frequencies = [1.0, 2.0]
    s11_real = [0.1, 0.2]
    s11_imag = [0.0, 0.0]
    mode = (0,)
    y_mode_real: dict[str, list[float]] = {}
    y_mode_imag: dict[str, list[float]] = {}
    for output_port, input_port, value in (
        (1, 1, 1.0),
        (1, 2, 0.0),
        (2, 1, 0.0),
        (2, 2, 2.0),
    ):
        label = SimulationResult._mode_trace_label(mode, output_port, mode, input_port)
        y_mode_real[label] = [value, value]
        y_mode_imag[label] = [0.0, 0.0]
    return SimulationResult(
        frequencies_ghz=frequencies,
        s11_real=s11_real,
        s11_imag=s11_imag,
        port_indices=[1, 2],
        mode_indices=[(0,)],
        y_parameter_mode_real=y_mode_real,
        y_parameter_mode_imag=y_mode_imag,
    )


def _source_from_result(
    result: SimulationResult | None = None,
    *,
    source_batch_id: int | None = 12,
    authority: str = "persisted_trace_batch",
) -> PostProcessingInputSource:
    resolved_result = result or _sample_result()
    return PostProcessingInputSource(
        source_batch_id=source_batch_id,
        canonical_payload=resolved_result.model_dump(mode="json"),
        authority=authority,
        run_kind="single_result",
    )


def test_execute_post_processing_pipeline_requires_mode_selection() -> None:
    with pytest.raises(ValueError, match="Please select one mode before running post-processing"):
        execute_post_processing_pipeline(
            PostProcessingRunRequest(
                source=_source_from_result(),
                input_source="raw_y",
                mode_filter="base",
                mode_token="",
                reference_impedance_ohm=50.0,
                step_sequence=[],
                circuit_definition=None,
            ),
            estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
        )


def test_execute_post_processing_pipeline_identity_marks_not_hfss_comparable() -> None:
    run = execute_post_processing_pipeline(
        PostProcessingRunRequest(
            source=_source_from_result(),
            input_source="raw_y",
            mode_filter="base",
            mode_token="0",
            reference_impedance_ohm=50.0,
            step_sequence=[
                {
                    "id": 1,
                    "type": "coordinate_transform",
                    "enabled": True,
                    "template": "identity",
                }
            ],
            circuit_definition=None,
        ),
        estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
    )

    assert run.sweep.labels == ("1", "2")
    assert run.flow_spec["hfss_comparable"] is False
    assert "Port Termination Compensation is disabled." in str(
        run.flow_spec["hfss_not_comparable_reason"]
    )
    assert run.flow_spec["steps"][0]["template"] == "identity"


def test_execute_post_processing_pipeline_ct_plus_kron_marks_hfss_comparable() -> None:
    run = execute_post_processing_pipeline(
        PostProcessingRunRequest(
            source=_source_from_result(),
            input_source="ptc_y",
            mode_filter="base",
            mode_token="0",
            reference_impedance_ohm=50.0,
            step_sequence=[
                {
                    "id": 1,
                    "type": "coordinate_transform",
                    "enabled": True,
                    "template": "cm_dm",
                    "weight_mode": "manual",
                    "alpha": 0.5,
                    "beta": 0.5,
                    "port_a": 1,
                    "port_b": 2,
                },
                {
                    "id": 2,
                    "type": "kron_reduction",
                    "enabled": True,
                    "keep_labels": ["dm(1,2)"],
                },
            ],
            circuit_definition=None,
        ),
        estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
    )

    assert run.sweep.labels == ("dm(1,2)",)
    assert run.flow_spec["hfss_comparable"] is True
    assert run.flow_spec["input_y_source"] == "ptc_y"
    assert len(run.flow_spec["steps"]) == 2
    assert run.normalized_steps[0]["alpha"] == 0.5


def test_execute_post_processing_pipeline_preserves_full_parameter_sweep_runtime() -> None:
    first = _sample_result()
    second = _sample_result().model_copy(deep=True)
    second.y_parameter_mode_real["om=0|op=1|im=0|ip=1"] = [3.0, 4.0]
    second.y_parameter_mode_real["om=0|op=2|im=0|ip=2"] = [5.0, 6.0]

    sweep_payload = simulation_sweep_run_to_payload(
        SimulationSweepRun(
            axes=(SimulationSweepAxis(target_value_ref="Lj", values=(900.0, 1100.0), unit="pH"),),
            points=(
                SimulationSweepPointResult(
                    point_index=0,
                    axis_indices=(0,),
                    axis_values={"Lj": 900.0},
                    result=first,
                ),
                SimulationSweepPointResult(
                    point_index=1,
                    axis_indices=(1,),
                    axis_values={"Lj": 1100.0},
                    result=second,
                ),
            ),
            representative_point_index=0,
        )
    )

    run = execute_post_processing_pipeline(
        PostProcessingRunRequest(
            source=PostProcessingInputSource(
                source_batch_id=77,
                canonical_payload=sweep_payload,
                authority="persisted_trace_batch",
                run_kind="parameter_sweep",
            ),
            input_source="raw_y",
            mode_filter="base",
            mode_token="0",
            reference_impedance_ohm=50.0,
            step_sequence=[],
            circuit_definition=None,
        ),
        estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
    )

    assert isinstance(run.runtime_output, PortMatrixSweepRun)
    assert run.flow_spec["run_kind"] == "parameter_sweep"
    assert run.flow_spec["point_count"] == 2
    assert run.flow_spec["preview_projection"] == {
        "kind": "representative_point",
        "point_index": 0,
        "axis_indices": [0],
        "axis_values": {"Lj": 900.0},
    }
    assert run.preview_sweep.trace(0, 0) == [1.0 + 0.0j, 1.0 + 0.0j]
    assert run.runtime_output.points[1].sweep.trace(0, 0) == [3.0 + 0.0j, 4.0 + 0.0j]
    assert run.runtime_output.points[1].sweep.trace(1, 1) == [5.0 + 0.0j, 6.0 + 0.0j]


def test_execute_post_processing_pipeline_returns_context_and_progress() -> None:
    progress_updates = []
    context = UseCaseContext(
        actor=ActorContext(actor_id=5, role="admin", requested_by="api"),
        source="worker",
        task_id=42,
    )

    run = execute_post_processing_pipeline(
        PostProcessingRunRequest(
            source=_source_from_result(source_batch_id=42),
            input_source="raw_y",
            mode_filter="base",
            mode_token="0",
            reference_impedance_ohm=50.0,
            step_sequence=[],
            circuit_definition=None,
            context=context,
        ),
        estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
        progress_callback=progress_updates.append,
    )

    assert run.context == context
    assert [update.phase for update in run.progress_updates] == ["running", "completed"]
    assert progress_updates[0].to_payload()["details"]["source_batch_id"] == 42
    assert progress_updates[0].to_payload()["details"]["requested_by"] == "api"
    assert progress_updates[1].to_payload()["details"]["point_count"] == 1


def test_execute_post_processing_pipeline_accepts_persisted_style_source_payload() -> None:
    source = PostProcessingInputSource(
        source_batch_id=91,
        canonical_payload=simulation_sweep_run_to_payload(
            SimulationSweepRun(
                axes=(
                    SimulationSweepAxis(
                        target_value_ref="Lj",
                        values=(900.0, 1100.0),
                        unit="pH",
                    ),
                ),
                points=(
                    SimulationSweepPointResult(
                        point_index=0,
                        axis_indices=(0,),
                        axis_values={"Lj": 900.0},
                        result=_sample_result(),
                    ),
                    SimulationSweepPointResult(
                        point_index=1,
                        axis_indices=(1,),
                        axis_values={"Lj": 1100.0},
                        result=_sample_result(),
                    ),
                ),
                representative_point_index=0,
            )
        ),
        authority="persisted_trace_batch",
        run_kind="parameter_sweep",
    )

    run = execute_post_processing_pipeline(
        PostProcessingRunRequest(
            source=source,
            input_source="raw_y",
            mode_filter="base",
            mode_token="0",
            reference_impedance_ohm=50.0,
            step_sequence=[],
            circuit_definition=None,
        ),
        estimate_auto_weights=lambda _definition, _port_a, _port_b: (0.5, 0.5),
    )

    assert isinstance(run.runtime_output, PortMatrixSweepRun)
    assert run.flow_spec["run_kind"] == "parameter_sweep"
    assert run.flow_spec["point_count"] == 2
