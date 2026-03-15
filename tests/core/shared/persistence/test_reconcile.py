"""Tests for stale-task and incomplete-batch reconcile helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

import core.shared.persistence.reconcile as reconcile_module
from core.shared.persistence.models import DesignRecord, TraceBatchRecord, utc_now
from core.shared.persistence.reconcile import reconcile_stale_tasks_and_batches
from core.shared.persistence.unit_of_work import SqliteUnitOfWork


def _memory_session() -> Session:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_reconcile_marks_stale_tasks_and_orphan_batches_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path))

    with _memory_session() as session:
        uow = SqliteUnitOfWork(session)
        design = uow.datasets.add(
            DesignRecord(name="Reconcile Design", source_meta={}, parameters={})
        )
        uow.flush()
        assert design.id is not None

        active_batch = uow.result_bundles.add(
            TraceBatchRecord(
                dataset_id=design.id,
                bundle_type="circuit_simulation",
                role="cache",
                status="in_progress",
                source_meta={},
                config_snapshot={},
                result_payload={
                    "trace_records": [
                        {
                            "store_ref": {
                                "backend": "local_zarr",
                                "store_key": "designs/1/runtime/stale-batch.zarr",
                            }
                        }
                    ]
                },
            )
        )
        orphan_batch = uow.result_bundles.add(
            TraceBatchRecord(
                dataset_id=design.id,
                bundle_type="simulation_postprocess",
                role="derived_from_simulation",
                status="in_progress",
                source_meta={},
                config_snapshot={},
                result_payload={
                    "trace_records": [
                        {
                            "store_ref": {
                                "backend": "local_zarr",
                                "store_key": "designs/1/runtime/orphan-batch.zarr",
                            }
                        }
                    ]
                },
            )
        )
        uow.flush()
        assert active_batch.id is not None
        assert orphan_batch.id is not None

        stale_task = uow.tasks.create_task(
            "simulation_run",
            design.id,
            {"run_id": "stale"},
            "ui",
            trace_batch_id=active_batch.id,
        )
        assert stale_task.id is not None
        uow.tasks.mark_running(stale_task.id)
        stale_task.heartbeat_at = utc_now() - timedelta(minutes=10)

        for store_key in [
            "designs/1/runtime/stale-batch.zarr",
            "designs/1/runtime/orphan-batch.zarr",
        ]:
            store_path = tmp_path / store_key
            store_path.mkdir(parents=True, exist_ok=True)

        summary = reconcile_stale_tasks_and_batches(
            uow,
            stale_before=utc_now() - timedelta(minutes=5),
        )

        reconciled_task = uow.tasks.get_task(stale_task.id)
        reconciled_active_batch = uow.result_bundles.get(active_batch.id)
        reconciled_orphan_batch = uow.result_bundles.get(orphan_batch.id)

        assert reconciled_task is not None
        assert reconciled_task.status == "failed"
        assert reconciled_task.error_payload["error_code"] == "stale_task_timeout"
        assert reconciled_active_batch is not None
        assert reconciled_active_batch.status == "failed"
        assert reconciled_orphan_batch is not None
        assert reconciled_orphan_batch.status == "failed"
        assert summary.stale_task_ids == [stale_task.id]
        assert summary.orphan_batch_ids == [orphan_batch.id]
        assert set(summary.failed_batch_ids) == {active_batch.id, orphan_batch.id}
        assert set(summary.deleted_store_keys) == {
            "designs/1/runtime/stale-batch.zarr",
            "designs/1/runtime/orphan-batch.zarr",
        }
        assert len(summary.audit_log_ids) == 2
        assert not (tmp_path / "designs/1/runtime/stale-batch.zarr").exists()
        assert not (tmp_path / "designs/1/runtime/orphan-batch.zarr").exists()


def test_reconcile_preserves_batch_payload_shape_and_adds_only_small_summary_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path))

    with _memory_session() as session:
        uow = SqliteUnitOfWork(session)
        design = uow.datasets.add(
            DesignRecord(name="Reconcile Payload", source_meta={}, parameters={})
        )
        uow.flush()
        assert design.id is not None

        batch = uow.result_bundles.add(
            TraceBatchRecord(
                dataset_id=design.id,
                bundle_type="simulation_postprocess",
                role="derived_from_simulation",
                status="in_progress",
                source_meta={},
                config_snapshot={},
                result_payload={
                    "trace_batch_record": {
                        "summary_payload": {
                            "trace_count": 4,
                            "status_note": "still-running",
                        }
                    },
                    "trace_records": [
                        {
                            "store_ref": {
                                "backend": "local_zarr",
                                "store_key": "designs/1/runtime/payload-batch.zarr",
                            }
                        }
                    ],
                },
            )
        )
        uow.flush()
        assert batch.id is not None

        (tmp_path / "designs/1/runtime/payload-batch.zarr").mkdir(parents=True, exist_ok=True)

        summary = reconcile_stale_tasks_and_batches(
            uow,
            stale_before=utc_now() - timedelta(minutes=5),
        )

        reconciled_batch = uow.result_bundles.get(batch.id)
        assert reconciled_batch is not None
        assert summary.failed_batch_ids == [batch.id]
        assert summary.orphan_batch_ids == [batch.id]
        assert reconciled_batch.result_payload["trace_records"] == [
            {
                "store_ref": {
                    "backend": "local_zarr",
                    "store_key": "designs/1/runtime/payload-batch.zarr",
                }
            }
        ]

        trace_batch_record = reconciled_batch.result_payload["trace_batch_record"]
        assert isinstance(trace_batch_record, dict)
        summary_payload = trace_batch_record["summary_payload"]
        assert summary_payload["trace_count"] == 4
        assert summary_payload["status_note"] == "still-running"
        assert summary_payload["reconcile_reason"] == "orphan_incomplete_batch"
        assert isinstance(summary_payload["reconcile_stale_before"], str)
        assert set(summary_payload) == {
            "trace_count",
            "status_note",
            "reconcile_reason",
            "reconcile_stale_before",
        }
        assert "trace_records" not in summary_payload
        assert "trace_batch_record" not in summary_payload
        assert summary.deleted_store_keys == ["designs/1/runtime/payload-batch.zarr"]


def test_reconcile_commits_failed_state_before_cleanup(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path))

    with _memory_session() as session:
        uow = SqliteUnitOfWork(session)
        design = uow.datasets.add(
            DesignRecord(name="Reconcile Ordering", source_meta={}, parameters={})
        )
        uow.flush()
        assert design.id is not None

        batch = uow.result_bundles.add(
            TraceBatchRecord(
                dataset_id=design.id,
                bundle_type="simulation_postprocess",
                role="derived_from_simulation",
                status="in_progress",
                source_meta={},
                config_snapshot={},
                result_payload={
                    "trace_records": [
                        {
                            "store_ref": {
                                "backend": "local_zarr",
                                "store_key": "designs/1/runtime/order-check.zarr",
                            }
                        }
                    ]
                },
            )
        )
        uow.flush()
        assert batch.id is not None

        events: list[str] = []
        original_commit = uow.commit
        original_cleanup = reconcile_module._cleanup_store_keys

        def tracking_commit() -> None:
            events.append("commit")
            original_commit()

        def tracking_cleanup(store_keys: list[str]) -> list[str]:
            events.append("cleanup")
            persisted_batch = uow.result_bundles.get(batch.id)
            assert persisted_batch is not None
            assert persisted_batch.status == "failed"
            return original_cleanup(store_keys)

        monkeypatch.setattr(uow, "commit", tracking_commit)
        monkeypatch.setattr(reconcile_module, "_cleanup_store_keys", tracking_cleanup)

        (tmp_path / "designs/1/runtime/order-check.zarr").mkdir(parents=True, exist_ok=True)

        summary = reconcile_stale_tasks_and_batches(
            uow,
            stale_before=utc_now() - timedelta(minutes=5),
        )

        assert summary.failed_batch_ids == [batch.id]
        assert summary.orphan_batch_ids == [batch.id]
        assert summary.deleted_store_keys == ["designs/1/runtime/order-check.zarr"]
        assert events == ["commit", "cleanup"]


def test_reconcile_skips_cleanup_when_persistence_commit_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path))

    with _memory_session() as session:
        uow = SqliteUnitOfWork(session)
        design = uow.datasets.add(
            DesignRecord(name="Reconcile Commit Failure", source_meta={}, parameters={})
        )
        uow.flush()
        assert design.id is not None

        batch = uow.result_bundles.add(
            TraceBatchRecord(
                dataset_id=design.id,
                bundle_type="simulation_postprocess",
                role="derived_from_simulation",
                status="in_progress",
                source_meta={},
                config_snapshot={},
                result_payload={
                    "trace_records": [
                        {
                            "store_ref": {
                                "backend": "local_zarr",
                                "store_key": "designs/1/runtime/commit-failure.zarr",
                            }
                        }
                    ]
                },
            )
        )
        uow.flush()
        assert batch.id is not None

        stale_task = uow.tasks.create_task(
            "simulation_run",
            design.id,
            {"run_id": "commit-failure"},
            "ui",
            trace_batch_id=batch.id,
        )
        assert stale_task.id is not None
        uow.tasks.mark_running(stale_task.id)
        stale_task.heartbeat_at = utc_now() - timedelta(minutes=10)
        uow.commit()

        store_path = tmp_path / "designs/1/runtime/commit-failure.zarr"
        store_path.mkdir(parents=True, exist_ok=True)

        original_commit = uow.commit
        commit_calls: list[str] = []

        def failing_commit() -> None:
            commit_calls.append("commit")
            raise RuntimeError("commit failed")

        monkeypatch.setattr(uow, "commit", failing_commit)

        try:
            reconcile_stale_tasks_and_batches(
                uow,
                stale_before=utc_now() - timedelta(minutes=5),
            )
        except RuntimeError as exc:
            assert str(exc) == "commit failed"
        else:
            raise AssertionError("Expected reconcile to surface commit failure.")

        assert commit_calls == ["commit"]
        assert store_path.exists()

        monkeypatch.setattr(uow, "commit", original_commit)
        original_commit()

        persisted_task = uow.tasks.get_task(stale_task.id)
        persisted_batch = uow.result_bundles.get(batch.id)
        assert persisted_task is not None
        assert persisted_task.status == "running"
        assert persisted_batch is not None
        assert persisted_batch.status == "in_progress"
