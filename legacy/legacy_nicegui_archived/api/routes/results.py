"""`/api/v1/designs/*/latest` routes for persisted artifact lookup."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from legacy.legacy_nicegui_archived.api.dependencies import current_user
from legacy.legacy_nicegui_archived.api.schemas import (
    LatestCharacterizationResponse,
    LatestTraceBatchResponse,
)
from legacy.legacy_nicegui_archived.services.latest_result_lookup import (
    latest_characterization_result,
    latest_post_processing_result,
    latest_simulation_result,
)

router = APIRouter(tags=["results"])


@router.get("/designs/{design_id}/simulation/latest", response_model=LatestTraceBatchResponse)
def get_latest_simulation_result(design_id: int, request: Request) -> LatestTraceBatchResponse:
    """Return the newest completed raw simulation artifact."""
    _actor = current_user(request)
    artifact = latest_simulation_result(design_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed simulation result found for design {design_id}",
        )
    batch = artifact.batch
    return LatestTraceBatchResponse(
        batch_id=int(batch["id"]),
        design_id=int(batch["design_id"]),
        source_kind=str(batch["source_kind"]),
        stage_kind=str(batch["stage_kind"]),
        status=str(batch["status"]),
        parent_batch_id=batch["parent_batch_id"],
        setup_kind=batch["setup_kind"],
        setup_version=batch["setup_version"],
        provenance_payload=dict(batch["provenance_payload"]),
        summary_payload=dict(batch["summary_payload"]),
        task_id=int(artifact.task.id) if artifact.task is not None and artifact.task.id else None,
    )


@router.get("/designs/{design_id}/post-processing/latest", response_model=LatestTraceBatchResponse)
def get_latest_post_processing_result(
    design_id: int,
    request: Request,
) -> LatestTraceBatchResponse:
    """Return the newest completed post-processing artifact."""
    _actor = current_user(request)
    artifact = latest_post_processing_result(design_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed post-processing result found for design {design_id}",
        )
    batch = artifact.batch
    return LatestTraceBatchResponse(
        batch_id=int(batch["id"]),
        design_id=int(batch["design_id"]),
        source_kind=str(batch["source_kind"]),
        stage_kind=str(batch["stage_kind"]),
        status=str(batch["status"]),
        parent_batch_id=batch["parent_batch_id"],
        setup_kind=batch["setup_kind"],
        setup_version=batch["setup_version"],
        provenance_payload=dict(batch["provenance_payload"]),
        summary_payload=dict(batch["summary_payload"]),
        task_id=int(artifact.task.id) if artifact.task is not None and artifact.task.id else None,
    )


@router.get(
    "/designs/{design_id}/characterization/latest",
    response_model=LatestCharacterizationResponse,
)
def get_latest_characterization_result(
    design_id: int,
    request: Request,
) -> LatestCharacterizationResponse:
    """Return the newest persisted characterization run."""
    _actor = current_user(request)
    artifact = latest_characterization_result(design_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No completed characterization result found for design {design_id}",
        )
    run = artifact.analysis_run
    if run.id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Persisted analysis run is missing an ID",
        )
    return LatestCharacterizationResponse(
        analysis_run_id=int(run.id),
        design_id=int(run.design_id),
        analysis_id=str(run.analysis_id),
        analysis_label=str(run.analysis_label),
        run_id=str(run.run_id),
        status=str(run.status),
        input_trace_ids=[int(trace_id) for trace_id in run.input_trace_ids],
        input_batch_ids=[int(batch_id) for batch_id in run.input_batch_ids],
        input_scope=str(run.input_scope),
        trace_mode_group=str(run.trace_mode_group),
        config_payload=dict(run.config_payload),
        summary_payload=dict(run.summary_payload),
        created_at=run.created_at,
        completed_at=run.completed_at,
        task_id=int(artifact.task.id) if artifact.task is not None and artifact.task.id else None,
    )
