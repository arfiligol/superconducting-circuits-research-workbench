from __future__ import annotations

import ast
import builtins
from collections.abc import Mapping
from time import perf_counter
from traceback import extract_tb
from types import MappingProxyType
from typing import Protocol
from xml.etree import ElementTree

from src.app.domain.circuit_definitions import CircuitDefinitionRecord
from src.app.domain.schemdraw_render import (
    SchemdrawCursorPosition,
    SchemdrawDiagnostic,
    SchemdrawLinkedSchema,
    SchemdrawPreviewMetadata,
    SchemdrawProbePoint,
    SchemdrawRenderRequest,
    SchemdrawRenderResult,
)
from src.app.domain.session import SessionState
from src.app.services.service_errors import service_error


class SchemdrawDefinitionRepository(Protocol):
    def get_circuit_definition(self, definition_id: int) -> CircuitDefinitionRecord | None: ...


class SchemdrawSessionRepository(Protocol):
    def get_session_state(self) -> SessionState: ...


class SchemdrawRenderService:
    def __init__(
        self,
        *,
        definition_repository: SchemdrawDefinitionRepository,
        session_repository: SchemdrawSessionRepository,
    ) -> None:
        self._definition_repository = definition_repository
        self._session_repository = session_repository

    def render(self, request: SchemdrawRenderRequest) -> SchemdrawRenderResult:
        started_at = perf_counter()
        linked_schema = self._resolve_linked_schema(request.linked_schema)

        relation_diagnostics = _validate_relation_config(request.relation_config)
        if any(diagnostic.blocking for diagnostic in relation_diagnostics):
            return self._build_blocked_result(
                request=request,
                diagnostics=relation_diagnostics,
                render_time_ms=_elapsed_ms(started_at),
            )

        syntax_diagnostics, syntax_tree = _validate_python_source(request.source_text)
        if syntax_tree is None:
            return SchemdrawRenderResult(
                request_id=request.request_id,
                document_version=request.document_version,
                status="syntax_error",
                svg=None,
                diagnostics=syntax_diagnostics,
                cursor_position=_extract_cursor_position(request.relation_config),
                probe_points=_extract_probe_points(request.relation_config),
                render_time_ms=_elapsed_ms(started_at),
                preview_metadata=None,
            )

        runtime_diagnostics = _validate_render_entrypoint(syntax_tree)
        if any(diagnostic.blocking for diagnostic in runtime_diagnostics):
            return self._build_blocked_result(
                request=request,
                diagnostics=relation_diagnostics + runtime_diagnostics,
                render_time_ms=_elapsed_ms(started_at),
            )

        try:
            svg = _render_schemdraw_svg(
                source_text=request.source_text,
                relation_config=request.relation_config,
                linked_schema=linked_schema,
            )
        except SchemdrawRuntimeExecutionError as exc:
            return SchemdrawRenderResult(
                request_id=request.request_id,
                document_version=request.document_version,
                status="runtime_error",
                svg=None,
                diagnostics=relation_diagnostics
                + runtime_diagnostics
                + (
                    SchemdrawDiagnostic(
                        severity="error",
                        code="schemdraw_runtime_error",
                        message=exc.message,
                        source="render_runtime",
                        blocking=True,
                        line=exc.line,
                        column=exc.column,
                    ),
                ),
                cursor_position=_extract_cursor_position(request.relation_config),
                probe_points=_extract_probe_points(request.relation_config),
                render_time_ms=_elapsed_ms(started_at),
                preview_metadata=None,
            )
        preview_metadata = _extract_preview_metadata(
            svg,
            source_line_count=len(request.source_text.splitlines()),
            linked_definition_id=None if linked_schema is None else linked_schema.definition_id,
        )
        diagnostics = relation_diagnostics + runtime_diagnostics
        return SchemdrawRenderResult(
            request_id=request.request_id,
            document_version=request.document_version,
            status="rendered",
            svg=svg,
            diagnostics=diagnostics,
            cursor_position=_extract_cursor_position(request.relation_config),
            probe_points=_extract_probe_points(request.relation_config),
            render_time_ms=_elapsed_ms(started_at),
            preview_metadata=preview_metadata,
        )

    def _build_blocked_result(
        self,
        *,
        request: SchemdrawRenderRequest,
        diagnostics: tuple[SchemdrawDiagnostic, ...],
        render_time_ms: float,
    ) -> SchemdrawRenderResult:
        return SchemdrawRenderResult(
            request_id=request.request_id,
            document_version=request.document_version,
            status="blocked",
            svg=None,
            diagnostics=diagnostics,
            cursor_position=_extract_cursor_position(request.relation_config),
            probe_points=_extract_probe_points(request.relation_config),
            render_time_ms=render_time_ms,
            preview_metadata=None,
        )

    def _resolve_linked_schema(
        self,
        linked_schema: SchemdrawLinkedSchema | None,
    ) -> CircuitDefinitionRecord | None:
        if linked_schema is None:
            return None
        session = self._session_repository.get_session_state()
        definition = self._definition_repository.get_circuit_definition(linked_schema.definition_id)
        if definition is None:
            raise service_error(
                404,
                code="definition_not_found",
                category="not_found",
                message=f"Definition {linked_schema.definition_id} was not found.",
            )
        if definition.workspace_id != session.workspace_id:
            raise service_error(
                403,
                code="schemdraw_linked_schema_not_visible",
                category="permission_denied",
                message="The linked schema is not visible in the active workspace.",
            )
        if (
            definition.visibility_scope == "private"
            and definition.owner_user_id != _session_user_id(session)
        ):
            raise service_error(
                403,
                code="schemdraw_linked_schema_not_visible",
                category="permission_denied",
                message="The linked schema is not visible in the active workspace.",
            )
        if session.runtime_mode == "local" and definition.visibility_scope != "local":
            raise service_error(
                403,
                code="schemdraw_linked_schema_not_visible",
                category="permission_denied",
                message="The linked schema is not visible in the active workspace.",
            )
        return definition


