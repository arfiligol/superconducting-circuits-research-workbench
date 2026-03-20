"""Circuit domain models and Schematic Netlist parsing utilities."""

from __future__ import annotations

import ast
import json
import math
import pprint
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from core.simulation.domain.compiler import compile_simulation_topology
from core.simulation.domain.ir import CircuitElement, CircuitIR
from core.simulation.domain.validators import (
    validate_mutual_coupling_component_reference,
    validate_mutual_coupling_inductive_references,
    validate_port_row_contract,
    validate_public_node_token,
    validate_topology_component_reference,
)

DEFAULT_LAYOUT_DIRECTION = "lr"
GROUND_TOKEN = "0"
GROUND_TOKENS = {GROUND_TOKEN}
SUPPORTED_LAYOUT_PROFILES = {"generic", "jpa", "jtwpa"}
_TEMPLATE_PATTERN = re.compile(r"\$\{([^{}]+)\}")
_TEMPLATE_EXPRESSION_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)(?:([+-])(\d+))?$")

type TopologyTuple = tuple[str, str, str, str | int]


@dataclass(frozen=True)
class ParameterSpec:
    """Expanded parameter row."""

    name: str
    default: float
    unit: str

    def as_dict(self) -> dict[str, object]:
        """Serialize the expanded parameter row for previews."""
        return {"name": self.name, "default": self.default, "unit": self.unit}


@dataclass(frozen=True)
class ComponentSpec:
    """Expanded component row."""

    name: str
    unit: str
    default: float | None = None
    value_ref: str | None = None

    def resolved_value(self, parameters: Mapping[str, ParameterSpec]) -> float:
        """Resolve the effective numeric value for simulation and previews."""
        if self.default is not None:
            return self.default
        assert self.value_ref is not None
        return parameters[self.value_ref].default

    def as_dict(self) -> dict[str, object]:
        """Serialize the expanded component row for previews."""
        payload: dict[str, object] = {"name": self.name}
        if self.default is not None:
            payload["default"] = self.default
        if self.value_ref is not None:
            payload["value_ref"] = self.value_ref
        payload["unit"] = self.unit
        return payload


@dataclass(frozen=True)
class TopologyEntry:
    """Expanded topology tuple."""

    name: str
    node1: str
    node2: str
    value_ref: str | int

    @property
    def is_port(self) -> bool:
        """Return whether this row declares a port."""
        return _infer_element_kind(self.name) == "port"

    @property
    def is_mutual_coupling(self) -> bool:
        """Return whether this row declares a coupling element."""
        return _infer_element_kind(self.name) == "mutual_coupling"

    def as_tuple(self) -> TopologyTuple:
        """Serialize the expanded topology row for previews and Julia."""
        return (self.name, self.node1, self.node2, self.value_ref)


@dataclass(frozen=True)
class RepeatContext:
    """Resolved bindings for one repeat iteration."""

    index_name: str
    index_value: int
    symbols: dict[str, int]
    series: dict[str, float]

    def render_text(self, value: str) -> str:
        """Render all supported template interpolations inside one string."""
        if "${" in value and _TEMPLATE_PATTERN.search(value) is None:
            raise ValueError(f"Invalid template syntax '{value}'.")

        def _replace(match: re.Match[str]) -> str:
            expression = match.group(1).strip()
            return self._render_expression(expression)

        rendered = _TEMPLATE_PATTERN.sub(_replace, value)
        if "${" in rendered:
            raise ValueError(f"Unsupported template syntax '{value}'.")
        return rendered

    def _render_expression(self, expression: str) -> str:
        """Render one supported template expression."""
        match = _TEMPLATE_EXPRESSION_PATTERN.fullmatch(expression)
        if match is None:
            raise ValueError(f"Unsupported template expression '{expression}'.")

        name = match.group(1)
        sign = match.group(2)
        magnitude = match.group(3)
        offset = 0 if magnitude is None else int(magnitude)
        if sign == "-":
            offset *= -1

        if name in {self.index_name, "index"}:
            return str(self.index_value + offset)
        if name in self.symbols:
            return str(self.symbols[name] + offset)
        if name in self.series:
            if sign is not None:
                raise ValueError(f"Series variable '{name}' does not support +/- offsets.")
            return str(self.series[name])
        raise ValueError(f"Unknown repeat variable '{name}'.")


@dataclass
class ExpandedCircuitDefinition:
    """Fully expanded and validated netlist used for preview and simulation."""

    name: str
    components: list[ComponentSpec]
    topology: list[TopologyEntry]
    parameters: list[ParameterSpec] = field(default_factory=list)
    _component_specs: dict[str, ComponentSpec] = field(init=False, repr=False)
    _parameter_specs: dict[str, ParameterSpec] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._component_specs = {component.name: component for component in self.components}
        self._parameter_specs = {parameter.name: parameter for parameter in self.parameters}

    @property
    def component_specs(self) -> dict[str, ComponentSpec]:
        """Return a copy of the expanded component registry."""
        return dict(self._component_specs)

    @property
    def parameter_specs(self) -> dict[str, ParameterSpec]:
        """Return a copy of the expanded parameter registry."""
        return dict(self._parameter_specs)

    @property
    def available_port_indices(self) -> list[int]:
        """Return all declared port indices in ascending order."""
        return sorted(
            int(row.value_ref) for row in self.topology if row.is_port and int(row.value_ref) >= 1
        )

    def component_spec(self, component_ref: str) -> ComponentSpec | None:
        """Look up one component specification by topology value reference."""
        return self._component_specs.get(component_ref)

    def parameter_spec(self, parameter_name: str) -> ParameterSpec | None:
        """Look up one parameter specification by name."""
        return self._parameter_specs.get(parameter_name)

    def resolve_component_value(self, component_ref: str) -> float:
        """Resolve one component value into a concrete number."""
        component = self._component_specs.get(component_ref)
        if component is None:
            raise KeyError(component_ref)
        return component.resolved_value(self._parameter_specs)

    def to_payload(self) -> dict[str, object]:
        """Serialize the expanded netlist in public preview format."""
        payload: dict[str, object] = {
            "name": self.name,
            "components": [component.as_dict() for component in self.components],
            "topology": [row.as_tuple() for row in self.topology],
        }
        if self.parameters:
            payload["parameters"] = [parameter.as_dict() for parameter in self.parameters]
        return payload


