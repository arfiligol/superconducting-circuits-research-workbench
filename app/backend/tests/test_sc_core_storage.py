from sc_core.execution import TaskResultHandle
from sc_core.storage import (
    STORAGE_CONTRACT_VERSION,
    TraceBatchHandle,
    TraceBatchProvenance,
    TraceResultLinkage,
    TraceStoreLocator,
)


def test_trace_store_locator_round_trips_current_store_ref_shape() -> None:
    locator = TraceStoreLocator.from_mapping(
        {
            "backend": "local_zarr",
            "store_key": "designs/42/batches/105.zarr",
            "store_uri": "data/trace_store/designs/42/batches/105.zarr",
            "group_path": "/traces/9001",
            "array_path": "values",
            "dtype": "float64",
            "shape": [4, 3],
            "chunk_shape": [4, 1],
            "schema_version": "1.0",
        }
    )

    assert locator.shape == (4, 3)
    assert locator.chunk_shape == (4, 1)
    assert locator.to_payload()["contract_version"] == STORAGE_CONTRACT_VERSION


def test_trace_batch_provenance_extracts_snapshot_aliases() -> None:
    provenance = TraceBatchProvenance.from_snapshot(
        {
            "id": 88,
            "design_id": 7,
            "source_kind": "circuit_simulation",
            "stage_kind": "postprocess",
            "status": "completed",
            "parent_batch_id": 41,
            "setup_kind": "circuit_simulation.postprocess",
            "setup_version": "1.0",
            "provenance_payload": {"source_simulation_bundle_id": 41},
            "setup_payload": {"setup_kind": "circuit_simulation.postprocess"},
            "summary_payload": {"run_kind": "parameter_sweep"},
        }
    )

    assert provenance.source_kind == "circuit_simulation"
    assert provenance.stage_kind == "postprocess"
    assert provenance.source_batch_id == 41
    assert provenance.run_kind == "parameter_sweep"


def test_trace_result_linkage_and_batch_handle_build_from_current_contracts() -> None:
    linkage = TraceResultLinkage.from_result_handle(
        TaskResultHandle(trace_batch_id=88, analysis_run_id=12)
    )
    batch = TraceBatchHandle.from_snapshot(
        {
            "id": 88,
            "design_id": 7,
            "source_kind": "circuit_simulation",
            "stage_kind": "raw",
            "status": "completed",
            "parent_batch_id": None,
            "setup_kind": "circuit_simulation.raw",
            "setup_version": "1.0",
            "provenance_payload": {},
            "setup_payload": {"setup_kind": "circuit_simulation.raw"},
            "summary_payload": {"run_kind": "single_run"},
        }
    )

    assert linkage.has_outputs() is True
    assert linkage.to_payload() == {"trace_batch_id": 88, "analysis_run_id": 12}
    assert batch.trace_batch_id == 88
    assert batch.provenance.stage_kind == "raw"
