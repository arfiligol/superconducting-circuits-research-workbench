from __future__ import annotations

import json

from app_backend.api.presenters.storage import (
    build_metadata_record_ref_response,
    build_result_handle_ref_response,
    build_trace_payload_ref_response,
)
from app_backend.domain.datasets import TraceMetadataSummary
from app_backend.domain.tasks import (
    CharacterizationSetup,
    PostProcessingSetup,
    SimulationSetup,
    TaskDetail,
    TaskEvent,
    TaskProcessorDetail,
    TaskPublicationSummary,
    TaskQueueRow,
    WorkerLaneSummary,
)
from app_backend.services.simulation_result_explorer_service import ExplorerSelectionRequest
from app_backend.services.task_service import TaskService


def build_task_queue_row_response(queue_row: TaskQueueRow) -> dict[str, object]:
    return {
        "task_id": queue_row.task_id,
        "summary": queue_row.summary,
        "status": queue_row.status,
        "lane": queue_row.lane,
        "task_kind": queue_row.task_kind,
        "owner_display_name": queue_row.owner_display_name,
        "visibility_scope": queue_row.visibility_scope,
        "dataset_id": queue_row.dataset_id,
        "definition_id": queue_row.definition_id,
        "updated_at": queue_row.updated_at,
        "result_availability": queue_row.result_availability,
        "allowed_actions": {
            "attach": queue_row.allowed_actions.attach,
            "cancel": queue_row.allowed_actions.cancel,
            "terminate": queue_row.allowed_actions.terminate,
            "retry": queue_row.allowed_actions.retry,
            "rejection_reason": queue_row.allowed_actions.rejection_reason,
        },
        "control_state": queue_row.control_state,
        "reconcile": {
            "required": queue_row.reconcile.required,
            "reason": queue_row.reconcile.reason,
        },
    }


def build_task_detail_response(
    task: TaskDetail,
    task_service: TaskService,
) -> dict[str, object]:
    result_handoff = task_service.get_task_result_handoff(task.task_id)
    allowed_actions = task_service.get_task_allowed_actions(task.task_id)
    trace_payload_response = build_trace_payload_ref_response(task.result_refs.trace_payload)
    return {
        "task_id": task.task_id,
        "task_kind": task.kind,
        "lane": task.lane,
        "execution_mode": task.execution_mode,
        "status": task.status,
        "submitted_at": task.submitted_at,
        "owner_user_id": task.owner_user_id,
        "owner_display_name": task.owner_display_name,
        "workspace_id": task.workspace_id,
        "workspace_slug": task.workspace_slug,
        "visibility_scope": task.visibility_scope,
        "dataset_id": task.dataset_id,
        "definition_id": task.definition_id,
        "summary": task.summary,
        "worker_task_name": task.worker_task_name,
        "request_ready": task.request_ready,
        "submitted_from_active_dataset": task.submitted_from_active_dataset,
        "simulation_setup": (
            _build_simulation_setup_response(task.simulation_setup)
            if task.simulation_setup is not None
            else None
        ),
        "publication_summary": build_publication_summary_response(
            task_service.get_task_publication_summary(task.task_id)
        ),
        "downstream_source_capabilities": _build_downstream_source_capabilities_response(task),
        "post_processing_setup": (
            _build_post_processing_setup_response(task.post_processing_setup)
            if task.post_processing_setup is not None
            else None
        ),
        "characterization_setup": (
            _build_characterization_setup_response(task.characterization_setup)
            if task.characterization_setup is not None
            else None
        ),
        "upstream_task_id": task.upstream_task_id,
        "downstream_task_ids": list(task.downstream_task_ids),
        "control_state": task.control_state,
        "retry_of_task_id": task.retry_of_task_id,
        "allowed_actions": {
            "attach": allowed_actions.attach,
            "cancel": allowed_actions.cancel,
            "terminate": allowed_actions.terminate,
            "retry": allowed_actions.retry,
            "rejection_reason": allowed_actions.rejection_reason,
        },
        "dispatch": (
            {
                "dispatch_key": task.dispatch.dispatch_key,
                "status": task.dispatch.status,
                "submission_source": task.dispatch.submission_source,
                "accepted_at": task.dispatch.accepted_at,
                "last_updated_at": task.dispatch.last_updated_at,
                "queue_name": task.dispatch.queue_name,
                "enqueued_at": task.dispatch.enqueued_at,
                "runtime_job_id": task.dispatch.runtime_job_id,
                "dispatch_attempt_count": task.dispatch.dispatch_attempt_count,
                "last_dispatch_outcome": task.dispatch.last_dispatch_outcome,
                "last_dispatch_error_code": task.dispatch.last_dispatch_error_code,
            }
            if task.dispatch is not None
            else None
        ),
        "reconcile": {
            "required": task.reconcile.required,
            "reason": task.reconcile.reason,
        },
        "progress": {
            "phase": task.progress.phase,
            "percent_complete": task.progress.percent_complete,
            "summary": task.progress.summary,
            "updated_at": task.progress.updated_at,
        },
        "result_handoff": {
            "availability": result_handoff.availability,
            "primary_result_handle_id": result_handoff.primary_result_handle_id,
            "result_handle_count": result_handoff.result_handle_count,
            "trace_payload_available": result_handoff.trace_payload_available,
        },
        "result_refs": {
            "trace_batch_id": task.result_refs.trace_batch_id,
            "analysis_run_id": task.result_refs.analysis_run_id,
            "metadata_records": [
                build_metadata_record_ref_response(record).model_dump()
                for record in task.result_refs.metadata_records
            ],
            "trace_payload": (
                trace_payload_response.model_dump() if trace_payload_response is not None else None
            ),
            "result_handles": [
                build_result_handle_ref_response(handle).model_dump()
                for handle in task.result_refs.result_handles
            ],
        },
        "events": [build_task_event_response(event) for event in task.events],
    }


