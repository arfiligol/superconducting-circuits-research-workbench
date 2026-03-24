#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[rewrite-check] backend"
(
  cd "$ROOT_DIR/backend"
  uv run pytest -q
)

echo "[rewrite-check] frontend unit tests"
npm run test --prefix "$ROOT_DIR/frontend"

echo "[rewrite-check] desktop lint"
npm run lint --prefix "$ROOT_DIR/desktop"

echo "[rewrite-check] complete"
