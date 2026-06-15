#!/usr/bin/env python3
"""Ensure App-owned docs stay in the Product App documentation lane."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("docs")
SUFFIXES = {".md", ".mdx"}
SKIP_PREFIXES = (
    Path("docs/app"),
    Path("docs/api-reference"),
    Path("docs/docs_zhtw"),
    Path("docs/site"),
    Path("docs/reference/guardrails"),
    Path("docs/reference/api"),
)
SKIP_FILES = {Path("docs/index.mdx")}

ALLOWED_BOUNDARY_PHRASES = (
    "not belong",
    "不屬於",
    "outside this section",
    "live outside",
    "stay outside",
    "kept outside",
    "does not",
    "do not",
    "must not",
    "not a public",
    "not expose",
    "separate concerns",
    "separate concern",
    "boundary",
)

APP_ONLY_PATTERNS = (
    re.compile(r"\bProduct App\b"),
    re.compile(r"\bProduct Async\b"),
    re.compile(r"\bSchema Editor\b"),
    re.compile(r"\bResultView\b"),
    re.compile(r"\bTraceStore\b"),
    re.compile(r"\bFastAPI\b"),
    re.compile(r"\bBackend\b"),
    re.compile(r"\bFrontend\b"),
    re.compile(r"\bDesktop\b"),
    re.compile(r"\bElectron\b"),
    re.compile(r"\bWebUI\b"),
    re.compile(r"\bApplication Interface\b"),
    re.compile(r"\bApplication task\b"),
    re.compile(r"\bApplication Data\b"),
    re.compile(r"\bApplication Simulation\b"),
    re.compile(r"\bApplication Analysis\b"),
    re.compile(r"\bApplication-triggered\b"),
    re.compile(r"\bData Browser\b"),
    re.compile(r"\bData Search\b"),
    re.compile(r"\bData Ingestion\b"),
    re.compile(r"\bData Management\b"),
    re.compile(r"\bTask / Execution\b"),
    re.compile(r"(?<![\w.-])app/"),
    re.compile(r"(?<![\w.-])backend/"),
    re.compile(r"(?<![\w.-])frontend/"),
)


def _is_skipped(path: Path) -> bool:
    if path in SKIP_FILES:
        return True
    return any(path == prefix or prefix in path.parents for prefix in SKIP_PREFIXES)


def _source_paths() -> list[Path]:
    if not ROOT.exists():
        return []
    return sorted(
        path for path in ROOT.rglob("*") if path.suffix in SUFFIXES and not _is_skipped(path)
    )


def _is_allowed_boundary_line(line: str) -> bool:
    lowered = line.lower()
    return any(phrase in lowered for phrase in ALLOWED_BOUNDARY_PHRASES)


def main() -> int:
    errors: list[str] = []
    for path in _source_paths():
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for pattern in APP_ONLY_PATTERNS:
                if pattern.search(line):
                    if _is_allowed_boundary_line(line):
                        continue
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
