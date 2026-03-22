#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

mkdir -p "$ROOT_DIR/.cache/npm/frontend" "$ROOT_DIR/.cache/npm/desktop"

echo "[platform-install] root python env"
(
  cd "$ROOT_DIR"
  uv sync
)

echo "[platform-install] backend python env"
(
  cd "$ROOT_DIR/backend"
  uv sync
)

echo "[platform-install] frontend"
npm install --prefix "$ROOT_DIR/frontend" --cache "$ROOT_DIR/.cache/npm/frontend"

echo "[platform-install] desktop"
npm install --prefix "$ROOT_DIR/desktop" --cache "$ROOT_DIR/.cache/npm/desktop"

echo "[platform-install] complete"
