from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol

from sc_core.tasking import evaluate_task_control_action

from src.app.domain.audit import AuditRecord
from src.app.domain.session import SessionState
from src.app.domain.tasks import (
    CharacterizationSetup,
    PostProcessingSetup,
    SimulationSetup,
    TaskAllowedActions,
    TaskCreateDraft,
    TaskDetail,
    TaskDispatchReceipt,
    TaskEnqueueError,
    TaskEvent,
    TaskLifecycleUpdate,
    TaskSubmissionDraft,
    build_task_retry_event,
    task_submission_source_for,
)
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import service_error


class TaskControlRepository(Protocol):
    def create_task(self, draft: TaskCreateDraft) -> TaskDetail: ...

    def merge_task_event_metadata(
        self,
        task_id: int,
        event_key: str,
        metadata: dict[str, object],
    ) -> None: ...

    def append_task_event(
        self,
        task_id: int,
        event: TaskEvent,
    ) -> None: ...


class TaskControlSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class TaskControlAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class TaskControlQueueDispatcher(Protocol):
    def enqueue_submitted_task(self, task: TaskDetail) -> TaskDispatchReceipt: ...


class TaskControlHost(Protocol):
    def get_task(self, task_id: int) -> TaskDetail: ...

    def get_task_allowed_actions(self, task_id: int) -> TaskAllowedActions: ...

    def update_task_lifecycle(self, update: TaskLifecycleUpdate) -> TaskDetail: ...


