"""WS10 runtime startup and restart/recovery drills."""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from legacy.legacy_nicegui_archived.services.auth_service import ensure_bootstrap_admin
from legacy.legacy_nicegui_archived.services.execution_context import build_ui_use_case_context
from legacy.legacy_nicegui_archived.services.simulation_batch_persistence import create_pending_simulation_batch
from legacy.legacy_nicegui_archived.services.simulation_runner import SimulationRunResult
from legacy.legacy_nicegui_archived.services.simulation_submission import build_simulation_submission
from core.shared.persistence import database, get_unit_of_work
from core.shared.persistence.models import CircuitRecord, DesignRecord
from core.shared.persistence.startup_reconcile import run_startup_reconcile
from core.simulation.domain.circuit import (
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
    parse_circuit_definition_source,
)

_ROOT_DIR = Path(__file__).resolve().parents[2]


def _sample_circuit_source() -> dict[str, object]:
    return {
        "name": "WS10 Runtime Circuit",
        "parameters": [{"name": "Lj", "default": 1000.0, "unit": "pH"}],
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


def _configure_test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SC_DATABASE_PATH", str(tmp_path / "database.db"))
    monkeypatch.setenv("SC_RQ_REDIS_URL", f"fakeredis://runtime-{tmp_path.name}")
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    monkeypatch.setenv("SC_SESSION_SECRET", "ws10-runtime-secret")
    monkeypatch.setenv("SC_WORKER_STALE_TIMEOUT_SECONDS", "1")
    database.get_engine.cache_clear()
    for module_name in (
        "legacy.legacy_nicegui_archived.main",
        "legacy.legacy_nicegui_archived.services.task_submission",
        "worker.characterization_worker",
        "worker.characterization_tasks",
        "worker.config",
        "worker.dispatch",
        "worker.simulation_worker",
        "worker.simulation_tasks",
        "worker.simulation_execution",
    ):
        sys.modules.pop(module_name, None)
    importlib.import_module("worker.config").reset_fake_backend_cache()


def _configure_subprocess_environment(tmp_path: Path) -> dict[str, str]:
    runtime_env = dict(os.environ)
    runtime_env.update(
        {
            "SC_DATABASE_PATH": str(tmp_path / "database.db"),
            "SC_RQ_REDIS_URL": f"fakeredis://runtime-{tmp_path.name}",
            "SC_TRACE_STORE_ROOT": str(tmp_path / "trace_store"),
            "SC_SESSION_SECRET": "ws10-runtime-secret",
            "SC_WORKER_STALE_TIMEOUT_SECONDS": "1",
            "SC_APP_HOST": "127.0.0.1",
        }
    )
    return runtime_env


def _login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert response.status_code == 200


def _create_design_and_circuit(name: str) -> tuple[int, int]:
    with get_unit_of_work() as uow:
        design = uow.datasets.add(DesignRecord(name=name, source_meta={}, parameters={}))
        circuit = uow.circuits.add(
            CircuitRecord(
                name=f"{name}-circuit",
                definition_json=json.dumps(_sample_circuit_source()),
            )
        )
        uow.flush()
        assert design.id is not None
        assert circuit.id is not None
        uow.commit()
        return (int(design.id), int(circuit.id))


def _create_stale_simulation_task(*, design_id: int, actor_id: int) -> tuple[int, int]:
    with get_unit_of_work() as uow:
        batch = create_pending_simulation_batch(
            uow=uow,
            design_id=design_id,
            source_meta={"origin": "ws10_restart_test", "storage": "trace_store"},
            config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
            schema_source_hash="schema-ws10",
            simulation_setup_hash="setup-ws10",
            sweep_setup_hash=None,
        )
        uow.flush()
        assert batch.id is not None
        task = uow.tasks.create_task(
            task_kind="simulation",
            design_id=design_id,
            request_payload={"requested_via": "ws10_restart_test"},
            requested_by="restart_test",
            actor_id=actor_id,
            trace_batch_id=int(batch.id),
        )
        assert task.id is not None
        uow.tasks.mark_running(int(task.id))
        persisted_task = uow.tasks.get_task(int(task.id))
        assert persisted_task is not None
        persisted_task.heartbeat_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            seconds=600
        )
        uow.commit()
        return (int(task.id), int(batch.id))


