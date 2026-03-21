#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "backend"))

    from src.app.tooling.openapi_snapshot import check_openapi_snapshot_drift

    parser = argparse.ArgumentParser(
        description="Check whether the checked-in OpenAPI snapshot is stale.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=repo_root / "openapi.json",
        help="Path to the checked-in OpenAPI snapshot.",
    )
    args = parser.parse_args()

    report = check_openapi_snapshot_drift(args.snapshot.resolve())
    if report.is_current:
        print(f"[openapi-check] snapshot is current: {report.snapshot_path}")
        return 0

    print(f"[openapi-check] snapshot drift detected: {report.snapshot_path}")
    for line in report.diff_preview:
        print(line)
    if len(report.diff_preview) == 0:
        print("[openapi-check] snapshot content differs, but no diff preview was generated")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
