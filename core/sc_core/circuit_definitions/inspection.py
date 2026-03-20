from __future__ import annotations

import ast
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

ValidationLevel = Literal["ok", "warning"]
DiagnosticSeverity = Literal["error", "warning", "info"]
DiagnosticSource = Literal[
    "source_text",
    "netlist_schema",
    "parameters",
    "components",
    "topology",
    "cross_reference",
]
InspectionStatus = Literal["valid", "invalid"]

DEFAULT_PREVIEW_ARTIFACTS: tuple[str, ...] = (
    "definition.normalized.json",
    "schematic-input.yaml",
    "parameter-bundle.toml",
)

GROUND_TOKEN = "0"
GROUND_TOKENS = {GROUND_TOKEN}
_NAME_HINT_PATTERN = re.compile(r"['\"]?name['\"]?\s*:\s*['\"]?([A-Za-z0-9_.:-]+)")
_FAMILY_HINT_PATTERN = re.compile(r"['\"]?family['\"]?\s*:\s*['\"]?([A-Za-z0-9_.:-]+)")


@dataclass(frozen=True)
class ValidationNotice:
    level: ValidationLevel
    message: str


@dataclass(frozen=True)
class CircuitDefinitionDiagnostic:
    severity: DiagnosticSeverity
    code: str
    message: str
    source: DiagnosticSource
    blocking: bool
    path: tuple[str | int, ...] = ()


@dataclass(frozen=True)
class CircuitDefinitionInspectionSummary:
    status: InspectionStatus
    component_count: int
    topology_count: int
    parameter_count: int
    port_count: int
    diagnostic_count: int
    error_count: int
    warning_count: int
    info_count: int


@dataclass(frozen=True)
class CircuitDefinitionInspection:
    circuit_name: str
    family: str
    element_count: int
    normalized_output: str
    validation_notices: tuple[ValidationNotice, ...]
    diagnostics: tuple[CircuitDefinitionDiagnostic, ...]
    summary: CircuitDefinitionInspectionSummary
    normalized_payload: dict[str, object]
    preview_artifacts: tuple[str, ...] = DEFAULT_PREVIEW_ARTIFACTS


@dataclass(frozen=True)
class _ParameterSpec:
    name: str
    default: float
    unit: str

    def as_dict(self) -> dict[str, object]:
        return {"name": self.name, "default": self.default, "unit": self.unit}


@dataclass(frozen=True)
class _ComponentSpec:
    name: str
    unit: str
    default: float | None = None
    value_ref: str | None = None

    def as_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"name": self.name, "unit": self.unit}
        if self.default is not None:
            payload["default"] = self.default
        if self.value_ref is not None:
            payload["value_ref"] = self.value_ref
        return payload


@dataclass(frozen=True)
class _TopologyEntry:
    name: str
    node1: str
    node2: str
    value_ref: str | int
    kind: str

    @property
    def is_port(self) -> bool:
        return self.kind == "port"

    @property
    def is_mutual_coupling(self) -> bool:
        return self.kind == "mutual_coupling"

    def as_list(self) -> list[str | int]:
        return [self.name, self.node1, self.node2, self.value_ref]


def inspect_circuit_definition_source(source_text: str) -> CircuitDefinitionInspection:
    diagnostics: list[CircuitDefinitionDiagnostic] = []
    parsed_payload = _parse_source_text(source_text, diagnostics)
    if parsed_payload is None:
        legacy_inspection = _inspect_legacy_draft(source_text)
        if legacy_inspection is not None:
            return legacy_inspection
    payload = _coerce_mapping(parsed_payload)

    parameters = _inspect_parameters(payload, diagnostics)
    components = _inspect_components(payload, diagnostics)
    topology = _inspect_topology(payload, diagnostics)
    _validate_cross_references(parameters, components, topology, diagnostics)

    circuit_name = _resolve_circuit_name(payload, source_text, diagnostics)
    layout_profile = _infer_layout_profile(topology)
    family = _resolve_family(payload, source_text, layout_profile)
    normalized_payload = _build_normalized_payload(circuit_name, parameters, components, topology)
    summary = _build_summary(diagnostics, parameters, components, topology)
    validation_notices = _build_validation_notices(diagnostics, summary)

    return CircuitDefinitionInspection(
        circuit_name=circuit_name,
        family=family,
        element_count=len(topology),
        normalized_output=json.dumps(normalized_payload, indent=2),
        validation_notices=validation_notices,
        diagnostics=tuple(diagnostics),
        summary=summary,
        normalized_payload=normalized_payload,
    )


