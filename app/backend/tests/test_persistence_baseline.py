from __future__ import annotations

import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from app_backend.infrastructure.persistence.database import (
    bootstrap_metadata_schema,
    build_sqlite_database_url,
)
from app_backend.infrastructure.persistence.models import (
    RewriteCircuitDefinitionRecord,
    RewriteDatasetDesignRecord,
    RewritePublishedSimulationResultRecord,
    RewritePublishedSimulationTraceRecord,
    RewriteResultHandleRecord,
    RewriteStorageRecord,
    RewriteTaskDispatchRecord,
    RewriteTaskEventRecord,
    RewriteTaskRecord,
    RewriteTracePayloadRecord,
)
from app_backend.infrastructure.storage_reference_factory import (
    REWRITE_TRACE_SCHEMA_VERSION,
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

_UUID_V4_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def test_alembic_upgrade_creates_rewrite_storage_tables_and_supports_round_trip(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "rewrite-metadata.db"
    config = _build_alembic_config(database_path)

    command.upgrade(config, "head")

    engine = _create_engine(database_path)
    inspector = inspect(engine)
    assert sorted(inspector.get_table_names()) == [
        "alembic_version",
        "rewrite_app_context_records",
        "rewrite_auth_account_records",
        "rewrite_authenticated_session_records",
        "rewrite_characterization_registry_records",
        "rewrite_circuit_definitions",
        "rewrite_dataset_designs",
        "rewrite_dataset_records",
        "rewrite_dataset_traces",
        "rewrite_pending_invitation_acceptance_records",
        "rewrite_published_simulation_results",
        "rewrite_published_simulation_traces",
        "rewrite_refresh_token_records",
        "rewrite_result_handles",
        "rewrite_server_target_records",
        "rewrite_storage_records",
        "rewrite_task_dispatch_records",
        "rewrite_task_event_records",
        "rewrite_task_records",
        "rewrite_trace_capability_records",
        "rewrite_trace_payloads",
        "rewrite_workspace_default_dataset_records",
        "rewrite_workspace_invitation_records",
    ]

    dataset_record = build_metadata_record_ref(
        "dataset",
        "dataset:fluxonium-2025-031",
        version=3,
    )
    trace_payload = build_trace_payload_ref(
        payload_role="dataset_primary",
        store_key="datasets/fluxonium-2025-031/trace-batches/88.zarr",
        store_uri="trace_store/datasets/fluxonium-2025-031/trace-batches/88.zarr",
        group_path="trace_batches/88",
        array_path="signals/iq_real",
        dtype="float64",
        shape=(184, 1024),
        chunk_shape=(16, 1024),
    )
    result_record = build_metadata_record_ref(
        "result_handle",
        "result_handle:501",
        version=2,
    )
    result_handle = build_result_handle_ref(
        handle_id="result:fluxonium-2025-031:fit-summary",
        kind="fit_summary",
        status="materialized",
        label="Fluxonium fit summary",
        metadata_record=result_record,
        payload_backend="json_artifact",
        payload_format="json",
        payload_role="report_artifact",
        payload_locator="artifacts/fit-summary.json",
        provenance_task_id=303,
        provenance=build_result_provenance_ref(
            source_dataset_id="fluxonium-2025-031",
            source_task_id=303,
            trace_batch_record=build_metadata_record_ref(
                "trace_batch",
                "trace_batch:88",
                version=1,
            ),
        ),
    )

    with Session(engine) as session:
        dataset_row = RewriteStorageRecord(
            record_type=dataset_record.record_type,
            record_id=dataset_record.record_id,
            schema_version=dataset_record.schema_version,
            version=dataset_record.version,
        )
        trace_batch_row = RewriteStorageRecord(
            record_type="trace_batch",
            record_id="trace_batch:88",
            schema_version="sqlite_metadata.v1",
            version=1,
        )
        result_metadata_row = RewriteStorageRecord(
            record_type=result_record.record_type,
            record_id=result_record.record_id,
            schema_version=result_record.schema_version,
            version=result_record.version,
        )
        session.add_all([dataset_row, trace_batch_row, result_metadata_row])
        session.flush()

        session.add(
            RewriteTracePayloadRecord(
                owner_record_id=dataset_row.id,
                contract_version=trace_payload.contract_version,
                backend=trace_payload.backend,
                payload_role=trace_payload.payload_role,
                store_key=trace_payload.store_key,
                store_uri=trace_payload.store_uri,
                group_path=trace_payload.group_path,
                array_path=trace_payload.array_path,
                dtype=trace_payload.dtype,
                shape=list(trace_payload.shape),
                chunk_shape=list(trace_payload.chunk_shape),
                schema_version=trace_payload.schema_version,
                writer_version="rewrite-backend.v0",
            )
        )
        session.add(
            RewriteResultHandleRecord(
                metadata_record_id=result_metadata_row.id,
                handle_id=result_handle.handle_id,
                contract_version=result_handle.contract_version,
                kind=result_handle.kind,
                status=result_handle.status,
                label=result_handle.label,
                payload_backend=result_handle.payload_backend,
                payload_format=result_handle.payload_format,
                payload_role=result_handle.payload_role,
                payload_locator=result_handle.payload_locator,
                provenance_task_id=result_handle.provenance_task_id,
                source_dataset_id=result_handle.provenance.source_dataset_id,
                source_task_id=result_handle.provenance.source_task_id,
                trace_batch_record_id=trace_batch_row.id,
                analysis_run_record_id=None,
            )
        )
        session.add(
            RewriteTaskRecord(
                task_id=303,
                kind="post_processing",
                lane="simulation",
                execution_mode="run",
                status="completed",
                submitted_at="2026-03-11 19:05:00",
                owner_user_id="researcher-01",
                owner_display_name="Rewrite Local User",
                workspace_id="ws-device-lab",
                workspace_slug="device-lab",
                visibility_scope="owned",
                dataset_id="fluxonium-2025-031",
                definition_id=None,
                summary="Fluxonium fit bundle was post-processed.",
                queue_backend="backend_db",
                worker_task_name="post_processing_run_task",
                request_ready=True,
                submitted_from_active_dataset=True,
                progress_phase="completed",
                progress_percent_complete=100,
                progress_summary="post_processing_run_task completed in the simulation lane.",
                progress_updated_at="2026-03-11 19:18:00",
            )
        )
        session.add(
            RewriteTaskDispatchRecord(
                task_id=303,
                dispatch_key="dispatch:303:post_processing_run_task",
                status="completed",
                submission_source="active_dataset",
                accepted_at="2026-03-11 19:05:00",
                last_updated_at="2026-03-11 19:18:00",
            )
        )
        session.add(
            RewriteTaskEventRecord(
                task_id=303,
                event_key="task_submitted:2026-03-11 19:05:00",
                event_type="task_submitted",
                level="info",
                occurred_at="2026-03-11 19:05:00",
                message="Task submission accepted by local runtime.",
                metadata_json={
                    "task_status": "queued",
                    "dispatch_status": "completed",
                    "dispatch_key": "dispatch:303:post_processing_run_task",
                    "submission_source": "active_dataset",
                    "worker_task_name": "post_processing_run_task",
                    "dataset_id": "fluxonium-2025-031",
                    "definition_id": None,
                },
            )
        )
        session.commit()

        persisted_trace = session.scalar(
            select(RewriteTracePayloadRecord).where(
                RewriteTracePayloadRecord.store_key == trace_payload.store_key
            )
        )
        persisted_result = session.scalar(
            select(RewriteResultHandleRecord).where(
                RewriteResultHandleRecord.handle_id == result_handle.handle_id
            )
        )
        persisted_dataset_design = session.scalar(select(RewriteDatasetDesignRecord))
        persisted_definition = session.scalar(select(RewriteCircuitDefinitionRecord))
        persisted_publication = session.scalar(select(RewritePublishedSimulationResultRecord))
        persisted_published_trace = session.scalar(select(RewritePublishedSimulationTraceRecord))
        persisted_task = session.scalar(
            select(RewriteTaskRecord).where(RewriteTaskRecord.task_id == 303)
        )
        persisted_dispatch = session.scalar(
            select(RewriteTaskDispatchRecord).where(RewriteTaskDispatchRecord.task_id == 303)
        )
        persisted_event = session.scalar(
            select(RewriteTaskEventRecord).where(RewriteTaskEventRecord.task_id == 303)
        )

    assert persisted_trace is not None
    assert persisted_trace.schema_version == REWRITE_TRACE_SCHEMA_VERSION
    assert persisted_trace.shape == [184, 1024]
    assert persisted_result is not None
    assert persisted_result.source_dataset_id == "fluxonium-2025-031"
    assert persisted_result.provenance_task_id == 303
    assert persisted_dataset_design is None
    assert persisted_definition is None
    assert persisted_publication is None
    assert persisted_published_trace is None
    assert persisted_task is not None
    assert persisted_task.progress_phase == "completed"
    assert persisted_task.summary == "Fluxonium fit bundle was post-processed."
    assert persisted_dispatch is not None
    assert persisted_dispatch.dispatch_key == "dispatch:303:post_processing_run_task"
    assert persisted_dispatch.status == "completed"
    assert persisted_event is not None
    assert persisted_event.event_type == "task_submitted"
    assert persisted_event.metadata_json["dispatch_key"] == "dispatch:303:post_processing_run_task"


def test_bootstrap_metadata_schema_migrates_legacy_numeric_definition_ids_to_uuid(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "rewrite-legacy.db"
    config = _build_alembic_config(database_path)
    command.upgrade(config, "20260321_0005")

    engine = _create_engine(database_path)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE alembic_version"))
        connection.execute(
            text(
                """
                CREATE TABLE rewrite_circuit_definitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    definition_id INTEGER NOT NULL,
                    workspace_id VARCHAR(64) NOT NULL,
                    visibility_scope VARCHAR(32) NOT NULL,
                    lifecycle_state VARCHAR(32) NOT NULL,
                    owner_user_id VARCHAR(64) NOT NULL,
                    owner_display_name VARCHAR(128) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    created_at_iso VARCHAR(32) NOT NULL,
                    updated_at_iso VARCHAR(32) NOT NULL,
                    concurrency_token VARCHAR(64) NOT NULL,
                    source_hash VARCHAR(64) NOT NULL,
                    source_text TEXT NOT NULL,
                    normalized_output TEXT NOT NULL,
                    validation_notices_json JSON NOT NULL,
                    validation_summary_json JSON NOT NULL,
                    preview_artifacts_json JSON NOT NULL,
                    lineage_parent_id INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX ix_rewrite_circuit_definitions_definition_id
                ON rewrite_circuit_definitions (definition_id)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX ix_rewrite_circuit_definitions_workspace_visibility
                ON rewrite_circuit_definitions (workspace_id, visibility_scope)
                """
            )
        )
        connection.execute(
            text(
                """
                CREATE INDEX ix_rewrite_circuit_definitions_lifecycle_state
                ON rewrite_circuit_definitions (lifecycle_state)
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO rewrite_circuit_definitions (
                    definition_id,
                    workspace_id,
                    visibility_scope,
                    lifecycle_state,
                    owner_user_id,
                    owner_display_name,
                    name,
                    created_at_iso,
                    updated_at_iso,
                    concurrency_token,
                    source_hash,
                    source_text,
                    normalized_output,
                    validation_notices_json,
                    validation_summary_json,
                    preview_artifacts_json,
                    lineage_parent_id
                ) VALUES
                    (
                        12,
                        'workspace-local',
                        'local',
                        'published',
                        'user-local',
                        'Local Operator',
                        'Legacy Parent',
                        '2026-03-20T10:00:00Z',
                        '2026-03-20T10:00:00Z',
                        'etag_parent',
                        'hash_parent',
                        'parent source',
                        '{}',
                        '[]',
                        '{}',
                        '[]',
                        NULL
                    ),
                    (
                        34,
                        'workspace-local',
                        'local',
                        'draft',
                        'user-local',
                        'Local Operator',
                        'Legacy Child',
                        '2026-03-21T10:00:00Z',
                        '2026-03-21T10:00:00Z',
                        'etag_child',
                        'hash_child',
                        'child source',
                        '{}',
                        '[]',
                        '{}',
                        '[]',
                        12
                    )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO rewrite_task_records (
                    task_id,
                    kind,
                    lane,
                    execution_mode,
                    status,
                    submitted_at,
                    owner_user_id,
                    owner_display_name,
                    workspace_id,
                    workspace_slug,
                    visibility_scope,
                    dataset_id,
                    definition_id,
                    summary,
                    queue_backend,
                    worker_task_name,
                    request_ready,
                    submitted_from_active_dataset,
                    progress_phase,
                    progress_percent_complete,
                    progress_summary,
                    progress_updated_at
                ) VALUES (
                    901,
                    'simulation',
                    'simulation',
                    'run',
                    'completed',
                    '2026-03-21 11:00:00',
                    'user-local',
                    'Local Operator',
                    'workspace-local',
                    'local-space',
                    'local',
                    'dataset-local',
                    34,
                    'Legacy simulation completed.',
                    'local_runtime',
                    'simulation_run_task',
                    1,
                    1,
                    'completed',
                    100,
                    'Simulation completed.',
                    '2026-03-21 11:10:00'
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO rewrite_task_event_records (
                    task_id,
                    event_key,
                    event_type,
                    level,
                    occurred_at,
                    message,
                    metadata_json
                ) VALUES (
                    901,
                    'task_submitted:2026-03-21 11:00:00',
                    'task_submitted',
                    'info',
                    '2026-03-21 11:00:00',
                    'Legacy task accepted.',
                    :metadata_json
                )
                """
            ),
            {"metadata_json": '{"definition_id": 34, "task_status": "queued"}'},
        )

    bootstrap_metadata_schema(str(database_path))

    inspector = inspect(engine)
    assert sorted(inspector.get_table_names()) == [
        "alembic_version",
        "rewrite_app_context_records",
        "rewrite_auth_account_records",
        "rewrite_authenticated_session_records",
        "rewrite_characterization_registry_records",
        "rewrite_circuit_definitions",
        "rewrite_dataset_designs",
        "rewrite_dataset_records",
        "rewrite_dataset_traces",
        "rewrite_pending_invitation_acceptance_records",
        "rewrite_published_simulation_results",
        "rewrite_published_simulation_traces",
        "rewrite_refresh_token_records",
        "rewrite_result_handles",
        "rewrite_server_target_records",
        "rewrite_storage_records",
        "rewrite_task_dispatch_records",
        "rewrite_task_event_records",
        "rewrite_task_records",
        "rewrite_trace_capability_records",
        "rewrite_trace_payloads",
        "rewrite_workspace_default_dataset_records",
        "rewrite_workspace_invitation_records",
    ]

    definition_columns = {
        column["name"]: column["type"]
        for column in inspector.get_columns("rewrite_circuit_definitions")
    }
    task_columns = {
        column["name"]: column["type"] for column in inspector.get_columns("rewrite_task_records")
    }
    assert "CHAR" in str(definition_columns["definition_id"]).upper()
    assert "CHAR" in str(definition_columns["lineage_parent_id"]).upper()
    assert "CHAR" in str(task_columns["definition_id"]).upper()

    with Session(engine) as session:
        definitions = session.scalars(
            select(RewriteCircuitDefinitionRecord).order_by(RewriteCircuitDefinitionRecord.name)
        ).all()
        task = session.scalar(select(RewriteTaskRecord).where(RewriteTaskRecord.task_id == 901))
        event = session.scalar(
            select(RewriteTaskEventRecord).where(RewriteTaskEventRecord.task_id == 901)
        )

    assert len(definitions) == 2
    parent_definition = next(row for row in definitions if row.name == "Legacy Parent")
    child_definition = next(row for row in definitions if row.name == "Legacy Child")
    assert _UUID_V4_PATTERN.match(parent_definition.definition_id)
    assert _UUID_V4_PATTERN.match(child_definition.definition_id)
    assert child_definition.lineage_parent_id == parent_definition.definition_id
    assert task is not None
    assert task.definition_id == child_definition.definition_id
    assert event is not None
    assert event.metadata_json["definition_id"] == child_definition.definition_id
    assert session_scalar_text(engine, "SELECT version_num FROM alembic_version") == "20260430_0010"


def _build_alembic_config(database_path: Path) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", build_sqlite_database_url(database_path))
    return config


def _create_engine(database_path: Path):
    from sqlalchemy import create_engine

    return create_engine(build_sqlite_database_url(database_path))


def session_scalar_text(engine, query: str) -> str | None:
    with engine.connect() as connection:
        return connection.execute(text(query)).scalar_one_or_none()
