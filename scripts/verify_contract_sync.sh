#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Checking backend OpenAPI drift..."
(cd "$REPO_ROOT" && npm run openapi:check)

echo "==> Running sync_api_types.sh..."
"$SCRIPT_DIR/sync_api_types.sh"

echo "==> Checking for uncommitted changes in generated files..."
cd "$REPO_ROOT"
if git diff --exit-code openapi.json frontend/src/lib/api/generated/schema.d.ts; then
  echo "✅ Contract sync verification passed. No drift detected."
else
  echo ""
  echo "❌ Contract drift detected! The backend OpenAPI spec or generated schema.d.ts has changes."
  echo "👉 Please run './scripts/sync_api_types.sh' (or 'npm run sync:types') locally and commit the differences."
  echo ""
  if [ -n "${GITHUB_ACTIONS:-}" ]; then
    echo "::error title=Contract Drift Detected::The backend OpenAPI spec or generated schema has changed. Please run 'npm run sync:types' locally and commit the changes."
  fi
  exit 1
fi
