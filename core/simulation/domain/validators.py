"""Shared validators for circuit-netlist topology/runtime contracts."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from enum import StrEnum


class CircuitValidationCode(StrEnum):
    """Stable machine-readable error codes for circuit validation failures."""

    INVALID_NODE_TOKEN = "INVALID_NODE_TOKEN"
    UNSUPPORTED_GROUND_ALIAS = "UNSUPPORTED_GROUND_ALIAS"
    PORT_INDEX_NOT_INTEGER = "PORT_INDEX_NOT_INTEGER"
    DUPLICATE_PORT_INDEX = "DUPLICATE_PORT_INDEX"
    PORT_GROUND_TOPOLOGY = "PORT_GROUND_TOPOLOGY"
    TOPOLOGY_COMPONENT_REFERENCE_INVALID = "TOPOLOGY_COMPONENT_REFERENCE_INVALID"
    TOPOLOGY_COMPONENT_REFERENCE_UNDEFINED = "TOPOLOGY_COMPONENT_REFERENCE_UNDEFINED"
    MUTUAL_COUPLING_COMPONENT_REFERENCE_INVALID = "MUTUAL_COUPLING_COMPONENT_REFERENCE_INVALID"
    MUTUAL_COUPLING_COMPONENT_REFERENCE_UNDEFINED = "MUTUAL_COUPLING_COMPONENT_REFERENCE_UNDEFINED"
    MUTUAL_COUPLING_ELEMENT_NON_INDUCTIVE = "MUTUAL_COUPLING_ELEMENT_NON_INDUCTIVE"


class CircuitValidationError(ValueError):
    """ValueError subclass that carries one stable validation error code."""

    def __init__(self, code: CircuitValidationCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_public_node_token(raw_value: object) -> str:
    """Validate public node tokens: decimal strings only, ground is canonical `0`."""
    if not isinstance(raw_value, str):
        raise CircuitValidationError(
            CircuitValidationCode.INVALID_NODE_TOKEN,
            "Topology nodes must be numeric strings. Use '0' as the only ground token.",
        )

    node_text = raw_value.strip()
    if node_text.lower() == "gnd":
        raise CircuitValidationError(
            CircuitValidationCode.UNSUPPORTED_GROUND_ALIAS,
            "Ground must be the string '0'. The 'gnd' alias is not supported.",
        )
    if not node_text.isdigit():
        raise CircuitValidationError(
            CircuitValidationCode.INVALID_NODE_TOKEN,
            "Topology nodes must be numeric strings. Use '0' as the only ground token.",
        )
    return str(int(node_text))


def validate_port_row_contract(
    *,
    row_name: str,
    node1: str,
    node2: str,
    value_ref: object,
    seen_port_indices: set[int],
    is_ground_node: Callable[[str | int], bool],
) -> int:
    """Validate one `P*` row contract and return normalized port index."""
    if not isinstance(value_ref, int):
        raise CircuitValidationError(
            CircuitValidationCode.PORT_INDEX_NOT_INTEGER,
            f"Port '{row_name}' must use an integer port index.",
        )
    port_index = int(value_ref)
    if port_index in seen_port_indices:
        raise CircuitValidationError(
            CircuitValidationCode.DUPLICATE_PORT_INDEX,
            f"Duplicate port index '{value_ref}'.",
        )
    if is_ground_node(node1) == is_ground_node(node2):
        raise CircuitValidationError(
            CircuitValidationCode.PORT_GROUND_TOPOLOGY,
            f"Port '{row_name}' must connect exactly one side to ground ('0').",
        )
    return port_index


def validate_mutual_coupling_component_reference(
    *,
    row_name: str,
    value_ref: object,
    component_specs: Mapping[str, object],
) -> None:
    """Validate the component-reference slot of one `K*` row."""
    if not isinstance(value_ref, str):
        raise CircuitValidationError(
            CircuitValidationCode.MUTUAL_COUPLING_COMPONENT_REFERENCE_INVALID,
            f"Mutual coupling '{row_name}' must reference a component name.",
        )
    if value_ref not in component_specs:
        raise CircuitValidationError(
            CircuitValidationCode.MUTUAL_COUPLING_COMPONENT_REFERENCE_UNDEFINED,
            f"Mutual coupling '{row_name}' references undefined component '{value_ref}'.",
        )


def validate_topology_component_reference(
    *,
    row_name: str,
    value_ref: object,
    component_specs: Mapping[str, object],
) -> None:
    """Validate component-reference slot for non-`P*`/`K*` topology rows."""
    if not isinstance(value_ref, str):
        raise CircuitValidationError(
            CircuitValidationCode.TOPOLOGY_COMPONENT_REFERENCE_INVALID,
            f"Topology row '{row_name}' must reference a component name.",
        )
    if value_ref not in component_specs:
        raise CircuitValidationError(
            CircuitValidationCode.TOPOLOGY_COMPONENT_REFERENCE_UNDEFINED,
            f"Topology row '{row_name}' references undefined component '{value_ref}'.",
        )


def validate_mutual_coupling_inductive_references(
    *,
    row_name: str,
    first_ref: str,
    second_ref: str,
    element_kind_by_name: Mapping[str, str],
) -> None:
    """Validate that `K*` inductor references point to inductive elements."""
    allowed_kinds = {"inductor", "josephson_junction"}
    first_kind = element_kind_by_name.get(first_ref)
    second_kind = element_kind_by_name.get(second_ref)
    if first_kind not in allowed_kinds:
        raise CircuitValidationError(
            CircuitValidationCode.MUTUAL_COUPLING_ELEMENT_NON_INDUCTIVE,
            "Mutual coupling "
            f"'{row_name}' references unknown or non-inductive element '{first_ref}'.",
        )
    if second_kind not in allowed_kinds:
        raise CircuitValidationError(
            CircuitValidationCode.MUTUAL_COUPLING_ELEMENT_NON_INDUCTIVE,
            "Mutual coupling "
            f"'{row_name}' references unknown or non-inductive element '{second_ref}'.",
        )