@dataclass
class CircuitDefinition:
    """Source-form circuit netlist with cached expanded form."""

    name: str
    components: list[object]
    topology: list[object]
    parameters: list[object] = field(default_factory=list)
    _expanded: ExpandedCircuitDefinition = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.name = _normalize_non_empty_name(self.name, field_name="name")
        self.components = _ensure_block_list(self.components, block_name="components")
        self.topology = _ensure_block_list(self.topology, block_name="topology")
        self.parameters = _ensure_block_list(self.parameters, block_name="parameters")
        self._expanded = _expand_circuit_definition(
            name=self.name,
            component_items=self.components,
            topology_items=self.topology,
            parameter_items=self.parameters,
        )

    @classmethod
    def model_validate(cls, payload: Mapping[str, Any]) -> CircuitDefinition:
        """Provide a Pydantic-like validation entry point used by existing callers."""
        raw = _coerce_mapping(payload)
        if "name" not in raw:
            raise ValueError("Circuit Definition must define 'name'.")
        if "components" not in raw:
            raise ValueError("Circuit Definition must define 'components'.")
        if "topology" not in raw:
            raise ValueError("Circuit Definition must define 'topology'.")
        return cls(
            name=raw["name"],
            components=raw["components"],
            topology=raw["topology"],
            parameters=raw.get("parameters", []),
        )

    @staticmethod
    def canonical_node_token(node: str | int) -> str:
        """Normalize valid ground tokens into the canonical public value."""
        node_str = str(node).strip()
        if node_str.lower() in GROUND_TOKENS:
            return GROUND_TOKEN
        return node_str

    @classmethod
    def is_ground_node(cls, node: str | int) -> bool:
        """Return whether the token represents the only supported ground node."""
        return cls.canonical_node_token(node) == GROUND_TOKEN

    @property
    def expanded_definition(self) -> ExpandedCircuitDefinition:
        """Return the shared expanded form used by preview and simulation."""
        return self._expanded

    @property
    def available_port_indices(self) -> list[int]:
        """Return declared port indices sorted ascending."""
        return self._expanded.available_port_indices

    @property
    def effective_layout_direction(self) -> str:
        """Return the stable default layout direction."""
        return DEFAULT_LAYOUT_DIRECTION

    @property
    def effective_layout_profile(self) -> str:
        """Return the inferred preview profile for the expanded netlist."""
        return self.to_ir().layout_profile

    def component_spec(self, component_ref: str) -> ComponentSpec | None:
        """Look up a component specification by topology value reference."""
        return self._expanded.component_spec(component_ref)

    @property
    def component_specs(self) -> dict[str, ComponentSpec]:
        """Return a copy of the expanded component registry."""
        return self._expanded.component_specs

    @property
    def parameter_specs(self) -> dict[str, ParameterSpec]:
        """Return a copy of the expanded parameter registry."""
        return self._expanded.parameter_specs

    def resolve_component_value(self, component_ref: str) -> float:
        """Resolve one component value to a concrete numeric value."""
        return self._expanded.resolve_component_value(component_ref)

    def to_source_payload(self) -> dict[str, object]:
        """Serialize the original source form without expanding repeat blocks."""
        payload: dict[str, object] = {
            "name": self.name,
            "components": [_clone_source_value(item) for item in self.components],
            "topology": [_clone_source_value(item) for item in self.topology],
        }
        if self.parameters:
            payload["parameters"] = [_clone_source_value(item) for item in self.parameters]
        return payload

    def _build_lowered_elements(self) -> tuple[CircuitElement, ...]:
        """Lower the expanded netlist into the internal compiler element stream."""
        elements: list[CircuitElement] = []
        for row in self._expanded.topology:
            kind = _infer_element_kind(row.name)
            elements.append(
                CircuitElement(
                    name=row.name,
                    kind=kind,
                    node1=row.node1,
                    node2=row.node2,
                    value_ref=row.value_ref,
                )
            )
        return tuple(elements)

    def _infer_layout_profile(self, elements: tuple[CircuitElement, ...]) -> str:
        """Infer a stable layout profile from the expanded element mix."""
        series_inductive = 0
        shunt_capacitive = 0
        shunt_josephson = 0

        for element in elements:
            if element.is_port or element.is_mutual_coupling:
                continue
            is_shunt = self.is_ground_node(element.node1) ^ self.is_ground_node(element.node2)
            if not is_shunt:
                if element.kind in {"inductor", "josephson_junction"}:
                    series_inductive += 1
                continue
            if element.kind == "capacitor":
                shunt_capacitive += 1
            if element.kind == "josephson_junction":
                shunt_josephson += 1

        if series_inductive >= 3 and shunt_capacitive >= 2:
            return "jtwpa"
        if self.available_port_indices and shunt_capacitive >= 1 and shunt_josephson >= 1:
            return "jpa"
        return "generic"

    def to_ir(self) -> CircuitIR:
        """Compile the expanded netlist into the stable internal representation."""
        elements = self._build_lowered_elements()
        layout_profile = self._infer_layout_profile(elements)
        if layout_profile not in SUPPORTED_LAYOUT_PROFILES:
            layout_profile = "generic"
        return CircuitIR(
            circuit_name=self.name,
            layout_direction=DEFAULT_LAYOUT_DIRECTION,
            layout_profile=layout_profile,
            available_port_indices=tuple(self.available_port_indices),
            elements=elements,
        )

    def lowered_elements(self) -> list[CircuitElement]:
        """Compatibility facade returning lowered preview/compiler elements."""
        return self.to_ir().lowered_elements()

    def lowered_topology(self) -> list[tuple[str, str, str, str | int]]:
        """Compatibility facade returning simulation tuples."""
        return compile_simulation_topology(
            self.to_ir(),
            is_ground_node=lambda node: self.is_ground_node(node),
        )


def _coerce_mapping(payload: object) -> dict[str, Any]:
    """Normalize any mapping-like payload into a Python dict."""
    if isinstance(payload, dict):
        return dict(payload)
    if isinstance(payload, Mapping):
        return dict(payload.items())
    raise TypeError("Circuit Definition must be a mapping object.")


def _parse_text_payload(payload_text: str) -> dict[str, Any]:
    """Parse editor text as Python-literal first, then JSON."""
    stripped = payload_text.strip()
    if not stripped:
        raise ValueError("Circuit Definition text is empty.")

    try:
        parsed = ast.literal_eval(stripped)
    except Exception:
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Unable to parse Circuit Definition text: {exc}") from exc

    return _coerce_mapping(parsed)


