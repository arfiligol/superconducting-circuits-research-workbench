"""Tests for Schemdraw live-preview execution helpers."""

from legacy.legacy_nicegui_archived.services.schemdraw_live_preview import (
    build_relation_context,
    parse_relation_config_text,
    render_schemdraw_preview,
    render_schemdraw_source,
)


def test_parse_relation_config_text_returns_empty_dict_for_blank_input() -> None:
    assert parse_relation_config_text("") == {}
    assert parse_relation_config_text("   ") == {}


def test_parse_relation_config_text_rejects_non_object_json() -> None:
    try:
        parse_relation_config_text('["not", "an", "object"]')
    except ValueError as exc:
        assert "JSON object" in str(exc)
    else:
        raise AssertionError("Expected ValueError for non-object relation config")


def test_build_relation_context_includes_schema_metadata_and_config() -> None:
    context = build_relation_context(
        schema_id=12,
        schema_name="Test Schema",
        config={"tag": "draft"},
    )

    assert context["schema"] == {"id": 12, "name": "Test Schema"}
    assert context["config"] == {"tag": "draft"}


def test_render_schemdraw_source_from_d_variable_returns_svg() -> None:
    source = """
import schemdraw
import schemdraw.elements as elm

d = schemdraw.Drawing(canvas="svg", show=False)
d += elm.Resistor().label("R1")
"""

    svg = render_schemdraw_source(source)

    assert "<svg" in svg.lower()
    assert "R1" in svg


def test_render_schemdraw_source_supports_build_drawing_contract() -> None:
    source = """
import schemdraw
import schemdraw.elements as elm

def build_drawing(relation):
    d = schemdraw.Drawing(canvas="svg", show=False)
    d += elm.Line().right().length(1)
    d += elm.Label().at((0, 0.6)).label(relation["config"]["tag"])
    return d
"""
    relation_context = build_relation_context(
        schema_id=7,
        schema_name="Relation Demo",
        config={"tag": "manual-link"},
    )

    svg = render_schemdraw_source(source, relation_context=relation_context)

    assert "<svg" in svg.lower()
    assert "manual-link" in svg


def test_render_schemdraw_source_requires_drawing_output() -> None:
    source = "value = 1 + 1"

    try:
        render_schemdraw_source(source)
    except ValueError as exc:
        assert "Code must define `d`" in str(exc)
    else:
        raise AssertionError("Expected ValueError when drawing output is missing")


def test_render_schemdraw_preview_returns_pen_cursor_and_stdout() -> None:
    source = """
import schemdraw
import schemdraw.elements as elm

d = schemdraw.Drawing(canvas="svg", show=False)
d += elm.Line().right().length(2)
print(d.here)
"""

    result = render_schemdraw_preview(source)

    assert "<svg" in result.svg_content.lower()
    assert result.pen_position is not None
    assert result.pen_position[0] > 0
    assert "2" in result.stdout_text


def test_render_schemdraw_preview_collects_probe_points() -> None:
    source = """
import schemdraw
import schemdraw.elements as elm

d = schemdraw.Drawing(canvas="svg", show=False)
d += elm.Line().right().length(1.5)
probe_here(d, "after_right")
d += elm.Line().down().length(0.5)
probe_here(d, "after_down")
"""

    result = render_schemdraw_preview(source)

    assert len(result.probe_points) == 2
    assert result.probe_points[0][0] == "after_right"
    assert result.probe_points[1][0] == "after_down"
    assert result.probe_points[0][1][0] > 0


def test_render_schemdraw_source_rejects_unsafe_imports() -> None:
    source = """import os

import schemdraw
d = schemdraw.Drawing(canvas="svg", show=False)
"""

    try:
        render_schemdraw_source(source)
    except ValueError as exc:
        assert "Import 'os' is not allowed." in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsafe import")


def test_render_schemdraw_source_recovers_after_failed_render() -> None:
    unsafe_source = """import subprocess
"""
    good_source = """
import schemdraw
import schemdraw.elements as elm

d = schemdraw.Drawing(canvas="svg", show=False)
d += elm.Resistor().label("R2")
"""

    try:
        render_schemdraw_source(unsafe_source)
    except ValueError:
        pass
    else:
        raise AssertionError("Expected failure for unsafe source")

    svg = render_schemdraw_source(good_source)
    assert "<svg" in svg.lower()
    assert "R2" in svg
