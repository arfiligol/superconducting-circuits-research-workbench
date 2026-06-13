from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import matplotlib
import pytest
import schemdraw
import schemdraw.elements as elm
from schemdraw_circuit_library import (
    CoupledLineLadderSection,
    FloatingLCXYResonator,
    GroundedLCResonator,
    PiSectionChain,
    PointCoupledReadoutPurcell,
    ReadoutLineHangingQWRMTL,
    ReadoutPurcellHangingQWRMTL,
    ReflectiveJPACapacitiveCoupledLC,
    TransmissionLineSegment,
    theme_color,
)
from schemdraw_circuit_library.theme import Theme

matplotlib.use("Agg")

ComponentFactory = Callable[[Theme], elm.ElementCompound]


def _grounded_lc(theme: Theme) -> GroundedLCResonator:
    return GroundedLCResonator(
        component_id="resonator",
        name="r",
        unit_length=3.0,
        theme=theme,
        port_label=r"$P_1$",
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


def _reflective_jpa(theme: Theme) -> ReflectiveJPACapacitiveCoupledLC:
    return ReflectiveJPACapacitiveCoupledLC(
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
    ("grounded_lc", "GroundedLCResonator", _grounded_lc),
    ("floating_lc_xy", "FloatingLCXYResonator", _floating_lc_xy),
    ("reflective_jpa", "ReflectiveJPACapacitiveCoupledLC", _reflective_jpa),
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
    return cast(elm.ElementCompound, component)


def _metadata(
    component: elm.ElementCompound,
) -> tuple[tuple[tuple[str, object], ...], object, object]:
    return (
        tuple((name, component.anchors[name]) for name in sorted(component.anchors)),
        component.physical_nodes,
        component.ports,
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
    assert resonator.port_stub_units == 0.5
    assert resonator.spacing == resonator.unit_length
    assert resonator.height == resonator.unit_length
    assert resonator.port_stub == resonator.unit_length / 2
    assert resonator.c_label == r"$C_{r}$"
    assert resonator.l_label == r"$L_{r}$"
    assert resonator.port_label == r"$P_1$"
