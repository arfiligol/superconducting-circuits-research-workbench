import time
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from src.app.domain.tasks import TaskLifecycleUpdate
from src.app.infrastructure.runtime import (
    get_rewrite_app_state_repository,
    get_task_service,
    reset_runtime_state,
)
from src.app.main import app
from tests.worker_runtime_harness import drain_lane_queue

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_app_state() -> None:
    reset_runtime_state()
    client.cookies.clear()


def _login() -> None:
    switched = client.patch(
        "/session/runtime-mode",
        json={
            "runtime_mode": "online",
            "server_origin": "http://127.0.0.1:8000",
            "label": "Default Rewrite Server",
        },
    )
    assert switched.status_code == 200
    response = client.post(
        "/session/login",
        json={
            "email": "rewrite.local@example.com",
            "password": "rewrite-local-password",
        },
    )
    assert response.status_code == 200


def _simulation_setup_payload(
    *,
    ptc_enabled: bool,
    parameter_sweeps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "frequency_sweep": {
            "start_ghz": 1.0,
            "stop_ghz": 8.0,
            "point_count": 401,
            "spacing": "linear",
        },
        "parameter_sweeps": parameter_sweeps or [],
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
            "enabled": ptc_enabled,
            "mode": "auto",
            "compensate_ports": ["port_1", "port_2"],
        },
    }


