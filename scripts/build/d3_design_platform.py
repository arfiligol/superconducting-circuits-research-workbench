#!/usr/bin/env python3
"""Resolve and run one declared D3 design Procedure from a requirement request."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKBENCH_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = WORKBENCH_ROOT.parent
DEFAULT_CATALOG = (
    WORKBENCH_ROOT
    / "notebooks"
    / "pluto"
    / "D3 Intrinsic Purcell Filter Design"
    / "d3_procedure_catalog.v1.json"
)
REQUEST_SCHEMA = "d3-design-procedure-request.v1"
CATALOG_SCHEMA = "d3-design-procedure-catalog.v1"
PLACEHOLDER = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object.")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve(value: object, role: str) -> Path:
    text = str(value).strip()
    if not text:
        raise ValueError(f"paths.{role} must be nonempty.")
    path = Path(text)
    return (path if path.is_absolute() else WORKSPACE_ROOT / path).resolve()


def _load_catalog(path: Path) -> dict[str, Any]:
    catalog = _read_json(path)
    if set(catalog) != {"schema_version", "status", "procedures"}:
        raise ValueError("D3 Procedure catalog keys do not match its v1 contract.")
    if catalog["schema_version"] != CATALOG_SCHEMA:
        raise ValueError(f"Expected {CATALOG_SCHEMA}.")
    procedures = catalog["procedures"]
    if not isinstance(procedures, list):
        raise ValueError("D3 Procedure catalog procedures must be one list.")
    ids = [str(item["id"]) for item in procedures]
    if len(ids) != len(set(ids)):
        raise ValueError("D3 Procedure ids must be unique.")
    return catalog


def _load_request(path: Path) -> dict[str, Any]:
    request = _read_json(path)
    if set(request) != {"schema_version", "topology", "goal", "paths"}:
        raise ValueError("D3 Procedure request keys do not match its v1 contract.")
    if request["schema_version"] != REQUEST_SCHEMA:
        raise ValueError(f"Expected {REQUEST_SCHEMA}.")
    if not isinstance(request["paths"], dict):
        raise ValueError("D3 Procedure request paths must be one object.")
    return request


def _select(catalog: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    selector = {
        "topology": str(request["topology"]),
        "goal": str(request["goal"]),
    }
    matches = [
        procedure
        for procedure in catalog["procedures"]
        if procedure.get("selector") == selector
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Requirement selector {selector!r} resolved to {len(matches)} Procedures."
        )
    return matches[0]


def _resolve_paths(
    procedure: dict[str, Any], request: dict[str, Any], *, create_outputs: bool
) -> dict[str, Path]:
    required = procedure["required_paths"]
    supplied = request["paths"]
    if set(supplied) != set(required):
        missing = sorted(set(required) - set(supplied))
        extra = sorted(set(supplied) - set(required))
        raise ValueError(f"Procedure path mismatch; missing={missing}, extra={extra}.")
    resolved = {role: _resolve(supplied[role], role) for role in required}
    for role, kind in required.items():
        path = resolved[role]
        if kind == "file":
            if not path.is_file():
                raise ValueError(f"Required file paths.{role} does not exist: {path}")
        elif kind == "directory":
            if not path.is_dir():
                raise ValueError(f"Required directory paths.{role} does not exist: {path}")
        elif kind == "output_file":
            if create_outputs:
                path.parent.mkdir(parents=True, exist_ok=True)
        elif kind == "output_directory":
            if create_outputs:
                path.mkdir(parents=True, exist_ok=True)
        else:
            raise ValueError(f"Unsupported required path kind {kind!r}.")
    return resolved


def _validate_open_side_input(path: Path) -> None:
    payload = _read_json(path)
    if payload.get("schema_version") != "d3-readout-open-side-maxwell.v2":
        raise ValueError(
            "open_side_contract_required: canonical design requires "
            "d3-readout-open-side-maxwell.v2."
        )
    if (
        payload.get("readout_self_capacitance_ownership")
        != "localized_open_side_interface_owns_reduced_readout_shunt"
    ):
        raise ValueError("The local Maxwell block must own the reduced readout shunt.")
    region = payload.get("region_ownership")
    if not isinstance(region, dict):
        raise ValueError("Open-side v2 requires region_ownership.")
    required = {
        "modeling_mode": "full_region_replacement",
        "distributed_readout_length_reference": (
            "shorted_end_to_open_side_local_cut_plane"
        ),
        "distributed_line_excludes_local_region": True,
        "electric_energy_owner": "this_maxwell_matrix",
    }
    for key, expected in required.items():
        if region.get(key) != expected:
            raise ValueError(f"Open-side region_ownership.{key} must equal {expected!r}.")


def _validate_initializer(path: Path) -> None:
    payload = _read_json(path)
    assumptions = payload.get("assumptions")
    if not isinstance(assumptions, dict):
        raise ValueError("D3 initializer requires assumptions.")
    if (
        assumptions.get("readout_length_reference")
        != "initializer_for_shorted_end_to_open_side_local_cut_plane"
    ):
        raise ValueError("D3 initializer lengths must reference the open-side cut plane.")
    if assumptions.get("open_side_local_loading_included_in_formula") is not False:
        raise ValueError(
            "The analytical initializer must leave open-side loading to the physical model."
        )


def _preflight(
    procedure: dict[str, Any], paths: dict[str, Path]
) -> None:
    for check in procedure["preflight"]:
        if check == "open_side_maxwell_v2":
            _validate_open_side_input(paths["qubit_open_side"])
        elif check == "cut_plane_length_initializer":
            _validate_initializer(paths["initializer"])
        else:
            raise ValueError(f"Unknown D3 Procedure preflight {check!r}.")


def _expand(value: str, paths: dict[str, Path]) -> str:
    def replacement(match: re.Match[str]) -> str:
        role = match.group(1)
        if role not in paths:
            raise ValueError(f"Unknown Procedure path placeholder {role!r}.")
        return str(paths[role])

    return PLACEHOLDER.sub(replacement, value)


def _plan(
    catalog_path: Path,
    catalog: dict[str, Any],
    request_path: Path,
    request: dict[str, Any],
    *,
    create_outputs: bool,
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any]]:
    procedure = _select(catalog, request)
    paths = _resolve_paths(procedure, request, create_outputs=create_outputs)
    _preflight(procedure, paths)
    stages = [
        {
            "id": stage["id"],
            "argv": [_expand(str(value), paths) for value in stage["argv"]],
            "expected_outputs": [
                _expand(str(value), paths) for value in stage["expected_outputs"]
            ],
        }
        for stage in procedure["stages"]
    ]
    input_hashes = {
        role: _sha256(path)
        for role, path in paths.items()
        if procedure["required_paths"][role] == "file"
    }
    plan = {
        "schema_version": "d3-design-procedure-plan.v1",
        "procedure_id": procedure["id"],
        "procedure_status": procedure["status"],
        "selector": procedure["selector"],
        "catalog_path": str(catalog_path),
        "catalog_sha256": _sha256(catalog_path),
        "request_path": str(request_path),
        "request_sha256": _sha256(request_path),
        "resolved_paths": {role: str(path) for role, path in paths.items()},
        "input_sha256": input_hashes,
        "stages": stages,
        "receipt": _expand(str(procedure["receipt"]), paths),
    }
    return procedure, paths, plan


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def _run(plan: dict[str, Any]) -> Path:
    started = datetime.now(timezone.utc)
    stage_records: list[dict[str, Any]] = []
    for stage in plan["stages"]:
        stage_started = datetime.now(timezone.utc)
        completed = subprocess.run(stage["argv"], cwd=WORKBENCH_ROOT, check=False)
        stage_record = {
            "id": stage["id"],
            "argv": stage["argv"],
            "started_at": stage_started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "returncode": completed.returncode,
        }
        stage_records.append(stage_record)
        if completed.returncode != 0:
            raise RuntimeError(
                f"Procedure stage {stage['id']} failed with exit code {completed.returncode}."
            )
        missing = [path for path in stage["expected_outputs"] if not Path(path).exists()]
        if missing:
            raise RuntimeError(
                f"Procedure stage {stage['id']} did not produce expected outputs: {missing}"
            )
    receipt_path = Path(plan["receipt"])
    receipt = {
        "schema_version": "d3-design-procedure-run.v1",
        "status": "complete",
        "procedure_id": plan["procedure_id"],
        "selector": plan["selector"],
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "catalog_sha256": plan["catalog_sha256"],
        "request_sha256": plan["request_sha256"],
        "platform_sha256": _sha256(Path(__file__).resolve()),
        "resolved_paths": plan["resolved_paths"],
        "input_sha256": plan["input_sha256"],
        "stages": stage_records,
    }
    _atomic_json(receipt_path, receipt)
    return receipt_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    for command in ("plan", "run"):
        child = subparsers.add_parser(command)
        child.add_argument("request", type=Path)
    arguments = parser.parse_args(argv)
    catalog_path = arguments.catalog.resolve()
    catalog = _load_catalog(catalog_path)
    if arguments.command == "list":
        print(
            json.dumps(
                [
                    {
                        "id": item["id"],
                        "selector": item["selector"],
                        "status": item["status"],
                        "description": item["description"],
                    }
                    for item in catalog["procedures"]
                ],
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    request_path = arguments.request.resolve()
    request = _load_request(request_path)
    _, _, plan = _plan(
        catalog_path,
        catalog,
        request_path,
        request,
        create_outputs=arguments.command == "run",
    )
    if arguments.command == "plan":
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0
    print(_run(plan))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)
