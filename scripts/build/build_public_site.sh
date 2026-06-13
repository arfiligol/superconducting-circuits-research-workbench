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

uv run python scripts/check_docs_language.py
npm run build --prefix site
uv run python scripts/check_docs_nav_routes.py --check-built
./scripts/build/build_api_docs.sh

API_DEST="site/dist/api"
rm -rf "${API_DEST}"
mkdir -p "${API_DEST}/python" "${API_DEST}/julia"
rsync -a --delete build/api-reference/python/html/ "${API_DEST}/python/"
rsync -a --delete build/api-reference/julia/html/ "${API_DEST}/julia/"
cat > "${API_DEST}/versions.js" <<'EOF'
var DOC_VERSIONS = [
];
EOF
cat > "${API_DEST}/julia/siteinfo.js" <<'EOF'
var DOCUMENTER_VERSION_SELECTOR_DISABLED = true;
EOF

uv run python scripts/build/check_api_reference_links.py