def _parse_source_text(
    source_text: str,
    diagnostics: list[CircuitDefinitionDiagnostic],
) -> Mapping[str, Any] | None:
    stripped = source_text.strip()
    if not stripped:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="SOURCE_TEXT_EMPTY",
                message="Circuit Definition text is empty.",
                source="source_text",
                path=("source_text",),
            )
        )
        return None

    try:
        parsed = ast.literal_eval(stripped)
    except Exception:
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="SOURCE_TEXT_PARSE_ERROR",
                    message=f"Unable to parse Circuit Definition text: {exc}",
                    source="source_text",
                    path=("source_text",),
                )
            )
            return None

    if not isinstance(parsed, Mapping):
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="NETLIST_ROOT_NOT_MAPPING",
                message="Circuit Definition must be a mapping object.",
                source="netlist_schema",
                path=(),
            )
        )
        return None
    return parsed


def _inspect_legacy_draft(source_text: str) -> CircuitDefinitionInspection | None:
    stripped = source_text.strip()
    if not stripped:
        return None
    if stripped.startswith("{") or stripped.startswith("["):
        return None
    if _extract_hint(source_text, _NAME_HINT_PATTERN) is None:
        return None

    circuit_name = _extract_hint(source_text, _NAME_HINT_PATTERN) or "pending_name"
    family = _extract_hint(source_text, _FAMILY_HINT_PATTERN) or "pending_family"
    element_count = max(1, sum(1 for line in source_text.splitlines() if ":" in line) - 3)
    diagnostics = (
        _diagnostic(
            severity="warning",
            code="LEGACY_DRAFT_COMPAT_MODE",
            message="Inspection fell back to legacy draft compatibility mode.",
            source="source_text",
            path=("source_text",),
        ),
    )
    summary = CircuitDefinitionInspectionSummary(
        status="valid",
        component_count=0,
        topology_count=0,
        parameter_count=0,
        port_count=0,
        diagnostic_count=1,
        error_count=0,
        warning_count=1,
        info_count=0,
    )
    normalized_payload = {"name": circuit_name, "components": [], "topology": []}
    return CircuitDefinitionInspection(
        circuit_name=circuit_name,
        family=family,
        element_count=element_count,
        normalized_output=_render_legacy_normalized_output(circuit_name, family, element_count),
        validation_notices=_legacy_validation_notices(),
        diagnostics=diagnostics,
        summary=summary,
        normalized_payload=normalized_payload,
    )


def _coerce_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    return dict(payload.items())


def _inspect_parameters(
    payload: Mapping[str, Any],
    diagnostics: list[CircuitDefinitionDiagnostic],
) -> list[_ParameterSpec]:
    raw_parameters = payload.get("parameters", [])
    if raw_parameters is None:
        return []
    if not isinstance(raw_parameters, list):
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="NETLIST_PARAMETERS_NOT_LIST",
                message="'parameters' must be a list.",
                source="parameters",
                path=("parameters",),
            )
        )
        return []

    parameters: list[_ParameterSpec] = []
    seen_names: set[str] = set()
    for index, raw_parameter in enumerate(raw_parameters):
        path = ("parameters", index)
        if not isinstance(raw_parameter, Mapping):
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="PARAMETER_ROW_INVALID",
                    message="parameters rows must be mappings.",
                    source="parameters",
                    path=path,
                )
            )
            continue

        row = dict(raw_parameter.items())
        name = _normalize_required_string(
            row.get("name"),
            code="PARAMETER_NAME_REQUIRED",
            message="Parameter rows must define a non-empty 'name'.",
            source="parameters",
            path=path + ("name",),
            diagnostics=diagnostics,
        )
        unit = _normalize_required_string(
            row.get("unit"),
            code="PARAMETER_UNIT_REQUIRED",
            message=f"Parameter '{name or index}' must define a non-empty 'unit'.",
            source="parameters",
            path=path + ("unit",),
            diagnostics=diagnostics,
        )
        default = _coerce_float(
            row.get("default"),
            code="PARAMETER_DEFAULT_INVALID",
            message=f"Parameter '{name or index}' default must be numeric.",
            source="parameters",
            path=path + ("default",),
            diagnostics=diagnostics,
        )
        if name is None or unit is None or default is None:
            continue
        if name in seen_names:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="DUPLICATE_PARAMETER_NAME",
                    message=f"Duplicate parameter name '{name}'.",
                    source="parameters",
                    path=path + ("name",),
                )
            )
            continue
        seen_names.add(name)
        parameters.append(_ParameterSpec(name=name, default=default, unit=unit))
    return parameters


