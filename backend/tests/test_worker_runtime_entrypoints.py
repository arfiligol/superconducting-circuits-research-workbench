from __future__ import annotations

from rq import SimpleWorker, Worker
from src.app.infrastructure.worker_runtime import entrypoints


def test_configure_worker_process_environment_sets_macos_fork_safety_override(
    monkeypatch,
) -> None:
    monkeypatch.delenv("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", raising=False)
    monkeypatch.setattr(entrypoints.sys, "platform", "darwin")

    entrypoints._configure_worker_process_environment()

    assert entrypoints.os.environ["OBJC_DISABLE_INITIALIZE_FORK_SAFETY"] == "YES"


def test_worker_class_uses_simple_worker_on_macos(monkeypatch) -> None:
    monkeypatch.setattr(entrypoints.sys, "platform", "darwin")

    assert entrypoints._worker_class() is SimpleWorker


def test_worker_class_uses_standard_worker_off_macos(monkeypatch) -> None:
    monkeypatch.setattr(entrypoints.sys, "platform", "linux")

    assert entrypoints._worker_class() is Worker
