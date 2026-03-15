"""Filesystem helpers for the standalone CLI local runtime store."""

from __future__ import annotations

from datetime import UTC, datetime
from json import dumps, loads
from os import getenv
from pathlib import Path
from typing import Any

from pydantic import BaseModel

RUNTIME_ROOT_ENV = "SC_CLI_RUNTIME_ROOT"


def runtime_store_root() -> Path:
    env_root = getenv(RUNTIME_ROOT_ENV)
    if env_root:
        return Path(env_root).expanduser().resolve()
    return (Path.cwd() / ".sc-runtime").resolve()


def session_state_path() -> Path:
    return runtime_store_root() / "session.json"


def definition_catalog_path() -> Path:
    return runtime_store_root() / "definitions" / "catalog.json"


def dataset_catalog_path() -> Path:
    return runtime_store_root() / "datasets" / "catalog.json"


def task_registry_path() -> Path:
    return runtime_store_root() / "tasks" / "registry.json"


def task_events_path(task_id: int) -> Path:
    return runtime_store_root() / "tasks" / "events" / f"{task_id}.json"


def task_results_path(task_id: int) -> Path:
    return runtime_store_root() / "tasks" / "results" / f"{task_id}.json"


def bundle_receipts_path() -> Path:
    return runtime_store_root() / "bundles" / "receipts.json"


def read_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    return loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_model(path: Path, model: BaseModel) -> None:
    write_json(path, model.model_dump(mode="json"))


def record_bundle_receipt(
    *,
    bundle_family: str,
    operation: str,
    receipt: BaseModel,
) -> None:
    current = read_json(bundle_receipts_path())
    receipts: list[dict[str, object]]
    if isinstance(current, list):
        receipts = [entry for entry in current if isinstance(entry, dict)]
    else:
        receipts = []
    receipts.append(
        {
            "bundle_family": bundle_family,
            "operation": operation,
            "recorded_at": datetime.now(UTC).isoformat(),
            "receipt": receipt.model_dump(mode="json"),
        }
    )
    write_json(bundle_receipts_path(), receipts)