class TaskControlService:
    def __init__(
        self,
        repository: TaskControlRepository,
        session_repository: TaskControlSessionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: TaskControlAuditRepository | None = None,
        queue_dispatcher: TaskControlQueueDispatcher | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository
        self._queue_dispatcher = queue_dispatcher

    def cancel_task(self, task_id: int, *, host: TaskControlHost) -> int:
        task = host.get_task(task_id)
        session = self._session_repository.get_session_state()
        self._authorize_task_action(
            session,
            task,
            own_action="cancel_own_task",
            workspace_action="cancel_workspace_task",
            denied_code="task_cancel_denied",
            denied_message="The current session cannot cancel this task.",
        )
        decision = evaluate_task_control_action("cancel", current_state=task.status)
        if not decision.accepted or decision.requested_state is None:
            raise service_error(
                409,
                code=decision.rejection_reason or "task_not_cancellable",
                category="conflict",
                message="The task cannot be cancelled in its current state.",
            )
        occurred_at = _generated_at()
        updated_task = host.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task_id,
                status=decision.requested_state,
                progress_percent_complete=(
                    100
                    if decision.requested_state == "cancelled"
                    else task.progress.percent_complete
                ),
                progress_summary=(
                    "Task was cancelled before execution started."
                    if decision.requested_state == "cancelled"
                    else "Cancellation was requested for the task."
                ),
                progress_updated_at=occurred_at,
                summary=(
                    "Task was cancelled before execution started."
                    if decision.requested_state == "cancelled"
                    else task.summary
                ),
            )
        )
        self._merge_lifecycle_audit_metadata(
            updated_task=updated_task,
            metadata={
                "audit_action": "task.cancel_requested",
                **decision.to_payload(),
            },
        )
        self._append_audit_record(
            action_kind="task.cancel_requested",
            resource_id=str(task_id),
            outcome="accepted",
            payload={
                "task_status": task.status,
                "lane": task.lane,
                **decision.to_payload(),
            },
        )
        return task_id

    def terminate_task(self, task_id: int, *, host: TaskControlHost) -> int:
        task = host.get_task(task_id)
        session = self._session_repository.get_session_state()
        self._authorize_task_action(
            session,
            task,
            own_action="terminate_workspace_task",
            workspace_action="terminate_workspace_task",
            denied_code="task_terminate_denied",
            denied_message="The current session cannot terminate this task.",
        )
        decision = evaluate_task_control_action("terminate", current_state=task.status)
        if not decision.accepted or decision.requested_state is None:
            raise service_error(
                409,
                code=decision.rejection_reason or "task_not_terminable",
                category="conflict",
                message="The task cannot be force terminated in its current state.",
            )
        occurred_at = _generated_at()
        updated_task = host.update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=task_id,
                status=decision.requested_state,
                progress_percent_complete=task.progress.percent_complete,
                progress_summary="Force termination was requested for the task.",
                progress_updated_at=occurred_at,
                summary=task.summary,
            )
        )
        self._merge_lifecycle_audit_metadata(
            updated_task=updated_task,
            metadata={
                "audit_action": "task.terminate_requested",
                **decision.to_payload(),
            },
        )
        self._append_audit_record(
            action_kind="task.terminate_requested",
            resource_id=str(task_id),
            outcome="accepted",
            payload={
                "task_status": task.status,
                "lane": task.lane,
                **decision.to_payload(),
            },
        )
        return task_id

    def retry_task(self, task_id: int, *, host: TaskControlHost) -> int:
        source_task = host.get_task(task_id)
        session = self._session_repository.get_session_state()
        self._authorize_task_action(
            session,
            source_task,
            own_action="retry_own_task",
            workspace_action="retry_workspace_task",
            denied_code="task_retry_denied",
            denied_message="The current session cannot retry this task.",
        )
        allowed_actions = host.get_task_allowed_actions(source_task.task_id)
        if not allowed_actions.retry:
            raise service_error(
                409,
                code="task_retry_denied",
                category="conflict",
                message="The task cannot be retried in its current state.",
            )

        created = self._repository.create_task(
            TaskCreateDraft(
                kind=source_task.kind,
                lane=_normalize_runtime_lane(source_task.lane),
                execution_mode=source_task.execution_mode,
                owner_user_id=source_task.owner_user_id,
                owner_display_name=source_task.owner_display_name,
                workspace_id=source_task.workspace_id,
                workspace_slug=source_task.workspace_slug,
                visibility_scope=source_task.visibility_scope,
                dataset_id=source_task.dataset_id,
                definition_id=source_task.definition_id,
                summary=f"Retry of task {source_task.task_id}: {source_task.summary}",
                worker_task_name=source_task.worker_task_name,
                request_ready=source_task.request_ready,
                submitted_from_active_dataset=source_task.submitted_from_active_dataset,
                submission_source=(
                    source_task.dispatch.submission_source
                    if source_task.dispatch is not None
                    else task_submission_source_for(
                        submitted_from_active_dataset=source_task.submitted_from_active_dataset,
                        dataset_id=source_task.dataset_id,
                    )
                ),
                simulation_setup=source_task.simulation_setup,
                post_processing_setup=source_task.post_processing_setup,
                upstream_task_id=source_task.upstream_task_id,
                retry_of_task_id=source_task.task_id,
            )
        )
        created_detail = host.get_task(created.task_id)
        retry_event = build_task_retry_event(
            source_task=source_task,
            replacement_task_id=created_detail.task_id,
            occurred_at=_generated_at(),
            actor_user_id=_session_user_id(self._session_repository.get_session_state()),
        )
        self._repository.append_task_event(source_task.task_id, retry_event)
        self._repository.append_task_event(
            created_detail.task_id,
            TaskEvent(
                event_key=f"task_retried:{retry_event.occurred_at}:source",
                event_type="task_retried",
                level="info",
                occurred_at=retry_event.occurred_at,
                message="Task was created as a retry of a previous terminal task.",
                metadata={
                    "retry_of_task_id": source_task.task_id,
                    "actor_user_id": _session_user_id(self._session_repository.get_session_state()),
                    "audit_action": "task.retried",
                },
            ),
        )
        self._merge_submission_metadata(
            created_detail,
            draft=TaskSubmissionDraft(
                kind=source_task.kind,
                dataset_id=source_task.dataset_id,
                definition_id=source_task.definition_id,
                summary=created_detail.summary,
                simulation_setup=source_task.simulation_setup,
                post_processing_setup=source_task.post_processing_setup,
                characterization_setup=source_task.characterization_setup,
                upstream_task_id=source_task.upstream_task_id,
            ),
            upstream_task=(
                host.get_task(created_detail.upstream_task_id)
                if created_detail.upstream_task_id is not None
                else None
            ),
        )
        self._append_audit_record(
            action_kind="task.retried",
            resource_id=str(created_detail.task_id),
            outcome="accepted",
            payload={
                "retry_of_task_id": source_task.task_id,
                "source_status": source_task.status,
                "lane": source_task.lane,
            },
        )
        self._enqueue_submitted_task_if_supported(
            created_detail,
            runtime_mode=session.runtime_mode,
        )
        return created_detail.task_id

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

    def _merge_lifecycle_audit_metadata(
        self,
        *,
        updated_task: TaskDetail,
        metadata: dict[str, object],
    ) -> None:
        if len(updated_task.events) == 0:
            return
        self._repository.merge_task_event_metadata(
            updated_task.task_id,
            updated_task.events[-1].event_key,
            metadata,
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

    def _authorize_task_action(
        self,
        session: SessionState,
        task: TaskDetail,
        *,
        own_action: str,
        workspace_action: str,
        denied_code: str,
        denied_message: str,
    ) -> None:
        self._authorization_service.authorize(
            session,
            own_action if task.owner_user_id == _session_user_id(session) else workspace_action,  # type: ignore[arg-type]
            resource=_task_resource(task),
            denied_code=denied_code,
            denied_message=denied_message,
        )


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


def _task_resource(task: TaskDetail):
    from src.app.domain.authorization import AuthorizationResourceEnvelope

    return AuthorizationResourceEnvelope(
        resource_kind="task",
        workspace_id=task.workspace_id,
        owner_user_id=task.owner_user_id,
        visibility_scope=task.visibility_scope,
        lifecycle_state="active",
    )


def _generated_at() -> str:
    return datetime.now(UTC).isoformat()
