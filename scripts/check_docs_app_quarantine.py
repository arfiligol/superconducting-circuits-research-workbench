#!/usr/bin/env python3
"""Ensure research-first docs do not expose Product App implementation workflow."""

from __future__ import annotations

import re
from pathlib import Path

ROOTS = (Path("docs/start"), Path("docs/workflows"), Path("docs/concepts"))
SUFFIXES = {".md", ".mdx"}

APP_ONLY_PATTERNS = (
    re.compile(r"\bProduct App\b"),
    re.compile(r"\bProduct Async\b"),
    re.compile(r"\bSchema Editor\b"),
    re.compile(r"\bResultView\b"),
    re.compile(r"\bTraceStore\b"),
    re.compile(r"\bFastAPI\b"),
    re.compile(r"\bBackend\b"),
    re.compile(r"\bFrontend\b"),
    re.compile(r"\bWebUI\b"),
    re.compile(r"\bApplication Interface\b"),
    re.compile(r"\bApplication task\b"),
    re.compile(r"\bApplication Data\b"),
    re.compile(r"\bApplication Simulation\b"),
    re.compile(r"\bApplication-triggered\b"),
    re.compile(r"(?<![\w.-])app/"),
    re.compile(r"(?<![\w.-])backend/"),
    re.compile(r"(?<![\w.-])frontend/"),
)


def _source_paths() -> list[Path]:
    paths: list[Path] = []
    for root in ROOTS:
        if not root.exists():
            continue
        paths.extend(sorted(path for path in root.rglob("*") if path.suffix in SUFFIXES))
    return paths


def main() -> int:
    errors: list[str] = []
    for path in _source_paths():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in APP_ONLY_PATTERNS:
                if pattern.search(line):
                    errors.append(
                        f"{path.as_posix()}:{line_number}: app-only docs term "
                        f"'{pattern.pattern}' belongs under docs/app/"
                    )
                    break

    if errors:
        print("Docs App quarantine check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Docs App quarantine check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
