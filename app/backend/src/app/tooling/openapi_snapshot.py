from __future__ import annotations

import difflib
import inspect
import json
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from src.app.main import create_application


@dataclass(frozen=True)
class OpenApiDriftReport:
    snapshot_path: Path
    is_current: bool
    generated_render: str
    checked_in_render: str | None
    diff_preview: tuple[str, ...]


def build_openapi_snapshot() -> dict[str, Any]:
    snapshot = create_application().openapi()
    snapshot.setdefault("components", {}).setdefault("schemas", {}).update(
        _build_api_schema_components()
    )
    return snapshot


def render_openapi_snapshot(snapshot: dict[str, Any] | None = None) -> str:
    resolved_snapshot = snapshot or build_openapi_snapshot()
    return json.dumps(resolved_snapshot, indent=2, ensure_ascii=False)


def export_openapi_snapshot(snapshot_path: Path) -> Path:
    snapshot_path.write_text(render_openapi_snapshot(), encoding="utf-8")
    return snapshot_path


def _build_api_schema_components() -> dict[str, Any]:
    schema_models: list[type[BaseModel]] = []
    seen: set[type[BaseModel]] = set()
    for module_name in (
        "src.app.api.schemas.circuit_definitions",
        "src.app.api.schemas.datasets",
        "src.app.api.schemas.errors",
        "src.app.api.schemas.session",
        "src.app.api.schemas.storage",
        "src.app.api.schemas.tasks",
    ):
        module = import_module(module_name)
        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate, BaseModel) or candidate is BaseModel:
                continue
            if not candidate.__module__.startswith("src.app.api.schemas."):
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            schema_models.append(candidate)

    _, definitions = models_json_schema(
        [(schema_model, "validation") for schema_model in schema_models],
        ref_template="#/components/schemas/{model}",
    )
    raw_schemas = definitions.get("$defs", {})
    return {
        str(name): schema
        for name, schema in raw_schemas.items()
        if isinstance(schema, dict)
    }


def check_openapi_snapshot_drift(snapshot_path: Path) -> OpenApiDriftReport:
    generated_snapshot = build_openapi_snapshot()
    generated_render = render_openapi_snapshot(generated_snapshot)

    if not snapshot_path.exists():
        return OpenApiDriftReport(
            snapshot_path=snapshot_path,
            is_current=False,
            generated_render=generated_render,
            checked_in_render=None,
            diff_preview=("checked-in snapshot is missing",),
        )

    checked_in_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    checked_in_render = render_openapi_snapshot(checked_in_snapshot)
    is_current = checked_in_snapshot == generated_snapshot
    return OpenApiDriftReport(
        snapshot_path=snapshot_path,
        is_current=is_current,
        generated_render=generated_render,
        checked_in_render=checked_in_render,
        diff_preview=_build_diff_preview(
            checked_in_render=checked_in_render,
            generated_render=generated_render,
        ),
    )


def _build_diff_preview(
    *,
    checked_in_render: str,
    generated_render: str,
) -> tuple[str, ...]:
    diff_lines = tuple(
        difflib.unified_diff(
            checked_in_render.splitlines(),
            generated_render.splitlines(),
            fromfile="openapi.json",
            tofile="generated-openapi",
            lineterm="",
        )
    )
    return diff_lines[:40]
