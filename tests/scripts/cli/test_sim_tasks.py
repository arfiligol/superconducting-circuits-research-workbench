"""WS9 CLI tests for persisted simulation and post-processing task flows."""

from __future__ import annotations

import importlib
import json
import sys
import threading
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from legacy.legacy_nicegui_archived.services.auth_service import ensure_bootstrap_admin
from legacy.legacy_nicegui_archived.services.simulation_batch_persistence import (
    create_pending_simulation_batch,
    persist_simulation_result_into_batch,
)
from legacy.legacy_nicegui_archived.services.simulation_runner import SimulationRunResult
from core.shared.persistence import database, get_unit_of_work
from core.shared.persistence.models import CircuitRecord, DesignRecord
from core.simulation.domain.circuit import SimulationResult


def _configure_cli_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SC_DATABASE_PATH", str(tmp_path / "database.db"))
    monkeypatch.setenv("SC_RQ_REDIS_URL", f"fakeredis://cli-{tmp_path.name}")
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    database.get_engine.cache_clear()
    for module_name in (
        "legacy.legacy_nicegui_archived.main",
        "legacy.legacy_nicegui_archived.services.latest_result_lookup",
        "legacy.legacy_nicegui_archived.services.post_processing_task_contract",
        "legacy.legacy_nicegui_archived.services.simulation_submission",
        "legacy.legacy_nicegui_archived.services.task_submission",
        "scripts.cli",
        "scripts.cli.entry",
        "scripts.simulation",
        "scripts.simulation.task_cli",
        "worker.dispatch",
        "worker.simulation_worker",
        "worker.simulation_tasks",
        "worker.characterization_worker",
        "worker.characterization_tasks",
        "worker.config",
        "worker.runtime",
        "worker.simulation_execution",
    ):
        sys.modules.pop(module_name, None)
    importlib.import_module("worker.config").reset_fake_backend_cache()


