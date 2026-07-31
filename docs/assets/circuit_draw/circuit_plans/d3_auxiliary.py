from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import schemdraw
import schemdraw.elements as elm
from _lib.style import Theme, circuit_drawing
from schemdraw_circuit_library import (
    CoupledCPWTransmissionLine,
    FloatingParallelLC,
    GroundedLCResonator,
    InterdigitatedCapacitor,
    PiSectionChain,
    Port50Ohm,
    TransmissionLineSegment,
    theme_color,
)
from schemdraw_circuit_library.metadata import (
    add_at_public_terminal,
    public_terminal_point,
    validate_block_clearance,
)
from schemdraw_circuit_library.rendering import load_schematic_export


def _config(
    path: str,
) -> tuple[dict[str, Any], dict[str, Any], float, dict[str, dict[str, Any]]]:
    export = load_schematic_export(path)
    config = export["render_hints"]["schemdraw"]
    node_labels = {
        str(item["id"]): dict(item)
        for item in export.get("node_labels", [])
        if isinstance(item, Mapping) and "id" in item
    }
    return (
        dict(config.get("labels", {})),
        dict(config.get("parameters", {})),
        float(config.get("unit_length", 1.5)),
        node_labels,
    )


def _label(labels: Mapping[str, Any], name: str, default: str) -> str:
    value = labels.get(name, default)
    if not isinstance(value, str):
        raise ValueError(f"D3 auxiliary label {name!r} must be a string.")
    return value


def _point(component: Any, terminal: str) -> tuple[float, float]:
    return public_terminal_point(component, terminal, transformed=True)


def _d3_transmission_line_segment(**kwargs: Any) -> TransmissionLineSegment:
    """Keep D3 box labels inside their boxes without an automatic outer copy."""

    segment = TransmissionLineSegment(**kwargs)
    segment._userparams.pop("label", None)
    return segment


def _node_label_intent(
    node_labels: Mapping[str, Mapping[str, Any]],
    name: str,
    default: str,
) -> tuple[str, str, float | tuple[float, float] | None]:
    spec = node_labels.get(name, {})
    label = spec.get("label", default)
    hints = spec.get("hints", {})
    if not isinstance(label, str):
        raise ValueError(f"D3 node label {name!r} must be a string.")
    if not isinstance(hints, Mapping):
        raise ValueError(f"D3 node label {name!r} hints must be a mapping.")
    loc = hints.get("loc", "top")
    if loc not in {"top", "bottom", "left", "right"}:
        raise ValueError(f"D3 node label {name!r} has unsupported loc {loc!r}.")
    offset = hints.get("offset")
    if isinstance(offset, list):
        offset = tuple(offset)
    if offset is not None and not isinstance(offset, int | float | tuple):
        raise ValueError(f"D3 node label {name!r} has invalid offset {offset!r}.")
    return label, loc, offset


def _draw_node_label(
    drawing: schemdraw.Drawing,
    point: tuple[float, float],
    label: str,
    *,
    color: str,
    loc: str = "top",
    offset: float | tuple[float, float] | None = None,
) -> None:
    kwargs: dict[str, Any] = {"loc": loc, "color": color}
    if offset is not None:
        kwargs["ofst"] = offset
    drawing.add(elm.Dot(color=color).at(point).label(label, **kwargs).hold())


def _bus_label(
    drawing: schemdraw.Drawing,
    point: tuple[float, float],
    label: str,
    *,
    color: str,
) -> None:
    drawing.add(elm.Label(label, color=color).at(point))


def _port(
    drawing: schemdraw.Drawing,
    point: tuple[float, float],
    *,
    side: str,
    load_direction: str,
    port_label: str,
    resistance_label: str,
    unit_length: float,
    theme: Theme,
) -> Port50Ohm:
    return add_at_public_terminal(
        drawing,
        Port50Ohm(
            component_id=f"d3_auxiliary_{side}_{port_label}",
            unit_length=unit_length,
            side=side,
            stub_units=0.8,
            load_direction=load_direction,
            theme=theme,
            port_label=port_label,
            resistance_label=resistance_label,
            resistance_label_loc="top" if load_direction == "up" else "bottom",
            show_nodes=False,
            show_terminals=True,
            show_labels=True,
        ).theta(0),
        "circuit",
        point,
    )


