#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

PUBLIC_SITE_URL="${PUBLIC_SITE_URL:-https://arfiligol.github.io}"
PUBLIC_BASE_PATH="${PUBLIC_BASE_PATH-/superconducting-circuits-research-workbench}"

PUBLIC_BASE_PATH="$(uv run python - "${PUBLIC_BASE_PATH}" <<'PY'
import sys

base = sys.argv[1].strip()
if base in {"", "/"}:
    print("")
else:
    print("/" + base.strip("/"))
PY
)"

export PUBLIC_SITE_URL
export PUBLIC_BASE_PATH

npm run build --prefix site

DOCS_SITE_URL="$(uv run python - "${PUBLIC_SITE_URL}" "${PUBLIC_BASE_PATH}" <<'PY'
import sys

site_url = sys.argv[1].rstrip("/")
base = sys.argv[2].strip("/")
path = "/".join(part for part in (base, "docs") if part)
print(f"{site_url}/{path}/" if path else f"{site_url}/docs/")
PY
)"

DOCS_SITE_URL="${DOCS_SITE_URL}" ./scripts/build_docs_sites.sh

DOCS_DEST="site/dist/docs"
rm -rf "${DOCS_DEST}"
mkdir -p "${DOCS_DEST}"

EXCLUDED_PREFIX="$(uv run python - "${DOCS_SITE_URL}" <<'PY'
from urllib.parse import urlparse
import sys

parts = [part for part in urlparse(sys.argv[1]).path.strip("/").split("/") if part]
print(parts[0] if parts else "")
PY
)"

RSYNC_EXCLUDES=()
if [ -n "${EXCLUDED_PREFIX}" ]; then
  RSYNC_EXCLUDES+=(--exclude "${EXCLUDED_PREFIX}/")
fi

rsync -a --delete "${RSYNC_EXCLUDES[@]}" docs/site/ "${DOCS_DEST}/"
