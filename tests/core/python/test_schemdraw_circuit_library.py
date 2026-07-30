from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast

import matplotlib
import pytest
import schemdraw
import schemdraw.elements as elm
from matplotlib import pyplot as plt
from schemdraw_circuit_library import (
    SCHEMATIC_DOT_RADIUS,
    CapacitivelyCoupledGroundedLCResonator,
    CoupledLineLadderSection,
    FloatingLCResonator,
    FloatingLCXYResonator,
    FloatingParallelLC,
    GroundedLCResonator,
    InductanceLoop,
    InductiveBranch,
    InterdigitatedCapacitor,
    PiSectionChain,
    PointCoupledReadoutPurcell,
    Port50Ohm,
    PortTerminal,
    ReadoutLineHangingQWRMTL,
    ReadoutPurcellHangingQWRMTL,
    TransmissionLineSegment,
    theme_color,
)
from schemdraw_circuit_library.components.transmission_lines import (
    D3IntrinsicPurcellEquivalentCircuitPlan,
    D3IntrinsicPurcellHybridizedCircuitPlan,
)
from schemdraw_circuit_library.metadata import BusSpec, TerminalSpec, public_terminal_point
from schemdraw_circuit_library.rendering import (
    UnsupportedSchematicComponentError,
    add_schematic_export_to_drawing,
    load_schematic_export,
)
from schemdraw_circuit_library.theme import Theme

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[3]
ComponentFactory = Callable[[Theme], elm.ElementCompound]
EXECUTABLE_COMPONENT_MODULES = (
    "core/python/circuit_libraries/schemdraw_circuit_library/components/ports/terminations.py",
    "core/python/circuit_libraries/schemdraw_circuit_library/components/lumped/resonators.py",
    "core/python/circuit_libraries/schemdraw_circuit_library/components/transmission_lines/pi_sections.py",
    "core/python/circuit_libraries/schemdraw_circuit_library/components/transmission_lines/systems.py",
    "core/python/circuit_libraries/schemdraw_circuit_library/components/couplers/coupled_lines.py",
)


def _grounded_lc(theme: Theme) -> GroundedLCResonator:
    return GroundedLCResonator(
        component_id="resonator",
        name="r",
        unit_length=3.0,
        theme=theme,
        port_label=r"$P_1$",
    )


def _port50(theme: Theme) -> Port50Ohm:
    return Port50Ohm(
        component_id="signal_port",
        unit_length=2.0,
        theme=theme,
        port_label=r"$P_1$",
    )


def _port_terminal(theme: Theme) -> PortTerminal:
    return PortTerminal(
        component_id="signal_terminal",
        unit_length=2.0,
        side="left",
        theme=theme,
        port_label=r"$P_1$",
    )


def _inductive_branch_linear(theme: Theme) -> InductiveBranch:
    return InductiveBranch(branch_kind="linear", unit_length=2.0, theme=theme)


def _inductive_branch_josephson(theme: Theme) -> InductiveBranch:
    return InductiveBranch(branch_kind="josephson", unit_length=2.0, theme=theme)


def _inductive_branch_squid(theme: Theme) -> InductiveBranch:
    return InductiveBranch(branch_kind="squid", unit_length=2.0, theme=theme)


def _inductance_loop_linear(theme: Theme) -> InductanceLoop:
    return InductanceLoop(
        component_id="linear_loop",
        element_kind="linear",
        unit_length=2.0,
        theme=theme,
        left_label=r"$L_{q1}$",
        right_label=r"$L_{q2}$",
    )


def _inductance_loop_josephson(theme: Theme) -> InductanceLoop:
    return InductanceLoop(
        component_id="josephson_loop",
        element_kind="josephson",
        unit_length=2.0,
        theme=theme,
        left_label=r"$JJ_1$",
        right_label=r"$JJ_2$",
    )


def _floating_lc(theme: Theme) -> FloatingLCResonator:
    return FloatingLCResonator(
        component_id="floating",
        unit_length=2.0,
        theme=theme,
        inductive_branch_kind="squid",
        upper_port_label=r"$P_1$",
        lower_port_label=r"$P_2$",
    )


def _floating_lc_xy(theme: Theme) -> FloatingLCXYResonator:
    return FloatingLCXYResonator(
        component_id="floating",
        unit_length=2.0,
        theme=theme,
        pad1_label=r"$P_1$",
        pad2_label=r"$P_2$",
        xy_label=r"$XY$",
    )


def _capacitively_coupled_grounded_lc(theme: Theme) -> CapacitivelyCoupledGroundedLCResonator:
    return CapacitivelyCoupledGroundedLCResonator(
        component_id="jpa",
        unit_length=2.2,
        theme=theme,
        port_label=r"$P_1$",
    )