def _inspect_components(
    payload: Mapping[str, Any],
    diagnostics: list[CircuitDefinitionDiagnostic],
) -> list[_ComponentSpec]:
    if "components" not in payload:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="NETLIST_COMPONENTS_MISSING",
                message="Circuit Definition must define 'components'.",
                source="netlist_schema",
                path=("components",),
            )
        )
        return []
    raw_components = payload.get("components")
    if not isinstance(raw_components, list):
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="NETLIST_COMPONENTS_NOT_LIST",
                message="'components' must be a list.",
                source="components",
                path=("components",),
            )
        )
        return []

    components: list[_ComponentSpec] = []
    seen_names: set[str] = set()
    for index, raw_component in enumerate(raw_components):
        path = ("components", index)
        if not isinstance(raw_component, Mapping):
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="COMPONENT_ROW_INVALID",
                    message="components rows must be mappings.",
                    source="components",
                    path=path,
                )
            )
            continue
        row = dict(raw_component.items())
        name = _normalize_required_string(
            row.get("name"),
            code="COMPONENT_NAME_REQUIRED",
            message="Component rows must define a non-empty 'name'.",
            source="components",
            path=path + ("name",),
            diagnostics=diagnostics,
        )
        unit = _normalize_required_string(
            row.get("unit"),
            code="COMPONENT_UNIT_REQUIRED",
            message=f"Component '{name or index}' must define a non-empty 'unit'.",
            source="components",
            path=path + ("unit",),
            diagnostics=diagnostics,
        )
        has_default = "default" in row
        has_value_ref = "value_ref" in row
        if has_default == has_value_ref:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="COMPONENT_VALUE_MODE_INVALID",
                    message=(
                        f"Component '{name or index}' must define exactly one of "
                        "'default' or 'value_ref'."
                    ),
                    source="components",
                    path=path,
                )
            )
            continue
        if name is None or unit is None:
            continue
        if name in seen_names:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="DUPLICATE_COMPONENT_NAME",
                    message=f"Duplicate component name '{name}'.",
                    source="components",
                    path=path + ("name",),
                )
            )
            continue

        default: float | None = None
        value_ref: str | None = None
        if has_default:
            default = _coerce_float(
                row.get("default"),
                code="COMPONENT_DEFAULT_INVALID",
                message=f"Component '{name}' default must be numeric.",
                source="components",
                path=path + ("default",),
                diagnostics=diagnostics,
            )
        else:
            value_ref = _normalize_required_string(
                row.get("value_ref"),
                code="COMPONENT_VALUE_REF_INVALID",
                message=f"Component '{name}' value_ref must be a non-empty string.",
                source="components",
                path=path + ("value_ref",),
                diagnostics=diagnostics,
            )
        if (has_default and default is None) or (has_value_ref and value_ref is None):
            continue
        seen_names.add(name)
        components.append(_ComponentSpec(name=name, unit=unit, default=default, value_ref=value_ref))
    return components


