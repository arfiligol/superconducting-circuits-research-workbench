"""Check deployed API reference entrypoints and cross-links."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE_DIST = ROOT / "site" / "dist"


def _read_required(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"Missing required API reference artifact: {path}")
    return path.read_text(encoding="utf-8")


def _require_contains(path: Path, html: str, needles: list[str]) -> None:
    missing = [needle for needle in needles if needle not in html]
    if missing:
        formatted = ", ".join(missing)
        raise SystemExit(f"{path} is missing required link text/path: {formatted}")


def main() -> None:
    docs_index = SITE_DIST / "docs" / "index.html"
    python_index = SITE_DIST / "api" / "python" / "index.html"
    julia_index = SITE_DIST / "api" / "julia" / "index.html"
    julia_siteinfo = SITE_DIST / "api" / "julia" / "siteinfo.js"
    api_versions = SITE_DIST / "api" / "versions.js"

    docs_html = _read_required(docs_index)
    python_html = _read_required(python_index)
    julia_html = _read_required(julia_index)
    _read_required(julia_siteinfo)
    _read_required(api_versions)

    _require_contains(docs_index, docs_html, ["api/python", "api/julia"])
    _require_contains(python_index, python_html, ["../../docs/", "../julia/"])
    _require_contains(julia_index, julia_html, ["../../docs/", "../python/"])


if __name__ == "__main__":
    main()
