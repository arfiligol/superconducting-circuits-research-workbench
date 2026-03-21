"""RQ worker-lane integration tests for probe, failure, and crash semantics."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from core.shared.persistence import database
from core.shared.persistence.models import DesignRecord
from core.shared.persistence.reconcile import reconcile_stale_tasks_and_batches
from core.shared.persistence.unit_of_work import get_unit_of_work
from core.simulation.domain.circuit import (
    FrequencyRange,
    SimulationConfig,
    SimulationResult,
    parse_circuit_definition_source,
)
from legacy.legacy_nicegui_archived.pages.simulation.submit_actions import (
    build_simulation_submission,
)
from legacy.legacy_nicegui_archived.services.characterization_task_contract import (
    build_characterization_submission,
)
from legacy.legacy_nicegui_archived.services.execution_context import (
    ActorContext,
    build_ui_use_case_context,
)
from legacy.legacy_nicegui_archived.services.post_processing_task_contract import (
    build_post_processing_submission,
)
from legacy.legacy_nicegui_archived.services.simulation_batch_persistence import (
    create_pending_simulation_batch,
    persist_simulation_result_into_batch,
)
from legacy.legacy_nicegui_archived.services.simulation_runner import SimulationRunResult
from legacy.legacy_nicegui_archived.services.task_submission import create_api_task

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _utcnow() -> datetime:
    """Return one naive UTC timestamp without using deprecated utcnow()."""
    return datetime.now(UTC).replace(tzinfo=None)


def _configure_worker_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SC_DATABASE_PATH", str(tmp_path / "database.db"))
    monkeypatch.setenv("SC_RQ_REDIS_URL", f"fakeredis://worker-{tmp_path.name}")
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(tmp_path / "trace_store"))
    database.get_engine.cache_clear()
    for module_name in ("worker.config",):
        sys.modules.pop(module_name, None)
    importlib.import_module("worker.config").reset_fake_backend_cache()


def _reload_worker_modules() -> tuple[object, object, object, object]:
    for module_name in [
        "worker.characterization_tasks",
        "worker.characterization_worker",
        "worker.simulation_tasks",
        "worker.simulation_worker",
        "worker.runtime",
        "worker.config",
    ]:
        sys.modules.pop(module_name, None)

    simulation_worker = importlib.import_module("worker.simulation_worker")
    simulation_tasks = importlib.import_module("worker.simulation_tasks")
    characterization_worker = importlib.import_module("worker.characterization_worker")
    characterization_tasks = importlib.import_module("worker.characterization_tasks")
    return (
        simulation_worker,
        simulation_tasks,
        characterization_worker,
        characterization_tasks,
    )


def _create_task(task_kind: str) -> int:
    with get_unit_of_work() as uow:
        design = uow.datasets.add(
            DesignRecord(
                name=f"{task_kind}-design",
                source_meta={},
                parameters={},
            )
        )
        uow.flush()
        assert design.id is not None
        task = uow.tasks.create_task(
            task_kind,
            design.id,
            {"requested_via": "test"},
            "test",
        )
        uow.commit()
        assert task.id is not None
        return task.id


def _enqueue_test_job(queue: object, task_func: object, *args: object) -> None:
    queue.enqueue(
        task_func,
        *args,
        job_timeout=-1,
        failure_ttl=86400,
        result_ttl=3600,
    )


def _sample_simulation_circuit():
    return parse_circuit_definition_source(
        {
            "name": "WS6 Worker Simulation",
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


def _create_completed_raw_batch(*, design_id: int) -> int:
    with get_unit_of_work() as uow:
        batch = create_pending_simulation_batch(
            uow=uow,
            design_id=design_id,
            source_meta={"origin": "worker_test", "storage": "trace_store"},
            config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
            schema_source_hash="schema-post",
            simulation_setup_hash="setup-post",
            sweep_setup_hash=None,
        )
        uow.flush()
        assert batch.id is not None
        batch_id = int(batch.id)
        persist_simulation_result_into_batch(
            uow=uow,
            batch_id=batch_id,
            result=_sample_simulation_result(),
            source_meta={"origin": "worker_test", "storage": "trace_store"},
            config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
            schema_source_hash="schema-post",
            simulation_setup_hash="setup-post",
        )
        uow.commit()
        return batch_id


def test_lane_workers_use_rq_queue_defaults(tmp_path: Path, monkeypatch) -> None:
    _configure_worker_env(tmp_path, monkeypatch)
    simulation_worker, _simulation_tasks, characterization_worker, _characterization_tasks = (
        _reload_worker_modules()
    )

    redis_url = f"fakeredis://worker-{tmp_path.name}"
    assert redis_url == simulation_worker.REDIS_URL
    assert redis_url == characterization_worker.REDIS_URL
    assert simulation_worker.QUEUE_NAME == "simulation"
    assert characterization_worker.QUEUE_NAME == "characterization"


def test_simulation_lane_probe_task_round_trips_taskrecord(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_worker_env(tmp_path, monkeypatch)
    simulation_worker, simulation_tasks, _characterization_worker, _characterization_tasks = (
        _reload_worker_modules()
    )
    task_id = _create_task("simulation_probe")

    _enqueue_test_job(simulation_worker.queue, simulation_tasks.simulation_probe_task, task_id)
    processed = simulation_worker.consume(max_tasks=1, idle_timeout=0.2, poll_interval=0.01)

    assert processed == 1
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.result_summary_payload["lane"] == "simulation"
        assert task.result_summary_payload["probe_result"] == "ok"


def test_characterization_lane_probe_task_round_trips_taskrecord(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_worker_env(tmp_path, monkeypatch)
    _simulation_worker, _simulation_tasks, characterization_worker, characterization_tasks = (
        _reload_worker_modules()
    )
    task_id = _create_task("characterization_probe")

    _enqueue_test_job(
        characterization_worker.queue,
        characterization_tasks.characterization_probe_task,
        task_id,
    )
    processed = characterization_worker.consume(max_tasks=1, idle_timeout=0.2, poll_interval=0.01)

    assert processed == 1
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.result_summary_payload["lane"] == "characterization"
        assert task.result_summary_payload["probe_result"] == "ok"


def test_real_characterization_worker_task_persists_analysis_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_worker_env(tmp_path, monkeypatch)
    _simulation_worker, _simulation_tasks, characterization_worker, _characterization_tasks = (
        _reload_worker_modules()
    )

    with get_unit_of_work() as uow:
        design = uow.datasets.add(
            DesignRecord(
                name="WS8 Worker Persisted Characterization",
                source_meta={},
                parameters={},
            )
        )
        uow.flush()
        assert design.id is not None
        design_id = int(design.id)
        uow.commit()

    submission = build_characterization_submission(
        design_id=design_id,
        analysis_id="admittance_extraction",
        analysis_label="Admittance Extraction",
        run_id="char-worker-1",
        trace_record_ids=[11, 12],
        selected_batch_ids=[7],
        selected_scope_token="all_dataset_records",
        trace_mode_group="base",
        config_state={"fit_window": 5},
        summary_payload={"selected_trace_count": 2},
        context=build_ui_use_case_context(
            actor_id=17,
            role="user",
            requested_by="test",
            metadata={"flow": "characterization"},
        ),
        force_rerun=False,
    )

    submitted = create_api_task(
        task_kind="characterization",
        design_id=design_id,
        request_payload=submission.api_request.model_dump(mode="json", exclude={"force_rerun"}),
        actor=ActorContext(actor_id=17, requested_by="test", role="user", auth_source="test"),
        force_rerun=False,
    )

    assert submitted.task.id is not None
    assert submitted.task.analysis_run_id is not None
    assert submitted.dispatch.worker_task_name == "characterization_run_task"
    task_id = int(submitted.task.id)
    analysis_run_id = int(submitted.task.analysis_run_id)

    monkeypatch.setattr(
        "core.analysis.application.services.resonance_extract_service.ResonanceExtractService.extract_admittance",
        lambda self, dataset_id, **kwargs: None,
    )

    processed = characterization_worker.consume(max_tasks=1, idle_timeout=0.2, poll_interval=0.01)

    assert processed == 1
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.analysis_run_id == analysis_run_id
        assert task.result_summary_payload["worker_task_name"] == "characterization_run_task"
        assert task.result_summary_payload["result_refs"] == {"analysis_run_id": analysis_run_id}

        analysis_run = uow.result_bundles.analysis_runs.get(analysis_run_id)
        assert analysis_run is not None
        assert analysis_run.status == "completed"
        assert analysis_run.analysis_id == "admittance_extraction"
        assert analysis_run.input_batch_ids == [7]


def test_simulation_lane_failure_task_marks_failed(tmp_path: Path, monkeypatch) -> None:
    _configure_worker_env(tmp_path, monkeypatch)
    simulation_worker, simulation_tasks, _characterization_worker, _characterization_tasks = (
        _reload_worker_modules()
    )
    task_id = _create_task("simulation_failure")

    _enqueue_test_job(
        simulation_worker.queue,
        simulation_tasks.simulation_failure_task,
        task_id,
        "boom",
    )
    processed = simulation_worker.consume(max_tasks=1, idle_timeout=0.2, poll_interval=0.01)

    assert processed == 1
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        assert task is not None
        assert task.status == "failed"
        assert task.error_payload["error_code"] == "worker_task_failed"
        assert task.error_payload["details"]["message"] == "boom"
        assert task.error_payload["details"]["lane"] == "simulation"


def test_real_simulation_worker_task_persists_trace_batch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_worker_env(tmp_path, monkeypatch)
    simulation_worker, _simulation_tasks, _characterization_worker, _characterization_tasks = (
        _reload_worker_modules()
    )

    with get_unit_of_work() as uow:
        design = uow.datasets.add(
            DesignRecord(
                name="WS6 Worker Persisted Simulation",
                source_meta={},
                parameters={},
            )
        )
        uow.flush()
        assert design.id is not None
        design_id = int(design.id)
        uow.commit()

    submission = build_simulation_submission(
        design_id=design_id,
        design_name="WS6 Worker Persisted Simulation",
        circuit=_sample_simulation_circuit(),
        freq_range=FrequencyRange(start_ghz=4.0, stop_ghz=5.0, points=3),
        config=SimulationConfig(),
        config_snapshot={"setup_kind": "circuit_simulation.raw", "setup_version": "1.0"},
        source_meta={"origin": "worker_test", "storage": "design_trace_store"},
        schema_source_hash="schema-ws6",
        simulation_setup_hash="setup-ws6",
        sweep_setup_payload=None,
        sweep_setup_hash=None,
        context=build_ui_use_case_context(
            actor_id=7,
            role="user",
            requested_by="test",
            metadata={"flow": "simulation"},
        ),
        force_rerun=False,
    )

    submitted = create_api_task(
        task_kind="simulation",
        design_id=design_id,
        request_payload=submission.api_request.model_dump(mode="json", exclude={"force_rerun"}),
        actor=ActorContext(actor_id=7, requested_by="test", role="user", auth_source="test"),
        force_rerun=False,
    )

    assert submitted.task.id is not None
    assert submitted.task.trace_batch_id is not None
    assert submitted.dispatch.worker_task_name == "simulation_run_task"
    task_id = int(submitted.task.id)
    trace_batch_id = int(submitted.task.trace_batch_id)

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
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.trace_batch_id == trace_batch_id
        assert task.result_summary_payload["worker_task_name"] == "simulation_run_task"
        assert task.result_summary_payload["result_refs"] == {"trace_batch_id": trace_batch_id}

        snapshot = uow.result_bundles.get_trace_batch_snapshot(trace_batch_id)
        assert snapshot is not None
        assert snapshot["status"] == "completed"
        assert snapshot["stage_kind"] == "raw"
        assert (
            snapshot["summary_payload"]["trace_batch_record"]["summary_payload"]["frequency_points"]
            == 3
        )
        assert (
            snapshot["summary_payload"]["trace_batch_record"]["summary_payload"]["trace_count"] >= 1
        )


def test_real_post_processing_worker_task_persists_trace_batch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _configure_worker_env(tmp_path, monkeypatch)
    simulation_worker, _simulation_tasks, _characterization_worker, _characterization_tasks = (
        _reload_worker_modules()
    )

    with get_unit_of_work() as uow:
        design = uow.datasets.add(
            DesignRecord(
                name="WS7 Worker Persisted Post-Processing",
                source_meta={},
                parameters={},
            )
        )
        uow.flush()
        assert design.id is not None
        design_id = int(design.id)
        uow.commit()

    source_batch_id = _create_completed_raw_batch(design_id=design_id)
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
            actor_id=9,
            role="user",
            requested_by="test",
            metadata={"flow": "post_processing"},
        ),
        force_rerun=False,
    )

    submitted = create_api_task(
        task_kind="post_processing",
        design_id=design_id,
        request_payload=submission.api_request.model_dump(mode="json", exclude={"force_rerun"}),
        actor=ActorContext(actor_id=9, requested_by="test", role="user", auth_source="test"),
        force_rerun=False,
    )

    assert submitted.task.id is not None
    assert submitted.task.trace_batch_id is not None
    assert submitted.dispatch.worker_task_name == "post_processing_run_task"
    task_id = int(submitted.task.id)
    trace_batch_id = int(submitted.task.trace_batch_id)

    processed = simulation_worker.consume(max_tasks=1, idle_timeout=0.2, poll_interval=0.01)

    assert processed == 1
    with get_unit_of_work() as uow:
        task = uow.tasks.get_task(task_id)
        assert task is not None
        assert task.status == "completed"
        assert task.trace_batch_id == trace_batch_id
        assert task.result_summary_payload["source_batch_id"] == source_batch_id
        assert task.result_summary_payload["result_refs"] == {"trace_batch_id": trace_batch_id}

        snapshot = uow.result_bundles.get_trace_batch_snapshot(trace_batch_id)
        assert snapshot is not None
        assert snapshot["status"] == "completed"
        assert snapshot["stage_kind"] == "postprocess"
        assert snapshot["parent_batch_id"] == source_batch_id
        assert snapshot["provenance_payload"]["source_simulation_bundle_id"] == source_batch_id


def test_crashed_worker_task_is_detected_as_stale(tmp_path: Path, monkeypatch) -> None:
    _configure_worker_env(tmp_path, monkeypatch)
    simulation_worker, simulation_tasks, _characterization_worker, _characterization_tasks = (
        _reload_worker_modules()
    )
    task_id = _create_task("simulation_crash")

    redis_url = os.getenv("SC_RQ_REDIS_URL")
    if not redis_url or redis_url.startswith("fakeredis://"):
        pytest.skip("Crash-isolation enqueue requires a real Redis backend for cross-process RQ.")

    _enqueue_test_job(simulation_worker.queue, simulation_tasks.simulation_crash_task, task_id, 86)
    env = {
        **os.environ,
        "SC_DATABASE_PATH": str(database.resolve_database_path()),
        "SC_RQ_REDIS_URL": redis_url,
    }
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "worker.simulation_worker",
            "--max-tasks",
            "1",
            "--idle-timeout",
            "0.2",
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 86

    with get_unit_of_work() as uow:
        running_task = uow.tasks.get_task(task_id)
        assert running_task is not None
        assert running_task.status == "running"
        running_task.heartbeat_at = _utcnow() - timedelta(minutes=10)
        uow.commit()

    with get_unit_of_work() as uow:
        summary = reconcile_stale_tasks_and_batches(
            uow,
            stale_before=_utcnow() - timedelta(minutes=5),
        )

    assert summary.stale_task_ids == [task_id]
    with get_unit_of_work() as uow:
        failed_task = uow.tasks.get_task(task_id)
        assert failed_task is not None
        assert failed_task.status == "failed"
        assert failed_task.error_payload["error_code"] == "stale_task_timeout"


def test_app_import_does_not_import_worker_or_julia_adapter_modules() -> None:
    env = {**os.environ, "PYTHON_JULIACALL_TRACE": "1"}
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import legacy.legacy_nicegui_archived.main; "
                "print('APP_IMPORT_OK'); "
                "print('worker.simulation_worker' in sys.modules); "
                "print('worker.characterization_worker' in sys.modules); "
                "print('core.simulation.application.run_simulation' in sys.modules); "
                "print('core.simulation.infrastructure.julia_adapter' in sys.modules)"
            ),
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    output_lines = result.stdout.strip().splitlines()
    assert output_lines == ["APP_IMPORT_OK", "False", "False", "True", "False"]
    combined_output = f"{result.stdout}\n{result.stderr}".lower()
    assert "juliacall" not in combined_output


def test_shared_use_case_modules_import_without_page_modules() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import legacy.legacy_nicegui_archived.services.simulation_runner; "
                "import legacy.legacy_nicegui_archived.services.post_processing_runner; "
                "import legacy.legacy_nicegui_archived.services.characterization_runner; "
                "print('USE_CASE_IMPORT_OK'); "
                "print("
                "any("
                "name.startswith('legacy.legacy_nicegui_archived.pages.') "
                "for name in sys.modules"
                ")"
                ")"
            ),
        ],
        cwd=_REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.strip().splitlines() == ["USE_CASE_IMPORT_OK", "False"]
