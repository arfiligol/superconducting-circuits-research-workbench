#!/usr/bin/env python3
"""Validate Astro Starlight documentation source and built routes."""

from __future__ import annotations

import argparse
import re
from pathlib import Path, PurePosixPath

DOCS_ROOT = Path("docs")
BUILT_DOCS_ROOT = Path("site/dist/docs")
SIDEBAR_CONFIG = Path("site/astro.config.mjs")
EXCLUDED_DIRS = {"api-reference", "site"}
SOURCE_SUFFIXES = {".md", ".mdx"}
LEGACY_VISUAL_SYNTAX_RE = re.compile(r'^\s*(?:!!!|\?\?\?|===\s+")|<div class="grid cards"')
SIDEBAR_SLUG_RE = re.compile(r'slug:\s*"([^"]+)"')
SIDEBAR_AUTOGENERATE_RE = re.compile(r'directory:\s*"([^"]+)"')


def _should_skip(path: Path) -> bool:
    relative = path.relative_to(DOCS_ROOT)
    return any(part in EXCLUDED_DIRS or part.startswith("docs_") for part in relative.parts)


def _source_markup_paths() -> list[Path]:
    paths: list[Path] = []
    for path in sorted(p for suffix in SOURCE_SUFFIXES for p in DOCS_ROOT.rglob(f"*{suffix}")):
        if _should_skip(path):
            continue
        paths.append(path)
    return paths


def _source_route(path: Path) -> PurePosixPath:
    return PurePosixPath(path.relative_to(DOCS_ROOT).as_posix())


def _expected_built_html_path(path: Path) -> Path:
    relative = _source_route(path)
    if relative.name in {"index.md", "index.mdx"}:
        if str(relative.parent) == ".":
            return BUILT_DOCS_ROOT / "index.html"
        return BUILT_DOCS_ROOT / Path(relative.parent.as_posix()) / "index.html"
    return BUILT_DOCS_ROOT / Path(relative.with_suffix("").as_posix()) / "index.html"


def _docs_route_slug(path: Path) -> str:
    relative = _source_route(path)
    route = PurePosixPath("docs") / relative
    route = route.parent if relative.name in {"index.md", "index.mdx"} else route.with_suffix("")
    return route.as_posix()


def _sidebar_coverage() -> tuple[set[str], set[str]]:
    if not SIDEBAR_CONFIG.is_file():
        return set(), set()
    config = SIDEBAR_CONFIG.read_text(encoding="utf-8")
    slugs = set(SIDEBAR_SLUG_RE.findall(config))
    autogenerate_dirs = set(SIDEBAR_AUTOGENERATE_RE.findall(config))
    return slugs, autogenerate_dirs


def _is_route_in_sidebar(route: str, slugs: set[str], autogenerate_dirs: set[str]) -> bool:
    if route in slugs:
        return True
    return any(
        route == directory or route.startswith(f"{directory}/") for directory in autogenerate_dirs
    )


def _check_source() -> list[str]:
    errors: list[str] = []
    slugs, autogenerate_dirs = _sidebar_coverage()
    if not slugs and not autogenerate_dirs:
        errors.append(
            f"[SOURCE] missing or unreadable sidebar config '{SIDEBAR_CONFIG.as_posix()}'"
        )
    if not any((DOCS_ROOT / f"index{suffix}").is_file() for suffix in SOURCE_SUFFIXES):
        errors.append("[SOURCE] missing docs/index.md or docs/index.mdx")
    if not _source_markup_paths():
        errors.append("[SOURCE] no Markdown docs found under docs/")
    for path in _source_markup_paths():
        route = _docs_route_slug(path)
        if not _is_route_in_sidebar(route, slugs, autogenerate_dirs):
            errors.append(
                "[SOURCE] docs page is not reachable from Starlight sidebar "
                f"route '{route}' from '{path.as_posix()}'"
            )
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if LEGACY_VISUAL_SYNTAX_RE.search(line):
                errors.append(
                    f"[SOURCE] forbidden legacy visual syntax in '{path.as_posix()}:{line_number}'"
                )
    return errors


def _check_built() -> list[str]:
    errors: list[str] = []
    for path in _source_markup_paths():
        expected = _expected_built_html_path(path)
        if not expected.is_file():
            errors.append(
                f"[BUILT] missing '{expected.as_posix()}' (from source '{path.as_posix()}')"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        action="append",
        dest="configs",
        help="Ignored compatibility option retained for old workflow invocations.",
    )
    parser.add_argument(
        "--check-source",
        action="store_true",
        help="Validate docs source files.",
    )
    parser.add_argument(
        "--check-built",
        action="store_true",
        help="Validate built Starlight HTML files under site/dist/docs/.",
    )
    args = parser.parse_args()

    check_source = args.check_source or not (args.check_source or args.check_built)
    check_built = args.check_built or not (args.check_source or args.check_built)

    errors: list[str] = []
    if check_source:
        errors.extend(_check_source())
    if check_built:
        errors.extend(_check_built())

    if errors:
        print("Docs route validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Docs route validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