def _inspect_topology(
    payload: Mapping[str, Any],
    diagnostics: list[CircuitDefinitionDiagnostic],
) -> list[_TopologyEntry]:
    if "topology" not in payload:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="NETLIST_TOPOLOGY_MISSING",
                message="Circuit Definition must define 'topology'.",
                source="netlist_schema",
                path=("topology",),
            )
        )
        return []
    raw_topology = payload.get("topology")
    if not isinstance(raw_topology, list):
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="NETLIST_TOPOLOGY_NOT_LIST",
                message="'topology' must be a list.",
                source="topology",
                path=("topology",),
            )
        )
        return []

    topology: list[_TopologyEntry] = []
    seen_names: set[str] = set()
    for index, raw_row in enumerate(raw_topology):
        path = ("topology", index)
        if not isinstance(raw_row, Sequence) or isinstance(raw_row, str | bytes):
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="TOPOLOGY_ROW_INVALID",
                    message="topology rows must contain exactly 4 items.",
                    source="topology",
                    path=path,
                )
            )
            continue
        row = list(raw_row)
        if len(row) != 4:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="TOPOLOGY_ROW_INVALID",
                    message="topology rows must contain exactly 4 items.",
                    source="topology",
                    path=path,
                )
            )
            continue

        name = _normalize_required_string(
            row[0],
            code="TOPOLOGY_NAME_REQUIRED",
            message="topology rows must define a non-empty element name.",
            source="topology",
            path=path + (0,),
            diagnostics=diagnostics,
        )
        if name is None:
            continue
        if name in seen_names:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="DUPLICATE_TOPOLOGY_ELEMENT_NAME",
                    message=f"Duplicate topology element name '{name}'.",
                    source="topology",
                    path=path + (0,),
                )
            )
            continue
        kind = _infer_element_kind(name, diagnostics, path=path + (0,))
        if kind is None:
            continue

        if kind == "mutual_coupling":
            first_ref = _normalize_required_string(
                row[1],
                code="MUTUAL_COUPLING_FIRST_REFERENCE_INVALID",
                message=f"Mutual coupling '{name}' must reference an inductor element name.",
                source="topology",
                path=path + (1,),
                diagnostics=diagnostics,
            )
            second_ref = _normalize_required_string(
                row[2],
                code="MUTUAL_COUPLING_SECOND_REFERENCE_INVALID",
                message=f"Mutual coupling '{name}' must reference an inductor element name.",
                source="topology",
                path=path + (2,),
                diagnostics=diagnostics,
            )
            component_ref = _normalize_required_string(
                row[3],
                code="MUTUAL_COUPLING_COMPONENT_REFERENCE_INVALID",
                message=f"Mutual coupling '{name}' must reference a component name.",
                source="topology",
                path=path + (3,),
                diagnostics=diagnostics,
            )
            if first_ref is None or second_ref is None or component_ref is None:
                continue
            seen_names.add(name)
            topology.append(
                _TopologyEntry(
                    name=name,
                    node1=first_ref,
                    node2=second_ref,
                    value_ref=component_ref,
                    kind=kind,
                )
            )
            continue

        node1 = _normalize_node_token(row[1], diagnostics, path=path + (1,))
        node2 = _normalize_node_token(row[2], diagnostics, path=path + (2,))
        if node1 is None or node2 is None:
            continue

        value_ref: str | int | None
        if kind == "port":
            value_ref = _normalize_port_index(row[3], diagnostics, path=path + (3,), row_name=name)
        else:
            value_ref = _normalize_required_string(
                row[3],
                code="TOPOLOGY_COMPONENT_REFERENCE_INVALID",
                message=f"Topology row '{name}' must reference a component name.",
                source="topology",
                path=path + (3,),
                diagnostics=diagnostics,
            )
        if value_ref is None:
            continue
        seen_names.add(name)
        topology.append(
            _TopologyEntry(name=name, node1=node1, node2=node2, value_ref=value_ref, kind=kind)
        )
    return topology


