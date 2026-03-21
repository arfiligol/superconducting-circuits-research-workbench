from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from sc_core.tasking import TaskExecutionMode, WorkerTaskName
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from src.app.domain.tasks import (
    TaskCreateDraft,
    TaskDetail,
    TaskDispatch,
    TaskDispatchStatus,
    TaskEvent,
    TaskEventLevel,
    TaskEventType,
    TaskKind,
    TaskLane,
    TaskProgress,
    TaskQueueBackend,
    TaskResultRefs,
    TaskStatus,
    TaskSubmissionSource,
    TaskVisibilityScope,
    build_task_dispatch,
    build_task_event_history,
    resolve_characterization_setup,
    resolve_downstream_task_ids,
    resolve_post_processing_setup,
    resolve_publication_summary,
    resolve_retry_of_task_id,
    resolve_simulation_setup,
    resolve_task_control_state,
    resolve_task_reconcile,
    resolve_upstream_task_id,
)
from src.app.infrastructure.persistence.models import (
    RewriteTaskDispatchRecord,
    RewriteTaskEventRecord,
    RewriteTaskRecord,
)


class SqliteRewriteTaskSnapshotRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def has_tasks(self) -> bool:
        with self._session_factory() as session:
            return session.scalar(select(func.count(RewriteTaskRecord.id))) != 0

    def list_tasks(self) -> tuple[TaskDetail, ...]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(RewriteTaskRecord).order_by(RewriteTaskRecord.task_id.asc())
            ).all()
            details: list[TaskDetail] = []
            changed = False
            for row in rows:
                dispatch_row, dispatch_changed = _upsert_dispatch_row(session, row)
                event_rows, event_changed = _upsert_task_events(
                    session,
                    row,
                    dispatch_row,
                )
                changed = changed or dispatch_changed or event_changed
                details.append(_to_task_detail(row, dispatch_row, event_rows))
            if changed:
                session.commit()
            return tuple(details)

    def get_task(self, task_id: int) -> TaskDetail | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteTaskRecord).where(RewriteTaskRecord.task_id == task_id)
            )
            if row is None:
                return None
            dispatch_row, dispatch_changed = _upsert_dispatch_row(session, row)
            event_rows, event_changed = _upsert_task_events(
                session,
                row,
                dispatch_row,
            )
            if dispatch_changed or event_changed:
                session.commit()
            return _to_task_detail(row, dispatch_row, event_rows)

    def list_task_events(self, task_id: int) -> tuple[TaskEvent, ...]:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteTaskRecord).where(RewriteTaskRecord.task_id == task_id)
            )
            if row is None:
                return ()
            dispatch_row, dispatch_changed = _upsert_dispatch_row(session, row)
            event_rows, event_changed = _upsert_task_events(
                session,
                row,
                dispatch_row,
            )
            if dispatch_changed or event_changed:
                session.commit()
            return _to_task_events(event_rows)

    def create_task(self, draft: TaskCreateDraft) -> TaskDetail:
        with self._session_factory() as session:
            next_task_id = session.scalar(select(func.max(RewriteTaskRecord.task_id))) or 305
            row = RewriteTaskRecord(
                task_id=next_task_id + 1,
                kind=draft.kind,
                lane=draft.lane,
                execution_mode=draft.execution_mode,
                status="queued",
                submitted_at="2026-03-12 10:30:00",
                owner_user_id=draft.owner_user_id,
                owner_display_name=draft.owner_display_name,
                workspace_id=draft.workspace_id,
                workspace_slug=draft.workspace_slug,
                visibility_scope=draft.visibility_scope,
                dataset_id=draft.dataset_id,
                definition_id=draft.definition_id,
                summary=draft.summary,
                queue_backend="rq_redis",
                worker_task_name=draft.worker_task_name,
                request_ready=draft.request_ready,
                submitted_from_active_dataset=draft.submitted_from_active_dataset,
                progress_phase="queued",
                progress_percent_complete=0,
                progress_summary="Task accepted by the local runtime.",
                progress_updated_at="2026-03-12 10:30:00",
            )
            session.add(row)
            session.flush()
            dispatch_row, _ = _upsert_dispatch_row(
                session,
                row,
                build_task_dispatch(
                    task_id=row.task_id,
                    worker_task_name=row.worker_task_name,
                    task_status=cast(TaskStatus, row.status),
                    submitted_from_active_dataset=row.submitted_from_active_dataset,
                    dataset_id=row.dataset_id,
                    accepted_at=row.submitted_at,
                    last_updated_at=row.progress_updated_at,
                    submission_source=draft.submission_source,
                ),
            )
            event_rows, _ = _upsert_task_events(
                session,
                row,
                dispatch_row,
            )
            session.commit()
            session.refresh(row)
            session.refresh(dispatch_row)
            return _to_task_detail(row, dispatch_row, event_rows)

    def save_task_snapshot(self, task: TaskDetail) -> TaskDetail:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteTaskRecord).where(RewriteTaskRecord.task_id == task.task_id)
            )
            if row is None:
                row = RewriteTaskRecord(task_id=task.task_id)
                session.add(row)

            row.kind = task.kind
            row.lane = task.lane
            row.execution_mode = task.execution_mode
            row.status = task.status
            row.submitted_at = task.submitted_at
            row.owner_user_id = task.owner_user_id
            row.owner_display_name = task.owner_display_name
            row.workspace_id = task.workspace_id
            row.workspace_slug = task.workspace_slug
            row.visibility_scope = task.visibility_scope
            row.dataset_id = task.dataset_id
            row.definition_id = task.definition_id
            row.summary = task.summary
            row.queue_backend = task.queue_backend
            row.worker_task_name = task.worker_task_name
            row.request_ready = task.request_ready
            row.submitted_from_active_dataset = task.submitted_from_active_dataset
            row.progress_phase = task.progress.phase
            row.progress_percent_complete = task.progress.percent_complete
            row.progress_summary = task.progress.summary
            row.progress_updated_at = task.progress.updated_at

            session.flush()
            dispatch_row, _ = _upsert_dispatch_row(
                session,
                row,
                build_task_dispatch(
                    task_id=task.task_id,
                    worker_task_name=task.worker_task_name,
                    task_status=task.status,
                    submitted_from_active_dataset=task.submitted_from_active_dataset,
                    dataset_id=task.dataset_id,
                    accepted_at=task.submitted_at,
                    last_updated_at=task.progress.updated_at,
                    current_dispatch=task.dispatch,
                ),
            )
            event_rows, _ = _upsert_task_events(
                session,
                row,
                dispatch_row,
                result_refs=task.result_refs,
            )
            session.commit()
            session.refresh(row)
            session.refresh(dispatch_row)
            return _to_task_detail(row, dispatch_row, event_rows, result_refs=task.result_refs)

    def merge_task_event_metadata(
        self,
        task_id: int,
        event_key: str,
        metadata: Mapping[str, object],
    ) -> None:
        with self._session_factory() as session:
            row = session.scalar(
                select(RewriteTaskEventRecord).where(
                    RewriteTaskEventRecord.task_id == task_id,
                    RewriteTaskEventRecord.event_key == event_key,
                )
            )
            if row is None:
                return
            merged_metadata = dict(row.metadata_json)
            changed = False
            for key, value in metadata.items():
                if merged_metadata.get(key) != value:
                    merged_metadata[key] = value
                    changed = True
            if not changed:
                return
            row.metadata_json = merged_metadata
            session.commit()

    def append_task_event(
        self,
        task_id: int,
        event: TaskEvent,
    ) -> None:
        with self._session_factory() as session:
            existing = session.scalar(
                select(RewriteTaskEventRecord).where(
                    RewriteTaskEventRecord.task_id == task_id,
                    RewriteTaskEventRecord.event_key == event.event_key,
                )
            )
            if existing is not None:
                _apply_task_event_row(existing, event)
                session.commit()
                return
            row = RewriteTaskEventRecord(task_id=task_id, event_key=event.event_key)
            _apply_task_event_row(row, event)
            session.add(row)
            session.commit()


