"""Application-level execution service for Characterization analyses."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from functools import partial
from typing import Literal

from legacy.legacy_nicegui_archived.services.execution_context import UseCaseContext
from legacy.legacy_nicegui_archived.services.task_progress import (
    ProgressCallback,
    TaskProgressUpdate,
    emit_progress,
    progress_update,
)
from core.analysis.application.services.characterization_fitting_service import (
    CharacterizationFittingService,
    SquidFittingConfig,
    Y11FittingConfig,
)
from core.analysis.application.services.resonance_extract_service import ResonanceExtractService
from core.analysis.application.services.resonance_fit_service import ResonanceFitService
from core.analysis.domain import (
    NormalizedTraceRecord,
    normalize_trace_record,
)
from core.shared.persistence import get_unit_of_work
from core.shared.persistence.models import AnalysisRunRecord
from core.shared.persistence.unit_of_work import SqliteUnitOfWork


def _utcnow() -> datetime:
    """Return one naive UTC timestamp without using deprecated utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)


def invoke_sync_operation(
    operation: Callable[[], CharacterizationRunResult],
) -> CharacterizationRunResult:
    """Run one zero-arg sync operation for injected async executors."""
    return operation()


@dataclass(frozen=True)
class SweepSupportDiagnostic:
    """Support boundary for one analysis against selected parameter-sweep traces."""

    status: Literal["sweep-ready", "partial", "blocked"]
    reason: str


@dataclass(frozen=True)
class CharacterizationRunRequest:
    """Shared request contract for one characterization execution."""

    analysis_id: str
    dataset_id: int
    config_state: Mapping[str, str | float | int | None]
    analysis_label: str | None = None
    run_id: str = ""
    trace_record_ids: Sequence[int] | None = None
    selected_batch_ids: Sequence[int] = ()
    selected_scope_token: str = ""
    trace_mode_group: str | None = None
    summary_payload: Mapping[str, object] = field(default_factory=dict)
    context: UseCaseContext = field(default_factory=UseCaseContext)


@dataclass(frozen=True)
class CharacterizationRunResult:
    """Shared result contract for one characterization execution."""

    analysis_id: str
    dataset_id: int
    selected_trace_ids: tuple[int, ...]
    selected_batch_ids: tuple[int, ...]
    analysis_run: AnalysisRunRecord | None
    trace_mode_group: str
    sweep_support: SweepSupportDiagnostic | None
    context: UseCaseContext
    progress_updates: tuple[TaskProgressUpdate, ...] = ()


CharacterizationAsyncExecutor = Callable[
    [Callable[[], CharacterizationRunResult]],
    Awaitable[CharacterizationRunResult],
]


def _value_ndim(values: object) -> int:
    """Infer nested list dimensionality without loading numerical libraries."""
    if not isinstance(values, Sequence) or isinstance(values, str | bytes) or not values:
        return 1
    first = values[0]
    if isinstance(first, Sequence) and not isinstance(first, str | bytes):
        return 1 + _value_ndim(first)
    return 1


def _axis_name(record: NormalizedTraceRecord, index: int) -> str:
    if index >= len(record.axes):
        return ""
    return str(record.axes[index].get("name", "")).strip().lower()


def _axis_label(record: NormalizedTraceRecord, index: int) -> str:
    if index >= len(record.axes):
        return ""
    return str(record.axes[index].get("name", "")).strip()


def _is_l_jun_axis(name: str) -> bool:
    return name in {"l_jun", "l_ind"}


def _is_sweep_record(record: NormalizedTraceRecord) -> bool:
    shape = record.trace_shape()
    value_ndim = len(shape) if shape else _value_ndim(record.values)
    if value_ndim > 1:
        return True
    if len(record.axes) <= 1:
        return False
    return record.axis_length(1) > 1


def _load_selected_records(
    dataset_id: int,
    trace_record_ids: Sequence[int] | None,
) -> list[NormalizedTraceRecord]:
    with get_unit_of_work() as uow:
        records = [
            normalize_trace_record(record)
            for record in uow.data_records.list_by_dataset(dataset_id)
        ]
        if trace_record_ids is None:
            return records
        selected_ids = {int(record_id) for record_id in trace_record_ids}
        return [record for record in records if int(record.id or 0) in selected_ids]


def _selected_s21_records(records: Iterable[NormalizedTraceRecord]) -> list[NormalizedTraceRecord]:
    return [
        record
        for record in records
        if str(record.data_type) == "s_parameters"
        and str(record.parameter).strip().upper() == "S21"
    ]


