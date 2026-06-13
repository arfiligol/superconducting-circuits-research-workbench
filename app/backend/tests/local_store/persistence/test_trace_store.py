"""Tests for TraceStore Zarr baseline behavior."""

from __future__ import annotations

import numpy as np
import zarr
from app_backend.infrastructure.local_store.models import DataRecord
from app_backend.infrastructure.local_store.trace_store import (
    TRACE_STORE_SCHEMA_VERSION,
    LocalZarrTraceStore,
    LocalZarrTraceStoreBackend,
    S3ZarrTraceStoreBackend,
    TraceStore,
    TraceStoreBackendBinding,
    coerce_trace_store_ref,
    get_trace_store_backend_binding,
    get_trace_store_runtime_config,
)


def test_local_zarr_trace_store_satisfies_contract() -> None:
    store = LocalZarrTraceStore()

    assert isinstance(store, TraceStore)
    assert store.backend == "local_zarr"


def test_backend_bindings_keep_locator_logic_inside_persistence(tmp_path) -> None:
    local_backend = LocalZarrTraceStoreBackend(root_path=tmp_path / "trace_store")
    s3_backend = S3ZarrTraceStoreBackend(bucket="trace-bucket", prefix="tutorial")

    assert isinstance(local_backend, TraceStoreBackendBinding)
    assert isinstance(s3_backend, TraceStoreBackendBinding)

    local_key = local_backend.build_store_key(design_id=42, batch_id=105)
    assert local_key == "designs/42/batches/105.zarr"
    assert local_backend.resolve_store_path(store_key=local_key) == (
        tmp_path / "trace_store" / "designs/42/batches/105.zarr"
    )
    assert local_backend.build_store_uri(store_key=local_key).endswith(
        "trace_store/designs/42/batches/105.zarr"
    )

    s3_key = s3_backend.build_store_key(design_id=42, batch_id=105)
    assert s3_key == "tutorial/designs/42/batches/105.zarr"
    assert s3_backend.build_store_uri(store_key=s3_key) == (
        "s3://trace-bucket/tutorial/designs/42/batches/105.zarr"
    )


def test_runtime_config_selects_backend_contract_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    monkeypatch.setenv("SC_TRACE_STORE_BACKEND", "s3_zarr")
    monkeypatch.setenv("SC_TRACE_STORE_S3_BUCKET", "trace-bucket")
    monkeypatch.setenv("SC_TRACE_STORE_S3_PREFIX", "tutorial")

    config = get_trace_store_runtime_config()
    assert config.default_backend == "s3_zarr"
    assert config.local_root_path == (tmp_path / "trace_store")

    binding = get_trace_store_backend_binding(config=config)
    assert isinstance(binding, S3ZarrTraceStoreBackend)
    assert binding.build_store_key(design_id=7, batch_id=9) == "tutorial/designs/7/batches/9.zarr"


def test_local_zarr_trace_store_writes_trace_and_reads_slices(tmp_path) -> None:
    store = LocalZarrTraceStore(root_path=tmp_path / "trace_store")
    values = np.arange(12, dtype=np.float64).reshape(4, 3)

    write_result = store.write_trace(
        design_id=42,
        batch_id=105,
        trace_id=9001,
        values=values,
        axes=[
            {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0, 6.0, 7.0]},
            {"name": "L_jun", "unit": "nH", "values": [8.0, 9.0, 10.0]},
        ],
    )

    assert write_result.axes == [
        {"name": "frequency", "unit": "GHz", "length": 4},
        {"name": "L_jun", "unit": "nH", "length": 3},
    ]
    assert write_result.store_ref["backend"] == "local_zarr"
    assert write_result.store_ref["store_key"] == "designs/42/batches/105.zarr"
    assert write_result.store_ref["group_path"] == "/traces/9001"
    assert write_result.store_ref["array_path"] == "values"
    assert write_result.store_ref["shape"] == [4, 3]
    assert write_result.store_ref["chunk_shape"] == [4, 1]
    assert write_result.store_ref["schema_version"] == TRACE_STORE_SCHEMA_VERSION
    assert write_result.store_ref["payload_role"] == "raw"
    assert write_result.store_ref["store_uri"].endswith("designs/42/batches/105.zarr")

    read_column = store.read_trace_slice(write_result.store_ref, selection=(slice(None), 1))
    np.testing.assert_array_equal(read_column, values[:, 1])

    read_row = store.read_trace_slice(write_result.store_ref, selection=(1, slice(None)))
    np.testing.assert_array_equal(read_row, values[1, :])

    axis_values = store.read_axis_slice(
        write_result.store_ref,
        axis_name="frequency",
        selection=slice(1, 3),
    )
    np.testing.assert_array_equal(axis_values, np.array([5.0, 6.0]))


