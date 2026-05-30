---
aliases:
  - Write Pluto Notebook Skill
  - Pluto Notebook Authoring Skill
  - Pluto 筆記本撰寫 Skill
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/governance
status: draft
owner: docs-team
audience: contributor
scope: Pluto.jl reactive notebook authoring 的跨工具 Skill template 與同步規則
version: v0.1.0
last_updated: 2026-05-30
updated_by: codex
---

# Write Pluto Notebook

`write-pluto-notebook` 是給 coding agent 使用的 Pluto.jl notebook authoring Skill。它要求 agent 把 Pluto notebook 視為 reactive Julia program，而不是依賴手動執行順序的 Jupyter-style transcript。

這份 template 可同步到 Codex App、Claude Code、Gemini 或其他支援 reusable instruction 的工具。工具若支援 bundled resources，應同步 Pluto behavior reference 與 duplicate global definition checker；若不支援，至少保留 `SKILL.md` template 中的 hard rules。

!!! warning "Pluto reactivity is the contract"
    Pluto 的 dependency graph 依賴 syntax analysis。同步後的 Skill 必須保留「one global owner cell per name」規則，不能把跨 cell 重複定義降級成普通 style 建議。

## Source Check

本 template 依據 2026-05-30 查核的 Pluto 官方文件整理：