def _pi_chain(theme: Theme) -> PiSectionChain:
    return PiSectionChain(
        component_id="pi_chain",
        n=3,
        unit_length=1.7,
        theme=theme,
    )


def _transmission_segment(theme: Theme) -> TransmissionLineSegment:
    return TransmissionLineSegment(
        component_id="segment",
        unit_length=2.0,
        theme=theme,
        label=r"$Z_0, \ell$",
        left_label=r"$P_1$",
        right_label=r"$P_2$",
    )


def _point_coupled_readout_purcell(theme: Theme) -> PointCoupledReadoutPurcell:
    return PointCoupledReadoutPurcell(
        component_id="readout_purcell",
        unit_length=1.7,
        theme=theme,
        input_line_label=None,
        output_line_label=None,
        left_port_label=r"$P_1$",
        right_port_label=r"$P_2$",
    )


def _readout_line_hanging_qwr_mtl(theme: Theme) -> ReadoutLineHangingQWRMTL:
    return ReadoutLineHangingQWRMTL(
        component_id="readout_qwr_mtl",
        unit_length=1.8,
        track_gap_units=1.35,
        window_length_units=1.15,
        theme=theme,
        readout_label=None,
        left_port_label=r"$P_1$",
        right_port_label=r"$P_2$",
    )


def _readout_purcell_hanging_qwr_mtl(theme: Theme) -> ReadoutPurcellHangingQWRMTL:
    return ReadoutPurcellHangingQWRMTL(
        component_id="readout_purcell_qwr_mtl",
        unit_length=1.55,
        track_gap_units=1.0,
        qwr_gap_units=2.05,
        window_length_units=1.15,
        theme=theme,
        filter_label=None,
        left_port_label=r"$P_1$",
        right_port_label=r"$P_2$",
    )


def _coupled_line_ladder(theme: Theme) -> CoupledLineLadderSection:
    return CoupledLineLadderSection(
        component_id="coupled_line",
        unit_length=1.8,
        track_gap_units=1.5,
        theme=theme,
    )


COMPONENT_CASES: tuple[tuple[str, str, ComponentFactory], ...] = (
    ("port50", "Port50Ohm", _port50),
    ("port_terminal", "PortTerminal", _port_terminal),
    ("inductive_branch_linear", "InductiveBranch", _inductive_branch_linear),
    ("inductive_branch_josephson", "InductiveBranch", _inductive_branch_josephson),
    ("inductive_branch_squid", "InductiveBranch", _inductive_branch_squid),
    ("inductance_loop_linear", "InductanceLoop", _inductance_loop_linear),
    ("inductance_loop_josephson", "InductanceLoop", _inductance_loop_josephson),
    ("grounded_lc", "GroundedLCResonator", _grounded_lc),
    ("floating_lc", "FloatingLCResonator", _floating_lc),
    ("floating_lc_xy", "FloatingLCXYResonator", _floating_lc_xy),
    (
        "capacitively_coupled_grounded_lc",
        "CapacitivelyCoupledGroundedLCResonator",
        _capacitively_coupled_grounded_lc,
    ),
    ("pi_chain", "PiSectionChain", _pi_chain),
    ("transmission_segment", "TransmissionLineSegment", _transmission_segment),
    (
        "point_coupled_readout_purcell",
        "PointCoupledReadoutPurcell",
        _point_coupled_readout_purcell,
    ),
    (
        "readout_line_hanging_qwr_mtl",
        "ReadoutLineHangingQWRMTL",
        _readout_line_hanging_qwr_mtl,
    ),
    (
        "readout_purcell_hanging_qwr_mtl",
        "ReadoutPurcellHangingQWRMTL",
        _readout_purcell_hanging_qwr_mtl,
    ),
    ("coupled_line_ladder", "CoupledLineLadderSection", _coupled_line_ladder),
)


def test_schematic_dot_radius_is_project_wide_constant() -> None:
    assert SCHEMATIC_DOT_RADIUS == 0.1


def test_reusable_component_outward_leads_default_to_half_a_unit() -> None:
    components_and_leads = (
        (PortTerminal(unit_length=2.0), "stub"),
        (FloatingParallelLC(unit_length=2.0), "terminal_stub"),
        (PiSectionChain(unit_length=2.0), "port_stub"),
        (PointCoupledReadoutPurcell(unit_length=2.0), "port_stub"),
        (ReadoutLineHangingQWRMTL(unit_length=2.0), "port_stub"),
        (ReadoutPurcellHangingQWRMTL(unit_length=2.0), "port_stub"),
        (CoupledLineLadderSection(unit_length=2.0), "port_stub"),
        (InterdigitatedCapacitor(unit_length=2.0), "port_stub"),
    )

    for component, lead_attribute in components_and_leads:
        assert getattr(component, lead_attribute) == pytest.approx(0.5 * component.unit_length)