def _upsert_dispatch_row(
    session: Session,
    task_row: RewriteTaskRecord,
    dispatch: TaskDispatch | None = None,
) -> tuple[RewriteTaskDispatchRecord, bool]:
    row = session.scalar(
        select(RewriteTaskDispatchRecord).where(
            RewriteTaskDispatchRecord.task_id == task_row.task_id
        )
    )
    desired_dispatch = dispatch or build_task_dispatch(
        task_id=task_row.task_id,
        worker_task_name=task_row.worker_task_name,
        task_status=cast(TaskStatus, task_row.status),
        submitted_from_active_dataset=task_row.submitted_from_active_dataset,
        dataset_id=task_row.dataset_id,
        accepted_at=task_row.submitted_at,
        last_updated_at=task_row.progress_updated_at,
        current_dispatch=_to_task_dispatch(
            row,
            lane=cast(TaskLane, task_row.lane),
            events=(),
        ),
    )
    changed = False
    if row is None:
        row = RewriteTaskDispatchRecord(task_id=task_row.task_id)
        session.add(row)
        changed = True

    if row.dispatch_key != desired_dispatch.dispatch_key:
        row.dispatch_key = desired_dispatch.dispatch_key
        changed = True
    if row.status != desired_dispatch.status:
        row.status = desired_dispatch.status
        changed = True
    if row.submission_source != desired_dispatch.submission_source:
        row.submission_source = desired_dispatch.submission_source
        changed = True
    if row.accepted_at != desired_dispatch.accepted_at:
        row.accepted_at = desired_dispatch.accepted_at
        changed = True
    if row.last_updated_at != desired_dispatch.last_updated_at:
        row.last_updated_at = desired_dispatch.last_updated_at
        changed = True

    session.flush()
    return row, changed