def build_worker_summary_response(summary: WorkerLaneSummary) -> dict[str, object]:
    return {
        "lane": summary.lane,
        "idle_processors": summary.idle_processors,
        "running_processors": summary.running_processors,
        "degraded_processors": summary.degraded_processors,
        "draining_processors": summary.draining_processors,
        "offline_processors": summary.offline_processors,
    }


def build_processor_detail_response(processor: TaskProcessorDetail) -> dict[str, object]:
    return {
        "processor_id": processor.processor_id,
        "lane": processor.lane,
        "state": processor.state,
        "current_task_id": processor.current_task_id,
        "last_heartbeat_at": processor.last_heartbeat_at,
        "runtime_metadata": processor.runtime_metadata,
    }


def build_task_event_response(event: TaskEvent) -> dict[str, object]:
    return {
        "event_key": event.event_key,
        "event_type": event.event_type,
        "level": event.level,
        "occurred_at": event.occurred_at,
        "message": event.message,
        "metadata": {
            key: _deserialize_task_event_metadata_value(key, value)
            for key, value in dict(event.metadata).items()
        },
    }


def build_publication_summary_response(
    summary: TaskPublicationSummary,
) -> dict[str, object]:
    return {
        "state": summary.state,
        "publish_allowed": summary.publish_allowed,
        "publication_key": summary.publication_key,
        "target_dataset_id": summary.target_dataset_id,
        "target_design_id": summary.target_design_id,
        "target_design_name": summary.target_design_name,
        "published_trace_ids": list(summary.published_trace_ids),
        "published_at": summary.published_at,
        "source_task_id": summary.source_task_id,
        "source_result_handle_ids": list(summary.source_result_handle_ids),
    }


def build_published_trace_response(trace: TraceMetadataSummary) -> dict[str, object]:
    return {
        "trace_id": trace.trace_id,
        "dataset_id": trace.dataset_id,
        "design_id": trace.design_id,
        "family": trace.family,
        "parameter": trace.parameter,
        "representation": trace.representation,
        "trace_mode_group": trace.trace_mode_group,
        "source_kind": trace.source_kind,
        "stage_kind": trace.stage_kind,
        "provenance_summary": trace.provenance_summary,
        "analysis_capabilities": [
            {
                "capability_id": capability.capability_id,
                "analysis_id": capability.analysis_id,
                "analysis_label": capability.analysis_label,
                "input_role": capability.input_role,
                "input_role_label": capability.input_role_label,
                "status": capability.status,
                "summary": capability.summary,
                "reasons": [dict(reason.__dict__) for reason in capability.reasons],
            }
            for capability in trace.analysis_capabilities
        ],
    }


def build_explorer_filter_echo(
    selection_request: ExplorerSelectionRequest,
) -> dict[str, object]:
    return {
        "family": selection_request.family,
        "source": selection_request.source,
        "metric": selection_request.metric,
        "sweep_index": selection_request.sweep_index,
        "compare_axis_index": selection_request.compare_axis_index,
        "z0": selection_request.z0_ohm,
        "output_port": selection_request.output_port,
        "input_port": selection_request.input_port,
    }


def _build_simulation_setup_response(setup: SimulationSetup) -> dict[str, object]:
    return setup.to_mapping()


def _build_downstream_source_capabilities_response(
    task: TaskDetail,
) -> dict[str, object]:
    ptc = task.simulation_setup.ptc if task.simulation_setup is not None else None
    return {
        "raw": {
            "available": task.kind == "simulation",
        },
        "ptc": {
            "available": ptc.enabled if ptc is not None else False,
            "enabled": ptc.enabled if ptc is not None else False,
            "mode": ptc.mode if ptc is not None else None,
            "compensate_ports": list(ptc.compensate_ports) if ptc is not None else [],
        },
    }


def _build_post_processing_setup_response(setup: PostProcessingSetup) -> dict[str, object]:
    return setup.to_mapping()


def _build_characterization_setup_response(
    setup: CharacterizationSetup,
) -> dict[str, object]:
    return setup.to_mapping()


def _deserialize_task_event_metadata_value(key: str, value: object) -> object:
    if key not in {
        "simulation_setup",
        "post_processing_setup",
        "characterization_setup",
        "downstream_task_ids",
        "publication_summary",
        "characterization_result_summary",
        "characterization_result_detail",
        "characterization_run_history_row",
        "simulation_raw_bundle",
        "simulation_ptc_bundle",
        "post_processing_raw_bundle",
        "post_processing_ptc_bundle",
    }:
        return value
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value
