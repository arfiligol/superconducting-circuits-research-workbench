import time

import pytest
from fastapi.testclient import TestClient
from rq import Queue, SimpleWorker
from src.app.infrastructure.runtime import (
    get_queue_connection_factory,
    get_worker_runtime_settings,
    reset_runtime_state,
)
from src.app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    reset_runtime_state()
    client.cookies.clear()


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
    task_id: int,
    *,
    lane: str,
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    detail: dict[str, object] | None = None
    while time.time() < deadline:
        _drain_lane_queue(lane)
        detail = client.get(f"/tasks/{task_id}").json()["data"]
        if (
            detail["status"] == "completed"
            and detail["result_handoff"]["availability"] == "ready"
        ):
            return detail
        time.sleep(0.05)

    raise AssertionError(
        f"Task {task_id} did not complete within {timeout_seconds:.1f}s; last detail={detail!r}"
    )


def _simulation_setup_payload(
    *,
    parameter_sweeps: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "frequency_sweep": {
            "start_ghz": 4.0,
            "stop_ghz": 8.0,
            "point_count": 401,
            "spacing": "linear",
        },
        "parameter_sweeps": parameter_sweeps,
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
    }


def _create_two_port_sweepable_definition(name: str) -> str:
    response = client.post(
        "/circuit-definitions",
        json={
            "name": name,
            "source_text": """{
  "name": "TwoPortSweepableReadout",
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
    assert response.status_code == 201
    return str(response.json()["data"]["definition"]["definition_id"])


def _submit_simulation_and_wait(
    *,
    definition_id: str,
    parameter_sweeps: list[dict[str, object]],
) -> dict[str, object]:
    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "dataset_id": "local-dataset-001",
            "definition_id": definition_id,
            "summary": "Simulation workflow integration fixture.",
            "simulation_setup": _simulation_setup_payload(
                parameter_sweeps=parameter_sweeps,
            ),
        },
    )
    assert response.status_code == 201
    task = response.json()["data"]["task"]
    return _wait_for_task_ready(int(task["task_id"]), lane="simulation")


def _submit_post_processing_and_wait(
    *,
    upstream_task_id: int,
) -> dict[str, object]:
    response = client.post(
        "/tasks",
        json={
            "kind": "post_processing",
            "dataset_id": "local-dataset-001",
            "summary": "Post-processing workflow integration fixture.",
            "upstream_task_id": upstream_task_id,
            "post_processing_setup": {
                "selections": [
                    {
                        "trace_family": "z_matrix",
                        "representation": "real",
                        "design_id": "design_local_flux_playground",
                        "trace_ids": ["trace_local_flux_preview"],
                    }
                ],
                "operations": [
                    {
                        "operation": "coordinate_transform",
                        "enabled": True,
                        "config": {
                            "template": "cm_dm",
                            "weight_mode": "auto",
                            "alpha": 0.5,
                            "beta": 0.5,
                            "port_a": 1,
                            "port_b": 2,
                        },
                    },
                    {
                        "operation": "kron_reduction",
                        "enabled": True,
                        "config": {"keep_labels": ["DM(1,2)"]},
                    },
                ],
            },
        },
    )
    assert response.status_code == 201
    task = response.json()["data"]["task"]
    return _wait_for_task_ready(int(task["task_id"]), lane="simulation")


def _create_design(name: str) -> str:
    response = client.post(
        "/datasets/local-dataset-001/designs",
        json={"name": name},
    )
    assert response.status_code == 201
    return str(response.json()["data"]["design"]["design_id"])


def _trace_keys_from_view(task_id: int, query: str) -> list[str]:
    response = client.get(f"/tasks/{task_id}/simulation-results/view{query}")
    assert response.status_code == 200
    return [
        str(series["trace_key"])
        for series in response.json()["data"]["plot"]["series"]
        if isinstance(series.get("trace_key"), str)
    ]


def test_simulation_workflow_integration_covers_submit_explorer_and_bulk_save() -> None:
    definition_id = _create_two_port_sweepable_definition("SimulationWorkflowIntegrationDefinition")

    single_axis_task = _submit_simulation_and_wait(
        definition_id=definition_id,
        parameter_sweeps=[
            {
                "parameter": "Lj",
                "values": [850.0, 1000.0, 1150.0],
                "unit": "pH",
            }
        ],
    )
    assert single_axis_task["status"] == "completed"
    assert single_axis_task["result_handoff"]["availability"] == "ready"

    bootstrap = client.get(
        f"/tasks/{single_axis_task['task_id']}/simulation-results/bootstrap"
    )
    assert bootstrap.status_code == 200
    bootstrap_payload = bootstrap.json()["data"]
    assert bootstrap_payload["task_id"] == single_axis_task["task_id"]
    assert bootstrap_payload["task_status"] == "completed"
    assert bootstrap_payload["bootstrap"]["parameter_sweep"] == {
        "active": True,
        "point_count": 3,
        "compare_axis_index": 0,
        "axes": [
            {
                "parameter": "Lj",
                "label": "Lj",
                "unit": "pH",
                "values": [850.0, 1000.0, 1150.0],
                "selected_value_index": 0,
            }
        ],
    }

    single_axis_view = client.get(
        f"/tasks/{single_axis_task['task_id']}/simulation-results/view"
        "?family=s_matrix&source=raw&metric=magnitude_db&output_port=1&input_port=1"
        "&sweep_index=0&compare_axis_index=0"
    )
    assert single_axis_view.status_code == 200
    single_axis_payload = single_axis_view.json()["data"]
    assert single_axis_payload["selection"]["compare_axis_index"] == 0
    assert [series["label"] for series in single_axis_payload["plot"]["series"]] == [
        "Lj = 850 pH",
        "Lj = 1000 pH",
        "Lj = 1150 pH",
    ]

    bulk_design_id = _create_design("Simulation Workflow Visible Trace Save")
    bulk_publish = client.post(
        f"/tasks/{single_axis_task['task_id']}/result-traces/publish",
        json={
            "design_id": bulk_design_id,
            "trace_keys": _trace_keys_from_view(
                single_axis_task["task_id"],
                (
                    "?family=s_matrix&source=raw&metric=magnitude_db&output_port=1&input_port=1"
                    "&sweep_index=0&compare_axis_index=0"
                ),
            ),
            "parameter_name": "Readout Admittance",
        },
    )
    assert bulk_publish.status_code == 200
    bulk_payload = bulk_publish.json()["data"]
    assert bulk_payload["operation"] == "published"
    assert len(bulk_payload["traces"]) == 3
    assert [trace["parameter"] for trace in bulk_payload["traces"]] == [
        "Readout Admittance · Lj = 850 pH",
        "Readout Admittance · Lj = 1000 pH",
        "Readout Admittance · Lj = 1150 pH",
    ]

    multi_axis_task = _submit_simulation_and_wait(
        definition_id=definition_id,
        parameter_sweeps=[
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
    )
    assert multi_axis_task["status"] == "completed"
    assert multi_axis_task["result_handoff"]["availability"] == "ready"

    compare_axis_view = client.get(
        f"/tasks/{multi_axis_task['task_id']}/simulation-results/view"
        "?family=s_matrix&source=raw&metric=magnitude_db&output_port=1&input_port=1"
        "&sweep_index=5&compare_axis_index=1"
    )
    assert compare_axis_view.status_code == 200
    compare_axis_payload = compare_axis_view.json()["data"]
    assert compare_axis_payload["selection"]["sweep_index"] == 5
    assert compare_axis_payload["selection"]["compare_axis_index"] == 1
    assert [series["label"] for series in compare_axis_payload["plot"]["series"]] == [
        "Cj = 900 fF",
        "Cj = 1000 fF",
    ]


def test_post_processing_workflow_integration_covers_kron_kept_ports_and_single_trace_save(
) -> None:
    definition_id = _create_two_port_sweepable_definition(
        "PostProcessingWorkflowIntegrationDefinition"
    )
    simulation_task = _submit_simulation_and_wait(
        definition_id=definition_id,
        parameter_sweeps=[
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
    )
    assert simulation_task["status"] == "completed"

    post_processing_task = _submit_post_processing_and_wait(
        upstream_task_id=int(simulation_task["task_id"]),
    )
    assert post_processing_task["status"] == "completed"
    assert post_processing_task["result_handoff"]["availability"] == "ready"

    bootstrap = client.get(
        f"/tasks/{post_processing_task['task_id']}/simulation-results/bootstrap"
    )
    assert bootstrap.status_code == 200
    bootstrap_payload = bootstrap.json()["data"]
    output_ports = bootstrap_payload["bootstrap"]["trace_selector"]["output_ports"]
    input_ports = bootstrap_payload["bootstrap"]["trace_selector"]["input_ports"]
    assert len(output_ports) == 1
    assert len(input_ports) == 1
    assert "DM" in output_ports[0]["label"]
    assert "DM" in input_ports[0]["label"]

    post_processing_view = client.get(
        f"/tasks/{post_processing_task['task_id']}/simulation-results/view"
        "?family=z_matrix&source=raw&metric=real&z0=50&output_port=1&input_port=1"
    )
    assert post_processing_view.status_code == 200
    post_processing_payload = post_processing_view.json()["data"]
    assert post_processing_payload["selection"]["output_port_label"] == output_ports[0]["label"]
    assert post_processing_payload["selection"]["input_port_label"] == input_ports[0]["label"]
    assert len(post_processing_payload["plot"]["series"]) >= 1

    single_design_id = _create_design("Post Processing Visible Trace Save")
    visible_trace_keys = _trace_keys_from_view(
        int(post_processing_task["task_id"]),
        "?family=z_matrix&source=raw&metric=real&z0=50&output_port=1&input_port=1",
    )
    assert len(visible_trace_keys) >= 1
    single_publish = client.post(
        f"/tasks/{post_processing_task['task_id']}/result-traces/publish",
        json={
            "design_id": single_design_id,
            "trace_keys": [visible_trace_keys[0]],
            "parameter_name": "Reduced Z11",
        },
    )
    assert single_publish.status_code == 200
    single_payload = single_publish.json()["data"]
    assert single_payload["operation"] == "published"
    assert len(single_payload["traces"]) == 1
    assert single_payload["traces"][0]["parameter"] == "Reduced Z11"
    assert single_payload["traces"][0]["stage_kind"] == "postprocess"