def test_local_zarr_trace_store_supports_incremental_slice_writes(tmp_path) -> None:
    store = LocalZarrTraceStore(root_path=tmp_path / "trace_store")
    write_result = store.create_trace(
        design_id=42,
        batch_id=105,
        trace_id=9002,
        shape=(4, 3),
        dtype=np.float64,
        axes=[
            {"name": "frequency", "unit": "GHz", "values": [4.0, 5.0, 6.0, 7.0]},
            {"name": "L_q", "unit": "nH", "values": [10.0, 12.0, 14.0]},
        ],
        chunk_shape=(4, 1),
        payload_role="processed",
    )

    root = zarr.open_group(store=tmp_path / "trace_store" / "designs/42/batches/105.zarr", mode="r")
    version_markers = dict(root["traces"]["9002"].attrs["version_markers"])

    assert write_result.store_ref["payload_role"] == "processed"
    assert version_markers["schema_version"] == TRACE_STORE_SCHEMA_VERSION
    assert version_markers["payload_role"] == "processed"

    store.write_trace_slice(
        write_result.store_ref,
        selection=(slice(None), 0),
        values=np.array([1.0, 2.0, 3.0, 4.0]),
    )
    store.write_trace_slice(
        write_result.store_ref,
        selection=(slice(None), 2),
        values=np.array([5.0, 6.0, 7.0, 8.0]),
    )

    np.testing.assert_array_equal(
        store.read_trace_slice(write_result.store_ref, selection=(slice(None), 0)),
        np.array([1.0, 2.0, 3.0, 4.0]),
    )
    np.testing.assert_array_equal(
        store.read_trace_slice(write_result.store_ref, selection=(slice(None), 2)),
        np.array([5.0, 6.0, 7.0, 8.0]),
    )


def test_trace_store_ref_accepts_s3_backend_as_extension_direction() -> None:
    ref = coerce_trace_store_ref(
        {
            "backend": "s3_zarr",
            "store_key": "designs/42/batches/105.zarr",
            "store_uri": "s3://trace-bucket/designs/42/batches/105.zarr",
            "group_path": "/traces/9001",
            "array_path": "values",
            "dtype": "float64",
            "shape": [4001, 11],
            "chunk_shape": [4001, 1],
            "schema_version": "1.0",
            "payload_role": "analysis",
        }
    )

    assert ref["backend"] == "s3_zarr"
    assert ref["store_key"] == "designs/42/batches/105.zarr"
    assert ref["payload_role"] == "analysis"


def test_trace_store_ref_derives_store_key_from_legacy_local_store_uri() -> None:
    ref = coerce_trace_store_ref(
        {
            "backend": "local_zarr",
            "store_uri": "data/trace_store/designs/42/batches/105.zarr",
            "group_path": "/traces/9001",
            "array_path": "values",
            "dtype": "float64",
            "shape": [4001, 11],
            "chunk_shape": [4001, 1],
            "schema_version": "1.0",
        }
    )

    assert ref["store_key"] == "designs/42/batches/105.zarr"
    assert ref["store_uri"] == "data/trace_store/designs/42/batches/105.zarr"


def test_data_record_uses_store_ref_shape_metadata_without_inline_values() -> None:
    record = DataRecord(
        dataset_id=1,
        data_type="y_params",
        parameter="Y11",
        representation="imaginary",
        axes=[
            {"name": "frequency", "unit": "GHz", "length": 4001},
            {"name": "L_jun", "unit": "nH", "length": 11},
        ],
        values=[],
        store_ref={
            "backend": "local_zarr",
            "store_key": "designs/1/batches/2.zarr",
            "store_uri": "data/trace_store/designs/1/batches/2.zarr",
            "group_path": "/traces/3",
            "array_path": "values",
            "dtype": "float64",
            "shape": [4001, 11],
            "chunk_shape": [4001, 1],
            "schema_version": "1.0",
        },
    )

    assert record.trace_shape() == (4001, 11)
    assert record.axis_length(0) == 4001
    assert record.axis_length(1) == 11
