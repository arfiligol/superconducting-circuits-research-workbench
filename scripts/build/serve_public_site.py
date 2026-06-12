#!/usr/bin/env python3
"""Serve the built public documentation artifact for local preview."""

from __future__ import annotations

import argparse
import functools
import http.server
import os
import socketserver
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = ROOT_DIR / "site" / "dist"
BUILD_SCRIPT = ROOT_DIR / "scripts" / "build" / "build_public_site.sh"
REQUIRED_ENTRYPOINTS = (
    DIST_DIR / "index.html",
    DIST_DIR / "docs" / "index.html",
    DIST_DIR / "api" / "python" / "index.html",
    DIST_DIR / "api" / "julia" / "index.html",
)


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Serve site/dist locally so /docs/, /api/python/, and /api/julia/ "
            "can be previewed from one GitHub Pages-like artifact."
        )
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind. Use 0.0.0.0 for LAN access.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4173,
        help="Port for the local static server.",
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Rebuild the combined public site artifact before serving.",
    )
    return parser.parse_args()


def missing_entrypoints() -> list[Path]:
    return [path for path in REQUIRED_ENTRYPOINTS if not path.is_file()]


def artifact_needs_local_rebuild() -> bool:
    if "PUBLIC_BASE_PATH" in os.environ:
        return False

    index_path = DIST_DIR / "index.html"
    if not index_path.is_file():
        return False

    return f"/{ROOT_DIR.name}/" in index_path.read_text(encoding="utf-8")


def build_artifact() -> None:
    env = os.environ.copy()
    env.setdefault("PUBLIC_BASE_PATH", "")
    subprocess.run([str(BUILD_SCRIPT)], cwd=ROOT_DIR, check=True, env=env)


def ensure_artifact(force_build: bool) -> None:
    if force_build or missing_entrypoints() or artifact_needs_local_rebuild():
        build_artifact()

    missing = missing_entrypoints()
    if missing:
        formatted = "\n".join(f"- {path.relative_to(ROOT_DIR)}" for path in missing)
        raise SystemExit(f"Public site artifact is incomplete:\n{formatted}")


def main() -> int:
    args = parse_args()
    ensure_artifact(force_build=args.build)

    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=str(DIST_DIR),
    )

    try:
        with ReusableTCPServer((args.host, args.port), handler) as httpd:
            base_url = f"http://{args.host}:{args.port}"
            print(f"Serving {DIST_DIR.relative_to(ROOT_DIR)}")
            print(f"Public site: {base_url}/")
            print(f"Docs:        {base_url}/docs/")
            print(f"Python API:  {base_url}/api/python/")
            print(f"Julia API:   {base_url}/api/julia/")
            print("Press Ctrl-C to stop.")
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        return 0
    except OSError as exc:
        print(f"Could not start server on {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
