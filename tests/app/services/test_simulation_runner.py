"""Tests for the shared simulation execution boundary."""

from __future__ import annotations

import asyncio
from typing import cast

from legacy.legacy_nicegui_archived.services.execution_context import ActorContext, UseCaseContext
from legacy.legacy_nicegui_archived.services.simulation_runner import (
    SimulationRunRequest,
    execute_simulation_run,
    execute_simulation_run_async,
)
from core.simulation.domain.circuit import (
    CircuitDefinition,
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
)


def _sample_result() -> SimulationResult:
    return SimulationResult(
        frequencies_ghz=[1.0, 2.0],
        s11_real=[0.1, 0.2],
        s11_imag=[0.0, 0.0],
        port_indices=[1],
        mode_indices=[(0,)],
        y_parameter_mode_real={"om=0|op=1|im=0|ip=1": [1.0, 1.0]},
        y_parameter_mode_imag={"om=0|op=1|im=0|ip=1": [0.0, 0.0]},
    )


def test_execute_simulation_run_preserves_actor_context_and_progress() -> None:
    captured: dict[str, object] = {}
    progress_updates = []

    def _fake_execute(circuit: object, freq_range: FrequencyRange, config: SimulationConfig | None):
        captured["circuit"] = circuit
        captured["freq_range"] = freq_range
        captured["config"] = config
        return _sample_result()

    request = SimulationRunRequest(
        circuit=cast(CircuitDefinition, {"netlist": "demo"}),
        freq_range=FrequencyRange(start_ghz=1.0, stop_ghz=2.0, points=2),
        config=SimulationConfig(),
        context=UseCaseContext(
            actor=ActorContext(actor_id=7, role="user", requested_by="cli"),
            source="worker",
            task_id=11,
        ),
        stage_label="unit_test",
    )

    result = execute_simulation_run(
        request,
        progress_callback=progress_updates.append,
        execute=_fake_execute,
    )

    assert captured["circuit"] == {"netlist": "demo"}
    assert captured["freq_range"] == request.freq_range
    assert captured["config"] == request.config
    assert result.context.actor.actor_id == 7
    assert result.context.actor.role == "user"
    assert [update.phase for update in progress_updates] == ["running", "completed"]
    assert progress_updates[0].to_payload()["stale_after_seconds"] == 60
    assert progress_updates[1].to_payload()["details"]["requested_by"] == "cli"
    assert result.result.port_indices == [1]


def test_execute_simulation_run_async_uses_same_boundary() -> None:
    request = SimulationRunRequest(
        circuit=cast(CircuitDefinition, {"netlist": "demo"}),
        freq_range=FrequencyRange(start_ghz=1.0, stop_ghz=2.0, points=2),
    )

    result = asyncio.run(
        execute_simulation_run_async(
            request,
            execute=lambda _circuit, _freq_range, _config: _sample_result(),
        )
    )

    assert result.simulation_result.frequencies_ghz == [1.0, 2.0]
    assert [update.phase for update in result.progress_updates] == ["running", "completed"]
