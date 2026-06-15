from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

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
    GroundedLCResonator,
    InductanceLoop,
    InductiveBranch,
    PiSectionChain,
    PointCoupledReadoutPurcell,
    Port50Ohm,
    PortTerminal,
    ReadoutLineHangingQWRMTL,
    ReadoutPurcellHangingQWRMTL,
    TransmissionLineSegment,
    theme_color,
)
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
    assert resonator.physical_nodes == {
        "signal": ["signal", "cap_top", "ind_top"],
        "gnd": ["cap_bot", "ind_bot", "gnd"],
    }


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
