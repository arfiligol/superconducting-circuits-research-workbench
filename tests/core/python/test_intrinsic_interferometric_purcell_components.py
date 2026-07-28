from __future__ import annotations

import json
from pathlib import Path

import schemdraw
import schemdraw.elements as elm
from schemdraw_circuit_library import (
    InterdigitatedCapacitor,
    IntrinsicInterferometricPurcellFilter,
    IntrinsicInterferometricPurcellFilterEquivalent,
    IntrinsicInterferometricPurcellFilterEquivalentWithQubit,
    IntrinsicInterferometricPurcellFilterWithQubit,
)
from schemdraw_circuit_library.rendering import add_schematic_export_to_drawing

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "docs/assets/circuit_draw/reusable_components"


def test_accepted_reusable_component_exports_and_mappings() -> None:
    cases = (
        (
            "interdigitated_capacitor",
            InterdigitatedCapacitor,
            {"terminal_1", "terminal_2"},
        ),
        (
            "intrinsic_interferometric_purcell_filter",
            IntrinsicInterferometricPurcellFilter,
            {"readout_attachment", "feedline_attachment"},
        ),
        (
            "intrinsic_interferometric_purcell_filter_with_qubit",
            IntrinsicInterferometricPurcellFilterWithQubit,
            {"island_1", "island_2", "feedline_attachment"},
        ),
        (
            "intrinsic_interferometric_purcell_filter_equivalent",
            IntrinsicInterferometricPurcellFilterEquivalent,
            {"readout_attachment", "feedline_attachment"},
        ),
        (
            "intrinsic_interferometric_purcell_filter_equivalent_with_qubit",
            IntrinsicInterferometricPurcellFilterEquivalentWithQubit,
            {"island_1", "island_2", "feedline_attachment"},
        ),
    )

    for directory, component_type, expected_ports in cases:
        export_data = json.loads((ASSETS / directory / "schematic_export.json").read_text())
        assert export_data["ports"] == []
        with schemdraw.Drawing(show=False, transparent=True) as drawing:
            component = add_schematic_export_to_drawing(
                drawing,
                export_data,
                theme="light",
            )
        assert isinstance(component, component_type)
        assert set(component.ports) == expected_ports

    idc_export = json.loads(
        (ASSETS / "interdigitated_capacitor/schematic_export.json").read_text()
    )
    assert [
        (relation["id"], relation["from"], relation["to"])
        for relation in idc_export["relations"]
    ] == [
        ("feedline_idc_c1g", "terminal_1", "ground"),
        ("feedline_idc_c2g", "terminal_2", "ground"),
        ("feedline_idc_c12", "terminal_1", "terminal_2"),
    ]

    for directory in (
        "intrinsic_interferometric_purcell_filter_with_qubit",
        "intrinsic_interferometric_purcell_filter_equivalent_with_qubit",
    ):
        export_data = json.loads((ASSETS / directory / "schematic_export.json").read_text())
        linearized = [
            relation
            for relation in export_data["relations"]
            if relation["role"] == "floating_qubit_linearized_josephson_inductance"
        ]
        assert [
            (relation["relation_type"], relation["parameters"]["schematic_kind"])
            for relation in linearized
        ] == [("series", "inductor"), ("series", "inductor")]
        with schemdraw.Drawing(show=False, transparent=True) as drawing:
            component = add_schematic_export_to_drawing(drawing, export_data, theme="light")
        branch = component.qubit_block.inductive_branch
        assert branch.branch_kind == "linearized_josephson"
        assert isinstance(branch.left_inductor, elm.Inductor)
        assert isinstance(branch.right_inductor, elm.Inductor)