def _validate_relation_config(
    relation_config: Mapping[str, object],
) -> tuple[SchemdrawDiagnostic, ...]:
    diagnostics: list[SchemdrawDiagnostic] = []
    labels = relation_config.get("labels")
    if labels is not None and (
        not isinstance(labels, Mapping)
        or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in labels.items()
        )
    ):
        diagnostics.append(
            SchemdrawDiagnostic(
                severity="error",
                code="schemdraw_relation_invalid",
                message="relation_config.labels must be a mapping of string to string.",
                source="relation_config",
                blocking=True,
            )
        )
    probe_points = relation_config.get("probe_points")
    if probe_points is not None and not isinstance(probe_points, list):
        diagnostics.append(
            SchemdrawDiagnostic(
                severity="error",
                code="schemdraw_relation_invalid",
                message="relation_config.probe_points must be a list when provided.",
                source="relation_config",
                blocking=True,
            )
        )
    return tuple(diagnostics)


def _validate_python_source(
    source_text: str,
) -> tuple[tuple[SchemdrawDiagnostic, ...], ast.Module | None]:
    try:
        return (), ast.parse(source_text)
    except SyntaxError as exc:
        message = exc.msg.strip() if isinstance(exc.msg, str) and len(exc.msg.strip()) > 0 else None
        return (
            (
                SchemdrawDiagnostic(
                    severity="error",
                    code="schemdraw_syntax_error",
                    message=(
                        f"Python syntax error: {message}"
                        if message is not None
                        else "Python syntax error."
                    ),
                    source="python_syntax",
                    blocking=True,
                    line=exc.lineno,
                    column=exc.offset,
                ),
            ),
            None,
        )