def _build_simulation_request_payload(
    *,
    design_id: int,
    design_name: str,
    circuit_id: int,
    actor_id: int,
) -> dict[str, Any]:
    circuit_record = parse_circuit_definition_source(_sample_circuit_source())
    freq_range = FrequencyRange(start_ghz=4.0, stop_ghz=5.0, points=3)
    config = SimulationConfig()
    config_snapshot = {
        "setup_kind": "circuit_simulation.raw",
        "setup_version": "1.0",
        "freq_range": freq_range.model_dump(mode="json"),
        "config": config.model_dump(mode="json"),
    }
    submission = build_simulation_submission(
        design_id=design_id,
        design_name=design_name,
        circuit=circuit_record,
        freq_range=freq_range,
        config=config,
        config_snapshot=config_snapshot,
        source_meta={"origin": "ws10_restart_test", "storage": "trace_store"},
        schema_source_hash=f"schema:{circuit_id}",
        simulation_setup_hash="setup:ws10",
        sweep_setup_payload=None,
        sweep_setup_hash=None,
        context=build_ui_use_case_context(
            actor_id=actor_id,
            role="admin",
            metadata={"source": "ws10_restart_test"},
        ),
        force_rerun=False,
    )
    return submission.api_request.model_dump(mode="json", exclude={"force_rerun"})


def _simulation_worker_thread(delay_seconds: float = 0.05) -> threading.Thread:
    def _run() -> None:
        time.sleep(delay_seconds)
        importlib.import_module("worker.simulation_worker").consume(
            max_tasks=1,
            idle_timeout=2.0,
            poll_interval=0.01,
        )

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread


def _free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


def _wait_for_log_text(
    log_path: Path,
    expected_text: str,
    *,
    timeout_seconds: float = 60.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            content = log_path.read_text(encoding="utf-8")
            if expected_text in content:
                return
        except Exception:
            time.sleep(0.2)
    raise AssertionError(f"Timed out waiting for log text '{expected_text}' in {log_path}")


def _wait_for_http_ready(
    *,
    port: int,
    timeout_seconds: float = 60.0,
) -> None:
    import http.client

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            connection.request("GET", "/login")
            response = connection.getresponse()
            response.read()
            connection.close()
            if response.status == 200:
                return
        except Exception:
            time.sleep(0.2)
    raise AssertionError(f"Timed out waiting for sc-legacy-nicegui on port {port}")


@pytest.fixture()
def runtime_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, Any], None, None]:
    _configure_test_environment(tmp_path, monkeypatch)
    app_main = importlib.import_module("legacy.legacy_nicegui_archived.main")
    admin = ensure_bootstrap_admin()
    with TestClient(app_main.ui_app) as client:
        _login(client)
        yield client, admin
    database.get_engine.cache_clear()


