"""Development-only docs site command wrapper."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

PROJECT_NAME = "superconducting-circuits-research-workbench"


def find_repo_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        pyproject = candidate / "pyproject.toml"
        if not pyproject.is_file():
            continue

        with pyproject.open("rb") as file:
            metadata = tomllib.load(file)

        if metadata.get("project", {}).get("name") == PROJECT_NAME:
            return candidate

    raise SystemExit(f"Could not find {PROJECT_NAME!r} repo root from {start}")


def run_serve(args: list[str]) -> int:
    repo_root = find_repo_root(Path.cwd().resolve())
    serve_script = repo_root / "scripts" / "build" / "serve_public_site.py"
    try:
        return subprocess.run([sys.executable, str(serve_script), *args], cwd=repo_root).returncode
    except KeyboardInterrupt:
        return 130


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docs-site",
        description="Development-only helper for the local documentation site artifact.",
    )
    parser.add_argument("command", choices=("serve",), help="Command to run.")
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the selected command.",
    )

    namespace = parser.parse_args(argv)

    if namespace.command == "serve":
        return run_serve(namespace.args)

    parser.error(f"unsupported command: {namespace.command}")
    return 2
