from __future__ import annotations

from app_backend.domain.runtime_contracts.execution import TaskResultHandle
from app_backend.domain.storage import ResultHandleKind
from app_backend.domain.tasks import TaskCreateDraft, TaskResultRefs
from app_backend.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
)


def build_pending_result_refs(
    *,
    task_id: int,
    draft: TaskCreateDraft,
) -> TaskResultRefs:
    pending_record = build_metadata_record_ref(
        "result_handle",
        f"result_handle:pending:{task_id}",
        version=1,
    )
    return TaskResultRefs(
        result_handle=TaskResultHandle(),
        metadata_records=(pending_record,),
        trace_payload=None,
        result_handles=(
            build_result_handle_ref(
                handle_id=f"task-result:{task_id}:primary",
                kind=_default_result_handle_kind(draft.kind),
                status="pending",
                label=_default_result_handle_label(draft.kind),
                metadata_record=pending_record,
                payload_backend=None,
                payload_format=None,
                payload_role=None,
                payload_locator=None,
                provenance_task_id=task_id,
                provenance=build_result_provenance_ref(
                    source_dataset_id=draft.dataset_id,
                    source_task_id=task_id,
                ),
            ),
        ),
    )


def _default_result_handle_kind(task_kind: str) -> ResultHandleKind:
    if task_kind == "characterization":
        return "characterization_report"
    if task_kind == "post_processing":
        return "fit_summary"
    return "simulation_trace"


def _default_result_handle_label(task_kind: str) -> str:
    if task_kind == "characterization":
        return "Pending characterization report"
    if task_kind == "post_processing":
        return "Pending fit summary"
    return "Pending simulation trace"
