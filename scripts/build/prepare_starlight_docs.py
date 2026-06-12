#!/usr/bin/env python3
"""Prepare Astro Starlight documentation content from the repo docs source."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml

ROOT_DIR = Path(__file__).resolve().parents[2]
DOCS_SOURCE = ROOT_DIR / "docs"
STARLIGHT_DOCS = ROOT_DIR / "site" / "src" / "content" / "docs" / "docs"
EXCLUDED_DIRS = {"api-reference", "javascripts", "site", "stylesheets"}
MARKUP_SUFFIXES = {".md", ".mdx"}
STARLIGHT_FRONTMATTER_KEYS = (
    "description",
    "editUrl",
    "head",
    "tableOfContents",
    "template",
    "hero",
    "lastUpdated",
    "prev",
    "next",
    "sidebar",
    "banner",
    "pagefind",
    "draft",
)


def split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text

    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text

    parsed = yaml.safe_load(text[4:end]) or {}
    frontmatter = parsed if isinstance(parsed, dict) else {}
    return frontmatter, text[end + 5 :]


def infer_title(frontmatter: dict[str, object], body: str, source_path: Path) -> str:
    title = frontmatter.get("title")
    if isinstance(title, str) and title:
        return title

    match = re.search(r"(?m)^#\s+(.+?)\s*$", body)
    if match:
        return re.sub(r"\s+\{#.+\}\s*$", "", match.group(1)).strip()

    if source_path.name == "index.md":
        return source_path.parent.name.replace("-", " ").title()
    return source_path.stem.replace("-", " ").title()


def strip_first_h1(body: str) -> str:
    lines = body.splitlines()
    prefix: list[str] = []
    for index, line in enumerate(lines):
        if not line.strip():
            prefix.append(line)
            continue
        if line.startswith("import ") or line.startswith("export "):
            prefix.append(line)
            continue
        if line.startswith("# "):
            remainder = lines[index + 1 :]
            while remainder and not remainder[0].strip():
                remainder.pop(0)
            rendered_prefix = "\n".join(prefix).strip()
            rendered_remainder = "\n".join(remainder).lstrip()
            if rendered_prefix and rendered_remainder:
                return f"{rendered_prefix}\n\n{rendered_remainder}\n"
            if rendered_prefix:
                return f"{rendered_prefix}\n"
            return f"{rendered_remainder}\n" if rendered_remainder else ""
        return body
    return body


def rewrite_markdown_links(body: str) -> str:
    pattern = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\s]+?\.mdx?)(#[^)]+)?\)")

    def replace(match: re.Match[str]) -> str:
        label, raw_url, anchor = match.groups()
        parsed = urlsplit(raw_url)
        if parsed.scheme or parsed.netloc:
            return match.group(0)

        path = parsed.path
        if path.endswith("/index.md"):
            path = path[: -len("index.md")]
        elif path.endswith("/index.mdx"):
            path = path[: -len("index.mdx")]
        elif path.endswith(".md"):
            path = f"{path[:-3]}/"
        elif path.endswith(".mdx"):
            path = f"{path[:-4]}/"

        rewritten = urlunsplit(("", "", path, parsed.query, ""))
        if anchor:
            rewritten = f"{rewritten}{anchor}"
        return f"[{label}]({rewritten})"

    return pattern.sub(replace, body)


def render_frontmatter(title: str, source_frontmatter: dict[str, object]) -> str:
    rendered: dict[str, object] = {"title": title}
    for key in STARLIGHT_FRONTMATTER_KEYS:
        if key in source_frontmatter:
            rendered[key] = source_frontmatter[key]

    lines = ["---", f"title: {json.dumps(title, ensure_ascii=False)}"]
    extra = {key: value for key, value in rendered.items() if key != "title"}
    if extra:
        dumped = yaml.safe_dump(extra, allow_unicode=True, sort_keys=False).rstrip()
        lines.extend(dumped.splitlines())
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def target_for(source_path: Path) -> Path | None:
    relative = source_path.relative_to(DOCS_SOURCE)
    if any(part in EXCLUDED_DIRS or part.startswith("docs_") for part in relative.parts):
        return None
    if relative.name.startswith("."):
        return None

    if source_path.suffix in MARKUP_SUFFIXES:
        if source_path.name.endswith(".en.md"):
            preferred = source_path.with_name(source_path.name.replace(".en.md", ".md"))
            preferred_mdx = preferred.with_suffix(".mdx")
            if preferred.exists() or preferred_mdx.exists():
                return None
            relative = relative.with_name(relative.name.replace(".en.md", ".md"))
        return STARLIGHT_DOCS / relative

    return STARLIGHT_DOCS / relative


def transform_markup(source_path: Path) -> str:
    text = source_path.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(text)
    title = infer_title(frontmatter, body, source_path)
    body = strip_first_h1(body)
    body = rewrite_markdown_links(body)
    return render_frontmatter(title, frontmatter) + body


def prepare() -> None:
    if STARLIGHT_DOCS.exists():
        shutil.rmtree(STARLIGHT_DOCS)
    STARLIGHT_DOCS.mkdir(parents=True, exist_ok=True)

    for source_path in DOCS_SOURCE.rglob("*"):
        if source_path.is_dir():
            continue

        target_path = target_for(source_path)
        if target_path is None:
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        if source_path.suffix in MARKUP_SUFFIXES:
            target_path.write_text(transform_markup(source_path), encoding="utf-8")
        else:
            shutil.copy2(source_path, target_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    prepare()
    print(f"Prepared Starlight docs at {STARLIGHT_DOCS.relative_to(ROOT_DIR)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