def _submit_local_simulation(
    *,
    definition_id: int = 3,
    ptc_enabled: bool = True,
    parameter_sweeps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    response = client.post(
        "/tasks",
        json={
            "kind": "simulation",
            "dataset_id": "local-dataset-001",
            "definition_id": definition_id,
            "summary": "Result publication source task.",
            "simulation_setup": _simulation_setup_payload(
                ptc_enabled=ptc_enabled,
                parameter_sweeps=parameter_sweeps,
            ),
        },
    )
    assert response.status_code == 201
    task = response.json()["data"]["task"]
    detail = task
    for _ in range(3):
        drain_lane_queue("simulation")
        for _ in range(5):
            detail = client.get(f"/tasks/{task['task_id']}").json()["data"]
            if (
                detail["status"] == "completed"
                and detail["result_handoff"]["availability"] == "ready"
            ):
                return detail
            time.sleep(0.05)
    return detail


def _published_trace_ids(task_id: int, *, include_ptc: bool) -> list[str]:
    trace_ids = [
        f"trace_simulation_task_{task_id}_s_matrix_raw",
        f"trace_simulation_task_{task_id}_y_matrix_raw",
        f"trace_simulation_task_{task_id}_z_matrix_raw",
    ]
    if include_ptc:
        trace_ids.extend(
            [
                f"trace_simulation_task_{task_id}_y_matrix_ptc",
                f"trace_simulation_task_{task_id}_z_matrix_ptc",
            ]
        )
    return trace_ids


def _trace_key(
    *,
    family: str,
    source: str,
    output_port: int = 1,
    input_port: int = 1,
    z0_ohm: int | None = None,
) -> str:
    parts = [
        f"family={family}",
        f"source={source}",
        "trace_mode_group=base",
        f"output_port={output_port}",
        f"input_port={input_port}",
        "output_mode=mode_0",
        "input_mode=mode_0",
    ]
    if z0_ohm is not None:
        parts.append(f"z0_ohm={z0_ohm}")
    return "|".join(parts)


def _create_sweepable_definition(name: str) -> int:
    response = client.post(
        "/circuit-definitions",
        json={
            "name": name,
            "source_text": """{
  "name": "SweepableReadoutChain",
  "parameters": [
    {"name": "Lj", "default": 1000.0, "unit": "pH"}
  ],
  "components": [
    {"name": "R1", "default": 50.0, "unit": "Ohm"},
    {"name": "C1", "default": 100.0, "unit": "fF"},
    {"name": "Lj1", "value_ref": "Lj", "unit": "pH"}
  ],
  "topology": [
    ("P1", "1", "0", 1),
    ("R1", "1", "0", "R1"),
    ("C1", "1", "2", "C1"),
    ("Lj1", "2", "0", "Lj1")
  ]
}""",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["definition"]["definition_id"]


@contextmanager
def _bind_client_app_context(test_client: TestClient):
    app_context_id = test_client.cookies.get("sc_app_context")
    assert app_context_id is not None
    repository = get_rewrite_app_state_repository()
    binding = repository.bind_request_app_context_id(app_context_id)
    try:
        yield
    finally:
        repository.reset_request_app_context_id(binding)


def test_completed_simulation_task_can_be_published_and_is_queryable() -> None:
    task = _submit_local_simulation(ptc_enabled=True)

    before_publish = client.get(f"/tasks/{task['task_id']}")
    assert before_publish.status_code == 200
    assert before_publish.json()["data"]["publication_summary"] == {
        "state": "not_published",
        "publish_allowed": True,
        "publication_key": None,
        "target_dataset_id": None,
        "target_design_id": None,
        "target_design_name": None,
        "published_trace_ids": [],
        "published_at": None,
        "source_task_id": task["task_id"],
        "source_result_handle_ids": [
            f"task-result:{task['task_id']}:primary",
        ],
    }

    publish_response = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={
            "dataset_id": "local-dataset-001",
            "design_name": "Fluxonium Simulation Save",
        },
    )

    assert publish_response.status_code == 200
    payload = publish_response.json()["data"]
    assert payload["operation"] == "published"
    assert payload["publication_summary"]["state"] == "published"
    assert payload["publication_summary"]["target_dataset_id"] == "local-dataset-001"
    assert payload["publication_summary"]["target_design_id"] == "design_fluxonium-simulation-save"
    assert payload["publication_summary"]["target_design_name"] == "Fluxonium Simulation Save"
    assert payload["task"]["publication_summary"]["state"] == "published"
    assert payload["design"]["design_id"] == "design_fluxonium-simulation-save"
    assert len(payload["traces"]) == 5

    reloaded = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert reloaded["publication_summary"]["state"] == "published"
    assert reloaded["publication_summary"]["published_trace_ids"] == _published_trace_ids(
        task["task_id"],
        include_ptc=True,
    )

    reset_runtime_state()
    client.cookies.clear()
    persisted = client.get(f"/tasks/{task['task_id']}").json()["data"]
    assert persisted["publication_summary"]["state"] == "published"
    assert (
        persisted["publication_summary"]["target_design_id"]
        == "design_fluxonium-simulation-save"
    )
    durable_designs = client.get("/datasets/local-dataset-001/designs")
    assert durable_designs.status_code == 200
    assert any(
        row["design_id"] == "design_fluxonium-simulation-save"
        for row in durable_designs.json()["data"]["rows"]
    )
    durable_traces = client.get(
        "/datasets/local-dataset-001/designs/design_fluxonium-simulation-save/traces"
    )
    assert durable_traces.status_code == 200
    assert sorted(
        row["trace_id"] for row in durable_traces.json()["data"]["rows"]
    ) == sorted(
        _published_trace_ids(
            task["task_id"],
            include_ptc=True,
        )
    )


def test_pending_failed_and_wrong_kind_publish_requests_are_rejected_truthfully() -> None:
    pending_response = client.post(
        "/tasks/300/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Pending Publish"},
    )
    assert pending_response.status_code == 409
    assert pending_response.json()["error"]["code"] == "simulation_result_publish_not_ready"

    failed_task = _submit_local_simulation(ptc_enabled=False)
    with _bind_client_app_context(client):
        get_task_service().update_task_lifecycle(
            TaskLifecycleUpdate(
                task_id=failed_task["task_id"],
                status="failed",
                progress_percent_complete=100,
                progress_summary="Execution failed after result materialization.",
                progress_updated_at="2026-03-19T12:10:00+00:00",
                summary="Execution failed after result materialization.",
            )
        )

    failed_response = client.post(
        f"/tasks/{failed_task['task_id']}/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Failed Publish"},
    )
    assert failed_response.status_code == 409
    assert failed_response.json()["error"]["code"] == "simulation_result_publish_not_ready"

    _login()
    wrong_kind_response = client.post(
        "/tasks/303/simulation-results/publish",
        json={"dataset_id": "fluxonium-2025-031", "design_name": "Wrong Kind"},
    )
    assert wrong_kind_response.status_code == 409
    assert (
        wrong_kind_response.json()["error"]["code"]
        == "simulation_result_publish_task_invalid"
    )


