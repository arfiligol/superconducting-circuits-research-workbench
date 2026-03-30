from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse

from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryQuery,
    CharacterizationArtifactPayloadQuery,
    CharacterizationResultBrowseQuery,
    CharacterizationRunHistoryQuery,
    CharacterizationTaggingRequest,
    DatasetCreateDraft,
    DatasetDetail,
    DatasetProfileUpdate,
    DesignBrowseQuery,
    DesignCreateDraft,
    RawDataIngestionDraft,
    RawDataTraceDraft,
    TraceAxis,
    TraceBrowseQuery,
    TraceUpdateDraft,
)
from src.app.infrastructure.request_debug import current_debug_ref
from src.app.infrastructure.runtime import get_dataset_service
from src.app.services.dataset_service import DatasetService
from src.app.services.service_errors import ServiceError, service_error

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
def list_dataset_catalog(
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    limit: Annotated[str | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        resolved_limit = _parse_limit(limit)
        rows = [asdict(row) for row in dataset_service.list_dataset_catalog()]
    except ServiceError as exc:
        return _service_error_response(exc)

    page_rows, meta = _paginate_rows(
        rows,
        limit=resolved_limit,
        cursor=cursor,
        filter_echo={},
    )
    return _success_response(data={"rows": page_rows}, meta=meta)


@router.post("")
def create_dataset(
    payload: Annotated[object, Body(...)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        draft = _parse_dataset_create_payload(payload)
        result = dataset_service.create_dataset(draft)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "created",
            "dataset": _serialize_dataset_profile(result.dataset),
            "catalog_row": _serialize_catalog_row(result.catalog_row),
            "catalog_rows": [
                _serialize_catalog_row(row) for row in dataset_service.list_dataset_catalog()
            ],
        },
        status_code=201,
        meta={"generated_at": _generated_at()},
    )


@router.get("/{dataset_id}/profile")
def get_dataset_profile(
    dataset_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        detail = dataset_service.get_dataset_profile(dataset_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data=_serialize_dataset_profile(detail))


@router.patch("/{dataset_id}/profile")
def update_dataset_profile(
    dataset_id: str,
    payload: Annotated[object, Body(...)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        update = _parse_dataset_profile_payload(payload)
        result = dataset_service.update_dataset_profile(dataset_id, update)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "dataset": _serialize_dataset_profile(result.dataset),
            "updated_fields": list(result.updated_fields),
        }
    )


@router.post("/{dataset_id}/archive")
def archive_dataset(
    dataset_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        result = dataset_service.archive_dataset(dataset_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "archived",
            "dataset": _serialize_dataset_profile(result.dataset),
            "catalog_row": _serialize_catalog_row(result.catalog_row),
            "catalog_rows": [
                _serialize_catalog_row(row) for row in dataset_service.list_dataset_catalog()
            ],
        },
        meta={"generated_at": _generated_at()},
    )


@router.delete("/{dataset_id}")
def delete_dataset(
    dataset_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        result = dataset_service.delete_dataset(dataset_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "deleted",
            "dataset": _serialize_dataset_profile(result.dataset),
            "catalog_row": _serialize_catalog_row(result.catalog_row),
            "catalog_rows": [
                _serialize_catalog_row(row) for row in dataset_service.list_dataset_catalog()
            ],
        },
        meta={"generated_at": _generated_at()},
    )


@router.post("/{dataset_id}/ingestions")
def ingest_raw_data(
    dataset_id: str,
    payload: Annotated[object, Body(...)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        draft = _parse_raw_data_ingestion_payload(payload)
        result = dataset_service.ingest_raw_data(dataset_id, draft)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "materialized",
            "dataset": _serialize_dataset_profile(result.dataset),
            "design": asdict(result.design),
            "traces": [asdict(trace) for trace in result.traces],
        },
        meta={"generated_at": _generated_at()},
    )


@router.get("/{dataset_id}/metrics-summary")
def list_tagged_core_metrics(
    dataset_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        rows = [asdict(row) for row in dataset_service.list_tagged_core_metrics(dataset_id)]
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data={"rows": rows})


@router.get("/{dataset_id}/designs")
def list_designs(
    dataset_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    limit: Annotated[str | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        resolved_limit = _parse_limit(limit)
        rows = [
            asdict(row)
            for row in dataset_service.list_designs(
                dataset_id,
                DesignBrowseQuery(search=_normalize_optional_text(search)),
            )
        ]
    except ServiceError as exc:
        return _service_error_response(exc)

    page_rows, meta = _paginate_rows(
        rows,
        limit=resolved_limit,
        cursor=cursor,
        filter_echo={
            "dataset_id": dataset_id,
            "search": _normalize_optional_text(search),
        },
    )
    return _success_response(data={"rows": page_rows}, meta=meta)


@router.post("/{dataset_id}/designs")
def create_design(
    dataset_id: str,
    payload: Annotated[object, Body(...)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        draft = _parse_design_create_payload(payload)
        result = dataset_service.create_design(dataset_id, draft)
        design_rows = [
            _serialize_design_browse_row(row)
            for row in dataset_service.list_designs(dataset_id, DesignBrowseQuery())
        ]
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "created",
            "dataset": _serialize_dataset_profile(result.dataset),
            "design": _serialize_design_browse_row(result.design),
            "design_rows": design_rows,
        },
        status_code=201,
        meta={"generated_at": _generated_at()},
    )


@router.get("/{dataset_id}/designs/{design_id}/traces")
def list_trace_metadata(
    dataset_id: str,
    design_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    limit: Annotated[str | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    family: Annotated[str | None, Query()] = None,
    representation: Annotated[str | None, Query()] = None,
    source_kind: Annotated[str | None, Query()] = None,
    trace_mode_group: Annotated[str | None, Query()] = None,
    axis_name: Annotated[str | None, Query()] = None,
    collection_key: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        resolved_limit = _parse_limit(limit)
        rows = [
            _serialize_trace_browse_row(row)
            for row in dataset_service.list_trace_metadata(
                dataset_id,
                design_id,
                TraceBrowseQuery(
                    search=_normalize_optional_text(search),
                    family=_normalize_family(family),
                    representation=_normalize_optional_text(representation),
                    source_kind=_normalize_source_kind(source_kind),
                    trace_mode_group=_normalize_trace_mode_group(trace_mode_group),
                    axis_name=_normalize_optional_text(axis_name),
                    collection_key=_normalize_optional_text(collection_key),
                ),
            )
        ]
    except ServiceError as exc:
        return _service_error_response(exc)

    page_rows, meta = _paginate_rows(
        rows,
        limit=resolved_limit,
        cursor=cursor,
        filter_echo={
            "dataset_id": dataset_id,
            "design_id": design_id,
            "search": _normalize_optional_text(search),
            "family": _normalize_family(family),
            "representation": _normalize_optional_text(representation),
            "source_kind": _normalize_source_kind(source_kind),
            "trace_mode_group": _normalize_trace_mode_group(trace_mode_group),
            "axis_name": _normalize_optional_text(axis_name),
            "collection_key": _normalize_optional_text(collection_key),
        },
    )
    return _success_response(data={"rows": page_rows}, meta=meta)


@router.get("/{dataset_id}/designs/{design_id}/traces/{trace_id}")
def get_trace_detail(
    dataset_id: str,
    design_id: str,
    trace_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        detail = dataset_service.get_trace_detail(dataset_id, design_id, trace_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data=_serialize_trace_detail(detail))


@router.get("/{dataset_id}/designs/{design_id}/traces/{trace_id}/edit")
def get_trace_edit_detail(
    dataset_id: str,
    design_id: str,
    trace_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        detail = dataset_service.get_trace_edit_detail(dataset_id, design_id, trace_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data=_serialize_trace_edit_detail(detail))


@router.patch("/{dataset_id}/designs/{design_id}/traces/{trace_id}")
def update_trace(
    dataset_id: str,
    design_id: str,
    trace_id: str,
    payload: Annotated[object, Body(...)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        update = _parse_trace_update_payload(payload)
        result = dataset_service.update_trace(dataset_id, design_id, trace_id, update)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "updated",
            "trace": _serialize_trace_browse_row(result.trace),
        }
    )


@router.delete("/{dataset_id}/designs/{design_id}/traces/{trace_id}")
def delete_trace(
    dataset_id: str,
    design_id: str,
    trace_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        result = dataset_service.delete_trace(dataset_id, design_id, trace_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "deleted",
            "deleted_trace_id": trace_id,
            "deleted_count": len(result.deleted_trace_ids),
            "design": _serialize_design_browse_row(result.design),
        }
    )


@router.post("/{dataset_id}/designs/{design_id}/traces/batch-delete")
def batch_delete_traces(
    dataset_id: str,
    design_id: str,
    payload: Annotated[object, Body(...)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        trace_ids = _parse_trace_batch_delete_payload(payload)
        result = dataset_service.delete_traces(dataset_id, design_id, trace_ids)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "operation": "deleted",
            "deleted_trace_ids": list(result.deleted_trace_ids),
            "deleted_count": len(result.deleted_trace_ids),
            "design": _serialize_design_browse_row(result.design),
        }
    )


@router.get("/{dataset_id}/designs/{design_id}/characterization-results")
def list_characterization_results(
    dataset_id: str,
    design_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    limit: Annotated[str | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    analysis_id: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        resolved_limit = _parse_limit(limit)
        rows = [
            asdict(row)
            for row in dataset_service.list_characterization_results(
                dataset_id,
                design_id,
                CharacterizationResultBrowseQuery(
                    search=_normalize_optional_text(search),
                    status=_normalize_characterization_result_status(status),
                    analysis_id=_normalize_optional_text(analysis_id),
                ),
            )
        ]
    except ServiceError as exc:
        return _service_error_response(exc)

    page_rows, meta = _paginate_rows(
        rows,
        limit=resolved_limit,
        cursor=cursor,
        filter_echo={
            "dataset_id": dataset_id,
            "design_id": design_id,
            "search": _normalize_optional_text(search),
            "status": _normalize_characterization_result_status(status),
            "analysis_id": _normalize_optional_text(analysis_id),
        },
    )
    return _success_response(data={"rows": page_rows}, meta=meta)


@router.get("/{dataset_id}/designs/{design_id}/characterization-analysis-registry")
def list_characterization_analysis_registry(
    dataset_id: str,
    design_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    selected_trace_ids: Annotated[list[str] | None, Query()] = None,
) -> JSONResponse:
    try:
        result = dataset_service.list_characterization_analysis_registry(
            dataset_id,
            design_id,
            CharacterizationAnalysisRegistryQuery(
                selected_trace_ids=_normalize_trace_ids(selected_trace_ids),
            ),
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "rows": [asdict(row) for row in result.rows],
            "input_collection_payload": (
                asdict(result.input_collection_payload)
                if result.input_collection_payload is not None
                else None
            ),
        },
        meta={
            "generated_at": _generated_at(),
            "filter_echo": {
                "dataset_id": dataset_id,
                "design_id": design_id,
                "selected_trace_ids": list(_normalize_trace_ids(selected_trace_ids)),
            },
        },
    )


@router.get("/{dataset_id}/designs/{design_id}/characterization-run-history")
def list_characterization_run_history(
    dataset_id: str,
    design_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    limit: Annotated[str | None, Query()] = None,
    cursor: Annotated[str | None, Query()] = None,
    analysis_id: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        resolved_limit = _parse_limit(limit)
        rows = [
            asdict(row)
            for row in dataset_service.list_characterization_run_history(
                dataset_id,
                design_id,
                CharacterizationRunHistoryQuery(
                    analysis_id=_normalize_optional_text(analysis_id),
                ),
            )
        ]
    except ServiceError as exc:
        return _service_error_response(exc)

    page_rows, meta = _paginate_rows(
        rows,
        limit=resolved_limit,
        cursor=cursor,
        filter_echo={
            "dataset_id": dataset_id,
            "design_id": design_id,
            "analysis_id": _normalize_optional_text(analysis_id),
        },
    )
    return _success_response(data={"rows": page_rows}, meta=meta)


@router.get("/{dataset_id}/designs/{design_id}/characterization-results/{result_id}")
def get_characterization_result(
    dataset_id: str,
    design_id: str,
    result_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        detail = dataset_service.get_characterization_result(dataset_id, design_id, result_id)
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "result_id": detail.result_id,
            "dataset_id": detail.dataset_id,
            "design_id": detail.design_id,
            "analysis_id": detail.analysis_id,
            "title": detail.title,
            "status": detail.status,
            "freshness_summary": detail.freshness_summary,
            "provenance_summary": detail.provenance_summary,
            "trace_count": detail.trace_count,
            "updated_at": detail.updated_at,
            "input_trace_ids": list(detail.input_trace_ids),
            "payload": detail.payload,
            "diagnostics": [asdict(diagnostic) for diagnostic in detail.diagnostics],
            "artifact_refs": [asdict(artifact_ref) for artifact_ref in detail.artifact_refs],
            "identify_surface": {
                "source_parameters": [
                    asdict(source_parameter)
                    for source_parameter in detail.identify_surface.source_parameters
                ],
                "designated_metrics": [
                    asdict(metric_option)
                    for metric_option in detail.identify_surface.designated_metrics
                ],
                "applied_tags": [
                    asdict(applied_tag) for applied_tag in detail.identify_surface.applied_tags
                ],
            },
        }
    )


@router.get(
    "/{dataset_id}/designs/{design_id}/characterization-results/{result_id}/artifacts/{artifact_id}"
)
def get_characterization_artifact_payload(
    dataset_id: str,
    design_id: str,
    result_id: str,
    artifact_id: str,
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
    preset_id: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        payload = dataset_service.get_characterization_artifact_payload(
            dataset_id,
            design_id,
            result_id,
            artifact_id,
            CharacterizationArtifactPayloadQuery(
                preset_id=_normalize_optional_text(preset_id),
            ),
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(data=asdict(payload))


@router.post("/{dataset_id}/designs/{design_id}/characterization-results/{result_id}/taggings")
def apply_characterization_tagging(
    dataset_id: str,
    design_id: str,
    result_id: str,
    payload: Annotated[object, Body(...)],
    dataset_service: Annotated[DatasetService, Depends(get_dataset_service)],
) -> JSONResponse:
    try:
        request = _parse_characterization_tagging_payload(payload)
        result = dataset_service.apply_characterization_tagging(
            dataset_id,
            design_id,
            result_id,
            request,
        )
    except ServiceError as exc:
        return _service_error_response(exc)
    return _success_response(
        data={
            "tagging_status": result.tagging_status,
            "dataset_id": result.dataset_id,
            "design_id": result.design_id,
            "result_id": result.result_id,
            "artifact_id": result.artifact_id,
            "source_parameter": result.source_parameter,
            "designated_metric": result.designated_metric,
            "tagged_metric": asdict(result.tagged_metric),
        }
    )


def _serialize_dataset_profile(detail: DatasetDetail) -> dict[str, object]:
    return {
        "dataset_id": detail.dataset_id,
        "name": detail.name,
        "family": detail.family,
        "owner_display_name": detail.owner,
        "owner_user_id": detail.owner_user_id,
        "workspace_id": detail.workspace_id,
        "visibility_scope": detail.visibility_scope,
        "lifecycle_state": detail.lifecycle_state,
        "updated_at": detail.updated_at,
        "device_type": detail.device_type,
        "capabilities": list(detail.capabilities),
        "source": detail.source,
        "status": detail.status,
        "allowed_actions": asdict(detail.allowed_actions),
    }


def _serialize_catalog_row(row: object) -> dict[str, object]:
    return asdict(row)


def _serialize_design_browse_row(row: object) -> dict[str, object]:
    return asdict(row)


def _serialize_trace_browse_row(row: object) -> dict[str, object]:
    return {
        "trace_id": row.trace_id,
        "dataset_id": row.dataset_id,
        "design_id": row.design_id,
        "family": row.family,
        "parameter": row.parameter,
        "representation": row.representation,
        "trace_mode_group": row.trace_mode_group,
        "source_kind": row.source_kind,
        "stage_kind": row.stage_kind,
        "ndim": row.ndim,
        "shape": list(row.shape),
        "axes_summary": {
            "rank": row.axes_summary.rank,
            "axis_names": list(row.axes_summary.axis_names),
            "axis_units": list(row.axes_summary.axis_units),
            "axis_lengths": list(row.axes_summary.axis_lengths),
        },
        "axis_signature": row.axis_signature,
        "available_sweep_axes": list(row.available_sweep_axes),
        "collection_projection": (
            {
                "collection_key": row.collection_projection.collection_key,
                "kind": row.collection_projection.kind,
                "group_label": row.collection_projection.group_label,
            }
            if row.collection_projection is not None
            else None
        ),
        "provenance_summary": row.provenance_summary,
        "allowed_actions": asdict(row.allowed_actions),
        "mutation_policy_summary": row.mutation_policy_summary,
        "analysis_capabilities": [
            _serialize_trace_capability(item) for item in row.analysis_capabilities
        ],
    }


def _serialize_trace_detail(detail: object) -> dict[str, object]:
    return {
        "trace_id": detail.trace_id,
        "dataset_id": detail.dataset_id,
        "design_id": detail.design_id,
        "family": detail.family,
        "parameter": detail.parameter,
        "representation": detail.representation,
        "trace_mode_group": detail.trace_mode_group,
        "source_kind": detail.source_kind,
        "stage_kind": detail.stage_kind,
        "axes": [asdict(axis) for axis in detail.axes],
        "ndim": detail.ndim,
        "shape": list(detail.shape),
        "axes_summary": {
            "rank": detail.axes_summary.rank,
            "axis_names": list(detail.axes_summary.axis_names),
            "axis_units": list(detail.axes_summary.axis_units),
            "axis_lengths": list(detail.axes_summary.axis_lengths),
        },
        "axis_signature": detail.axis_signature,
        "available_sweep_axes": list(detail.available_sweep_axes),
        "collection_projection": (
            {
                "collection_key": detail.collection_projection.collection_key,
                "kind": detail.collection_projection.kind,
                "group_label": detail.collection_projection.group_label,
            }
            if detail.collection_projection is not None
            else None
        ),
        "preview_payload": detail.preview_payload,
        "payload_ref": asdict(detail.payload_ref) if detail.payload_ref is not None else None,
        "result_handles": [asdict(handle) for handle in detail.result_handles],
        "analysis_capabilities": [
            _serialize_trace_capability(item) for item in detail.analysis_capabilities
        ],
    }


def _serialize_trace_edit_detail(detail: object) -> dict[str, object]:
    return {
        "trace_id": detail.trace_id,
        "dataset_id": detail.dataset_id,
        "design_id": detail.design_id,
        "editable_metadata": asdict(detail.editable_metadata),
        "immutable_summary": asdict(detail.immutable_summary),
        "editable_numeric_payload": detail.editable_numeric_payload,
        "allowed_actions": asdict(detail.allowed_actions),
        "mutation_policy_summary": detail.mutation_policy_summary,
        "analysis_capabilities": [
            _serialize_trace_capability(item) for item in detail.analysis_capabilities
        ],
    }


def _serialize_trace_capability(capability: object) -> dict[str, object]:
    return {
        "capability_id": capability.capability_id,
        "analysis_id": capability.analysis_id,
        "analysis_label": capability.analysis_label,
        "input_role": capability.input_role,
        "input_role_label": capability.input_role_label,
        "status": capability.status,
        "summary": capability.summary,
        "reasons": [asdict(reason) for reason in capability.reasons],
    }


def _parse_dataset_create_payload(payload: object) -> DatasetCreateDraft:
    body = _as_mapping(payload)
    return DatasetCreateDraft(
        name=_require_text(body.get("name"), field="name"),
        family=_require_text(body.get("family"), field="family"),
        device_type=_require_text(body.get("device_type"), field="device_type"),
        source=_require_text(body.get("source"), field="source"),
    )


def _parse_design_create_payload(payload: object) -> DesignCreateDraft:
    body = _as_mapping(payload)
    return DesignCreateDraft(
        name=_require_text(body.get("name"), field="name"),
    )


def _parse_dataset_profile_payload(payload: object) -> DatasetProfileUpdate:
    body = _as_mapping(payload)
    device_type = _require_text(body.get("device_type"), field="device_type")
    source = _require_text(body.get("source"), field="source")
    raw_capabilities = body.get("capabilities", [])
    if not isinstance(raw_capabilities, list) or any(
        not isinstance(item, str) or len(item.strip()) == 0 for item in raw_capabilities
    ):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="capabilities must be an array of non-empty strings.",
        )
    capabilities = tuple(item.strip() for item in raw_capabilities)
    if len(capabilities) != len(set(capabilities)):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="capabilities must not contain duplicates.",
        )
    return DatasetProfileUpdate(
        device_type=device_type,
        capabilities=capabilities,
        source=source,
    )


def _parse_characterization_tagging_payload(payload: object) -> CharacterizationTaggingRequest:
    body = _as_mapping(payload)
    return CharacterizationTaggingRequest(
        artifact_id=_require_text(body.get("artifact_id"), field="artifact_id"),
        source_parameter=_require_text(
            body.get("source_parameter"),
            field="source_parameter",
        ),
        designated_metric=_require_text(
            body.get("designated_metric"),
            field="designated_metric",
        ),
    )


def _parse_raw_data_ingestion_payload(payload: object) -> RawDataIngestionDraft:
    body = _as_mapping(payload)
    kind = _require_text(body.get("kind"), field="kind")
    if kind not in {"measurement", "layout_simulation"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="kind must be measurement or layout_simulation.",
        )
    raw_traces = body.get("traces")
    if not isinstance(raw_traces, list) or len(raw_traces) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="traces must be a non-empty array.",
        )
    return RawDataIngestionDraft(
        kind=kind,
        design_name=_require_text(body.get("design_name"), field="design_name"),
        design_id=_optional_text(body.get("design_id"), field="design_id"),
        provenance_label=_require_text(body.get("provenance_label"), field="provenance_label"),
        traces=tuple(_parse_raw_trace_payload(item) for item in raw_traces),
    )


def _parse_trace_update_payload(payload: object) -> TraceUpdateDraft:
    body = _as_mapping(payload)
    if "preview_payload" in body:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=(
                "preview_payload is preview-only and cannot be submitted to the trace edit path."
            ),
        )
    if "axes" in body:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="axes are not directly editable; submit numeric_payload instead.",
        )
    numeric_payload = None
    if "numeric_payload" in body:
        numeric_payload = body.get("numeric_payload")
        if not isinstance(numeric_payload, dict):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="numeric_payload must be an object when provided.",
            )
    update = TraceUpdateDraft(
        parameter=_optional_text(body.get("parameter"), field="parameter"),
        representation=_optional_text(body.get("representation"), field="representation"),
        provenance_summary=_optional_text(
            body.get("provenance_summary"),
            field="provenance_summary",
        ),
        numeric_payload=numeric_payload,
    )
    if (
        update.parameter is None
        and update.representation is None
        and update.provenance_summary is None
        and update.numeric_payload is None
    ):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=(
                "Request body must include at least one editable trace field: "
                "parameter, representation, provenance_summary, or numeric_payload."
            ),
        )
    return update


def _parse_trace_batch_delete_payload(payload: object) -> tuple[str, ...]:
    body = _as_mapping(payload)
    raw_trace_ids = body.get("trace_ids")
    if not isinstance(raw_trace_ids, list) or len(raw_trace_ids) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="trace_ids must be a non-empty array.",
        )
    trace_ids = tuple(_require_text(value, field="trace_ids[]") for value in raw_trace_ids)
    if len(trace_ids) != len(set(trace_ids)):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="trace_ids must not contain duplicates.",
        )
    return trace_ids


def _parse_raw_trace_payload(payload: object) -> RawDataTraceDraft:
    body = _as_mapping(payload)
    raw_axes = body.get("axes")
    if not isinstance(raw_axes, list) or len(raw_axes) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="traces[].axes must be a non-empty array.",
        )
    preview_payload = body.get("preview_payload")
    if not isinstance(preview_payload, dict):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="traces[].preview_payload must be an object.",
        )
    return RawDataTraceDraft(
        trace_id=_optional_text(body.get("trace_id"), field="traces[].trace_id"),
        family=_require_family(body.get("family"), field="traces[].family"),
        parameter=_require_text(body.get("parameter"), field="traces[].parameter"),
        representation=_require_text(
            body.get("representation"),
            field="traces[].representation",
        ),
        trace_mode_group=_require_trace_mode_group(
            body.get("trace_mode_group"),
            field="traces[].trace_mode_group",
        ),
        stage_kind=_require_trace_stage_kind(body.get("stage_kind"), field="traces[].stage_kind"),
        provenance_summary=_require_text(
            body.get("provenance_summary"),
            field="traces[].provenance_summary",
        ),
        axes=tuple(_parse_trace_axis(axis) for axis in raw_axes),
        preview_payload=preview_payload,
    )


def _parse_trace_axis(payload: object) -> TraceAxis:
    body = _as_mapping(payload)
    length = body.get("length")
    if not isinstance(length, int) or length <= 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="axes[].length must be a positive integer.",
        )
    return TraceAxis(
        name=_require_text(body.get("name"), field="axes[].name"),
        unit=_require_text(body.get("unit"), field="axes[].unit"),
        length=length,
    )