def test_dual_lane_startup_commands_boot(
    tmp_path: Path,
) -> None:
    env = _configure_subprocess_environment(tmp_path)
    app_port = _free_port()
    env["SC_APP_PORT"] = str(app_port)
    env["NICEGUI_SCREEN_TEST_PORT"] = str(app_port)
    start = subprocess.run(
        ["./scripts/dev_start.sh"],
        cwd=_ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert start.returncode == 0, start.stderr
    try:
        _wait_for_http_ready(port=app_port)
        _wait_for_log_text(
            _ROOT_DIR / "tmp/dev_logs/worker-simulation.log",
            "simulation lane startup reconcile",
        )
        _wait_for_log_text(
            _ROOT_DIR / "tmp/dev_logs/worker-characterization.log",
            "characterization lane startup reconcile",
        )
    finally:
        stop = subprocess.run(
            ["./scripts/dev_stop.sh"],
            cwd=_ROOT_DIR,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert stop.returncode == 0, stop.stderr


def test_worker_restart_reconcile_leaves_app_readable(
    runtime_client: tuple[TestClient, Any],
) -> None:
    client, admin = runtime_client
    design_id, _circuit_id = _create_design_and_circuit("WS10 Worker Restart")
    task_id, batch_id = _create_stale_simulation_task(
        design_id=design_id,
        actor_id=int(admin.id or 0),
    )

    before = client.get(f"/api/v1/tasks/{task_id}")
    assert before.status_code == 200
    assert before.json()["status"] == "running"
    assert client.get("/dashboard").status_code == 200

    summary = run_startup_reconcile(source="worker:simulation", stale_after_seconds=1)

    assert summary.stale_task_ids == [task_id]
    assert batch_id in summary.failed_batch_ids
    after = client.get(f"/api/v1/tasks/{task_id}")
    assert after.status_code == 200
    assert after.json()["status"] == "failed"
    assert after.json()["error_payload"]["error_code"] == "stale_task_timeout"
    assert client.get("/dashboard").status_code == 200


def test_worker_survives_while_app_restarts_and_state_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_test_environment(tmp_path, monkeypatch)
    app_main = importlib.import_module("legacy.legacy_nicegui_archived.main")
    admin = ensure_bootstrap_admin()
    design_id, circuit_id = _create_design_and_circuit("WS10 App Restart")
    simulation_execution = importlib.import_module("worker.simulation_execution")

    def _fake_execute(
        request: Any,
        *,
        progress_callback: Any = None,
        execute: Any = None,
    ) -> SimulationRunResult:
        return SimulationRunResult(
            simulation_result=_sample_simulation_result(),
            context=request.context,
        )

    monkeypatch.setattr(simulation_execution, "execute_simulation_run", _fake_execute)
    task_id = 0
    worker = _simulation_worker_thread(delay_seconds=0.1)
    with TestClient(app_main.ui_app) as client:
        _login(client)
        response = client.post(
            "/api/v1/tasks/simulation",
            json=_build_simulation_request_payload(
                design_id=design_id,
                design_name="WS10 App Restart",
                circuit_id=circuit_id,
                actor_id=int(admin.id or 0),
            ),
        )
        assert response.status_code in {201, 202}
        task_id = int(response.json()["task"]["id"])
        queued = client.get(f"/api/v1/tasks/{task_id}")
        assert queued.status_code == 200
        assert queued.json()["status"] in {"queued", "running"}

    worker.join(timeout=5)

    with TestClient(app_main.ui_app) as restarted_client:
        _login(restarted_client)
        task_response = restarted_client.get(f"/api/v1/tasks/{task_id}")
        assert task_response.status_code == 200
        assert task_response.json()["status"] == "completed"
        latest_response = restarted_client.get(f"/api/v1/designs/{design_id}/simulation/latest")
        assert latest_response.status_code == 200
        assert int(latest_response.json()["task_id"]) == task_id


def test_app_and_worker_restart_together_keep_persisted_failure_visible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_test_environment(tmp_path, monkeypatch)
    app_main = importlib.import_module("legacy.legacy_nicegui_archived.main")
    admin = ensure_bootstrap_admin()
    design_id, _circuit_id = _create_design_and_circuit("WS10 Joint Restart")
    task_id, batch_id = _create_stale_simulation_task(
        design_id=design_id,
        actor_id=int(admin.id or 0),
    )

    app_summary = run_startup_reconcile(source="app", stale_after_seconds=1)
    worker_summary = run_startup_reconcile(source="worker:simulation", stale_after_seconds=1)

    assert task_id in app_summary.stale_task_ids
    assert batch_id in app_summary.failed_batch_ids
    assert worker_summary.stale_task_ids == []

    with TestClient(app_main.ui_app) as client:
        _login(client)
        task_response = client.get(f"/api/v1/tasks/{task_id}")
        assert task_response.status_code == 200
        assert task_response.json()["status"] == "failed"
        design_tasks = client.get(f"/api/v1/designs/{design_id}/tasks")
        assert design_tasks.status_code == 200
        statuses = [row["status"] for row in design_tasks.json()["tasks"]]
        assert "failed" in statuses
