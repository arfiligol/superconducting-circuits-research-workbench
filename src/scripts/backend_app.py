from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = str(os.getenv("SC_APP_HOST", "127.0.0.1") or "127.0.0.1").strip() or "127.0.0.1"
    port = int(os.getenv("SC_APP_PORT", "8000"))
    reload = str(os.getenv("SC_APP_RELOAD", "0")).strip().lower() in {"1", "true", "yes", "on"}

    uvicorn.run(
        "src.app.main:app",
        host=host,
        port=port,
        reload=reload,
    )
