---
aliases:
  - Zensical Native Style
  - Zensical 原生文件風格
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/documentation
status: stable
owner: docs-team
audience: contributor
scope: 參考 writing-docs-with-zensical skill 後整理出的專案內 Zensical 原生文件風格規範。
version: v1.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Zensical Native Style

Use this page when you create or revise technical docs for the Native zh-TW Build. It captures the project-local version of the writing style from the `writing-docs-with-zensical` skill: lead with the current contract, keep pages practical, and use Zensical-native structure instead of dumping plain Markdown into the theme.

!!! info "How to use this page"
    這頁補充 `Standards`、`Information Layout` 與 `Style`。若它們和本頁衝突，以更具體的 owner page 為準；若只是語氣或呈現方式不同，優先採用本頁的 Zensical-native 寫法。

## Page Rhythm

Start each page with a short purpose paragraph. It should say what the topic does and why the reader needs it.

Lead with the happy path, then document caveats, unsupported cases, migration notes, and validation signals. Do not open a current SoT page with removed tools or historical implementations.

Use compact sections. Each section should answer one primary question, and examples should appear close to the workflow they explain.

## Writing Rules

- Use direct, practical wording.
- Lead with the current active contract.
- Keep historical context in notes, warnings, migration sections, or archive pages.
- Include exact commands only after confirming them from repo docs or config.
- Prefer examples over abstract explanation.
- Document failure modes and expected validation signals when they prevent repeated debugging.
- Avoid marketing language, internal team narration, and dense policy prose.

## Zensical Patterns

Use standard Markdown and the repo’s configured Zensical features:

- frontmatter for stable page metadata
- admonitions for important side information
- content tabs for variants that readers must compare
- Mermaid diagrams for architecture or workflow diagrams
- card grids only for overview/index pages
- relative Markdown links for internal docs
- fenced code blocks with language identifiers

!!! warning "Do not invent theme syntax"
    Do not add per-fence copy syntax, custom table-copy JavaScript, `mkdocs.yml`, or new Zensical site configuration unless the repo has explicitly adopted it.

## Validation

For docs changes, run the docs checks listed in `Build Commands` and `Testing`.
If the change touches navigation, frontmatter, links, or a new docs page, also check that the page appears through the intended directory route.

## Agent Rule { #agent-rule }

```markdown
## Zensical Native Style
- Write docs under `docs/` using the repo's Native zh-TW Build and `zensical.toml`; do not introduce `mkdocs.yml`.
- Start each page with a short purpose paragraph and lead with the current active contract.
- Put removed, superseded, or historical implementations in migration notes, warnings, unsupported-case sections, or archive pages, not in the opening narrative.
- Use compact sections, direct practical wording, and examples close to the workflow they explain.
- Use Zensical-native patterns: frontmatter, admonitions, content tabs, Mermaid diagrams, overview card grids, relative Markdown links, and fenced code blocks with language identifiers.
- Do not invent unvalidated theme syntax, per-fence copy hacks, table-copy JavaScript, or site config changes.
- Confirm exact commands from repo docs/config before documenting them.
- Run the relevant docs validation commands after documentation changes.
```
