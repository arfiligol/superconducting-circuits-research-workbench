from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from typing import Protocol

from app_backend.domain.datasets import (
    DatasetDetail,
    ResultTracePublicationDraft,
    ResultTracePublicationResult,
    SimulationResultPublicationDraft,
    SimulationResultPublicationRecord,
    SimulationResultPublicationResult,
)
from app_backend.domain.runtime_contracts.tasking import (
    ProcessorHeartbeat,
)
from app_backend.domain.session import SessionState
from app_backend.domain.tasks import (
    CharacterizationSetup,
    PostProcessingSetup,
    SimulationSetup,
    TaskAllowedActions,
    TaskDetail,
    TaskEvent,
    TaskEventHistoryQuery,
    TaskHistoryView,
    TaskLifecycleUpdate,
    TaskListQuery,
    TaskProcessorDetail,
    TaskProcessorRuntimeView,
    TaskPublicationSummary,
    TaskQueueAggregateSummary,
    TaskQueueRow,
    TaskQueueView,
    TaskResultAvailability,
    TaskResultHandoff,
    TaskSubmissionDraft,
    WorkerLaneSummary,
    build_task_dispatch,
)
from app_backend.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from app_backend.services.authorization_service import AuthorizationService
from app_backend.services.service_errors import ServiceFieldError, service_error
from app_backend.services.task_mutation_service import TaskMutationService
from app_backend.services.task_publication_service import TaskPublicationService


class TaskRepository(Protocol):
    def list_tasks(self) -> Sequence[TaskDetail]: ...

    def get_task(self, task_id: int) -> TaskDetail | None: ...

    def claim_next_queued_task(
        self,
        runner_id: str,
        claimed_at: str,
        workspace_id: str,
    ) -> TaskDetail | None: ...

    def get_task_history_view(self, task_id: int) -> TaskHistoryView | None: ...

    def list_task_events(self, task_id: int) -> Sequence[TaskEvent]: ...

    def update_task_lifecycle(self, update: TaskLifecycleUpdate) -> TaskDetail | None: ...


class TaskDatasetRepository(Protocol):
    def get_dataset(self, dataset_id: str) -> DatasetDetail | None: ...

    def get_simulation_result_publication_record(
        self,
        source_task_id: int,
    ) -> SimulationResultPublicationRecord | None: ...


class TaskCircuitDefinitionRepository(Protocol):
    def get_circuit_definition(self, definition_id: str) -> object | None: ...


class TaskSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class TaskProcessorSummaryRepository(Protocol):
    def list_lane_summaries(self, workspace_id: str) -> Sequence[WorkerLaneSummary]: ...

    def list_heartbeats(
        self,
        workspace_id: str | None = None,
    ) -> Sequence[ProcessorHeartbeat]: ...


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        session_repository: TaskSessionRepository,
        dataset_repository: TaskDatasetRepository,
        circuit_definition_repository: TaskCircuitDefinitionRepository,
        mutation_service: TaskMutationService,
        publication_service: TaskPublicationService,
        authorization_service: AuthorizationService | None = None,
        processor_summary_repository: TaskProcessorSummaryRepository | None = None,
    ) -> None:
        self._repository = repository
        self._session_repository = session_repository
        self._dataset_repository = dataset_repository
        self._circuit_definition_repository = circuit_definition_repository
        self._mutation_service = mutation_service
        self._publication_service = publication_service
        self._authorization_service = authorization_service or AuthorizationService(
            CasbinAuthorizationAdapter()
        )
        self._processor_summary_repository = processor_summary_repository

    def list_tasks(self, query: TaskListQuery) -> list[TaskDetail]:
        tasks = [
            self._normalize_task(task)
            for task in self._repository.list_tasks()
            if self._matches_query(task, query)
        ]
        return _sort_tasks(tasks)[: query.limit]

    def claim_next_queued_task(self, *, runner_id: str, claimed_at: str) -> TaskDetail | None:
        session = self._session_repository.get_session_state()
        task = self._repository.claim_next_queued_task(
            runner_id,
            claimed_at,
            session.workspace_id,
        )
        if task is None:
            return None
        return self.get_task(task.task_id)

    def get_queue_view(self, query: TaskListQuery) -> TaskQueueView:
        session = self._session_repository.get_session_state()
        visible_tasks = [
            self._normalize_task(task)
            for task in self._repository.list_tasks()
            if self._matches_query(task, query)
        ]
        sorted_tasks = _sort_tasks(visible_tasks)
        paged_tasks, next_cursor, prev_cursor = _paginate_tasks(sorted_tasks, query=query)
        rows = tuple(
            _build_queue_row(task, self._build_allowed_actions(task, session))
            for task in paged_tasks
        )
        aggregate_summary = _build_queue_aggregate_summary(sorted_tasks)
        return TaskQueueView(
            rows=rows,
            worker_summary=(
                tuple(self._processor_summary_repository.list_lane_summaries(session.workspace_id))
                if self._processor_summary_repository is not None
                and session.runtime_mode == "local"
                else ()
            ),
            aggregate_summary=aggregate_summary,
            total_count=len(sorted_tasks),
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            has_more=next_cursor is not None or prev_cursor is not None,
        )

    def get_processor_runtime_view(
        self,
        *,
        lane: str | None = None,
    ) -> TaskProcessorRuntimeView:
        session = self._session_repository.get_session_state()
        if self._processor_summary_repository is None or session.runtime_mode != "local":
            return TaskProcessorRuntimeView(processors=(), worker_summary=())
        heartbeats = tuple(
            heartbeat
            for heartbeat in self._processor_summary_repository.list_heartbeats(
                session.workspace_id
            )
            if lane is None or heartbeat.lane == lane
        )
        processors = tuple(_serialize_processor_heartbeat(heartbeat) for heartbeat in heartbeats)
        summary = tuple(
            summary
            for summary in self._processor_summary_repository.list_lane_summaries(
                session.workspace_id
            )
            if lane is None or summary.lane == lane
        )
        return TaskProcessorRuntimeView(processors=processors, worker_summary=summary)

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

    def get_circuit_definition(self, definition_id: str | None) -> object | None:
        if definition_id is None:
            return None
        return self._circuit_definition_repository.get_circuit_definition(definition_id)

    def get_task_result_handoff(self, task_id: int) -> TaskResultHandoff:
        return _build_result_handoff(self.get_task(task_id))

    def get_task_allowed_actions(self, task_id: int) -> TaskAllowedActions:
        task = self.get_task(task_id)
        session = self._session_repository.get_session_state()
        return self._build_allowed_actions(task, session)

    def get_task_publication_summary(self, task_id: int) -> TaskPublicationSummary:
        task = self.get_task(task_id)
        publication_record = self._dataset_repository.get_simulation_result_publication_record(
            task_id
        )
        if publication_record is not None:
            return TaskPublicationSummary(
                state="published",
                publish_allowed=False,
                publication_key=publication_record.publication_key,
                target_dataset_id=publication_record.target_dataset_id,
                target_design_id=publication_record.target_design_id,
                target_design_name=publication_record.target_design_name,
                published_trace_ids=publication_record.published_trace_ids,
                published_at=publication_record.published_at,
                source_task_id=publication_record.source_task_id,
                source_result_handle_ids=publication_record.source_result_handle_ids,
            )
        if task.publication_summary is not None:
            return task.publication_summary
        return self._build_default_publication_summary(task)

    def publish_simulation_result(
        self,
        task_id: int,
        draft: SimulationResultPublicationDraft,
        *,
        dataset_id: str | None = None,
    ) -> SimulationResultPublicationResult:
        return self._publication_service.publish_simulation_result(
            task_id,
            draft,
            dataset_id=dataset_id,
            host=self,
        )

    def publish_result_trace(
        self,
        task_id: int,
        draft: ResultTracePublicationDraft,
    ) -> ResultTracePublicationResult:
        return self._publication_service.publish_result_trace(
            task_id,
            draft,
            host=self,
        )

    def submit_task(self, draft: TaskSubmissionDraft) -> TaskDetail:
        return self.get_task(self._mutation_service.submit_task(draft))

    def cancel_task(self, task_id: int) -> TaskDetail:
        return self.get_task(self._mutation_service.cancel_task(task_id, host=self))

    def terminate_task(self, task_id: int) -> TaskDetail:
        return self.get_task(self._mutation_service.terminate_task(task_id, host=self))

    def retry_task(self, task_id: int) -> TaskDetail:
        return self.get_task(self._mutation_service.retry_task(task_id, host=self))

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
        if not _matches_status_filter(task, query.status_filter):
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
        resolved_scope = _resolve_scope_for_session(scope, session)
        if resolved_scope == "local":
            return task.visibility_scope == "local"
        if resolved_scope == "owned":
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

    def _build_default_publication_summary(self, task: TaskDetail) -> TaskPublicationSummary:
        default_dataset = (
            self._dataset_repository.get_dataset(task.dataset_id)
            if task.dataset_id is not None
            else None
        )
        state = self._session_repository.get_session_state()
        publish_allowed = False
        if default_dataset is not None and self._authorization_service.is_visible_dataset(
            default_dataset, state
        ):
            dataset_actions = self._authorization_service.build_dataset_allowed_actions(
                default_dataset,
                state,
            )
            publish_allowed = (
                dataset_actions.ingest_raw_data
                and task.kind in {"simulation", "post_processing"}
                and task.status == "completed"
                and _build_result_handoff(task).availability == "ready"
                and (task.kind != "simulation" or task.simulation_setup is not None)
            )
        return TaskPublicationSummary(
            state="not_published",
            publish_allowed=publish_allowed,
            source_task_id=task.task_id,
            source_result_handle_ids=tuple(
                handle.handle_id for handle in task.result_refs.result_handles
            ),
        )

    def _normalize_task(self, task: TaskDetail) -> TaskDetail:
        (
            simulation_setup,
            post_processing_setup,
            characterization_setup,
        ) = self._resolve_retry_contract_snapshot(
            task,
            seen_task_ids={task.task_id},
        )
        return replace(
            task,
            simulation_setup=simulation_setup,
            post_processing_setup=post_processing_setup,
            characterization_setup=characterization_setup,
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
    ) -> tuple[
        SimulationSetup | None,
        PostProcessingSetup | None,
        CharacterizationSetup | None,
    ]:
        simulation_setup = task.simulation_setup
        post_processing_setup = task.post_processing_setup
        characterization_setup = task.characterization_setup
        if task.retry_of_task_id is None or (
            simulation_setup is not None
            and post_processing_setup is not None
            and characterization_setup is not None
        ):
            return simulation_setup, post_processing_setup, characterization_setup

        if task.retry_of_task_id in seen_task_ids:
            return simulation_setup, post_processing_setup, characterization_setup

        retry_source = self._repository.get_task(task.retry_of_task_id)
        if retry_source is None:
            return simulation_setup, post_processing_setup, characterization_setup

        seen_task_ids.add(retry_source.task_id)
        (
            source_simulation_setup,
            source_post_processing_setup,
            source_characterization_setup,
        ) = self._resolve_retry_contract_snapshot(
            retry_source,
            seen_task_ids=seen_task_ids,
        )
        if simulation_setup is None:
            simulation_setup = source_simulation_setup
        if post_processing_setup is None:
            post_processing_setup = source_post_processing_setup
        if characterization_setup is None:
            characterization_setup = source_characterization_setup
        return simulation_setup, post_processing_setup, characterization_setup


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