def _normalize_trace_ids(values: list[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    return tuple(value.strip() for value in values if value.strip())


def _as_mapping(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="Request body must be an object.",
        )
    return payload


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or len(value.strip()) == 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=f"{field} must be a non-empty string.",
        )
    return value.strip()


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _require_text(value, field=field)


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized if normalized else None


def _normalize_family(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if normalized not in {"s_matrix", "y_matrix", "z_matrix"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="family must be one of s_matrix, y_matrix, or z_matrix.",
        )
    return normalized


def _normalize_source_kind(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if normalized not in {"circuit_simulation", "layout_simulation", "measurement"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message=(
                "source_kind must be one of circuit_simulation, layout_simulation, or measurement."
            ),
        )
    return normalized


def _normalize_trace_mode_group(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if normalized not in {"base", "sideband", "all"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="trace_mode_group must be one of base, sideband, or all.",
        )
    return normalized


def _normalize_trace_stage_kind(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if normalized not in {"raw", "preprocess", "postprocess"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="stage_kind must be one of raw, preprocess, or postprocess.",
        )
    return normalized


def _require_family(value: object, *, field: str) -> str:
    normalized = _normalize_family(_require_text(value, field=field))
    assert normalized is not None
    return normalized


def _require_trace_mode_group(value: object, *, field: str) -> str:
    normalized = _normalize_trace_mode_group(_require_text(value, field=field))
    assert normalized is not None
    return normalized


def _require_trace_stage_kind(value: object, *, field: str) -> str:
    normalized = _normalize_trace_stage_kind(_require_text(value, field=field))
    assert normalized is not None
    return normalized


def _normalize_characterization_result_status(value: str | None) -> str | None:
    normalized = _normalize_optional_text(value)
    if normalized is None:
        return None
    if normalized not in {"completed", "failed", "blocked"}:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="status must be one of completed, failed, or blocked.",
        )
    return normalized


def _parse_limit(value: str | None) -> int:
    if value is None:
        return 20
    try:
        limit = int(value)
    except ValueError as exc:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="limit must be a positive integer.",
        ) from exc
    if limit <= 0 or limit > 100:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="limit must be between 1 and 100.",
        )
    return limit


def _paginate_rows(
    rows: list[dict[str, object]],
    *,
    limit: int,
    cursor: str | None,
    filter_echo: dict[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    offset = _parse_cursor(cursor)
    if offset > len(rows):
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="cursor is out of range for the requested collection.",
        )
    page_rows = rows[offset : offset + limit]
    next_offset = offset + len(page_rows)
    prev_offset = max(offset - limit, 0)
    has_more = next_offset < len(rows)
    return page_rows, {
        "generated_at": _generated_at(),
        "limit": limit,
        "next_cursor": str(next_offset) if has_more else None,
        "prev_cursor": str(prev_offset) if offset > 0 else None,
        "has_more": has_more,
        "filter_echo": filter_echo,
    }


def _parse_cursor(cursor: str | None) -> int:
    if cursor is None:
        return 0
    try:
        value = int(cursor)
    except ValueError as exc:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="cursor must be an integer offset.",
        ) from exc
    if value < 0:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="cursor must be zero or a positive integer.",
        )
    return value


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
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "error": {
                "code": exc.code,
                "category": exc.category,
                "message": exc.message,
                "retryable": exc.category == "internal_error",
                "debug_ref": current_debug_ref(),
            },
        },
    )


def _generated_at() -> str:
    return datetime.now(UTC).isoformat()