def _clone_source_value(value: object) -> object:
    """Copy nested source values so formatting helpers do not share mutable state."""
    if isinstance(value, dict):
        return {str(key): _clone_source_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(_clone_source_value(item) for item in value)
    if isinstance(value, list):
        return [_clone_source_value(item) for item in value]
    return value


def _normalize_non_empty_name(raw_value: object, *, field_name: str) -> str:
    """Normalize and validate a required non-empty string field."""
    if not isinstance(raw_value, str):
        raise ValueError(f"{field_name} must be a string.")
    value = raw_value.strip()
    if not value:
        raise ValueError(f"{field_name} must not be empty.")
    return value


def _ensure_block_list(raw_value: object, *, block_name: str) -> list[object]:
    """Validate one top-level block list."""
    if raw_value is None:
        return []
    if not isinstance(raw_value, list):
        raise ValueError(f"'{block_name}' must be a list.")
    return list(raw_value)


def _infer_element_kind(element_name: str) -> str:
    """Infer element kind from the public topology element prefix."""
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
    raise ValueError(f"Unsupported topology element prefix for '{element_name}'.")


def _normalize_node_token(raw_value: object) -> str:
    """Validate public node tokens: decimal strings only, with '0' as the only ground."""
    return validate_public_node_token(raw_value)


def _resolve_template_value(raw_value: object, context: RepeatContext | None) -> object:
    """Render template strings only when inside a repeat emit block."""
    if not isinstance(raw_value, str):
        return raw_value
    if "${" not in raw_value:
        return raw_value
    if context is None:
        raise ValueError("Template interpolation is only supported inside repeat emit rows.")
    return context.render_text(raw_value)


def _resolve_float(raw_value: object, context: RepeatContext | None, *, field_name: str) -> float:
    """Resolve a numeric literal or templated numeric string to float."""
    value = _resolve_template_value(raw_value, context)
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be numeric.")
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be numeric.") from exc
    raise ValueError(f"{field_name} must be numeric.")


def _parse_repeat_context(
    repeat_raw: Mapping[str, Any],
) -> tuple[int, str, int, dict[str, Any], dict[str, Any], list[object]]:
    """Validate the shape of one repeat block and return normalized fields."""
    allowed_keys = {"count", "index", "start", "symbols", "series", "emit"}
    unknown_keys = set(repeat_raw) - allowed_keys
    if unknown_keys:
        unknown_list = ", ".join(sorted(unknown_keys))
        raise ValueError(f"Unsupported repeat keys: {unknown_list}.")

    count_raw = repeat_raw.get("count")
    if not isinstance(count_raw, int) or isinstance(count_raw, bool) or count_raw <= 0:
        raise ValueError("repeat.count must be a positive integer.")
    count = count_raw

    index_name = _normalize_non_empty_name(repeat_raw.get("index"), field_name="repeat.index")

    start_raw = repeat_raw.get("start", 0)
    if not isinstance(start_raw, int) or isinstance(start_raw, bool):
        raise ValueError("repeat.start must be an integer.")
    start = start_raw

    symbols_raw = repeat_raw.get("symbols", {})
    if not isinstance(symbols_raw, Mapping):
        raise ValueError("repeat.symbols must be a mapping when provided.")
    series_raw = repeat_raw.get("series", {})
    if not isinstance(series_raw, Mapping):
        raise ValueError("repeat.series must be a mapping when provided.")

    emit_raw = repeat_raw.get("emit")
    if not isinstance(emit_raw, list) or not emit_raw:
        raise ValueError("repeat.emit must be a non-empty list.")

    return (count, index_name, start, dict(symbols_raw), dict(series_raw), list(emit_raw))


def _build_repeat_iteration_context(
    *,
    index_name: str,
    index_value: int,
    offset: int,
    symbols_raw: Mapping[str, Any],
    series_raw: Mapping[str, Any],
) -> RepeatContext:
    """Resolve all symbol/series bindings for one repeat iteration."""
    symbol_values: dict[str, int] = {}
    for symbol_name, symbol_spec_raw in symbols_raw.items():
        normalized_symbol_name = _normalize_non_empty_name(
            symbol_name,
            field_name="repeat.symbols key",
        )
        symbol_spec = _coerce_mapping(symbol_spec_raw)
        base_raw = symbol_spec.get("base")
        step_raw = symbol_spec.get("step")
        if not isinstance(base_raw, int) or isinstance(base_raw, bool):
            raise ValueError(f"repeat.symbols.{normalized_symbol_name}.base must be an integer.")
        if not isinstance(step_raw, int) or isinstance(step_raw, bool):
            raise ValueError(f"repeat.symbols.{normalized_symbol_name}.step must be an integer.")
        symbol_values[normalized_symbol_name] = base_raw + (step_raw * offset)

    series_values: dict[str, float] = {}
    for series_name, series_spec_raw in series_raw.items():
        normalized_series_name = _normalize_non_empty_name(
            series_name,
            field_name="repeat.series key",
        )
        series_spec = _coerce_mapping(series_spec_raw)
        base_raw = series_spec.get("base")
        step_raw = series_spec.get("step")
        if isinstance(base_raw, bool) or not isinstance(base_raw, int | float):
            raise ValueError(f"repeat.series.{normalized_series_name}.base must be numeric.")
        if isinstance(step_raw, bool) or not isinstance(step_raw, int | float):
            raise ValueError(f"repeat.series.{normalized_series_name}.step must be numeric.")
        series_values[normalized_series_name] = float(base_raw) + (float(step_raw) * offset)

    return RepeatContext(
        index_name=index_name,
        index_value=index_value,
        symbols=symbol_values,
        series=series_values,
    )


def _is_repeat_row(raw_item: object) -> bool:
    """Return whether a block item is a repeat wrapper row."""
    return isinstance(raw_item, Mapping) and "repeat" in raw_item


def _expand_parameter_row(raw_item: object, context: RepeatContext | None) -> ParameterSpec:
    """Expand one explicit parameter row."""
    if not isinstance(raw_item, Mapping):
        raise ValueError("parameters rows must be mappings or repeat blocks.")
    row = _coerce_mapping(raw_item)
    if "repeat" in row:
        raise ValueError("Nested repeat blocks are not supported.")

    name = _normalize_non_empty_name(
        _resolve_template_value(row.get("name"), context),
        field_name="parameters[*].name",
    )
    unit = _normalize_non_empty_name(
        _resolve_template_value(row.get("unit"), context),
        field_name=f"Parameter '{name}' unit",
    )
    default = _resolve_float(
        row.get("default"),
        context,
        field_name=f"Parameter '{name}' default",
    )
    return ParameterSpec(name=name, default=default, unit=unit)


def _expand_component_row(raw_item: object, context: RepeatContext | None) -> ComponentSpec:
    """Expand one explicit component row."""
    if not isinstance(raw_item, Mapping):
        raise ValueError("components rows must be mappings or repeat blocks.")
    row = _coerce_mapping(raw_item)
    if "repeat" in row:
        raise ValueError("Nested repeat blocks are not supported.")

    name = _normalize_non_empty_name(
        _resolve_template_value(row.get("name"), context),
        field_name="components[*].name",
    )
    unit = _normalize_non_empty_name(
        _resolve_template_value(row.get("unit"), context),
        field_name=f"Component '{name}' unit",
    )

    has_default = "default" in row
    has_value_ref = "value_ref" in row
    if has_default == has_value_ref:
        raise ValueError(f"Component '{name}' must define exactly one of 'default' or 'value_ref'.")

    if has_default:
        default = _resolve_float(
            row["default"],
            context,
            field_name=f"Component '{name}' default",
        )
        return ComponentSpec(name=name, unit=unit, default=default)

    value_ref = _normalize_non_empty_name(
        _resolve_template_value(row["value_ref"], context),
        field_name=f"Component '{name}' value_ref",
    )
    return ComponentSpec(name=name, unit=unit, value_ref=value_ref)


def _expand_topology_row(raw_item: object, context: RepeatContext | None) -> TopologyEntry:
    """Expand one explicit topology row."""
    if isinstance(raw_item, Mapping):
        if "repeat" in raw_item:
            raise ValueError("Nested repeat blocks are not supported.")
        raise ValueError("topology rows must be 4-item tuples/lists or repeat blocks.")
    if not isinstance(raw_item, Sequence) or isinstance(raw_item, str | bytes):
        raise ValueError("topology rows must be 4-item tuples/lists or repeat blocks.")

    values = list(raw_item)
    if len(values) != 4:
        raise ValueError("topology rows must contain exactly 4 items.")

    name = _normalize_non_empty_name(
        _resolve_template_value(values[0], context),
        field_name="topology[*][0]",
    )
    kind = _infer_element_kind(name)

    if kind == "mutual_coupling":
        node1 = _normalize_non_empty_name(
            _resolve_template_value(values[1], context),
            field_name=f"Mutual coupling '{name}' first inductor reference",
        )
        node2 = _normalize_non_empty_name(
            _resolve_template_value(values[2], context),
            field_name=f"Mutual coupling '{name}' second inductor reference",
        )
        value_ref = _normalize_non_empty_name(
            _resolve_template_value(values[3], context),
            field_name=f"Mutual coupling '{name}' value_ref",
        )
        return TopologyEntry(name=name, node1=node1, node2=node2, value_ref=value_ref)

    node1 = _normalize_node_token(_resolve_template_value(values[1], context))
    node2 = _normalize_node_token(_resolve_template_value(values[2], context))

    if kind == "port":
        port_index = values[3]
        if not isinstance(port_index, int) or isinstance(port_index, bool):
            raise ValueError(f"Port '{name}' must use an integer port index.")
        return TopologyEntry(name=name, node1=node1, node2=node2, value_ref=int(port_index))

    value_ref = _normalize_non_empty_name(
        _resolve_template_value(values[3], context),
        field_name=f"Topology row '{name}' value_ref",
    )
    return TopologyEntry(name=name, node1=node1, node2=node2, value_ref=value_ref)


def _expand_block_items[T](
    raw_items: list[object],
    *,
    block_name: str,
    expand_row: Callable[[object, RepeatContext | None], T],
) -> list[T]:
    """Expand one top-level block containing explicit rows and repeat blocks."""
    expanded: list[T] = []
    for raw_item in raw_items:
        if not _is_repeat_row(raw_item):
            expanded.append(expand_row(raw_item, None))
            continue

        repeat_wrapper = _coerce_mapping(raw_item)
        repeat_raw = _coerce_mapping(repeat_wrapper["repeat"])
        count, index_name, start, symbols_raw, series_raw, emit_rows = _parse_repeat_context(
            repeat_raw
        )

        for offset in range(count):
            index_value = start + offset
            context = _build_repeat_iteration_context(
                index_name=index_name,
                index_value=index_value,
                offset=offset,
                symbols_raw=symbols_raw,
                series_raw=series_raw,
            )
            for emit_row in emit_rows:
                if _is_repeat_row(emit_row):
                    raise ValueError("Nested repeat blocks are not supported.")
                expanded.append(expand_row(emit_row, context))
    return expanded


def _validate_expanded_circuit(expanded: ExpandedCircuitDefinition) -> None:
    """Validate expanded cross-references after repeat expansion."""
    parameter_specs = expanded.parameter_specs
    component_specs = expanded.component_specs

    seen_parameter_names: set[str] = set()
    for parameter in expanded.parameters:
        if parameter.name in seen_parameter_names:
            raise ValueError(f"Duplicate parameter name '{parameter.name}'.")
        seen_parameter_names.add(parameter.name)

    seen_component_names: set[str] = set()
    for component in expanded.components:
        if component.name in seen_component_names:
            raise ValueError(f"Duplicate component name '{component.name}'.")
        if component.value_ref is not None:
            parameter = parameter_specs.get(component.value_ref)
            if parameter is None:
                raise ValueError(
                    f"Component '{component.name}' references undefined parameter "
                    f"'{component.value_ref}'."
                )
            if parameter.unit != component.unit:
                raise ValueError(
                    f"Component '{component.name}' unit '{component.unit}' does not match "
                    f"parameter '{parameter.name}' unit '{parameter.unit}'."
                )
        seen_component_names.add(component.name)

    seen_topology_names: set[str] = set()
    seen_port_indices: set[int] = set()
    element_kind_by_name: dict[str, str] = {}

    for row in expanded.topology:
        if row.name in seen_topology_names:
            raise ValueError(f"Duplicate topology element name '{row.name}'.")
        seen_topology_names.add(row.name)
        row_kind = _infer_element_kind(row.name)
        element_kind_by_name[row.name] = row_kind

        if row_kind == "port":
            port_index = validate_port_row_contract(
                row_name=row.name,
                node1=row.node1,
                node2=row.node2,
                value_ref=row.value_ref,
                seen_port_indices=seen_port_indices,
                is_ground_node=CircuitDefinition.is_ground_node,
            )
            seen_port_indices.add(port_index)
            continue

        if row_kind == "mutual_coupling":
            validate_mutual_coupling_component_reference(
                row_name=row.name,
                value_ref=row.value_ref,
                component_specs=component_specs,
            )
            continue

        validate_topology_component_reference(
            row_name=row.name,
            value_ref=row.value_ref,
            component_specs=component_specs,
        )

    for row in expanded.topology:
        if not row.is_mutual_coupling:
            continue
        validate_mutual_coupling_inductive_references(
            row_name=row.name,
            first_ref=row.node1,
            second_ref=row.node2,
            element_kind_by_name=element_kind_by_name,
        )


def _expand_circuit_definition(
    *,
    name: str,
    component_items: list[object],
    topology_items: list[object],
    parameter_items: list[object],
) -> ExpandedCircuitDefinition:
    """Expand all repeat blocks, then validate the resulting netlist."""
    expanded_parameters = _expand_block_items(
        parameter_items,
        block_name="parameters",
        expand_row=_expand_parameter_row,
    )
    expanded_components = _expand_block_items(
        component_items,
        block_name="components",
        expand_row=_expand_component_row,
    )
    expanded_topology = _expand_block_items(
        topology_items,
        block_name="topology",
        expand_row=_expand_topology_row,
    )

    expanded = ExpandedCircuitDefinition(
        name=name,
        components=expanded_components,
        topology=expanded_topology,
        parameters=expanded_parameters,
    )
    _validate_expanded_circuit(expanded)
    return expanded


def parse_circuit_definition_source(
    payload: str | Mapping[str, Any] | CircuitDefinition,
) -> CircuitDefinition:
    """Parse source text or a mapping into a validated source-form circuit definition."""
    if isinstance(payload, CircuitDefinition):
        return payload

    raw = _parse_text_payload(payload) if isinstance(payload, str) else _coerce_mapping(payload)
    return CircuitDefinition.model_validate(raw)


def expand_circuit_definition(
    payload: str | Mapping[str, Any] | CircuitDefinition,
) -> ExpandedCircuitDefinition:
    """Return the expanded form for any supported circuit-definition input."""
    return parse_circuit_definition_source(payload).expanded_definition


def format_circuit_definition(circuit: CircuitDefinition | ExpandedCircuitDefinition) -> str:
    """Render either source form or expanded form using stable Python-literal formatting."""
    payload = (
        circuit.to_source_payload()
        if isinstance(circuit, CircuitDefinition)
        else circuit.to_payload()
    )
    return pprint.pformat(payload, sort_dicts=False, width=100)


def format_expanded_circuit_definition(
    payload: CircuitDefinition | ExpandedCircuitDefinition,
) -> str:
    """Render the expanded netlist preview used by Schema Editor and Simulation."""
    expanded = (
        payload if isinstance(payload, ExpandedCircuitDefinition) else payload.expanded_definition
    )
    return pprint.pformat(expanded.to_payload(), sort_dicts=False, width=100)


class FrequencyRange(BaseModel):
    """Frequency sweep configuration."""

    start_ghz: float = Field(description="Start frequency in GHz")
    stop_ghz: float = Field(description="Stop frequency in GHz")
    points: int = Field(default=1000, description="Number of frequency points")


class DriveSourceConfig(BaseModel):
    """Single hbsolve source specification."""

    pump_freq_ghz: float = Field(default=5.0, description="Pump frequency for this source (GHz).")
    port: int = Field(default=1, description="Source port index.")
    current_amp: float = Field(default=0.0, description="Source current amplitude in A.")
    mode_components: tuple[int, ...] | None = Field(
        default=None,
        description=(
            "Explicit hbsolve mode tuple for this source. "
            "Use (0,) for DC, (1,) for the first pump tone, or (1, 0)/(0, 1) for multi-pump."
        ),
    )


class SimulationConfig(BaseModel):
    """Configuration for hbsolve simulation."""

    pump_freq_ghz: float = Field(default=5.0, description="Pump frequency in GHz")
    pump_current_amp: float = Field(
        default=0.0,
        description="Legacy single-source current amplitude in A (used when sources is empty).",
    )
    pump_port: int = Field(
        default=1,
        description="Legacy single-source port index (used when sources is empty).",
    )
    pump_mode_index: int = Field(
        default=1,
        description="Legacy single-source mode index (used when sources is empty).",
    )
    n_modulation_harmonics: int = Field(default=10, description="Number of modulation harmonics")
    n_pump_harmonics: int = Field(default=20, description="Number of pump harmonics")
    sources: list[DriveSourceConfig] | None = Field(
        default=None,
        description=(
            "Drive source list passed to hbsolve. If omitted, a single legacy source "
            "(pump_freq_ghz, pump_port, pump_current_amp) is used."
        ),
    )
    include_dc: bool = Field(default=False, description="Include DC term in harmonic solve")
    enable_three_wave_mixing: bool = Field(default=False, description="Enable 3-wave mixing")
    enable_four_wave_mixing: bool = Field(default=True, description="Enable 4-wave mixing")
    max_intermod_order: int | None = Field(
        default=None,
        description="Maximum intermodulation order (None means infinite).",
    )
    max_iterations: int = Field(default=1000, description="Maximum nonlinear solver iterations")
    f_tol: float = Field(default=1e-8, description="Nonlinear solver tolerance")
    line_search_switch_tol: float = Field(
        default=1e-5,
        description="Switch-off line search tolerance",
    )
    alpha_min: float = Field(default=1e-4, description="Minimum line-search alpha")


class SimulationResult(BaseModel):
    """Result from a circuit simulation."""

    frequencies_ghz: list[float] = Field(description="Frequency points in GHz")
    s11_real: list[float] = Field(description="Real part of S11")
    s11_imag: list[float] = Field(description="Imaginary part of S11")
    port_indices: list[int] = Field(
        default_factory=lambda: [1],
        description="Available simulated port indices.",
    )
    s_parameter_real: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Real-part traces keyed by zero-mode S-parameter label (for example S21).",
    )
    s_parameter_imag: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Imag-part traces keyed by zero-mode S-parameter label (for example S21).",
    )
    mode_indices: list[tuple[int, ...]] = Field(
        default_factory=lambda: [(0,)],
        description="Available signal/idler mode tuples reported by hbsolve.",
    )
    s_parameter_mode_real: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Real-part traces keyed by mode-aware S-parameter label.",
    )
    s_parameter_mode_imag: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Imag-part traces keyed by mode-aware S-parameter label.",
    )
    z_parameter_mode_real: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Real-part traces keyed by mode-aware native Z-parameter label.",
    )
    z_parameter_mode_imag: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Imag-part traces keyed by mode-aware native Z-parameter label.",
    )
    y_parameter_mode_real: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Real-part traces keyed by mode-aware Y-parameter label.",
    )
    y_parameter_mode_imag: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Imag-part traces keyed by mode-aware Y-parameter label.",
    )
    qe_parameter_mode: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Mode-aware QE traces keyed by output/input mode+port label.",
    )
    qe_ideal_parameter_mode: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Mode-aware QEideal traces keyed by output/input mode+port label.",
    )
    cm_parameter_mode: dict[str, list[float]] = Field(
        default_factory=dict,
        description="Mode-aware commutation traces keyed by output mode+port label.",
    )

    def _resolved_s_parameter_real(self) -> dict[str, list[float]]:
        """Return the real-part trace map with a guaranteed S11 fallback."""
        return self.s_parameter_real or {"S11": self.s11_real}

    def _resolved_s_parameter_imag(self) -> dict[str, list[float]]:
        """Return the imag-part trace map with a guaranteed S11 fallback."""
        return self.s_parameter_imag or {"S11": self.s11_imag}

    @staticmethod
    def normalize_mode(mode: tuple[int, ...] | list[int]) -> tuple[int, ...]:
        """Normalize any mode sequence to a canonical tuple of ints."""
        normalized = tuple(int(value) for value in mode)
        return normalized or (0,)

    @classmethod
    def mode_token(cls, mode: tuple[int, ...] | list[int]) -> str:
        """Encode a mode tuple into a stable string token."""
        normalized = cls.normalize_mode(mode)
        return ",".join(str(value) for value in normalized)

    @classmethod
    def parse_mode_token(cls, token: str) -> tuple[int, ...]:
        """Decode a canonical mode token back into a tuple."""
        cleaned = str(token).strip()
        if not cleaned:
            return (0,)
        return cls.normalize_mode(tuple(int(part.strip()) for part in cleaned.split(",")))

    @property
    def available_port_indices(self) -> list[int]:
        """Return sorted available ports, derived from traces when not explicitly set."""
        normalized = sorted({int(port) for port in self.port_indices if int(port) >= 1})
        if normalized:
            return normalized

        detected_ports: set[int] = set()
        for label in self._resolved_s_parameter_real():
            parsed = self._parse_s_parameter_label(label)
            if parsed is None:
                continue
            detected_ports.update(parsed)
        return sorted(detected_ports) or [1]

    @property
    def available_mode_indices(self) -> list[tuple[int, ...]]:
        """Return sorted available signal/idler mode tuples."""

        def _mode_sort_key(mode: tuple[int, ...]) -> tuple[int, int, tuple[int, ...]]:
            return (0 if all(value == 0 for value in mode) else 1, sum(abs(v) for v in mode), mode)

        if self.mode_indices:
            unique_modes = {self.normalize_mode(mode) for mode in self.mode_indices}
            return sorted(unique_modes, key=_mode_sort_key)

        detected_modes: set[tuple[int, ...]] = set()
        for label in self.s_parameter_mode_real:
            parsed = self._parse_mode_trace_label(label)
            if parsed is None:
                continue
            output_mode, _, input_mode, _ = parsed
            detected_modes.add(output_mode)
            detected_modes.add(input_mode)
        return sorted(detected_modes, key=_mode_sort_key) or [(0,)]

    @property
    def available_s_parameter_labels(self) -> list[str]:
        """Return sorted available zero-mode S-parameter labels."""
        labels = set(self._resolved_s_parameter_real()) & set(self._resolved_s_parameter_imag())
        return sorted(labels) or ["S11"]

    @property
    def available_mode_s_parameter_labels(self) -> list[str]:
        """Return sorted available mode-aware S-parameter labels."""
        labels = set(self._resolved_mode_s_parameter_real()) & set(
            self._resolved_mode_s_parameter_imag()
        )
        return sorted(labels)

    @property
    def available_mode_z_parameter_labels(self) -> list[str]:
        """Return sorted available mode-aware native Z-parameter labels."""
        labels = set(self.z_parameter_mode_real) & set(self.z_parameter_mode_imag)
        return sorted(labels)

    @property
    def available_mode_y_parameter_labels(self) -> list[str]:
        """Return sorted available mode-aware Y-parameter labels."""
        labels = set(self.y_parameter_mode_real) & set(self.y_parameter_mode_imag)
        return sorted(labels)

    @property
    def available_mode_qe_labels(self) -> list[str]:
        """Return sorted available mode-aware QE labels."""
        return sorted(self.qe_parameter_mode)

    @property
    def available_mode_qe_ideal_labels(self) -> list[str]:
        """Return sorted available mode-aware QEideal labels."""
        return sorted(self.qe_ideal_parameter_mode)

    @property
    def available_mode_cm_labels(self) -> list[str]:
        """Return sorted available mode-aware CM labels."""
        return sorted(self.cm_parameter_mode)

    @staticmethod
    def _parse_s_parameter_label(label: str) -> tuple[int, int] | None:
        """Parse labels like S21 into (output_port, input_port)."""
        if not label.startswith("S"):
            return None
        digits = label[1:]
        if len(digits) != 2 or not digits.isdigit():
            return None
        output_port = int(digits[0])
        input_port = int(digits[1])
        if output_port < 1 or input_port < 1:
            return None
        return (output_port, input_port)

    @staticmethod
    def _trace_label(output_port: int, input_port: int) -> str:
        """Build the canonical zero-mode trace label."""
        return f"S{int(output_port)}{int(input_port)}"

    @classmethod
    def _mode_trace_label(
        cls,
        output_mode: tuple[int, ...] | list[int],
        output_port: int,
        input_mode: tuple[int, ...] | list[int],
        input_port: int,
    ) -> str:
        """Build the canonical mode-aware trace label."""
        return (
            f"om={cls.mode_token(output_mode)}|op={int(output_port)}|"
            f"im={cls.mode_token(input_mode)}|ip={int(input_port)}"
        )

    @classmethod
    def _parse_mode_trace_label(
        cls,
        label: str,
    ) -> tuple[tuple[int, ...], int, tuple[int, ...], int] | None:
        """Parse a mode-aware trace label into output/input modes and ports."""
        parts = str(label).split("|")
        if len(parts) != 4:
            return None
        try:
            part_map = {
                segment.split("=", maxsplit=1)[0]: segment.split("=", maxsplit=1)[1]
                for segment in parts
            }
            output_mode = cls.parse_mode_token(part_map["om"])
            output_port = int(part_map["op"])
            input_mode = cls.parse_mode_token(part_map["im"])
            input_port = int(part_map["ip"])
        except (KeyError, ValueError, IndexError):
            return None
        return (output_mode, output_port, input_mode, input_port)

    @classmethod
    def _cm_trace_label(
        cls,
        output_mode: tuple[int, ...] | list[int],
        output_port: int,
    ) -> str:
        """Build the canonical mode-aware CM label."""
        return f"om={cls.mode_token(output_mode)}|op={int(output_port)}"

    @classmethod
    def _parse_cm_trace_label(cls, label: str) -> tuple[tuple[int, ...], int] | None:
        """Parse a mode-aware commutation label."""
        parts = str(label).split("|")
        if len(parts) != 2:
            return None
        try:
            part_map = {
                segment.split("=", maxsplit=1)[0]: segment.split("=", maxsplit=1)[1]
                for segment in parts
            }
            output_mode = cls.parse_mode_token(part_map["om"])
            output_port = int(part_map["op"])
        except (KeyError, ValueError, IndexError):
            return None
        return (output_mode, output_port)

    def _resolved_mode_s_parameter_real(self) -> dict[str, list[float]]:
        """Return the mode-aware real-part S map with a zero-mode fallback."""
        if self.s_parameter_mode_real:
            return self.s_parameter_mode_real

        zero_mode = (0,)
        return {
            self._mode_trace_label(zero_mode, output_port, zero_mode, input_port): (
                self.get_s_parameter_real(output_port, input_port)
            )
            for output_port in self.available_port_indices
            for input_port in self.available_port_indices
            if self._trace_label(output_port, input_port) in self.available_s_parameter_labels
        }

    def _resolved_mode_s_parameter_imag(self) -> dict[str, list[float]]:
        """Return the mode-aware imag-part S map with a zero-mode fallback."""
        if self.s_parameter_mode_imag:
            return self.s_parameter_mode_imag

        zero_mode = (0,)
        return {
            self._mode_trace_label(zero_mode, output_port, zero_mode, input_port): (
                self.get_s_parameter_imag(output_port, input_port)
            )
            for output_port in self.available_port_indices
            for input_port in self.available_port_indices
            if self._trace_label(output_port, input_port) in self.available_s_parameter_labels
        }

    def get_s_parameter_real(self, output_port: int = 1, input_port: int = 1) -> list[float]:
        """Return the real part of the requested zero-mode S-parameter."""
        label = self._trace_label(output_port, input_port)
        return self.get_s_parameter_real_by_label(label)

    def get_s_parameter_real_by_label(self, label: str) -> list[float]:
        """Return the real part of a zero-mode S-parameter by canonical label."""
        trace_map = self._resolved_s_parameter_real()
        if label in trace_map:
            return trace_map[label]
        if label == "S11":
            return self.s11_real
        raise KeyError(f"S-parameter trace '{label}' is not available.")

    def get_s_parameter_imag(self, output_port: int = 1, input_port: int = 1) -> list[float]:
        """Return the imaginary part of the requested zero-mode S-parameter."""
        label = self._trace_label(output_port, input_port)
        return self.get_s_parameter_imag_by_label(label)

    def get_s_parameter_imag_by_label(self, label: str) -> list[float]:
        """Return the imaginary part of a zero-mode S-parameter by canonical label."""
        trace_map = self._resolved_s_parameter_imag()
        if label in trace_map:
            return trace_map[label]
        if label == "S11":
            return self.s11_imag
        raise KeyError(f"S-parameter trace '{label}' is not available.")

    def get_s_parameter_complex(
        self,
        output_port: int = 1,
        input_port: int = 1,
    ) -> list[complex]:
        """Return the requested complex zero-mode S-parameter trace."""
        return self.get_mode_s_parameter_complex((0,), output_port, (0,), input_port)

    def get_mode_s_parameter_real(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Return the real part of the requested mode-aware S-parameter."""
        label = self._mode_trace_label(output_mode, output_port, input_mode, input_port)
        trace_map = self._resolved_mode_s_parameter_real()
        if label in trace_map:
            return trace_map[label]
        raise KeyError(f"Mode-aware S trace '{label}' is not available.")

    def get_mode_s_parameter_imag(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Return the imaginary part of the requested mode-aware S-parameter."""
        label = self._mode_trace_label(output_mode, output_port, input_mode, input_port)
        trace_map = self._resolved_mode_s_parameter_imag()
        if label in trace_map:
            return trace_map[label]
        raise KeyError(f"Mode-aware S trace '{label}' is not available.")

    def get_mode_s_parameter_complex(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[complex]:
        """Return the requested complex mode-aware S-parameter trace."""
        return [
            complex(r, i)
            for r, i in zip(
                self.get_mode_s_parameter_real(output_mode, output_port, input_mode, input_port),
                self.get_mode_s_parameter_imag(output_mode, output_port, input_mode, input_port),
                strict=False,
            )
        ]

    def get_s_parameter_magnitude(
        self,
        output_port: int = 1,
        input_port: int = 1,
    ) -> list[float]:
        """Calculate |Sij| for the selected trace."""
        return self.get_mode_s_parameter_magnitude((0,), output_port, (0,), input_port)

    def get_mode_s_parameter_magnitude(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Calculate |S| for the selected mode-aware trace."""
        return [
            math.sqrt(r**2 + i**2)
            for r, i in zip(
                self.get_mode_s_parameter_real(output_mode, output_port, input_mode, input_port),
                self.get_mode_s_parameter_imag(output_mode, output_port, input_mode, input_port),
                strict=False,
            )
        ]

    def get_s_parameter_db(
        self,
        output_port: int = 1,
        input_port: int = 1,
    ) -> list[float]:
        """Calculate 20*log10(|Sij|) for the selected trace."""
        return self.get_mode_s_parameter_db((0,), output_port, (0,), input_port)

    def get_mode_s_parameter_db(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Calculate 20*log10(|S|) for the selected mode-aware trace."""
        values: list[float] = []
        for magnitude in self.get_mode_s_parameter_magnitude(
            output_mode,
            output_port,
            input_mode,
            input_port,
        ):
            values.append(20.0 * math.log10(max(magnitude, 1e-15)))
        return values

    def get_s_parameter_phase_deg(
        self,
        output_port: int = 1,
        input_port: int = 1,
    ) -> list[float]:
        """Calculate phase(Sij) in degrees."""
        return self.get_mode_s_parameter_phase_deg((0,), output_port, (0,), input_port)

    def get_mode_s_parameter_phase_deg(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Calculate phase(S) in degrees for the selected mode-aware trace."""
        return [
            math.degrees(math.atan2(i, r))
            for r, i in zip(
                self.get_mode_s_parameter_real(output_mode, output_port, input_mode, input_port),
                self.get_mode_s_parameter_imag(output_mode, output_port, input_mode, input_port),
                strict=False,
            )
        ]

    def get_gain_linear(self, output_port: int = 1, input_port: int = 1) -> list[float]:
        """Calculate power gain as |Sij|^2."""
        return self.get_mode_gain_linear((0,), output_port, (0,), input_port)

    def get_mode_gain_linear(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Calculate power gain as |S|^2 for the selected mode-aware trace."""
        magnitudes = self.get_mode_s_parameter_magnitude(
            output_mode,
            output_port,
            input_mode,
            input_port,
        )
        return [magnitude**2 for magnitude in magnitudes]

    def get_gain_db(self, output_port: int = 1, input_port: int = 1) -> list[float]:
        """Calculate gain in dB as 10*log10(|Sij|^2)."""
        return self.get_mode_gain_db((0,), output_port, (0,), input_port)

    def get_mode_gain_db(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Calculate gain in dB as 10*log10(|S|^2) for the selected mode-aware trace."""
        values: list[float] = []
        for gain in self.get_mode_gain_linear(output_mode, output_port, input_mode, input_port):
            values.append(10.0 * math.log10(max(gain, 1e-30)))
        return values

    def _get_mode_complex_trace(
        self,
        *,
        real_map: dict[str, list[float]],
        imag_map: dict[str, list[float]],
        label: str,
        family_name: str,
    ) -> list[complex]:
        """Resolve a complex-valued mode-aware trace from parallel real/imag maps."""
        if label not in real_map or label not in imag_map:
            raise KeyError(f"Mode-aware {family_name} trace '{label}' is not available.")
        return [complex(r, i) for r, i in zip(real_map[label], imag_map[label], strict=False)]

    def get_mode_z_parameter_complex(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[complex]:
        """Return the native mode-aware Z-parameter trace."""
        label = self._mode_trace_label(output_mode, output_port, input_mode, input_port)
        return self._get_mode_complex_trace(
            real_map=self.z_parameter_mode_real,
            imag_map=self.z_parameter_mode_imag,
            label=label,
            family_name="Z",
        )

    def get_mode_y_parameter_complex(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[complex]:
        """Return the mode-aware Y-parameter trace."""
        label = self._mode_trace_label(output_mode, output_port, input_mode, input_port)
        return self._get_mode_complex_trace(
            real_map=self.y_parameter_mode_real,
            imag_map=self.y_parameter_mode_imag,
            label=label,
            family_name="Y",
        )

    def get_mode_qe(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Return the mode-aware QE trace."""
        label = self._mode_trace_label(output_mode, output_port, input_mode, input_port)
        if label in self.qe_parameter_mode:
            return self.qe_parameter_mode[label]
        raise KeyError(f"Mode-aware QE trace '{label}' is not available.")

    def get_mode_qe_ideal(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
        input_mode: tuple[int, ...] | list[int] = (0,),
        input_port: int = 1,
    ) -> list[float]:
        """Return the mode-aware ideal QE trace."""
        label = self._mode_trace_label(output_mode, output_port, input_mode, input_port)
        if label in self.qe_ideal_parameter_mode:
            return self.qe_ideal_parameter_mode[label]
        raise KeyError(f"Mode-aware QEideal trace '{label}' is not available.")

    def get_mode_cm(
        self,
        output_mode: tuple[int, ...] | list[int] = (0,),
        output_port: int = 1,
    ) -> list[float]:
        """Return the mode-aware commutation trace."""
        label = self._cm_trace_label(output_mode, output_port)
        if label in self.cm_parameter_mode:
            return self.cm_parameter_mode[label]
        raise KeyError(f"Mode-aware CM trace '{label}' is not available.")

    @property
    def s11_complex(self) -> list[complex]:
        """Return complex S11 values."""
        return self.get_s_parameter_complex(1, 1)

    @property
    def s11_magnitude(self) -> list[float]:
        """Calculate |S11| magnitude."""
        return self.get_s_parameter_magnitude(1, 1)

    @property
    def s11_db(self) -> list[float]:
        """Calculate 20*log10(|S11|)."""
        return self.get_s_parameter_db(1, 1)

    @property
    def s11_phase_deg(self) -> list[float]:
        """Calculate S11 phase in degrees."""
        return self.get_s_parameter_phase_deg(1, 1)

    @property
    def return_gain_linear(self) -> list[float]:
        """Calculate return gain as |S11|^2."""
        return self.get_gain_linear(1, 1)

    @property
    def return_gain_db(self) -> list[float]:
        """Calculate return gain in dB as 10*log10(|S11|^2)."""
        return self.get_gain_db(1, 1)

    def calculate_input_impedance_ohm(
        self,
        reference_impedance_ohm: float = 50.0,
        port: int = 1,
    ) -> list[complex]:
        """Convert Sii to input impedance using a real reference impedance."""
        try:
            return self.get_mode_z_parameter_complex((0,), port, (0,), port)
        except KeyError:
            pass

        epsilon = 1e-12
        values: list[complex] = []

        for s11 in self.get_s_parameter_complex(port, port):
            denominator = 1.0 - s11
            if abs(denominator) <= epsilon:
                values.append(complex(float("nan"), float("nan")))
                continue
            values.append(reference_impedance_ohm * ((1.0 + s11) / denominator))

        return values

    def calculate_input_admittance_s(
        self,
        reference_impedance_ohm: float = 50.0,
        port: int = 1,
    ) -> list[complex]:
        """Convert Sii to input admittance using a real reference impedance."""
        try:
            return self.get_mode_y_parameter_complex((0,), port, (0,), port)
        except KeyError:
            pass

        epsilon = 1e-18
        values: list[complex] = []

        for impedance in self.calculate_input_impedance_ohm(
            reference_impedance_ohm,
            port=port,
        ):
            if not (impedance.real == impedance.real and impedance.imag == impedance.imag):
                values.append(complex(float("nan"), float("nan")))
                continue
            if abs(impedance) <= epsilon:
                values.append(complex(float("nan"), float("nan")))
                continue
            values.append(1.0 / impedance)

        return values
