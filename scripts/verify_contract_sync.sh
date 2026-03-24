#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Checking backend OpenAPI drift..."
(cd "$REPO_ROOT" && npm run openapi:check)

echo "==> Checking for uncommitted OpenAPI snapshot changes..."
cd "$REPO_ROOT"
if git diff --exit-code openapi.json; then
  echo "✅ Contract sync verification passed. OpenAPI snapshot is current."
else
  echo ""
  echo "❌ Contract drift detected! The backend OpenAPI snapshot has changes."
  echo "👉 Please run 'npm run openapi:export' locally and commit the updated openapi.json."
  echo ""
  if [ -n "${GITHUB_ACTIONS:-}" ]; then
    echo "::error title=Contract Drift Detected::The backend OpenAPI snapshot has changed. Please run 'npm run openapi:export' locally and commit the updated openapi.json."
  fi
  exit 1
fi
