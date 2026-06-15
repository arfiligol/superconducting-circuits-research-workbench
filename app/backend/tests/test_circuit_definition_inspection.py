import json

from app_backend.domain.circuit_definition_inspection import (
    DEFAULT_PREVIEW_ARTIFACTS,
    ValidationNotice,
    inspect_circuit_definition_source,
)


def test_inspection_returns_structured_summary_for_valid_netlist() -> None:
    inspection = inspect_circuit_definition_source(
        json.dumps(
            {
                "name": "SmokeStableSeriesLC",
                "components": [
                    {"name": "R1", "default": 50.0, "unit": "Ohm"},
                    {"name": "C1", "default": 100.0, "unit": "fF"},
                    {"name": "Lj1", "default": 1000.0, "unit": "pH"},
                    {"name": "C2", "default": 1000.0, "unit": "fF"},
                ],
                "topology": [
                    ["P1", "1", "0", 1],
                    ["R1", "1", "0", "R1"],
                    ["C1", "1", "2", "C1"],
                    ["Lj1", "2", "0", "Lj1"],
                    ["C2", "2", "0", "C2"],
                ],
            }
        )
    )

    assert inspection.circuit_name == "SmokeStableSeriesLC"
    assert inspection.family == "jpa"
    assert inspection.element_count == 5
    assert inspection.preview_artifacts == DEFAULT_PREVIEW_ARTIFACTS
    assert inspection.summary.status == "valid"
    assert inspection.summary.component_count == 4
    assert inspection.summary.topology_count == 5
    assert inspection.summary.parameter_count == 0
    assert inspection.summary.port_count == 1
    assert inspection.summary.error_count == 0
    assert inspection.diagnostics == ()
    assert inspection.validation_notices == (
        ValidationNotice(level="ok", message="Circuit netlist passes canonical inspection."),
        ValidationNotice(
            level="ok",
            message="Normalized output is aligned with the canonical circuit-netlist contract.",
        ),
    )
    assert inspection.normalized_payload["topology"][0] == ["P1", "1", "0", 1]
    assert '"name": "SmokeStableSeriesLC"' in inspection.normalized_output


def test_inspection_reports_missing_required_blocks() -> None:
    inspection = inspect_circuit_definition_source(json.dumps({"name": "OnlyName"}))

    assert inspection.circuit_name == "OnlyName"
    assert inspection.summary.status == "invalid"
    assert inspection.summary.error_count == 2
    assert {diagnostic.code for diagnostic in inspection.diagnostics} == {
        "NETLIST_COMPONENTS_MISSING",
        "NETLIST_TOPOLOGY_MISSING",
    }
    assert all(diagnostic.blocking for diagnostic in inspection.diagnostics)


def test_inspection_reports_component_parameter_reference_failures() -> None:
    inspection = inspect_circuit_definition_source(
        json.dumps(
            {
                "name": "BadReferences",
                "parameters": [{"name": "Lj", "default": 1000.0, "unit": "nH"}],
                "components": [
                    {"name": "Lj1", "value_ref": "Lj", "unit": "pH"},
                    {"name": "C1", "value_ref": "Cj", "unit": "fF"},
                ],
                "topology": [["Lj1", "1", "0", "Lj1"], ["C1", "1", "0", "C1"]],
            }
        )
    )

    assert inspection.summary.status == "invalid"
    assert inspection.summary.error_count == 2
    assert [diagnostic.code for diagnostic in inspection.diagnostics] == [
        "COMPONENT_PARAMETER_UNIT_MISMATCH",
        "PARAMETER_REFERENCE_UNDEFINED",
    ]
    assert inspection.validation_notices[0].level == "warning"


def test_inspection_reports_topology_contract_failures_with_machine_codes() -> None:
    inspection = inspect_circuit_definition_source(
        json.dumps(
            {
                "name": "BadTopology",
                "components": [
                    {"name": "R1", "default": 50.0, "unit": "Ohm"},
                    {"name": "K1", "default": 0.1, "unit": "H"},
                ],
                "topology": [
                    ["P1", "1", "gnd", 1],
                    ["R1", "1", "2", "MissingComponent"],
                    ["K1", "R1", "L2", "K1"],
                ],
            }
        )
    )

    assert inspection.summary.status == "invalid"
    assert {diagnostic.code for diagnostic in inspection.diagnostics} == {
        "UNSUPPORTED_GROUND_ALIAS",
        "TOPOLOGY_COMPONENT_REFERENCE_UNDEFINED",
        "MUTUAL_COUPLING_ELEMENT_NON_INDUCTIVE",
    }


def test_inspection_preserves_compatibility_family_hint_when_present() -> None:
    inspection = inspect_circuit_definition_source(
        json.dumps(
            {
                "name": "FamilyHinted",
                "family": "fluxonium",
                "components": [{"name": "R1", "default": 50.0, "unit": "Ohm"}],
                "topology": [["R1", "1", "0", "R1"]],
            }
        )
    )

    assert inspection.family == "fluxonium"
    assert "family" not in inspection.normalized_payload
