import hashlib
import json
import struct
from pathlib import Path

from fastapi.testclient import TestClient
from src.app.infrastructure.rewrite_catalog_repository import (
    LOCAL_SPACE_RESONATOR_DEFINITION_ID,
)
from src.app.main import app

client = TestClient(app)


def test_runner_claim_complete_publishes_staged_zarr() -> None:
    created = _submit_simulation_task()

    claim_response = client.post("/runner/v1/tasks/claim")
    assert claim_response.status_code == 200
    claim_payload = claim_response.json()["data"]
    assert claim_payload["task"]["task_id"] == str(created["task_id"])
    assert claim_payload["task"]["task_kind"] == "julia_simulation_frequency_sweep"

    heartbeat_response = client.post(f"/runner/v1/tasks/{created['task_id']}/heartbeat")
    assert heartbeat_response.status_code == 200
    assert heartbeat_response.json()["data"]["status"] == "running"

    progress_response = client.post(
        f"/runner/v1/tasks/{created['task_id']}/progress",
        json={"percent_complete": 33, "summary": "Runner fixture progress."},
    )
    assert progress_response.status_code == 200
    assert progress_response.json()["data"]["status"] == "running"

    cancellation_response = client.get(f"/runner/v1/tasks/{created['task_id']}/cancellation")
    assert cancellation_response.status_code == 200
    assert cancellation_response.json()["data"]["cancelled"] is False

    task_dir = _repo_root() / Path(claim_payload["staging"]["task_dir"])
    manifest_path = _write_small_result_package(task_dir, task_id=str(created["task_id"]))
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    complete_response = client.post(
        f"/runner/v1/tasks/{created['task_id']}/complete",
        json={
            "runner_id": "runner_test_001",
            "manifest_path": f"tasks/{created['task_id']}/manifest.json",
            "manifest_sha256": manifest_sha256,
        },
    )
    assert complete_response.status_code == 200
    publication = complete_response.json()["data"]["publication"]
    assert publication["store_key"] == (
        f"datasets/local-dataset-001/designs/{LOCAL_SPACE_RESONATOR_DEFINITION_ID}/"
        f"batches/batch_{created['task_id']}.zarr"
    )
    assert publication["trace_ids"] == [f"batch_{created['task_id']}:S11"]

    detail = client.get(f"/tasks/{created['task_id']}").json()["data"]
    assert detail["status"] == "completed"

    traces_response = client.get(
        f"/datasets/local-dataset-001/designs/{LOCAL_SPACE_RESONATOR_DEFINITION_ID}/traces"
    )
    assert traces_response.status_code == 200
    traces = traces_response.json()["data"]["rows"]
    published_trace = next(
        trace for trace in traces if trace["trace_id"] == f"batch_{created['task_id']}:S11"
    )
    assert published_trace["shape"] == [5]


