"""Fail when active code or tooling treats archived code as active."""

from __future__ import annotations

import re
import sys
import tomllib
from collections.abc import Iterator
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVED_DIR = REPO_ROOT / "archived"
SELF = Path(__file__).resolve()

SKIP_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".playwright-mcp",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".worktrees",
    "__pycache__",
    "archived",
    "docs_zhtw",
    "node_modules",
    "site",
}
TEXT_SUFFIXES = {
    ".cfg",
    ".css",
    ".jl",
    ".js",
    ".json",
    ".md",
    ".mdx",
    ".py",
    ".rst",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"\bfrom\s+archived\b"),
    re.compile(r"\bimport\s+archived\b"),
    re.compile(r"archived[/\\]"),
)


def main() -> int:
    failures: list[str] = []
    if not ARCHIVED_DIR.is_dir():
        failures.append("archived/ directory is missing.")

    failures.extend(_check_root_pyproject())
    failures.extend(_check_active_text_references())

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Archive quarantine checks passed.")
    return 0


def _check_root_pyproject() -> list[str]:
    pyproject_path = REPO_ROOT / "pyproject.toml"
    payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    failures: list[str] = []

    workspace_members = (
        payload.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    )
    for member in workspace_members:
        if _contains_archived_path(member):
            failures.append(f"{pyproject_path}: workspace member points at archived code: {member}")

    pyright = payload.get("tool", {}).get("basedpyright", {})
    for key in ("include", "extraPaths"):
        for path in pyright.get(key, []):
            if _contains_archived_path(path):
                failures.append(
                    f"{pyproject_path}: basedpyright {key} points at archived code: {path}"
                )

    ruff = payload.get("tool", {}).get("ruff", {})
    for path in ruff.get("src", []):
        if _contains_archived_path(path):
            failures.append(f"{pyproject_path}: ruff src points at archived code: {path}")

    return failures


def _check_active_text_references() -> list[str]:
    failures: list[str] = []
    for path in _iter_active_files():
        if path.resolve() == SELF:
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Makefile"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in FORBIDDEN_TEXT_PATTERNS:
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                rel = path.relative_to(REPO_ROOT)
                failures.append(f"{rel}:{line}: active file references archived quarantine")
    return failures


def _iter_active_files() -> Iterator[Path]:
    for root, dirnames, filenames in REPO_ROOT.walk(top_down=True):
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in SKIP_DIR_NAMES and not dirname.endswith(".egg-info")
        ]
        for filename in filenames:
            yield root / filename


def _contains_archived_path(value: object) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.replace("\\", "/").strip("/")
    return normalized == "archived" or normalized.startswith("archived/")


if __name__ == "__main__":
    raise SystemExit(main())
