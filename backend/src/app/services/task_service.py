from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Protocol

from sc_core.tasking import (
    ProcessorHeartbeat,
    evaluate_task_control_action,
    resolve_worker_task_route,
)

from src.app.domain.audit import AuditRecord
from src.app.domain.datasets import (
    CharacterizationAnalysisRegistryRow,
    DatasetDetail,
    DesignBrowseRow,
    ResultTracePublicationDraft,
    ResultTracePublicationResult,
    SimulationResultPublicationDraft,
    SimulationResultPublicationRecord,
    SimulationResultPublicationResult,
    TraceMetadataSummary,
)
from src.app.domain.result_traces import (
    ResultTraceSelection,
)
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
    TaskEventHistoryQuery,
    TaskHistoryView,
    TaskKind,
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
    build_task_retry_event,
    task_submission_source_for,
)
from src.app.infrastructure.audit_records import build_audit_record
from src.app.infrastructure.casbin_authorization import CasbinAuthorizationAdapter
from src.app.infrastructure.persisted_runtime import (
    available_sources_for_task_family,
    port_options_for_task,
)
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

    def get_design(self, dataset_id: str, design_id: str) -> DesignBrowseRow | None: ...

    def list_trace_metadata(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[TraceMetadataSummary]: ...

    def list_characterization_analysis_registry(
        self,
        dataset_id: str,
        design_id: str,
    ) -> Sequence[CharacterizationAnalysisRegistryRow]: ...

    def get_simulation_result_publication_record(
        self,
        source_task_id: int,
    ) -> SimulationResultPublicationRecord | None: ...

    def publish_simulation_result(
        self,
        *,
        task: TaskDetail,
        dataset_id: str,
        draft: SimulationResultPublicationDraft,
    ) -> SimulationResultPublicationResult | None: ...

    def publish_result_trace(
        self,
        *,
        task: TaskDetail,
        basis_task: TaskDetail,
        dataset: DatasetDetail,
        design: DesignBrowseRow,
        draft: ResultTracePublicationDraft,
    ) -> ResultTracePublicationResult | None: ...


class TaskCircuitDefinitionRepository(Protocol):
    def get_circuit_definition(self, definition_id: str) -> object | None: ...


class TaskSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class TaskAuditRepository(Protocol):
    def append(self, record: AuditRecord) -> None: ...


class TaskProcessorSummaryRepository(Protocol):
    def list_lane_summaries(self, workspace_id: str) -> Sequence[WorkerLaneSummary]: ...

    def list_heartbeats(
        self,
        workspace_id: str | None = None,
    ) -> Sequence[ProcessorHeartbeat]: ...


class TaskQueueDispatcher(Protocol):
    def enqueue_submitted_task(self, task: TaskDetail) -> TaskDispatchReceipt: ...


@dataclass(frozen=True)
class _ResultTraceValidationContext:
    task: TaskDetail
    basis_task: TaskDetail
    port_options: dict[int, str]
    sweep_count: int
    has_parameter_sweep: bool


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
        queue_dispatcher: TaskQueueDispatcher | None = None,
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
        self._queue_dispatcher = queue_dispatcher

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
        paged_tasks, next_cursor, prev_cursor = _paginate_tasks(sorted_tasks, query=query)
        rows = tuple(
            _build_queue_row(task, self._build_allowed_actions(task, session))
            for task in paged_tasks
        )
        aggregate_summary = _build_queue_aggregate_summary(sorted_tasks)
        return TaskQueueView(
            rows=rows,
            worker_summary=(
                tuple(
                    self._processor_summary_repository.list_lane_summaries(session.workspace_id)
                )
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
        task = self.get_task(task_id)
        state = self._session_repository.get_session_state()
        self._ensure_publishable_simulation_task(task)
        source_dataset_id = task.dataset_id
        if source_dataset_id is None:
            raise service_error(
                422,
                code="simulation_result_publish_target_required",
                category="validation",
                message="Simulation result publication requires a source dataset binding.",
            )
        if dataset_id is not None and dataset_id != source_dataset_id:
            raise service_error(
                409,
                code="simulation_result_publish_target_unsupported",
                category="conflict",
                message=(
                    "Simulation result publication currently supports only "
                    "the source task dataset as the target."
                ),
            )
        target_dataset_id = source_dataset_id
        if target_dataset_id is None:
            raise service_error(
                422,
                code="simulation_result_publish_target_required",
                category="validation",
                message="dataset_id is required when the source task has no dataset binding.",
            )
        target_dataset = self._dataset_repository.get_dataset(target_dataset_id)
        if target_dataset is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {target_dataset_id} was not found.",
            )
        if not self._authorization_service.is_visible_dataset(target_dataset, state):
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {target_dataset_id} was not found.",
            )
        dataset_actions = self._authorization_service.build_dataset_allowed_actions(
            target_dataset,
            state,
        )
        if not dataset_actions.ingest_raw_data:
            raise service_error(
                403,
                code="simulation_result_publish_denied",
                category="permission_denied",
                message=(
                    "The active session cannot save simulation results "
                    "into the target dataset."
                ),
            )

        existing_publication = self.get_task_publication_summary(task_id)
        resolved_design = self._resolve_publication_design_target(
            target_dataset_id=target_dataset_id,
            draft=draft,
        )
        requested_design_id = resolved_design.design_id
        requested_design_name = resolved_design.name
        if existing_publication.state == "published":
            if (
                existing_publication.target_dataset_id == target_dataset_id
                and existing_publication.target_design_id == requested_design_id
            ):
                try:
                    result = self._dataset_repository.publish_simulation_result(
                        task=task,
                        dataset_id=target_dataset_id,
                        draft=SimulationResultPublicationDraft(
                            design_name=existing_publication.target_design_name
                            or requested_design_name,
                            design_id=requested_design_id,
                        ),
                    )
                except Exception as exc:
                    raise service_error(
                        500,
                        code="simulation_result_publication_persistence_failed",
                        category="persistence_error",
                        message="Simulation result publication could not be persisted.",
                    ) from exc
                if result is None:
                    raise service_error(
                        409,
                        code="simulation_result_publish_unavailable",
                        category="conflict",
                        message="Simulation result publish target could not be materialized.",
                    )
                return result
            raise service_error(
                409,
                code="simulation_result_already_published",
                category="conflict",
                message=(
                    "This simulation result was already published "
                    "to a different dataset/design target."
                ),
            )

        try:
            result = self._dataset_repository.publish_simulation_result(
                task=replace(task, publication_summary=existing_publication),
                dataset_id=target_dataset_id,
                draft=SimulationResultPublicationDraft(
                    design_name=requested_design_name,
                    design_id=requested_design_id,
                ),
            )
        except Exception as exc:
            raise service_error(
                500,
                code="simulation_result_publication_persistence_failed",
                category="persistence_error",
                message="Simulation result publication could not be persisted.",
            ) from exc
        if result is None:
            raise service_error(
                409,
                code="simulation_result_publish_unavailable",
                category="conflict",
                message="Simulation result publish target could not be materialized.",
            )
        if len(task.events) > 0:
            self._repository.merge_task_event_metadata(
                task.task_id,
                task.events[0].event_key,
                {
                    "publication_summary": json.dumps(
                        _serialize_publication_summary(
                            TaskPublicationSummary(
                                state="published",
                                publish_allowed=False,
                                publication_key=result.publication_key,
                                target_dataset_id=result.dataset.dataset_id,
                                target_design_id=result.design.design_id,
                                target_design_name=result.design.name,
                                published_trace_ids=tuple(
                                    trace.trace_id for trace in result.traces
                                ),
                                published_at=result.published_at,
                                source_task_id=task.task_id,
                                source_result_handle_ids=tuple(
                                    handle.handle_id
                                    for handle in task.result_refs.result_handles
                                ),
                            )
                        )
                    ),
                },
            )
        self._append_audit_record(
            action_kind="task.result_published",
            resource_id=str(task.task_id),
            outcome="completed",
            payload={
                "dataset_id": result.dataset.dataset_id,
                "design_id": result.design.design_id,
                "trace_ids": [trace.trace_id for trace in result.traces],
                "publication_key": result.publication_key,
                "state": result.state,
            },
        )
        return result

    def publish_result_trace(
        self,
        task_id: int,
        draft: ResultTracePublicationDraft,
    ) -> ResultTracePublicationResult:
        task = self.get_task(task_id)
        state = self._session_repository.get_session_state()
        self._ensure_publishable_result_task(task)
        basis_task = self._resolve_result_trace_basis_task(task)
        source_dataset_id = task.dataset_id
        if source_dataset_id is None:
            raise service_error(
                422,
                code="result_trace_publish_target_required",
                category="validation",
                message="Result trace publication requires a source dataset binding.",
            )
        target_dataset = self._dataset_repository.get_dataset(source_dataset_id)
        if target_dataset is None:
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {source_dataset_id} was not found.",
            )
        if not self._authorization_service.is_visible_dataset(target_dataset, state):
            raise service_error(
                404,
                code="dataset_not_found",
                category="not_found",
                message=f"Dataset {source_dataset_id} was not found.",
            )
        dataset_actions = self._authorization_service.build_dataset_allowed_actions(
            target_dataset,
            state,
        )
        if not dataset_actions.ingest_raw_data:
            raise service_error(
                403,
                code="result_trace_publish_denied",
                category="permission_denied",
                message="The active session cannot save result traces into the target dataset.",
            )
        resolved_design = self._resolve_publication_design_target(
            target_dataset_id=source_dataset_id,
            draft=SimulationResultPublicationDraft(design_id=draft.design_id),
        )
        existing_publication = self.get_task_publication_summary(task_id)
        if existing_publication.state == "published" and (
            existing_publication.target_dataset_id != source_dataset_id
            or existing_publication.target_design_id != resolved_design.design_id
        ):
            raise service_error(
                409,
                code="result_trace_publish_target_conflict",
                category="conflict",
                message=(
                    "This task already published traces to a different design target. "
                    "Choose the existing design or start from a different task."
                ),
            )
        self._validate_result_trace_selections(
            task=task,
            basis_task=basis_task,
            trace_keys=draft.trace_keys,
        )
        try:
            result = self._dataset_repository.publish_result_trace(
                task=task,
                basis_task=basis_task,
                dataset=target_dataset,
                design=resolved_design,
                draft=draft,
            )
        except ValueError as exc:
            raise service_error(
                409,
                code="result_trace_publish_unavailable",
                category="conflict",
                message="Result trace publish target could not be materialized.",
            ) from exc
        except Exception as exc:
            raise service_error(
                500,
                code="result_trace_publication_persistence_failed",
                category="persistence_error",
                message="Result trace publication could not be persisted.",
            ) from exc
        if result is None:
            raise service_error(
                409,
                code="result_trace_publish_unavailable",
                category="conflict",
                message="Result trace publish target could not be materialized.",
            )
        publication_summary = self.get_task_publication_summary(task_id)
        if len(task.events) > 0:
            self._repository.merge_task_event_metadata(
                task.task_id,
                task.events[0].event_key,
                {
                    "publication_summary": json.dumps(
                        _serialize_publication_summary(publication_summary)
                    ),
                },
            )
        self._append_audit_record(
            action_kind="task.result_trace_published",
            resource_id=str(task.task_id),
            outcome="completed",
            payload={
                "dataset_id": result.dataset.dataset_id,
                "design_id": result.design.design_id,
                "trace_ids": [trace.trace_id for trace in result.traces],
                "trace_keys": list(result.trace_keys),
                "publication_key": result.publication_key,
                "state": result.state,
            },
        )
        return result

    def _resolve_publication_design_target(
        self,
        *,
        target_dataset_id: str,
        draft: SimulationResultPublicationDraft,
    ) -> DesignBrowseRow:
        if draft.design_id is not None:
            design = self._dataset_repository.get_design(target_dataset_id, draft.design_id)
            if design is None:
                raise service_error(
                    404,
                    code="design_not_found",
                    category="not_found",
                    message=(
                        "The selected design is not available in the target dataset. "
                        "Create it first or choose an existing design."
                    ),
                )
            return design
        if draft.design_name is None:
            raise service_error(
                422,
                code="simulation_result_publish_target_required",
                category="validation",
                message="Simulation result publication requires design_id or design_name.",
            )
        return DesignBrowseRow(
            design_id=_build_publication_design_id(draft.design_name),
            dataset_id=target_dataset_id,
            name=draft.design_name,
            source_coverage={},
            compare_readiness="blocked",
            trace_count=0,
            updated_at="",
        )

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
                lane=_normalize_runtime_lane(worker_route.lane),
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
                characterization_setup=draft.characterization_setup,
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
        self._enqueue_submitted_task_if_supported(detail, runtime_mode=session.runtime_mode)
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
                characterization_setup=source_task.characterization_setup,
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
        self._enqueue_submitted_task_if_supported(
            created_detail,
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

    def _ensure_publishable_simulation_task(self, task: TaskDetail) -> None:
        if task.kind != "simulation":
            raise service_error(
                409,
                code="simulation_result_publish_task_invalid",
                category="conflict",
                message="Only simulation tasks can publish simulation results.",
            )
        if task.status != "completed":
            raise service_error(
                409,
                code="simulation_result_publish_not_ready",
                category="conflict",
                message="Only completed simulation tasks with ready results can be published.",
            )
        handoff = _build_result_handoff(task)
        if handoff.availability != "ready":
            raise service_error(
                409,
                code="simulation_result_publish_not_ready",
                category="conflict",
                message="Only completed simulation tasks with ready results can be published.",
            )
        if task.simulation_setup is None:
            raise service_error(
                409,
                code="simulation_result_publish_not_ready",
                category="conflict",
                message="Only completed simulation tasks with persisted setup can be published.",
            )

    def _ensure_publishable_result_task(self, task: TaskDetail) -> None:
        if task.kind not in {"simulation", "post_processing"}:
            raise service_error(
                409,
                code="result_trace_publish_task_invalid",
                category="conflict",
                message=(
                    "Only simulation and post-processing tasks can publish "
                    "result traces."
                ),
            )
        if task.status != "completed":
            raise service_error(
                409,
                code="result_trace_publish_not_ready",
                category="conflict",
                message="Only completed tasks with ready results can be published.",
            )
        handoff = _build_result_handoff(task)
        if handoff.availability != "ready":
            raise service_error(
                409,
                code="result_trace_publish_not_ready",
                category="conflict",
                message="Only completed tasks with ready results can be published.",
            )
        if task.kind == "simulation" and task.simulation_setup is None:
            raise service_error(
                409,
                code="result_trace_publish_not_ready",
                category="conflict",
                message="Only completed simulation tasks with persisted setup can be published.",
            )

    def _resolve_result_trace_basis_task(self, task: TaskDetail) -> TaskDetail:
        if task.kind == "simulation":
            if task.simulation_setup is None:
                raise service_error(
                    409,
                    code="result_trace_publish_not_ready",
                    category="conflict",
                    message="Simulation result publication requires persisted setup.",
                )
            return task
        if task.kind != "post_processing" or task.upstream_task_id is None:
            raise service_error(
                409,
                code="result_trace_publish_task_invalid",
                category="conflict",
                message=(
                    "Only simulation and post-processing tasks can publish "
                    "result traces."
                ),
            )
        upstream_task = self.get_task(task.upstream_task_id)
        if upstream_task.kind != "simulation" or upstream_task.simulation_setup is None:
            raise service_error(
                409,
                code="result_trace_publish_upstream_invalid",
                category="conflict",
                message=(
                    "Post-processing result publication requires an upstream "
                    "simulation task with persisted setup."
                ),
            )
        return upstream_task

    def _validate_result_trace_selections(
        self,
        *,
        task: TaskDetail,
        basis_task: TaskDetail,
        trace_keys: tuple[str, ...],
    ) -> None:
        if len(trace_keys) == 0:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="At least one trace_key is required.",
            )

        validation_context = _ResultTraceValidationContext(
            task=task,
            basis_task=basis_task,
            port_options=port_options_for_task(
                task,
                basis_task=basis_task,
                definition=self.get_circuit_definition(basis_task.definition_id),
            ),
            sweep_count=_result_trace_sweep_count(basis_task),
            has_parameter_sweep=len(basis_task.simulation_setup.parameter_sweeps) > 0,
        )

        for trace_key in trace_keys:
            self._validate_result_trace_selection(
                trace_key=trace_key,
                validation_context=validation_context,
            )

    def _validate_result_trace_selection(
        self,
        *,
        trace_key: str,
        validation_context: _ResultTraceValidationContext,
    ) -> None:
        try:
            selection = ResultTraceSelection.from_trace_key(trace_key)
        except ValueError as exc:
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=str(exc),
            ) from exc
        if selection.source not in available_sources_for_task_family(
            validation_context.task,
            selection.family,
        ):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message=(
                    f"source {selection.source} is not available for family "
                    f"{selection.family}."
                ),
            )
        if (
            selection.output_port not in validation_context.port_options
            or selection.input_port not in validation_context.port_options
        ):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="Requested trace selection ports are not available for this result.",
            )
        if selection.trace_mode_group != "base":
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="Only base trace selections are supported.",
            )
        if selection.output_mode != "mode_0" or selection.input_mode != "mode_0":
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="Only mode_0 trace selections are supported.",
            )
        if not validation_context.has_parameter_sweep:
            if selection.sweep_index is not None:
                raise service_error(
                    400,
                    code="request_validation_failed",
                    category="validation_error",
                    message="Requested trace selection does not expose parameter sweep points.",
                )
            return
        if (
            selection.sweep_index is None
            or selection.sweep_index < 0
            or selection.sweep_index >= validation_context.sweep_count
        ):
            raise service_error(
                400,
                code="request_validation_failed",
                category="validation_error",
                message="Requested trace selection parameter sweep point is invalid.",
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
                and (
                    task.kind != "simulation" or task.simulation_setup is not None
                )
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
        ) = (
            self._resolve_retry_contract_snapshot(
                retry_source,
                seen_task_ids=seen_task_ids,
            )
        )
        if simulation_setup is None:
            simulation_setup = source_simulation_setup
        if post_processing_setup is None:
            post_processing_setup = source_post_processing_setup
        if characterization_setup is None:
            characterization_setup = source_characterization_setup
        return simulation_setup, post_processing_setup, characterization_setup

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
        if self._queue_dispatcher is None:
            return
        if runtime_mode != "local":
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
            trace_id
            for trace_id in setup.selected_trace_ids
            if trace_id not in traces_by_id
        ]
        if len(missing_trace_ids) > 0:
            raise service_error(
                422,
                code="characterization_trace_selection_invalid",
                category="validation",
                message=(
                    "Selected traces must belong to the chosen design in the current dataset."
                ),
                field_errors=(
                    tuple(
                        ServiceFieldError(
                            field=f"characterization_setup.selected_trace_ids[{index}]",
                            message="Trace is not available in the selected design scope.",
                        )
                        for index, trace_id in enumerate(setup.selected_trace_ids)
                        if trace_id in set(missing_trace_ids)
                    )
                ),
            )
        registry_rows = tuple(
            self._dataset_repository.list_characterization_analysis_registry(
                dataset_id,
                setup.design_id,
            )
        )
        registry_row = next(
            (
                row
                for row in registry_rows
                if row.analysis_id.casefold() == setup.analysis_id.casefold()
            ),
            None,
        )
        if registry_row is None:
            raise service_error(
                422,
                code="characterization_analysis_invalid",
                category="validation",
                message="analysis_id is not recognized for the selected design.",
            )
        if registry_row.availability_state == "unavailable":
            raise service_error(
                409,
                code="characterization_analysis_unavailable",
                category="conflict",
                message=registry_row.trace_compatibility.summary,
            )
        if setup.analysis_id != "admittance_extraction":
            raise service_error(
                409,
                code="characterization_analysis_unsupported",
                category="conflict",
                message=(
                    "Local characterization currently supports only "
                    "the admittance_extraction analysis."
                ),
            )
        self._validate_admittance_characterization(
            setup=setup,
            selected_traces=tuple(traces_by_id[trace_id] for trace_id in setup.selected_trace_ids),
            registry_row=registry_row,
        )

    def _validate_admittance_characterization(
        self,
        *,
        setup: CharacterizationSetup,
        selected_traces: tuple[TraceMetadataSummary, ...],
        registry_row: CharacterizationAnalysisRegistryRow,
    ) -> None:
        if len(selected_traces) < 2:
            raise service_error(
                422,
                code="characterization_trace_selection_incompatible",
                category="validation",
                message=registry_row.trace_compatibility.summary,
            )
        if any(trace.trace_mode_group != "base" for trace in selected_traces):
            raise service_error(
                422,
                code="characterization_trace_selection_incompatible",
                category="validation",
                message=(
                    "Admittance extraction currently requires base-mode traces only."
                ),
            )
        if any(trace.family != "y_matrix" for trace in selected_traces):
            raise service_error(
                422,
                code="characterization_trace_selection_incompatible",
                category="validation",
                message="Admittance extraction currently requires Y-matrix traces.",
            )
        selected_sources = {trace.source_kind for trace in selected_traces}
        if "measurement" not in selected_sources or not (
            {"layout_simulation", "circuit_simulation"} & selected_sources
        ):
            raise service_error(
                422,
                code="characterization_trace_selection_incompatible",
                category="validation",
                message=(
                    "Admittance extraction requires one measurement trace and "
                    "one compatible simulation trace."
                ),
            )
        if "fit_window" not in setup.analysis_config:
            raise service_error(
                422,
                code="characterization_config_invalid",
                category="validation",
                message="characterization_setup.analysis_config.fit_window is required.",
            )
        fit_window = setup.analysis_config.get("fit_window")
        if (
            not isinstance(fit_window, list)
            or len(fit_window) != 2
            or not all(isinstance(value, int | float) for value in fit_window)
        ):
            raise service_error(
                422,
                code="characterization_config_invalid",
                category="validation",
                message=(
                    "characterization_setup.analysis_config.fit_window must be "
                    "an array of two numbers."
                ),
            )
        if float(fit_window[0]) >= float(fit_window[1]):
            raise service_error(
                422,
                code="characterization_config_invalid",
                category="validation",
                message=(
                    "characterization_setup.analysis_config.fit_window must be "
                    "strictly increasing."
                ),
            )
        residual_tolerance = setup.analysis_config.get("residual_tolerance")
        if not isinstance(residual_tolerance, int | float) or float(residual_tolerance) <= 0:
            raise service_error(
                422,
                code="characterization_config_invalid",
                category="validation",
                message=(
                    "characterization_setup.analysis_config.residual_tolerance "
                    "must be a positive number."
                ),
            )


def _default_task_summary(task_kind: TaskKind, dataset_id: str | None) -> str:
    if dataset_id is None:
        return f"{task_kind.replace('_', ' ')} task accepted by the local runtime."
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


def _serialize_publication_summary(summary: TaskPublicationSummary) -> dict[str, object]:
    return summary.to_mapping()


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


def _build_publication_design_id(design_name: str) -> str:
    slug = "-".join(
        token
        for token in "".join(
            character.lower() if character.isalnum() else " "
            for character in design_name
        ).split()
        if len(token) > 0
    )
    return f"design_{slug}" if len(slug) > 0 else "design_simulation_result"


def _result_trace_sweep_count(task: TaskDetail) -> int:
    total = 1
    for axis in task.simulation_setup.parameter_sweeps:
        total *= max(len(axis.values), 1)
    return total




def _workspace_resource(workspace_id: str):
    from src.app.domain.authorization import AuthorizationResourceEnvelope

    return AuthorizationResourceEnvelope(
        resource_kind="workspace",
        workspace_id=workspace_id,
        owner_user_id=None,
        visibility_scope="workspace",
        lifecycle_state="active",
    )


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


def _generated_at() -> str:
    return datetime.now(UTC).isoformat()
