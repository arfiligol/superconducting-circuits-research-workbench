---
aliases:
  - Linting & Formatting
  - Lint 與格式化
tags:
  - diataxis/reference
  - audience/contributor
  - sot/true
  - topic/execution
status: stable
owner: docs-team
audience: contributor
scope: rewrite branch 的 Python、frontend、desktop 與 Julia lint / format / type-check 規範。
version: v3.0.0
last_updated: 2026-05-28
updated_by: codex
---

# Linting & Formatting

!!! info "How to use this page"
    這頁只回答格式化、lint、type-check 的日常執行方式。需要測試層級或 merge gate 時，分別看 `Testing` 與 `CI Gates`。

## Tooling

- Python: Ruff + BasedPyright
- Frontend/Desktop: project-local lint / format / typecheck commands
- Julia: package-local tests and formatter when configured
- Repo gate: pre-commit（若 hook 已設置）

## Command Map

=== "Python / Repo"

    ```bash
    uv run ruff format .
    uv run ruff check .
    uv run basedpyright app/backend/app_backend core/analysis core/python core/sc_core core/shared core/simulation scripts
    uv run pre-commit run --all-files
    ```

=== "Frontend"

    ```bash
    npm run lint --prefix app/frontend
    npm run format --prefix app/frontend
    npm run typecheck --prefix app/frontend
    ```

=== "Desktop"

    ```bash
    npm run lint --prefix app/desktop
    npm run build --prefix app/desktop
    ```

=== "Julia"

    ```bash
    julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'
    julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'
    ```

## Policy

| 規則 | 說明 |
| --- | --- |
| touched files 不接受新增 lint error | 不可把既有噪音當成新增問題的遮羞布 |
| 型別錯誤優先修正 | 不以忽略規則掩蓋結構問題 |
| frontend 未建立前維持 Python/docs baseline | 建立後即納入常規 gate |

!!! tip "Good default"
    小範圍改動至少應先跑 touched area 對應的 format、lint 與 type-check；不要把整個 repo gate 留到 commit 前才第一次發現問題。

## Agent Rule { #agent-rule }

```markdown
## Lint / Format Commands
- **Python format**: `uv run ruff format .`
- **Python lint**: `uv run ruff check .`
- **Python type check**: `uv run basedpyright app/backend/app_backend core/analysis core/python core/sc_core core/shared core/simulation scripts`
- **Pre-commit**: `uv run pre-commit run --all-files`
- **Frontend lint**: `npm run lint --prefix app/frontend`
- **Frontend format**: `npm run format --prefix app/frontend`
- **Frontend typecheck**: `npm run typecheck --prefix app/frontend`
- **Desktop lint/build**: `npm run lint --prefix app/desktop` and `npm run build --prefix app/desktop`
- **Julia package checks**: `julia --project=core/julia/SuperconductingCircuitsCore -e 'using Pkg; Pkg.test()'`, `julia --project=core/julia/SuperconductingCircuitsVisualizer -e 'using Pkg; Pkg.test()'`, `julia --project=core/julia/SuperconductingCircuitsRunner -e 'using Pkg; Pkg.test()'`, and `JULIA_PYTHONCALL_EXE="$PWD/.venv/bin/python" julia --project=core/julia/SuperconductingCircuitsAnalysisBridge -e 'using Pkg; Pkg.test()'`
- **Policy**: no new lint or type errors in touched areas.
```