def _matched_port_regularizer(
    drawing: schemdraw.Drawing,
    *,
    center_x: float,
    y: float,
    labels: Mapping[str, Any],
    unit_length: float,
    theme: Theme,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    regularizer = add_at_public_terminal(
        drawing,
        PiSectionChain(
            component_id="d3_auxiliary_matched_port_regularizer",
            n=2,
            unit_length=unit_length,
            spacing_units=2.0,
            height_units=1.0,
            port_stub_units=1.2,
            reduce_capacitance=True,
            theme=theme,
            l_label_template=_label(
                labels,
                "feedline_regularizer_inductance_label",
                r"$L_{\mathrm{sep}}$",
            )
            .replace("{", "{{")
            .replace("}", "}}"),
            c_half_label=_label(
                labels,
                "feedline_regularizer_half_capacitance_label",
                r"$C_{\mathrm{sep}}/2$",
            ),
            c_reduced_label=_label(
                labels,
                "feedline_regularizer_center_capacitance_label",
                r"$C_{\mathrm{sep}}$",
            ),
            show_terminals=False,
            show_nodes=False,
            show_labels=True,
        ),
        "tap_1",
        (center_x, y),
    )
    center = _point(regularizer, "tap_1")
    left = _point(regularizer, "left")
    right = _point(regularizer, "right")
    return left, center, right


def _distributed_feedline(
    drawing: schemdraw.Drawing,
    *,
    center_x: float,
    y: float,
    labels: Mapping[str, Any],
    unit_length: float,
    theme: Theme,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    left_half = add_at_public_terminal(
        drawing,
        _d3_transmission_line_segment(
            component_id="d3_auxiliary_distributed_feedline_left",
            unit_length=unit_length,
            length_units=2.5,
            theme=theme,
            label=_label(
                labels,
                "feedline_left_label",
                r"$\mathrm{CPW\ feedline}\ \ell_f/2$",
            ),
            left_terminal="none",
            right_terminal="none",
            boxed=True,
            box_height_units=0.72,
            show_nodes=False,
            show_terminals=False,
            show_labels=True,
        ),
        "tail",
        (center_x, y),
    )
    center = _point(left_half, "tail")
    right_half = add_at_public_terminal(
        drawing,
        _d3_transmission_line_segment(
            component_id="d3_auxiliary_distributed_feedline_right",
            unit_length=unit_length,
            length_units=2.5,
            theme=theme,
            label=_label(
                labels,
                "feedline_right_label",
                r"$\mathrm{CPW\ feedline}\ \ell_f/2$",
            ),
            left_terminal="none",
            right_terminal="none",
            boxed=True,
            box_height_units=0.72,
            show_nodes=False,
            show_terminals=False,
            show_labels=True,
        ),
        "head",
        center,
    )
    left = _point(left_half, "head")
    right = _point(right_half, "tail")
    return left, center, right


def build_linewidth_la_equivalent(
    export_path: str,
    *,
    theme: Theme = "light",
) -> schemdraw.Drawing:
    labels, _, unit_length, node_labels = _config(export_path)
    color = theme_color(theme)
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=8) as drawing:
        primary = drawing.add(
            GroundedLCResonator(
                component_id="linewidth_la_filter",
                unit_length=unit_length,
                spacing_units=1.0,
                height_units=1.15,
                theme=theme,
                c_label=_label(labels, "cp_label", r"$C_p$"),
                l_label=_label(labels, "lp_label", r"$L_p$"),
                show_nodes=False,
                show_terminals=False,
            ).at((0.0, 2.6 * unit_length))
        )
        primary_right = _point(primary, "right")
        diagonal_left = (primary_right[0] + 1.1 * unit_length, primary_right[1])
        drawing.add(elm.Line(color=color).endpoints(primary_right, diagonal_left))
        diagonal = add_at_public_terminal(
            drawing,
            GroundedLCResonator(
                component_id="linewidth_la_bridge_diagonal",
                unit_length=unit_length,
                spacing_units=1.0,
                height_units=1.15,
                theme=theme,
                c_label=_label(labels, "cn_diag_label", r"$C_n^{\mathrm{diag}}$"),
                l_label=_label(labels, "ln_diag_label", r"$L_n^{\mathrm{diag}}$"),
                show_nodes=False,
                show_terminals=False,
            ).theta(0),
            "left",
            diagonal_left,
        )
        diagonal_right = _point(diagonal, "right")
        idc_left = (diagonal_right[0] + 2.0 * unit_length, diagonal_right[1])
        drawing.add(elm.Line(color=color).endpoints(diagonal_right, idc_left))
        idc = add_at_public_terminal(
            drawing,
            InterdigitatedCapacitor(
                component_id="linewidth_la_idc",
                unit_length=unit_length,
                width_units=1.55,
                shunt_height_units=1.0,
                port_stub_units=1.8,
                theme=theme,
                c1g_label=_label(labels, "cpg_label", r"$C_{pG}^{\mathrm{IDC}}$"),
                c2g_label=_label(labels, "cfcg_label", r"$C_{f_cG}^{\mathrm{IDC}}$"),
                c12_label=_label(labels, "cpfc_label", r"$C_{pf_c}^{\mathrm{IDC}}$"),
                show_nodes=False,
                show_terminals=False,
            ).theta(0),
            "terminal_1",
            idc_left,
        )
        idc_right = _point(idc, "terminal_2")
        left, center, right = _matched_port_regularizer(
            drawing,
            center_x=idc_right[0],
            y=-1.0 * unit_length,
            labels=labels,
            unit_length=unit_length,
            theme=theme,
        )
        drawing.add(elm.Line(color=color).endpoints(idc_right, center))
        _port(
            drawing,
            left,
            side="left",
            load_direction="up",
            port_label=_label(labels, "input_port_label", r"$P_1$"),
            resistance_label=_label(labels, "input_port_resistance_label", r"$R_{50}$"),
            unit_length=unit_length,
            theme=theme,
        )
        _port(
            drawing,
            right,
            side="right",
            load_direction="up",
            port_label=_label(labels, "output_port_label", r"$P_2$"),
            resistance_label=_label(labels, "output_port_resistance_label", r"$R_{50}$"),
            unit_length=unit_length,
            theme=theme,
        )
        p_label, p_loc, p_offset = _node_label_intent(
            node_labels,
            "filter",
            r"$p$",
        )
        _draw_node_label(
            drawing,
            ((primary_right[0] + diagonal_left[0]) / 2, primary_right[1]),
            p_label,
            color=color,
            loc=p_loc,
            offset=p_offset,
        )
        fc_label, fc_loc, fc_offset = _node_label_intent(
            node_labels,
            "feedline_attachment",
            r"$f_c$",
        )
        _draw_node_label(
            drawing,
            center,
            fc_label,
            color=color,
            loc=fc_loc,
            offset=fc_offset,
        )
    return drawing


def build_linewidth_la_hybridized(
    export_path: str,
    *,
    theme: Theme = "light",
) -> schemdraw.Drawing:
    labels, _, unit_length, node_labels = _config(export_path)
    color = theme_color(theme)
    filter_color = "#4774cf" if theme == "light" else "#60a5fa"
    diagonal_color = "#8a50d0" if theme == "light" else "#c084fc"
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=8) as drawing:
        head = drawing.add(
            _d3_transmission_line_segment(
                component_id="linewidth_la_filter_head",
                unit_length=unit_length,
                length_units=2.0,
                theme=theme,
                label=_label(labels, "filter_head_label", r"$\mathrm{CPW}\ \ell_p^s$"),
                left_terminal="ground",
                right_terminal="none",
                boxed=True,
                line_color=filter_color,
                line_width=3.0,
                show_nodes=False,
                show_terminals=False,
            ).at((0.0, 2.6 * unit_length))
        )
        diagonal = add_at_public_terminal(
            drawing,
            _d3_transmission_line_segment(
                component_id="linewidth_la_filter_diagonal",
                unit_length=unit_length,
                length_units=1.8,
                theme=theme,
                label=_label(
                    labels,
                    "filter_diagonal_label",
                    r"$\mathrm{MTL\ diagonal}\ \ell_c$",
                ),
                left_terminal="none",
                right_terminal="none",
                boxed=True,
                line_color=diagonal_color,
                line_width=3.0,
                show_nodes=False,
                show_terminals=False,
            ),
            "head",
            _point(head, "tail"),
        )
        tail = add_at_public_terminal(
            drawing,
            _d3_transmission_line_segment(
                component_id="linewidth_la_filter_tail",
                unit_length=unit_length,
                length_units=2.0,
                theme=theme,
                label=_label(labels, "filter_tail_label", r"$\mathrm{CPW}\ \ell_p^o$"),
                left_terminal="none",
                right_terminal="none",
                boxed=True,
                line_color=filter_color,
                line_width=3.0,
                show_nodes=False,
                show_terminals=False,
            ),
            "head",
            _point(diagonal, "tail"),
        )
        filter_tail = _point(tail, "tail")
        idc = add_at_public_terminal(
            drawing,
            InterdigitatedCapacitor(
                component_id="linewidth_la_idc",
                unit_length=unit_length,
                width_units=1.55,
                shunt_height_units=1.0,
                port_stub_units=1.8,
                theme=theme,
                c1g_label=_label(labels, "cpg_label", r"$C_{pG}^{\mathrm{IDC}}$"),
                c2g_label=_label(labels, "cfcg_label", r"$C_{f_cG}^{\mathrm{IDC}}$"),
                c12_label=_label(labels, "cpfc_label", r"$C_{pf_c}^{\mathrm{IDC}}$"),
                show_nodes=False,
                show_terminals=False,
            ).theta(0),
            "terminal_1",
            filter_tail,
        )
        validate_block_clearance(
            {"filter_tail": tail, "feedline_idc": idc},
            clearance=0,
            include_labels=False,
        )
        idc_right = _point(idc, "terminal_2")
        left, center, right = _distributed_feedline(
            drawing,
            center_x=idc_right[0],
            y=-1.0 * unit_length,
            labels=labels,
            unit_length=unit_length,
            theme=theme,
        )
        drawing.add(elm.Line(color=color).endpoints(idc_right, center))
        _port(
            drawing,
            left,
            side="left",
            load_direction="up",
            port_label=_label(labels, "input_port_label", r"$P_1$"),
            resistance_label=_label(labels, "input_port_resistance_label", r"$R_{50}$"),
            unit_length=unit_length,
            theme=theme,
        )
        _port(
            drawing,
            right,
            side="right",
            load_direction="up",
            port_label=_label(labels, "output_port_label", r"$P_2$"),
            resistance_label=_label(labels, "output_port_resistance_label", r"$R_{50}$"),
            unit_length=unit_length,
            theme=theme,
        )
        p_label, p_loc, p_offset = _node_label_intent(
            node_labels,
            "filter",
            r"$p$",
        )
        _draw_node_label(
            drawing,
            filter_tail,
            p_label,
            color=color,
            loc=p_loc,
            offset=p_offset,
        )
        fc_label, fc_loc, fc_offset = _node_label_intent(
            node_labels,
            "feedline_attachment",
            r"$f_c$",
        )
        _draw_node_label(
            drawing,
            center,
            fc_label,
            color=color,
            loc=fc_loc,
            offset=fc_offset,
        )
    return drawing


