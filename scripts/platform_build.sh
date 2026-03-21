#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[platform-build] backend startup smoke"
(
  cd "$ROOT_DIR/backend"
  uv run python - <<'PY'
from src.app.main import app

print(app.title)
PY
)

echo "[platform-build] frontend"
npm run build --prefix "$ROOT_DIR/frontend"

echo "[platform-build] desktop"
npm run build --prefix "$ROOT_DIR/desktop"

echo "[platform-build] complete"