def test_reusable_component_port50_loads_default_to_seven_tenths_of_a_unit() -> None:
    unit_length = 2.0
    grounded = GroundedLCResonator(
        unit_length=unit_length,
        port_label=r"$P_1$",
        resistance_label=r"$R_{50}$",
    )
    coupled = CapacitivelyCoupledGroundedLCResonator(unit_length=unit_length)
    floating_xy = FloatingLCXYResonator(unit_length=unit_length)
    loads = (
        Port50Ohm(unit_length=unit_length),
        grounded.port,
        coupled.port,
        floating_xy.pad1_port_terminal,
        floating_xy.pad2_port_terminal,
        floating_xy.xy_port_terminal,
    )

    for load in loads:
        assert isinstance(load, Port50Ohm)
        assert load.stub == pytest.approx(0.7 * unit_length)
    assert public_terminal_point(grounded, "left") == pytest.approx(
        public_terminal_point(grounded.port, "signal", transformed=True)
    )


def test_port50_geometry_and_electrical_metadata_contract() -> None:
    unit_length = 4.0
    terminal = PortTerminal(unit_length=unit_length)
    port = Port50Ohm(unit_length=unit_length)

    assert terminal.stub_units == 0.5
    assert terminal.anchors["terminal"] == pytest.approx((0.5 * unit_length, 0))
    assert terminal.public_terminals == {
        "signal": TerminalSpec("port", "terminal", "right"),
        "circuit": TerminalSpec("port", "node", "left"),
    }
    assert port.stub_units == 0.7
    assert port.load_lead_units == 0.25
    assert port.anchors["node"] == pytest.approx((0, 0))
    assert port.anchors["terminal"] == pytest.approx((0.7 * unit_length, 0))
    assert port.anchors["res_top"] == pytest.approx((0, -0.25 * unit_length))
    assert port.anchors["res_bot"] == pytest.approx((0, -unit_length))
    assert port.physical_nodes == {
        "port": ["node", "terminal", "res_top"],
        "gnd": ["res_bot", "gnd"],
    }
    assert port.ports == {"signal": "port"}
    assert port.public_terminals == {
        "signal": TerminalSpec("port", "terminal", "right"),
        "circuit": TerminalSpec("port", "node", "left"),
    }
    assert port.buses == {
        "stub": BusSpec("port", ("node", "terminal")),
        "load_lead": BusSpec("port", ("node", "res_top")),
    }


@pytest.mark.parametrize("load_lead_units", (-0.1, 0, 1.0, 1.1))
def test_port50_rejects_load_lead_outside_its_height(load_lead_units: float) -> None:
    with pytest.raises(
        ValueError,
        match=r"requires 0 < load_lead_units < height_units",
    ):
        Port50Ohm(height_units=1.0, load_lead_units=load_lead_units)


@pytest.mark.parametrize("unit_length", (1.5, 3.0, 6.0))
@pytest.mark.parametrize(("side", "sign"), (("left", -1), ("right", 1)))
def test_port50_terminal_clears_resistor_bbox_by_half_a_unit(
    unit_length: float,
    side: Literal["left", "right"],
    sign: int,
) -> None:
    port = Port50Ohm(
        unit_length=unit_length,
        side=side,
        show_labels=False,
    )
    resistor_bbox = port.resistor.get_bbox(transform=True, includetext=False)
    occupied_edge = resistor_bbox.xmin if sign < 0 else resistor_bbox.xmax
    clearance = sign * (port.anchors["terminal"][0] - occupied_edge)

    assert clearance >= 0.5 * unit_length


def test_d3_port50_resistor_glyphs_end_at_their_ground_anchors() -> None:
    for component_type in (
        D3IntrinsicPurcellEquivalentCircuitPlan,
        D3IntrinsicPurcellHybridizedCircuitPlan,
    ):
        component = component_type(unit_length=1.5, show_labels=False)
        for port in (component.input_port, component.output_port):
            assert port.height_units == 1.0
            assert tuple(port.resistor.absanchors["end"]) == pytest.approx(port.anchors["gnd"])