def build_intrinsic_pair_notch_equivalent(
    export_path: str,
    *,
    theme: Theme = "light",
) -> schemdraw.Drawing:
    labels, _, unit_length, _ = _config(export_path)
    color = theme_color(theme)
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=8) as drawing:
        readout = drawing.add(
            GroundedLCResonator(
                component_id="intrinsic_pair_readout",
                unit_length=unit_length,
                spacing_units=1.0,
                height_units=1.15,
                theme=theme,
                c_label=_label(labels, "cr_label", r"$C_r$"),
                l_label=_label(labels, "lr_label", r"$L_r$"),
                show_nodes=False,
                show_terminals=False,
            ).at((0.0, 0.0))
        )
        filter_resonator = drawing.add(
            GroundedLCResonator(
                component_id="intrinsic_pair_filter",
                unit_length=unit_length,
                spacing_units=1.0,
                height_units=1.15,
                theme=theme,
                c_label=_label(labels, "cp_label", r"$C_p$"),
                l_label=_label(labels, "lp_label", r"$L_p$"),
                show_nodes=False,
                show_terminals=False,
            ).at((8.0 * unit_length, 0.0))
        )
        bridge_left = _point(readout, "right")
        bridge_right = _point(filter_resonator, "left")
        bridge_total = bridge_right[0] - bridge_left[0]
        bridge = add_at_public_terminal(
            drawing,
            FloatingParallelLC(
                component_id="intrinsic_pair_bridge",
                unit_length=unit_length,
                width_units=(bridge_total / unit_length) - 1.0,
                branch_offset_units=0.8,
                terminal_stub_units=0.5,
                theme=theme,
                c_label=_label(labels, "cn_label", r"$C_n$"),
                l_label=_label(labels, "ln_label", r"$L_n$"),
                show_nodes=False,
                show_terminals=False,
            ),
            "left",
            bridge_left,
        )
        if abs(_point(bridge, "right")[0] - bridge_right[0]) > 1e-9:
            raise ValueError("D3 equivalent notch bridge does not close on the filter bus.")
        readout_node = _point(readout, "left")
        filter_node = _point(filter_resonator, "right")
        _port(
            drawing,
            readout_node,
            side="left",
            load_direction="up",
            port_label=r"$P_r$",
            resistance_label=_label(labels, "input_port_resistance_label", r"$R_{50}$"),
            unit_length=unit_length,
            theme=theme,
        )
        _port(
            drawing,
            filter_node,
            side="right",
            load_direction="up",
            port_label=r"$P_p$",
            resistance_label=_label(labels, "output_port_resistance_label", r"$R_{50}$"),
            unit_length=unit_length,
            theme=theme,
        )
        _bus_label(
            drawing,
            (readout_node[0] + 0.55 * unit_length, readout_node[1] + 0.35 * unit_length),
            r"$r$",
            color=color,
        )
        _bus_label(
            drawing,
            (filter_node[0] - 0.55 * unit_length, filter_node[1] + 0.35 * unit_length),
            r"$p$",
            color=color,
        )
    return drawing


