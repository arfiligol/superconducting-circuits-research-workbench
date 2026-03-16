from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from alembic import command
from alembic.config import Config
from sc_core.tasking import resolve_worker_task_route
from sqlalchemy import delete
from src.app.domain.tasks import TaskCreateDraft
from src.app.infrastructure.persistence import (
    RewriteTaskDispatchRecord,
    RewriteTaskEventRecord,
    SqliteRewriteTaskSnapshotRepository,
    build_sqlite_database_url,
    create_metadata_session_factory,
)
from src.app.infrastructure.rewrite_app_state_repository import build_seed_tasks


def test_sqlite_task_snapshot_repository_round_trips_task_rows(tmp_path: Path) -> None:
    database_path = tmp_path / "rewrite-task-repository.db"
    _upgrade_schema(database_path)
    repository = SqliteRewriteTaskSnapshotRepository(
        create_metadata_session_factory(str(database_path))
    )

    seeded_task = next(task for task in build_seed_tasks() if task.task_id == 303)

    assert repository.has_tasks() is False
    persisted_seed = repository.save_task_snapshot(seeded_task)
    assert persisted_seed.task_id == seeded_task.task_id
    assert persisted_seed.dispatch is not None
    assert persisted_seed.dispatch.dispatch_key == "dispatch:303:post_processing_run_task"
    assert [event.event_type for event in persisted_seed.events] == [
        "task_submitted",
        "task_completed",
    ]
    assert repository.has_tasks() is True
    fetched_seed = repository.get_task(303)
    assert fetched_seed is not None
    assert fetched_seed.task_id == persisted_seed.task_id
    assert fetched_seed.status == persisted_seed.status
    assert fetched_seed.dispatch == persisted_seed.dispatch
    assert fetched_seed.events == persisted_seed.events
    assert repository.list_task_events(303) == persisted_seed.events
    assert fetched_seed.result_refs.result_handles == ()
    listed_tasks = repository.list_tasks()
    assert [task.task_id for task in listed_tasks] == [303]
    assert listed_tasks[0].events == persisted_seed.events

    worker_route = resolve_worker_task_route(
        "characterization",
        request_is_valid=True,
        has_trace_batch_id=False,
    )
    created = repository.create_task(
        TaskCreateDraft(
            kind="characterization",
            lane=worker_route.lane,
            execution_mode=worker_route.execution_mode,
            owner_user_id="researcher-01",
            owner_display_name="Rewrite Local User",
            workspace_id="ws-device-lab",
            workspace_slug="device-lab",
            visibility_scope="workspace",
            dataset_id="fluxonium-2025-031",
            definition_id=None,
            summary="characterization task accepted for dataset fluxonium-2025-031.",
            worker_task_name=worker_route.worker_task_name,
            request_ready=worker_route.request_ready,
            submitted_from_active_dataset=True,
            submission_source="active_dataset",
        )
    )
    assert created.task_id == 304
    assert created.status == "queued"
    assert created.dispatch is not None
    assert created.dispatch.status == "accepted"
    assert created.dispatch.submission_source == "active_dataset"
    assert created.progress.phase == "queued"
    assert created.result_refs.result_handles == ()
    assert [event.event_type for event in created.events] == ["task_submitted"]
    assert repository.get_task(304) == created
    assert [task.task_id for task in repository.list_tasks()] == [303, 304]

    updated = repository.save_task_snapshot(
        replace(
            created,
            status="failed",
            summary="Persisted failure snapshot",
            progress=replace(
                created.progress,
                phase="failed",
                percent_complete=100,
                summary="Persisted failure summary.",
                updated_at="2026-03-12 11:05:00",
            ),
        )
    )
    assert updated.status == "failed"
    assert updated.dispatch is not None
    assert updated.dispatch.status == "failed"
    persisted_updated = repository.get_task(304)
    assert persisted_updated is not None
    assert persisted_updated.progress.summary == "Persisted failure summary."
    assert persisted_updated.dispatch is not None
    assert persisted_updated.dispatch.last_updated_at == "2026-03-12 11:05:00"
    assert [event.event_type for event in persisted_updated.events] == [
        "task_submitted",
        "task_failed",
    ]

    with create_metadata_session_factory(str(database_path))() as session:
        session.execute(
            delete(RewriteTaskDispatchRecord).where(RewriteTaskDispatchRecord.task_id == 304)
        )
        session.execute(
            delete(RewriteTaskEventRecord).where(RewriteTaskEventRecord.task_id == 304)
        )
        session.commit()

    backfilled_dispatch = repository.get_task(304)
    assert backfilled_dispatch is not None
    assert backfilled_dispatch.dispatch is not None
    assert backfilled_dispatch.dispatch.dispatch_key == "dispatch:304:characterization_run_task"
    assert backfilled_dispatch.dispatch.status == "failed"
    assert [event.event_type for event in backfilled_dispatch.events] == [
        "task_submitted",
        "task_failed",
    ]


def _upgrade_schema(database_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", build_sqlite_database_url(database_path))
    command.upgrade(config, "head")
