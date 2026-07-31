from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from schemdraw import Drawing
from schemdraw.elements import ElementCompound

from ..components import (
    CapacitivelyCoupledGroundedLCResonator,
    D3IntrinsicPurcellEquivalentCircuitPlan,
    D3IntrinsicPurcellHybridizedCircuitPlan,
    FloatingLCXYResonator,
    GroundedLCResonator,
    InterdigitatedCapacitor,
    IntrinsicInterferometricPurcellFilter,
    IntrinsicInterferometricPurcellFilterEquivalent,
    IntrinsicInterferometricPurcellFilterEquivalentWithQubit,
    IntrinsicInterferometricPurcellFilterWithQubit,
)
from ..components.lumped import InductiveBranchKind
from ..metadata import NodeLabelPlacement, NodeLabelSpec
from ..theme import Theme


class UnsupportedSchematicComponentError(ValueError):
    """Raised when an export has no Schemdraw visual mapping."""


JsonMapping = Mapping[str, Any]
_PHYSICAL_NODE_LABEL_COMPONENTS = frozenset(
    {
        IntrinsicInterferometricPurcellFilter.component_kind,
        IntrinsicInterferometricPurcellFilterWithQubit.component_kind,
        IntrinsicInterferometricPurcellFilterEquivalent.component_kind,
        IntrinsicInterferometricPurcellFilterEquivalentWithQubit.component_kind,
        D3IntrinsicPurcellEquivalentCircuitPlan.component_kind,
        D3IntrinsicPurcellHybridizedCircuitPlan.component_kind,
    }
)


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
    physical_node_labels = _physical_node_labels(
        export_data,
        config=config,
        required=component_type in _PHYSICAL_NODE_LABEL_COMPONENTS,
    )

    selected_unit_length = unit_length
    if selected_unit_length is None:
        selected_unit_length = _float_value(config, "unit_length", default=3.0)

    component = _build_component(
        component_type=component_type,
        labels=labels,
        parameters=parameters,
        physical_node_labels=physical_node_labels,
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
    physical_node_labels: Mapping[str, NodeLabelSpec],
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
            resistance_label=_optional_string(labels, "resistance_label"),
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

    if component_type == InterdigitatedCapacitor.component_kind:
        return InterdigitatedCapacitor(
            component_id=_string_value(parameters, "component_id", default="idc"),
            unit_length=unit_length,
            theme=theme,
            c1g_label=_string_value(labels, "c1g_label", default=r"$C_{1g}$"),
            c2g_label=_string_value(labels, "c2g_label", default=r"$C_{2g}$"),
            c12_label=_string_value(labels, "c12_label", default=r"$C_{12}$"),
            terminal_1_label=_optional_string(labels, "terminal_1_label"),
            terminal_2_label=_optional_string(labels, "terminal_2_label"),
        )

    if component_type == IntrinsicInterferometricPurcellFilter.component_kind:
        return IntrinsicInterferometricPurcellFilter(
            component_id=_string_value(parameters, "component_id", default="intrinsic_filter"),
            unit_length=unit_length,
            theme=theme,
            readout_label=_optional_string(labels, "readout_label"),
            filter_label=_optional_string(labels, "filter_label"),
            readout_head_label=_optional_string(labels, "readout_head_label"),
            readout_tail_label=_optional_string(labels, "readout_tail_label"),
            filter_head_label=_optional_string(labels, "filter_head_label"),
            filter_tail_label=_optional_string(labels, "filter_tail_label"),
            mtl_label=_string_value(labels, "mtl_label", default=r"$\mathrm{MTL}\ \ell_c$"),
            capacitive_label=_string_value(labels, "capacitive_label", default=r"$C_m$"),
            inductive_label=_string_value(labels, "inductive_label", default=r"$M$"),
            c1g_label=_string_value(labels, "c1g_label", default=r"$C_{1g}$"),
            c2g_label=_string_value(labels, "c2g_label", default=r"$C_{2g}$"),
            c12_label=_string_value(labels, "c12_label", default=r"$C_{12}$"),
            c0r_label=_optional_string(labels, "c0r_label"),
            physical_node_labels=physical_node_labels,
        )

    if component_type == IntrinsicInterferometricPurcellFilterWithQubit.component_kind:
        qubit_branch_kind = cast(
            InductiveBranchKind,
            _string_value(
                parameters,
                "qubit_inductive_branch_kind",
            ),
        )
        return IntrinsicInterferometricPurcellFilterWithQubit(
            component_id=_string_value(
                parameters,
                "component_id",
                default="intrinsic_filter_with_qubit",
            ),
            unit_length=unit_length,
            theme=theme,
            readout_label=_optional_string(labels, "readout_label"),
            filter_label=_optional_string(labels, "filter_label"),
            readout_head_label=_optional_string(labels, "readout_head_label"),
            readout_tail_label=_optional_string(labels, "readout_tail_label"),
            filter_head_label=_optional_string(labels, "filter_head_label"),
            filter_tail_label=_optional_string(labels, "filter_tail_label"),
            mtl_label=_string_value(labels, "mtl_label", default=r"$\mathrm{MTL}\ \ell_c$"),
            capacitive_label=_string_value(labels, "capacitive_label", default=r"$C_m$"),
            inductive_label=_string_value(labels, "inductive_label", default=r"$M$"),
            c1g_label=_string_value(labels, "c1g_label", default=r"$C_{1g}$"),
            c2g_label=_string_value(labels, "c2g_label", default=r"$C_{2g}$"),
            c12_label=_string_value(labels, "c12_label", default=r"$C_{12}$"),
            c01_label=_string_value(labels, "c01_label", default=r"$C_{01}$"),
            c02_label=_string_value(labels, "c02_label", default=r"$C_{02}$"),
            qubit_c12_label=_string_value(
                labels,
                "qubit_c12_label",
                default=r"$C_{12,q}$",
            ),
            cr1_label=_string_value(labels, "cr1_label", default=r"$C_{r1}$"),
            cr2_label=_string_value(labels, "cr2_label", default=r"$C_{r2}$"),
            lj1_label=_string_value(labels, "lj1_label", default=r"$L_{J1}$"),
            lj2_label=_string_value(labels, "lj2_label", default=r"$L_{J2}$"),
            qubit_inductive_branch_kind=qubit_branch_kind,
            c0r_label=_optional_string(labels, "c0r_label"),
            physical_node_labels=physical_node_labels,
        )

    if component_type == IntrinsicInterferometricPurcellFilterEquivalent.component_kind:
        return IntrinsicInterferometricPurcellFilterEquivalent(
            component_id=_string_value(
                parameters,
                "component_id",
                default="intrinsic_filter_equivalent",
            ),
            unit_length=unit_length,
            theme=theme,
            cr_label=_string_value(labels, "cr_label", default=r"$C_r$"),
            lr_label=_string_value(labels, "lr_label", default=r"$L_r$"),
            cp_label=_string_value(labels, "cp_label", default=r"$C_p$"),
            lp_label=_string_value(labels, "lp_label", default=r"$L_p$"),
            cn_label=_string_value(labels, "cn_label", default=r"$C_n$"),
            ln_label=_string_value(labels, "ln_label", default=r"$L_n$"),
            cpg_label=_string_value(
                labels,
                "cpg_label",
                default=r"$C_{pG}^{\mathrm{IDC}}$",
            ),
            cfcg_label=_string_value(
                labels,
                "cfcg_label",
                default=r"$C_{f_cG}^{\mathrm{IDC}}$",
            ),
            cpfc_label=_string_value(
                labels,
                "cpfc_label",
                default=r"$C_{pf_c}^{\mathrm{IDC}}$",
            ),
            c0r_label=_optional_string(labels, "c0r_label"),
            physical_node_labels=physical_node_labels,
        )

    if component_type == IntrinsicInterferometricPurcellFilterEquivalentWithQubit.component_kind:
        qubit_branch_kind = cast(
            InductiveBranchKind,
            _string_value(
                parameters,
                "qubit_inductive_branch_kind",
            ),
        )
        return IntrinsicInterferometricPurcellFilterEquivalentWithQubit(
            component_id=_string_value(
                parameters,
                "component_id",
                default="intrinsic_filter_equivalent_with_qubit",
            ),
            unit_length=unit_length,
            theme=theme,
            cr_label=_string_value(labels, "cr_label", default=r"$C_r$"),
            lr_label=_string_value(labels, "lr_label", default=r"$L_r$"),
            cp_label=_string_value(labels, "cp_label", default=r"$C_p$"),
            lp_label=_string_value(labels, "lp_label", default=r"$L_p$"),
            cn_label=_string_value(labels, "cn_label", default=r"$C_n$"),
            ln_label=_string_value(labels, "ln_label", default=r"$L_n$"),
            cpg_label=_string_value(
                labels,
                "cpg_label",
                default=r"$C_{pG}^{\mathrm{IDC}}$",
            ),
            cfcg_label=_string_value(
                labels,
                "cfcg_label",
                default=r"$C_{f_cG}^{\mathrm{IDC}}$",
            ),
            cpfc_label=_string_value(
                labels,
                "cpfc_label",
                default=r"$C_{pf_c}^{\mathrm{IDC}}$",
            ),
            c01_label=_string_value(labels, "c01_label", default=r"$C_{01}$"),
            c02_label=_string_value(labels, "c02_label", default=r"$C_{02}$"),
            qubit_c12_label=_string_value(
                labels,
                "qubit_c12_label",
                default=r"$C_{12,q}$",
            ),
            cr1_label=_string_value(labels, "cr1_label", default=r"$C_{r1}$"),
            cr2_label=_string_value(labels, "cr2_label", default=r"$C_{r2}$"),
            lj1_label=_string_value(labels, "lj1_label", default=r"$L_{J1}$"),
            lj2_label=_string_value(labels, "lj2_label", default=r"$L_{J2}$"),
            qubit_inductive_branch_kind=qubit_branch_kind,
            c0r_label=_optional_string(labels, "c0r_label"),
            physical_node_labels=physical_node_labels,
        )

    if component_type == D3IntrinsicPurcellEquivalentCircuitPlan.component_kind:
        return D3IntrinsicPurcellEquivalentCircuitPlan(
            component_id=_string_value(parameters, "component_id"),
            unit_length=unit_length,
            theme=theme,
            cr_label=_string_value(labels, "cr_label", default=r"$C_r$"),
            lr_label=_string_value(labels, "lr_label", default=r"$L_r$"),
            cp_label=_string_value(labels, "cp_label", default=r"$C_p$"),
            lp_label=_string_value(labels, "lp_label", default=r"$L_p$"),
            cn_label=_string_value(labels, "cn_label", default=r"$C_n$"),
            ln_label=_string_value(labels, "ln_label", default=r"$L_n$"),
            cpg_label=_string_value(labels, "cpg_label", default=r"$C_{pG}^{\mathrm{IDC}}$"),
            cfcg_label=_string_value(labels, "cfcg_label", default=r"$C_{f_cG}^{\mathrm{IDC}}$"),
            cpfc_label=_string_value(labels, "cpfc_label", default=r"$C_{pf_c}^{\mathrm{IDC}}$"),
            c01_label=_string_value(labels, "c01_label", default=r"$C_{01}$"),
            c02_label=_string_value(labels, "c02_label", default=r"$C_{02}$"),
            qubit_c12_label=_string_value(labels, "qubit_c12_label", default=r"$C_{12}$"),
            cr1_label=_string_value(labels, "cr1_label", default=r"$C_{r1}$"),
            cr2_label=_string_value(labels, "cr2_label", default=r"$C_{r2}$"),
            lj1_label=_string_value(labels, "lj1_label", default=r"$L_{J1}$"),
            lj2_label=_string_value(labels, "lj2_label", default=r"$L_{J2}$"),
            qubit_inductive_branch_kind=cast(
                InductiveBranchKind,
                _string_value(parameters, "qubit_inductive_branch_kind"),
            ),
            c0r_label=_optional_string(labels, "c0r_label"),
            feedline_regularizer_inductance_label=_string_value(
                labels,
                "feedline_regularizer_inductance_label",
                default=r"$L_{\mathrm{sep}}$",
            ),
            feedline_regularizer_half_capacitance_label=_string_value(
                labels,
                "feedline_regularizer_half_capacitance_label",
                default=r"$C_{\mathrm{sep}}/2$",
            ),
            feedline_regularizer_center_capacitance_label=_string_value(
                labels,
                "feedline_regularizer_center_capacitance_label",
                default=r"$C_{\mathrm{sep}}$",
            ),
            input_port_label=_string_value(labels, "input_port_label", default=r"$P_1$"),
            output_port_label=_string_value(labels, "output_port_label", default=r"$P_2$"),
            input_port_resistance_label=_string_value(
                labels, "input_port_resistance_label", default=r"$R_{50}$"
            ),
            output_port_resistance_label=_string_value(
                labels, "output_port_resistance_label", default=r"$R_{50}$"
            ),
            physical_node_labels=physical_node_labels,
        )

    if component_type == D3IntrinsicPurcellHybridizedCircuitPlan.component_kind:
        return D3IntrinsicPurcellHybridizedCircuitPlan(
            component_id=_string_value(parameters, "component_id"),
            unit_length=unit_length,
            theme=theme,
            readout_label=_optional_string(labels, "readout_label"),
            filter_label=_optional_string(labels, "filter_label"),
            readout_head_label=_optional_string(labels, "readout_head_label"),
            readout_tail_label=_optional_string(labels, "readout_tail_label"),
            filter_head_label=_optional_string(labels, "filter_head_label"),
            filter_tail_label=_optional_string(labels, "filter_tail_label"),
            mtl_label=_string_value(labels, "mtl_label", default=r"$\mathrm{MTL}\ \ell_c$"),
            capacitive_label=_string_value(labels, "capacitive_label", default=r"$C_m$"),
            inductive_label=_string_value(labels, "inductive_label", default=r"$M$"),
            c1g_label=_string_value(labels, "cpg_label", default=r"$C_{pG}^{\mathrm{IDC}}$"),
            c2g_label=_string_value(labels, "cfcg_label", default=r"$C_{f_cG}^{\mathrm{IDC}}$"),
            c12_label=_string_value(labels, "cpfc_label", default=r"$C_{pf_c}^{\mathrm{IDC}}$"),
            c01_label=_string_value(labels, "c01_label", default=r"$C_{01}$"),
            c02_label=_string_value(labels, "c02_label", default=r"$C_{02}$"),
            qubit_c12_label=_string_value(labels, "qubit_c12_label", default=r"$C_{12}$"),
            cr1_label=_string_value(labels, "cr1_label", default=r"$C_{r1}$"),
            cr2_label=_string_value(labels, "cr2_label", default=r"$C_{r2}$"),
            lj1_label=_string_value(labels, "lj1_label", default=r"$L_{J1}$"),
            lj2_label=_string_value(labels, "lj2_label", default=r"$L_{J2}$"),
            qubit_inductive_branch_kind=cast(
                InductiveBranchKind,
                _string_value(parameters, "qubit_inductive_branch_kind"),
            ),
            c0r_label=_optional_string(labels, "c0r_label"),
            feedline_left_label=_string_value(
                labels,
                "feedline_left_label",
                default=r"$\mathrm{CPW\ feedline}\ \ell_f/2$",
            ),
            feedline_right_label=_string_value(
                labels,
                "feedline_right_label",
                default=r"$\mathrm{CPW\ feedline}\ \ell_f/2$",
            ),
            input_port_label=_string_value(labels, "input_port_label", default=r"$P_1$"),
            output_port_label=_string_value(labels, "output_port_label", default=r"$P_2$"),
            input_port_resistance_label=_string_value(
                labels, "input_port_resistance_label", default=r"$R_{50}$"
            ),
            output_port_resistance_label=_string_value(
                labels, "output_port_resistance_label", default=r"$R_{50}$"
            ),
            physical_node_labels=physical_node_labels,
        )

    raise UnsupportedSchematicComponentError(
        f"Unsupported Schemdraw component_type: {component_type!r}."
    )


def _physical_node_labels(
    export_data: JsonMapping,
    *,
    config: JsonMapping,
    required: bool,
) -> dict[str, NodeLabelSpec]:
    node_bindings = _node_bindings(config, required=required)
    raw_labels = export_data.get("node_labels")
    if raw_labels is None:
        if required:
            raise ValueError("node_labels must be an array for this component.")
        return {}
    if not isinstance(raw_labels, list):
        raise ValueError("node_labels must be an array.")

    labels: dict[str, NodeLabelSpec] = {}
    label_targets: dict[str, str] = {}
    for index, raw_label in enumerate(raw_labels):
        if not isinstance(raw_label, Mapping):
            raise ValueError(f"node_labels[{index}] must be an object.")

        node = _string_value(raw_label, "id")
        if not node:
            raise ValueError(f"node_labels[{index}].id must be nonempty.")
        if node in labels:
            raise ValueError(f"node_labels contains duplicate id {node!r}.")
        source_target = _string_value(raw_label, "target")
        if not source_target:
            raise ValueError(f"node_labels[{index}].target must be nonempty.")
        label_targets[node] = source_target

        hints = _mapping_value(raw_label, "hints", default={})
        if hints is None:
            raise ValueError(f"node_labels[{index}].hints must be an object.")
        placement_value = hints.get("placement")
        target_value = hints.get("placement_target")
        if placement_value is None or target_value is None:
            if required:
                raise ValueError(
                    f"node_labels[{index}] must define hints.placement and "
                    "hints.placement_target."
                )
            continue
        if placement_value not in {"bus_middle", "marker", "terminal"}:
            raise ValueError(
                f"node_labels[{index}].hints.placement has unsupported value "
                f"{placement_value!r}."
            )
        if not isinstance(target_value, str) or not target_value:
            raise ValueError(
                f"node_labels[{index}].hints.placement_target must be a nonempty string."
            )

        labels[node] = NodeLabelSpec(
            text=_string_value(raw_label, "label"),
            placement=cast(NodeLabelPlacement, placement_value),
            target=target_value,
            loc=_string_value(hints, "loc", default="top"),
            offset=_node_label_offset(hints.get("offset"), index=index),
        )

    if required:
        binding_roles = set(node_bindings)
        label_roles = set(labels)
        missing = sorted(label_roles - binding_roles)
        extra = sorted(binding_roles - label_roles)
        if missing or extra:
            details = []
            if missing:
                details.append(f"missing roles {missing!r}")
            if extra:
                details.append(f"extra roles {extra!r}")
            raise ValueError("node_bindings does not match node_labels: " + ", ".join(details))
        for role, target in label_targets.items():
            if node_bindings[role] != target:
                raise ValueError(
                    f"node_labels role {role!r} targets {target!r}, but "
                    f"node_bindings maps it to {node_bindings[role]!r}."
                )
    return labels


def _node_bindings(
    config: JsonMapping,
    *,
    required: bool,
) -> dict[str, str]:
    raw_bindings = config.get("node_bindings")
    if raw_bindings is None:
        if required:
            raise ValueError("render_hints.schemdraw.node_bindings must be an object.")
        return {}
    if not isinstance(raw_bindings, Mapping):
        raise ValueError("render_hints.schemdraw.node_bindings must be an object.")

    bindings: dict[str, str] = {}
    endpoint_owners: dict[str, str] = {}
    for role, endpoint in raw_bindings.items():
        if not isinstance(role, str) or not role:
            raise ValueError("node_bindings roles must be nonempty strings.")
        if not isinstance(endpoint, str) or not endpoint:
            raise ValueError(
                f"node_bindings endpoint for role {role!r} must be a nonempty string."
            )
        previous_role = endpoint_owners.setdefault(endpoint, role)
        if previous_role != role:
            raise ValueError(
                f"node_bindings endpoint {endpoint!r} is assigned to both "
                f"{previous_role!r} and {role!r}."
            )
        bindings[role] = endpoint
    return bindings


def _node_label_offset(
    value: Any,
    *,
    index: int,
) -> float | tuple[float, float] | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"node_labels[{index}].hints.offset must be numeric.")
    if isinstance(value, int | float):
        return float(value)
    if (
        isinstance(value, list | tuple)
        and len(value) == 2
        and all(isinstance(item, int | float) and not isinstance(item, bool) for item in value)
    ):
        return (float(value[0]), float(value[1]))
    raise ValueError(
        f"node_labels[{index}].hints.offset must be one number or a two-number array."
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
