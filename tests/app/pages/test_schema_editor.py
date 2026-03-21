"""Tests for Schema Editor source persistence and expanded preview helpers."""

from legacy.legacy_nicegui_archived.pages.schema_editor import _editor_text_from_record, _stored_schema_text_from_editor
from core.simulation.domain.circuit import (
    format_expanded_circuit_definition,
    parse_circuit_definition_source,
)


def test_stored_schema_text_from_editor_preserves_exact_editor_content() -> None:
    editor_text = """{
    "name": "RepeatExample",
    "components": [
        {"name": "R1", "default": 50.0, "unit": "Ohm"},
    ],
    "topology": [("P1", "1", "0", 1)],
}"""

    assert _stored_schema_text_from_editor(editor_text) == editor_text


def test_editor_text_from_record_preserves_saved_source_format() -> None:
    saved_text = """{'name': 'RepeatExample',
 'components': [{'name': 'R1', 'default': 50.0, 'unit': 'Ohm'}],
 'topology': [('P1', '1', '0', 1)]}"""

    assert _editor_text_from_record(saved_text) == saved_text


def test_parse_circuit_definition_rejects_legacy_value_alias() -> None:
    legacy_value_text = """{
    "name": "LegacyValue",
    "components": [{"name": "R1", "value": 50.0, "unit": "Ohm"}],
    "topology": [("P1", "1", "0", 1), ("R1", "1", "0", "R1")]
}"""

    try:
        parse_circuit_definition_source(legacy_value_text)
    except ValueError as exc:
        assert "exactly one of 'default' or 'value_ref'" in str(exc)
    else:
        raise AssertionError("Expected legacy 'value' alias to be rejected")


def test_parse_circuit_definition_rejects_legacy_gnd_alias() -> None:
    legacy_gnd_text = """{
    "name": "LegacyGround",
    "components": [{"name": "R1", "default": 50.0, "unit": "Ohm"}],
    "topology": [("P1", "1", "gnd", 1), ("R1", "1", "0", "R1")]
}"""

    try:
        parse_circuit_definition_source(legacy_gnd_text)
    except ValueError as exc:
        assert "Ground must be the string '0'" in str(exc)
    else:
        raise AssertionError("Expected legacy 'gnd' alias to be rejected")


def test_expanded_preview_formats_repeat_source() -> None:
    circuit = parse_circuit_definition_source(
        {
            "name": "PreviewRepeat",
            "components": [
                {
                    "repeat": {
                        "count": 2,
                        "index": "cell",
                        "symbols": {
                            "n": {"base": 1, "step": 1},
                            "n2": {"base": 2, "step": 1},
                        },
                        "emit": [
                            {"name": "L${n}_${n2}", "default": 10.0, "unit": "nH"},
                        ],
                    }
                }
            ],
            "topology": [
                ("P1", "1", "0", 1),
                {
                    "repeat": {
                        "count": 2,
                        "index": "cell",
                        "symbols": {
                            "n": {"base": 1, "step": 1},
                            "n2": {"base": 2, "step": 1},
                        },
                        "emit": [
                            ("L${n}_${n2}", "${n}", "${n2}", "L${n}_${n2}"),
                        ],
                    }
                },
            ],
        }
    )

    preview_text = format_expanded_circuit_definition(circuit)

    assert "L1_2" in preview_text
    assert "L2_3" in preview_text
    assert "'repeat'" not in preview_text
