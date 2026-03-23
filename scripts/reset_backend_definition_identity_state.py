#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from core.shared.persistence.trace_store import get_trace_store_path
    from src.app.infrastructure.audit_store import (
        bootstrap_audit_store,
        resolve_audit_database_path,
    )
    from src.app.infrastructure.persistence.database import (
        bootstrap_metadata_schema,
        resolve_metadata_database_path,
    )
    from src.app.infrastructure.runtime import reset_runtime_state
    from src.app.settings import get_settings

    reset_runtime_state()
    settings = get_settings()
    metadata_database_path = resolve_metadata_database_path(settings.database_path)
    audit_database_path = resolve_audit_database_path(settings.audit_database_path)
    trace_store_path = get_trace_store_path()

    removed_paths: list[str] = []
    missing_paths: list[str] = []
    for path in (metadata_database_path, audit_database_path, trace_store_path):
        if path.is_dir():
            shutil.rmtree(path)
            removed_paths.append(str(path))
            continue
        if path.exists():
            path.unlink()
            removed_paths.append(str(path))
            continue
        missing_paths.append(str(path))

    bootstrap_metadata_schema(settings.database_path)
    bootstrap_audit_store(settings.audit_database_path)
    reset_runtime_state()

    print("[definition-identity-reset] completed")
    print(f"[definition-identity-reset] metadata_db={metadata_database_path}")
    print(f"[definition-identity-reset] audit_db={audit_database_path}")
    print(f"[definition-identity-reset] trace_store={trace_store_path}")
    if removed_paths:
        print("[definition-identity-reset] removed:")
        for path in removed_paths:
            print(f"  - {path}")
    if missing_paths:
        print("[definition-identity-reset] already_missing:")
        for path in missing_paths:
            print(f"  - {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