def _upsert_task_events(
    session: Session,
    task_row: RewriteTaskRecord,
    dispatch_row: RewriteTaskDispatchRecord,
    *,
    result_refs: TaskResultRefs | None = None,
) -> tuple[tuple[RewriteTaskEventRecord, ...], bool]:
    desired_events = build_task_event_history(
        _to_task_detail(task_row, dispatch_row, (), result_refs=result_refs)
    )
    existing_rows: list[RewriteTaskEventRecord] = list(
        session.scalars(
        select(RewriteTaskEventRecord)
        .where(RewriteTaskEventRecord.task_id == task_row.task_id)
        .order_by(RewriteTaskEventRecord.occurred_at.asc(), RewriteTaskEventRecord.id.asc())
        ).all()
    )
    existing_by_key = {row.event_key: row for row in existing_rows}
    changed = False
    for event in desired_events:
        row = existing_by_key.get(event.event_key)
        if row is None:
            row = RewriteTaskEventRecord(task_id=task_row.task_id, event_key=event.event_key)
            session.add(row)
            existing_rows.append(row)
            existing_by_key[event.event_key] = row
            changed = True
            changed = _apply_task_event_row(row, event) or changed
            continue
        if result_refs is not None:
            changed = _apply_task_event_row(row, event) or changed

    session.flush()
    existing_rows.sort(key=lambda row: (row.occurred_at, row.id or 0))
    return tuple(existing_rows), changed


def _apply_task_event_row(row: RewriteTaskEventRecord, event: TaskEvent) -> bool:
    changed = False
    if row.event_type != event.event_type:
        row.event_type = event.event_type
        changed = True
    if row.level != event.level:
        row.level = event.level
        changed = True
    if row.occurred_at != event.occurred_at:
        row.occurred_at = event.occurred_at
        changed = True
    if row.message != event.message:
        row.message = event.message
        changed = True
    merged_metadata = dict(row.metadata_json or {})
    merged_metadata.update(cast(dict[str, object], event.metadata))
    if row.metadata_json != merged_metadata:
        row.metadata_json = merged_metadata
        changed = True
    return changed


def _to_task_dispatch(
    dispatch_row: RewriteTaskDispatchRecord | None,
    *,
    lane: TaskLane,
    events: tuple[TaskEvent, ...],
) -> TaskDispatch | None:
    if dispatch_row is None:
        return None
    metadata = _resolve_dispatch_contract_metadata(events)
    return TaskDispatch(
        dispatch_key=dispatch_row.dispatch_key,
        status=cast(TaskDispatchStatus, dispatch_row.status),
        submission_source=cast(TaskSubmissionSource, dispatch_row.submission_source),
        accepted_at=dispatch_row.accepted_at,
        last_updated_at=dispatch_row.last_updated_at,
        queue_name=(
            str(metadata["queue_name"])
            if isinstance(metadata.get("queue_name"), str)
            else lane
        ),
        enqueued_at=(
            str(metadata["enqueued_at"])
            if isinstance(metadata.get("enqueued_at"), str)
            else dispatch_row.accepted_at
        ),
        runtime_job_id=(
            str(metadata["runtime_job_id"])
            if isinstance(metadata.get("runtime_job_id"), str)
            else dispatch_row.dispatch_key.replace(":", "__")
        ),
        dispatch_attempt_count=(
            int(metadata["dispatch_attempt_count"])
            if isinstance(metadata.get("dispatch_attempt_count"), int)
            else 1
        ),
        last_dispatch_outcome=(
            str(metadata["last_dispatch_outcome"])
            if isinstance(metadata.get("last_dispatch_outcome"), str)
            else ("accepted" if dispatch_row.status == "accepted" else "claimed")
        ),
        last_dispatch_error_code=(
            str(metadata["last_dispatch_error_code"])
            if isinstance(metadata.get("last_dispatch_error_code"), str)
            else None
        ),
    )