def _diagnose_analysis_sweep_support_from_records(
    *,
    analysis_id: str,
    records: Sequence[NormalizedTraceRecord | object],
) -> SweepSupportDiagnostic | None:
    """Classify parameter-sweep support for one analysis against selected records."""
    normalized_records = [normalize_trace_record(record) for record in records]
    sweep_records = [record for record in normalized_records if _is_sweep_record(record)]
    if not sweep_records:
        return None

    max_ndim = max(
        len(record.trace_shape()) or _value_ndim(record.values) for record in sweep_records
    )
    second_axis_names = {_axis_name(record, 1) for record in sweep_records if len(record.axes) > 1}
    second_axis_labels = {
        _axis_label(record, 1)
        for record in sweep_records
        if len(record.axes) > 1 and _axis_label(record, 1)
    }
    has_non_l_jun_second_axis = any(
        axis_name and not _is_l_jun_axis(axis_name) for axis_name in second_axis_names
    )
    has_multiple_second_axes = len(second_axis_names) > 1

    if analysis_id == "admittance_extraction":
        if max_ndim > 2:
            return SweepSupportDiagnostic(
                status="blocked",
                reason="Admittance extraction supports up to 2D sweeps only.",
            )
        if has_multiple_second_axes:
            return SweepSupportDiagnostic(
                status="blocked",
                reason=(
                    "Admittance extraction supports one shared sweep axis across selected traces."
                ),
            )
        if second_axis_labels:
            sweep_axis_label = sorted(second_axis_labels)[0]
            return SweepSupportDiagnostic(
                status="sweep-ready",
                reason=(
                    f"2D Freq x {sweep_axis_label} sweeps are supported for admittance extraction."
                ),
            )
        return SweepSupportDiagnostic(
            status="sweep-ready",
            reason="2D admittance sweeps are supported.",
        )

    if analysis_id in {"y11_fit", "squid_fitting"}:
        if max_ndim > 2:
            return SweepSupportDiagnostic(
                status="blocked",
                reason="This fitting path supports up to 2D sweeps only.",
            )
        if has_non_l_jun_second_axis:
            return SweepSupportDiagnostic(
                status="blocked",
                reason="This fitting path requires a 2D Freq x L_jun sweep.",
            )
        return SweepSupportDiagnostic(
            status="sweep-ready",
            reason="2D Freq x L_jun sweeps are supported.",
        )

    if analysis_id == "s21_resonance_fit":
        s21_sweep_records = [
            record
            for record in _selected_s21_records(normalized_records)
            if _is_sweep_record(record)
        ]
        if not s21_sweep_records:
            return None

        s21_max_ndim = max(
            len(record.trace_shape()) or _value_ndim(record.values) for record in s21_sweep_records
        )
        if s21_max_ndim > 2:
            return SweepSupportDiagnostic(
                status="blocked",
                reason="S21 resonance fitting supports at most one sweep axis.",
            )
        s21_second_axis_names = {
            _axis_name(record, 1) for record in s21_sweep_records if len(record.axes) > 1
        }
        if s21_second_axis_names and all(_is_l_jun_axis(name) for name in s21_second_axis_names):
            return SweepSupportDiagnostic(
                status="sweep-ready",
                reason=("2D Freq x L_jun sweeps persist per-slice bias and render Mode vs L_jun."),
            )
        return SweepSupportDiagnostic(
            status="partial",
            reason=(
                "Single-axis 2D sweeps run per slice, but only L_jun sweeps get the canonical "
                "Mode vs L_jun artifact."
            ),
        )

    return None


def diagnose_analysis_sweep_support(
    *,
    analysis_id: str,
    dataset_id: int,
    trace_record_ids: Sequence[int] | None,
) -> SweepSupportDiagnostic | None:
    """Load selected traces and classify parameter-sweep support for one analysis."""
    records = _load_selected_records(dataset_id, trace_record_ids)
    return _diagnose_analysis_sweep_support_from_records(
        analysis_id=analysis_id,
        records=records,
    )


def _config_int(
    config_state: Mapping[str, str | float | int | None],
    name: str,
    default: int,
) -> int:
    value = config_state.get(name)
    if value is None:
        return default
    return int(value)


def _config_float(config_state: Mapping[str, str | float | int | None], name: str) -> float | None:
    value = config_state.get(name)
    if value is None:
        return None
    return float(value)


def _config_str(
    config_state: Mapping[str, str | float | int | None],
    name: str,
    default: str,
) -> str:
    value = config_state.get(name)
    if value is None:
        return default
    return str(value)


