"""Tests for task, auth, and audit persistence repositories."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sc_core.execution import build_execution_event_log
from sqlmodel import Session, SQLModel, create_engine

from core.shared.persistence.models import DesignRecord, TraceBatchRecord, utc_now
from core.shared.persistence.repositories.audit_log_repository import AuditLogRepository
from core.shared.persistence.repositories.task_repository import TaskRepository
from core.shared.persistence.repositories.user_repository import UserRepository


def _memory_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_task_repository_lifecycle_roundtrips_payloads_and_links() -> None:
    with _memory_session() as session:
        design = DesignRecord(name="Task Design", source_meta={}, parameters={})
        raw_batch = TraceBatchRecord(
            dataset_id=1,
            design_id=1,
            bundle_type="circuit_simulation",
            role="cache",
            status="completed",
            source_meta={},
            config_snapshot={},
            result_payload={},
        )
        analysis_run = TraceBatchRecord(
            dataset_id=1,
            design_id=1,
            bundle_type="characterization",
            role="analysis_run",
            status="completed",
            source_meta={"analysis_id": "fit_lc"},
            config_snapshot={},
            result_payload={},
        )
        session.add(design)
        session.flush()
        assert design.id is not None

        raw_batch.dataset_id = design.id
        analysis_run.dataset_id = design.id
        session.add(raw_batch)
        session.add(analysis_run)
        session.flush()
        assert raw_batch.id is not None
        assert analysis_run.id is not None

        user = UserRepository(session).create_user("alice", "hash-a", "admin")
        assert user.id is not None

        repo = TaskRepository(session)
        task = repo.create_task(
            "simulation_run",
            design.id,
            {"setup_hash": "sha256:setup"},
            "ui",
            actor_id=user.id,
            dedupe_key="simulation:1:sha256:setup",
        )
        assert task.id is not None
        assert task.status == "queued"
        assert task.request_payload["setup_hash"] == "sha256:setup"

        repo.mark_running(task.id)
        repo.heartbeat(task.id, {"phase": "simulate", "step": "2/5"})
        repo.mark_completed(
            task.id,
            raw_batch.id,
            {"summary": "5 traces written"},
            analysis_run_id=analysis_run.id,
        )
        session.commit()

        persisted = repo.get_task(task.id)
        assert persisted is not None
        assert persisted.status == "completed"
        assert persisted.trace_batch_id == raw_batch.id
        assert persisted.analysis_run_id == analysis_run.id
        assert persisted.actor_id == user.id
        assert persisted.progress_payload == {"phase": "simulate", "step": "2/5"}
        assert persisted.result_summary_payload == {"summary": "5 traces written"}
        assert persisted.error_payload == {}
        assert persisted.created_at.tzinfo == UTC
        assert persisted.started_at is not None
        assert persisted.started_at.tzinfo == UTC
        assert persisted.heartbeat_at is not None
        assert persisted.heartbeat_at.tzinfo == UTC
        assert persisted.completed_at is not None
        assert persisted.completed_at.tzinfo == UTC


def test_task_repository_marks_failures_and_finds_latest_active_and_stale_tasks() -> None:
    with _memory_session() as session:
        design = DesignRecord(name="Task Filters", source_meta={}, parameters={})
        other_design = DesignRecord(name="Other Design", source_meta={}, parameters={})
        session.add(design)
        session.add(other_design)
        session.flush()
        assert design.id is not None
        assert other_design.id is not None

        repo = TaskRepository(session)
        first = repo.create_task(
            "simulation_run",
            design.id,
            {"point_count": 101},
            "cli",
            dedupe_key="simulation:filters",
        )
        assert first.id is not None
        first.created_at = utc_now() - timedelta(minutes=10)
        repo.mark_running(first.id)
        first.heartbeat_at = utc_now() - timedelta(minutes=10)

        second = repo.create_task(
            "simulation_run",
            design.id,
            {"point_count": 201},
            "api",
            dedupe_key="simulation:filters-completed",
        )
        assert second.id is not None
        repo.mark_running(second.id)
        repo.mark_failed(
            second.id,
            {
                "error_code": "simulation_failed",
                "summary": "Singular matrix",
                "details": {"point_index": 14},
            },
        )

        latest = repo.create_task(
            "simulation_run",
            design.id,
            {"point_count": 301},
            "ui",
            dedupe_key="simulation:latest",
        )
        assert latest.id is not None

        foreign = repo.create_task(
            "simulation_run",
            other_design.id,
            {"point_count": 1},
            "ui",
            dedupe_key="simulation:other",
        )
        assert foreign.id is not None
        session.commit()

        failed = repo.get_task(second.id)
        assert failed is not None
        assert failed.status == "failed"
        assert failed.error_payload["error_code"] == "simulation_failed"
        assert failed.completed_at is not None
        assert failed.completed_at.tzinfo == UTC

        active = repo.find_active_by_dedupe_key("simulation:filters")
        assert active is not None
        assert active.id == first.id
        assert repo.find_active_by_dedupe_key("simulation:filters-completed") is None
        latest_task = repo.get_latest_task_by_kind(design.id, "simulation_run")
        assert latest_task is not None
        assert latest_task.id == latest.id

        design_tasks = repo.list_tasks_by_design(design.id)
        assert [task.id for task in design_tasks] == [latest.id, second.id, first.id]
        queued_only = repo.list_tasks_by_design(design.id, status_filter="queued")
        assert [task.id for task in queued_only] == [latest.id]
        stale = repo.list_stale_running_tasks(utc_now() - timedelta(minutes=5))
        assert [task.id for task in stale] == [first.id]


def test_user_repository_updates_credentials_and_active_state() -> None:
    with _memory_session() as session:
        repo = UserRepository(session)
        admin = repo.create_user("admin", "hash-1", "admin")
        user = repo.create_user("user", "hash-2", "user", is_active=False)
        session.commit()

        assert admin.id is not None
        assert user.id is not None
        persisted_admin = repo.get_by_username("admin")
        persisted_user = repo.get_by_id(user.id)
        assert persisted_admin is not None
        assert persisted_admin.id == admin.id
        assert persisted_user is not None
        assert persisted_user.id == user.id
        assert [record.username for record in repo.list_users()] == ["admin", "user"]

        updated = repo.set_password(admin.id, "hash-3")
        disabled = repo.set_active(user.id, True)
        session.commit()

        assert updated.password_hash == "hash-3"
        assert disabled.is_active is True


def test_user_repository_rejects_invalid_role() -> None:
    with _memory_session() as session:
        repo = UserRepository(session)

        repo.create_user("admin", "hash-1", "admin")
        repo.create_user("user", "hash-2", "user")

        try:
            repo.create_user("guest", "hash-3", "guest")
        except ValueError as exc:
            assert "Unsupported user role" in str(exc)
        else:
            raise AssertionError("Expected invalid user role to be rejected.")


def test_audit_log_repository_appends_and_filters_actor_logs() -> None:
    with _memory_session() as session:
        user_repo = UserRepository(session)
        alice = user_repo.create_user("alice", "hash-a", "admin")
        bob = user_repo.create_user("bob", "hash-b", "user")
        session.flush()
        assert alice.id is not None
        assert bob.id is not None

        repo = AuditLogRepository(session)
        first = repo.append_log(
            actor_id=alice.id,
            action_kind="task.dispatch",
            resource_kind="task",
            resource_id=1,
            summary="Alice dispatched simulation task 1",
            payload={"requested_by": "ui"},
        )
        second = repo.append_log(
            actor_id=bob.id,
            action_kind="auth.login",
            resource_kind="session",
            resource_id="session-2",
            summary="Bob logged in",
            payload={"ip": "127.0.0.1"},
        )
        session.commit()

        assert first.id is not None
        assert second.id is not None
        assert [log.id for log in repo.list_logs()] == [second.id, first.id]
        assert [log.id for log in repo.list_logs_by_actor(alice.id)] == [first.id]
        assert repo.list_logs_by_actor(9999) == []


def test_audit_log_repository_redacts_secret_and_raw_numeric_payloads() -> None:
    with _memory_session() as session:
        repo = AuditLogRepository(session)
        payload = {
            "requested_by": "ui",
            "password_hash": "secret-hash",
            "token": "secret-token",
            "values": [1.0, 2.0, 3.0],
            "nested": {
                "authorization": "Bearer abc",
                "trace_values": [9.0],
                "safe": {"trace_batch_id": 7},
            },
        }

        log = repo.append_log(
            actor_id=None,
            action_kind="task.retry",
            resource_kind="task",
            resource_id=9,
            summary="Retried task 9",
            payload=payload,
        )
        session.commit()

        payload["nested"]["safe"]["trace_batch_id"] = 99

        assert log.payload == {
            "requested_by": "ui",
            "password_hash": "[REDACTED]",
            "token": "[REDACTED]",
            "values": "[OMITTED]",
            "nested": {
                "authorization": "[REDACTED]",
                "trace_values": "[OMITTED]",
                "safe": {"trace_batch_id": 7},
            },
        }


def test_audit_log_repository_appends_canonical_execution_events_with_safe_copy() -> None:
    with _memory_session() as session:
        event = build_execution_event_log(
            action_kind="task.control_requested",
            resource_kind="task",
            resource_id=17,
            summary="Requested cancellation for task 17",
            payload={
                "token": "secret-token",
                "result_refs": {"trace_batch_id": 5},
                "values": [1.0, 2.0],
            },
        )
        repo = AuditLogRepository(session)

        log = repo.append_execution_event(actor_id=None, event=event)
        session.commit()
        event.payload["result_refs"] = {"trace_batch_id": 99}

        assert log.payload == {
            "token": "[REDACTED]",
            "result_refs": {"trace_batch_id": 5},
            "values": "[OMITTED]",
        }
