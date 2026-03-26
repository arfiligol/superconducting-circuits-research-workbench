from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Protocol

from sc_core.tasking import resolve_worker_task_route

from src.app.domain.audit import AuditRecord
from src.app.domain.characterization_analysis import (
    evaluate_characterization_analysis_scope,
    get_characterization_analysis_spec,
    validate_characterization_analysis_config,
)
from src.app.domain.datasets import (
    DatasetDetail,
    DesignBrowseRow,
    TraceMetadataSummary,
)
from src.app.domain.session import SessionState
from src.app.domain.tasks import (
    CharacterizationSetup,
    PostProcessingSetup,
    SimulationSetup,
    TaskCreateDraft,
    TaskDetail,
    TaskDispatchReceipt,
    TaskEnqueueError,
    TaskKind,
    TaskSubmissionDraft,
    task_submission_source_for,
)
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import ServiceFieldError, service_error


class TaskSubmissionRepository(Protocol):
    def get_task(self, task_id: int) -> TaskDetail | None: ...

    def create_task(self, draft: TaskCreateDraft) -> TaskDetail: ...

    def merge_task_event_metadata(
        self,
        task_id: int,
        event_key: str,
        metadata: dict[str, object],
    ) -> None: ...


class TaskSubmissionDatasetRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def get_design(self, dataset_id: str, design_id: str) -> DesignBrowseRow | None: ...

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[TraceMetadataSummary]: ...


class TaskSubmissionCircuitDefinitionRepository(Protocol):
    def get_circuit_definition(self, definition_id: str) -> object | None: ...


class TaskSubmissionSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class TaskSubmissionAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class TaskSubmissionQueueDispatcher(Protocol):
    def enqueue_submitted_task(self, task: TaskDetail) -> TaskDispatchReceipt: ...