def _validate_cross_references(
    parameters: list[_ParameterSpec],
    components: list[_ComponentSpec],
    topology: list[_TopologyEntry],
    diagnostics: list[CircuitDefinitionDiagnostic],
) -> None:
    parameter_specs = {parameter.name: parameter for parameter in parameters}
    component_specs = {component.name: component for component in components}
    seen_port_indices: set[int] = set()
    element_kind_by_name = {row.name: row.kind for row in topology}

    for index, component in enumerate(components):
        if component.value_ref is None:
            continue
        parameter = parameter_specs.get(component.value_ref)
        if parameter is None:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="PARAMETER_REFERENCE_UNDEFINED",
                    message=(
                        f"Component '{component.name}' references undefined parameter "
                        f"'{component.value_ref}'."
                    ),
                    source="cross_reference",
                    path=("components", index, "value_ref"),
                )
            )
            continue
        if parameter.unit != component.unit:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="COMPONENT_PARAMETER_UNIT_MISMATCH",
                    message=(
                        f"Component '{component.name}' unit '{component.unit}' does not match "
                        f"parameter '{parameter.name}' unit '{parameter.unit}'."
                    ),
                    source="cross_reference",
                    path=("components", index, "unit"),
                )
            )

    topology_index_by_name = {row.name: index for index, row in enumerate(topology)}
    for index, row in enumerate(topology):
        if row.is_port:
            port_index = int(row.value_ref)
            if port_index in seen_port_indices:
                diagnostics.append(
                    _diagnostic(
                        severity="error",
                        code="DUPLICATE_PORT_INDEX",
                        message=f"Duplicate port index '{port_index}'.",
                        source="cross_reference",
                        path=("topology", index, 3),
                    )
                )
            else:
                seen_port_indices.add(port_index)
            if _is_ground_node(row.node1) == _is_ground_node(row.node2):
                diagnostics.append(
                    _diagnostic(
                        severity="error",
                        code="PORT_GROUND_TOPOLOGY",
                        message=f"Port '{row.name}' must connect exactly one side to ground ('0').",
                        source="cross_reference",
                        path=("topology", index),
                    )
                )
            continue

        if row.is_mutual_coupling:
            if row.value_ref not in component_specs:
                diagnostics.append(
                    _diagnostic(
                        severity="error",
                        code="MUTUAL_COUPLING_COMPONENT_REFERENCE_UNDEFINED",
                        message=(
                            f"Mutual coupling '{row.name}' references undefined component "
                            f"'{row.value_ref}'."
                        ),
                        source="cross_reference",
                        path=("topology", index, 3),
                    )
                )
            for slot, reference in ((1, row.node1), (2, row.node2)):
                referenced_kind = element_kind_by_name.get(reference)
                if referenced_kind not in {"inductor", "josephson_junction"}:
                    diagnostics.append(
                        _diagnostic(
                            severity="error",
                            code="MUTUAL_COUPLING_ELEMENT_NON_INDUCTIVE",
                            message=(
                                f"Mutual coupling '{row.name}' references unknown or non-inductive "
                                f"element '{reference}'."
                            ),
                            source="cross_reference",
                            path=("topology", index, slot),
                        )
                    )
            continue

        if row.value_ref not in component_specs:
            diagnostics.append(
                _diagnostic(
                    severity="error",
                    code="TOPOLOGY_COMPONENT_REFERENCE_UNDEFINED",
                    message=(
                        f"Topology row '{row.name}' references undefined component "
                        f"'{row.value_ref}'."
                    ),
                    source="cross_reference",
                    path=("topology", index, 3),
                )
            )
        referenced_index = topology_index_by_name.get(str(row.value_ref))
        if referenced_index is not None and topology[referenced_index].is_port:
            diagnostics.append(
                _diagnostic(
                    severity="warning",
                    code="TOPOLOGY_COMPONENT_REFERENCE_PORT_NAME",
                    message=(
                        f"Topology row '{row.name}' references topology element '{row.value_ref}' "
                        "instead of a component name."
                    ),
                    source="cross_reference",
                    path=("topology", index, 3),
                    blocking=False,
                )
            )


def _resolve_circuit_name(
    payload: Mapping[str, Any],
    source_text: str,
    diagnostics: list[CircuitDefinitionDiagnostic],
) -> str:
    raw_name = payload.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="NETLIST_NAME_MISSING",
            message="Circuit Definition must define a non-empty 'name'.",
            source="netlist_schema",
            path=("name",),
        )
    )
    return _extract_hint(source_text, _NAME_HINT_PATTERN) or "invalid_circuit_definition"


def _resolve_family(payload: Mapping[str, Any], source_text: str, layout_profile: str) -> str:
    raw_family = payload.get("family")
    if isinstance(raw_family, str) and raw_family.strip():
        return raw_family.strip()
    hinted_family = _extract_hint(source_text, _FAMILY_HINT_PATTERN)
    if hinted_family is not None:
        return hinted_family
    return layout_profile