def _build_analysis_run_record(
    request: CharacterizationRunRequest,
    *,
    selected_trace_ids: Sequence[int],
    status: str = "completed",
    analysis_run_id: int | None = None,
    completed_at: datetime | None = None,
    summary_payload: Mapping[str, object] | None = None,
) -> AnalysisRunRecord:
    """Build one logical analysis-run record for Characterization persistence."""
    normalized_config_payload: dict[str, object] = dict(request.config_state)
    normalized_config_payload.setdefault(
        "selected_trace_ids",
        [int(trace_id) for trace_id in selected_trace_ids],
    )
    normalized_config_payload.setdefault(
        "selected_trace_count",
        len([int(trace_id) for trace_id in selected_trace_ids]),
    )
    normalized_config_payload.setdefault(
        "selected_trace_mode_group",
        str(request.trace_mode_group or ""),
    )
    normalized_summary_payload = dict(summary_payload or request.summary_payload)
    normalized_summary_payload.setdefault(
        "selected_trace_count",
        len([int(trace_id) for trace_id in selected_trace_ids]),
    )
    normalized_summary_payload.setdefault(
        "selected_trace_mode_group",
        str(request.trace_mode_group or ""),
    )
    return AnalysisRunRecord(
        id=analysis_run_id,
        design_id=request.dataset_id,
        analysis_id=request.analysis_id,
        analysis_label=str(request.analysis_label or request.analysis_id),
        run_id=str(request.run_id),
        status=status,
        input_trace_ids=[int(trace_id) for trace_id in selected_trace_ids],
        input_batch_ids=[int(batch_id) for batch_id in request.selected_batch_ids],
        input_scope=str(request.selected_scope_token),
        trace_mode_group=str(request.trace_mode_group or ""),
        config_payload=normalized_config_payload,
        summary_payload=normalized_summary_payload,
        completed_at=completed_at,
    )


def _persist_analysis_run_record(
    analysis_run: AnalysisRunRecord,
    *,
    uow: SqliteUnitOfWork | None = None,
) -> AnalysisRunRecord:
    """Persist one logical analysis run through the shared boundary."""
    if uow is not None:
        return uow.result_bundles.analysis_runs.save(analysis_run)
    with get_unit_of_work() as local_uow:
        persisted_run = local_uow.result_bundles.analysis_runs.save(analysis_run)
        local_uow.commit()
        return persisted_run


def create_pending_analysis_run(
    request: CharacterizationRunRequest,
    *,
    selected_trace_ids: Sequence[int] | None = None,
    uow: SqliteUnitOfWork | None = None,
) -> AnalysisRunRecord:
    """Create one queued logical analysis run before worker dispatch."""
    trace_ids = tuple(
        int(trace_id) for trace_id in (selected_trace_ids or request.trace_record_ids or ())
    )
    return _persist_analysis_run_record(
        _build_analysis_run_record(
            request,
            selected_trace_ids=trace_ids,
            status="queued",
            summary_payload={
                **dict(request.summary_payload),
                "phase": "queued",
                "selected_trace_count": len(trace_ids),
            },
        ),
        uow=uow,
    )


def save_analysis_run_status(
    request: CharacterizationRunRequest,
    *,
    analysis_run_id: int | None,
    selected_trace_ids: Sequence[int],
    status: str,
    summary_payload: Mapping[str, object] | None = None,
    completed_at: datetime | None = None,
    uow: SqliteUnitOfWork | None = None,
) -> AnalysisRunRecord:
    """Update one logical analysis run to the requested persisted status."""
    return _persist_analysis_run_record(
        _build_analysis_run_record(
            request,
            selected_trace_ids=selected_trace_ids,
            status=status,
            analysis_run_id=analysis_run_id,
            completed_at=completed_at,
            summary_payload=summary_payload,
        ),
        uow=uow,
    )


