from __future__ import annotations

import io
import logging

from src.app.infrastructure.request_debug import (
    RequestDebugFormatter,
    bind_request_debug_context,
    reset_request_debug_context,
)


def test_request_debug_formatter_fills_missing_fields_for_child_logger_records() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        RequestDebugFormatter(
            "%(levelname)s %(name)s [corr=%(correlation_id)s debug=%(debug_ref)s] %(message)s"
        )
    )

    logger = logging.getLogger("tests.request_debug.child")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)

    logger.info("child logger record")

    output = stream.getvalue()
    assert "child logger record" in output
    assert "corr=req" not in output
    assert "corr=corr:req:unbound" in output
    assert "debug=debug:req:unbound" in output


def test_request_debug_formatter_uses_bound_request_context() -> None:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        RequestDebugFormatter(
            "%(levelname)s %(name)s [corr=%(correlation_id)s debug=%(debug_ref)s] %(message)s"
        )
    )

    logger = logging.getLogger("tests.request_debug.bound")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)

    binding = bind_request_debug_context(
        correlation_id="corr:req:test-case",
        debug_ref="debug:req:test-case",
    )
    try:
        logger.info("bound logger record")
    finally:
        reset_request_debug_context(binding)

    output = stream.getvalue()
    assert "bound logger record" in output
    assert "corr=corr:req:test-case" in output
    assert "debug=debug:req:test-case" in output