def test_repeated_publish_is_idempotent_and_does_not_duplicate_dataset_records() -> None:
    task = _submit_local_simulation(ptc_enabled=False)
    first = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Stable Publish Target"},
    )
    assert first.status_code == 200
    assert first.json()["data"]["operation"] == "published"

    second = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Stable Publish Target"},
    )
    assert second.status_code == 200
    assert second.json()["data"]["operation"] == "already_published"
    assert second.json()["data"]["design"]["name"] == "Stable Publish Target"

    traces = client.get(
        "/datasets/local-dataset-001/designs/design_stable-publish-target/traces"
    )
    assert traces.status_code == 200
    rows = traces.json()["data"]["rows"]
    assert len(rows) == 3
    assert [row["trace_id"] for row in rows] == _published_trace_ids(
        task["task_id"],
        include_ptc=False,
    )

    reset_runtime_state()
    client.cookies.clear()

    third = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={"dataset_id": "local-dataset-001", "design_name": "Stable Publish Target"},
    )
    assert third.status_code == 200
    assert third.json()["data"]["operation"] == "already_published"

    post_reset_rows = client.get(
        "/datasets/local-dataset-001/designs/design_stable-publish-target/traces"
    ).json()["data"]["rows"]
    assert len(post_reset_rows) == 3
    assert [row["trace_id"] for row in post_reset_rows] == _published_trace_ids(
        task["task_id"],
        include_ptc=False,
    )


def test_published_trace_records_keep_source_task_provenance_and_are_browse_visible() -> None:
    task = _submit_local_simulation(ptc_enabled=True)
    publish = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={
            "dataset_id": "local-dataset-001",
            "design_name": "Published Explorer Design",
        },
    )
    assert publish.status_code == 200

    designs = client.get("/datasets/local-dataset-001/designs")
    assert designs.status_code == 200
    design_rows = designs.json()["data"]["rows"]
    published_design = next(
        row for row in design_rows if row["design_id"] == "design_published-explorer-design"
    )
    assert published_design["source_coverage"]["circuit_simulation"] == 5

    trace_rows = client.get(
        "/datasets/local-dataset-001/designs/design_published-explorer-design/traces"
    )
    assert trace_rows.status_code == 200
    rows = trace_rows.json()["data"]["rows"]
    assert {row["source_kind"] for row in rows} == {"circuit_simulation"}

    trace_detail = client.get(
        "/datasets/local-dataset-001/designs/design_published-explorer-design/"
        f"traces/trace_simulation_task_{task['task_id']}_y_matrix_ptc"
    )
    assert trace_detail.status_code == 200
    detail = trace_detail.json()["data"]
    assert detail["result_handles"][0]["provenance_task_id"] == task["task_id"]
    assert detail["result_handles"][0]["provenance"]["source_task_id"] == task["task_id"]
    assert detail["result_handles"][0]["provenance"]["source_dataset_id"] == "local-dataset-001"
    assert detail["payload_ref"]["store_key"].startswith(
        "datasets/local-dataset-001/designs/design_published-explorer-design/"
    )


def test_publish_can_target_an_explicitly_created_design_by_design_id() -> None:
    created_design = client.post(
        "/datasets/local-dataset-001/designs",
        json={"name": "Explicit Local Save Target"},
    )
    assert created_design.status_code == 201
    design = created_design.json()["data"]["design"]

    task = _submit_local_simulation(ptc_enabled=False)
    publish = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={
            "dataset_id": "local-dataset-001",
            "design_id": design["design_id"],
        },
    )

    assert publish.status_code == 200
    payload = publish.json()["data"]
    assert payload["operation"] == "published"
    assert payload["publication_summary"]["target_design_id"] == design["design_id"]
    assert payload["publication_summary"]["target_design_name"] == design["name"]
    assert payload["design"]["design_id"] == design["design_id"]
    assert payload["design"]["name"] == design["name"]
    assert payload["design"]["trace_count"] == 3
    assert payload["design"]["source_coverage"] == {
        "measurement": 0,
        "layout_simulation": 0,
        "circuit_simulation": 3,
    }

    browsed_designs = client.get("/datasets/local-dataset-001/designs")
    assert browsed_designs.status_code == 200
    published_design = next(
        row
        for row in browsed_designs.json()["data"]["rows"]
        if row["design_id"] == design["design_id"]
    )
    assert published_design["name"] == design["name"]
    assert published_design["trace_count"] == 3

    trace_rows = client.get(
        f"/datasets/local-dataset-001/designs/{design['design_id']}/traces"
    )
    assert trace_rows.status_code == 200
    assert [row["trace_id"] for row in trace_rows.json()["data"]["rows"]] == _published_trace_ids(
        task["task_id"],
        include_ptc=False,
    )


