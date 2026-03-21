"""Shared simulation execution boundary for UI, worker, and future CLI/API callers."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field

from legacy.legacy_nicegui_archived.services.execution_context import UseCaseContext
from legacy.legacy_nicegui_archived.services.task_progress import (
    ProgressCallback,
    TaskProgressUpdate,
    emit_progress,
    progress_update,
)
from core.simulation.application.run_simulation import run_simulation
from core.simulation.domain.circuit import (
    CircuitDefinition,
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
)

_SIMULATION_STALE_AFTER_SECONDS = 60
SimulationExecutor = Callable[
    [CircuitDefinition, FrequencyRange, SimulationConfig | None],
    SimulationResult,
]


@dataclass(frozen=True)
class SimulationRunRequest:
    """Shared request contract for one simulation execution."""

    circuit: CircuitDefinition
    freq_range: FrequencyRange
    config: SimulationConfig | None = None
    context: UseCaseContext = field(default_factory=UseCaseContext)
    stage_label: str = "simulation"


@dataclass(frozen=True)
class SimulationRunResult:
    """Shared result contract for one simulation execution."""

    simulation_result: SimulationResult
    context: UseCaseContext
    progress_updates: tuple[TaskProgressUpdate, ...] = ()

    @property
    def result(self) -> SimulationResult:
        """Backward-compatible alias for callers that expect `result`."""
        return self.simulation_result


def execute_simulation_run(
    request: SimulationRunRequest,
    *,
    progress_callback: ProgressCallback | None = None,
    execute: SimulationExecutor | None = None,
) -> SimulationRunResult:
    """Execute one simulation run through a shared application boundary."""
    updates: list[TaskProgressUpdate] = []
    updates.append(
        emit_progress(
            progress_callback,
            progress_update(
                phase="running",
                summary="Simulation execution started.",
                stage_label=request.stage_label,
                stale_after_seconds=_SIMULATION_STALE_AFTER_SECONDS,
                details={
                    "source": request.context.source,
                    "requested_by": request.context.requested_by,
                },
            ),
        )
    )
    simulation_result = (execute or run_simulation)(
        request.circuit,
        request.freq_range,
        request.config,
    )
    updates.append(
        emit_progress(
            progress_callback,
            progress_update(
                phase="completed",
                summary="Simulation execution completed.",
                stage_label=request.stage_label,
                details={
                    "source": request.context.source,
                    "requested_by": request.context.requested_by,
                    "frequency_points": len(simulation_result.frequencies_ghz),
                    "port_count": len(simulation_result.port_indices),
                },
            ),
        )
    )
    return SimulationRunResult(
        simulation_result=simulation_result,
        context=request.context,
        progress_updates=tuple(updates),
    )


async def execute_simulation_run_async(
    request: SimulationRunRequest,
    *,
    progress_callback: ProgressCallback | None = None,
    execute: SimulationExecutor | None = None,
) -> SimulationRunResult:
    """Async adapter for the shared simulation boundary."""
    return await asyncio.to_thread(
        execute_simulation_run,
        request,
        progress_callback=progress_callback,
        execute=execute,
    )
