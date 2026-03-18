from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from typing import Protocol

from sc_core.tasking import evaluate_task_control_action, resolve_worker_task_route

from src.app.domain.audit import AuditRecord
from src.app.domain.datasets import DatasetDetail
from src.app.domain.session import SessionState
from src.app.domain.tasks import (
    PostProcessingSetup,
    SimulationSetup,
    TaskAllowedActions,
    TaskCreateDraft,
    TaskDetail,
    TaskEvent,
    TaskEventHistoryQuery,
    TaskHistoryView,
    TaskKind,
    TaskLifecycleUpdate,
    TaskListQuery,
    TaskQueueRow,
    TaskQueueView,
    TaskResultAvailability,
    TaskResultHandoff,
    TaskSubmissionDraft,
    WorkerLaneSummary,
    build_task_dispatch,
    build_task_retry_event,
    task_submission_source_for,
)
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.services.authorization_service import AuthorizationService
from src.app.services.service_errors import ServiceFieldError, service_error


class TaskRepository(Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...

    def get_task(self, task_id: int) -> TaskDetail | None: ...

    def get_task_history_view(self, task_id: int) -> TaskHistoryView | None: ...

    def list_task_events(self, task_id: int) -> Sequence[TaskEvent]: ...

    def create_task(self, draft: TaskCreateDraft) -> TaskDetail: ...

    def update_task_lifecycle(self, update: TaskLifecycleUpdate) -> TaskDetail | None: ...

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


class TaskDatasetRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...


class TaskCircuitDefinitionRepository(Protocol):
    def get_circuit_definition(self, definition_id: int) -> object | None: ...


class TaskSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class TaskAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class TaskProcessorSummaryRepository(Protocol):
    def list_lane_summaries(self, workspace_id: str) -> Sequence[WorkerLaneSummary]: ...


class TaskExecutionDriver(Protocol):
    def execute_submitted_task(self, task_id: int) -> None: ...


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        session_repository: TaskSessionRepository,
        dataset_repository: TaskDatasetRepository,
        circuit_definition_repository: TaskCircuitDefinitionRepository,
        authorization_service: AuthorizationService | None = None,
        audit_repository: TaskAuditRepository | None = None,
        processor_summary_repository: TaskProcessorSummaryRepository | None = None,
        execution_driver: TaskExecutionDriver | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._dataset_repository = dataset_repository
        self._circuit_definition_repository = circuit_definition_repository
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._audit_repository = audit_repository
        self._processor_summary_repository = processor_summary_repository
        self._execution_driver = execution_driver

    def set_execution_driver(self, execution_driver: TaskExecutionDriver | None) -> None:
        self._execution_driver = execution_driver

    def list_tasks(self, query: TaskListQuery) -> list[TaskDetail]:
        tasks = [
            self._normalize_task(task)
            for task in self._repository.list_tasks()
            if self._matches_query(task, query)
        ]
        return _sort_tasks(tasks)[: query.limit]

    def get_queue_view(self, query: TaskListQuery) -> TaskQueueView:
        session = self._session_repository.get_session_state()
        visible_tasks = [
            self._normalize_task(task)
            for task in self._repository.list_tasks()
            if self._matches_query(task, query)
        ]
        sorted_tasks = _sort_tasks(visible_tasks)
        rows = tuple(
            _build_queue_row(task, self._build_allowed_actions(task, session))
            for task in sorted_tasks[: query.limit]
        )
        visible_workspace_tasks = [
            self._normalize_task(task)
            for task in self._repository.list_tasks()
            if self._is_visible(
                task,
                session,
                scope="local" if session.runtime_mode == "local" else "workspace",
            )
        ]
        return TaskQueueView(
            rows=rows,
            worker_summary=_build_worker_summary(
                visible_tasks=visible_workspace_tasks,
                runtime_mode=session.runtime_mode,
                processor_summaries=(
                    self._processor_summary_repository.list_lane_summaries(session.workspace_id)
                    if self._processor_summary_repository is not None
                    and session.runtime_mode != "local"
                    else ()
                ),
            ),
            total_count=len(sorted_tasks),
            next_cursor=str(rows[-1].task_id)
            if len(sorted_tasks) > query.limit and len(rows) > 0
            else None,
            prev_cursor=None,
            has_more=len(sorted_tasks) > query.limit,
        )

    def get_task(self, task_id: int) -> TaskDetail:
        history = self._load_visible_task_history(task_id)
        return replace(
            history.task,
            events=tuple(
                _select_task_events(
                    history.task.events,
                    TaskEventHistoryQuery(
                        order="asc",
                        limit=history.event_count,
                    ),
                )
            ),
        )

    def get_task_result_handoff(self, task_id: int) -> TaskResultHandoff:
        return _build_result_handoff(self.get_task(task_id))

    def get_task_allowed_actions(self, task_id: int) -> TaskAllowedActions:
        task = self.get_task(task_id)
        session = self._session_repository.get_session_state()
        return self._build_allowed_actions(task, session)

    def submit_task(self, draft: TaskSubmissionDraft) -> TaskDetail:
        session = self._session_repository.get_session_state()
        if session.user is None:
            raise service_error(
                401,
                code="auth_required",
                category="auth_required",
                message="Submitting tasks requires an authenticated session.",
            )
        self._authorization_service.authorize(
            session,
            "submit_task",
            resource=_task_resource(session.workspace_id),
            denied_code="task_submit_denied",
            denied_message="The current session cannot submit tasks in the active workspace.",
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
        if draft.kind == "post_processing" and upstream_task is None:
            raise service_error(
                422,
                code="post_processing_upstream_required",
                category="validation",
                message="Post-processing tasks require upstream_task_id.",
            )

        if (
            resolved_dataset_id is not None
            and self._dataset_repository.get_dataset(resolved_dataset_id) is None
        ):
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {resolved_dataset_id} was not found.",
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

        owner_user_id = _session_user_id(session)
        owner_display_name = session.user.display_name if session.user is not None else "anonymous"
        submission_source = task_submission_source_for(
            submitted_from_active_dataset=submitted_from_active_dataset,
            dataset_id=resolved_dataset_id,
        )
        worker_route = resolve_worker_task_route(
            draft.kind,
            request_is_valid=True,
            has_trace_batch_id=False,
        )
        created_task = self._repository.create_task(
            TaskCreateDraft(
                kind=draft.kind,
                lane=worker_route.lane,
                execution_mode=worker_route.execution_mode,
                owner_user_id=owner_user_id,
                owner_display_name=owner_display_name,
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
                submission_source=submission_source,
                simulation_setup=draft.simulation_setup,
                post_processing_setup=draft.post_processing_setup,
                upstream_task_id=draft.upstream_task_id,
            )
        )
        detail = self.get_task(created_task.task_id)
        self._merge_submission_metadata(
            detail,
            draft=draft,
            upstream_task=upstream_task,
        )
        self._append_audit_record(
            action_kind="task.submitted",
            resource_id=str(detail.task_id),
            outcome="accepted",
            payload={
                "task_kind": detail.kind,
                "lane": detail.lane,
                "dataset_id": detail.dataset_id,
                "definition_id": detail.definition_id,
                "upstream_task_id": detail.upstream_task_id,
                "submission_source": detail.dispatch.submission_source if detail.dispatch else None,
            },
        )
        self._execute_submitted_task_if_supported(
            task_id=detail.task_id,
            task_kind=detail.kind,
            runtime_mode=session.runtime_mode,
        )
        return self.get_task(created_task.task_id)

    def cancel_task(self, task_id: int) -> TaskDetail:
        task = self.get_task(task_id)
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
        updated_task = self.update_task_lifecycle(
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
        return self.get_task(task_id)

    def terminate_task(self, task_id: int) -> TaskDetail:
        task = self.get_task(task_id)
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
        updated_task = self.update_task_lifecycle(
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
        return self.get_task(task_id)

    def retry_task(self, task_id: int) -> TaskDetail:
        source_task = self.get_task(task_id)
        session = self._session_repository.get_session_state()
        self._authorize_task_action(
            session,
            source_task,
            own_action="retry_own_task",
            workspace_action="retry_workspace_task",
            denied_code="task_retry_denied",
            denied_message="The current session cannot retry this task.",
        )
        allowed_actions = self._build_allowed_actions(source_task, session)
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
                lane=source_task.lane,
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
        created_detail = self.get_task(created.task_id)
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
                upstream_task_id=source_task.upstream_task_id,
            ),
            upstream_task=(
                self.get_task(created_detail.upstream_task_id)
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
        self._execute_submitted_task_if_supported(
            task_id=created_detail.task_id,
            task_kind=created_detail.kind,
            runtime_mode=session.runtime_mode,
        )
        return self.get_task(created_detail.task_id)

    def list_task_events(
        self,
        task_id: int,
        query: TaskEventHistoryQuery,
    ) -> list[TaskEvent]:
        return list(self.get_task_history(task_id, query).task.events)

    def get_task_history(
        self,
        task_id: int,
        query: TaskEventHistoryQuery,
    ) -> TaskHistoryView:
        history = self._load_visible_task_history(task_id)
        selected_events = tuple(_select_task_events(history.task.events, query))
        latest_event = (
            selected_events[0]
            if query.order == "desc" and len(selected_events) > 0
            else history.latest_event
        )
        return TaskHistoryView(
            task=replace(history.task, events=selected_events),
            event_count=history.event_count,
            latest_event=latest_event,
        )

    def update_task_lifecycle(self, update: TaskLifecycleUpdate) -> TaskDetail:
        detail = self._repository.get_task(update.task_id)
        if detail is None:
            raise service_error(
                404,
                code="task_not_found",
                category="not_found",
                message=f"Task {update.task_id} was not found.",
            )

        field_errors = _validate_task_lifecycle_update(update)
        if len(field_errors) > 0:
            raise service_error(
                422,
                code="task_lifecycle_update_invalid",
                category="validation",
                message="Task lifecycle update is invalid.",
                field_errors=field_errors,
            )

        enriched_update = replace(
            update,
            dispatch=build_task_dispatch(
                task_id=detail.task_id,
                worker_task_name=detail.worker_task_name,
                task_status=update.status,
                submitted_from_active_dataset=detail.submitted_from_active_dataset,
                dataset_id=detail.dataset_id,
                accepted_at=detail.submitted_at,
                last_updated_at=update.progress_updated_at,
                current_dispatch=detail.dispatch,
            ),
        )
        updated_task = self._repository.update_task_lifecycle(enriched_update)
        if updated_task is None:
            raise service_error(
                404,
                code="task_not_found",
                category="not_found",
                message=f"Task {update.task_id} was not found.",
            )
        return self.get_task(updated_task.task_id)

    def _load_visible_task_history(self, task_id: int) -> TaskHistoryView:
        history = self._repository.get_task_history_view(task_id)
        session = self._session_repository.get_session_state()
        if history is None or not self._is_visible(history.task, session, scope="workspace"):
            raise service_error(
                404,
                code="task_not_found",
                category="not_found",
                message=f"Task {task_id} was not found.",
            )
        normalized_task = self._normalize_task(history.task)
        latest_event_candidates = _select_task_events(
            normalized_task.events,
            TaskEventHistoryQuery(order="desc", limit=1),
        )
        return TaskHistoryView(
            task=normalized_task,
            event_count=len(normalized_task.events),
            latest_event=latest_event_candidates[0] if len(latest_event_candidates) > 0 else None,
        )

    def _matches_query(self, task: TaskDetail, query: TaskListQuery) -> bool:
        session = self._session_repository.get_session_state()
        if not self._is_visible(task, session, scope=query.scope):
            return False
        if query.status is not None and task.status != query.status:
            return False
        if query.lane is not None and task.lane != query.lane:
            return False
        if query.dataset_id is not None and task.dataset_id != query.dataset_id:
            return False
        if query.search_query is None:
            return True
        needle = query.search_query.casefold()
        return (
            needle in task.summary.casefold()
            or needle in task.owner_display_name.casefold()
            or needle in str(task.task_id)
        )

    def _is_visible(
        self,
        task: TaskDetail,
        session: SessionState,
        *,
        scope: str,
    ) -> bool:
        if not self._authorization_service.is_visible_task(task, session):
            return False
        if session.runtime_mode == "local":
            return task.visibility_scope == "local"
        if scope == "owned":
            return task.owner_user_id == _session_user_id(session)
        return True

    def _build_allowed_actions(
        self,
        task: TaskDetail,
        session: SessionState,
    ) -> TaskAllowedActions:
        runtime_actions = _build_runtime_allowed_actions(task)
        authorization_actions = self._authorization_service.build_task_allowed_actions(
            task, session
        )
        rejection_reason = (
            runtime_actions.rejection_reason or authorization_actions.rejection_reason
        )
        return TaskAllowedActions(
            attach=runtime_actions.attach and authorization_actions.attach,
            cancel=runtime_actions.cancel and authorization_actions.cancel,
            terminate=runtime_actions.terminate and authorization_actions.terminate,
            retry=runtime_actions.retry and authorization_actions.retry,
            rejection_reason=rejection_reason,
        )

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

    def _normalize_task(self, task: TaskDetail) -> TaskDetail:
        simulation_setup, post_processing_setup = self._resolve_retry_contract_snapshot(
            task,
            seen_task_ids={task.task_id},
        )
        return replace(
            task,
            simulation_setup=simulation_setup,
            post_processing_setup=post_processing_setup,
            dispatch=build_task_dispatch(
                task_id=task.task_id,
                worker_task_name=task.worker_task_name,
                task_status=task.status,
                submitted_from_active_dataset=task.submitted_from_active_dataset,
                dataset_id=task.dataset_id,
                accepted_at=task.submitted_at,
                last_updated_at=task.progress.updated_at,
                current_dispatch=task.dispatch,
            ),
            events=tuple(
                _select_task_events(
                    task.events,
                    TaskEventHistoryQuery(order="asc", limit=max(len(task.events), 1)),
                )
            ),
        )

    def _resolve_retry_contract_snapshot(
        self,
        task: TaskDetail,
        *,
        seen_task_ids: set[int],
    ) -> tuple[SimulationSetup | None, PostProcessingSetup | None]:
        simulation_setup = task.simulation_setup
        post_processing_setup = task.post_processing_setup
        if task.retry_of_task_id is None or (
            simulation_setup is not None and post_processing_setup is not None
        ):
            return simulation_setup, post_processing_setup

        if task.retry_of_task_id in seen_task_ids:
            return simulation_setup, post_processing_setup

        retry_source = self._repository.get_task(task.retry_of_task_id)
        if retry_source is None:
            return simulation_setup, post_processing_setup

        seen_task_ids.add(retry_source.task_id)
        source_simulation_setup, source_post_processing_setup = (
            self._resolve_retry_contract_snapshot(
                retry_source,
                seen_task_ids=seen_task_ids,
            )
        )
        if simulation_setup is None:
            simulation_setup = source_simulation_setup
        if post_processing_setup is None:
            post_processing_setup = source_post_processing_setup
        return simulation_setup, post_processing_setup

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
            downstream_task_ids = tuple(
                sorted({*upstream_task.downstream_task_ids, task.task_id})
            )
            self._repository.merge_task_event_metadata(
                upstream_task.task_id,
                upstream_task.events[0].event_key,
                {
                    "downstream_task_ids": json.dumps(list(downstream_task_ids)),
                    "audit_action": "task.submitted",
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

    def _execute_submitted_task_if_supported(
        self,
        *,
        task_id: int,
        task_kind: TaskKind,
        runtime_mode: str,
    ) -> None:
        if self._execution_driver is None:
            return
        if runtime_mode != "local":
            return
        self._execution_driver.execute_submitted_task(task_id)

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
        if not self._is_visible(upstream_task, session, scope="workspace"):
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


def _default_task_summary(task_kind: TaskKind, dataset_id: str | None) -> str:
    if dataset_id is None:
        return f"{task_kind.replace('_', ' ')} task accepted by rewrite scaffold."
    return f"{task_kind.replace('_', ' ')} task accepted for dataset {dataset_id}."


def _submission_contract_metadata(
    draft: TaskSubmissionDraft,
) -> dict[str, object]:
    metadata: dict[str, object] = {}
    if draft.simulation_setup is not None:
        metadata["simulation_setup"] = json.dumps(
            _serialize_simulation_setup(draft.simulation_setup)
        )
    if draft.post_processing_setup is not None:
        metadata["post_processing_setup"] = json.dumps(
            _serialize_post_processing_setup(draft.post_processing_setup)
        )
    if draft.upstream_task_id is not None:
        metadata["upstream_task_id"] = draft.upstream_task_id
    return metadata


def _serialize_simulation_setup(setup: SimulationSetup) -> dict[str, object]:
    return setup.to_mapping()


def _serialize_post_processing_setup(setup: PostProcessingSetup) -> dict[str, object]:
    return setup.to_mapping()


def _session_user_id(session: SessionState) -> str:
    if session.user is None:
        return "anonymous"
    return session.user.user_id


def _validate_task_lifecycle_update(
    update: TaskLifecycleUpdate,
) -> tuple[ServiceFieldError, ...]:
    field_errors: list[ServiceFieldError] = []
    if not 0 <= update.progress_percent_complete <= 100:
        field_errors.append(
            ServiceFieldError(
                field="progress_percent_complete",
                message="progress_percent_complete must be between 0 and 100.",
            )
        )
    if update.status == "queued" and update.progress_percent_complete != 0:
        field_errors.append(
            ServiceFieldError(
                field="progress_percent_complete",
                message="Queued tasks must report 0 percent_complete.",
            )
        )
    if update.status == "dispatching" and update.progress_percent_complete != 0:
        field_errors.append(
            ServiceFieldError(
                field="progress_percent_complete",
                message="Dispatching tasks must report 0 percent_complete.",
            )
        )
    if (
        update.status
        in {"running", "cancellation_requested", "cancelling", "termination_requested"}
        and update.progress_percent_complete == 100
    ):
        field_errors.append(
            ServiceFieldError(
                field="progress_percent_complete",
                message="Active runtime tasks cannot report 100 percent_complete.",
            )
        )
    if update.status == "completed" and update.progress_percent_complete != 100:
        field_errors.append(
            ServiceFieldError(
                field="progress_percent_complete",
                message="Completed tasks must report 100 percent_complete.",
            )
        )
    if len(update.progress_summary.strip()) == 0:
        field_errors.append(
            ServiceFieldError(
                field="progress_summary",
                message="progress_summary must not be empty.",
            )
        )
    if len(update.progress_updated_at.strip()) == 0:
        field_errors.append(
            ServiceFieldError(
                field="progress_updated_at",
                message="progress_updated_at must not be empty.",
            )
        )
    return tuple(field_errors)


def _select_task_events(
    events: Sequence[TaskEvent],
    query: TaskEventHistoryQuery,
) -> list[TaskEvent]:
    filtered = [
        _redact_task_event(event)
        for event in events
        if query.event_type is None or event.event_type == query.event_type
    ]
    filtered.sort(
        key=lambda event: (event.occurred_at, event.event_key),
        reverse=query.order == "desc",
    )
    return filtered[: query.limit]


def _redact_task_event(event: TaskEvent) -> TaskEvent:
    safe_metadata = {
        key: value for key, value in event.metadata.items() if not _is_sensitive_event_field(key)
    }
    return replace(event, metadata=safe_metadata)


def _is_sensitive_event_field(field_name: str) -> bool:
    sensitive_tokens = (
        "secret",
        "token",
        "password",
        "credential",
        "payload_body",
        "request_body",
        "connection_string",
        "store_uri",
    )
    normalized = field_name.lower()
    return any(token in normalized for token in sensitive_tokens)


def _sort_tasks(tasks: Sequence[TaskDetail]) -> list[TaskDetail]:
    return sorted(
        tasks,
        key=lambda task: (_task_priority(task), task.progress.updated_at, task.task_id),
        reverse=True,
    )


def _task_priority(task: TaskDetail) -> int:
    if task.status in {
        "dispatching",
        "running",
        "cancellation_requested",
        "cancelling",
        "termination_requested",
        "queued",
    }:
        return 2
    if task.control_state != "none":
        return 1
    return 0


def _build_queue_row(task: TaskDetail, allowed_actions: TaskAllowedActions) -> TaskQueueRow:
    return TaskQueueRow(
        task_id=task.task_id,
        summary=task.summary,
        status=task.status,
        control_state=task.control_state,
        lane=task.lane,
        task_kind=task.kind,
        owner_display_name=task.owner_display_name,
        visibility_scope=task.visibility_scope,
        dataset_id=task.dataset_id,
        definition_id=task.definition_id,
        updated_at=task.progress.updated_at,
        result_availability=_result_availability_for(task),
        allowed_actions=allowed_actions,
    )


def _build_runtime_allowed_actions(task: TaskDetail) -> TaskAllowedActions:
    if task.status in {"completed", "failed", "cancelled", "terminated"}:
        return TaskAllowedActions(
            attach=True,
            cancel=False,
            terminate=False,
            retry=True,
            rejection_reason="task_already_terminal",
        )
    if task.control_state == "termination_requested":
        return TaskAllowedActions(
            attach=True,
            cancel=False,
            terminate=False,
            retry=False,
            rejection_reason="termination_requested",
        )
    if task.status == "cancelling":
        return TaskAllowedActions(
            attach=True,
            cancel=False,
            terminate=True,
            retry=False,
            rejection_reason="cancellation_in_progress",
        )
    if task.control_state == "cancellation_requested":
        return TaskAllowedActions(
            attach=True,
            cancel=False,
            terminate=True,
            retry=False,
            rejection_reason="cancellation_requested",
        )
    if task.status == "running":
        return TaskAllowedActions(
            attach=True,
            cancel=True,
            terminate=True,
            retry=False,
        )
    if task.status == "dispatching":
        return TaskAllowedActions(
            attach=True,
            cancel=True,
            terminate=False,
            retry=False,
        )
    return TaskAllowedActions(
        attach=True,
        cancel=True,
        terminate=False,
        retry=False,
    )


def _build_result_handoff(task: TaskDetail) -> TaskResultHandoff:
    return TaskResultHandoff(
        availability=_result_availability_for(task),
        primary_result_handle_id=(
            task.result_refs.result_handles[0].handle_id
            if len(task.result_refs.result_handles) > 0
            else None
        ),
        result_handle_count=len(task.result_refs.result_handles),
        trace_payload_available=task.result_refs.trace_payload is not None,
    )


def _result_availability_for(task: TaskDetail) -> TaskResultAvailability:
    if task.result_refs.trace_payload is not None:
        return "ready"
    if any(handle.status == "materialized" for handle in task.result_refs.result_handles):
        return "ready"
    if task.status in {"completed", "failed", "cancelled", "terminated"}:
        return "none"
    return "pending"


def _build_worker_summary(
    *,
    visible_tasks: Sequence[TaskDetail],
    runtime_mode: str,
    processor_summaries: Sequence[WorkerLaneSummary],
) -> tuple[WorkerLaneSummary, ...]:
    if runtime_mode == "local":
        return _build_local_worker_summary(visible_tasks)
    if len(processor_summaries) > 0:
        return tuple(processor_summaries)
    summaries: list[WorkerLaneSummary] = []
    for lane in ("simulation", "characterization"):
        lane_tasks = [task for task in visible_tasks if task.lane == lane]
        busy_processors = sum(1 for task in lane_tasks if task.status in {"dispatching", "running"})
        degraded_processors = sum(
            1 for task in lane_tasks if task.status == "termination_requested"
        )
        draining_processors = sum(
            1 for task in lane_tasks if task.status in {"cancellation_requested", "cancelling"}
        )
        summaries.append(
            WorkerLaneSummary(
                lane=lane,
                healthy_processors=max(
                    1 - min(busy_processors + degraded_processors + draining_processors, 1), 0
                ),
                busy_processors=busy_processors,
                degraded_processors=degraded_processors,
                draining_processors=draining_processors,
                offline_processors=0,
            )
        )
    return tuple(summaries)


def _build_local_worker_summary(
    visible_tasks: Sequence[TaskDetail],
) -> tuple[WorkerLaneSummary, ...]:
    active_statuses = {"dispatching", "running"}
    draining_statuses = {"cancellation_requested", "cancelling"}
    summaries: list[WorkerLaneSummary] = []
    lane_capacity = {"simulation": 1, "characterization": 0}
    lane_order = ("simulation", "characterization")
    for lane in lane_order:
        lane_tasks = [task for task in visible_tasks if task.lane == lane]
        busy_processors = min(
            sum(1 for task in lane_tasks if task.status in active_statuses),
            lane_capacity[lane],
        )
        degraded_processors = min(
            sum(1 for task in lane_tasks if task.status == "termination_requested"),
            max(lane_capacity[lane] - busy_processors, 0),
        )
        draining_processors = min(
            sum(1 for task in lane_tasks if task.status in draining_statuses),
            max(lane_capacity[lane] - busy_processors - degraded_processors, 0),
        )
        healthy_processors = max(
            lane_capacity[lane] - busy_processors - degraded_processors - draining_processors,
            0,
        )
        offline_processors = 1 if lane_capacity[lane] == 0 else 0
        summaries.append(
            WorkerLaneSummary(
                lane=lane,  # type: ignore[arg-type]
                healthy_processors=healthy_processors,
                busy_processors=busy_processors,
                degraded_processors=degraded_processors,
                draining_processors=draining_processors,
                offline_processors=offline_processors,
            )
        )
    return tuple(summaries)


def _workspace_resource(workspace_id: str):
    from src.app.domain.authorization import AuthorizationResourceEnvelope

    return AuthorizationResourceEnvelope(
        resource_kind="workspace",
        workspace_id=workspace_id,
        owner_user_id=None,
        visibility_scope="workspace",
        lifecycle_state="active",
    )


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


def _generated_at() -> str:
    return datetime.now(UTC).isoformat()