def test_publish_rejects_unsupported_alternate_target_dataset_semantics() -> None:
    task = _submit_local_simulation(ptc_enabled=False)

    publish = client.post(
        f"/tasks/{task['task_id']}/simulation-results/publish",
        json={
            "dataset_id": "fluxonium-2025-031",
            "design_name": "Wrong Dataset Target",
        },
    )

    assert publish.status_code == 409
    assert (
        publish.json()["error"]["code"]
        == "simulation_result_publish_target_unsupported"
    )


def test_trace_scoped_publish_creates_only_selected_trace_and_is_idempotent() -> None:
    created_design = client.post(
        "/datasets/local-dataset-001/designs",
        json={"name": "Current Trace Save Target"},
    )
    assert created_design.status_code == 201
    design = created_design.json()["data"]["design"]

    task = _submit_local_simulation(ptc_enabled=True)
    trace_key = _trace_key(family="y_matrix", source="ptc", z0_ohm=50)

    first = client.post(
        f"/tasks/{task['task_id']}/result-traces/publish",
        json={
            "design_id": design["design_id"],
            "trace_key": trace_key,
            "parameter_name": "Readout Admittance",
        },
    )

    assert first.status_code == 200
    payload = first.json()["data"]
    assert payload["operation"] == "published"
    assert payload["trace_key"] == trace_key
    assert payload["trace"]["trace_id"] == (
        f"trace_task_{task['task_id']}_readout-admittance_y_matrix_ptc_o1_i1_mode_0_mode_0_z0_50"
    )
    assert payload["publication_summary"]["published_trace_ids"] == [
        payload["trace"]["trace_id"]
    ]
    assert payload["design"]["trace_count"] == 1

    trace_rows = client.get(
        f"/datasets/local-dataset-001/designs/{design['design_id']}/traces"
    )
    assert trace_rows.status_code == 200
    rows = trace_rows.json()["data"]["rows"]
    assert [row["trace_id"] for row in rows] == [payload["trace"]["trace_id"]]
    assert rows[0]["parameter"] == "Readout Admittance"

    trace_detail = client.get(
        f"/datasets/local-dataset-001/designs/{design['design_id']}/traces/{payload['trace']['trace_id']}"
    )
    assert trace_detail.status_code == 200
    trace_payload = trace_detail.json()["data"]
    assert trace_payload["preview_payload"]["kind"] == "series"
    assert trace_payload["preview_payload"]["parameter"] == "Readout Admittance"
    assert trace_payload["preview_payload"]["default_parameter"] == "Y11"
    assert trace_payload["preview_payload"]["history_steps"] == ["PTC"]
    assert len(trace_payload["preview_payload"]["points"]) == trace_payload["axes"][0]["length"]

    second = client.post(
        f"/tasks/{task['task_id']}/result-traces/publish",
        json={
            "design_id": design["design_id"],
            "trace_key": trace_key,
            "parameter_name": "Readout Admittance",
        },
    )
    assert second.status_code == 200
    assert second.json()["data"]["operation"] == "already_published"

    repeated_rows = client.get(
        f"/datasets/local-dataset-001/designs/{design['design_id']}/traces"
    ).json()["data"]["rows"]
    assert [row["trace_id"] for row in repeated_rows] == [payload["trace"]["trace_id"]]