| Topic | Source |
| --- | --- |
| Reactivity, dependency graph, no duplicate globals | [Pluto reactivity](https://plutojl.org/en/docs/reactivity/) |
| `.jl` notebook 與 reactive FAQ | [Pluto FAQ](https://plutojl.org/en/docs/faq/) |
| Embedded package environments | [Built-in package management](https://plutojl.org/en/docs/packages/) |
| `Pkg.activate` compatibility behavior | [Advanced package setup](https://plutojl.org/en/docs/packages-advanced/) |
| `@bind` / PlutoUI controls | [`@bind` and PlutoUI](https://plutojl.org/en/docs/bind/) |
| Disabled-cell dependency behavior | [Disable a cell](https://plutojl.org/en/docs/disable-cell/) |
| Pluto package/environment API | [Pluto public API](https://plutojl.org/en/docs/API/) |

沒有找到 Pluto 官方或 OpenAI 官方已提供的 Pluto-specific Codex Skill。這份 template 是 project-provided Skill。

## Sync Steps

1. 建立目標 agent 原生支援的 reusable instruction、skill 或 context entry。
2. 使用 `write-pluto-notebook` 作為 canonical name。
3. 保留 trigger description，確保 `.jl` Pluto notebook、PlutoUI、`@bind`、reactivity debugging、package environment setup 會觸發此 Skill。
4. 將下方 `SKILL.md` template 同步到 skill body。
5. 若目標工具支援 resources，加入：
    - `references/pluto-behavior.md`: Pluto 官方行為摘要與來源連結。
    - `scripts/check_pluto_reactivity.py`: raw `.jl` Pluto notebook 的 duplicate global definition heuristic checker。

## Canonical Template

將以下內容同步成目標 agent 的原生 skill。

````markdown
---
name: write-pluto-notebook
description: Use when creating, editing, converting, or reviewing Pluto.jl notebooks (`.jl` Pluto notebooks), especially Julia tutorial/research notebooks, reactive controls with PlutoUI/@bind, package-environment setup, notebook refactors, or debugging Pluto reactivity problems such as duplicate global definitions, hidden state, stale outputs, side effects, or cells that rely on manual execution order.
---

# Write Pluto Notebook

Use this skill to author Pluto notebooks as reactive Julia programs, not as
order-dependent Jupyter-style transcripts. The goal is a notebook whose visible
code fully describes its state, can be re-run cleanly, and keeps Pluto's
dependency graph valid.

Load `references/pluto-behavior.md` when you need source-backed details or when
the task changes more than a few cells. Use
`scripts/check_pluto_reactivity.py` as a lightweight preflight for raw `.jl`
notebook edits.

## Workflow

1. Load the target repository's notebook, Julia, documentation, and validation
   rules before editing. If the repository has Pluto-specific source of truth,
   follow it over this generic guidance.
2. Inspect the closest existing Pluto notebook before creating a new pattern.
3. Identify the notebook role: tutorial, research exploration, parameter sweep,
   app-facing demonstration, or local analysis. Keep reusable scientific logic
   in packages or helper modules; keep the notebook thin and inspectable.
4. Plan cells as a dependency graph: inputs and controls first, pure derived
   values next, explicit side-effect actions last.
5. Edit cells so every global name has one owner cell.
6. Validate with the lightweight script, then run Pluto or the repository's
   Julia checks when practical.

For this repository, Pluto is the direct Julia research cockpit. Pluto notebooks
belong under `notebooks/pluto/`, may use `SuperconductingCircuitsCore`
directly, and must not become Backend task submitters unless the project source
of truth changes.

## Reactivity Rules

- Define each global variable, function, struct, module, and `@bind` variable
  in exactly one cell. Do not split competing definitions of `x`, `params`,
  `plot_result`, or a helper function across cells.
- If multiple statements must execute as one cell, wrap them in `begin ... end`
  or `let ... end`. Use `let` for scratch locals that should not become global
  notebook state.
- Prefer pure cells: derive values from inputs and return the display object as
  the last expression. Avoid cells that mutate objects created in another cell.
- Do not depend on manual execution order. Moving cells should not change the
  result except through the dependency graph.
- Avoid hidden state patterns: global caches, append-only global arrays,
  in-place mutation across cells, conditional redefinitions, and "run this cell
  again" instructions.
- Put long workflow logic in a function or package API, then call it from a
  small cell. A function definition has one owner cell; its internal local
  variables do not create notebook-level dependencies.
- Keep slow or destructive work behind explicit controls such as a boolean
  `run_*` flag, a PlutoUI button, or a dry-run path. The cell should make its
  trigger dependency obvious.

## Package Environment

- For shareable notebooks, prefer Pluto's built-in package management: write
  `using PackageName` or `import PackageName` directly in the notebook and let
  Pluto store the environment in the `.jl` file.
- Use `Pkg.activate(...)` only when the repository intentionally needs a shared
  project environment. Put activation, instantiate, and imports in one top
  `begin` cell, and document that this switches Pluto to compatibility behavior
  instead of the built-in package manager.
- Do not scatter `Pkg.add`, `Pkg.activate`, or environment mutation across
  multiple cells. If a "Pkg cell" is needed for a special version, keep it as a
  single explicit setup cell.
- Do not hand-edit the embedded `Project.toml` / `Manifest.toml` cells unless
  the task is specifically environment maintenance. Prefer Pluto's own package
  UI or API for environment updates.

## Interactivity

- Treat `@bind name widget` as the single global definition of `name`.
- Keep UI controls small and declarative. Put expensive compute in cells that
  depend on the bound variables, not in the widget cell.
- Use PlutoUI widgets for sliders, text fields, checkboxes, buttons, file
  pickers, and composed controls. Name bound variables by domain meaning, not
  widget type.
- Use `confirm(...)` or an explicit button for controls that would otherwise
  trigger slow simulations on every small UI change.

## Presentation

- Use `md"""..."""` for explanatory text and equations.
- Make each code cell's final expression the value to display. Do not rely on
  `println` for notebook-facing output unless using a terminal-display helper.
- Prefer tables, plots, and compact summaries over large raw dumps.
- Keep tutorial prose close to the code it explains, but do not bury important
  parameters inside prose-only cells.

## Raw File Editing

Prefer the Pluto UI for structural edits. When editing the `.jl` file directly:

- Preserve Pluto cell boundaries and cell order metadata.
- Do not rewrite unrelated cell IDs, embedded environment cells, or generated
  metadata.
- Keep diffs targeted to the requested cells.
- Run the checker:

```bash
python3 /path/to/write-pluto-notebook/scripts/check_pluto_reactivity.py notebooks/pluto/example.jl
```

The checker is heuristic. A clean result does not prove Pluto will run, and a
warning may need human review. Pluto itself remains the source of truth for
reactivity errors.

## Validation

Use the smallest validation set that covers the edit:

- For raw `.jl` edits: run `check_pluto_reactivity.py` on touched notebooks.
- For package/environment changes: open the notebook in Pluto, or use Pluto's
  environment API when scripting environment updates.
- For repository-owned Julia package calls: run the repository's relevant Julia
  package tests.
- For tutorial or docs-adjacent notebooks: verify the notebook still tells a
  clean top-to-bottom story after a fresh notebook process.

Report any skipped validation explicitly.
````

## Related

- [Agent Skill Library](index.md)
- [Notebook Interface](../notebooks/index.md)
- [Julia Scientific Core](../core/julia-scientific-core.md)