def _paginate_tasks(
    tasks: Sequence[TaskDetail],
    *,
    query: TaskListQuery,
) -> tuple[tuple[TaskDetail, ...], str | None, str | None]:
    if query.after is not None and query.before is not None:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="after and before cannot be used together.",
        )
    start_index = 0
    end_index = len(tasks)
    if query.after is not None:
        cursor_index = _find_cursor_index(tasks, query.after)
        start_index = cursor_index + 1
        end_index = min(start_index + query.limit, len(tasks))
    elif query.before is not None:
        cursor_index = _find_cursor_index(tasks, query.before)
        end_index = cursor_index
        start_index = max(end_index - query.limit, 0)
    else:
        end_index = min(query.limit, len(tasks))
    paged = tuple(tasks[start_index:end_index])
    next_cursor = str(paged[-1].task_id) if end_index < len(tasks) and len(paged) > 0 else None
    prev_cursor = str(paged[0].task_id) if start_index > 0 and len(paged) > 0 else None
    return paged, next_cursor, prev_cursor


def _find_cursor_index(tasks: Sequence[TaskDetail], cursor: str) -> int:
    try:
        cursor_task_id = int(cursor)
    except ValueError as exc:
        raise service_error(
            400,
            code="request_validation_failed",
            category="validation_error",
            message="cursor must be a task_id string.",
        ) from exc
    for index, task in enumerate(tasks):
        if task.task_id == cursor_task_id:
            return index
    raise service_error(
        400,
        code="request_validation_failed",
        category="validation_error",
        message=f"cursor task {cursor_task_id} was not found in the current filter scope.",
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
        reconcile=task.reconcile,
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


def _matches_status_filter(task: TaskDetail, status_filter: str) -> bool:
    if status_filter == "all":
        return True
    if status_filter == "active":
        return task.status in {
            "queued",
            "dispatching",
            "running",
            "cancellation_requested",
            "cancelling",
            "termination_requested",
        }
    return task.status in {"completed", "failed", "cancelled", "terminated"}


def _build_queue_aggregate_summary(tasks: Sequence[TaskDetail]) -> TaskQueueAggregateSummary:
    pending = sum(1 for task in tasks if task.status in {"queued", "dispatching"})
    running = sum(
        1
        for task in tasks
        if task.status
        in {
            "running",
            "cancellation_requested",
            "cancelling",
            "termination_requested",
        }
    )
    completed = sum(1 for task in tasks if task.status == "completed")
    failed = sum(1 for task in tasks if task.status == "failed")
    cancelled = sum(1 for task in tasks if task.status == "cancelled")
    terminated = sum(1 for task in tasks if task.status == "terminated")
    result_ready = sum(1 for task in tasks if _result_availability_for(task) == "ready")
    return TaskQueueAggregateSummary(
        total=len(tasks),
        pending=pending,
        running=running,
        completed=completed,
        failed=failed,
        cancelled=cancelled,
        terminated=terminated,
        result_ready=result_ready,
    )


def _resolve_scope_for_session(scope: str, session: SessionState) -> str:
    if session.runtime_mode == "local":
        return "local"
    return scope


def _serialize_processor_heartbeat(heartbeat: ProcessorHeartbeat) -> TaskProcessorDetail:
    return TaskProcessorDetail(
        processor_id=heartbeat.processor_id,
        lane=heartbeat.lane,
        state=heartbeat.state,
        current_task_id=heartbeat.current_task_id,
        last_heartbeat_at=heartbeat.last_heartbeat_at.isoformat(),
        runtime_metadata=dict(heartbeat.runtime_metadata),
    )
