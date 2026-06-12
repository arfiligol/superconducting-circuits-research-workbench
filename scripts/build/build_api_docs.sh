#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

TARGET="${1:-all}"

build_python_api() {
  uv run sphinx-build -W --keep-going \
    -b html \
    docs/api-reference/python/source \
    build/api-reference/python/html
}

build_julia_api() {
  julia --project=docs/api-reference/julia -e 'using Pkg; Pkg.instantiate()'
  julia --project=docs/api-reference/julia docs/api-reference/julia/make.jl
}

case "${TARGET}" in
  all)
    build_python_api
    build_julia_api
    ;;
  python)
    build_python_api
    ;;
  julia)
    build_julia_api
    ;;
  *)
    echo "Usage: $0 [all|python|julia]" >&2
    exit 2
    ;;
esac
