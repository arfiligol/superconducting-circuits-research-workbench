#!/usr/bin/env python3
"""Validate Zensical navigation routes against source docs and built HTML output."""

from __future__ import annotations

import argparse
import tomllib
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

DEFAULT_CONFIGS = ("zensical.toml",)


def _iter_nav_markdown_paths(node: Any) -> list[str]:
    paths: list[str] = []
    if isinstance(node, list):
        for item in node:
            paths.extend(_iter_nav_markdown_paths(item))
        return paths
    if isinstance(node, dict):
        for value in node.values():
            paths.extend(_iter_nav_markdown_paths(value))
        return paths
    if isinstance(node, str) and node.endswith(".md"):
        paths.append(node)
    return paths


def _load_config(config_path: Path) -> tuple[list[str], Path, str]:
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    nav = project.get("nav", [])
    site_dir = Path(str(project.get("site_dir", "docs/site")))
    site_prefix = urlparse(str(project.get("site_url", ""))).path.strip("/")
    paths = sorted(set(_iter_nav_markdown_paths(nav)))
    return paths, site_dir, site_prefix


def _expected_built_html_path(relative_md_path: str, *, site_dir: Path) -> Path:
    relative_md = PurePosixPath(relative_md_path)
    if relative_md.name == "index.md":
        if str(relative_md.parent) == ".":
            relative_html = PurePosixPath("index.html")
        else:
            relative_html = relative_md.parent / "index.html"
    else:
        relative_html = relative_md.with_suffix("") / "index.html"
    return site_dir / Path(relative_html.as_posix())


def _check_source(config_path: Path, *, nav_paths: list[str]) -> list[str]:
    missing: list[str] = []
    for relative_md_path in nav_paths:
        expected = Path("docs") / relative_md_path
        if not expected.exists():
            missing.append(
                f"[SOURCE] {config_path.name}: missing '{expected.as_posix()}' "
                f"(from nav '{relative_md_path}')"
            )
    return missing


def _check_built(config_path: Path, *, nav_paths: list[str], site_dir: Path) -> list[str]:
    missing: list[str] = []
    for relative_md_path in nav_paths:
        expected = _expected_built_html_path(relative_md_path, site_dir=site_dir)
        if not expected.exists():
            missing.append(
                f"[BUILT] {config_path.name}: missing '{expected.as_posix()}' "
                f"(from nav '{relative_md_path}')"
            )
    return missing


def _check_built_prefixed(
    config_path: Path,
    *,
    nav_paths: list[str],
    site_dir: Path,
    site_prefix: str,
) -> list[str]:
    if not site_prefix:
        return []
    missing: list[str] = []
    prefixed_site_dir = site_dir / site_prefix
    for relative_md_path in nav_paths:
        expected = _expected_built_html_path(relative_md_path, site_dir=prefixed_site_dir)
        if not expected.exists():
            missing.append(
                f"[BUILT-PREFIXED] {config_path.name}: missing '{expected.as_posix()}' "
                f"(from nav '{relative_md_path}')"
            )
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate nav routes in zensical*.toml against source docs files and/or built HTML."
        )
    )
    parser.add_argument(
        "--config",
        action="append",
        dest="configs",
        help=("Config file to validate (repeatable). Defaults to zensical.toml."),
    )
    parser.add_argument(
        "--check-source",
        action="store_true",
        help="Validate nav routes map to source docs files under docs/.",
    )
    parser.add_argument(
        "--check-built",
        action="store_true",
        help="Validate nav routes map to built HTML files under each config site_dir.",
    )
    args = parser.parse_args()

    configs = [Path(p) for p in (args.configs or DEFAULT_CONFIGS)]
    check_source = args.check_source or not (args.check_source or args.check_built)
    check_built = args.check_built or not (args.check_source or args.check_built)

    errors: list[str] = []
    for config_path in configs:
        if not config_path.exists():
            errors.append(f"[CONFIG] Missing config file: {config_path.as_posix()}")
            continue
        nav_paths, site_dir, site_prefix = _load_config(config_path)
        if check_source:
            errors.extend(_check_source(config_path, nav_paths=nav_paths))
        if check_built:
            errors.extend(_check_built(config_path, nav_paths=nav_paths, site_dir=site_dir))
            errors.extend(
                _check_built_prefixed(
                    config_path,
                    nav_paths=nav_paths,
                    site_dir=site_dir,
                    site_prefix=site_prefix,
                )
            )

    if errors:
        print("Docs nav route validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Docs nav route validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
