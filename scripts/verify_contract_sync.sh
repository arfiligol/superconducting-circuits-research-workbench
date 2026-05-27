#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Checking backend OpenAPI drift..."
(cd "$REPO_ROOT/backend" && uv run python ../scripts/check_openapi_drift.py)

echo "==> Checking for uncommitted OpenAPI snapshot changes..."
cd "$REPO_ROOT"
if git diff --exit-code openapi.json; then
  echo "✅ Contract sync verification passed. OpenAPI snapshot is current."
else
  echo ""
  echo "❌ Contract drift detected! The backend OpenAPI snapshot has changes."
  echo "👉 Please run './scripts/sync_api_types.sh' locally and commit the updated OpenAPI artifacts."
  echo ""
  if [ -n "${GITHUB_ACTIONS:-}" ]; then
    echo "::error title=Contract Drift Detected::The backend OpenAPI snapshot has changed. Please run './scripts/sync_api_types.sh' locally and commit the updated OpenAPI artifacts."
  fi
  exit 1
fi