def _validate_render_entrypoint(
    syntax_tree: ast.Module,
) -> tuple[SchemdrawDiagnostic, ...]:
    allowed_imports = {"schemdraw", "schemdraw.elements"}
    diagnostics: list[SchemdrawDiagnostic] = []
    build_drawing_found = False

    for node in ast.walk(syntax_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in allowed_imports:
                    diagnostics.append(
                        SchemdrawDiagnostic(
                            severity="error",
                            code="schemdraw_runtime_error",
                            message=f"Import '{alias.name}' is not allowed in Schemdraw preview.",
                            source="render_runtime",
                            blocking=True,
                            line=node.lineno,
                            column=node.col_offset,
                        )
                    )
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module not in allowed_imports:
                diagnostics.append(
                    SchemdrawDiagnostic(
                        severity="error",
                        code="schemdraw_runtime_error",
                        message=f"Import from '{module}' is not allowed in Schemdraw preview.",
                        source="render_runtime",
                        blocking=True,
                        line=node.lineno,
                        column=node.col_offset,
                    )
                )
        if isinstance(node, ast.FunctionDef) and node.name == "build_drawing":
            build_drawing_found = True
            if len(node.args.args) != 1:
                diagnostics.append(
                    SchemdrawDiagnostic(
                        severity="error",
                        code="schemdraw_runtime_error",
                        message="build_drawing must accept exactly one relation argument.",
                        source="render_runtime",
                        blocking=True,
                        line=node.lineno,
                        column=node.col_offset,
                    )
                )

    if not build_drawing_found:
        diagnostics.append(
            SchemdrawDiagnostic(
                severity="error",
                code="schemdraw_runtime_error",
                message="Schemdraw source must define build_drawing(relation).",
                source="render_runtime",
                blocking=True,
            )
        )
    return tuple(diagnostics)


def _render_schemdraw_svg(
    *,
    source_text: str,
    relation_config: Mapping[str, object],
    linked_schema: CircuitDefinitionRecord | None,
) -> str:
    try:
        import matplotlib

        matplotlib.use("Agg", force=True)
    except Exception:
        pass
    code = compile(source_text, filename="<schemdraw-preview>", mode="exec")
    namespace: dict[str, object] = {
        "__builtins__": _safe_builtins(),
    }
    try:
        exec(code, namespace)
    except Exception as exc:
        raise _runtime_error_from_exception(exc) from exc
    build_drawing = namespace.get("build_drawing")
    if not callable(build_drawing):
        raise SchemdrawRuntimeExecutionError(
            message="Schemdraw source must define build_drawing(relation).",
        )

    relation = _freeze_relation_payload(relation_config, linked_schema)
    try:
        drawing = build_drawing(relation)
    except Exception as exc:
        raise _runtime_error_from_exception(exc) from exc

    get_imagedata = getattr(drawing, "get_imagedata", None)
    if not callable(get_imagedata):
        raise SchemdrawRuntimeExecutionError(
            message="build_drawing(relation) must return a schemdraw Drawing object.",
        )

    try:
        svg_bytes = get_imagedata("svg")
    except Exception as exc:
        raise _runtime_error_from_exception(exc) from exc

    svg = svg_bytes.decode("utf-8") if isinstance(svg_bytes, bytes) else str(svg_bytes)
    return _normalize_svg_markup(svg)


def _extract_preview_metadata(
    svg: str,
    *,
    source_line_count: int,
    linked_definition_id: int | None,
) -> SchemdrawPreviewMetadata:
    root = ElementTree.fromstring(svg)
    width = _svg_dimension_to_int(root.attrib.get("width", "0"))
    height = _svg_dimension_to_int(root.attrib.get("height", "0"))
    view_box = root.attrib.get("viewBox", "")
    return SchemdrawPreviewMetadata(
        width=width,
        height=height,
        view_box=view_box,
        source_line_count=source_line_count,
        linked_definition_id=linked_definition_id,
    )


def _extract_cursor_position(
    relation_config: Mapping[str, object],
) -> SchemdrawCursorPosition | None:
    raw_value = relation_config.get("cursor_position")
    if not isinstance(raw_value, Mapping):
        return None
    x = raw_value.get("x")
    y = raw_value.get("y")
    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
        return None
    return SchemdrawCursorPosition(x=float(x), y=float(y))


def _extract_probe_points(
    relation_config: Mapping[str, object],
) -> tuple[SchemdrawProbePoint, ...]:
    raw_value = relation_config.get("probe_points")
    if not isinstance(raw_value, list):
        return ()
    probe_points: list[SchemdrawProbePoint] = []
    for item in raw_value:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        x = item.get("x")
        y = item.get("y")
        if isinstance(name, str) and isinstance(x, (int, float)) and isinstance(y, (int, float)):
            probe_points.append(SchemdrawProbePoint(name=name, x=float(x), y=float(y)))
    return tuple(probe_points)


def _session_user_id(session: SessionState) -> str:
    return session.user.user_id if session.user is not None else "anonymous"


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)


class SchemdrawRuntimeExecutionError(Exception):
    def __init__(
        self,
        *,
        message: str,
        line: int | None = None,
        column: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


def _safe_builtins() -> dict[str, object]:
    allowed_names = {
        "abs",
        "bool",
        "dict",
        "enumerate",
        "float",
        "int",
        "len",
        "list",
        "max",
        "min",
        "range",
        "round",
        "set",
        "str",
        "sum",
        "tuple",
        "zip",
    }
    safe = {name: getattr(builtins, name) for name in allowed_names}
    safe["__import__"] = _restricted_import
    return safe


def _restricted_import(
    name: str,
    globals: object | None = None,
    locals: object | None = None,
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> object:
    if level != 0:
        raise ImportError("Relative imports are not allowed in Schemdraw preview.")
    if name not in {"schemdraw", "schemdraw.elements"}:
        raise ImportError(f"Import '{name}' is not allowed in Schemdraw preview.")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _freeze_relation_payload(
    relation_config: Mapping[str, object],
    linked_schema: CircuitDefinitionRecord | None,
) -> Mapping[str, object]:
    relation_payload = {
        **relation_config,
        "linked_schema": None
        if linked_schema is None
        else {
            "definition_id": linked_schema.definition_id,
            "workspace_id": linked_schema.workspace_id,
            "name": linked_schema.name,
            "visibility_scope": linked_schema.visibility_scope,
            "source_hash": linked_schema.source_hash,
        },
    }
    frozen = _freeze_value(relation_payload)
    if not isinstance(frozen, Mapping):
        raise ValueError("Frozen relation payload must remain a mapping.")
    return frozen


def _freeze_value(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_value(item) for item in value)
    return value


def _runtime_error_from_exception(exc: Exception) -> SchemdrawRuntimeExecutionError:
    line = None
    for frame in reversed(extract_tb(exc.__traceback__)):
        if frame.filename == "<schemdraw-preview>":
            line = frame.lineno
            break
    return SchemdrawRuntimeExecutionError(
        message=str(exc) or "Schemdraw preview execution failed.",
        line=line,
    )


def _normalize_svg_markup(svg: str) -> str:
    start = svg.find("<svg")
    if start < 0:
        raise SchemdrawRuntimeExecutionError(
            message="Schemdraw preview did not produce SVG output.",
        )
    return svg[start:].strip()


def _svg_dimension_to_int(raw_value: str) -> int:
    normalized = raw_value.strip().lower().removesuffix("px").removesuffix("pt")
    try:
        return round(float(normalized))
    except ValueError:
        return 0
