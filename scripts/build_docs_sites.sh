#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

SOURCE_CONFIG="${ZENSICAL_CONFIG:-zensical.toml}"
CONFIG_PATH="${SOURCE_CONFIG}"
TEMP_STEM=""
TEMP_CONFIG=""

cleanup() {
  if [ -n "${TEMP_STEM}" ] && [ -f "${TEMP_STEM}" ]; then
    rm -f "${TEMP_STEM}"
  fi
  if [ -n "${TEMP_CONFIG}" ] && [ -f "${TEMP_CONFIG}" ]; then
    rm -f "${TEMP_CONFIG}"
  fi
}
trap cleanup EXIT

if [ -n "${DOCS_SITE_URL:-}" ]; then
  TEMP_STEM="$(mktemp ".zensical-public.XXXXXX")"
  TEMP_CONFIG="${TEMP_STEM}.toml"
  rm -f "${TEMP_STEM}"
  uv run python - "${SOURCE_CONFIG}" "${TEMP_CONFIG}" "${DOCS_SITE_URL}" <<'PY'
from pathlib import Path
import re
import sys

source_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
site_url = sys.argv[3]

text = source_path.read_text(encoding="utf-8")
text, count = re.subn(r'(?m)^site_url = ".*"$', f'site_url = "{site_url}"', text, count=1)
if count != 1:
    raise SystemExit(f"Expected exactly one site_url entry in {source_path}")
target_path.write_text(text, encoding="utf-8")
PY
  CONFIG_PATH="${TEMP_CONFIG}"
fi

read -r SITE_ROOT SITE_PREFIX < <(uv run python - "${CONFIG_PATH}" <<'PY'
from urllib.parse import urlparse
import tomllib
from pathlib import Path
import sys

data = tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
site_dir = str(data.get("project", {}).get("site_dir", "docs/site"))
site_url = str(data.get("project", {}).get("site_url", ""))
print(site_dir, urlparse(site_url).path.strip("/"))
PY
)

if [ -z "${SITE_ROOT}" ] || [ "${SITE_ROOT}" = "." ] || [ "${SITE_ROOT}" = "/" ]; then
  echo "Refusing to remove unsafe Zensical site_dir: ${SITE_ROOT}" >&2
  exit 1
fi

uv run python scripts/check_docs_nav_routes.py --config "${CONFIG_PATH}" --check-source

bash ./scripts/prepare_docs_locales.sh

rm -rf "${SITE_ROOT}"

uv run --group dev zensical build -f "${CONFIG_PATH}"

if [ -n "${SITE_PREFIX}" ]; then
  mkdir -p "${SITE_ROOT}/${SITE_PREFIX}"
  rsync -a --delete \
    --exclude "${SITE_PREFIX}/" \
    "${SITE_ROOT}/" "${SITE_ROOT}/${SITE_PREFIX}/"
fi

uv run python scripts/check_docs_nav_routes.py --config "${CONFIG_PATH}" --check-built
