import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from src.app.infrastructure.durable_runtime_seed import seed_durable_runtime_state
from src.app.infrastructure.runtime import get_task_audit_repository, reset_runtime_state


@pytest.fixture(autouse=True)
def reset_runtime_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Generator[None, None, None]:
    monkeypatch.setenv("SC_DATABASE_PATH", str(tmp_path / "runtime-metadata.db"))
    monkeypatch.setenv("SC_AUDIT_DATABASE_PATH", str(tmp_path / "runtime-audit.db"))
    relative_data_root = Path("data") / "test-runtime" / tmp_path.name
    monkeypatch.setenv("SC_TRACE_STORE_ROOT", str(relative_data_root / "trace_store"))
    monkeypatch.setenv("SC_STAGING_ROOT", str(relative_data_root / "staging"))
    monkeypatch.setenv("SC_ARTIFACTS_ROOT", str(relative_data_root / "artifacts"))
    reset_runtime_state()
    seed_durable_runtime_state()
    get_task_audit_repository().clear()
    yield
    reset_runtime_state()
    get_task_audit_repository().clear()
    reset_runtime_state()
    repo_root = Path(__file__).resolve().parents[3]
    shutil.rmtree(repo_root / relative_data_root, ignore_errors=True)
