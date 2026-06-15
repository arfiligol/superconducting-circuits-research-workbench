from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from schemdraw import Drawing
from schemdraw.elements import ElementCompound

from ..components import (
    CapacitivelyCoupledGroundedLCResonator,
    FloatingLCXYResonator,
    GroundedLCResonator,
)
from ..components.lumped import InductiveBranchKind
from ..theme import Theme


class UnsupportedSchematicComponentError(ValueError):
    """Raised when an export has no Schemdraw visual mapping."""


JsonMapping = Mapping[str, Any]


def load_schematic_export(path: str | Path) -> JsonMapping:
    """Load renderer-neutral schematic export data from a committed fixture."""

    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("Schematic export JSON root must be an object.")
    return loaded


def add_schematic_export_to_drawing(
    drawing: Drawing,
    export_data: JsonMapping,
    *,
    theme: Theme,
    unit_length: float | None = None,
) -> ElementCompound:
    """Add the Schemdraw component requested by a Core schematic export."""

    config = _schemdraw_config(export_data)
    component_type = _string_value(config, "component_type")
    labels = _mapping_value(config, "labels", default={})
    parameters = _mapping_value(config, "parameters", default={})
    if labels is None or parameters is None:
        raise ValueError("labels and parameters must be objects.")

    selected_unit_length = unit_length
    if selected_unit_length is None:
        selected_unit_length = _float_value(config, "unit_length", default=3.0)

    component = _build_component(
        component_type=component_type,
        labels=labels,
        parameters=parameters,
        theme=theme,
        unit_length=selected_unit_length,
    )
    return cast(ElementCompound, drawing.add(component))


def _schemdraw_config(export_data: JsonMapping) -> JsonMapping:
    render_hints = _mapping_value(export_data, "render_hints", default={})
    if render_hints is None:
        raise UnsupportedSchematicComponentError("Schematic export is missing render_hints.")
    schemdraw_config = _mapping_value(render_hints, "schemdraw", default=None)
    if schemdraw_config is None:
        raise UnsupportedSchematicComponentError(
            "Schematic export is missing render_hints.schemdraw."
        )
    return schemdraw_config


def _build_component(
    *,
    component_type: str,
    labels: JsonMapping,
    parameters: JsonMapping,
    theme: Theme,
    unit_length: float,
) -> ElementCompound:
    branch_kind = cast(
        InductiveBranchKind,
        _string_value(parameters, "inductive_branch_kind", default="linear"),
    )

    if component_type == GroundedLCResonator.component_kind:
        return GroundedLCResonator(
            component_id=_string_value(parameters, "component_id", default="grounded_lc"),
            unit_length=unit_length,
            theme=theme,
            inductive_branch_kind=branch_kind,
            c_label=_optional_string(labels, "c_label"),
            l_label=_optional_string(labels, "l_label"),
            junction_label=_optional_string(labels, "junction_label"),
            squid_label=_optional_string(labels, "squid_label"),
            port_label=_optional_string(labels, "port_label"),
        )

    if component_type == CapacitivelyCoupledGroundedLCResonator.component_kind:
        return CapacitivelyCoupledGroundedLCResonator(
            component_id=_string_value(parameters, "component_id", default="coupled_grounded_lc"),
            unit_length=unit_length,
            theme=theme,
            inductive_branch_kind=branch_kind,
            coupling_label=_optional_string(labels, "coupling_label"),
            c_label=_optional_string(labels, "c_label"),
            l_label=_optional_string(labels, "l_label"),
            junction_label=_optional_string(labels, "junction_label"),
            squid_label=_optional_string(labels, "squid_label"),
            port_label=_optional_string(labels, "port_label"),
            resistance_label=_optional_string(labels, "resistance_label"),
        )

    if component_type == FloatingLCXYResonator.component_kind:
        return FloatingLCXYResonator(
            component_id=_string_value(parameters, "component_id", default="floating_lc_xy"),
            unit_length=unit_length,
            theme=theme,
            inductive_branch_kind=branch_kind,
            c_g1_label=_optional_string(labels, "c_g1_label"),
            c_g2_label=_optional_string(labels, "c_g2_label"),
            c_q_label=_optional_string(labels, "c_q_label"),
            l_q1_label=_optional_string(labels, "l_q1_label"),
            l_q2_label=_optional_string(labels, "l_q2_label"),
            c_xy1_label=_optional_string(labels, "c_xy1_label"),
            c_xy2_label=_optional_string(labels, "c_xy2_label"),
            pad1_label=_optional_string(labels, "pad1_label"),
            pad2_label=_optional_string(labels, "pad2_label"),
            xy_label=_optional_string(labels, "xy_label"),
            port_resistance_label=_optional_string(labels, "port_resistance_label"),
        )

    raise UnsupportedSchematicComponentError(
        f"Unsupported Schemdraw component_type: {component_type!r}."
    )


def _mapping_value(
    data: JsonMapping,
    key: str,
    *,
    default: JsonMapping | None,
) -> JsonMapping | None:
    value = data.get(key, default)
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be an object.")
    return value


def _string_value(data: JsonMapping, key: str, *, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string.")
    return value


def _optional_string(data: JsonMapping, key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string when provided.")
    return value


def _float_value(data: JsonMapping, key: str, *, default: float) -> float:
    value = data.get(key, default)
    if not isinstance(value, int | float):
        raise ValueError(f"{key} must be a number.")
    return float(value)


__all__ = [
    "UnsupportedSchematicComponentError",
    "add_schematic_export_to_drawing",
    "load_schematic_export",
]
