#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Exporting OpenAPI spec from backend..."
(cd "$REPO_ROOT/app/backend" && uv run python ../../scripts/export_openapi.py)

echo "==> Generating TypeScript types..."
cd "$REPO_ROOT/app/frontend"
npx openapi-typescript "$REPO_ROOT/openapi.json" \
  --output src/lib/api/generated/schema.d.ts

echo "==> Done. Check app/frontend/src/lib/api/generated/schema.d.ts"