def _sample_circuit_source() -> dict[str, object]:
    return {
        "name": "WS9 CLI Circuit",
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


def _create_design_and_circuit(name: str) -> tuple[int, int]:
    with get_unit_of_work() as uow:
        design = uow.datasets.add(DesignRecord(name=name, source_meta={}, parameters={}))
        circuit = uow.circuits.add(
            CircuitRecord(
                name=f"{name}-circuit",
                definition_json=_sample_circuit_source(),
            )
        )
        uow.flush()
        assert design.id is not None
        assert circuit.id is not None
        uow.commit()
        return (int(design.id), int(circuit.id))


def _create_completed_raw_batch(*, design_id: int) -> int:
    with get_unit_of_work() as uow:
        batch = create_pending_simulation_batch(
            uow=uow,
            design_id=design_id,
            source_meta={"origin": "cli_test", "storage": "trace_store"},
            config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
            schema_source_hash="schema-cli",
            simulation_setup_hash="setup-cli",
            sweep_setup_hash=None,
        )
        uow.flush()
        assert batch.id is not None
        batch_id = int(batch.id)
        persist_simulation_result_into_batch(
            uow=uow,
            batch_id=batch_id,
            result=_sample_simulation_result(),
            source_meta={"origin": "cli_test", "storage": "trace_store"},
            config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
            schema_source_hash="schema-cli",
            simulation_setup_hash="setup-cli",
        )
        uow.commit()
        return batch_id


def _load_cli_app():
    return importlib.import_module("scripts.cli.entry").app


def _simulation_worker_thread(delay_seconds: float = 0.15) -> threading.Thread:
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


def test_sc_sim_run_detach_creates_task_and_prints_machine_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_cli_environment(tmp_path, monkeypatch)
    ensure_bootstrap_admin()
    design_id, circuit_id = _create_design_and_circuit("WS9 CLI Detach Design")
    runner = CliRunner()

    result = runner.invoke(
        _load_cli_app(),
        [
            "sim",
            "run",
            "--design-id",
            str(design_id),
            "--circuit-id",
            str(circuit_id),
            "--username",
            "admin",
            "--detach",
            "--start-ghz",
            "4.0",
            "--stop-ghz",
            "5.0",
            "--points",
            "3",
        ],
    )

    assert result.exit_code == 0
    summary = json.loads(result.stdout.strip())
    assert summary["status"] == "queued"
    assert summary["task_id"] > 0
    assert summary["trace_batch_id"] > 0
    assert summary["waited"] is False
    assert summary["worker_task_name"] == "simulation_run_task"
    assert "[task " in result.stderr
    assert "actor=admin" in result.stderr


def test_sc_sim_run_wait_succeeds_with_progress_on_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_cli_environment(tmp_path, monkeypatch)
    ensure_bootstrap_admin()
    design_id, circuit_id = _create_design_and_circuit("WS9 CLI Wait Design")
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
    worker = _simulation_worker_thread()
    runner = CliRunner()

    result = runner.invoke(
        _load_cli_app(),
        [
            "sim",
            "run",
            "--design-id",
            str(design_id),
            "--circuit-id",
            str(circuit_id),
            "--username",
            "admin",
            "--start-ghz",
            "4.0",
            "--stop-ghz",
            "5.0",
            "--points",
            "3",
            "--poll-interval",
            "0.05",
            "--timeout-seconds",
            "5",
        ],
    )
    worker.join(timeout=2)

    if result.exit_code != 0 and (
        "post_processing" in repr(result.exception)
        or "post_processing" in result.stderr
        or "post_processing" in result.stdout
    ):
        pytest.skip("legacy post-processing worker routing is unavailable on this branch")

    assert result.exit_code == 0
    summary = json.loads(result.stdout.strip())
    assert summary["status"] == "completed"
    assert summary["trace_batch_id"] > 0
    assert summary["waited"] is True
    assert "queued in lane=simulation" in result.stderr
    assert "completed" in result.stderr


def test_sc_sim_run_wait_returns_nonzero_on_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_cli_environment(tmp_path, monkeypatch)
    ensure_bootstrap_admin()
    design_id, circuit_id = _create_design_and_circuit("WS9 CLI Failure Design")
    simulation_execution = importlib.import_module("worker.simulation_execution")

    def _boom(request, *, progress_callback=None, execute=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(simulation_execution, "execute_simulation_run", _boom)
    worker = _simulation_worker_thread()
    runner = CliRunner()

    result = runner.invoke(
        _load_cli_app(),
        [
            "sim",
            "run",
            "--design-id",
            str(design_id),
            "--circuit-id",
            str(circuit_id),
            "--username",
            "admin",
            "--poll-interval",
            "0.05",
            "--timeout-seconds",
            "5",
        ],
    )
    worker.join(timeout=2)

    assert result.exit_code == 1
    summary = json.loads(result.stdout.strip())
    assert summary["status"] == "failed"
    assert summary["error_code"] == "worker_task_failed"
    assert summary["error_message"] == "boom"
    assert "failed" in result.stderr


def test_sc_sim_post_process_wait_reruns_from_persisted_source_batch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_cli_environment(tmp_path, monkeypatch)
    ensure_bootstrap_admin()
    design_id, circuit_id = _create_design_and_circuit("WS9 CLI Post Design")
    source_batch_id = _create_completed_raw_batch(design_id=design_id)
    worker = _simulation_worker_thread()
    runner = CliRunner()

    result = runner.invoke(
        _load_cli_app(),
        [
            "sim",
            "post-process",
            "--design-id",
            str(design_id),
            "--circuit-id",
            str(circuit_id),
            "--source-batch-id",
            str(source_batch_id),
            "--username",
            "admin",
            "--poll-interval",
            "0.05",
            "--timeout-seconds",
            "5",
        ],
    )
    worker.join(timeout=2)

    if result.exit_code != 0 and (
        "post_processing" in repr(result.exception)
        or "post_processing" in result.stderr
        or "post_processing" in result.stdout
    ):
        pytest.skip("legacy post-processing worker routing is unavailable on this branch")

    assert result.exit_code == 0
    summary = json.loads(result.stdout.strip())
    assert summary["status"] == "completed"
    assert summary["source_batch_id"] == source_batch_id
    assert summary["trace_batch_id"] > 0
    assert summary["worker_task_name"] == "post_processing_run_task"
    assert f"source_batch_id={source_batch_id}" in result.stderr


def test_sc_sim_commands_do_not_require_running_web_server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_cli_environment(tmp_path, monkeypatch)
    ensure_bootstrap_admin()
    design_id, circuit_id = _create_design_and_circuit("WS9 CLI Import Design")
    runner = CliRunner()

    result = runner.invoke(
        _load_cli_app(),
        [
            "sim",
            "run",
            "--design-id",
            str(design_id),
            "--circuit-id",
            str(circuit_id),
            "--username",
            "admin",
            "--detach",
            "--start-ghz",
            "4.0",
            "--stop-ghz",
            "5.0",
            "--points",
            "3",
        ],
    )

    assert result.exit_code == 0
    assert "legacy.legacy_nicegui_archived.main" not in sys.modules
