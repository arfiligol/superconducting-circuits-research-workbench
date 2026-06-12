#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

uv run python scripts/check_docs_nav_routes.py --check-source
uv run python scripts/check_docs_app_quarantine.py
./scripts/build_docs_sites.sh
uv run python scripts/check_docs_nav_routes.py --check-built

echo "Docs integrity verification passed."