def execute_characterization_run(
    request: CharacterizationRunRequest,
    *,
    progress_callback: ProgressCallback | None = None,
    persist_analysis_run: bool = True,
    analysis_run_id: int | None = None,
) -> CharacterizationRunResult:
    """Execute one characterization analysis run through the shared boundary."""
    trace_ids = list(request.trace_record_ids) if request.trace_record_ids is not None else None
    sweep_support = diagnose_analysis_sweep_support(
        analysis_id=request.analysis_id,
        dataset_id=request.dataset_id,
        trace_record_ids=trace_ids,
    )
    if sweep_support is not None and sweep_support.status == "blocked":
        raise ValueError(f"Sweep support: blocked - {sweep_support.reason}")
    updates: list[TaskProgressUpdate] = []
    selected_trace_ids = tuple(trace_ids or [])
    selected_batch_ids = tuple(int(batch_id) for batch_id in request.selected_batch_ids)
    updates.append(
        emit_progress(
            progress_callback,
            progress_update(
                phase="running",
                summary="Characterization execution started.",
                stage_label="characterization",
                stale_after_seconds=60,
                details={
                    "source": request.context.source,
                    "requested_by": request.context.requested_by,
                    "analysis_id": request.analysis_id,
                    "selected_trace_count": len(selected_trace_ids),
                },
            ),
        )
    )

    if request.analysis_id == "admittance_extraction":
        ResonanceExtractService().extract_admittance(
            str(request.dataset_id),
            record_ids=trace_ids,
            trace_mode_group=request.trace_mode_group,
        )
    elif request.analysis_id == "s21_resonance_fit":
        ResonanceFitService().perform_fit(
            dataset_identifier=str(request.dataset_id),
            parameter="S21",
            model=_config_str(request.config_state, "model", "notch"),
            resonators=_config_int(request.config_state, "resonators", 1),
            f_min=_config_float(request.config_state, "f_min"),
            f_max=_config_float(request.config_state, "f_max"),
            record_ids=trace_ids,
        )
    elif request.analysis_id == "squid_fitting":
        CharacterizationFittingService().run_squid_fitting(
            dataset_id=request.dataset_id,
            config=SquidFittingConfig(
                fit_model=_config_str(request.config_state, "fit_model", "WITH_LS"),
                ls_min_nh=_config_float(request.config_state, "ls_min_nh"),
                ls_max_nh=_config_float(request.config_state, "ls_max_nh"),
                c_min_pf=_config_float(request.config_state, "c_min_pf"),
                c_max_pf=_config_float(request.config_state, "c_max_pf"),
                fixed_c_pf=_config_float(request.config_state, "fixed_c_pf"),
                fit_min_nh=_config_float(request.config_state, "fit_min_nh"),
                fit_max_nh=_config_float(request.config_state, "fit_max_nh"),
            ),
            record_ids=trace_ids,
            trace_mode_group=request.trace_mode_group,
        )
    elif request.analysis_id == "y11_fit":
        CharacterizationFittingService().run_y11_fitting(
            dataset_id=request.dataset_id,
            config=Y11FittingConfig(
                ls1_init_nh=float(_config_float(request.config_state, "ls1_init_nh") or 0.01),
                ls2_init_nh=float(_config_float(request.config_state, "ls2_init_nh") or 0.01),
                c_init_pf=float(_config_float(request.config_state, "c_init_pf") or 0.885),
                c_max_pf=float(_config_float(request.config_state, "c_max_pf") or 3.0),
            ),
            record_ids=trace_ids,
            trace_mode_group=request.trace_mode_group,
        )
    else:
        raise ValueError(f"Unsupported analysis id: {request.analysis_id}")

    persisted_analysis_run = None
    if persist_analysis_run:
        completed_summary_payload = {
            **dict(request.summary_payload),
            "selected_trace_count": len(selected_trace_ids),
            "selected_trace_mode_group": str(request.trace_mode_group or ""),
        }
        persisted_analysis_run = save_analysis_run_status(
            request,
            analysis_run_id=analysis_run_id,
            selected_trace_ids=selected_trace_ids,
            status="completed",
            summary_payload=completed_summary_payload,
            completed_at=_utcnow(),
        )
    else:
        persisted_analysis_run = _build_analysis_run_record(
            request,
            selected_trace_ids=selected_trace_ids,
            status="completed",
            analysis_run_id=analysis_run_id,
            completed_at=_utcnow(),
            summary_payload={
                **dict(request.summary_payload),
                "selected_trace_count": len(selected_trace_ids),
                "selected_trace_mode_group": str(request.trace_mode_group or ""),
            },
        )
    updates.append(
        emit_progress(
            progress_callback,
            progress_update(
                phase="persisted",
                summary=f"Recorded analysis run #{persisted_analysis_run.id}.",
                stage_label="characterization",
                details={
                    "analysis_run_id": persisted_analysis_run.id,
                    "analysis_id": request.analysis_id,
                    "run_id": str(request.run_id),
                },
            ),
        )
    )

    updates.append(
        emit_progress(
            progress_callback,
            progress_update(
                phase="completed",
                summary=f"{request.analysis_label or request.analysis_id} completed.",
                stage_label="characterization",
                details={
                    "source": request.context.source,
                    "requested_by": request.context.requested_by,
                    "analysis_id": request.analysis_id,
                    "selected_trace_count": len(selected_trace_ids),
                    "trace_mode_group": str(request.trace_mode_group or ""),
                    "analysis_run_id": persisted_analysis_run.id,
                },
            ),
        )
    )
    return CharacterizationRunResult(
        analysis_id=request.analysis_id,
        dataset_id=request.dataset_id,
        selected_trace_ids=selected_trace_ids,
        selected_batch_ids=selected_batch_ids,
        analysis_run=persisted_analysis_run,
        trace_mode_group=str(request.trace_mode_group or ""),
        sweep_support=sweep_support,
        context=request.context,
        progress_updates=tuple(updates),
    )


