from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from dataclasses import dataclass
from secrets import token_urlsafe

logger = logging.getLogger(__name__)

REQUEST_DEBUG_LOG_FORMAT = (
    "%(levelname)s %(name)s [corr=%(correlation_id)s debug=%(debug_ref)s] %(message)s"
)

_CORRELATION_ID: ContextVar[str | None] = ContextVar("request_correlation_id", default=None)
_DEBUG_REF: ContextVar[str | None] = ContextVar("request_debug_ref", default=None)


@dataclass(frozen=True)
class RequestDebugBinding:
    correlation_token: Token[str | None]
    debug_ref_token: Token[str | None]


class RequestDebugFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = current_correlation_id()
        record.debug_ref = current_debug_ref()
        return True


class RequestDebugFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = current_correlation_id()
        if not hasattr(record, "debug_ref"):
            record.debug_ref = current_debug_ref()
        return super().format(record)


def configure_backend_logging() -> None:
    root_logger = logging.getLogger()
    if not _has_request_debug_filter(root_logger):
        root_logger.addFilter(RequestDebugFilter())
    if len(root_logger.handlers) == 0:
        handler = logging.StreamHandler()
        handler.setFormatter(RequestDebugFormatter(REQUEST_DEBUG_LOG_FORMAT))
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)
        return

    for handler in root_logger.handlers:
        formatter = handler.formatter
        if isinstance(formatter, RequestDebugFormatter):
            continue
        if formatter is None:
            handler.setFormatter(RequestDebugFormatter(REQUEST_DEBUG_LOG_FORMAT))
            continue
        format_string = getattr(formatter, "_fmt", "")
        if "%(correlation_id)" in format_string or "%(debug_ref)" in format_string:
            handler.setFormatter(RequestDebugFormatter(format_string))


def bind_request_debug_context(
    *,
    correlation_id: str | None = None,
    debug_ref: str | None = None,
) -> RequestDebugBinding:
    resolved_correlation_id = correlation_id or f"corr:req:{token_urlsafe(8)}"
    resolved_debug_ref = debug_ref or f"debug:req:{token_urlsafe(8)}"
    return RequestDebugBinding(
        correlation_token=_CORRELATION_ID.set(resolved_correlation_id),
        debug_ref_token=_DEBUG_REF.set(resolved_debug_ref),
    )


def reset_request_debug_context(binding: RequestDebugBinding) -> None:
    _CORRELATION_ID.reset(binding.correlation_token)
    _DEBUG_REF.reset(binding.debug_ref_token)


def current_correlation_id() -> str:
    return _CORRELATION_ID.get() or "corr:req:unbound"


def current_debug_ref() -> str:
    return _DEBUG_REF.get() or "debug:req:unbound"


def _has_request_debug_filter(logger_instance: logging.Logger) -> bool:
    return any(isinstance(log_filter, RequestDebugFilter) for log_filter in logger_instance.filters)