def build_intrinsic_pair_notch_hybridized(
    export_path: str,
    *,
    theme: Theme = "light",
) -> schemdraw.Drawing:
    labels, _, unit_length, _ = _config(export_path)
    color = theme_color(theme)
    readout_color = "#dc4c4c" if theme == "light" else "#fb7185"
    filter_color = "#4774cf" if theme == "light" else "#60a5fa"
    gap = 2.5 * unit_length
    with circuit_drawing(theme=theme, unit=unit_length, fontsize=8) as drawing:
        readout_head = drawing.add(
            _d3_transmission_line_segment(
                component_id="intrinsic_pair_readout_head",
                unit_length=unit_length,
                length_units=2.0,
                theme=theme,
                label=_label(labels, "readout_head_label", r"$\mathrm{CPW}\ \ell_r^s$"),
                left_terminal="ground",
                right_terminal="none",
                boxed=True,
                line_color=readout_color,
                line_width=3.0,
                show_nodes=False,
                show_terminals=False,
            ).at((0.0, 0.0))
        )
        filter_head = drawing.add(
            _d3_transmission_line_segment(
                component_id="intrinsic_pair_filter_head",
                unit_length=unit_length,
                length_units=2.0,
                theme=theme,
                label=_label(labels, "filter_head_label", r"$\mathrm{CPW}\ \ell_p^s$"),
                left_terminal="ground",
                right_terminal="none",
                boxed=True,
                line_color=filter_color,
                line_width=3.0,
                show_nodes=False,
                show_terminals=False,
            ).at((0.0, -gap))
        )
        window = add_at_public_terminal(
            drawing,
            CoupledCPWTransmissionLine(
                component_id="intrinsic_pair_mtl",
                unit_length=unit_length,
                width_units=1.8,
                track_gap_units=gap / unit_length,
                theme=theme,
                label=_label(labels, "mtl_label", r"$\mathrm{MTL}\ \ell_c$"),
                show_label=True,
                show_terminals=False,
            ),
            "readout_start",
            _point(readout_head, "tail"),
        )
        if abs(_point(filter_head, "tail")[0] - _point(window, "filter_start")[0]) > 1e-9:
            raise ValueError("D3 hybridized notch filter head does not meet the MTL window.")
        readout_tail = add_at_public_terminal(
            drawing,
            _d3_transmission_line_segment(
                component_id="intrinsic_pair_readout_tail",
                unit_length=unit_length,
                length_units=2.0,
                theme=theme,
                label=_label(labels, "readout_tail_label", r"$\mathrm{CPW}\ \ell_r^o$"),
                left_terminal="none",
                right_terminal="none",
                boxed=True,
                line_color=readout_color,
                line_width=3.0,
                show_nodes=False,
                show_terminals=False,
            ),
            "head",
            _point(window, "readout_end"),
        )
        filter_tail = add_at_public_terminal(
            drawing,
            _d3_transmission_line_segment(
                component_id="intrinsic_pair_filter_tail",
                unit_length=unit_length,
                length_units=2.0,
                theme=theme,
                label=_label(labels, "filter_tail_label", r"$\mathrm{CPW}\ \ell_p^o$"),
                left_terminal="none",
                right_terminal="none",
                boxed=True,
                line_color=filter_color,
                line_width=3.0,
                show_nodes=False,
                show_terminals=False,
            ),
            "head",
            _point(window, "filter_end"),
        )
        readout_node = _point(readout_tail, "tail")
        filter_node = _point(filter_tail, "tail")
        _port(
            drawing,
            readout_node,
            side="right",
            load_direction="up",
            port_label=r"$P_r$",
            resistance_label=_label(labels, "input_port_resistance_label", r"$R_{50}$"),
            unit_length=unit_length,
            theme=theme,
        )
        _port(
            drawing,
            filter_node,
            side="right",
            load_direction="down",
            port_label=r"$P_p$",
            resistance_label=_label(labels, "output_port_resistance_label", r"$R_{50}$"),
            unit_length=unit_length,
            theme=theme,
        )
        _bus_label(
            drawing,
            (readout_node[0] - 0.25 * unit_length, readout_node[1] + 0.35 * unit_length),
            r"$r$",
            color=color,
        )
        _bus_label(
            drawing,
            (filter_node[0] - 0.25 * unit_length, filter_node[1] - 0.35 * unit_length),
            r"$p$",
            color=color,
        )
    return drawing


def build_auxiliary_drawing(
    export_path: str,
    *,
    kind: str,
    theme: Theme = "light",
) -> schemdraw.Drawing:
    builders = {
        "linewidth_la_equivalent": build_linewidth_la_equivalent,
        "linewidth_la_hybridized": build_linewidth_la_hybridized,
        "intrinsic_pair_notch_equivalent": build_intrinsic_pair_notch_equivalent,
        "intrinsic_pair_notch_hybridized": build_intrinsic_pair_notch_hybridized,
    }
    try:
        builder = builders[kind]
    except KeyError as exc:
        raise ValueError(f"Unknown D3 auxiliary drawing kind: {kind!r}.") from exc
    return builder(export_path, theme=theme)
