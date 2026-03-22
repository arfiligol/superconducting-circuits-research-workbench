from collections.abc import Generator
from pathlib import Path

import pytest
from src.app.infrastructure.runtime import get_task_audit_repository, reset_runtime_state


@pytest.fixture(autouse=True)
def reset_runtime_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[None, None, None]:
    monkeypatch.setenv("SC_DATABASE_PATH", str(tmp_path / "runtime-metadata.db"))
    monkeypatch.setenv("SC_AUDIT_DATABASE_PATH", str(tmp_path / "runtime-audit.db"))
    monkeypatch.setenv("SC_RQ_REDIS_URL", f"fakeredis://{tmp_path.name}")
    reset_runtime_state()
    get_task_audit_repository().clear()
    yield
    reset_runtime_state()
    get_task_audit_repository().clear()
    reset_runtime_state()