class TaskSubmissionService:
    def __init__(
        self,
        repository: TaskSubmissionRepository,
        session_repository: TaskSubmissionSessionRepository,
        dataset_repository: TaskSubmissionDatasetRepository,
        circuit_definition_repository: TaskSubmissionCircuitDefinitionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: TaskSubmissionAuditRepository | None = None,
        queue_dispatcher: TaskSubmissionQueueDispatcher | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._dataset_repository = dataset_repository
        self._circuit_definition_repository = circuit_definition_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository
        self._queue_dispatcher = queue_dispatcher

    def submit_task(self, draft: TaskSubmissionDraft) -> int:
        session = self._session_repository.get_session_state()
        if session.user is None:
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="Submitting tasks requires an authenticated session.",
            )
        resolved_dataset_id = draft.dataset_id or session.active_dataset_id
        submitted_from_active_dataset = draft.dataset_id is None and resolved_dataset_id is not None
        upstream_task = self._resolve_upstream_task(draft.upstream_task_id)

        if draft.kind == "simulation" and draft.definition_id is None:
            raise service_error(
                422,
                code="simulation_definition_required",
                category="validation",
                message="Simulation tasks require definition_id.",
            )
        if draft.kind == "simulation" and draft.simulation_setup is None:
            raise service_error(
                422,
                code="simulation_setup_required",
                category="validation",
                message="Simulation tasks require simulation_setup.",
            )
        if draft.kind in {"post_processing", "characterization"} and resolved_dataset_id is None:
            raise service_error(
                422,
                code="dataset_context_required",
                category="validation",
                message=f"{draft.kind} tasks require dataset_id or an active dataset.",
            )
        if draft.kind == "post_processing" and draft.post_processing_setup is None:
            raise service_error(
                422,
                code="post_processing_setup_required",
                category="validation",
                message="Post-processing tasks require post_processing_setup.",
            )
        if draft.kind == "characterization" and draft.characterization_setup is None:
            raise service_error(
                422,
                code="characterization_setup_required",
                category="validation",
                message="Characterization tasks require characterization_setup.",
            )
        if draft.kind == "post_processing" and upstream_task is None:
            raise service_error(
                422,
                code="post_processing_upstream_required",
                category="validation",
                message="Post-processing tasks require upstream_task_id.",
            )

        resolved_dataset = (
            self._dataset_repository.get_dataset(resolved_dataset_id)
            if resolved_dataset_id is not None
            else None
        )
        if resolved_dataset_id is not None and resolved_dataset is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {resolved_dataset_id} was not found.",
            )
        if resolved_dataset is not None and not self._authorization_service.is_visible_dataset(
            resolved_dataset,
            session,
        ):
            raise service_error(
                403,
                code="dataset_not_visible_in_workspace",
                category="permission_denied",
                message="The selected dataset is not visible in the active workspace.",
            )
        if (
            draft.definition_id is not None
            and self._circuit_definition_repository.get_circuit_definition(draft.definition_id)
            is None
        ):
            raise service_error(
                404,
                code="circuit_definition_not_found",
                category="not_found",
                message=f"Circuit definition {draft.definition_id} was not found.",
            )
        if upstream_task is not None:
            self._validate_upstream_task(
                upstream_task=upstream_task,
                draft=draft,
                resolved_dataset_id=resolved_dataset_id,
            )
        if draft.kind == "characterization":
            self._validate_characterization_submission(
                dataset_id=resolved_dataset_id,
                setup=draft.characterization_setup,
            )
        self._authorization_service.authorize(
            session,
            "submit_task",
            resource=_task_resource(session.workspace_id),
            denied_code="task_submit_denied",
            denied_message="The current session cannot submit tasks in the active workspace.",
        )

        worker_route = resolve_worker_task_route(
            draft.kind,
            request_is_valid=True,
            has_trace_batch_id=False,
        )
        created_task = self._repository.create_task(
            TaskCreateDraft(
                kind=draft.kind,
                lane=_normalize_runtime_lane(worker_route.lane),
                execution_mode=worker_route.execution_mode,
                owner_user_id=_session_user_id(session),
                owner_display_name=(
                    session.user.display_name if session.user is not None else "anonymous"
                ),
                workspace_id=session.workspace_id,
                workspace_slug=session.workspace_slug,
                visibility_scope=(
                    "local"
                    if session.runtime_mode == "local"
                    else ("workspace" if session.default_task_scope == "workspace" else "owned")
                ),
                dataset_id=resolved_dataset_id,
                definition_id=draft.definition_id,
                summary=draft.summary or _default_task_summary(draft.kind, resolved_dataset_id),
                worker_task_name=worker_route.worker_task_name,
                request_ready=worker_route.request_ready,
                submitted_from_active_dataset=submitted_from_active_dataset,
                submission_source=task_submission_source_for(
                    submitted_from_active_dataset=submitted_from_active_dataset,
                    dataset_id=resolved_dataset_id,
                ),
                simulation_setup=draft.simulation_setup,
                post_processing_setup=draft.post_processing_setup,
                characterization_setup=draft.characterization_setup,
                upstream_task_id=draft.upstream_task_id,
            )
        )
        created_detail = self._repository.get_task(created_task.task_id)
        if created_detail is None:
            raise service_error(
                404,
                code="task_not_found",
                category="not_found",
                message=f"Task {created_task.task_id} was not found.",
            )
        self._merge_submission_metadata(
            created_detail,
            draft=draft,
            upstream_task=upstream_task,
        )
        self._append_audit_record(
            action_kind="task.submitted",
            resource_id=str(created_detail.task_id),
            outcome="accepted",
            payload={
                "task_kind": created_detail.kind,
                "lane": created_detail.lane,
                "dataset_id": created_detail.dataset_id,
                "definition_id": created_detail.definition_id,
                "upstream_task_id": created_detail.upstream_task_id,
                "submission_source": (
                    created_detail.dispatch.submission_source
                    if created_detail.dispatch is not None
                    else None
                ),
            },
        )
        self._enqueue_submitted_task_if_supported(
            created_detail,
            runtime_mode=session.runtime_mode,
        )
        return created_task.task_id

    def _merge_submission_metadata(
        self,
        task: TaskDetail,
        *,
        draft: TaskSubmissionDraft,
        upstream_task: TaskDetail | None,
    ) -> None:
        if len(task.events) == 0:
            return
        submission_metadata = {
            "audit_action": "task.submitted",
            **_submission_contract_metadata(draft),
        }
        self._repository.merge_task_event_metadata(
            task.task_id,
            task.events[0].event_key,
            submission_metadata,
        )
        if upstream_task is not None and len(upstream_task.events) > 0:
            downstream_task_ids = tuple(sorted({*upstream_task.downstream_task_ids, task.task_id}))
            self._repository.merge_task_event_metadata(
                upstream_task.task_id,
                upstream_task.events[0].event_key,
                {
                    "downstream_task_ids": json.dumps(list(downstream_task_ids)),
                    "audit_action": "task.submitted",
                },
            )

    def _merge_dispatch_contract_metadata(
        self,
        task: TaskDetail,
        receipt: TaskDispatchReceipt,
    ) -> None:
        if len(task.events) == 0:
            return
        self._repository.merge_task_event_metadata(
            task.task_id,
            task.events[0].event_key,
            {
                "queue_name": receipt.queue_name,
                "enqueued_at": receipt.enqueued_at,
                "runtime_job_id": receipt.runtime_job_id,
                "dispatch_attempt_count": receipt.dispatch_attempt_count,
                "last_dispatch_outcome": receipt.last_dispatch_outcome,
                "last_dispatch_error_code": receipt.last_dispatch_error_code,
            },
        )

    def _append_audit_record(
        self,
        *,
        action_kind: str,
        resource_id: str,
        outcome: str,
        payload: dict[str, object],
    ) -> None:
        if self._audit_repository is None:
            return
        session = self._session_repository.get_session_state()
        self._audit_repository.append(
            build_audit_record(
                state=session,
                action_kind=action_kind,
                resource_kind="task",
                resource_id=resource_id,
                outcome=outcome,
                payload=payload,
            )
        )

    def _enqueue_submitted_task_if_supported(
        self,
        task: TaskDetail,
        *,
        runtime_mode: str,
    ) -> None:
        if self._queue_dispatcher is None or runtime_mode != "local":
            return
        try:
            receipt = self._queue_dispatcher.enqueue_submitted_task(task)
        except TaskEnqueueError as exc:
            self._merge_dispatch_contract_metadata(task, exc.receipt)
            self._append_audit_record(
                action_kind="task.enqueue_failed",
                resource_id=str(task.task_id),
                outcome="failed",
                payload={
                    "lane": task.lane,
                    "queue_name": exc.receipt.queue_name,
                    "runtime_job_id": exc.receipt.runtime_job_id,
                    "error_code": exc.code,
                },
            )
            raise service_error(
                503,
                code="task_enqueue_failed",
                category="task_execution_failed",
                message="Task was persisted, but the local worker queue could not accept it.",
                details={
                    "task_id": task.task_id,
                    "dispatch": _dispatch_error_payload(task, exc.receipt),
                },
            ) from exc
        self._merge_dispatch_contract_metadata(task, receipt)

    def _resolve_upstream_task(self, upstream_task_id: int | None) -> TaskDetail | None:
        if upstream_task_id is None:
            return None
        task = self._repository.get_task(upstream_task_id)
        if task is None:
            raise service_error(
                404,
                code="upstream_task_not_found",
                category="not_found",
                message=f"Upstream task {upstream_task_id} was not found.",
            )
        return task

    def _validate_upstream_task(
        self,
        *,
        upstream_task: TaskDetail,
        draft: TaskSubmissionDraft,
        resolved_dataset_id: str | None,
    ) -> None:
        session = self._session_repository.get_session_state()
        if not self._is_visible(upstream_task, session):
            raise service_error(
                404,
                code="upstream_task_not_found",
                category="not_found",
                message=f"Upstream task {upstream_task.task_id} was not found.",
            )
        if draft.kind == "post_processing" and upstream_task.kind != "simulation":
            raise service_error(
                422,
                code="post_processing_upstream_invalid",
                category="validation",
                message="Post-processing tasks must reference an upstream simulation task.",
            )
        if resolved_dataset_id is not None and upstream_task.dataset_id != resolved_dataset_id:
            raise service_error(
                422,
                code="upstream_task_dataset_mismatch",
                category="validation",
                message="upstream_task_id must belong to the same dataset context as the new task.",
            )

    def _is_visible(self, task: TaskDetail, session: SessionState) -> bool:
        if not self._authorization_service.is_visible_task(task, session):
            return False
        if session.runtime_mode == "local":
            return task.visibility_scope == "local"
        return True

    def _validate_characterization_submission(
        self,
        *,
        dataset_id: str | None,
        setup: CharacterizationSetup | None,
    ) -> None:
        if dataset_id is None or setup is None:
            raise service_error(
                422,
                code="dataset_context_required",
                category="validation",
                message="Characterization tasks require dataset_id or an active dataset.",
            )
        design = self._dataset_repository.get_design(dataset_id, setup.design_id)
        if design is None:
            raise service_error(
                404,
                code="design_not_found",
                category="not_found",
                message="The selected design is not available in the target dataset.",
            )
        if len(setup.selected_trace_ids) == 0:
            raise service_error(
                422,
                code="characterization_trace_selection_required",
                category="validation",
                message="Characterization tasks require at least one selected trace.",
            )
        trace_rows = tuple(
            self._dataset_repository.list_trace_metadata(dataset_id, setup.design_id)
        )
        traces_by_id = {trace.trace_id: trace for trace in trace_rows}
        missing_trace_ids = [
            trace_id for trace_id in setup.selected_trace_ids if trace_id not in traces_by_id
        ]
        if len(missing_trace_ids) > 0:
            missing_trace_id_set = set(missing_trace_ids)
            raise service_error(
                422,
                code="characterization_trace_selection_invalid",
                category="validation",
                message=(
                    "Selected traces must belong to the chosen design in the current dataset."
                ),
                field_errors=tuple(
                    ServiceFieldError(
                        field=f"characterization_setup.selected_trace_ids[{index}]",
                        message="Trace is not available in the selected design scope.",
                    )
                    for index, trace_id in enumerate(setup.selected_trace_ids)
                    if trace_id in missing_trace_id_set
                ),
            )
        spec = get_characterization_analysis_spec(setup.analysis_id)
        if spec is None:
            raise service_error(
                422,
                code="characterization_analysis_invalid",
                category="validation",
                message="analysis_id is not recognized for the selected design.",
            )
        if not spec.local_runtime_supported:
            raise service_error(
                409,
                code="characterization_analysis_unsupported",
                category="conflict",
                message=(
                    "Local characterization currently supports only "
                    "the admittance_extraction analysis."
                ),
            )
        scope_evaluation = evaluate_characterization_analysis_scope(
            spec=spec,
            traces=trace_rows,
            selected_trace_ids=setup.selected_trace_ids,
        )
        if not scope_evaluation.selected_scope_ready:
            raise service_error(
                422,
                code="characterization_trace_selection_incompatible",
                category="validation",
                message=scope_evaluation.summary,
            )
        config_error = validate_characterization_analysis_config(
            spec,
            setup.analysis_config,
        )
        if config_error is not None:
            raise service_error(
                422,
                code="characterization_config_invalid",
                category="validation",
                message=config_error,
            )


