from __future__ import annotations

from pathlib import Path
from typing import cast

import matplotlib
import schemdraw
from schemdraw_circuit_library import GroundedLCResonator, theme_color
from schemdraw_circuit_library.theme import Theme

matplotlib.use("Agg")


def _render_grounded_lc(theme: Theme, output_dir: Path) -> GroundedLCResonator:
    unit_length = 3.0
    color = theme_color(theme)
    with schemdraw.Drawing(show=False, transparent=True, dpi=96) as drawing:
        drawing.config(unit=unit_length, color=color, lw=1.8, fontsize=12)
        resonator = drawing.add(
            GroundedLCResonator(
                component_id="resonator",
                name="r",
                unit_length=unit_length,
                theme=theme,
                port_label=r"$P_1$",
            )
        )

    drawing.save(str(output_dir / f"grounded_lc.{theme}.svg"), transparent=True)
    drawing.save(str(output_dir / f"grounded_lc.{theme}.png"), transparent=True, dpi=96)
    return cast(GroundedLCResonator, resonator)


def _metadata(component: GroundedLCResonator) -> tuple[tuple[str, ...], object, object]:
    return (
        tuple(sorted(component.anchors)),
        component.physical_nodes,
        component.ports,
    )


def test_grounded_lc_resonator_theme_metadata_is_stable(tmp_path: Path) -> None:
    light = _render_grounded_lc("light", tmp_path)
    dark = _render_grounded_lc("dark", tmp_path)

    assert GroundedLCResonator.component_kind == "GroundedLCResonator"
    assert light.unit_length == 3.0
    assert light.spacing_units == 1.0
    assert light.height_units == 1.0
    assert light.port_stub_units == 0.5
    assert light.spacing == light.unit_length
    assert light.height == light.unit_length
    assert light.port_stub == light.unit_length / 2
    assert light.c_label == r"$C_{r}$"
    assert light.l_label == r"$L_{r}$"
    assert light.port_label == r"$P_1$"
    assert light.physical_nodes == {
        "signal": ["port", "signal", "cap_top", "ind_top"],
        "gnd": ["cap_bot", "ind_bot", "gnd"],
    }
    assert light.ports == {"signal": "signal"}
    assert _metadata(light) == _metadata(dark)

    for theme in ("light", "dark"):
        assert (tmp_path / f"grounded_lc.{theme}.svg").exists()
        assert (tmp_path / f"grounded_lc.{theme}.png").exists()