@pytest.mark.parametrize("module_path", EXECUTABLE_COMPONENT_MODULES)
def test_component_modules_are_directly_executable(module_path: str, tmp_path: Path) -> None:
    output_dir = tmp_path / Path(module_path).stem

    subprocess.run(
        [
            sys.executable,
            str(ROOT / module_path),
            "--no-show",
            "--theme",
            "both",
            "--unit-length",
            "1.25",
            "--save",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert list(output_dir.glob("*.light.svg"))
    assert list(output_dir.glob("*.dark.svg"))
    assert list(output_dir.glob("*.light.png"))
    assert list(output_dir.glob("*.dark.png"))


def _render_component(
    stem: str,
    factory: ComponentFactory,
    theme: Theme,
    output_dir: Path,
) -> elm.ElementCompound:
    unit_length = 2.0
    color = theme_color(theme)
    with schemdraw.Drawing(show=False, transparent=True, dpi=96) as drawing:
        drawing.config(unit=unit_length, color=color, lw=1.8, fontsize=12)
        component = drawing.add(factory(theme))

    drawing.save(str(output_dir / f"{stem}.{theme}.svg"), transparent=True)
    drawing.save(str(output_dir / f"{stem}.{theme}.png"), transparent=True, dpi=96)
    plt.close("all")
    return cast(elm.ElementCompound, component)


def _metadata(
    component: elm.ElementCompound,
) -> tuple[tuple[tuple[str, object], ...], object, object, object]:
    return (
        tuple((name, component.anchors[name]) for name in sorted(component.anchors)),
        component.physical_nodes,
        component.ports,
        getattr(component, "labels", {}),
    )


@pytest.mark.parametrize(("stem", "component_kind", "factory"), COMPONENT_CASES)
def test_reusable_components_keep_metadata_stable_across_themes(
    stem: str,
    component_kind: str,
    factory: ComponentFactory,
    tmp_path: Path,
) -> None:
    light = _render_component(stem, factory, "light", tmp_path)
    dark = _render_component(stem, factory, "dark", tmp_path)

    assert light.component_kind == component_kind
    assert _metadata(light) == _metadata(dark)
    assert light.physical_nodes
    assert light.ports

    for theme in ("light", "dark"):
        assert (tmp_path / f"{stem}.{theme}.svg").exists()
        assert (tmp_path / f"{stem}.{theme}.png").exists()


def test_grounded_lc_resonator_contract() -> None:
    resonator = _grounded_lc("light")

    assert GroundedLCResonator.component_kind == "GroundedLCResonator"
    assert resonator.unit_length == 3.0
    assert resonator.spacing_units == 1.0
    assert resonator.height_units == 1.0
    assert resonator.spacing == resonator.unit_length
    assert resonator.height == resonator.unit_length
    assert resonator.c_label == r"$C_{r}$"
    assert resonator.branch_label == r"$L_{r}$"
    assert isinstance(resonator.port, PortTerminal)
    assert resonator.anchors["signal"] != resonator.anchors["cap_top"]
    assert not hasattr(resonator, "signal_dot")
    assert not hasattr(resonator, "cap_top_dot")
    assert not hasattr(resonator, "ind_top_dot")
    assert public_terminal_point(resonator, "left") == pytest.approx(
        public_terminal_point(resonator.port, "signal", transformed=True)
    )
    assert resonator.physical_nodes == {
        "signal": ["start", "end", "signal", "cap_top", "ind_top"],
        "gnd": ["cap_bot", "ind_bot", "gnd"],
    }
    assert resonator.buses["signal"].anchors[0] == "start"


def test_capacitively_coupled_grounded_lc_node_policy() -> None:
    resonator = _capacitively_coupled_grounded_lc("light")
    without_nodes = CapacitivelyCoupledGroundedLCResonator(show_nodes=False)

    assert (
        resonator.anchors["resonator"][0]
        < resonator.anchors["branch_top"][0]
        < resonator.anchors["port_node"][0]
        < resonator.anchors["port_terminal"][0]
    )
    assert resonator.port.load_direction == "down"
    assert not hasattr(resonator, "resonator_dot")
    assert not hasattr(resonator, "branch_top_dot")
    assert not hasattr(resonator.port, "node_dot")
    assert not hasattr(without_nodes, "branch_top_dot")
    assert not hasattr(without_nodes.port, "node_dot")


def test_floating_lc_xy_tile_and_node_policy() -> None:
    resonator = _floating_lc_xy("light")

    assert (
        resonator.anchors["pad1_port"][0]
        < resonator.anchors["pad1_port_node"][0]
        < resonator.anchors["pad1"][0]
        < resonator.anchors["c_q_top"][0]
        < resonator.anchors["inductance_loop_top"][0]
        < resonator.anchors["top_bus_end"][0]
        < resonator.anchors["xy"][0]
        < resonator.anchors["xy_port_node"][0]
        < resonator.anchors["xy_port"][0]
    )
    assert resonator.pad1_port_terminal.load_direction == "up"
    assert resonator.pad2_port_terminal.load_direction == "down"
    assert resonator.xy_port_terminal.load_direction == "down"
    assert all(
        not hasattr(resonator, dot)
        for dot in ("pad1_dot", "pad2_dot", "c_q_top_dot", "c_q_bot_dot", "xy_dot")
    )
    assert not hasattr(resonator.pad1_port_terminal, "node_dot")
    assert not hasattr(resonator.parallel_inductor_branch, "top_dot")


def test_inductance_loop_attributes_match_element_kind() -> None:
    linear = _inductance_loop_linear("light")
    josephson = _inductance_loop_josephson("light")

    assert isinstance(linear.left_inductor, elm.Inductor)
    assert not hasattr(linear, "left_junction")
    assert isinstance(josephson.left_junction, elm.Josephson)
    assert not hasattr(josephson, "left_inductor")


def test_upward_grounds_use_half_turn_orientation() -> None:
    assert (
        Port50Ohm(load_direction="up").ground.transform.theta,
        FloatingLCResonator().ground_upper.transform.theta,
        FloatingLCXYResonator().ground1.transform.theta,
    ) == (180, 180, 180)


@pytest.mark.parametrize(
    ("fixture", "expected_kind", "expected_branch_kind"),
    (
        (
            "docs/assets/circuit_draw/pluto_examples/grounded_lc_resonator/schematic_export.json",
            "GroundedLCResonator",
            "linear",
        ),
        (
            "docs/assets/circuit_draw/pluto_examples/reflective_jpa_capacitive_coupled_lc/schematic_export.json",
            "CapacitivelyCoupledGroundedLCResonator",
            "josephson",
        ),
        (
            "docs/assets/circuit_draw/pluto_examples/floating_lc_xy_line/schematic_export.json",
            "FloatingLCXYResonator",
            "linear",
        ),
    ),
)
def test_renderer_adapter_consumes_core_schematic_export(
    fixture: str,
    expected_kind: str,
    expected_branch_kind: str,
    tmp_path: Path,
) -> None:
    export_data = load_schematic_export(ROOT / fixture)
    render_hints = cast(dict[str, object], export_data["render_hints"])
    schemdraw_hints = cast(dict[str, object], render_hints["schemdraw"])
    parameters = cast(dict[str, object], schemdraw_hints["parameters"])

    assert schemdraw_hints["component_type"] == expected_kind
    assert parameters["inductive_branch_kind"] == expected_branch_kind

    rendered: list[elm.ElementCompound] = []
    for theme in ("light", "dark"):
        with schemdraw.Drawing(show=False, transparent=True, dpi=96) as drawing:
            drawing.config(unit=2.0, color=theme_color(theme), lw=1.8, fontsize=12)
            component = add_schematic_export_to_drawing(drawing, export_data, theme=theme)
        drawing.save(str(tmp_path / f"{expected_kind}.{theme}.svg"), transparent=True)
        plt.close("all")
        rendered.append(component)

    assert rendered[0].component_kind == expected_kind
    assert _metadata(rendered[0]) == _metadata(rendered[1])
    if expected_branch_kind == "josephson":
        assert any(
            relation["relation_type"] == "josephson_junction"
            for relation in export_data["relations"]
        )
        assert isinstance(rendered[0].inductive_branch.branch, elm.Josephson)


def test_grounded_lc_renderer_preserves_port_labels() -> None:
    fixture = (
        ROOT / "docs/assets/circuit_draw/pluto_examples/grounded_lc_resonator/schematic_export.json"
    )
    with schemdraw.Drawing(show=False, transparent=True) as drawing:
        component = add_schematic_export_to_drawing(
            drawing,
            load_schematic_export(fixture),
            theme="light",
        )

    assert isinstance(component, GroundedLCResonator)
    assert isinstance(component.port, Port50Ohm)
    assert component.port.load_direction == "down"
    assert component.port.labels == {"port": r"$P_1$", "resistance": r"$R_{50}$"}
    assert not hasattr(component, "signal_dot")


def test_renderer_adapter_rejects_unknown_component_type() -> None:
    export_data = {
        "render_hints": {
            "schemdraw": {
                "component_type": "UnknownVisual",
                "labels": {},
                "parameters": {"component_id": "unknown"},
            }
        }
    }

    with (
        schemdraw.Drawing(show=False, transparent=True) as drawing,
        pytest.raises(UnsupportedSchematicComponentError),
    ):
        add_schematic_export_to_drawing(drawing, export_data, theme="light")