def _default_task_summary(task_kind: TaskKind, dataset_id: str | None) -> str:
    if dataset_id is None:
        return f"{task_kind.replace('_', ' ')} task accepted by the local runtime."
    return f"{task_kind.replace('_', ' ')} task accepted for dataset {dataset_id}."


def _submission_contract_metadata(draft: TaskSubmissionDraft) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if draft.simulation_setup is not None:
        metadata["simulation_setup"] = json.dumps(
            _serialize_simulation_setup(draft.simulation_setup)
        )
    if draft.post_processing_setup is not None:
        metadata["post_processing_setup"] = json.dumps(
            _serialize_post_processing_setup(draft.post_processing_setup)
        )
    if draft.characterization_setup is not None:
        metadata["characterization_setup"] = json.dumps(
            _serialize_characterization_setup(draft.characterization_setup)
        )
    if draft.upstream_task_id is not None:
        metadata["upstream_task_id"] = draft.upstream_task_id
    return metadata


def _serialize_simulation_setup(setup: SimulationSetup) -> dict[str, object]:
    return setup.to_mapping()


def _serialize_post_processing_setup(setup: PostProcessingSetup) -> dict[str, object]:
    return setup.to_mapping()


def _serialize_characterization_setup(setup: CharacterizationSetup) -> dict[str, object]:
    return setup.to_mapping()


