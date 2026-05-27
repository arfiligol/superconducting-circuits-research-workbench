from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select
from src.app.infrastructure.persistence import (
    RewriteResultHandleRecord,
    RewriteTracePayloadRecord,
    SqliteRewriteStorageMetadataRepository,
    build_sqlite_database_url,
    create_metadata_session_factory,
)
from src.app.infrastructure.storage_reference_factory import (
    build_metadata_record_ref,
    build_result_handle_ref,
    build_result_provenance_ref,
    build_trace_payload_ref,
)


def test_sqlite_storage_metadata_repository_round_trips_storage_entities(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "rewrite-storage-repository.db"
    _upgrade_schema(database_path)
    session_factory = create_metadata_session_factory(str(database_path))
    repository = SqliteRewriteStorageMetadataRepository(session_factory)

    dataset_record = build_metadata_record_ref(
        "dataset",
        "dataset:fluxonium-2025-031",
        version=3,
    )
    trace_batch_record = build_metadata_record_ref(
        "trace_batch",
        "trace_batch:88",
        version=1,
    )
    result_record = build_metadata_record_ref(
        "result_handle",
        "result_handle:501",
        version=2,
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
            trace_batch_record=trace_batch_record,
        ),
    )

    assert repository.save_storage_record(dataset_record) == dataset_record
    assert repository.get_storage_record(dataset_record.record_id) == dataset_record

    assert repository.save_trace_payload(
        dataset_record,
        trace_payload,
        writer_version="rewrite-backend.v0",
    ) == trace_payload
    assert repository.get_trace_payload(trace_payload.store_key) == trace_payload
    assert repository.get_trace_payload_for_owner_record(dataset_record.record_id) == trace_payload

    persisted_result = repository.save_result_handle(result_handle)
    assert persisted_result == result_handle
    assert repository.get_result_handle(result_handle.handle_id) == result_handle
    assert repository.list_result_handles_for_task(303) == (result_handle,)

    with session_factory() as session:
        stored_trace = session.scalar(
            select(RewriteTracePayloadRecord).where(
                RewriteTracePayloadRecord.store_key == trace_payload.store_key
            )
        )
        stored_result = session.scalar(
            select(RewriteResultHandleRecord).where(
                RewriteResultHandleRecord.handle_id == result_handle.handle_id
            )
        )

    assert stored_trace is not None
    assert stored_trace.writer_version == "rewrite-backend.v0"
    assert stored_result is not None
    assert stored_result.source_dataset_id == "fluxonium-2025-031"


def _upgrade_schema(database_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        build_sqlite_database_url(database_path),
    )
    command.upgrade(config, "head")
