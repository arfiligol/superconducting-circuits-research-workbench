"""Integration tests for the WS5 `/api/v1/*` contract."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from legacy.legacy_nicegui_archived.pages.simulation.submit_actions import build_simulation_submission
from legacy.legacy_nicegui_archived.services.auth_service import authenticate_user, ensure_bootstrap_admin, hash_password
from legacy.legacy_nicegui_archived.services.characterization_task_contract import build_characterization_submission
from legacy.legacy_nicegui_archived.services.execution_context import build_ui_use_case_context
from legacy.legacy_nicegui_archived.services.post_processing_task_contract import build_post_processing_submission
from legacy.legacy_nicegui_archived.services.simulation_batch_persistence import (
    create_pending_simulation_batch,
    persist_simulation_result_into_batch,
)
from legacy.legacy_nicegui_archived.services.simulation_runner import SimulationRunResult
from core.shared.persistence import database, get_unit_of_work
from core.shared.persistence.models import AnalysisRunRecord, DesignRecord, TraceBatchRecord
from core.simulation.domain.circuit import (
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
    parse_circuit_definition_source,
)


def _configure_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SC_DATABASE_PATH", str(tmp_path / "database.db"))
    monkeypatch.setenv("SC_RQ_REDIS_URL", f"fakeredis://api-{tmp_path.name}")
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    monkeypatch.setenv("SC_SESSION_SECRET", "ws5-test-secret")
    database.get_engine.cache_clear()
    for module_name in (
        "worker.characterization_worker",
        "worker.characterization_tasks",
        "worker.config",
        "worker.dispatch",
        "worker.simulation_worker",
        "worker.simulation_tasks",
    ):
        sys.modules.pop(module_name, None)
    importlib.import_module("worker.config").reset_fake_backend_cache()


@pytest.fixture()
def client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[TestClient, None, None]:
    _configure_test_environment(tmp_path, monkeypatch)
    app_main = importlib.import_module("legacy.legacy_nicegui_archived.main")
    ensure_bootstrap_admin()
    with TestClient(app_main.ui_app) as test_client:
        yield test_client
    database.get_engine.cache_clear()


def _login(
    client: TestClient,
    *,
    username: str = "admin",
    password: str = "admin",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return dict(response.json())


def _create_design(name: str) -> int:
    with get_unit_of_work() as uow:
        design = uow.datasets.add(
            DesignRecord(
                name=name,
                source_meta={},
                parameters={},
            )
        )
        uow.flush()
        assert design.id is not None
        uow.commit()
        return int(design.id)


def _create_local_user(*, username: str, password: str, role: str = "user") -> int:
    with get_unit_of_work() as uow:
        user = uow.users.create_user(
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        uow.commit()
        assert user.id is not None
        return int(user.id)


def _create_completed_trace_batch(
    *,
    design_id: int,
    bundle_type: str,
    role: str,
    source_kind: str,
    stage_kind: str,
    summary_payload: dict[str, object],
) -> int:
    with get_unit_of_work() as uow:
        batch = TraceBatchRecord(
            dataset_id=design_id,
            bundle_type=bundle_type,
            role=role,
            status="completed",
            source_meta={"source_kind": source_kind, "stage_kind": stage_kind},
            config_snapshot={"setup_kind": f"{source_kind}.{stage_kind}", "setup_version": "v1"},
            result_payload=dict(summary_payload),
        )
        uow.result_bundles.add(batch)
        uow.flush()
        assert batch.id is not None
        uow.commit()
        return int(batch.id)


def _create_completed_raw_simulation_batch(*, design_id: int) -> int:
    with get_unit_of_work() as uow:
        batch = create_pending_simulation_batch(
            uow=uow,
            design_id=design_id,
            source_meta={"origin": "api_test", "storage": "trace_store"},
            config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
            schema_source_hash="schema-post",
            simulation_setup_hash="setup-post",
            sweep_setup_hash=None,
        )
        assert batch.id is not None
        batch_id = int(batch.id)
        persist_simulation_result_into_batch(
            uow=uow,
            batch_id=batch_id,
            result=_sample_simulation_result(),
            source_meta={"origin": "api_test", "storage": "trace_store"},
            config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
            schema_source_hash="schema-post",
            simulation_setup_hash="setup-post",
        )
        uow.commit()
        return batch_id


def _create_completed_task(
    *,
    task_kind: str,
    design_id: int,
    requested_by: str,
    actor_id: int | None = None,
    trace_batch_id: int | None = None,
    analysis_run_id: int | None = None,
    result_summary_payload: dict[str, object] | None = None,
) -> int:
    with get_unit_of_work() as uow:
        task = uow.tasks.create_task(
            task_kind=task_kind,
            design_id=design_id,
            request_payload={"requested_via": "test"},
            requested_by=requested_by,
            actor_id=actor_id,
        )
        assert task.id is not None
        uow.tasks.mark_running(int(task.id))
        uow.tasks.mark_completed(
            int(task.id),
            trace_batch_id,
            dict(result_summary_payload or {}),
            analysis_run_id=analysis_run_id,
        )
        uow.commit()
        return int(task.id)


def _sample_simulation_circuit():
    return parse_circuit_definition_source(
        {
            "name": "WS6 Persisted Simulation",
            "parameters": [
                {"name": "Lj", "default": 1000.0, "unit": "pH"},
            ],
            "components": [
                {"name": "R50", "default": 50.0, "unit": "Ohm"},
                {"name": "Lj1", "value_ref": "Lj", "unit": "pH"},
                {"name": "C1", "default": 120.0, "unit": "fF"},
            ],
            "topology": [
                ("P1", "1", "0", 1),
                ("R1", "1", "0", "R50"),
                ("Lj1", "1", "2", "Lj1"),
                ("C1", "2", "0", "C1"),
            ],
        }
    )


def _sample_simulation_result() -> SimulationResult:
    return SimulationResult(
        frequencies_ghz=[4.0, 4.5, 5.0],
        s11_real=[0.1, 0.2, 0.25],
        s11_imag=[0.0, -0.05, -0.1],
        port_indices=[1],
        mode_indices=[(0,)],
        y_parameter_mode_real={"om=0|op=1|im=0|ip=1": [1.0, 1.1, 1.2]},
        y_parameter_mode_imag={"om=0|op=1|im=0|ip=1": [0.0, 0.0, 0.0]},
    )


def test_auth_endpoints_and_page_guard(client: TestClient) -> None:
    unauthenticated_api = client.get("/api/v1/auth/me")
    assert unauthenticated_api.status_code == 401
    assert unauthenticated_api.json() == {"detail": "Unauthenticated"}

    unauthenticated_page = client.get("/dashboard", follow_redirects=False)
    assert unauthenticated_page.status_code == 307
    assert unauthenticated_page.headers["location"] == "/login?next=%2Fdashboard"

    bad_password = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )
    assert bad_password.status_code == 401
    assert bad_password.json() == {"detail": "Invalid username or password"}

    login_payload = _login(client)
    assert login_payload["authenticated"] is True
    assert login_payload["user"]["username"] == "admin"
    assert login_payload["user"]["role"] == "admin"

    me_payload = client.get("/api/v1/auth/me")
    assert me_payload.status_code == 200
    assert me_payload.json()["user"]["username"] == "admin"

    authenticated_page = client.get("/dashboard")
    assert authenticated_page.status_code == 200

    logout_payload = client.post("/api/v1/auth/logout")
    assert logout_payload.status_code == 200
    assert logout_payload.json() == {"authenticated": False, "message": "Logged out"}

    me_after_logout = client.get("/api/v1/auth/me")
    assert me_after_logout.status_code == 401
    assert me_after_logout.json() == {"detail": "Unauthenticated"}


def test_admin_user_management_and_audit_api(client: TestClient) -> None:
    _login(client)

    created = client.post(
        "/api/v1/admin/users",
        json={
            "username": "alice",
            "password": "pw-1",
            "role": "user",
            "is_active": True,
        },
    )
    assert created.status_code == 201
    created_payload = created.json()
    alice_id = int(created_payload["id"])
    assert created_payload["username"] == "alice"
    assert created_payload["role"] == "user"

    listed = client.get("/api/v1/admin/users")
    assert listed.status_code == 200
    usernames = [row["username"] for row in listed.json()["users"]]
    assert usernames == ["admin", "alice"]

    updated = client.patch(
        f"/api/v1/admin/users/{alice_id}",
        json={"role": "user", "is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False

    reenabled = client.patch(
        f"/api/v1/admin/users/{alice_id}",
        json={"is_active": True},
    )
    assert reenabled.status_code == 200
    assert reenabled.json()["is_active"] is True

    reset = client.post(
        f"/api/v1/admin/users/{alice_id}/password-reset",
        json={"new_password": "pw-2"},
    )
    assert reset.status_code == 200
    assert reset.json()["username"] == "alice"

    audit_logs = client.get("/api/v1/admin/audit-logs")
    assert audit_logs.status_code == 200
    action_kinds = [row["action_kind"] for row in audit_logs.json()["logs"]]
    assert "admin.user_created" in action_kinds
    assert "admin.user_updated" in action_kinds
    assert "admin.user_password_reset" in action_kinds

    non_admin_client = client.__class__(client.app)
    try:
        login = non_admin_client.post(
            "/api/v1/auth/login",
            json={"username": "alice", "password": "pw-2"},
        )
        assert login.status_code == 200
        forbidden = non_admin_client.get("/api/v1/admin/users")
        assert forbidden.status_code == 403
        assert forbidden.json() == {"detail": "Admin role required"}
    finally:
        non_admin_client.close()


def test_admin_role_validation_returns_controlled_client_errors(client: TestClient) -> None:
    _login(client)

    invalid_create = client.post(
        "/api/v1/admin/users",
        json={
            "username": "bad-role",
            "password": "pw-1",
            "role": "guest",
            "is_active": True,
        },
    )
    assert invalid_create.status_code == 422
    assert invalid_create.json()["detail"][0]["loc"] == ["body", "role"]

    created = client.post(
        "/api/v1/admin/users",
        json={
            "username": "role-test",
            "password": "pw-1",
            "role": "admin",
            "is_active": True,
        },
    )
    assert created.status_code == 201
    user_id = int(created.json()["id"])
    assert created.json()["role"] == "admin"

    invalid_patch = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "guest"},
    )
    assert invalid_patch.status_code == 422
    assert invalid_patch.json()["detail"][0]["loc"] == ["body", "role"]

    valid_patch = client.patch(
        f"/api/v1/admin/users/{user_id}",
        json={"role": "user"},
    )
    assert valid_patch.status_code == 200
    assert valid_patch.json()["role"] == "user"


def test_task_creation_get_and_design_listing_use_real_task_records(
    client: TestClient,
) -> None:
    design_id = _create_design("WS5 Task API Design")
    user_id = _create_local_user(username="builder", password="builder-pass", role="user")

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "builder", "password": "builder-pass"},
    )
    assert login.status_code == 200

    simulation = client.post(
        "/api/v1/tasks/simulation",
        json={
            "design_id": design_id,
            "schema_source_hash": "schema-a",
            "simulation_setup_hash": "setup-a",
            "request_payload": {"sweep": "single"},
            "force_rerun": False,
        },
    )
    assert simulation.status_code == 202
    simulation_payload = simulation.json()
    assert simulation_payload["dedupe_hit"] is False
    assert simulation_payload["dispatched_lane"] == "simulation"
    assert simulation_payload["worker_task_name"] == "simulation_smoke_task"
    assert simulation_payload["task"]["design_id"] == design_id
    assert simulation_payload["task"]["actor_id"] == user_id
    simulation_task_id = int(simulation_payload["task"]["id"])

    simulation_dedupe = client.post(
        "/api/v1/tasks/simulation",
        json={
            "design_id": design_id,
            "schema_source_hash": "schema-a",
            "simulation_setup_hash": "setup-a",
            "request_payload": {"sweep": "single"},
            "force_rerun": False,
        },
    )
    assert simulation_dedupe.status_code == 202
    assert simulation_dedupe.json()["dedupe_hit"] is True
    assert int(simulation_dedupe.json()["task"]["id"]) == simulation_task_id

    post_processing = client.post(
        "/api/v1/tasks/post-processing",
        json={
            "design_id": design_id,
            "source_batch_id": 12,
            "input_source": "raw_y",
            "request_payload": {"mode_token": "0"},
            "force_rerun": False,
        },
    )
    assert post_processing.status_code == 202
    assert post_processing.json()["dispatched_lane"] == "simulation"
    assert post_processing.json()["worker_task_name"] == "post_processing_smoke_task"

    characterization = client.post(
        "/api/v1/tasks/characterization",
        json={
            "design_id": design_id,
            "analysis_id": "admittance_extraction",
            "trace_record_ids": [1, 2],
            "selected_batch_ids": [12],
            "trace_mode_group": "base",
            "config_state": {"fit_window": 5},
            "force_rerun": False,
        },
    )
    assert characterization.status_code == 202
    characterization_payload = characterization.json()
    assert characterization_payload["dispatched_lane"] == "characterization"
    assert characterization_payload["worker_task_name"] == "characterization_smoke_task"

    task_detail = client.get(f"/api/v1/tasks/{simulation_task_id}")
    assert task_detail.status_code == 200
    assert task_detail.json()["id"] == simulation_task_id
    assert task_detail.json()["status"] == "queued"

    design_tasks = client.get(f"/api/v1/designs/{design_id}/tasks")
    assert design_tasks.status_code == 200
    task_kinds = [task["task_kind"] for task in design_tasks.json()["tasks"]]
    assert task_kinds == ["characterization", "post_processing", "simulation"]


def test_post_processing_task_submission_dispatches_real_worker_path_and_persists_result(
    client: TestClient,
) -> None:
    design_id = _create_design("WS7 Persisted Post-Processing Design")
    _login(client, username="admin", password="admin")
    source_batch_id = _create_completed_raw_simulation_batch(design_id=design_id)

    submission = build_post_processing_submission(
        design_id=design_id,
        source_batch_id=source_batch_id,
        input_source="raw_y",
        mode_filter="base",
        mode_token="0",
        reference_impedance_ohm=50.0,
        step_sequence=[],
        termination_plan_payload=None,
        circuit_definition=_sample_simulation_circuit(),
        context=build_ui_use_case_context(
            actor_id=1,
            role="admin",
            metadata={"flow": "post_processing", "design_id": design_id},
        ),
        force_rerun=False,
    )

    post_processing = client.post(
        "/api/v1/tasks/post-processing",
        json=submission.api_request.model_dump(mode="json"),
    )
    assert post_processing.status_code == 202
    payload = post_processing.json()
    assert payload["dedupe_hit"] is False
    assert payload["dispatched_lane"] == "simulation"
    assert payload["worker_task_name"] == "post_processing_run_task"
    task_id = int(payload["task"]["id"])
    trace_batch_id = int(payload["task"]["trace_batch_id"])

    simulation_worker = importlib.import_module("worker.simulation_worker")
    processed = simulation_worker.consume(max_tasks=1, idle_timeout=0.2, poll_interval=0.01)
    assert processed == 1

    task_detail = client.get(f"/api/v1/tasks/{task_id}")
    assert task_detail.status_code == 200
    task_payload = task_detail.json()
    assert task_payload["status"] == "completed"
    assert task_payload["trace_batch_id"] == trace_batch_id
    assert task_payload["result_summary_payload"]["source_batch_id"] == source_batch_id

    latest_post_processing = client.get(f"/api/v1/designs/{design_id}/post-processing/latest")
    assert latest_post_processing.status_code == 200
    latest_payload = latest_post_processing.json()
    assert latest_payload["batch_id"] == trace_batch_id
    assert latest_payload["parent_batch_id"] == source_batch_id
    summary_payload = latest_payload["summary_payload"]["trace_batch_record"]["summary_payload"]
    assert summary_payload["run_kind"] == "single_result"
    assert summary_payload["input_source"] == "raw_y"


def test_characterization_task_submission_dispatches_real_worker_path_and_persists_result(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    design_id = _create_design("WS8 Persisted Characterization Design")
    _login(client, username="admin", password="admin")

    submission = build_characterization_submission(
        design_id=design_id,
        analysis_id="admittance_extraction",
        analysis_label="Admittance Extraction",
        run_id="char-api-1",
        trace_record_ids=[1, 2],
        selected_batch_ids=[12],
        selected_scope_token="all_dataset_records",
        trace_mode_group="base",
        config_state={"fit_window": 5},
        summary_payload={"selected_trace_count": 2},
        context=build_ui_use_case_context(
            actor_id=1,
            role="admin",
            metadata={"flow": "characterization", "design_id": design_id},
        ),
        force_rerun=False,
    )

    characterization = client.post(
        "/api/v1/tasks/characterization",
        json=submission.api_request.model_dump(mode="json"),
    )
    assert characterization.status_code == 202
    payload = characterization.json()
    assert payload["dedupe_hit"] is False
    assert payload["dispatched_lane"] == "characterization"
    assert payload["worker_task_name"] == "characterization_run_task"
    task_id = int(payload["task"]["id"])
    analysis_run_id = int(payload["task"]["analysis_run_id"])

    monkeypatch.setattr(
        "core.analysis.application.services.resonance_extract_service.ResonanceExtractService.extract_admittance",
        lambda self, dataset_id, **kwargs: None,
    )

    characterization_worker = importlib.import_module("worker.characterization_worker")
    processed = characterization_worker.consume(max_tasks=1, idle_timeout=0.2, poll_interval=0.01)
    assert processed == 1

    task_detail = client.get(f"/api/v1/tasks/{task_id}")
    assert task_detail.status_code == 200
    task_payload = task_detail.json()
    assert task_payload["status"] == "completed"
    assert task_payload["analysis_run_id"] == analysis_run_id
    assert task_payload["result_summary_payload"]["worker_task_name"] == (
        "characterization_run_task"
    )

    latest_characterization = client.get(f"/api/v1/designs/{design_id}/characterization/latest")
    assert latest_characterization.status_code == 200
    latest_payload = latest_characterization.json()
    assert latest_payload["analysis_run_id"] == analysis_run_id
    assert latest_payload["task_id"] == task_id
    assert latest_payload["analysis_id"] == "admittance_extraction"
    assert latest_payload["input_batch_ids"] == [12]


def test_simulation_task_submission_dispatches_real_worker_path_and_persists_result(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    design_id = _create_design("WS6 Persisted Simulation Design")
    _login(client, username="admin", password="admin")

    submission = build_simulation_submission(
        design_id=design_id,
        design_name="WS6 Persisted Simulation Design",
        circuit=_sample_simulation_circuit(),
        freq_range=FrequencyRange(start_ghz=4.0, stop_ghz=5.0, points=3),
        config=SimulationConfig(),
        config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
        source_meta={"origin": "api_test", "storage": "design_trace_store"},
        schema_source_hash="schema-ws6",
        simulation_setup_hash="setup-ws6",
        sweep_setup_payload=None,
        sweep_setup_hash=None,
        context=build_ui_use_case_context(
            actor_id=1,
            role="admin",
            metadata={"flow": "simulation", "design_id": design_id},
        ),
        force_rerun=False,
    )

    simulation = client.post(
        "/api/v1/tasks/simulation",
        json=submission.api_request.model_dump(mode="json"),
    )
    assert simulation.status_code == 202
    payload = simulation.json()
    assert payload["dedupe_hit"] is False
    assert payload["dispatched_lane"] == "simulation"
    assert payload["worker_task_name"] == "simulation_run_task"
    assert payload["task"]["status"] == "queued"
    assert payload["task"]["trace_batch_id"] is not None
    task_id = int(payload["task"]["id"])
    trace_batch_id = int(payload["task"]["trace_batch_id"])

    simulation_worker = importlib.import_module("worker.simulation_worker")
    simulation_execution = importlib.import_module("worker.simulation_execution")

    def _fake_execute_simulation_run(request, *, progress_callback=None, execute=None):
        return SimulationRunResult(
            simulation_result=_sample_simulation_result(),
            context=request.context,
        )

    monkeypatch.setattr(
        simulation_execution,
        "execute_simulation_run",
        _fake_execute_simulation_run,
    )

    processed = simulation_worker.consume(max_tasks=1, idle_timeout=0.2, poll_interval=0.01)
    assert processed == 1

    task_detail = client.get(f"/api/v1/tasks/{task_id}")
    assert task_detail.status_code == 200
    assert task_detail.json()["status"] == "completed"
    assert task_detail.json()["trace_batch_id"] == trace_batch_id
    assert task_detail.json()["result_summary_payload"]["worker_task_name"] == "simulation_run_task"

    latest_simulation = client.get(f"/api/v1/designs/{design_id}/simulation/latest")
    assert latest_simulation.status_code == 200
    latest_payload = latest_simulation.json()
    assert latest_payload["batch_id"] == trace_batch_id
    assert latest_payload["task_id"] == task_id
    assert latest_payload["stage_kind"] == "raw"
    assert (
        latest_payload["summary_payload"]["trace_batch_record"]["summary_payload"][
            "frequency_points"
        ]
        == 3
    )

    with get_unit_of_work() as uow:
        snapshot = uow.result_bundles.get_trace_batch_snapshot(trace_batch_id)
        assert isinstance(snapshot, dict)
        assert snapshot["status"] == "completed"
        assert (
            snapshot["summary_payload"]["trace_batch_record"]["summary_payload"]["frequency_points"]
            == 3
        )
        assert (
            snapshot["summary_payload"]["trace_batch_record"]["summary_payload"]["trace_count"] >= 1
        )


def test_latest_result_lookup_endpoints_use_persisted_artifacts_only(
    client: TestClient,
) -> None:
    design_id = _create_design("WS5 Latest Lookup Design")
    admin_payload = _login(client)
    admin_id = int(admin_payload["user"]["id"])

    simulation_batch_id = _create_completed_trace_batch(
        design_id=design_id,
        bundle_type="circuit_simulation",
        role="manual_export",
        source_kind="circuit_simulation",
        stage_kind="raw",
        summary_payload={"trace_count": 12},
    )
    post_processing_batch_id = _create_completed_trace_batch(
        design_id=design_id,
        bundle_type="simulation_postprocess",
        role="manual_export",
        source_kind="circuit_simulation",
        stage_kind="postprocess",
        summary_payload={"flow": "ptc_y"},
    )

    with get_unit_of_work() as uow:
        analysis_run = uow.result_bundles.analysis_runs.add(
            AnalysisRunRecord(
                design_id=design_id,
                analysis_id="admittance_extraction",
                analysis_label="Admittance Extraction",
                run_id="run-1",
                status="completed",
                input_trace_ids=[1, 2],
                input_batch_ids=[simulation_batch_id],
                input_scope="selected_trace_records",
                trace_mode_group="base",
                config_payload={"fit_window": 5},
                summary_payload={"peak_count": 1},
            )
        )
        uow.commit()
        assert analysis_run.id is not None
        analysis_run_id = int(analysis_run.id)

    simulation_task_id = _create_completed_task(
        task_kind="simulation",
        design_id=design_id,
        requested_by="api",
        actor_id=admin_id,
        trace_batch_id=simulation_batch_id,
        result_summary_payload={"flow": "simulation"},
    )
    post_processing_task_id = _create_completed_task(
        task_kind="post_processing",
        design_id=design_id,
        requested_by="api",
        actor_id=admin_id,
        trace_batch_id=post_processing_batch_id,
        result_summary_payload={"flow": "post_processing"},
    )
    characterization_task_id = _create_completed_task(
        task_kind="characterization",
        design_id=design_id,
        requested_by="api",
        actor_id=admin_id,
        analysis_run_id=analysis_run_id,
        result_summary_payload={"flow": "characterization"},
    )

    latest_simulation = client.get(f"/api/v1/designs/{design_id}/simulation/latest")
    assert latest_simulation.status_code == 200
    assert latest_simulation.json()["batch_id"] == simulation_batch_id
    assert latest_simulation.json()["task_id"] == simulation_task_id
    assert latest_simulation.json()["stage_kind"] == "raw"

    latest_post_processing = client.get(f"/api/v1/designs/{design_id}/post-processing/latest")
    assert latest_post_processing.status_code == 200
    assert latest_post_processing.json()["batch_id"] == post_processing_batch_id
    assert latest_post_processing.json()["task_id"] == post_processing_task_id
    assert latest_post_processing.json()["stage_kind"] == "postprocess"

    latest_characterization = client.get(f"/api/v1/designs/{design_id}/characterization/latest")
    assert latest_characterization.status_code == 200
    assert latest_characterization.json()["analysis_run_id"] == analysis_run_id
    assert latest_characterization.json()["task_id"] == characterization_task_id
    assert latest_characterization.json()["analysis_id"] == "admittance_extraction"


def test_bootstrap_admin_recovery_restores_active_login_capable_admin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_test_environment(tmp_path, monkeypatch)
    ensure_bootstrap_admin()

    with get_unit_of_work() as uow:
        admin = uow.users.get_by_username("admin")
        assert admin is not None
        assert admin.id is not None
        uow.users.set_active(int(admin.id), False)
        uow.commit()

    assert authenticate_user("admin", "admin") is None

    recovered = ensure_bootstrap_admin()
    assert recovered.username == "admin"
    assert recovered.role == "admin"
    assert recovered.is_active is True

    with get_unit_of_work() as uow:
        persisted_admin = uow.users.get_by_username("admin")
        assert persisted_admin is not None
        assert persisted_admin.role == "admin"
        assert persisted_admin.is_active is True

    authenticated = authenticate_user("admin", "admin")
    assert authenticated is not None
    assert authenticated.username == "admin"
    assert authenticated.role == "admin"
    assert authenticated.is_active is True