async def execute_characterization_run_async(
    request: CharacterizationRunRequest,
    *,
    executor: CharacterizationAsyncExecutor | None = None,
    progress_callback: ProgressCallback | None = None,
    heartbeat_interval_seconds: float = 5.0,
    long_running_warning_after_seconds: float = 60.0,
    persist_analysis_run: bool = True,
    analysis_run_id: int | None = None,
) -> CharacterizationRunResult:
    """Async adapter for the shared characterization boundary."""
    updates: list[TaskProgressUpdate] = []

    def _record_progress(update: TaskProgressUpdate) -> None:
        updates.append(update)
        if progress_callback is not None:
            progress_callback(update)

    operation = partial(
        execute_characterization_run,
        request,
        progress_callback=_record_progress,
        persist_analysis_run=persist_analysis_run,
        analysis_run_id=analysis_run_id,
    )
    if executor is None:
        task = asyncio.create_task(asyncio.to_thread(operation))
    else:

        async def _run_with_executor() -> CharacterizationRunResult:
            return await executor(partial(invoke_sync_operation, operation))

        task = asyncio.create_task(_run_with_executor())

    started_at = _utcnow()
    warning_emitted = False
    while True:
        try:
            result = await asyncio.wait_for(
                asyncio.shield(task),
                timeout=heartbeat_interval_seconds,
            )
            combined_updates = list(updates)
            for update in result.progress_updates:
                if update not in combined_updates:
                    combined_updates.append(update)
            return replace(result, progress_updates=tuple(combined_updates))
        except TimeoutError:
            elapsed_seconds = max(1, int((_utcnow() - started_at).total_seconds()))
            _record_progress(
                progress_update(
                    phase="heartbeat",
                    summary=f"Analysis worker still running... {elapsed_seconds}s elapsed.",
                    stage_label="characterization",
                    stale_after_seconds=int(long_running_warning_after_seconds),
                    details={
                        "analysis_id": request.analysis_id,
                        "elapsed_seconds": elapsed_seconds,
                    },
                )
            )
            if not warning_emitted and elapsed_seconds >= int(long_running_warning_after_seconds):
                warning_emitted = True
                _record_progress(
                    progress_update(
                        phase="warning",
                        summary=(
                            "Long-running analysis detected; worker heartbeat continues every 5s."
                        ),
                        stage_label="characterization",
                        warning="long_running_analysis",
                        stale_after_seconds=int(long_running_warning_after_seconds),
                        details={
                            "analysis_id": request.analysis_id,
                            "elapsed_seconds": elapsed_seconds,
                        },
                    )
                )


def execute_analysis_run(
    *,
    analysis_id: str,
    dataset_id: int,
    config_state: Mapping[str, str | float | int | None],
    trace_record_ids: Sequence[int] | None = None,
    trace_mode_group: str | None = None,
) -> None:
    """Backward-compatible wrapper for the shared characterization boundary."""
    execute_characterization_run(
        CharacterizationRunRequest(
            analysis_id=analysis_id,
            dataset_id=dataset_id,
            config_state=config_state,
            trace_record_ids=trace_record_ids,
            trace_mode_group=trace_mode_group,
            analysis_label=analysis_id,
        )
    )


__all__ = [
    "CharacterizationRunRequest",
    "CharacterizationRunResult",
    "SweepSupportDiagnostic",
    "_diagnose_analysis_sweep_support_from_records",
    "create_pending_analysis_run",
    "diagnose_analysis_sweep_support",
    "execute_analysis_run",
    "execute_characterization_run",
    "execute_characterization_run_async",
    "invoke_sync_operation",
    "save_analysis_run_status",
]
