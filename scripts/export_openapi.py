#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from src.app.tooling.openapi_snapshot import export_openapi_snapshot

    parser = argparse.ArgumentParser(description="Export the backend OpenAPI snapshot.")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root / "openapi.json",
        help="Path to the checked-in OpenAPI snapshot.",
    )
    args = parser.parse_args()
    output_path = args.output.resolve()
    export_openapi_snapshot(output_path)
    print(f"[openapi-export] wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
