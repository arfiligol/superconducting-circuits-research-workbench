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
    assert claim_payload["task"]["task_kind"] == "julia_runner_smoke"

    heartbeat_response = client.post(f"/runner/v1/tasks/{created['task_id']}/heartbeat")
    assert heartbeat_response.status_code == 200
    assert heartbeat_response.json()["data"]["status"] == "running"

    progress_response = client.post(
        f"/runner/v1/tasks/{created['task_id']}/progress",
        json={"percent_complete": 33, "summary": "Runner smoke progress."},
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
            "manifest_path": claim_payload["staging"]["manifest"],
            "manifest_sha256": manifest_sha256,
            "output_target": {
                "dataset_id": "local-dataset-001",
                "design_id": "design_runner_smoke",
            },
        },
    )
    assert complete_response.status_code == 200
    publication = complete_response.json()["data"]["publication"]
    assert publication["store_key"] == (
        "datasets/local-dataset-001/designs/design_runner_smoke/"
        f"batches/batch_{created['task_id']}.zarr"
    )
    assert publication["trace_ids"] == ["S11"]

    detail = client.get(f"/tasks/{created['task_id']}").json()["data"]
    assert detail["status"] == "completed"

    traces_response = client.get(
        "/datasets/local-dataset-001/designs/design_runner_smoke/traces"
    )
    assert traces_response.status_code == 200
    traces = traces_response.json()["data"]["rows"]
    assert [trace["trace_id"] for trace in traces] == ["S11"]
    assert traces[0]["shape"] == [5]


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


def _submit_simulation_task(*, summary: str = "Runner smoke publication.") -> dict[str, object]:
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
                    "solver_family": "runner-smoke",
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
    result_root = task_dir / "result.zarr"
    _write_group(result_root)
    _write_group(result_root / "axes")
    _write_group(result_root / "traces")
    _write_group(result_root / "traces" / "S11")
    _write_zarr_array(result_root / "axes" / "frequency", [4.0e9, 4.5e9, 5.0e9, 5.5e9, 6.0e9])
    _write_zarr_array(result_root / "traces" / "S11" / "real", [1.0, 0.5, 0.0, -0.5, -1.0])
    _write_zarr_array(result_root / "traces" / "S11" / "imag", [0.0, 0.1, 0.2, 0.1, 0.0])
    (task_dir / "logs").mkdir(parents=True, exist_ok=True)
    (task_dir / "logs" / "runner.log").write_text("runner smoke\n")
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
