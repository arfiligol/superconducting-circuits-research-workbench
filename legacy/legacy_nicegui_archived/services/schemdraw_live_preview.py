"""Helpers for Schemdraw code execution and SVG rendering in WebUI live preview."""

from __future__ import annotations

import ast
import builtins
import contextlib
import inspect
import io
import json
import multiprocessing
import re
from collections.abc import Callable
from dataclasses import dataclass

import schemdraw
import schemdraw.elements as elm

_SVG_VIEWBOX_PATTERN = re.compile(
    r'height="([0-9.eE+-]+)pt"\s+width="([0-9.eE+-]+)pt"\s+'
    r'viewBox="([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)"'
)

_ALLOWED_BUILTINS: dict[str, object] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}
_ALLOWED_IMPORTS = {
    "math",
    "schemdraw",
    "schemdraw.elements",
}
_FORBIDDEN_CALL_NAMES = {
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "setattr",
    "vars",
}
_FORBIDDEN_NODE_TYPES = (
    ast.AsyncFor,
    ast.AsyncFunctionDef,
    ast.AsyncWith,
    ast.Await,
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Lambda,
    ast.Nonlocal,
    ast.Raise,
    ast.Try,
    ast.While,
    ast.With,
    ast.Yield,
    ast.YieldFrom,
)
_MAX_SOURCE_CHARS = 20_000
_RENDER_TIMEOUT_SECONDS = 2.5


def parse_relation_config_text(config_text: str) -> dict[str, object]:
    """Parse relation JSON text; return empty dict for blank input."""
    stripped = config_text.strip()
    if not stripped:
        return {}

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Relation config must be valid JSON: {exc.msg}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Relation config must be a JSON object.")

    return parsed


def build_relation_context(
    *,
    schema_id: int | None,
    schema_name: str | None,
    config: dict[str, object],
) -> dict[str, object]:
    """Build relation context payload injected into user Schemdraw code."""
    return {
        "schema": {
            "id": schema_id,
            "name": schema_name,
        },
        "config": config,
    }


def _add_svg_padding(svg_text: str, pad_pt: float = 12.0) -> str:
    """Expand SVG bounds to reduce edge clipping around labels and strokes."""
    match = _SVG_VIEWBOX_PATTERN.search(svg_text)
    if match is None:
        return svg_text

    height = float(match.group(1))
    width = float(match.group(2))
    x0 = float(match.group(3))
    y0 = float(match.group(4))
    view_w = float(match.group(5))
    view_h = float(match.group(6))

    replacement = (
        f'height="{height + 2 * pad_pt}pt" '
        f'width="{width + 2 * pad_pt}pt" '
        f'viewBox="{x0 - pad_pt} {y0 - pad_pt} {view_w + 2 * pad_pt} {view_h + 2 * pad_pt}"'
    )
    return _SVG_VIEWBOX_PATTERN.sub(replacement, svg_text, count=1)


def _call_build_drawing(
    builder: Callable[..., object],
    relation_context: dict[str, object],
) -> object:
    """Call build_drawing with optional context argument based on signature."""
    try:
        parameter_count = len(inspect.signature(builder).parameters)
    except (TypeError, ValueError):
        parameter_count = 1

    if parameter_count == 0:
        return builder()
    return builder(relation_context)


def _resolve_drawing_from_scope(
    *,
    exec_locals: dict[str, object],
    relation_context: dict[str, object],
) -> schemdraw.Drawing:
    """Resolve the drawing object from executed source scope."""
    builder_obj = exec_locals.get("build_drawing")
    drawing_candidate: object

    if callable(builder_obj):
        drawing_candidate = _call_build_drawing(builder_obj, relation_context)
    else:
        drawing_candidate = exec_locals.get("d")

    if not isinstance(drawing_candidate, schemdraw.Drawing):
        raise ValueError(
            "Code must define `d` as schemdraw.Drawing or a `build_drawing(relation)` function "
            "returning schemdraw.Drawing."
        )

    return drawing_candidate