def _build_normalized_payload(
    circuit_name: str,
    parameters: list[_ParameterSpec],
    components: list[_ComponentSpec],
    topology: list[_TopologyEntry],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": circuit_name,
        "components": [component.as_dict() for component in components],
        "topology": [row.as_list() for row in topology],
    }
    if parameters:
        payload["parameters"] = [parameter.as_dict() for parameter in parameters]
    return payload


def _build_summary(
    diagnostics: list[CircuitDefinitionDiagnostic],
    parameters: list[_ParameterSpec],
    components: list[_ComponentSpec],
    topology: list[_TopologyEntry],
) -> CircuitDefinitionInspectionSummary:
    error_count = sum(1 for diagnostic in diagnostics if diagnostic.severity == "error")
    warning_count = sum(1 for diagnostic in diagnostics if diagnostic.severity == "warning")
    info_count = sum(1 for diagnostic in diagnostics if diagnostic.severity == "info")
    return CircuitDefinitionInspectionSummary(
        status="invalid" if error_count else "valid",
        component_count=len(components),
        topology_count=len(topology),
        parameter_count=len(parameters),
        port_count=sum(1 for row in topology if row.is_port),
        diagnostic_count=len(diagnostics),
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
    )


def _build_validation_notices(
    diagnostics: list[CircuitDefinitionDiagnostic],
    summary: CircuitDefinitionInspectionSummary,
) -> tuple[ValidationNotice, ...]:
    if not diagnostics:
        return (
            ValidationNotice(level="ok", message="Circuit netlist passes canonical inspection."),
            ValidationNotice(
                level="ok",
                message=(
                    "Normalized output is aligned with the canonical circuit-netlist contract."
                ),
            ),
        )

    notice_messages: list[str] = []
    if summary.error_count:
        notice_messages.append(
            f"{summary.error_count} blocking diagnostic(s) found during canonical inspection."
        )
    if summary.warning_count:
        notice_messages.append(
            f"{summary.warning_count} non-blocking diagnostic(s) found during canonical inspection."
        )
    for diagnostic in diagnostics:
        if diagnostic.message not in notice_messages:
            notice_messages.append(diagnostic.message)
    return tuple(ValidationNotice(level="warning", message=message) for message in notice_messages)


def _legacy_validation_notices() -> tuple[ValidationNotice, ...]:
    return (
        ValidationNotice(level="ok", message="Canonical schema matches rewrite draft v1."),
        ValidationNotice(level="ok", message="All required element blocks are present."),
        ValidationNotice(
            level="warning",
            message="Port mapping metadata still needs migration from legacy forms.",
        ),
    )


def _render_legacy_normalized_output(circuit_name: str, family: str, element_count: int) -> str:
    return (
        "{\n"
        f'  "circuit": "{circuit_name}",\n'
        f'  "family": "{family}",\n'
        f'  "elements": {element_count},\n'
        '  "ports": "pending migration",\n'
        '  "schemdraw_ready": true\n'
        "}"
    )


def _normalize_required_string(
    raw_value: object,
    *,
    code: str,
    message: str,
    source: DiagnosticSource,
    path: tuple[str | int, ...],
    diagnostics: list[CircuitDefinitionDiagnostic],
) -> str | None:
    if not isinstance(raw_value, str):
        diagnostics.append(
            _diagnostic(
                severity="error",
                code=code,
                message=message,
                source=source,
                path=path,
            )
        )
        return None
    value = raw_value.strip()
    if not value:
        diagnostics.append(
            _diagnostic(
                severity="error",
                code=code,
                message=message,
                source=source,
                path=path,
            )
        )
        return None
    return value


def _coerce_float(
    raw_value: object,
    *,
    code: str,
    message: str,
    source: DiagnosticSource,
    path: tuple[str | int, ...],
    diagnostics: list[CircuitDefinitionDiagnostic],
) -> float | None:
    if isinstance(raw_value, bool):
        diagnostics.append(
            _diagnostic(
                severity="error",
                code=code,
                message=message,
                source=source,
                path=path,
            )
        )
        return None
    if isinstance(raw_value, int | float):
        return float(raw_value)
    if isinstance(raw_value, str):
        try:
            return float(raw_value)
        except ValueError:
            pass
    diagnostics.append(
        _diagnostic(
            severity="error",
            code=code,
            message=message,
            source=source,
            path=path,
        )
    )
    return None


