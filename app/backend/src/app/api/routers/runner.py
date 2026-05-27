from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from src.app.domain.tasks import TaskDetail, TaskLifecycleUpdate, TaskListQuery
from src.app.infrastructure.request_debug import current_debug_ref
from src.app.infrastructure.runtime import (
    get_runner_result_publisher,
    get_task_service,
)
from src.app.services.runner_result_publisher import (
    RunnerPublicationResult,
    RunnerResultPublisher,
)
from src.app.services.service_errors import ServiceError
from src.app.services.task_service import TaskService
from src.app.settings import get_settings

router = APIRouter(prefix="/runner/v1/tasks", tags=["runner"])


@router.post("/claim")
def claim_task(
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        task = _next_claimable_task(task_service)
        if task is None:
            return _success_response(data={"task": None, "staging": None})
        claimed = task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task.task_id,
                status="claimed",
                progress_percent_complete=max(0, min(task.progress.percent_complete, 89)),
                progress_summary="Task claimed by Julia Runner.",
                progress_updated_at=_generated_at(),
            )
        )
        task_dir = _staging_task_dir(claimed.task_id)
        result_zarr = task_dir / "result.zarr"
        manifest = task_dir / "manifest.json"
        (task_dir / "logs").mkdir(parents=True, exist_ok=True)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "task": _build_runner_task_payload(claimed),
            "staging": {
                "mode": "local_filesystem",
                "task_dir": _display_path(task_dir),
                "result_zarr": _display_path(result_zarr),
                "manifest": _display_path(manifest),
            },
        }
    )


@router.post("/{task_id}/heartbeat")
def heartbeat_task(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        task = task_service.get_task(task_id)
        updated = task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task.task_id,
                status="running" if task.status == "claimed" else task.status,
                progress_percent_complete=max(1, min(task.progress.percent_complete, 99)),
                progress_summary=task.progress.summary or "Runner heartbeat received.",
                progress_updated_at=_generated_at(),
            )
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data={"task_id": updated.task_id, "status": updated.status})


@router.post("/{task_id}/progress")
def report_progress(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
    body: Annotated[Mapping[str, object] | None, Body()] = None,
) -> JSONResponse:
    try:
        payload = body or {}
        task = task_service.get_task(task_id)
        percent = int(payload.get("percent_complete", task.progress.percent_complete))
        summary = str(payload.get("summary") or task.progress.summary or "Runner progress.")
        updated = task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task.task_id,
                status="running",
                progress_percent_complete=max(1, min(percent, 99)),
                progress_summary=summary,
                progress_updated_at=_generated_at(),
            )
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data={"task_id": updated.task_id, "status": updated.status})


@router.get("/{task_id}/cancellation")
def get_cancellation(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> JSONResponse:
    try:
        task = task_service.get_task(task_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "task_id": task.task_id,
            "cancelled": task.status
            in {
                "cancellation_requested",
                "cancelling",
                "cancelled",
                "termination_requested",
                "terminated",
            },
        }
    )


@router.post("/{task_id}/complete")
def complete_task(
    task_id: int,
    publisher: Annotated[RunnerResultPublisher, Depends(get_runner_result_publisher)],
    body: Annotated[Mapping[str, object], Body()],
) -> JSONResponse:
    try:
        result = publisher.publish_complete_result(
            task_id=task_id,
            runner_id=str(body.get("runner_id") or "runner_local"),
            manifest_path=str(body.get("manifest_path") or ""),
            manifest_sha256=(
                str(body["manifest_sha256"])
                if isinstance(body.get("manifest_sha256"), str)
                else None
            ),
            output_target=(
                body.get("output_target")
                if isinstance(body.get("output_target"), Mapping)
                else None
            ),
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data={"publication": _build_publication_payload(result)})


@router.post("/{task_id}/fail")
def fail_task(
    task_id: int,
    task_service: Annotated[TaskService, Depends(get_task_service)],
    body: Annotated[Mapping[str, object], Body()],
) -> JSONResponse:
    try:
        message = str(body.get("message") or "Runner task failed.")
        updated = task_service.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task_id,
                status="failed",
                progress_percent_complete=100,
                progress_summary=message,
                progress_updated_at=_generated_at(),
                summary=message,
            )
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data={"task_id": updated.task_id, "status": updated.status})


def _next_claimable_task(task_service: TaskService) -> TaskDetail | None:
    tasks = task_service.list_tasks(
        TaskListQuery(
            status="queued",
            status_filter="all",
            scope="workspace",
            limit=50,
        )
    )
    if len(tasks) == 0:
        return None
    return tasks[0]


def _build_runner_task_payload(task: TaskDetail) -> dict[str, object]:
    return {
        "task_id": str(task.task_id),
        "task_kind": _runner_task_kind(task),
        "input": _runner_task_input(task),
        "output_target": {
            "dataset_id": task.dataset_id,
            "design_id": task.definition_id or f"design_task_{task.task_id}",
        },
    }


def _runner_task_kind(task: TaskDetail) -> str:
    if task.kind == "simulation":
        if task.simulation_setup is not None and len(task.simulation_setup.parameter_sweeps) > 0:
            return "julia_simulation_parameter_sweep"
        return "julia_runner_smoke"
    if task.kind == "post_processing":
        return "julia_postprocess_coordinate_transform"
    if task.kind == "characterization":
        return "julia_analysis_trace_summary"
    return str(task.kind)


def _runner_task_input(task: TaskDetail) -> dict[str, object]:
    if task.simulation_setup is not None:
        return {"simulation_setup": task.simulation_setup.to_mapping()}
    if task.post_processing_setup is not None:
        return {"post_processing_setup": task.post_processing_setup.to_mapping()}
    if task.characterization_setup is not None:
        return {"characterization_setup": task.characterization_setup.to_mapping()}
    return {}


def _build_publication_payload(result: RunnerPublicationResult) -> dict[str, object]:
    return {
        "task_id": result.task_id,
        "dataset_id": result.dataset_id,
        "design_id": result.design_id,
        "batch_id": result.batch_id,
        "store_key": result.store_key,
        "store_uri": result.store_uri,
        "manifest_artifact_path": result.manifest_artifact_path,
        "trace_ids": list(result.trace_ids),
    }


def _staging_task_dir(task_id: int) -> Path:
    settings = get_settings()
    staging_root = Path(settings.staging_root)
    if not staging_root.is_absolute():
        staging_root = _repo_root() / staging_root
    return staging_root / "tasks" / str(task_id)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(_repo_root()))
    except ValueError:
        return str(path)


def _success_response(
    *,
    data: dict[str, object],
    status_code: int = 200,
    meta: dict[str, object] | None = None,
) -> JSONResponse:
    content: dict[str, object] = {"ok": True, "data": data}
    if meta is not None:
        content["meta"] = meta
    return JSONResponse(status_code=status_code, content=content)


def _service_error_response(exc: ServiceError) -> JSONResponse:
    error: dict[str, object] = {
        "code": exc.code,
        "category": exc.category,
        "message": exc.message,
        "retryable": exc.category in {"internal_error", "persistence_error"},
        "debug_ref": current_debug_ref(),
    }
    details = dict(exc.details)
    if len(exc.field_errors) > 0:
        details["field_errors"] = [
            {"field": field_error.field, "message": field_error.message}
            for field_error in exc.field_errors
        ]
    if len(details) > 0:
        error["details"] = details
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": error})


def _generated_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
