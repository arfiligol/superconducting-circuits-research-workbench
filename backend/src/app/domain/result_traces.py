from __future__ import annotations

import ast
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from src.app.domain.tasks import TaskDetail

_FAMILIES = {"s_matrix", "y_matrix", "z_matrix"}
_SOURCES = {"raw", "ptc"}
_MODE_GROUPS = {"base"}
_DEFAULT_MODE = "mode_0"


@dataclass(frozen=True)
class ResultTraceSelection:
    family: str
    source: str
    output_port: int
    input_port: int
    trace_mode_group: str = "base"
    output_mode: str = _DEFAULT_MODE
    input_mode: str = _DEFAULT_MODE
    z0_ohm: float | None = None

    def to_trace_key(self) -> str:
        parts = [
            f"family={self.family}",
            f"source={self.source}",
            f"trace_mode_group={self.trace_mode_group}",
            f"output_port={self.output_port}",
            f"input_port={self.input_port}",
            f"output_mode={self.output_mode}",
            f"input_mode={self.input_mode}",
        ]
        if self.z0_ohm is not None:
            parts.append(f"z0_ohm={_format_z0(self.z0_ohm)}")
        return "|".join(parts)

    @classmethod
    def from_trace_key(cls, trace_key: str) -> ResultTraceSelection:
        raw_parts = [part.strip() for part in trace_key.split("|") if len(part.strip()) > 0]
        payload: dict[str, str] = {}
        for part in raw_parts:
            key, separator, value = part.partition("=")
            if separator != "=" or len(key.strip()) == 0 or len(value.strip()) == 0:
                raise ValueError("trace_key is malformed")
            payload[key.strip()] = value.strip()

        family = payload.get("family")
        source = payload.get("source")
        trace_mode_group = payload.get("trace_mode_group", "base")
        output_mode = payload.get("output_mode", _DEFAULT_MODE)
        input_mode = payload.get("input_mode", _DEFAULT_MODE)
        if family not in _FAMILIES:
            raise ValueError("trace_key family is invalid")
        if source not in _SOURCES:
            raise ValueError("trace_key source is invalid")
        if trace_mode_group not in _MODE_GROUPS:
            raise ValueError("trace_key trace_mode_group is invalid")
        output_port = _parse_positive_int(payload.get("output_port"), field="output_port")
        input_port = _parse_positive_int(payload.get("input_port"), field="input_port")
        raw_z0 = payload.get("z0_ohm")
        z0_ohm = None
        if raw_z0 is not None:
            z0_ohm = float(raw_z0)
            if z0_ohm <= 0:
                raise ValueError("trace_key z0_ohm must be positive")
        elif family in {"y_matrix", "z_matrix"}:
            z0_ohm = 50.0
        return cls(
            family=family,
            source=source,
            output_port=output_port,
            input_port=input_port,
            trace_mode_group=trace_mode_group,
            output_mode=output_mode,
            input_mode=input_mode,
            z0_ohm=z0_ohm,
        )


def build_trace_parameter(selection: ResultTraceSelection) -> str:
    family_prefix = {
        "s_matrix": "S",
        "y_matrix": "Y",
        "z_matrix": "Z",
    }[selection.family]
    return f"{family_prefix}{selection.output_port}{selection.input_port}"


def build_trace_id(*, task_id: int, selection: ResultTraceSelection) -> str:
    base = (
        f"trace_task_{task_id}_{selection.family}_{selection.source}"
        f"_o{selection.output_port}_i{selection.input_port}"
        f"_{selection.output_mode}_{selection.input_mode}"
    )
    if selection.z0_ohm is not None:
        return f"{base}_z0_{_format_z0(selection.z0_ohm).replace('.', '_')}"
    return base


def available_sources_for_family(task: TaskDetail, family: str) -> tuple[str, ...]:
    if family in {"y_matrix", "z_matrix"} and ptc_available(task):
        return ("raw", "ptc")
    return ("raw",)


def resolve_port_options(
    task: TaskDetail,
    *,
    definition: object | None,
) -> dict[int, str]:
    port_indices = _extract_definition_port_indices(definition)
    if len(port_indices) == 0:
        port_indices = _extract_setup_port_indices(task)
    if len(port_indices) == 0:
        port_indices = (1,)
    return {index: f"Port {index}" for index in port_indices}


def ptc_available(task: TaskDetail) -> bool:
    return (
        task.simulation_setup is not None
        and task.simulation_setup.ptc is not None
        and task.simulation_setup.ptc.enabled
    )


def _parse_positive_int(value: str | None, *, field: str) -> int:
    if value is None:
        raise ValueError(f"trace_key {field} is required")
    resolved = int(value)
    if resolved <= 0:
        raise ValueError(f"trace_key {field} must be positive")
    return resolved


def _format_z0(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _extract_definition_port_indices(definition: object | None) -> tuple[int, ...]:
    if definition is None:
        return ()

    normalized_output = _parse_mapping_literal(getattr(definition, "normalized_output", None))
    if normalized_output is not None:
        expanded_payload = normalized_output.get("expanded")
        expanded_mapping = (
            expanded_payload
            if isinstance(expanded_payload, Mapping)
            else _parse_mapping_literal(expanded_payload)
        )
        expanded_indices = _extract_topology_port_indices(
            None if expanded_mapping is None else expanded_mapping.get("topology")
        )
        if len(expanded_indices) > 0:
            return expanded_indices

    source_payload = _parse_mapping_literal(getattr(definition, "source_text", None))
    if source_payload is None:
        return ()
    return _extract_topology_port_indices(source_payload.get("topology"))


def _parse_mapping_literal(value: object) -> Mapping[str, object] | None:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if len(stripped) == 0:
        return None
    try:
        parsed = ast.literal_eval(stripped)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, Mapping) else None


def _extract_topology_port_indices(topology: object) -> tuple[int, ...]:
    if not isinstance(topology, Sequence) or isinstance(topology, (str, bytes)):
        return ()

    indices: set[int] = set()
    for row in topology:
        port_index = _extract_port_index_from_topology_row(row)
        if port_index is not None:
            indices.add(port_index)
    return tuple(sorted(indices))


def _extract_port_index_from_topology_row(row: object) -> int | None:
    if not isinstance(row, Sequence) or isinstance(row, (str, bytes)) or len(row) < 4:
        return None
    element_name = row[0]
    if not isinstance(element_name, str):
        return None
    stripped = element_name.strip().lower()
    if not stripped.startswith("p"):
        return None
    if not stripped[1:].isdigit():
        return None
    value_ref = row[3]
    if isinstance(value_ref, int) and value_ref >= 1:
        return value_ref
    return int(stripped[1:])


def _extract_setup_port_indices(task: TaskDetail) -> tuple[int, ...]:
    if task.simulation_setup is None:
        return ()

    indices: set[int] = set()
    for source in task.simulation_setup.sources:
        port_index = _extract_port_index_from_token(source.target)
        if port_index is not None:
            indices.add(port_index)
    if task.simulation_setup.ptc is not None:
        for port in task.simulation_setup.ptc.compensate_ports:
            port_index = _extract_port_index_from_token(port)
            if port_index is not None:
                indices.add(port_index)
    return tuple(sorted(indices))


def _extract_port_index_from_token(token: object) -> int | None:
    if not isinstance(token, str):
        return None
    stripped = token.strip().lower()
    if stripped.startswith("port_") and stripped[5:].isdigit():
        return int(stripped[5:])
    if stripped.startswith("p") and stripped[1:].isdigit():
        return int(stripped[1:])
    return None