def _session_user_id(session: SessionState) -> str:
    if session.user is None:
        return "anonymous"
    return session.user.user_id


def _dispatch_error_payload(
    task: TaskDetail,
    receipt: TaskDispatchReceipt,
) -> dict[str, object]:
    return {
        "dispatch_key": task.dispatch.dispatch_key if task.dispatch is not None else None,
        "queue_name": receipt.queue_name,
        "runtime_job_id": receipt.runtime_job_id,
        "dispatch_attempt_count": receipt.dispatch_attempt_count,
        "last_dispatch_outcome": receipt.last_dispatch_outcome,
        "last_dispatch_error_code": receipt.last_dispatch_error_code,
    }


def _normalize_runtime_lane(lane: str) -> str:
    return "simulation" if lane == "post_processing" else lane


def _task_resource(task: TaskDetail | str):
    from src.app.domain.authorization import AuthorizationResourceEnvelope

    if isinstance(task, str):
        return AuthorizationResourceEnvelope(
            resource_kind="task",
            workspace_id=task,
            owner_user_id=None,
            visibility_scope="workspace",
            lifecycle_state="active",
        )
    return AuthorizationResourceEnvelope(
        resource_kind="task",
        workspace_id=task.workspace_id,
        owner_user_id=task.owner_user_id,
        visibility_scope=task.visibility_scope,
        lifecycle_state="active",
    )
