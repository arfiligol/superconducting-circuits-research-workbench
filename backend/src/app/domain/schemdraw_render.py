from dataclasses import dataclass
from typing import Literal

SchemdrawRenderStatus = Literal["rendered", "blocked", "syntax_error", "runtime_error"]
SchemdrawRenderMode = Literal["debounced", "manual"]
SchemdrawDiagnosticSeverity = Literal["error", "warning", "info"]
SchemdrawDiagnosticSource = Literal[
    "request",
    "relation_config",
    "python_syntax",
    "render_runtime",
]


@dataclass(frozen=True)
class SchemdrawLinkedSchema:
    definition_id: str
    workspace_id: str
    name: str
    source_hash: str | None = None


@dataclass(frozen=True)
class SchemdrawRenderRequest:
    source_text: str
    relation_config: dict[str, object]
    linked_schema: SchemdrawLinkedSchema | None
    document_version: int
    request_id: str
    render_mode: SchemdrawRenderMode


@dataclass(frozen=True)
class SchemdrawDiagnostic:
    severity: SchemdrawDiagnosticSeverity
    code: str
    message: str
    source: SchemdrawDiagnosticSource
    blocking: bool
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class SchemdrawPreviewMetadata:
    width: int
    height: int
    view_box: str
    source_line_count: int
    linked_definition_id: str | None


@dataclass(frozen=True)
class SchemdrawCursorPosition:
    x: float
    y: float


@dataclass(frozen=True)
class SchemdrawProbePoint:
    name: str
    x: float
    y: float


@dataclass(frozen=True)
class SchemdrawRenderResult:
    request_id: str
    document_version: int
    status: SchemdrawRenderStatus
    svg: str | None
    diagnostics: tuple[SchemdrawDiagnostic, ...]
    cursor_position: SchemdrawCursorPosition | None
    probe_points: tuple[SchemdrawProbePoint, ...]
    render_time_ms: float | None
    preview_metadata: SchemdrawPreviewMetadata | None