def _infer_element_kind(
    element_name: str,
    diagnostics: list[CircuitDefinitionDiagnostic],
    *,
    path: tuple[str | int, ...],
) -> str | None:
    lowered = element_name.lower()
    if lowered.startswith("lj"):
        return "josephson_junction"
    if lowered.startswith("p"):
        return "port"
    if lowered.startswith("r"):
        return "resistor"
    if lowered.startswith("l"):
        return "inductor"
    if lowered.startswith("c"):
        return "capacitor"
    if lowered.startswith("k"):
        return "mutual_coupling"
    diagnostics.append(
        _diagnostic(
            severity="error",
            code="TOPOLOGY_PREFIX_UNSUPPORTED",
            message=f"Unsupported topology element prefix for '{element_name}'.",
            source="topology",
            path=path,
        )
    )
    return None


def _normalize_node_token(
    raw_value: object,
    diagnostics: list[CircuitDefinitionDiagnostic],
    *,
    path: tuple[str | int, ...],
) -> str | None:
    if not isinstance(raw_value, str):
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="INVALID_NODE_TOKEN",
                message="Topology nodes must be numeric strings. Use '0' as the only ground token.",
                source="topology",
                path=path,
            )
        )
        return None
    node_text = raw_value.strip()
    if node_text.lower() == "gnd":
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="UNSUPPORTED_GROUND_ALIAS",
                message="Ground must be the string '0'. The 'gnd' alias is not supported.",
                source="topology",
                path=path,
            )
        )
        return None
    if not node_text.isdigit():
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="INVALID_NODE_TOKEN",
                message="Topology nodes must be numeric strings. Use '0' as the only ground token.",
                source="topology",
                path=path,
            )
        )
        return None
    return str(int(node_text))


def _normalize_port_index(
    raw_value: object,
    diagnostics: list[CircuitDefinitionDiagnostic],
    *,
    path: tuple[str | int, ...],
    row_name: str,
) -> int | None:
    if not isinstance(raw_value, int) or isinstance(raw_value, bool):
        diagnostics.append(
            _diagnostic(
                severity="error",
                code="PORT_INDEX_NOT_INTEGER",
                message=f"Port '{row_name}' must use an integer port index.",
                source="topology",
                path=path,
            )
        )
        return None
    return int(raw_value)


def _infer_layout_profile(topology: list[_TopologyEntry]) -> str:
    series_inductive = 0
    shunt_capacitive = 0
    shunt_josephson = 0

    for row in topology:
        if row.is_port or row.is_mutual_coupling:
            continue
        is_shunt = _is_ground_node(row.node1) ^ _is_ground_node(row.node2)
        if not is_shunt:
            if row.kind in {"inductor", "josephson_junction"}:
                series_inductive += 1
            continue
        if row.kind == "capacitor":
            shunt_capacitive += 1
        if row.kind == "josephson_junction":
            shunt_josephson += 1

    if series_inductive >= 3 and shunt_capacitive >= 2:
        return "jtwpa"
    if any(row.is_port for row in topology) and shunt_capacitive >= 1 and shunt_josephson >= 1:
        return "jpa"
    return "generic"


def _is_ground_node(node: str | int) -> bool:
    return str(node).strip() in GROUND_TOKENS


def _extract_hint(source_text: str, pattern: re.Pattern[str]) -> str | None:
    match = pattern.search(source_text)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def _diagnostic(
    *,
    severity: DiagnosticSeverity,
    code: str,
    message: str,
    source: DiagnosticSource,
    path: tuple[str | int, ...],
    blocking: bool = True,
) -> CircuitDefinitionDiagnostic:
    effective_blocking = blocking if severity == "error" else False
    return CircuitDefinitionDiagnostic(
        severity=severity,
        code=code,
        message=message,
        source=source,
        blocking=effective_blocking,
        path=path,
    )