@dataclass(frozen=True)
class SchemdrawRenderResult:
    """One Schemdraw preview render result."""

    svg_content: str
    pen_position: tuple[float, float] | None
    probe_points: list[tuple[str, tuple[float, float]]]
    stdout_text: str


def _safe_import(
    name: str,
    globals_dict: dict[str, object] | None = None,
    locals_dict: dict[str, object] | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> object:
    """Allow imports only from an explicit safe allowlist."""
    if level != 0:
        raise ImportError("Relative imports are not allowed.")
    if name not in _ALLOWED_IMPORTS:
        raise ImportError(f"Import '{name}' is not allowed.")
    return builtins.__import__(name, globals_dict, locals_dict, fromlist, level)


def _validate_source_safety(source_text: str) -> None:
    """Validate source code against a conservative Python subset for preview."""
    if len(source_text) > _MAX_SOURCE_CHARS:
        raise ValueError(f"Source is too long (max {_MAX_SOURCE_CHARS} characters).")

    try:
        tree = ast.parse(source_text, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"Python syntax error at line {exc.lineno}: {exc.msg}") from exc

    for node in ast.walk(tree):
        if isinstance(node, _FORBIDDEN_NODE_TYPES):
            raise ValueError(f"Unsupported syntax in preview sandbox: {type(node).__name__}.")

        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in _ALLOWED_IMPORTS:
                    raise ValueError(f"Import '{alias.name}' is not allowed.")

        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if module_name not in _ALLOWED_IMPORTS:
                raise ValueError(f"Import from '{module_name}' is not allowed.")

        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("Dunder names are not allowed in preview sandbox.")

        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise ValueError("Dunder attribute access is not allowed in preview sandbox.")

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in _FORBIDDEN_CALL_NAMES
        ):
            raise ValueError(f"Call to '{node.func.id}' is not allowed in preview sandbox.")


def _extract_pen_position(drawing: schemdraw.Drawing) -> tuple[float, float] | None:
    """Extract drawing cursor position (`d.here`) as a simple xy tuple."""
    here = getattr(drawing, "here", None)
    if here is None:
        return None

    if hasattr(here, "x") and hasattr(here, "y"):
        try:
            return (float(here.x), float(here.y))
        except (TypeError, ValueError):
            return None

    if isinstance(here, tuple | list) and len(here) >= 2:
        try:
            return (float(here[0]), float(here[1]))
        except (TypeError, ValueError):
            return None

    return None


def _render_schemdraw_source_once(
    source_text: str,
    *,
    relation_context: dict[str, object],
) -> SchemdrawRenderResult:
    """Execute one validated Schemdraw source snippet and return preview result."""
    _validate_source_safety(source_text)

    pen_probes: list[tuple[str, tuple[float, float]]] = []

    def probe_here(drawing: object, label: str = "") -> tuple[float, float] | None:
        """Record one pen/cursor position for learning/debug probes."""
        if not isinstance(drawing, schemdraw.Drawing):
            raise ValueError("probe_here expects a schemdraw.Drawing instance as first argument.")

        position = _extract_pen_position(drawing)
        if position is None:
            return None

        probe_label = str(label).strip() or f"probe_{len(pen_probes) + 1}"
        pen_probes.append((probe_label, position))
        return position

    exec_globals = {
        "__builtins__": {
            **_ALLOWED_BUILTINS,
            "__import__": _safe_import,
        },
        "schemdraw": schemdraw,
        "elm": elm,
        "elements": elm,
        "relation": relation_context,
        "probe_here": probe_here,
    }
    exec_locals: dict[str, object] = {}

    stdout_buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stdout_buffer):
            exec(
                compile(source_text, "<schemdraw-live-preview>", "exec"),
                exec_globals,
                exec_locals,
            )
    except Exception as exc:
        raise ValueError(f"Schemdraw code execution failed: {exc}") from exc

    drawing = _resolve_drawing_from_scope(
        exec_locals=exec_locals,
        relation_context=relation_context,
    )

    try:
        svg_bytes = drawing.get_imagedata("svg")
    except Exception as exc:
        raise ValueError(f"Failed to export Schemdraw SVG: {exc}") from exc

    return SchemdrawRenderResult(
        svg_content=_add_svg_padding(svg_bytes.decode("utf-8")),
        pen_position=_extract_pen_position(drawing),
        probe_points=pen_probes,
        stdout_text=stdout_buffer.getvalue().strip(),
    )


