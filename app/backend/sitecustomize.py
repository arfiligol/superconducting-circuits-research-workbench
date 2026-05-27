from __future__ import annotations

import sys
from pathlib import Path


def _prepend_path(path: Path) -> None:
    resolved = str(path.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


_BACKEND_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_ROOT.parent

# Backend standalone `uv run ...` needs both package roots:
# - repo root for `core.*`
# - `core/` for `sc_core.*`
_prepend_path(_REPO_ROOT)
_prepend_path(_REPO_ROOT / "core")
