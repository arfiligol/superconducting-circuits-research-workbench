#!/usr/bin/env python3
"""Fail when editable docs source contains non-English CJK text."""

from __future__ import annotations

import re
from pathlib import Path

CJK_RE = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]")
SUFFIXES = {".md", ".mdx", ".rst"}

DOCS_ROOT = Path("docs")
ALLOWLIST_PATH = Path("scripts/check_docs_language_allowlist.txt")
SOURCE_FILES = [Path("site/astro.config.mjs")]
SOURCE_ROOTS = [Path(".agent/rules")]
SKIP_PREFIXES = (
    Path("docs/api-reference"),
    Path("docs/docs_zhtw"),
    Path("docs/site"),
    Path("site/src/content/docs/docs"),
)


def _is_skipped(path: Path) -> bool:
    return any(path == prefix or prefix in path.parents for prefix in SKIP_PREFIXES)


def _iter_sources() -> list[Path]:
    paths: list[Path] = []
    if DOCS_ROOT.exists():
        paths.extend(
            path
            for path in DOCS_ROOT.rglob("*")
            if path.suffix in SUFFIXES and not _is_skipped(path)
        )
    for root in SOURCE_ROOTS:
        if root.exists():
            paths.extend(path for path in root.rglob("*.md") if not _is_skipped(path))
    paths.extend(path for path in SOURCE_FILES if path.exists())
    return sorted(set(paths))


def _load_allowlist() -> dict[str, set[str]]:
    allowlist: dict[str, set[str]] = {}
    if not ALLOWLIST_PATH.exists():
        return allowlist
    for line_number, raw_line in enumerate(
        ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines(), 1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise SystemExit(
                f"{ALLOWLIST_PATH.as_posix()}:{line_number}: expected '<path-or-*>:<literal>'"
            )
        path_pattern, literal = line.split(":", 1)
        path_pattern = path_pattern.strip()
        literal = literal.strip()
        if not path_pattern or not literal:
            raise SystemExit(
                f"{ALLOWLIST_PATH.as_posix()}:{line_number}: expected '<path-or-*>:<literal>'"
            )
        allowlist.setdefault(path_pattern, set()).add(literal)
    return allowlist


def _is_allowed(path: Path, line: str, allowlist: dict[str, set[str]]) -> bool:
    path_key = path.as_posix()
    literals = set(allowlist.get("*", set()))
    literals.update(allowlist.get(path_key, set()))
    return any(literal in line for literal in literals)


def main() -> int:
    errors: list[str] = []
    allowlist = _load_allowlist()
    for path in _iter_sources():
        if path.name.endswith(".en.md"):
            errors.append(
                f"{path.as_posix()}: language-specific docs suffix is not allowed; use .md or .mdx"
            )
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CJK_RE.search(line) and not _is_allowed(path, line, allowlist):
                errors.append(f"{path.as_posix()}:{line_number}: contains non-English CJK text")

    if errors:
        print("Docs language check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Docs language check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