def _render_worker(
    source_text: str,
    relation_context: dict[str, object],
    queue: multiprocessing.Queue[dict[str, str | None]],
) -> None:
    """Run untrusted user source in a subprocess and return result via queue."""
    try:
        result = _render_schemdraw_source_once(
            source_text,
            relation_context=relation_context,
        )
    except Exception as exc:
        queue.put({"ok": "0", "error": str(exc)})
        return

    payload: dict[str, str | None] = {
        "ok": "1",
        "svg": result.svg_content,
        "stdout": result.stdout_text,
        "probes_json": json.dumps(
            [
                {"label": label, "x": position[0], "y": position[1]}
                for label, position in result.probe_points
            ],
            ensure_ascii=True,
        ),
        "pen_x": None,
        "pen_y": None,
    }
    if result.pen_position is not None:
        payload["pen_x"] = f"{result.pen_position[0]:.4f}"
        payload["pen_y"] = f"{result.pen_position[1]:.4f}"
    queue.put(payload)


def render_schemdraw_preview(
    source_text: str,
    *,
    relation_context: dict[str, object] | None = None,
) -> SchemdrawRenderResult:
    """Execute one Schemdraw source snippet in a subprocess and return preview result."""
    normalized_relation_context = relation_context or {
        "schema": {"id": None, "name": None},
        "config": {},
    }

    context = multiprocessing.get_context("spawn")
    queue: multiprocessing.Queue[dict[str, str | None]] = context.Queue(maxsize=1)
    process = context.Process(
        target=_render_worker,
        args=(source_text, normalized_relation_context, queue),
    )
    process.start()
    process.join(timeout=_RENDER_TIMEOUT_SECONDS)

    if process.is_alive():
        process.terminate()
        process.join()
        raise ValueError(
            f"Render timed out after {_RENDER_TIMEOUT_SECONDS:.1f}s. "
            "Please simplify the code and try again."
        )

    if queue.empty():
        raise ValueError("Render process failed without returning a result.")

    result = queue.get()
    if result.get("ok") != "1":
        error_text = str(result.get("error", "Unknown render error."))
        raise ValueError(error_text)

    pen_position: tuple[float, float] | None = None
    pen_x = result.get("pen_x")
    pen_y = result.get("pen_y")
    if pen_x is not None and pen_y is not None:
        pen_position = (float(pen_x), float(pen_y))

    probe_points: list[tuple[str, tuple[float, float]]] = []
    probes_json = result.get("probes_json")
    if probes_json:
        try:
            parsed_probes = json.loads(probes_json)
            if isinstance(parsed_probes, list):
                for item in parsed_probes:
                    if not isinstance(item, dict):
                        continue
                    label = str(item.get("label", "")).strip() or f"probe_{len(probe_points) + 1}"
                    raw_x = item.get("x")
                    raw_y = item.get("y")
                    if raw_x is None or raw_y is None:
                        continue
                    x_val = float(raw_x)
                    y_val = float(raw_y)
                    probe_points.append((label, (x_val, y_val)))
        except Exception:
            probe_points = []

    return SchemdrawRenderResult(
        svg_content=str(result.get("svg", "")),
        pen_position=pen_position,
        probe_points=probe_points,
        stdout_text=str(result.get("stdout", "") or ""),
    )


def render_schemdraw_source(
    source_text: str,
    *,
    relation_context: dict[str, object] | None = None,
) -> str:
    """Execute one Schemdraw source snippet in a subprocess and return SVG."""
    return render_schemdraw_preview(
        source_text,
        relation_context=relation_context,
    ).svg_content
