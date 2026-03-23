from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient
from rq import Queue, SimpleWorker
from src.app.infrastructure.runtime import (
    get_queue_connection_factory,
    get_worker_runtime_settings,
    reset_runtime_state,
)
from src.app.main import app


def _queue_for_lane(lane: str) -> Queue:
    settings = get_worker_runtime_settings()
    return Queue(
        settings.queue_name_for_lane(lane),
        connection=get_queue_connection_factory()(),
    )


def _drain_lane_queue(lane: str) -> None:
    queue = _queue_for_lane(lane)
    worker = SimpleWorker([queue], connection=queue.connection)
    worker.work(burst=True)


def _wait_for_task_ready(
    client: TestClient,
    task_id: int,
    *,
    lane: str,
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    detail: dict[str, object] | None = None
    while time.time() < deadline:
        _drain_lane_queue(lane)
        detail_response = client.get(f"/tasks/{task_id}")
        detail_response.raise_for_status()
        detail = detail_response.json()["data"]
        if (
            detail["status"] == "completed"
            and detail["result_handoff"]["availability"] == "ready"
        ):
            return detail
        time.sleep(0.05)

    raise RuntimeError(
        f"Failed to materialize the frontend simulation E2E fixture within {timeout_seconds:.1f}s; "
        f"last detail={detail!r}"
    )


def _seed_fixture() -> dict[str, object]:
    reset_runtime_state()
    client = TestClient(app)
    client.cookies.clear()

    definition_response = client.post(
        "/circuit-definitions",
        json={
            "name": "FrontendE2ESimulationDefinition",
            "source_text": """{
  "name": "FrontendE2ETwoPortSweepableReadout",
  "parameters": [
    {"name": "Lj", "default": 1000.0, "unit": "pH"},
    {"name": "Cj", "default": 1000.0, "unit": "fF"}
  ],
  "components": [
    {"name": "R1", "default": 50.0, "unit": "Ohm"},
    {"name": "R2", "default": 50.0, "unit": "Ohm"},
    {"name": "Lj1", "value_ref": "Lj", "unit": "pH"},
    {"name": "C1", "value_ref": "Cj", "unit": "fF"}
  ],
  "topology": [
    ("P1", "1", "0", 1),
    ("R1", "1", "0", "R1"),
    ("P2", "2", "0", 2),
    ("R2", "2", "0", "R2"),
    ("Lj1", "1", "2", "Lj1"),
    ("C1", "1", "2", "C1")
  ]
}""",
        },
    )
    definition_response.raise_for_status()
    definition_id = str(definition_response.json()["data"]["definition"]["definition_id"])

    simulation_response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "dataset_id": "local-dataset-001",
            "definition_id": definition_id,
            "summary": "Frontend E2E compare-axis simulation fixture.",
            "simulation_setup": {
                "frequency_sweep": {
                    "start_ghz": 4.0,
                    "stop_ghz": 8.0,
                    "point_count": 401,
                    "spacing": "linear",
                },
                "parameter_sweeps": [
                    {
                        "parameter": "Lj",
                        "values": [850.0, 1000.0, 1150.0],
                        "unit": "pH",
                    },
                    {
                        "parameter": "Cj",
                        "values": [900.0, 1000.0],
                        "unit": "fF",
                    },
                ],
                "solver": {
                    "solver_family": "harmonic_balance",
                    "max_iterations": 20,
                    "convergence_tolerance": 1e-6,
                    "harmonic_balance": {
                        "enabled": True,
                        "harmonic_count": 5,
                        "oversample_factor": 2,
                    },
                },
                "sources": [
                    {
                        "source_id": "port_1_drive",
                        "kind": "port_drive",
                        "target": "port_1",
                        "amplitude": -30.0,
                        "frequency_ghz": 5.0,
                        "phase_deg": 0.0,
                    }
                ],
                "ptc": {
                    "enabled": False,
                    "mode": "auto",
                    "compensate_ports": ["port_1", "port_2"],
                },
            },
        },
    )
    simulation_response.raise_for_status()
    simulation_task_id = int(simulation_response.json()["data"]["task"]["task_id"])
    _wait_for_task_ready(client, simulation_task_id, lane="simulation")

    reset_runtime_state()
    return {
        "definition_id": definition_id,
        "simulation_task_id": simulation_task_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-path", required=True)
    parser.add_argument("--audit-database-path", required=True)
    parser.add_argument("--output-path", required=True)
    args = parser.parse_args()

    os.environ["SC_DATABASE_PATH"] = args.database_path
    os.environ["SC_AUDIT_DATABASE_PATH"] = args.audit_database_path
    os.environ.setdefault("SC_RQ_REDIS_URL", "fakeredis://frontend-simulation-e2e")

    payload = _seed_fixture()
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    main()