def _to_task_events(
    event_rows: tuple[RewriteTaskEventRecord, ...],
) -> tuple[TaskEvent, ...]:
    return tuple(
        TaskEvent.from_mapping(
            event_key=row.event_key,
            event_type=cast(TaskEventType, row.event_type),
            level=cast(TaskEventLevel, row.level),
            occurred_at=row.occurred_at,
            message=row.message,
            metadata=row.metadata_json,
        )
        for row in event_rows
    )


def _to_task_detail(
    row: RewriteTaskRecord,
    dispatch_row: RewriteTaskDispatchRecord,
    event_rows: tuple[RewriteTaskEventRecord, ...],
    *,
    result_refs: TaskResultRefs | None = None,
) -> TaskDetail:
    events = _to_task_events(event_rows)
    dispatch = _to_task_dispatch(
        dispatch_row,
        lane=cast(TaskLane, row.lane),
        events=events,
    )
    return TaskDetail(
        task_id=row.task_id,
        kind=cast(TaskKind, row.kind),
        lane=cast(TaskLane, row.lane),
        execution_mode=cast(TaskExecutionMode, row.execution_mode),
        status=cast(TaskStatus, row.status),
        submitted_at=row.submitted_at,
        owner_user_id=row.owner_user_id,
        owner_display_name=row.owner_display_name,
        workspace_id=row.workspace_id,
        workspace_slug=row.workspace_slug,
        visibility_scope=cast(TaskVisibilityScope, row.visibility_scope),
        dataset_id=row.dataset_id,
        definition_id=row.definition_id,
        summary=row.summary,
        queue_backend=_normalize_queue_backend(row.queue_backend),
        worker_task_name=cast(WorkerTaskName, row.worker_task_name),
        request_ready=row.request_ready,
        submitted_from_active_dataset=row.submitted_from_active_dataset,
        progress=TaskProgress(
            phase=cast(TaskStatus, row.progress_phase),
            percent_complete=row.progress_percent_complete,
            summary=row.progress_summary,
            updated_at=row.progress_updated_at,
        ),
        result_refs=result_refs or _empty_result_refs(),
        simulation_setup=resolve_simulation_setup(events),
        publication_summary=resolve_publication_summary(events),
        post_processing_setup=resolve_post_processing_setup(events),
        characterization_setup=resolve_characterization_setup(events),
        upstream_task_id=resolve_upstream_task_id(events),
        downstream_task_ids=resolve_downstream_task_ids(events),
        control_state=resolve_task_control_state(cast(TaskStatus, row.status), events),
        retry_of_task_id=resolve_retry_of_task_id(events),
        dispatch=dispatch,
        reconcile=resolve_task_reconcile(events),
        events=events,
    )


def _empty_result_refs() -> TaskResultRefs:
    from sc_core.execution import TaskResultHandle

    return TaskResultRefs(
        result_handle=TaskResultHandle(),
        metadata_records=(),
        trace_payload=None,
        result_handles=(),
    )


def _normalize_queue_backend(value: str) -> TaskQueueBackend:
    if value == "rq_redis":
        return "rq_redis"
    return "rq_redis"


def _resolve_dispatch_contract_metadata(
    events: tuple[TaskEvent, ...],
) -> dict[str, object]:
    keys = {
        "queue_name",
        "enqueued_at",
        "runtime_job_id",
        "dispatch_attempt_count",
        "last_dispatch_outcome",
        "last_dispatch_error_code",
    }
    resolved: dict[str, object] = {}
    for event in events:
        for key in keys:
            value = event.metadata.get(key)
            if value is not None:
                resolved[key] = value
    return resolved
