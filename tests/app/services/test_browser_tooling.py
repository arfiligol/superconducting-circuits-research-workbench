"""Tests for browser-side helper command builders."""

from legacy.legacy_nicegui_archived.services.browser_tooling import (
    build_schema_formatter_hotkey_js,
    build_schema_formatter_js,
    build_schematic_preview_action_js,
    build_schematic_preview_render_js,
    shared_frontend_tooling_head_html,
)


def test_shared_frontend_tooling_head_html_includes_helpers() -> None:
    """Shared head HTML should expose both preview and formatter helpers."""
    head_html = shared_frontend_tooling_head_html()

    assert "window.scCircuitPreview" in head_html
    assert "window.scSchemaFormatter" in head_html
    assert "@astral-sh/ruff-wasm-web" in head_html
    assert "@panzoom/panzoom" not in head_html
    assert "parseViewBox" in head_html
    assert "buildViewBoxForZoom" in head_html
    assert "fitPreview(state)" in head_html
    assert "panPreviewByPixels" in head_html
    assert "event.shiftKey" in head_html
    assert "const MAX_ZOOM = 20.0;" in head_html


def test_build_schematic_preview_render_js_escapes_payload() -> None:
    """Render command should serialize the payload as JSON."""
    command = build_schematic_preview_render_js(
        root_id="preview-root",
        label_id="preview-label",
        svg_content='<svg viewBox="0 0 10 10"></svg>',
        schema_key='schema:"demo"',
        empty_html="<div>Invalid</div>",
    )

    assert "window.scCircuitPreview?.render(" in command
    assert '"rootId": "preview-root"' in command
    assert '"labelId": "preview-label"' in command
    assert '\\"demo\\"' in command
    assert '"emptyHtml": "<div>Invalid</div>"' in command


def test_build_schematic_preview_action_js_validates_action() -> None:
    """Only supported preview actions should be accepted."""
    assert "zoomIn" in build_schematic_preview_action_js(action="zoomIn", root_id="preview-root")

    try:
        build_schematic_preview_action_js(action="invalid", root_id="preview-root")
    except ValueError as exc:
        assert "Unsupported preview action" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported preview action")


def test_build_schema_formatter_commands_reference_shared_helpers() -> None:
    """Formatter JS builders should call the shared browser helper methods."""
    format_command = build_schema_formatter_js("print('hello')")
    hotkey_command = build_schema_formatter_hotkey_js(
        button_id="format-button",
        scope_id="editor-scope",
    )

    assert "window.scSchemaFormatter?.format" in format_command
    assert "print('hello')" in format_command
    assert "window.scSchemaFormatter?.attachHotkey" in hotkey_command
    assert '"format-button"' in hotkey_command
    assert '"editor-scope"' in hotkey_command
