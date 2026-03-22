from __future__ import annotations

from dataclasses import replace

from redis.exceptions import ConnectionError
from rq import Queue, Worker
from src.app.infrastructure.runtime import get_worker_runtime_settings
from src.app.infrastructure.worker_runtime.diagnostics import probe_worker_runtime
from src.app.infrastructure.worker_runtime.redis_connection import build_queue_connection_factory


def test_probe_worker_runtime_reports_reachable_redis_without_workers() -> None:
    settings = replace(get_worker_runtime_settings(), redis_url="fakeredis://runtime-diagnostics")
    diagnostic = probe_worker_runtime(
        settings,
        build_queue_connection_factory(settings.redis_url),
    )

    assert diagnostic.queue_backend.reachable is True
    assert diagnostic.worker_count == 0
    assert diagnostic.missing_lanes == ("simulation", "characterization")
    assert diagnostic.unexpected_workers == ()


def test_probe_worker_runtime_groups_registered_workers_by_lane() -> None:
    settings = replace(get_worker_runtime_settings(), redis_url="fakeredis://runtime-workers")
    connection_factory = build_queue_connection_factory(settings.redis_url)
    connection = connection_factory()
    simulation_worker = Worker(
        [Queue(settings.simulation_queue_name, connection=connection)],
        connection=connection,
        name="sc-worker-simulation:4101",
    )
    characterization_worker = Worker(
        [Queue(settings.characterization_queue_name, connection=connection)],
        connection=connection,
        name="sc-worker-characterization:4102",
    )

    simulation_worker.register_birth()
    characterization_worker.register_birth()
    try:
        diagnostic = probe_worker_runtime(settings, connection_factory)
    finally:
        characterization_worker.register_death()
        simulation_worker.register_death()

    assert diagnostic.queue_backend.reachable is True
    assert diagnostic.worker_count == 2
    assert diagnostic.missing_lanes == ()
    assert diagnostic.lanes[0].worker_names == ("sc-worker-simulation:4101",)
    assert diagnostic.lanes[1].worker_names == ("sc-worker-characterization:4102",)


def test_probe_worker_runtime_reports_queue_connection_failure() -> None:
    settings = replace(get_worker_runtime_settings(), redis_url="redis://127.0.0.1:6399/0")

    def failing_connection_factory():
        raise ConnectionError("redis unavailable")

    diagnostic = probe_worker_runtime(settings, failing_connection_factory)

    assert diagnostic.queue_backend.reachable is False
    assert diagnostic.queue_backend.error_code == "queue_connection_failed"
    assert diagnostic.worker_count == 0
    assert diagnostic.missing_lanes == ("simulation", "characterization")