def test_trace_scoped_publish_supports_post_processing_tasks() -> None:
    upstream = _submit_local_simulation(ptc_enabled=True)
    post_processing = client.post(
        "/tasks",
        json={
            "kind": "post_processing",
            "dataset_id": "local-dataset-001",
            "summary": "Post-processing result save source.",
            "upstream_task_id": upstream["task_id"],
            "post_processing_setup": {
                "selections": [
                    {
                        "trace_family": "z_matrix",
                        "representation": "real",
                        "design_id": "design_local_flux_playground",
                        "trace_ids": ["trace_local_flux_preview"],
                    }
                ],
                "operations": [],
            },
        },
    )
    assert post_processing.status_code == 201
    queued = post_processing.json()["data"]["task"]
    assert queued["status"] == "queued"
    drain_lane_queue("simulation")
    task = client.get(f"/tasks/{queued['task_id']}").json()["data"]

    created_design = client.post(
        "/datasets/local-dataset-001/designs",
        json={"name": "Processed Trace Save Target"},
    )
    assert created_design.status_code == 201
    design = created_design.json()["data"]["design"]

    trace_key = _trace_key(family="z_matrix", source="raw", z0_ohm=50)
    publish = client.post(
        f"/tasks/{task['task_id']}/result-traces/publish",
        json={
            "design_id": design["design_id"],
            "trace_key": trace_key,
            "parameter_name": "Processed Z11",
        },
    )

    assert publish.status_code == 200
    payload = publish.json()["data"]
    assert payload["operation"] == "published"
    assert payload["trace"]["stage_kind"] == "postprocess"
    assert payload["trace"]["parameter"] == "Processed Z11"
    assert payload["trace"]["trace_id"] == (
        f"trace_task_{task['task_id']}_processed-z11_z_matrix_raw_o1_i1_mode_0_mode_0_z0_50"
    )
    trace_detail = client.get(
        f"/datasets/local-dataset-001/designs/{design['design_id']}/traces/{payload['trace']['trace_id']}"
    )
    assert trace_detail.status_code == 200
    assert trace_detail.json()["data"]["preview_payload"]["history_steps"] == ["Raw"]


def test_visible_trace_publish_materializes_each_visible_trace_as_a_saved_trace() -> None:
    definition_id = _create_sweepable_definition("VisibleTraceSaveDefinition")
    task = _submit_local_simulation(
        definition_id=definition_id,
        ptc_enabled=False,
        parameter_sweeps=[
            {
                "parameter": "Lj",
                "values": [850.0, 1000.0, 1150.0],
                "unit": "pH",
            }
        ],
    )

    explorer = client.get(
        f"/tasks/{task['task_id']}/simulation-results/view"
        "?family=s_matrix&source=raw&metric=magnitude_db&output_port=1&input_port=1"
        "&sweep_index=0&compare_axis_index=0"
    )
    assert explorer.status_code == 200
    trace_keys = [
        str(series["trace_key"])
        for series in explorer.json()["data"]["plot"]["series"]
        if isinstance(series.get("trace_key"), str)
    ]
    assert len(trace_keys) == 3

    created_design = client.post(
        "/datasets/local-dataset-001/designs",
        json={"name": "Visible Trace Save Target"},
    )
    assert created_design.status_code == 201
    design = created_design.json()["data"]["design"]

    publish = client.post(
        f"/tasks/{task['task_id']}/result-traces/publish",
        json={
            "design_id": design["design_id"],
            "trace_keys": trace_keys,
            "parameter_name": "Readout Admittance",
        },
    )

    assert publish.status_code == 200
    payload = publish.json()["data"]
    assert payload["operation"] == "published"
    assert payload["trace_key"] == trace_keys[0]
    assert payload["raw_data"]["trace_id"] is None
    assert len(payload["traces"]) == 3
    assert [trace["parameter"] for trace in payload["traces"]] == [
        "Readout Admittance · Lj = 850 pH",
        "Readout Admittance · Lj = 1000 pH",
        "Readout Admittance · Lj = 1150 pH",
    ]
    assert payload["publication_summary"]["published_trace_ids"] == [
        trace["trace_id"] for trace in payload["traces"]
    ]

    trace_rows = client.get(
        f"/datasets/local-dataset-001/designs/{design['design_id']}/traces"
    )
    assert trace_rows.status_code == 200
    rows = trace_rows.json()["data"]["rows"]
    assert {row["parameter"] for row in rows} == {
        "Readout Admittance · Lj = 850 pH",
        "Readout Admittance · Lj = 1000 pH",
        "Readout Admittance · Lj = 1150 pH",
    }
    assert {row["trace_id"] for row in rows} == {
        trace["trace_id"] for trace in payload["traces"]
    }

    repeated = client.post(
        f"/tasks/{task['task_id']}/result-traces/publish",
        json={
            "design_id": design["design_id"],
            "trace_keys": trace_keys,
            "parameter_name": "Readout Admittance",
        },
    )
    assert repeated.status_code == 200
    assert repeated.json()["data"]["operation"] == "already_published"