def test_runner_complete_rejects_output_target_override() -> None:
    created = _submit_simulation_task(summary="Runner output target guard.")
    claim_payload = client.post("/runner/v1/tasks/claim").json()["data"]
    task_dir = _repo_root() / Path(claim_payload["staging"]["task_dir"])
    manifest_path = _write_small_result_package(task_dir, task_id=str(created["task_id"]))

    response = client.post(
        f"/runner/v1/tasks/{created['task_id']}/complete",
        json={
            "runner_id": "runner_test_001",
            "manifest_path": claim_payload["staging"]["manifest"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "output_target": {
                "dataset_id": "other-dataset",
                "design_id": "other-design",
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "runner_complete_output_target_forbidden"


def test_runner_complete_rejects_unreadable_zarr_chunk() -> None:
    created = _submit_simulation_task(summary="Runner unreadable Zarr guard.")
    claim_payload = client.post("/runner/v1/tasks/claim").json()["data"]
    task_dir = _repo_root() / Path(claim_payload["staging"]["task_dir"])
    manifest_path = _write_small_result_package(task_dir, task_id=str(created["task_id"]))
    (task_dir / "result.zarr" / "traces" / "S11" / "real" / "0").unlink()

    response = client.post(
        f"/runner/v1/tasks/{created['task_id']}/complete",
        json={
            "runner_id": "runner_test_001",
            "manifest_path": claim_payload["staging"]["manifest"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "runner_zarr_unreadable"


def test_runner_publication_trace_ids_are_batch_scoped() -> None:
    first = _publish_small_runner_result("First repeated S11 publish.")
    second = _publish_small_runner_result("Second repeated S11 publish.")

    assert first["publication"]["trace_ids"] == [f"batch_{first['task_id']}:S11"]
    assert second["publication"]["trace_ids"] == [f"batch_{second['task_id']}:S11"]

    traces_response = client.get(
        f"/datasets/local-dataset-001/designs/{LOCAL_SPACE_RESONATOR_DEFINITION_ID}/traces"
    )
    assert traces_response.status_code == 200
    trace_ids = {trace["trace_id"] for trace in traces_response.json()["data"]["rows"]}
    assert f"batch_{first['task_id']}:S11" in trace_ids
    assert f"batch_{second['task_id']}:S11" in trace_ids


def test_runner_complete_rejects_path_traversal() -> None:
    created = _submit_simulation_task(summary="Runner path traversal guard.")
    response = client.post(
        f"/runner/v1/tasks/{created['task_id']}/complete",
        json={
            "runner_id": "runner_test_001",
            "manifest_path": "../manifest.json",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "runner_path_invalid"


def _publish_small_runner_result(summary: str) -> dict[str, object]:
    created = _submit_simulation_task(summary=summary)
    claim_payload = client.post("/runner/v1/tasks/claim").json()["data"]
    task_dir = _repo_root() / Path(claim_payload["staging"]["task_dir"])
    manifest_path = _write_small_result_package(task_dir, task_id=str(created["task_id"]))
    response = client.post(
        f"/runner/v1/tasks/{created['task_id']}/complete",
        json={
            "runner_id": "runner_test_001",
            "manifest_path": claim_payload["staging"]["manifest"],
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        },
    )
    assert response.status_code == 200
    return {
        "task_id": created["task_id"],
        "publication": response.json()["data"]["publication"],
    }


def _submit_simulation_task(
    *, summary: str = "Runner staged-result publication fixture."
) -> dict[str, object]:
    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "definition_id": LOCAL_SPACE_RESONATOR_DEFINITION_ID,
            "summary": summary,
            "simulation_setup": {
                "frequency_sweep": {
                    "start_ghz": 4.0,
                    "stop_ghz": 6.0,
                    "point_count": 5,
                    "spacing": "linear",
                },
                "parameter_sweeps": [],
                "solver": {
                    "solver_family": "josephson_circuits",
                    "max_iterations": 1,
                    "convergence_tolerance": 1e-6,
                    "harmonic_balance": {"enabled": False},
                },
                "sources": [
                    {
                        "source_id": "drive-port-a",
                        "kind": "port_drive",
                        "target": "port_1",
                        "amplitude": -35.0,
                    }
                ],
                "ptc": None,
            },
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["task"]


def _write_small_result_package(task_dir: Path, *, task_id: str) -> Path:
    """Write a tiny test fixture package for Backend publication validation only."""

    result_root = task_dir / "result.zarr"
    _write_group(result_root)
    _write_group(result_root / "axes")
    _write_group(result_root / "traces")
    _write_group(result_root / "traces" / "S11")
    _write_zarr_array(result_root / "axes" / "frequency", [4.0e9, 4.5e9, 5.0e9, 5.5e9, 6.0e9])
    _write_zarr_array(result_root / "traces" / "S11" / "real", [1.0, 0.5, 0.0, -0.5, -1.0])
    _write_zarr_array(result_root / "traces" / "S11" / "imag", [0.0, 0.1, 0.2, 0.1, 0.0])
    (task_dir / "logs").mkdir(parents=True, exist_ok=True)
    (task_dir / "logs" / "runner.log").write_text("runner staged-result fixture\n")
    manifest = {
        "schema_version": "sc.runner.result.v1",
        "task_id": task_id,
        "producer": {
            "runner": "SuperconductingCircuitsRunner",
            "runner_version": "0.1.0",
            "core_version": "0.1.0",
            "julia_version": "1.11",
        },
        "array_store": {"format": "zarr", "zarr_format": 2, "uri": "result.zarr"},
        "sweep": {
            "total_points": 1,
            "success_points": 1,
            "failed_points": 0,
            "failed": [],
        },
        "traces": [
            {
                "trace_key": "S11",
                "family": "s_matrix",
                "parameter": "S11",
                "representation": "complex",
                "real_path": "/traces/S11/real",
                "imag_path": "/traces/S11/imag",
                "shape": [5],
                "chunk_shape": [5],
                "dtype": "float64",
                "axes": [
                    {
                        "name": "frequency",
                        "unit": "Hz",
                        "path": "/axes/frequency",
                    }
                ],
            }
        ],
        "summary_tables": [],
        "logs": [{"kind": "runner_log", "path": "logs/runner.log"}],
    }
    manifest_path = task_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return manifest_path


def _write_group(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".zgroup").write_text(json.dumps({"zarr_format": 2}))


def _write_zarr_array(path: Path, values: list[float]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / ".zarray").write_text(
        json.dumps(
            {
                "zarr_format": 2,
                "shape": [len(values)],
                "chunks": [len(values)],
                "dtype": "<f8",
                "compressor": None,
                "fill_value": None,
                "order": "C",
                "filters": None,
            }
        )
    )
    (path / "0").write_bytes(struct.pack(f"<{len(values)}d", *values))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
